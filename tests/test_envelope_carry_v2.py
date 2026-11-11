import math
from types import SimpleNamespace
import unittest
from perfusion_research.envelope_carry_v2 import CarryEnvelope,robust_stopping_volume

class CarriedEnvelopeTests(unittest.TestCase):
    def test_variable_lag_stop_matches_independent_worst_step_rollout(self):
        for initial in (0.,2.,4.):
            for command in (0.,.37,3.1,7.):
                q=initial;u=command;volume=0.
                while True:
                    after=max(u+(q-u)*math.exp(-1./tau) for tau in (1.,20.))
                    volume+=(q+after)/120.;q=after
                    if u==0:break
                    u=max(0.,u-.15)
                a=math.exp(-1./20.);volume+=q*(1+a)/(1-a)/120.
                self.assertAlmostEqual(robust_stopping_volume(command,initial,1.,20.),volume,places=10)

    def test_viability_persists_with_adversarial_bounded_readings_and_varying_lag(self):
        envelope=CarryEnvelope(0.);q=0.;volume=.8;previous=0.
        for t in range(120):
            error=.3 if t%2==0 else -.3
            envelope.update(SimpleNamespace(time=float(t),reservoir=volume+error),[])
            low=max(0.,previous-.15);high=min(7.,previous+.15)
            u,feasible=envelope.cap(low,high)
            self.assertTrue(feasible,t)
            self.assertLessEqual(envelope.lower,volume+1e-10)
            self.assertLessEqual(q,envelope.flow_upper+1e-10)
            after=u+(q-u)*math.exp(-1./(1. if t%2 else 20.))
            volume-=(q+after)/120.;q=after
            self.assertGreaterEqual(volume,.29-1e-9)
            envelope.advance(u);previous=u
