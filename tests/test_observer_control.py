"""Fault identifiability, no-future-data behavior and experimental pairing."""
import unittest
from dataclasses import replace
from perfusion_lab.sensing import Observation, Twin
from perfusion_lab.control import Controller, POLICIES
from perfusion_lab.simulation import simulate
from perfusion_lab.benchmark import paired_interval
from perfusion_lab.model import SCENARIOS


def observation(t=0, hb=11, lab=9):
    return Observation(t, 4.5, .8, 63, hb, .98, 35, lab)


class ObserverTests(unittest.TestCase):
    def test_independent_reference_identifies_bias(self):
        twin=Twin(9)
        belief=twin.update(observation())
        self.assertEqual(belief.hb,9)
        self.assertTrue(belief.fault)
        self.assertLess(belief.hb_lower,9)

    def test_without_reference_bias_not_identifiable(self):
        belief=Twin(9).update(observation(lab=None))
        self.assertEqual(belief.hb,11)
        self.assertFalse(belief.fault)

    def test_dropout_widens_bounds(self):
        twin=Twin(9)
        a=twin.update(observation())
        b=twin.update(observation(t=30,hb=None,lab=None))
        self.assertTrue(b.stale)
        self.assertGreater(b.hb_upper-b.hb_lower,a.hb_upper-a.hb_lower)

    def test_no_lookahead_can_request_more_flow_at_low_level(self):
        obs=replace(observation(),reservoir=.26)
        belief=Twin(9).update(obs)
        sentinel=Controller('sentinel',1.85).decide(obs,belief)
        ablation=Controller('no_lookahead',1.85).decide(obs,belief)
        self.assertLessEqual(sentinel.command,ablation.command)

    def test_limits_all_policies(self):
        for policy in POLICIES:
            result=simulate('compound',policy,5,duration=120)
            commands=[2.4*result['patient']['bsa']]+[r['command'] for r in result['rows']]
            self.assertTrue(all(0<=q<=7 for q in commands))
            self.assertTrue(all(abs(a-b)<=.3+1e-9 for a,b in zip(commands,commands[1:])))

    def test_full_grid_smoke(self):
        for scenario in SCENARIOS:
            for policy in POLICIES:
                result=simulate(scenario,policy,100,duration=60)
                self.assertEqual(len(result['rows']),30)
                self.assertGreaterEqual(result['metrics']['deficit_auc'],0)

    def test_paired_interval_known_constant(self):
        result=paired_interval([3,3,3])
        self.assertEqual((result['mean'],result['low'],result['high']),(3,3,3))

    def test_no_controller_affects_scenario_hb(self):
        a=simulate('hb_bias','fixed',100,duration=120)
        b=simulate('hb_bias','sentinel',100,duration=120)
        self.assertEqual([r['hb_inline'] for r in a['rows']], [r['hb_inline'] for r in b['rows']])

    def test_custom_scenario_and_reference_period(self):
        from perfusion_lab.model import Scenario
        result=simulate(Scenario('custom',hb_bias=1.5),duration=120,lab_period=20)
        self.assertEqual(result['scenario'],'custom')
        self.assertEqual(result['lab_period'],20)
        self.assertEqual(result['scenario_parameters']['hb_bias'],1.5)
        self.assertLessEqual(max(r['reference_age'] for r in result['rows']),18)

    def test_invalid_fault_parameters(self):
        from perfusion_lab.model import Scenario
        for kw in ({'drainage':-1},{'saturation_loss':.6},{'hb_bias':float('nan')}):
            with self.assertRaises(ValueError):
                Scenario('invalid',**kw)
        with self.assertRaises(ValueError):
            simulate(lab_period=0)

    def test_reassurance_metrics_do_not_exceed_total_exposure(self):
        r=simulate('compound','reactive',100)['metrics']
        self.assertLessEqual(r['false_reassurance_margin_s'],r['false_reassurance_s'])
        self.assertLessEqual(r['concealed_deficit_auc'],r['deficit_auc'])
