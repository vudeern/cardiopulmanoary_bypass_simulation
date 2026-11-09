"""Declared, uncalibrated challenges outside the frozen controller's design.

No parameter in this module is inferred from a clinical device or population.
The alternate plant tests structural assumptions; it is not an independent
experimental reference or a higher-fidelity physiology model.
"""
from dataclasses import dataclass
import math
from .model import Plant, Scenario


@dataclass(frozen=True)
class StressScenario(Scenario):
    level_profile: str = 'none'
    event_start: float = .4
    event_end: float = .65
    drift_duration: float = .25
    flow_bias: float = 0.
    noise_scale: float = 1.

    def __post_init__(self):
        super().__post_init__()
        if self.level_profile not in ('none','step','ramp','initial'):
            raise ValueError('Unknown level profile')
        if not all(math.isfinite(v) for v in (self.event_start,self.event_end,
                self.drift_duration,self.flow_bias,self.noise_scale)):
            raise ValueError('Stress inputs must be finite')
        if not 0<=self.event_start<self.event_end<=1 or self.drift_duration<=0 or self.noise_scale<=0:
            raise ValueError('Invalid stress timing or noise scale')

    def inputs(self,t,duration):
        values=super().inputs(t,duration)
        phase=t/duration
        active=phase>=self.event_start
        if self.level_profile=='initial':
            bias=self.reservoir_bias
        elif self.level_profile=='step':
            bias=self.reservoir_bias if active else 0.
        elif self.level_profile=='ramp':
            bias=self.reservoir_bias*min(1.,max(0.,(phase-self.event_start)/self.drift_duration))
        else:
            bias=0.
        values.update(reservoir_bias=bias,
                      drainage=self.drainage if self.event_start<=phase<self.event_end else 1.,
                      flow_bias=self.flow_bias if active else 0.,
                      level_noise_scale=self.noise_scale,flow_noise_scale=self.noise_scale)
        return values


class StressPlant(Plant):
    """Change pump response and/or drainage law; conserve transfer exactly.

    Zero drainage lag, zero nonlinearity, cap 7.5 and pump tau 2 reproduce the
    original numerical plant. Nonzero settings are deliberate engineering
    perturbations unknown to the controller. A cap above 7.5 deliberately
    violates the detector's stated envelope assumption.
    """
    def __init__(self,patient,*,actuator_tau=2.,drainage_tau=0.,
                 venous_nonlinearity=0.,max_drainage=7.5):
        super().__init__(patient)
        if not all(math.isfinite(v) for v in (actuator_tau,drainage_tau,
                                              venous_nonlinearity,max_drainage)):
            raise ValueError('Plant settings must be finite')
        if actuator_tau<=0 or drainage_tau<0 or venous_nonlinearity<0 or max_drainage<=0:
            raise ValueError('Invalid stress plant settings')
        self.actuator_tau=actuator_tau
        self.drainage_tau=drainage_tau
        self.venous_nonlinearity=venous_nonlinearity
        self.max_drainage=max_drainage
        self.drainage_state=self.venous_return(1.)

    def venous_return(self,factor):
        filling=max(0.,(self.p.volume-self.reservoir-self.p.unstressed_volume)
                        /self.p.venous_compliance)
        return min(self.max_drainage,
                   factor*filling/(self.p.venous_resistance*(1.+self.venous_nonlinearity*filling)))

    def step(self,command,drainage,dt):
        old_flow=self.flow
        self.flow=command+(old_flow-command)*math.exp(-dt/self.actuator_tau)
        requested=(old_flow+self.flow)/2
        target=self.venous_return(drainage)
        if self.drainage_tau:
            decay=math.exp(-dt/self.drainage_tau)
            qv=target+(self.drainage_state-target)*(self.drainage_tau/dt)*(1.-decay)
            self.drainage_state=target+(self.drainage_state-target)*decay
        else:
            qv=target
            self.drainage_state=target
        returned=min(qv*dt/60.,self.p.volume-self.reservoir)
        available=self.reservoir+returned
        transferred=min(requested*dt/60.,available)
        actual_flow=transferred*60./dt
        self.reservoir=available-transferred
        equilibrium=actual_flow*self.p.resistance
        tau=self.p.resistance*self.p.compliance*60.
        self.pressure=equilibrium+(self.pressure-equilibrium)*math.exp(-dt/tau)
        return dict(flow=actual_flow,qv=qv,reservoir=self.reservoir,
                    pressure=self.pressure,empty_request=requested>actual_flow+1e-9,
                    patient_volume=self.p.volume-self.reservoir)
