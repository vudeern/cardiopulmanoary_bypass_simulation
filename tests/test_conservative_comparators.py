"""Comparator behavior and actuator constraints, independent of study outcomes."""
import unittest

from perfusion_lab.control import Controller
from perfusion_lab.sensing import Observation, Twin
from perfusion_lab.simulation import simulate


class ComparatorTests(unittest.TestCase):
    def test_zero_margin_preserves_original_trajectory(self):
        original = simulate('unmodeled_level_bias', seed=17)
        same = simulate('unmodeled_level_bias', seed=17,
                        controller_options={'reserve_margin':0.})
        self.assertEqual(original['rows'], same['rows'])
        self.assertEqual(original['metrics'], same['metrics'])

    def test_reserve_margin_can_limit_command_before_guard_detects(self):
        obs = Observation(0., 4.5, .5, 63., 7., .98, 35., None)
        belief = Twin(7.).update(obs)
        plain = Controller('sentinel', 1.85).decide(obs, belief)
        reserve = Controller('sentinel', 1.85, reserve_margin=.4).decide(obs, belief)
        self.assertLess(reserve.command, plain.command)

    def test_flow_cap_respects_slew_on_initial_ramp(self):
        r = simulate('nominal', seed=7, duration=120.,
                     controller_options={'flow_cap_index':1.6})
        previous = 2.4*r['patient']['bsa']
        cap = 1.6*r['patient']['bsa']
        for row in r['rows']:
            self.assertLessEqual(abs(row['command']-previous), .3+1e-9)
            self.assertLessEqual(row['command'], max(cap, previous-.3)+1e-9)
            previous = row['command']
        self.assertLessEqual(previous, cap+1e-9)

    def test_invalid_configuration_is_rejected(self):
        for options in ({'reserve_margin':-.1}, {'reserve_margin':float('nan')},
                        {'flow_cap_index':0.}, {'flow_cap_index':float('inf')}):
            with self.assertRaises(ValueError):
                Controller('sentinel', 1.85, **options)
        with self.assertRaises(ValueError):
            Controller('sentinel_guarded', 1.85, reserve_margin=.1)

    def test_cap_uses_patient_size_and_is_recorded(self):
        options = {'flow_cap_index':1.8}
        r = simulate('compound', seed=7, duration=60., controller_options=options)
        self.assertEqual(r['controller_options'], options)
        self.assertEqual(options, {'flow_cap_index':1.8})


if __name__ == '__main__':
    unittest.main()
