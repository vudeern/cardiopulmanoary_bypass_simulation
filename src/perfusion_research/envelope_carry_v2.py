"""Adaptive envelope follow-up: carried lower bound and variable-lag stop."""
import math
from .envelope_v2 import ProtectionEnvelope,EnvelopeRuntime,stopping_volume


def robust_stopping_volume(command,flow_upper,tau_min,tau_max,dt=1.,slew=.15):
    # While command exceeds flow, the fastest lag maximizes next flow. Once
    # braking command falls below flow, the slowest lag maximizes every later
    # flow. The decreasing ramp permits at most one switch; then sum the tail.
    if not math.isfinite(tau_min) or not 0<tau_min<=tau_max:raise ValueError('Invalid lag interval')
    stopping_volume(command,flow_upper,tau_max,dt,slew)  # Validate all other inputs.
    q=flow_upper;u=command;volume=0.;a=math.exp(-dt/tau_min)
    while u>q:
        after=u+(q-u)*a;volume+=(q+after)*dt/120.;q=after;u=max(0.,u-slew*dt)
    return volume+stopping_volume(u,q,tau_max,dt,slew)


class CarryEnvelope(ProtectionEnvelope):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.bound_out=0.

    def update(self,obs,calibrations):
        old=self.lower;loss=self.out_upper-self.bound_out
        super().update(obs,calibrations)
        if old is not None:self.lower=max(0.,old-loss,self.lower if self.lower is not None else 0.)
        self.bound_out=self.out_upper
        return self.lower

    def margin(self,command):
        if self.lower is None:return None
        return self.lower-.29-robust_stopping_volume(command,self.flow_upper,self.budget.tau_min_s,self.budget.tau_max_s,self.dt)


class CarryRuntime(EnvelopeRuntime):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.envelope=CarryEnvelope(2.4*kwargs['bsa'],kwargs.get('dt',1.),self.envelope.budget)
