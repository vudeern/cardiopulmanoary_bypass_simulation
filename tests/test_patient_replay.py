import math
from pathlib import Path
import tempfile
import unittest

from perfusion_lab.model import delivery
from perfusion_lab.patient_replay import read_observations, replay_oxygen

ROOT=Path(__file__).resolve().parents[1]


class PatientReplayTests(unittest.TestCase):
    def test_known_oxygen_arithmetic_and_legacy_default(self):
        self.assertAlmostEqual(delivery(5,10,.99,2,300),354.9)
        self.assertEqual(delivery(5,10,.99,2),delivery(5,10,.99,2,150))

    def test_missing_saturation_is_not_imputed_or_relabelled_measured(self):
        rows=read_observations(ROOT/'data/published-case/observations.csv')
        results=replay_oxygen(rows,2.73)
        self.assertEqual(len(results),5)
        self.assertTrue(all(r['sao2_fraction'] is None for r in results))
        self.assertTrue(all(r['saturation_status']=='unmeasured_sensitivity' for r in results))
        r=results[0]
        self.assertAlmostEqual(r['project_do2i_high'],296.41509/2.73)
        self.assertAlmostEqual(r['reported_do2i'],301.62/2.73)
        self.assertAlmostEqual(r['measured_pao2_increment_do2i'],10*2.61*.0031*(521-150)/2.73)

    def test_recorded_saturation_collapses_assumption_range(self):
        rows=read_observations(ROOT/'data/published-case/observations.csv')
        rows[0]['sao2_fraction']=.95
        r=replay_oxygen(rows,2.73)[0]
        self.assertEqual(r['saturation_status'],'recorded')
        self.assertEqual(r['project_do2i_low'],r['project_do2i_high'])
        self.assertEqual(r['saturation_endpoints'],[.95,.95])

    def test_rejects_bad_units_missing_values_and_time_order(self):
        original=(ROOT/'data/published-case/observations.csv').read_text()
        bad=[original.replace('480,2.61','1380,2.61'),
             original.replace('521,,','521,99,'),
             original.replace('521,,','nan,,'),
             original.replace('480,2.61','480,-2.61'),
             original.replace('flow_l_min','flow_ml_min'),
             original.replace('7.27',''),
             original.splitlines()[0]+'\n',
             original.splitlines()[0]+'\n480,2.61\n']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'observations.csv'
            for data in bad:
                with self.subTest(data=data[:100]):
                    p.write_text(data)
                    with self.assertRaises(ValueError):read_observations(p)

    def test_rejects_invalid_assumptions(self):
        rows=read_observations(ROOT/'data/published-case/observations.csv')
        for bsa in [0,-1,math.nan,math.inf]:
            with self.assertRaises(ValueError):replay_oxygen(rows,bsa)
        for endpoints in [(-.1,1),(.99,.98),(0,1.1),(math.nan,1)]:
            with self.assertRaises(ValueError):replay_oxygen(rows,2.73,endpoints)


if __name__=='__main__':unittest.main()
