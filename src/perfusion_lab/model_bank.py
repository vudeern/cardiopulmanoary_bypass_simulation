"""Calibration-constrained pump-model bank and conditional discrete reserve.

Intervals are engineering sets, not statistical confidence or safety proofs.
Shared calibration bias, changing venous bias and unmodelled pump dynamics can
invalidate them. Only delivered measurements and applied commands are used.
"""
import math
import numpy as np
from .integrity import ReferenceGuard
from .simc import MatchedSupervisor
from .control import Decision
from .model import oxygen_content,delivery


class ModelBankGuard(ReferenceGuard):
    def __init__(self,initial_flow,dt=1.,*,calibration_error=.04,model_error_flow=.1,
                 model_taus=(1.,2.,4.,8.,12.),fit_tolerance=.04,**options):
        values=(calibration_error,model_error_flow,fit_tolerance,*model_taus)
        if not model_taus or not all(math.isfinite(v) for v in values) or min(values)<0 or min(model_taus)<=0:raise ValueError('Invalid model bank settings')
        super().__init__(initial_flow,dt,**options)
        self.taus=np.array(model_taus,dtype=float);self.flows=np.full(len(model_taus),initial_flow,dtype=float)
        self.mass=np.zeros(len(model_taus));self.mass_history={};self.samples=[]
        self.cal_error,self.model_error,self.fit_tolerance=calibration_error,model_error_flow,fit_tolerance
        self.fit=None

    def update(self,obs,routine,calibrations):
        self.mass_history[round(obs.time,9)]=self.mass.copy()
        state=super().update(obs,routine,calibrations)
        changed=False
        for sample in calibrations:
            if self.samples and sample.acquired<=self.samples[-1][0]:continue
            self.samples.append((sample.acquired,sample.value,self.mass_history[round(sample.acquired,9)].copy()));changed=True
        self.samples=self.samples[-4:]
        if changed and len(self.samples)>=2:
            t=np.array([s[0] for s in self.samples]);values=np.array([s[1] for s in self.samples]);integrals=np.array([s[2] for s in self.samples])
            centered=t-t.mean();ss=float(centered@centered)
            z=values[:,None]-integrals;mean=z.mean(axis=0);slope=centered@z/ss
            errors=np.max(np.abs(z-(mean[None,:]+centered[:,None]*slope[None,:])),axis=0)
            bias=-60.*slope;active=(errors<=self.fit_tolerance)&(np.abs(bias)<=2.)
            self.fit=dict(t=t,centered=centered,ss=ss,mean=mean,slope=slope,error=errors,bias=bias,active=active)
        lower,upper=state['lower'],state['estimate']+state['uncertainty'];conflict=False;usable=False
        bank_lower=bank_upper=None;active_count=0;bias_upper=2.
        if self.fit is not None:
            f=self.fit;mask=f['active'];active_count=int(mask.sum());age=obs.time-self.samples[-1][0]
            if active_count and age<=self.max_age:
                weights=1./len(f['t'])+(obs.time-f['t'].mean())*f['centered']/f['ss']
                band=self.cal_error*float(np.abs(weights).sum())+self.model_error*age/60.
                prediction=self.mass+f['mean']+f['slope']*(obs.time-f['t'].mean())
                bank_lower=float(np.min((prediction-band-f['error'])[mask]));bank_upper=float(np.max((prediction+band+f['error'])[mask]))
                slope_error=60.*self.cal_error*float(np.abs(f['centered']/f['ss']).sum())
                bias_upper=float(np.max(f['bias'][mask]))+slope_error+self.model_error
                if state['quarantined']:
                    # Routine information is not needed when the independent
                    # calibration/model path is sufficiently supported.
                    lower,upper=bank_lower,bank_upper;usable=True
                else:
                    lower=max(lower,bank_lower);upper=min(upper,bank_upper)
                    conflict=lower>upper
                    if conflict:lower=min(state['lower'],bank_lower);upper=max(state['estimate']+state['uncertainty'],bank_upper)
                    else:usable=True
        state.update(estimate=max(0.,(lower+upper)/2.),lower=max(0.,lower),uncertainty=max(0.,(upper-lower)/2.),
            supported=usable,bank_supported=usable,bank_conflict=conflict,bank_lower=bank_lower,bank_upper=bank_upper,
            active_models=active_count,venous_bias_upper=bias_upper,
            pump_models=[(float(t),float(x)) for t,x,a in zip(self.taus,self.flows,self.fit['active'] if self.fit is not None else [False]*len(self.taus)) if a])
        return state

    def advance(self,command,measured_venous):
        next_flow=command+(self.flows-command)*np.exp(-self.dt/self.taus)
        self.mass+=(measured_venous-(self.flows+next_flow)/2.)*self.dt/60.;self.flows=next_flow
        super().advance(command,measured_venous)


