"""Level-fault identifiability, causal isolation and regression checks."""
from dataclasses import replace
import unittest

from perfusion_lab.sensing import Observation, Twin
from perfusion_lab.simulation import simulate


def obs(t, level):
    return Observation(t, 4.5, level, 63., 9., .98, 35., None)


class LevelGuardTests(unittest.TestCase):
    def test_positive_step_is_removed_from_level_and_drainage(self):
        twin = Twin(9., guard_level=True)
        twin.update(obs(0., .8))
        belief = twin.update(obs(2., 1.2))
        self.assertTrue(belief.level_fault)
        self.assertAlmostEqual(belief.level_bias, .4)
        self.assertAlmostEqual(belief.reservoir_lower, .72)
        self.assertAlmostEqual(belief.venous_flow, 4.5)

    def test_offset_removal_is_not_a_real_depletion(self):
        twin = Twin(9., guard_level=True)
        for t, level in [(0., .8), (2., 1.2), (4., 1.2)]:
            twin.update(obs(t, level))
        belief = twin.update(obs(6., .8))
        self.assertAlmostEqual(belief.level_bias, 0.)
        self.assertAlmostEqual(belief.venous_flow, 4.5)
        self.assertTrue(belief.level_fault)  # Explicitly latched; no recovery claim.

    def test_constant_initial_offset_is_not_identified(self):
        twin = Twin(9., guard_level=True)
        for t in range(0, 20, 2):
            belief = twin.update(obs(t, 1.2))
        self.assertFalse(belief.level_fault)
        self.assertEqual(belief.level_bias, 0.)

    def test_slow_drift_is_not_identified(self):
        twin = Twin(9., guard_level=True)
        for t in range(0, 100, 2):
            belief = twin.update(obs(t, .8+.001*t))
        self.assertFalse(belief.level_fault)

    def test_physically_possible_drainage_change_is_not_a_fault(self):
        twin = Twin(9., guard_level=True)
        twin.update(obs(0., .8))
        belief = twin.update(obs(2., .8-4.5*2/60.))
        self.assertFalse(belief.level_fault)  # Complete loss of drainage.

    def test_disabled_guard_preserves_original_observer(self):
        twin = Twin(9.)
        twin.update(obs(0., .8))
        belief = twin.update(obs(2., 1.2))
        self.assertFalse(belief.level_fault)
        self.assertIsNone(belief.reservoir_lower)

    def test_hb_reference_does_not_change_level_guard(self):
        a, b = Twin(9., guard_level=True), Twin(9., guard_level=True)
        for t, level in [(0., .8), (2., 1.2), (4., 1.2)]:
            left = a.update(obs(t, level))
            right = b.update(replace(obs(t, level), hb_lab=8., hb_inline=12.))
            self.assertEqual(left.level_bias, right.level_bias)
            self.assertEqual(left.reservoir_lower, right.reservoir_lower)

    def test_nominal_run_has_no_alarm_and_matches_original(self):
        baseline = simulate('nominal', 'sentinel', seed=7)
        guarded = simulate('nominal', 'sentinel_guarded', seed=7)
        self.assertEqual(baseline['metrics'], guarded['metrics'])
        self.assertEqual([r['command'] for r in baseline['rows']],
                         [r['command'] for r in guarded['rows']])


if __name__ == '__main__':
    unittest.main()
