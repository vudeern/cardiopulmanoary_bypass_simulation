"""Finite-candidate receding-horizon control plus explicit ablations.

All policies share the same flow and slew limits. The physical plant also limits
empty-reservoir transfer; the corresponding failure is counted. Only predictive
policies use a look-ahead reservoir constraint, which is part of their hypothesis.
"""
from dataclasses import dataclass
import numpy as np
from .model import delivery

POLICIES = ('fixed', 'reactive', 'sentinel', 'no_calibration', 'no_lookahead')


@dataclass(frozen=True)
class Decision:
    command: float
    infeasible: bool = False
    predicted_delivery: float = 0.


class Controller:
    def __init__(self, policy, bsa, dt=2., target=280.):
        if policy not in POLICIES:
            raise ValueError(f"Unknown policy {policy}")
        self.policy, self.bsa, self.dt, self.target = policy, bsa, dt, target
        self.previous = 2.4*bsa
        self.candidates = np.linspace(0., 7., 71)

    def decide(self, obs, belief):
        low, high = max(0., self.previous-.15*self.dt), min(7., self.previous+.15*self.dt)
        if self.policy == 'fixed':
            command = float(np.clip(2.4*self.bsa, low, high))
            result = Decision(command)
        elif self.policy == 'reactive':
            # A simple comparator, not a reproduction of clinical practice.
            hb = obs.hb_inline if obs.hb_inline is not None else belief.hb
            measured = delivery(obs.flow, hb, obs.sao2, self.bsa)
            command = self.previous + .004*(self.target-measured)
            result = Decision(float(np.clip(command, low, high)))
        else:
            # Model uncertainty enters through a conservative Hb bound. There is
            # no access to the true scenario, future disturbance, or patient Hb.
            q = self.candidates
            predicted = delivery(q, belief.hb_lower, obs.sao2, self.bsa)
            horizon = 20.  # s; a held-flow, local linear look-ahead
            predicted_reservoir = obs.reservoir + (belief.venous_flow-q)*horizon/60.
            # Deliberately approximate effective resistance from current pressure.
            resistance = obs.pressure/max(obs.flow, .5)
            pressure = q*resistance
            feasible = (q>=low-1e-9)&(q<=high+1e-9)&(pressure<=95.)
            if self.policy != 'no_lookahead':
                feasible &= predicted_reservoir>=.25
            deficit = np.maximum(0., self.target-predicted)/self.target
            cost = 100.*deficit**2 + .025*q**2 + .1*(q-self.previous)**2
            # Prefer adequate delivery with less pump demand; no cure-all claim.
            if feasible.any():
                index = int(np.argmin(np.where(feasible, cost, np.inf)))
                result = Decision(float(q[index]), False, float(predicted[index]))
            else:
                # Conflicting bounds are surfaced. A ramp-limited slowdown is a
                # deterministic fallback, not a guarantee against depletion.
                result = Decision(float(low), True, delivery(low, belief.hb_lower, obs.sao2, self.bsa))
        self.previous = result.command
        return result
