"""Faulty inline sensing and a transparent intermittent-reference observer."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Observation:
    time: float
    flow: float                 # L/min; assumes independent unbiased flow sensor
    reservoir: float            # L
    pressure: float             # mmHg
    hb_inline: float | None     # g/dL; missing is explicit, never zero
    sao2: float
    temperature: float
    hb_lab: float | None        # independent periodic reference


class Sensors:
    def __init__(self, seed: int, lab_period: float = 180.):
        self.rng = np.random.default_rng(seed)
        self.lab_period = lab_period
        self.next_lab = 0.

    def observe(self, t, state, hb, inputs) -> Observation:
        # Draw the same fixed number of samples per step for every policy,
        # including missing measurements: paired experiments share sensor noise.
        noise = self.rng.normal(size=6)
        lab = None
        if t+1e-9 >= self.next_lab:
            lab = float(hb + .10*noise[5])
            self.next_lab += self.lab_period
        inline = None if inputs['dropout'] else float(hb+inputs['hb_bias']+.07*noise[3])
        return Observation(t, max(0., state['flow']+.015*noise[0]),
                           max(0., state['reservoir']+.003*noise[1]+inputs['reservoir_bias']),
                           state['pressure']+.25*noise[2], inline,
                           float(np.clip(inputs['sao2']+.001*noise[4], .5, 1)),
                           inputs['temperature'], lab)


@dataclass(frozen=True)
class Belief:
    hb: float
    hb_lower: float
    hb_upper: float
    venous_flow: float
    fault: bool
    stale: bool
    reference_age: float
    reservoir_lower: float | None = None
    level_fault: bool = False
    level_bias: float = 0.


class Twin:
    """Bias correction is identifiable only with an independent reference.

    Bounds are engineering stress bounds, NOT calibrated confidence intervals.
    The width uses a .002 g/dL/s allowance for unresolved bias drift and a
    .25 g/dL base allowance. Neither is a guaranteed bound on Gaussian noise or
    rapid faults; the benchmark tests empirical coverage rather than asserting
    a probabilistic safety guarantee. Level bias is unmodeled in original policies;
    the optional guard tests a causal step-fault hypothesis only.
    """
    def __init__(self, initial_hb: float, calibrate: bool = True, guard_level: bool = False):
        self.hb = initial_hb
        self.bias = 0.
        self.last_reference = 0.
        self.last_inline = 0.
        self.previous = None
        self.calibrate = calibrate
        self.qv = 4.5
        self.guard_level = guard_level
        self.level_bias = 0.
        self.level_fault = False
        self.previous_level = None

    def _level(self, obs):
        """Causal step-fault hypothesis; no true reservoir or fault magnitude.

        Assume drainage in [0, 7.5] L/min (the plant's declared cap),
        independent unbiased flow sensing and 0.03 L noise/model allowance.
        A discontinuity outside that mass-balance envelope is assigned to the
        level channel. Estimate its size from the previous drainage estimate.
        The extra 0.08 L allowance after detection is an engineering margin,
        not a probabilistic bound. Initial offsets and slow drift are unobservable.
        """
        if self.guard_level and self.previous is not None:
            dt = obs.time-self.previous.time
            if dt > 0:
                delta = obs.reservoir-self.previous.reservoir
                lower = -obs.flow*dt/60.-.03
                upper = (7.5-obs.flow)*dt/60.+.03
                if delta < lower or delta > upper:
                    expected = (self.qv-obs.flow)*dt/60.
                    self.level_bias += delta-expected
                    self.level_fault = True
        return obs.reservoir-self.level_bias if self.guard_level else obs.reservoir

    def update(self, obs: Observation) -> Belief:
        if obs.hb_lab is not None:
            self.last_reference = obs.time
            if self.calibrate and obs.hb_inline is not None:
                self.bias = obs.hb_inline - obs.hb_lab
            if obs.hb_inline is None:
                self.hb = obs.hb_lab
        if obs.hb_inline is not None:
            self.hb = obs.hb_inline-self.bias
            self.last_inline = obs.time
        age = obs.time-self.last_reference
        stale = obs.time-self.last_inline > 10.
        width = .25 + .002*age + (.004*(obs.time-self.last_inline) if stale else 0.)
        self.hb = float(np.clip(self.hb, 2., 20.))
        level = self._level(obs)
        if self.previous is not None:
            dt = obs.time-self.previous.time
            if dt > 0:
                # Mass balance estimates drainage using only past observations.
                raw = obs.flow + (level-self.previous_level)*60./dt
                self.qv = .5*self.qv + .5*float(np.clip(raw, 0., 8.))
        else:
            self.qv = obs.flow
        self.previous = obs
        self.previous_level = level
        return Belief(self.hb, max(2., self.hb-width), min(20., self.hb+width),
                      self.qv, abs(self.bias)>.6 or stale, stale, age,
                      max(0., level-(.08 if self.level_fault else 0.)) if self.guard_level else None,
                      self.level_fault, self.level_bias)

