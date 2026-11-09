import math
import unittest
from dataclasses import replace
from perfusion_lab.depletion import DepletionController, DepletionRuntime
from perfusion_lab.reachability import joint_braking_reserve
from perfusion_lab.runtime import MeasurementFrame
from perfusion_lab.sensing import Observation, Twin


class DepletionTests(unittest.TestCase):
    def test_missing_calibration_brakes_and_acknowledges_applied_setpoint(self):
        runtime = DepletionRuntime(bsa=1.85, initial_hb=9.)
        obs = Observation(0., 4.44, .85, 60., 9., .98, 37., None)
        output = runtime.observe(MeasurementFrame(obs, 4.44))
        self.assertAlmostEqual(output.decision.command, 4.29)
        self.assertTrue(output.decision.infeasible)
        self.assertIn('depletion_calibration_unsupported', output.status)
        self.assertEqual(len(output.reference['protection_models']), 5)
        runtime.acknowledge(observation_time=0., applied_command=3.)
        self.assertEqual(runtime.controller.previous, 3.)
        self.assertIsNone(runtime.pending)

    def test_rejects_legacy_configuration(self):
        with self.assertRaises(ValueError):
            DepletionRuntime(bsa=1.85, initial_hb=9., guard_options={'interval_mode': 'legacy'})
        with self.assertRaises(ValueError):
            DepletionRuntime(bsa=1.85, initial_hb=9., controller_options={'reserve_mode': 'legacy'})

    def test_zero_return_reserve_ignores_optimistic_inflow_and_retained_fit(self):
        obs = Observation(0., 2., .85, 60., 9., .98, 37., None)
        belief = replace(Twin(9.).update(obs), venous_flow=7.)
        controller = DepletionController('hybrid', 1.85)
        controller.previous = 2.
        all_models = [(1., 2.), (12., 3.)]
        controller.set_reference_state(dict(bank_supported=True,
            pump_models=[(1., 2.)], protection_models=all_models, venous_bias_upper=0.))
        decision = controller.decide(obs, belief)
        self.assertAlmostEqual(controller.last_debug['braking_volume'],
                               joint_braking_reserve(all_models, decision.command, 0.))
        self.assertEqual(controller.last_debug['protection_inflow_floor'], 0.)

    def test_from_feasible_state_abrupt_zero_return_preserves_floor(self):
        for dt in (.5, 1., 2.):
            for tau in (1., 4., 12.):
                controller = DepletionController('hybrid', 1.85, dt=dt)
                controller.previous = 0.
                flow = 0.; volume = .85
                for k in range(round(240/dt)):
                    obs = Observation(k*dt, flow, volume, 60., 9., .98, 37., None)
                    belief = replace(Twin(9.).update(obs), venous_flow=6.)
                    controller.set_reference_state(dict(bank_supported=True,
                        protection_models=[(tau, flow)]))
                    before = controller.previous
                    decision = controller.decide(obs, belief)
                    self.assertLessEqual(abs(decision.command-before), .15*dt+1e-9)
                    following = decision.command+(flow-decision.command)*math.exp(-dt/tau)
                    # Supply can vanish without warning; no future return is
                    # passed into the controller or needed by its reserve.
                    qin = 5. if k*dt < 100 else 0.
                    volume += (qin-(flow+following)/2.)*dt/60.
                    flow = following
                    self.assertGreaterEqual(volume, .29-1e-8)


if __name__ == '__main__':
    unittest.main()
