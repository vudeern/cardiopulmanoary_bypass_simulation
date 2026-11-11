"""Measurement-based startup admission; rejects rather than hiding hot starts.

This is a simulation/runtime interlock, not equipment priming or a watchdog.
A rejection issues no command and does not physically stop an already moving pump.
"""
from dataclasses import replace
from .envelope_carry_v2 import CarryRuntime,CarryEnvelope


class StartupRejected(ValueError):
    def __init__(self,reason,details):
        self.reason=reason;self.details=details
        super().__init__(reason)


class ActuationContractViolation(RuntimeError):pass


class BootRuntime(CarryRuntime):
    def __init__(self,**kwargs):
        options=dict(kwargs.get('controller_options') or {})
        self.startup_flow_error=float(options.pop('startup_flow_error_lpm',.10))
        if not 0<=self.startup_flow_error<=7:raise ValueError('Invalid startup flow error')
        kwargs['controller_options']=options
        super().__init__(**kwargs)
        self.startup_authorized=False;self.actuation_fault=False;self.requested=None
        # Last held command is declared zero, not the inherited warm-start bias.
        self.controller.previous=self.controller.pi.previous=0.
        self.controller.pi.forecast.previous=0.
        self.controller.pi.core.track(0.)
        self.controller.nominal_flow=0.
        self.startup_details=None

    def observe(self,frame):
        self._validate(frame)
        if self.actuation_fault:raise ActuationContractViolation('Adapter must resolve the latched actuation fault before reinitializing')
        if not self.startup_authorized:
            budget=replace(self.envelope.budget,initial_flow_error_lpm=self.startup_flow_error)
            preview=CarryEnvelope(frame.observation.flow,self.dt,budget)
            preview.update(frame.observation,frame.calibrations)
            margin=preview.margin(0.)
            details=dict(observation_time=frame.observation.time,measured_flow=frame.observation.flow,
                motor_flow_upper=preview.flow_upper,volume_lower=preview.lower,held_zero_margin=margin)
            if margin is None:raise StartupRejected('no_bounded_level_source',details)
            if margin<0:raise StartupRejected('held_zero_stop_infeasible',details)
            # Commit only after admission; the normal path processes this frame once.
            self.envelope=CarryEnvelope(frame.observation.flow,self.dt,budget)
            self.guard.flow=frame.observation.flow;self.guard.flows[:]=frame.observation.flow
            self.controller.nominal_flow=frame.observation.flow
            self.startup_authorized=True;self.startup_details=details
        output=super().observe(frame)
        self.requested=output.decision.command
        self.controller.last_debug.update(startup_authorized=True,startup_margin=self.startup_details['held_zero_margin'])
        return replace(output,diagnostics=dict(self.controller.last_debug),status=output.status+('startup_admitted',))

    def acknowledge(self,*,observation_time,applied_command):
        planned=self.requested
        super().acknowledge(observation_time=observation_time,applied_command=applied_command)
        self.requested=None
        if planned is not None and applied_command>planned+1e-8:
            self.actuation_fault=True
            raise ActuationContractViolation('Higher-than-protected setpoint recorded; certificate invalidated, independent adapter stop required')
