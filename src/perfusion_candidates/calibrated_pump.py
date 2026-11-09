"""Development-only reserve over calibration-consistent pump hypotheses.

Pruning relies on the observer's calibration, bias and model-error assumptions.
If those assumptions discard the real response, protection can fail. No true
plant lag, hidden state, or future disturbance is supplied to this controller.
"""
import math
from perfusion_lab.reachability import ReachabilityController
from perfusion_lab.control import Decision
from perfusion_lab.model import oxygen_content, delivery
from perfusion_candidates.finite_return import finite_return_reserve
from perfusion_candidates.startup import StartupRuntime


class CalibratedPumpController(ReachabilityController):
    def __init__(self, *args, return_fraction=.5, return_horizon_s=30., **kwargs):
        if not math.isfinite(return_fraction) or not 0 <= return_fraction <= 1:
            raise ValueError('Return fraction must be within 0..1')
        if not math.isfinite(return_horizon_s) or not 0 <= return_horizon_s <= 120:
            raise ValueError('Return horizon must be within 0..120 seconds')
        super().__init__(*args, **kwargs)
        self.return_fraction = return_fraction
        self.return_horizon_s = return_horizon_s

    def decide(self, obs, belief):
        state = self.reference_state
        if state is None:
            raise ValueError('Reference state required')
        self.pi.previous = self.previous
        base = self.pi.decide(obs, belief)
        low = max(0., self.previous - .15*self.dt)
        high = min(7., self.previous + .15*self.dt)
        high = max(low, min(high, self.target*self.bsa /
                           (10.*oxygen_content(belief.hb_lower, obs.sao2))))
        if obs.pressure > 90.:
            high = low
        models = state.get('pump_models', ())
        supported = bool(state['bank_supported'] and models)
        # No independent absolute level support means no positive volume budget.
        budget = max(0., obs.reservoir-.29) if supported else 0.
        qin = self.return_fraction*max(0., belief.venous_flow-state['venous_bias_upper']-self.allowance)
        loss = lambda command: finite_return_reserve(models, command, qin, self.return_horizon_s, self.dt)
        feasible = supported and obs.reservoir >= .29 and loss(low) <= budget
        cap = low
        if feasible:
            cap = high
            if loss(high) > budget:
                left, right = low, high
                for _ in range(18):
                    mid = (left+right)/2.
                    if loss(mid) <= budget:
                        left = mid
                    else:
                        right = mid
                cap = left
        self.weight = min(self.weight+self.dt/10.,
                          max(self.weight-self.dt/10., float(supported)))
        requested = base.command
        if self.kind == 'hybrid' and supported and obs.pressure < 85. and obs.reservoir > self.recovery_floor:
            recovery = min(1., (obs.reservoir-self.recovery_floor)/.1)
            requested += self.weight*recovery*(high-base.command)
        applied = min(high, max(low, min(requested, cap)))
        self.pi.core.track(applied)
        self.pi.previous = self.previous = applied
        self.last_debug = dict(control_level_lower=obs.reservoir,
            override_weight=self.weight, override_eligible=supported,
            override_delta=applied-base.command, pi_command=base.command,
            braking_volume=loss(applied), braking_budget=budget,
            predictive_feasible=feasible, protection_active=applied < requested-1e-9,
            protection_unsupported=not supported, protection_inflow_floor=qin,
            return_credit_horizon_s=self.return_horizon_s, return_credit_fraction=self.return_fraction,
            protection_model_count=len(models))
        return Decision(applied, not feasible,
                        delivery(applied, belief.hb_lower, obs.sao2, self.bsa))


class CalibratedPumpRuntime(StartupRuntime):
    def __init__(self, *, bsa, initial_hb, dt=1., target=280., kind='hybrid',
                 level_mode='screened', controller_options=None, guard_options=None):
        super().__init__(bsa=bsa, initial_hb=initial_hb, dt=dt, target=target,
            kind=kind, level_mode=level_mode, controller_options=controller_options,
            guard_options=guard_options)
        self.controller = CalibratedPumpController(kind, bsa, dt, target,
            **dict(controller_options or {}))
