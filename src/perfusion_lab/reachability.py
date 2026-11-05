"""Development candidate: calibration-consistent sets and joint braking loss.

Engineering assumptions only: bounded calibration error, approximately constant
venous offset over four anchors, retained pump dynamics and future inflow floor.
Gaussian noise and unmodelled/shared corruption can invalidate these sets.
"""
import math
from functools import lru_cache
import numpy as np
from .integrity import ReferenceGuard
from .model_bank import ModelBankGuard, ModelBankController
from .control import Decision
from .model import oxygen_content, delivery


def clip_polygon(vertices, normal, limit):
    """Intersect a convex (offset L, venous bias L/min) polygon with a halfplane."""
    result = []
    if not vertices: return result
    previous = vertices[-1]
    prev = normal[0]*previous[0]+normal[1]*previous[1]-limit
    for current in vertices:
        now = normal[0]*current[0]+normal[1]*current[1]-limit
        if (prev <= 1e-12) != (now <= 1e-12):
            ratio = prev/(prev-now)
            result.append(tuple(previous[j]+ratio*(current[j]-previous[j]) for j in (0,1)))
        if now <= 1e-12: result.append(current)
        previous, prev = current, now
    return result


class ConsistentGuard(ModelBankGuard):
    def __init__(self, *args, interval_mode='consistent', **kwargs):
        if interval_mode not in ('legacy','consistent'): raise ValueError('Unknown interval mode')
        super().__init__(*args, **kwargs)
        self.interval_mode, self.polygons = interval_mode, []

    def update(self, obs, routine, calibrations):
        if self.interval_mode == 'legacy': return super().update(obs, routine, calibrations)
        self.mass_history[round(obs.time,9)] = self.mass.copy()
        state = ReferenceGuard.update(self, obs, routine, calibrations)
        changed = False
        for sample in calibrations:
            if self.samples and sample.acquired <= self.samples[-1][0]: continue
            self.samples.append((sample.acquired,sample.value,self.mass_history[round(sample.acquired,9)].copy()))
            changed = True
        self.samples = self.samples[-4:]
        if changed and len(self.samples) >= 2:
            last = self.samples[-1][0]
            self.polygons = []
            for model in range(len(self.taus)):
                zlast = self.samples[-1][1]-self.samples[-1][2][model]
                vertices = [(zlast-self.cal_error,-2.),(zlast+self.cal_error,-2.),
                            (zlast+self.cal_error,2.),(zlast-self.cal_error,2.)]
                for time,value,mass in self.samples:
                    elapsed = (time-last)/60.
                    z = value-mass[model]
                    error = self.cal_error+self.model_error*abs(elapsed)
                    vertices = clip_polygon(vertices,(1.,-elapsed),z+error)
                    vertices = clip_polygon(vertices,(-1.,elapsed),-z+error)
                if vertices: self.polygons.append((model,vertices))
        lower, upper = state['lower'], state['estimate']+state['uncertainty']
        supported = False; conflict = False; bank_lower = bank_upper = None
        bias_upper = 2.; models = []
        if self.polygons and obs.time-self.samples[-1][0] <= self.max_age:
            age = (obs.time-self.samples[-1][0])/60.
            lows, highs, biases = [], [], []
            for model,vertices in self.polygons:
                values = [self.mass[model]+offset-bias*age for offset,bias in vertices]
                lows.append(min(values)-self.model_error*age)
                highs.append(max(values)+self.model_error*age)
                biases.extend(bias for _,bias in vertices)
                models.append((float(self.taus[model]),float(self.flows[model])))
            bank_lower,bank_upper = min(lows),max(highs)
            bias_upper = max(biases)+self.model_error
            conflict = not state['quarantined'] and (lower > bank_upper or upper < bank_lower)
            if conflict:
                lower,upper = min(lower,bank_lower),max(upper,bank_upper)
            else:
                # The inline channel may signal a conflict, but agreement does
                # not justify trimming the independent calibration/model set.
                lower,upper = bank_lower,bank_upper
                supported = True
        state.update(estimate=max(0.,(lower+upper)/2.),lower=max(0.,lower),
            uncertainty=max(0.,(upper-lower)/2.),supported=supported,bank_supported=supported,
            bank_conflict=conflict,bank_lower=bank_lower,bank_upper=bank_upper,
            active_models=len(models),venous_bias_upper=bias_upper,pump_models=models)
        return state


