import unittest
from dataclasses import replace
from perfusion_candidates.calibrated_pump import CalibratedPumpController
from perfusion_candidates.finite_return import FiniteReturnController, finite_return_reserve
from perfusion_lab.sensing import Observation, Twin


class CalibratedPumpTests(unittest.TestCase):
    def decision(self, cls, state):
        controller = cls('hybrid', 1.85, return_fraction=.5, return_horizon_s=15.)
        controller.previous = 2.
        controller.set_reference_state(state)
        obs = Observation(0., 2., .85, 60., 9., .98, 37., None)
        belief = replace(Twin(9.).update(obs), venous_flow=4.)
        return controller, controller.decide(obs, belief)

    def test_identical_hypotheses_preserve_rc4_decision(self):
        models = [(1.,2.), (4.,2.), (12.,3.)]
        state = dict(bank_supported=True, venous_bias_upper=.2, pump_models=models, protection_models=models)
        old, a = self.decision(FiniteReturnController, state)
        new, b = self.decision(CalibratedPumpController, state)
        self.assertEqual(a,b)
        for key,value in old.last_debug.items(): self.assertEqual(value,new.last_debug[key])

    def test_reserve_uses_only_declared_calibration_consistent_set(self):
        retained = [(2.,2.), (4.,2.)]
        all_models = retained+[(12.,5.)]
        state = dict(bank_supported=True, venous_bias_upper=.2, pump_models=retained, protection_models=all_models)
        controller, decision = self.decision(CalibratedPumpController,state)
        self.assertEqual(controller.last_debug['protection_model_count'],2)
        self.assertAlmostEqual(controller.last_debug['braking_volume'],
            finite_return_reserve(retained,decision.command,.5*(4.-.2-.1),15.))

    def test_unsupported_information_still_brakes(self):
        state = dict(bank_supported=False, venous_bias_upper=2., pump_models=[], protection_models=[(12.,5.)])
        controller, decision = self.decision(CalibratedPumpController,state)
        self.assertAlmostEqual(decision.command,1.85)
        self.assertTrue(decision.infeasible)
        self.assertTrue(controller.last_debug['protection_unsupported'])


if __name__ == '__main__': unittest.main()