def discrete_reserve(initial_excess,tau,command_excess,slew,dt):
    """Conditional bound for a one-step command followed by discrete braking."""
    if min(initial_excess,command_excess)<0 or min(tau,slew,dt)<=0 or not all(math.isfinite(v) for v in (initial_excess,tau,command_excess,slew,dt)):raise ValueError('Invalid reserve inputs')
    a=math.exp(-dt/tau);initial=initial_excess*dt/120.*(1+a)/(1-a)
    n=math.ceil(command_excess/(slew*dt)) if command_excess else 0
    command_area=n*command_excess-slew*dt*n*(n-1)/2.
    return initial+command_area*dt/60.


class ModelBankController:
    def __init__(self,kind,bsa,dt=1.,target=280.,*,tau_c=5.,target_level=.65,flow_allowance=.1,recovery_floor=.6):
        if kind not in ('hybrid','pi') or not math.isfinite(flow_allowance) or flow_allowance<0 or not math.isfinite(recovery_floor) or recovery_floor<=.25:raise ValueError('Invalid model controller settings')
        self.kind,self.bsa,self.dt,self.target,self.allowance=kind,bsa,dt,target,flow_allowance
        self.pi=MatchedSupervisor('simc',bsa,dt,target,tau_c=tau_c,target_level=target_level)
        self.recovery_floor=recovery_floor
        self.previous=2.4*bsa;self.weight=0.;self.reference_state=None;self.last_debug={}

    def set_reference_state(self,state):self.reference_state=state

    def decide(self,obs,belief):
        s=self.reference_state
        if s is None:raise ValueError('Model bank state required')
        self.pi.previous=self.previous;base=self.pi.decide(obs,belief)
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        high=max(low,min(high,self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))))
        if obs.pressure>90.:high=low
        enabled=self.kind=='hybrid' and s['bank_supported'];desired=float(enabled)
        self.weight=min(self.weight+self.dt/10.,max(self.weight-self.dt/10.,desired))
        qin=max(0.,belief.venous_flow-s['venous_bias_upper']-self.allowance)
        budget=max(0.,obs.reservoir-.25-.04)
        initial=max((discrete_reserve(max(0.,flow-qin),tau,0.,.15,self.dt) for tau,flow in s['pump_models']),default=0.)
        loss=lambda u:initial+discrete_reserve(0.,1.,max(0.,u-qin),.15,self.dt)
        feasible=obs.reservoir>=.29 and loss(low)<=budget
        cap=high
        if enabled:
            if not feasible:cap=low
            elif loss(high)>budget:
                left,right=low,high
                for _ in range(18):
                    mid=(left+right)/2
                    if loss(mid)<=budget:left=mid
                    else:right=mid
                cap=left
        requested=base.command
        if enabled and obs.pressure<85. and obs.reservoir>self.recovery_floor:
            recovery=min(1.,(obs.reservoir-self.recovery_floor)/.1)
            requested=base.command+self.weight*recovery*(high-base.command)
        applied=min(high,max(low,min(requested,cap)))
        self.pi.core.track(applied);self.pi.previous=applied;self.previous=applied
        self.last_debug=dict(control_level_lower=obs.reservoir,override_weight=self.weight,override_eligible=enabled,
            override_delta=applied-base.command,pi_command=base.command,braking_volume=loss(applied),braking_budget=budget,predictive_feasible=feasible)
        return Decision(applied,enabled and not feasible,delivery(applied,belief.hb_lower,obs.sao2,self.bsa))