@lru_cache(maxsize=128)
def _ramp_terms(taus, dt, count):
    taus = np.asarray(taus,dtype=float)[:,None]
    a = np.exp(-dt/taus)
    steps = np.arange(1,count+1,dtype=float)[None,:]
    return a,steps,a**steps


def joint_braking_reserve(models, command, qin, dt=1., slew=.15):
    """Maximum prefix net loss for one command then maximum braking to zero.

    Includes every finite ramp prefix and an analytic infinite zero-command tail.
    Conditional on a retained first-order model and constant future inflow >=qin.
    It uses no actual future drainage or hidden plant parameters.
    """
    if not models: return 0.
    if not all(math.isfinite(v) for v in (command,qin,dt,slew)) or min(command,qin)<0 or min(dt,slew)<=0:
        raise ValueError('Invalid braking inputs')
    if any(not math.isfinite(t) or t<=0 or not math.isfinite(f) or f<0 for t,f in models):
        raise ValueError('Invalid pump hypotheses')
    n = max(1,math.ceil(command/(slew*dt)))
    taus = tuple(t for t,_ in models)
    a,m,power = _ramp_terms(taus,dt,n)
    flow = np.asarray([f for _,f in models])[:,None]
    decrement = slew*dt
    constant = flow-command-decrement/(1.-a)
    prefix = (m*(command+decrement/(1.-a)-qin)-decrement*m*m/2.
              +constant*(1.+a)/2.*(1.-power)/(1.-a))*dt/60.
    last_flow = command-decrement*n+decrement/(1.-a)+power[:,-1:]*constant
    # Formula remains valid at command=0 (one interval held at zero).
    last_flow = np.maximum(0.,last_flow)
    average = last_flow*(1.+a)/2.
    if qin == 0:
        tail = average/(1.-a)*dt/60.
    else:
        positive = average > qin
        count = np.zeros_like(average)
        count[positive] = np.ceil(np.log(qin/average[positive])/np.log(a[positive]))
        tail = (average*(1.-a**count)/(1.-a)-qin*count)*dt/60.
    return max(0.,float(np.max(prefix)),float(np.max(prefix[:,-1:]+tail)))


class ReachabilityController(ModelBankController):
    def __init__(self,*args,reserve_mode='joint',**kwargs):
        if reserve_mode not in ('legacy','joint'): raise ValueError('Unknown reserve mode')
        super().__init__(*args,**kwargs)
        self.reserve_mode = reserve_mode

    def decide(self, obs, belief):
        if self.reserve_mode == 'legacy' or self.kind == 'pi': return super().decide(obs,belief)
        state = self.reference_state
        if state is None: raise ValueError('Reference state required')
        self.pi.previous = self.previous
        base = self.pi.decide(obs,belief)
        low,high = max(0.,self.previous-.15*self.dt),min(7.,self.previous+.15*self.dt)
        high = max(low,min(high,self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))))
        if obs.pressure > 90.: high = low
        enabled = state['bank_supported']
        self.weight = min(self.weight+self.dt/10.,max(self.weight-self.dt/10.,float(enabled)))
        qin = max(0.,belief.venous_flow-state['venous_bias_upper']-self.allowance)
        budget = max(0.,obs.reservoir-.29)
        loss = lambda command: joint_braking_reserve(state['pump_models'],command,qin,self.dt)
        feasible = obs.reservoir >= .29 and loss(low) <= budget
        cap = high
        if enabled:
            if not feasible: cap = low
            elif loss(high) > budget:
                left,right = low,high
                for _ in range(18):
                    mid = (left+right)/2.
                    if loss(mid) <= budget: left = mid
                    else: right = mid
                cap = left
        requested = base.command
        if enabled and obs.pressure < 85. and obs.reservoir > self.recovery_floor:
            recovery = min(1.,(obs.reservoir-self.recovery_floor)/.1)
            requested += self.weight*recovery*(high-base.command)
        applied = min(high,max(low,min(requested,cap)))
        self.pi.core.track(applied);self.pi.previous = applied;self.previous = applied
        self.last_debug = dict(control_level_lower=obs.reservoir,override_weight=self.weight,
            override_eligible=enabled,override_delta=applied-base.command,pi_command=base.command,
            braking_volume=loss(applied),braking_budget=budget,predictive_feasible=feasible)
        return Decision(applied,enabled and not feasible,delivery(applied,belief.hb_lower,obs.sao2,self.bsa))
