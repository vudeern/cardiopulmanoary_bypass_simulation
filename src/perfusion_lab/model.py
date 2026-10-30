"""Low-order bypass plant with explicit units and auditable conservation.

This is an intentionally small, uncalibrated adult-like model. The pump transfers
volume from a reservoir to a compliant patient compartment; passive drainage
returns it. A separate Windkessel approximates arterial pressure. Hemoglobin,
temperature and oxygenator performance are scripted perturbations, not validated
biochemical/thermal models. No medical device specifications are reproduced.
"""
from dataclasses import dataclass
import math
import numpy as np


def oxygen_content(hb: float, sao2: float, pao2: float = 150.0) -> float:
    """Arterial content [mL O2/dL]; saturation is a fraction, Hb is g/dL."""
    return 1.34 * hb * sao2 + 0.0031 * pao2


def delivery(flow: float, hb: float, sao2: float, bsa: float) -> float:
    """Indexed DO2 [mL O2/min/m²]; 10 converts L to dL."""
    return 10.0 * flow * oxygen_content(hb, sao2) / bsa


@dataclass(frozen=True)
class Patient:
    """Synthetic adult-like parameters; deliberately not clinical defaults."""
    bsa: float = 1.85               # m²
    hb: float = 9.4                 # g/dL after a hypothetical initial dilution
    resistance: float = 14.0        # mmHg min/L, arterial resistance
    compliance: float = 0.0018      # L/mmHg, arterial compliance
    venous_compliance: float = 0.12 # L/mmHg, effective patient storage
    venous_resistance: float = 0.9  # mmHg min/L
    volume: float = 5.8             # L, patient + reservoir, conserved exactly
    unstressed_volume: float = 4.35 # L
    demand37: float = 125.0         # mL O2/min/m², hypothetical demand
    q10: float = 2.3                # dimensionless temperature-demand factor

    def __post_init__(self):
        values = vars(self)
        if any(not math.isfinite(v) or v <= 0 for v in values.values()):
            raise ValueError("Patient parameters must be finite and positive")
        if self.volume <= self.unstressed_volume or self.hb > 25:
            raise ValueError("Invalid storage volume or hemoglobin")

    @classmethod
    def sampled(cls, seed: int):
        """Independent deterministic virtual patient; not population inference."""
        rng = np.random.default_rng(seed)
        return cls(bsa=float(rng.uniform(1.55, 2.15)),
                   hb=float(rng.uniform(8.6, 10.2)),
                   resistance=float(rng.uniform(11, 18)),
                   compliance=float(rng.uniform(.0014, .0022)),
                   demand37=float(rng.uniform(110, 140)),
                   q10=float(rng.uniform(2.0, 2.7)))


@dataclass(frozen=True)
class Scenario:
    name: str
    dilution: float = 0.0           # eventual Hb decrement, g/dL
    hb_bias: float = 0.0            # additive inline sensor fault, g/dL
    drainage: float = 1.0           # fraction of unobstructed venous return
    saturation_loss: float = 0.0    # eventual arterial saturation decrement
    dropout: bool = False
    reservoir_bias: float = 0.0     # L; deliberately outside twin fault model

    def __post_init__(self):
        numeric = (self.dilution, self.hb_bias, self.drainage,
                   self.saturation_loss, self.reservoir_bias)
        if not all(math.isfinite(v) for v in numeric):
            raise ValueError('Scenario magnitudes must be finite')
        if self.dilution < 0 or not 0 <= self.drainage <= 1:
            raise ValueError('Use nonnegative dilution and drainage in [0, 1]')
        if not 0 <= self.saturation_loss <= .48:
            raise ValueError('Saturation loss must be in [0, .48]')

    def inputs(self, t: float, duration: float) -> dict:
        """Scenario changes are time-relative so short test runs remain useful."""
        phase = t / duration
        onset = min(1.0, max(0.0, (phase - .25) / .15))
        obstructed = .48 <= phase < .67
        return dict(hb_loss=self.dilution * onset,
                    hb_bias=self.hb_bias * onset,
                    drainage=self.drainage if obstructed else 1.0,
                    sao2=.98 - self.saturation_loss * onset,
                    temperature=32 + 5 * min(1.0, max(0., (phase-.35)/.5)),
                    dropout=self.dropout and .40 <= phase < .57,
                    reservoir_bias=self.reservoir_bias if obstructed else 0.)


SCENARIOS = {
    s.name: s for s in [
        Scenario("nominal"),
        Scenario("hemodilution", dilution=2.0),
        Scenario("hb_bias", dilution=1.8, hb_bias=2.0),
        Scenario("venous_obstruction", drainage=.46),
        Scenario("oxygenator_loss", saturation_loss=.16),
        Scenario("compound", dilution=1.8, hb_bias=2.0, drainage=.55,
                 saturation_loss=.06, dropout=True),
        Scenario("unmodeled_level_bias", dilution=1.8, drainage=.45,
                 reservoir_bias=.40),
    ]
}


class Plant:
    """Hidden ground truth. Controllers receive Observation, never this object."""
    def __init__(self, patient: Patient):
        self.p = patient
        self.reservoir = .85
        self.flow = 2.4 * patient.bsa
        self.pressure = self.flow * patient.resistance

    def venous_return(self, factor: float) -> float:
        patient_volume = self.p.volume - self.reservoir
        filling_pressure = max(0., (patient_volume-self.p.unstressed_volume)
                               / self.p.venous_compliance)
        return min(7.5, factor * filling_pressure / self.p.venous_resistance)

    def step(self, command: float, drainage: float, dt: float) -> dict:
        """Advance dt seconds, conservatively limit transfers to available volume.

        A first-order actuator is integrated analytically. Midpoint pump flow
        approximates the step average. Reservoir and patient volumes exchange
        equal/opposite quantities. Physical empty-reservoir limiting is recorded
        as a failed request, not silently reported as a successful controller.
        """
        old_flow = self.flow
        self.flow = command + (old_flow-command) * math.exp(-dt/2.)
        requested = (old_flow+self.flow)/2
        qv = self.venous_return(drainage)
        returned = min(qv*dt/60., self.p.volume-self.reservoir)
        available = self.reservoir + returned
        transferred = min(requested*dt/60., available)
        actual_flow = transferred * 60. / dt
        self.reservoir = available-transferred
        # Exact linear pressure update for held step-average inflow.
        eq = actual_flow*self.p.resistance
        tau = self.p.resistance*self.p.compliance*60.
        self.pressure = eq + (self.pressure-eq)*math.exp(-dt/tau)
        return dict(flow=actual_flow, qv=qv, reservoir=self.reservoir,
                    pressure=self.pressure, empty_request=requested>actual_flow+1e-9,
                    patient_volume=self.p.volume-self.reservoir)
