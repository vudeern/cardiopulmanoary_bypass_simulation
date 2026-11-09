"""Opt-in single-anchor startup using unchanged calibration/bias allowances.

One anchor bounds absolute volume while venous bias remains in the full +/-2
L/min prior. Uncertainty grows with age until later anchors constrain bias.
This is an engineering set, not a statistical coverage or safety guarantee.
"""
import math
from perfusion_lab.depletion import DepletionGuard
from perfusion_lab.integrity import ReferenceGuard
from perfusion_lab.reachability import clip_polygon
from perfusion_candidates.finite_return import FiniteReturnRuntime


class StartupGuard(DepletionGuard):
    def __init__(self, *args, minimum_anchors=1, interval_mode='consistent', **kwargs):
        if minimum_anchors not in (1, 2): raise ValueError('Minimum anchors must be one or two')
        self.minimum_anchors = minimum_anchors
        if interval_mode != 'consistent': raise ValueError('Unknown interval mode')
        super().__init__(*args, interval_mode=interval_mode, **kwargs)
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
        if changed and len(self.samples) >= self.minimum_anchors:
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
        state['protection_models'] = list(zip(map(float, self.taus), map(float, self.flows)))
        state['single_anchor_support'] = supported and len(self.samples) == 1
        return state


class StartupRuntime(FiniteReturnRuntime):
    def __init__(self, *, bsa, initial_hb, dt=1., target=280., kind='hybrid',
                 level_mode='screened', controller_options=None, guard_options=None):
        options = dict(guard_options or {})
        minimum = options.pop('startup_minimum_anchors', 1)
        super().__init__(bsa=bsa, initial_hb=initial_hb, dt=dt, target=target,
            kind=kind, level_mode=level_mode, controller_options=controller_options,
            guard_options=options)
        self.guard = StartupGuard(2.4*bsa, dt, minimum_anchors=minimum, **options)
