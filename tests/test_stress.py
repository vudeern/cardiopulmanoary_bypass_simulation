"""Independent invariants and causal inputs for unfamiliar-model challenges."""
import math
import unittest
import csv
from pathlib import Path
from perfusion_lab.model import Patient,Plant
from perfusion_lab.stress import StressPlant,StressScenario
from perfusion_lab.sensing import Sensors
from perfusion_lab.simulation import simulate


class StressTests(unittest.TestCase):
    def test_default_metrics_match_all_42_frozen_replay_cases(self):
        root=Path(__file__).resolve().parents[1]
        with (root/'results/metrics.csv').open() as handle:
            records=list(csv.DictReader(handle))
        records=[r for r in records if r['seed']=='100']
        self.assertEqual(len(records),42)
        for record in records:
            result=simulate(record['scenario'],record['policy'],seed=100)
            for metric,value in result['metrics'].items():
                self.assertEqual(value,float(record[metric]),(record['scenario'],record['policy'],metric))

    def test_neutral_alternate_plant_matches_original_exactly(self):
        a,b=Plant(Patient()),StressPlant(Patient())
        for i in range(80):
            q=3. if i%2 else 6.
            self.assertEqual(a.step(q,.45 if i>20 else 1.,2.),
                             b.step(q,.45 if i>20 else 1.,2.))

    def test_slow_actuator_matches_hand_calculation(self):
        p=Patient();plant=StressPlant(p,actuator_tau=8.)
        plant.step(6.,1.,2.)
        self.assertAlmostEqual(plant.flow,6.+(2.4*p.bsa-6.)*math.exp(-2./8.))

    def test_lagged_drainage_conserves_volume(self):
        p=Patient();plant=StressPlant(p,drainage_tau=12.,venous_nonlinearity=.04)
        for i in range(100):
            result=plant.step(7. if i%2 else 0.,.1 if i<50 else 1.,2.)
            self.assertAlmostEqual(result['reservoir']+result['patient_volume'],p.volume)
            self.assertGreaterEqual(result['reservoir'],0.)
            self.assertGreaterEqual(result['qv'],0.)
            self.assertLessEqual(result['qv'],7.5)

    def test_ramp_has_no_removal_jump(self):
        s=StressScenario('ramp',level_profile='ramp',reservoir_bias=.4)
        values=[s.inputs(t,1200.)['reservoir_bias'] for t in range(0,1200,2)]
        self.assertEqual(values[0],0.)
        self.assertAlmostEqual(values[-1],.4)
        self.assertTrue(all(0<=b-a<=.003 for a,b in zip(values,values[1:])))

    def test_initial_offset_exists_at_first_observation(self):
        s=StressScenario('initial',level_profile='initial',reservoir_bias=.4)
        self.assertEqual(s.inputs(0.,1200.)['reservoir_bias'],.4)

    def test_flow_fault_changes_only_explicit_sensor_channel(self):
        state=dict(flow=4.5,reservoir=.85,pressure=63.)
        inputs=StressScenario('flow',event_start=.2,event_end=.6,flow_bias=.75).inputs(500.,1200.)
        a=Sensors(17).observe(500.,state,9.,{**inputs,'flow_bias':0.})
        b=Sensors(17).observe(500.,state,9.,inputs)
        self.assertAlmostEqual(b.flow-a.flow,.75)
        self.assertEqual(a.reservoir,b.reservoir)
        self.assertEqual(a.hb_inline,b.hb_inline)

    def test_hidden_stress_config_is_logged_separately(self):
        r=simulate(StressScenario('ramp',level_profile='ramp',reservoir_bias=.4),
                   duration=120.,plant_options={'actuator_tau':8.})
        self.assertEqual(r['plant_model'],'StressPlant')
        self.assertEqual(r['plant_options'],{'actuator_tau':8.})
        self.assertEqual(r['controller_options'],{})

    def test_invalid_stress_settings_are_rejected(self):
        for options in ({'actuator_tau':0.},{'drainage_tau':-1.},{'max_drainage':float('nan')}):
            with self.assertRaises(ValueError):StressPlant(Patient(),**options)
        with self.assertRaises(ValueError):StressScenario('bad',level_profile='unknown')
        with self.assertRaises(ValueError):StressScenario('bad',event_start=.8,event_end=.4)


if __name__=='__main__':unittest.main()
