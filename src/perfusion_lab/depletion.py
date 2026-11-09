"""Conservative development protection; no promise of clinical safety.

Reserve assumes zero future return and retains the entire configured pump grid.
Unknown/conflicting calibration commands maximum permitted braking. Corrupted
absolute calibration and dynamics outside the grid can still defeat protection.
"""
from dataclasses import replace
from .reachability import ConsistentGuard, ReachabilityController, joint_braking_reserve
from .reachability_runtime import ReachabilityRuntime
from .control import Decision
from .model import oxygen_content, delivery


class DepletionGuard(ConsistentGuard):
    def update(self, obs, routine, calibrations):
        state = super().update(obs, routine, calibrations)
        # Calibration fit may reject the actual lag. Keep every configured lag
        # for stopping calculations, including when calibration is unsupported.
        state['protection_models'] = list(zip(map(float, self.taus), map(float, self.flows)))
        return state


class DepletionController(ReachabilityController):
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
        models = state.get('protection_models', ())
        supported = bool(state['bank_supported'] and models)
        # No independent absolute level support means no positive volume budget.
        budget = max(0., obs.reservoir-.29) if supported else 0.
        loss = lambda command: joint_braking_reserve(models, command, 0., self.dt)
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
            protection_unsupported=not supported, protection_inflow_floor=0.)
        return Decision(applied, not feasible,
                        delivery(applied, belief.hb_lower, obs.sao2, self.bsa))


class DepletionRuntime(ReachabilityRuntime):
    def __init__(self, *, bsa, initial_hb, dt=1., target=280., kind='hybrid',
                 level_mode='screened', controller_options=None, guard_options=None):
        super().__init__(bsa=bsa, initial_hb=initial_hb, dt=dt, target=target,
            kind=kind, level_mode=level_mode, controller_options=controller_options,
            guard_options=guard_options)
        if self.guard.interval_mode != 'consistent' or self.controller.reserve_mode != 'joint':
            raise ValueError('Depletion protection requires consistent sets and joint reserve')
        self.guard = DepletionGuard(2.4*bsa, dt, **dict(guard_options or {}))
        self.controller = DepletionController(kind, bsa, dt, target,
                                             **dict(controller_options or {}))

    def observe(self, frame):
        output = super().observe(frame)
        flags = ('depletion_protection_active',) if output.diagnostics['protection_active'] else ()
        if output.diagnostics['protection_unsupported']:
            flags += ('depletion_calibration_unsupported',)
        return replace(output, status=output.status+flags)
