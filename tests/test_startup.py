import math
import unittest
from perfusion_candidates.startup import StartupGuard, StartupRuntime
from perfusion_lab.depletion import DepletionGuard
from perfusion_lab.reference import LevelSample
from perfusion_lab.sensing import Observation


class StartupTests(unittest.TestCase):
    def test_one_anchor_bounds_volume_with_full_unknown_bias_prior(self):
        early = StartupGuard(4.44, calibration_error=.04, model_error_flow=.03)
        previous = DepletionGuard(4.44, calibration_error=.04, model_error_flow=.03)
        flow = 4.44; volume = .85; anchor = LevelSample(0., 6., .865)
        for t in range(120):
            obs = Observation(t, flow, volume+.1, 60., 9., .98, 37., None)
            samples = [anchor] if t == 6 else []
            state = early.update(obs, [], samples)
            old = previous.update(obs, [], samples)
            if t < 6:
                self.assertFalse(state['bank_supported'])
            else:
                self.assertTrue(state['bank_supported'])
                self.assertTrue(state['single_anchor_support'])
                self.assertLessEqual(state['lower'], volume+1e-9)
                self.assertGreaterEqual(state['estimate']+state['uncertainty'], volume-1e-9)
                self.assertGreaterEqual(state['venous_bias_upper'], 2.)
                self.assertFalse(old['bank_supported'])
                self.assertEqual(len(state['protection_models']), 5)
            command = 4.2+.3*math.sin(t/30.)
            for guard in (early, previous): guard.advance(command, 4.8)
            next_flow = command+(flow-command)*math.exp(-1/4.)
            volume += (4.2-(flow+next_flow)/2.)/60.; flow = next_flow

    def test_two_anchor_mode_and_missing_calibration_preserve_rc4(self):
        from perfusion_candidates.startup_simulation import simulate_startup
        from perfusion_candidates.simulation import simulate_finite_return
        args = dict(duration=180., dt=1., venous_measurement={},
            controller_options=dict(return_fraction=.5, return_horizon_s=15.),
            calibration_options=dict(period=60., delay=6.))
        expected = simulate_finite_return(**args)
        actual = simulate_startup(**args, reference_guard_options={'startup_minimum_anchors': 2})
        self.assertEqual(expected['metrics'], actual['metrics'])
        self.assertEqual(expected['rows'], actual['rows'])
        args['calibration_options']['dropout_prob'] = 1.
        expected = simulate_finite_return(**args)
        actual = simulate_startup(**args)
        self.assertEqual(expected['metrics'], actual['metrics'])
        self.assertEqual(expected['rows'], actual['rows'])

    def test_later_anchors_restore_identical_sets_for_identical_history(self):
        early = StartupGuard(4.44)
        previous = DepletionGuard(4.44)
        for t in range(181):
            obs = Observation(t, 4.44, .85, 60., 9., .98, 37., None)
            samples = [LevelSample(t-6, t, .85)] if t in (6, 66, 126) else []
            a = early.update(obs, [], samples); b = previous.update(obs, [], samples)
            if t >= 66:
                a.pop('single_anchor_support')
                self.assertEqual(a, b)
            for guard in (early, previous): guard.advance(4.44, 4.44)

    def test_stale_single_anchor_loses_support_and_bad_config_rejected(self):
        guard = StartupGuard(4.44, max_cal_age=10.)
        for t in range(12):
            obs = Observation(t, 4.44, .85, 60., 9., .98, 37., None)
            state = guard.update(obs, [], [LevelSample(0., 0., .85)] if t == 0 else [])
            guard.advance(4.44, 4.44)
        self.assertFalse(state['bank_supported'])
        with self.assertRaises(ValueError): StartupRuntime(bsa=1.85, initial_hb=9., guard_options={'startup_minimum_anchors': 0})


if __name__ == '__main__': unittest.main()
