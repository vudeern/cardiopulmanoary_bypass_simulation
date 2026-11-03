import unittest
from dataclasses import replace
from perfusion_lab.integrity import ReferenceGuard,FaultyReferences,IntegrityController
from perfusion_lab.reference import LevelSample
from perfusion_lab.sensing import Observation,Belief
from perfusion_lab.simulation import simulate
from perfusion_lab.stress import StressScenario


class IntegrityTests(unittest.TestCase):
 def obs(self,t,level=.85):return Observation(t,4.44,level,60.,9.,.98,37.,None)
 def step(self,g,t,routine=(),cal=(),level=.85):
  result=g.update(self.obs(t,level),routine,cal);g.advance(4.44,4.44);return result

 def test_startup_bias_checked_before_correction(self):
  g=ReferenceGuard(4.44)
  for t in range(7):
   r=self.step(g,t,[LevelSample(0,4,1.07)] if t==4 else [],[LevelSample(0,6,.85)] if t==6 else [])
   if t==4:self.assertFalse(r['events'])
  self.assertTrue(r['quarantined']);self.assertEqual(len(r['events']),1)
  self.assertEqual(r['events'][0]['reason'],'paired_audit_disagreement')
  self.assertFalse(r['events'][0]['accepted']);self.assertAlmostEqual(r['estimate'],.85)

 def test_clean_sample_accepted_and_jump_quarantined(self):
  g=ReferenceGuard(4.44,audit_wait=0.)
  r=self.step(g,0,[LevelSample(0,0,.85)],[LevelSample(0,0,.85)])
  self.assertTrue(r['events'][0]['accepted']);self.assertFalse(r['quarantined'])
  for t in range(1,61):r=self.step(g,t,[LevelSample(60,60,1.15)] if t==60 else [])
  self.assertTrue(r['quarantined']);self.assertFalse(r['events'][0]['accepted'])
  self.assertAlmostEqual(r['estimate'],.85)

 def test_valid_sample_can_be_rejected_when_inline_changes(self):
  g=ReferenceGuard(4.44,audit_wait=0.)
  self.step(g,0,[LevelSample(0,0,.85)],[LevelSample(0,0,.85)])
  for t in range(1,61):r=self.step(g,t,[LevelSample(60,60,.85)] if t==60 else [],level=1.45)
  self.assertFalse(r['events'][0]['accepted'])
  self.assertEqual(r['events'][0]['reason'],'prediction_disagreement')

 def test_shared_corruption_is_not_detectable_by_pair_agreement(self):
  g=ReferenceGuard(4.44,audit_wait=0.)
  r=self.step(g,0,[LevelSample(0,0,1.07)],[LevelSample(0,0,1.07)])
  self.assertTrue(r['events'][0]['accepted']);self.assertAlmostEqual(r['estimate'],1.07)
  # Actual .85 is known only to this test; the observer receives no such truth.
  self.assertGreater(r['estimate']-.85,.2)

 def test_uncertainty_grows_from_acquisition_not_arrival(self):
  g=ReferenceGuard(4.44,base_uncertainty=.04,drift_allowance=.002)
  for t in range(11):r=self.step(g,t,cal=[LevelSample(0,6,.85)] if t==6 else [])
  self.assertAlmostEqual(r['uncertainty'],.06);self.assertAlmostEqual(r['lower'],.79)
  self.assertEqual(r['calibration_count'],1);self.assertFalse(r['supported'])

 def test_future_and_unmatched_acquisitions_rejected(self):
  for sample in (LevelSample(0,4,.85),LevelSample(-1,0,.85)):
   g=ReferenceGuard(4.44)
   with self.assertRaises(ValueError):g.update(self.obs(0),[],[sample])

 def test_duplicate_calibration_cannot_inflate_support(self):
  g=ReferenceGuard(4.44)
  for t in range(5):r=self.step(g,t,cal=[LevelSample(0,0,.85)])
  self.assertEqual(r['calibration_count'],1);self.assertFalse(r['supported'])

 def test_clean_audits_required_for_recovery(self):
  g=ReferenceGuard(4.44,audit_wait=0.,clean_audits=2)
  r=self.step(g,0,[LevelSample(0,0,.85)],[LevelSample(0,0,.85)])
  self.assertTrue(r['quarantined'])
  for t in range(1,61):r=self.step(g,t,[LevelSample(60,60,.85)] if t==60 else [],[LevelSample(60,60,.85)] if t==60 else [])
  self.assertFalse(r['quarantined']);self.assertTrue(r['supported'])

 def test_quarantine_blocks_upward_override_during_fade(self):
  c=IntegrityController('hybrid',1.85);b=Belief(9.,8.7,9.3,4.44,False,False,0.)
  c.weight=1.;c.set_reference_state(dict(venous_bias=0.,supported=False))
  d=c.decide(self.obs(0),b)
  self.assertGreater(c.weight,0.);self.assertLessEqual(d.command,c.last_debug['pi_command'])

 def test_calibration_only_pi_ignores_corrupted_routine(self):
  args=dict(duration=180.,dt=1.,level_mode='calibration_only',controller_kind='simc',venous_measurement={},calibration_options=dict(period=60.,delay=6.),controller_options=dict(tau_c=5.,target_level=.65))
  a=simulate(StressScenario('clean'),reference_fault_options=dict(fault_bias=.4),**args)
  b=simulate(StressScenario('clean'),reference_fault_options=dict(fault_bias=-.4),**args)
  self.assertEqual(a['metrics'],b['metrics'])
  self.assertEqual([r['command'] for r in a['rows']],[r['command'] for r in b['rows']])

 def test_fault_profiles_and_labels_are_sensor_only(self):
  s=FaultyReferences(0,period=1.,delay=0.,noise_sd=0.,profile='step',start=2.,fault_bias=.2)
  self.assertEqual(s.observe(0,.85)[0].value,.85)
  self.assertEqual(s.observe(2,.85)[0].value,1.05)
  self.assertEqual(s.labels[2.],.2)

 def test_screening_ablation_uses_same_inputs_but_accepts_bad_reference(self):
  g=ReferenceGuard(4.44,audit_wait=0.,screen=False)
  r=self.step(g,0,[LevelSample(0,0,1.07)],[LevelSample(0,0,.85)])
  self.assertTrue(r['events'][0]['accepted']);self.assertAlmostEqual(r['estimate'],1.07)

 def test_invalid_settings_and_explicit_inputs(self):
  for kw in (dict(dt=0.),dict(drift_allowance=-1.),dict(clean_audits=3)):
   with self.assertRaises(ValueError):ReferenceGuard(4.44,**kw)
  with self.assertRaises(ValueError):simulate(duration=10.,dt=1.,level_mode='screened')

if __name__=='__main__':unittest.main()
