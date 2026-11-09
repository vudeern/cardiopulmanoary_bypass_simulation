"""Timing, information isolation and analytic bias-correction behavior."""
import unittest
from perfusion_lab.reference import LevelReferences,LevelSample,ReferenceLevel
from perfusion_lab.sensing import Observation
from perfusion_lab.simulation import simulate

def obs(t,level):return Observation(t,4.5,level,63.,9.,.98,35.,None)

class ReferenceTests(unittest.TestCase):
    def test_delay_does_not_expose_future_sample(self):
        sensor=LevelReferences(1,delay=4.,noise_sd=0.)
        self.assertEqual(sensor.observe(0.,.8),[])
        self.assertEqual(sensor.observe(2.,.7),[])
        sample=sensor.observe(4.,.6)[0]
        self.assertEqual((sample.acquired,sample.delivered,sample.value),(0.,4.,.8))

    def test_timestamp_matching_avoids_motion_becoming_bias(self):
        observer=ReferenceLevel('hold')
        observer.update(obs(0.,1.2),[])
        result=observer.update(obs(4.,1.),[LevelSample(0.,4.,.8)])
        self.assertAlmostEqual(result['bias'],.4)
        self.assertAlmostEqual(result['estimate'],.6)
        self.assertEqual(result['age'],4.)

    def test_unknown_and_stale_bounded_response_is_explicit(self):
        observer=ReferenceLevel('bounded',max_age=10.)
        self.assertEqual(observer.update(obs(0.,1.),[])['lower'],0.)
        observer.update(obs(2.,1.),[LevelSample(0.,2.,.6)])
        result=observer.update(obs(20.,.9),[])
        self.assertTrue(result['unknown']);self.assertEqual(result['lower'],0.)

    def test_age_allowance_matches_hand_calculation(self):
        observer=ReferenceLevel('bounded')
        observer.update(obs(0.,1.2),[LevelSample(0.,0.,.8)])
        result=observer.update(obs(60.,1.2),[])
        self.assertAlmostEqual(result['lower'],.8-.04-.003*60.)

    def test_dropout_does_not_change_random_draw_alignment(self):
        a=LevelReferences(17,period=2.,delay=0.)
        b=LevelReferences(17,period=2.,delay=0.,outage_start=2.,outage_end=4.)
        for t in (0.,2.,4.):
            left,right=a.observe(t,.8),b.observe(t,.8)
            if t!=2.:self.assertEqual(left,right)
            else:self.assertEqual(right,[])

    def test_common_mode_contaminates_the_reference_as_declared(self):
        sensor=LevelReferences(1,delay=0.,noise_sd=0.,common_mode_fraction=1.)
        self.assertAlmostEqual(sensor.observe(0.,.8,.4)[0].value,1.2)

    def test_ignored_reference_preserves_all_metrics(self):
        a=simulate(seed=17,duration=120.)
        b=simulate(seed=17,duration=120.,level_reference_options={})
        self.assertEqual(a['metrics'],b['metrics'])
        self.assertEqual([r['command'] for r in a['rows']],[r['command'] for r in b['rows']])

    def test_future_and_invalid_configuration_rejected(self):
        with self.assertRaises(ValueError):
            ReferenceLevel('hold').update(obs(0.,1.),[LevelSample(0.,2.,.8)])
        for options in ({'period':0.},{'delay':-1.},{'dropout_prob':1.1}):
            with self.assertRaises(ValueError):LevelReferences(1,**options)

    def test_verdict_rejects_oxygen_gain_with_worse_depletion(self):
        from examples.reference_study import evaluate_verdict
        rows=[dict(group='good',variant='simple_reference',metric=m,low=lo,high=hi)
              for m,lo,hi in [('low_reservoir_s',-2.,1.),('empty_request_s',0.,0.),
                             ('deficit_auc',10.,20.)]]
        self.assertFalse(evaluate_verdict(rows)['demonstrated'])

    def test_verdict_requires_positive_paired_deficit_interval(self):
        from examples.reference_study import evaluate_verdict
        rows=[dict(group='good',variant='simple_reference',metric=m,low=lo,high=hi)
              for m,lo,hi in [('low_reservoir_s',0.,0.),('empty_request_s',0.,0.),
                             ('deficit_auc',-1.,20.)]]
        self.assertFalse(evaluate_verdict(rows)['demonstrated'])

if __name__=='__main__':unittest.main()
