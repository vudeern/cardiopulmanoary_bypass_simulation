import math
from types import SimpleNamespace
import unittest
from perfusion_lab.reference import LevelSample
from perfusion_lab.runtime import MeasurementFrame
from perfusion_lab.sensing import Observation
from perfusion_research.envelope_v2 import EnvelopeRuntime
from perfusion_research.envelope_v2 import EnvelopeBudget,ProtectionEnvelope,stopping_volume

class IndependentEnvelopeTests(unittest.TestCase):
    def test_stop_bound_covers_independent_rollouts_across_lag_interval(self):
        for tau in (1.,2.,6.,12.,20.):
            for u in (0.,.37,3.1,7.):
                q=4.;command=u;total=0.;a=math.exp(-1./tau)
                while True:
                    after=command+(q-command)*a;total+=(q+after)/120.;q=after
                    if command==0:break
                    command=max(0.,command-.15)
                total+=q*(1+a)/(1-a)/120.
                self.assertLessEqual(total,stopping_volume(u,4.,20.)+1e-10)

    def test_command_interval_contains_unobserved_motor_state(self):
        for tau in (1.,3.7,20.):
            e=ProtectionEnvelope(4.);q=4.
            for u in (6.,6.,1.,0.,4.,2.,0.):
                q=u+(q-u)*math.exp(-1./tau);e.advance(u)
                self.assertLessEqual(e.flow_lower-1e-12,q);self.assertLessEqual(q,e.flow_upper+1e-12)

    def test_delayed_anchor_uses_upper_pumped_volume_and_no_future_return(self):
        e=ProtectionEnvelope(0.,budget=EnvelopeBudget(inline_error_L=None))
        e.update(SimpleNamespace(time=0.,reservoir=99.),[]);e.advance(1.)
        self.assertAlmostEqual(e.update(SimpleNamespace(time=1.,reservoir=99.),[LevelSample(0.,1.,1.)]),.7-e.out_upper)

    def test_contract_absent_brakes_and_does_not_certify(self):
        e=ProtectionEnvelope(4.,budget=EnvelopeBudget(inline_error_L=None,anchor_error_L=None))
        self.assertIsNone(e.update(SimpleNamespace(time=0.,reservoir=99.),[]))
        self.assertEqual(e.cap(1.,1.3),(1.,False))

    def test_shared_bias_inside_budget_does_not_raise_lower_above_truth(self):
        e=ProtectionEnvelope(0.)
        lower=e.update(SimpleNamespace(time=0.,reservoir=1.22),[LevelSample(0.,0.,1.22)])
        self.assertLessEqual(lower,1.)

    def test_initial_infeasibility_is_explicit(self):
        e=ProtectionEnvelope(4.)
        e.update(SimpleNamespace(time=0.,reservoir=.85),[])
        self.assertEqual(e.cap(3.85,4.15),(3.85,False))
        self.assertLess(e.margin(3.85),0.)

    def test_runtime_records_initial_fallback_and_rejects_unacknowledged_frame(self):
        runtime=EnvelopeRuntime(bsa=1.8,initial_hb=10.,controller_options={'return_horizon_s':0.})
        obs=Observation(time=0.,flow=4.32,reservoir=.85,pressure=60.,hb_inline=10.,sao2=.98,temperature=37.,hb_lab=10.)
        frame=MeasurementFrame(obs,4.,(),(LevelSample(0.,0.,.85),))
        output=runtime.observe(frame)
        self.assertAlmostEqual(output.decision.command,4.17)
        self.assertIn('independent_stop_not_certified',output.status)
        self.assertFalse(output.diagnostics['envelope_feasible'])
        with self.assertRaises(ValueError):runtime.observe(frame)
        self.assertEqual(runtime.envelope.time,0.)
        runtime.acknowledge(observation_time=0.,applied_command=output.decision.command)
        self.assertGreater(runtime.envelope.out_upper,0.)
