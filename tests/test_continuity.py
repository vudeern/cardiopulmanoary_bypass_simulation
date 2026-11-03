import math
import unittest
from dataclasses import replace
from perfusion_lab.continuity import ContinuityController
from perfusion_lab.sensing import Observation,Belief
from perfusion_lab.reference import LevelSample
from perfusion_lab.simulation import simulate
from perfusion_lab.stress import StressScenario


class ContinuityTests(unittest.TestCase):
 def fixture(self,t,level,venous=4.8):
  return Observation(t,4.2,level,60.,9.,.98,37.,None),Belief(9.,8.7,9.3,venous,False,False,0.)

 def exercise(self,inline_drift=0.,nominal_tau=4.):
  c=ContinuityController(1.85,nominal_tau=nominal_tau)
  flow=2.4*1.85;volume=.85;queue=[];snapshots=[]
  for t in range(420):
   if t in (0,60):queue.append(LevelSample(t,t+3,volume))
   c.observe_references([s for s in queue if s.delivered==t])
   obs,b=self.fixture(t,volume+inline_drift*t/420)
   d=c.decide(obs,b)
   snapshots.append((d.command,volume,dict(c.last_debug)))
   next_flow=d.command+(flow-d.command)*math.exp(-1/nominal_tau)
   volume+=(4.2-(flow+next_flow)/2)/60.;flow=next_flow
  return c,snapshots

 def test_reference_bias_fit_and_outage_prediction(self):
  c,rows=self.exercise()
  self.assertAlmostEqual(c.venous_bias,.6,places=10)
  for _,truth,debug in rows[63:]:
   self.assertAlmostEqual(debug['balance_level_estimate'],truth,places=10)
  self.assertGreater(rows[-1][2]['balance_reference_age'],180)
  self.assertFalse(rows[-1][2]['level_information_unknown'])
  self.assertGreater(rows[-1][0],1.)

 def test_inline_drift_cannot_change_anchored_commands(self):
  # Before first reference arrival the inline reading remains a fallback.
  # Keep pre-anchor histories identical, then drift only after anchoring.
  c=ContinuityController(1.85);d=ContinuityController(1.85)
  for t in range(300):
   if t==0:
    for controller in (c,d):controller.observe_references([LevelSample(0,0,.85)])
   obs,belief=self.fixture(t,.85)
   one=c.decide(obs,belief);two=d.decide(replace(obs,reservoir=.85+float(t)/300),belief)
   self.assertEqual(one,two)

 def test_rate_and_oxygen_constraints(self):
  c=ContinuityController(1.85)
  previous=c.previous
  for t in range(25):
   obs,b=self.fixture(t,.3)
   cmd=c.decide(replace(obs,pressure=110.),b).command
   self.assertGreaterEqual(cmd,0.);self.assertLessEqual(cmd,7.)
   self.assertLessEqual(abs(cmd-previous),.15+1e-12);self.assertLessEqual(cmd,previous)
   previous=cmd

 def test_no_reference_is_flagged_not_disguised_as_anchored(self):
  c=ContinuityController(1.85);obs,b=self.fixture(0,.85);c.decide(obs,b)
  self.assertTrue(c.last_debug['level_information_unknown'])
  self.assertIsNone(c.last_debug['balance_reference_age'])

 def test_future_and_unmatched_references_rejected(self):
  for sample in (LevelSample(0,4,.85),LevelSample(-1,0,.85)):
   c=ContinuityController(1.85);c.observe_references([sample]);obs,b=self.fixture(0,.85)
   with self.assertRaises(ValueError):c.decide(obs,b)

 def test_duplicate_old_reference_does_not_rewind_anchor(self):
  c=ContinuityController(1.85)
  for t in range(3):
   c.observe_references([LevelSample(0,0,.85)])
   obs,b=self.fixture(t,.85);c.decide(obs,b)
  self.assertEqual(c.anchor[0],0.);self.assertEqual(c.venous_bias,0.)

 def test_invalid_parameters_and_timing(self):
  for opts in (dict(nominal_tau=0.),dict(age_allowance=-1.),dict(tau_lower=11.),dict(base_allowance=float('nan'))):
   with self.assertRaises(ValueError):ContinuityController(1.85,**opts)
  c=ContinuityController(1.85);obs,b=self.fixture(0,.85);c.decide(obs,b)
  with self.assertRaises(ValueError):c.decide(obs,b)

 def test_arterial_flow_sensor_is_unused(self):
  args=dict(controller_kind='continuity',duration=120.,dt=1.,venous_measurement={},level_mode='hold')
  a=simulate(StressScenario('clean'),**args);b=simulate(StressScenario('bias',flow_bias=2.),**args)
  self.assertEqual(a['metrics'],b['metrics'])
  self.assertEqual([r['command'] for r in a['rows']],[r['command'] for r in b['rows']])

if __name__=='__main__':unittest.main()
