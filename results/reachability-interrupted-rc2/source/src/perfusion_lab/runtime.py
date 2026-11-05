"""Measurement-only controller boundary for simulation and future bench adapters.

No device I/O, timing scheduler or emergency stop is implemented here. Invalid
input raises before state changes; an adapter must own its independent watchdog.
The fixed-step model requires acknowledgement of each applied setpoint before
the next frame. A setpoint acknowledgement is not measured delivered pump flow.
"""
from dataclasses import dataclass, replace
import math
from .sensing import Observation, Twin, Belief
from .reference import LevelSample
from .control import Decision
from .model_bank import ModelBankGuard, ModelBankController


@dataclass(frozen=True)
class MeasurementFrame:
    observation: Observation
    venous_flow: float
    routine: tuple[LevelSample, ...] = ()
    calibrations: tuple[LevelSample, ...] = ()


@dataclass(frozen=True)
class ControlOutput:
    observation_time: float
    valid_until: float
    decision: Decision
    belief: Belief
    reference: dict
    diagnostics: dict
    status: tuple[str, ...]


class ControllerRuntime:
    """v1.14 controller behavior behind an explicit measurement/action contract.

    Initialization uses declared BSA and initial Hb, just as the simulation did.
    Those must come from measured/configured inputs in any future bench adapter.
    Fixed dt, acquisition-time alignment and reference delivery times are checked.
    """
    def __init__(self, *, bsa, initial_hb, dt=1., target=280., kind='hybrid',
                 level_mode='screened', controller_options=None, guard_options=None):
        if not all(math.isfinite(x) and x > 0 for x in (bsa, initial_hb, dt, target)):
            raise ValueError('Positive finite configuration required')
        if dt > 5 or 2.4*bsa > 7 or level_mode not in ('screened', 'calibration_only'):
            raise ValueError('Unsupported timing, initial flow or level mode')
        self.dt, self.mode = dt, level_mode
        self.guard = ModelBankGuard(2.4*bsa, dt, **dict(guard_options or {}))
        self.controller = ModelBankController(kind, bsa, dt, target, **dict(controller_options or {}))
        self.twin = Twin(initial_hb)
        self.last_time = None
        self.acquisitions = set()
        self.pending = None

    def _validate(self, frame):
        if self.pending is not None:
            raise ValueError('Acknowledge the previous applied setpoint first')
        obs = frame.observation
        required = (obs.time, obs.flow, obs.reservoir, obs.pressure,
                    obs.sao2, obs.temperature, frame.venous_flow)
        optional = (obs.hb_inline, obs.hb_lab)
        if not all(math.isfinite(v) for v in required) or not all(v is None or math.isfinite(v) for v in optional):
            raise ValueError('Nonfinite measurement')
        if obs.time < 0 or min(obs.flow, obs.reservoir, frame.venous_flow) < 0 or not 0 < obs.sao2 <= 1:
            raise ValueError('Invalid measurement range')
        if any(v is not None and v <= 0 for v in optional):
            raise ValueError('Hemoglobin must be positive or explicitly absent')
        if self.last_time is None:
            if obs.time != 0:
                raise ValueError('Start at time zero; adapter must establish the time origin')
        elif not math.isclose(obs.time-self.last_time, self.dt, rel_tol=0., abs_tol=1e-8):
            raise ValueError('Missing, duplicated or out-of-order frame')
        available = self.acquisitions | {round(obs.time, 9)}
        for samples in (frame.routine, frame.calibrations):
            times = []
            for sample in samples:
                if not all(math.isfinite(v) for v in (sample.acquired, sample.delivered, sample.value)):
                    raise ValueError('Nonfinite reference')
                if not 0 <= sample.acquired <= sample.delivered <= obs.time+1e-9 or sample.value < 0:
                    raise ValueError('Invalid or future reference')
                if round(sample.acquired, 9) not in available:
                    raise ValueError('Reference has no matching acquisition frame')
                times.append(sample.acquired)
            if times != sorted(times) or len(times) != len(set(times)):
                raise ValueError('Reference batch must have unique ordered acquisitions')

    def observe(self, frame: MeasurementFrame) -> ControlOutput:
        self._validate(frame)
        obs = frame.observation
        state = self.guard.update(obs, frame.routine if self.mode == 'screened' else (), frame.calibrations)
        belief = replace(self.twin.update(obs), venous_flow=frame.venous_flow)
        control_obs = replace(obs, reservoir=state['lower'], level_reference_age=state['age'], level_reference_bias=state['bias'])
        self.controller.set_reference_state(state)
        decision = self.controller.decide(control_obs, belief)
        if not math.isfinite(decision.command) or not 0 <= decision.command <= 7:
            raise RuntimeError('Controller produced an invalid command')
        status = []
        if not state['bank_supported']: status.append('model_recovery_unsupported')
        if state['bank_conflict']: status.append('reference_conflict')
        if state['quarantined']: status.append('routine_quarantined')
        if decision.infeasible: status.append('conditional_reserve_infeasible')
        if belief.stale: status.append('hemoglobin_stale')
        self.last_time = obs.time
        self.acquisitions.add(round(obs.time, 9))
        self.pending = (obs.time, frame.venous_flow)
        # Copies keep callers from changing observer/controller state via logs.
        from copy import deepcopy
        return ControlOutput(obs.time, obs.time+self.dt, decision, belief,
                             deepcopy(state), dict(self.controller.last_debug), tuple(status))

    def acknowledge(self, *, observation_time, applied_command):
        """Record the setpoint held for this interval, before the next frame.

        A future adapter must report discrepancies and use an independent stop
        path for stalled I/O; this API itself cannot stop equipment.
        """
        if self.pending is None or observation_time != self.pending[0]:
            raise ValueError('No pending command at that observation time')
        if not math.isfinite(applied_command) or not 0 <= applied_command <= 7:
            raise ValueError('Applied command must be finite and within 0..7 L/min')
        _, venous = self.pending
        if applied_command != self.controller.previous:
            self.controller.pi.core.track(applied_command)
            self.controller.pi.previous = applied_command
            self.controller.previous = applied_command
        self.guard.advance(applied_command, venous)
        self.pending = None
