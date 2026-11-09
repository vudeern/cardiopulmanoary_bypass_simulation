import math
import unittest
from dataclasses import replace
from perfusion_lab.selective import SelectiveController
from perfusion_lab.sensing import Observation,Belief
from perfusion_lab.reference import LevelSample
from perfusion_lab.simulation import simulate
from perfusion_lab.stress import StressScenario


class SelectiveTests(unittest.TestCase):
 def fixture(self,t,level=.85):
  return Observation(t,4.44,level,60.,9.,.98,37.,None),Belief(9.,8.7,9.3,4.44,False,False,0.)

 def test_disabled_override_is_exact_pi(self):
  args=dict(seed=42,duration=600.,dt=1.,level_mode='hold',venous_measurement=dict(bias=.5),
    level_reference_options=dict(period=60.,delay=4.),controller_options=dict(tau_c=1.5,target_level=.45))
  scenario=StressScenario('combined',drainage=.3,level_profile='ramp',reservoir_bias=.6,dilution=2.)
  a=simulate(scenario,controller_kind='simc',**args)
  args['controller_options']={**args['controller_options'],'mode':'disabled'}
  b=simulate(scenario,controller_kind='selective',**args)
  self.assertEqual(a['metrics'],b['metrics'])
  self.assertEqual([r['command'] for r in a['rows']],[r['command'] for r in b['rows']])

 def test_no_references_is_exact_pi(self):
  args=dict(seed=33,duration=300.,dt=1.,level_mode='hold',venous_measurement={},level_reference_options=dict(dropout_prob=1.),controller_options=dict(tau_c=1.5,target_level=.45))
  a=simulate('compound',controller_kind='simc',**args);b=simulate('compound',controller_kind='selective',**args)
  self.assertEqual(a['metrics'],b['metrics'])
  self.assertTrue(all(r['override_weight']==0 for r in b['rows']))

 def trajectory(self,mode='hybrid',disagree=False,near_pressure=False):
  c=SelectiveController(1.85,max_age=15.,strength=1.,agreement=.08,mode=mode)
  volume=.85;flow=4.44;records=[]
  for t in range(100):
   if t in (0,30):c.observe_references([LevelSample(t,t,volume)])
   obs,b=self.fixture(t,volume+(.5 if disagree and t>=40 else 0.))
   if near_pressure:obs=replace(obs,pressure=86.)
   d=c.decide(obs,b);records.append(dict(c.last_debug,command=d.command))
   nxt=d.command+(flow-d.command)*math.exp(-1/2.)
   volume+=(4.44-(flow+nxt)/2)/60.;flow=nxt
  return c,records

 def test_two_references_and_age_gate_with_smooth_fallback(self):
  c,rows=self.trajectory()
  self.assertTrue(all(r['override_weight']==0 for r in rows[:30]))
  self.assertTrue(rows[30]['override_eligible'])
  self.assertAlmostEqual(rows[39]['override_weight'],1.)
  self.assertFalse(rows[46]['override_eligible'])
  self.assertAlmostEqual(rows[56]['override_weight'],0.)
  for a,b in zip(rows,rows[1:]):
   self.assertLessEqual(abs(a['override_weight']-b['override_weight']),.1+1e-12)
   self.assertLessEqual(abs(a['command']-b['command']),.15+1e-12)
  self.assertAlmostEqual(c.pi.core.bias+c.pi.core.settings.kc*c.pi.core.error+c.pi.core.integral,c.previous)

 def test_disagreement_fades_override_before_age_limit(self):
  _,rows=self.trajectory(disagree=True)
  self.assertFalse(rows[40]['override_eligible'])
  self.assertGreater(rows[40]['estimate_disagreement'],.08)
  self.assertLess(rows[40]['override_weight'],rows[39]['override_weight'])

 def test_component_direction(self):
  for mode in ('brake_only','boost_only'):
   _,rows=self.trajectory(mode=mode)
   for r in rows:
    if mode=='brake_only':self.assertLessEqual(r['override_delta'],1e-12)
    else:self.assertGreaterEqual(r['override_delta'],-1e-12)

 def test_recovery_screen_preserves_braking_direction(self):
  _,rows=self.trajectory(near_pressure=True)
  self.assertTrue(any(r['override_weight']>0 for r in rows))
  for r in rows:self.assertLessEqual(r['override_delta'],1e-12)

 def test_applied_command_drives_shadow_pump(self):
  c,rows=self.trajectory();flow=4.44
  for r in rows:flow=r['command']+(flow-r['command'])*math.exp(-.5)
  self.assertAlmostEqual(c.flow,flow,places=12)

 def test_duplicate_and_future_reference_handling(self):
  c=SelectiveController(1.85)
  for t in range(4):
   c.observe_references([LevelSample(0,0,.85)]);obs,b=self.fixture(t);c.decide(obs,b)
  self.assertEqual(c.reference_count,1)
  for sample in (LevelSample(0,2,.85),LevelSample(-1,0,.85)):
   c=SelectiveController(1.85);c.observe_references([sample]);obs,b=self.fixture(0)
   with self.assertRaises(ValueError):c.decide(obs,b)

 def test_arterial_sensor_invariance_and_pressure_limit(self):
  args=dict(duration=180.,dt=1.,controller_kind='selective',level_mode='hold',venous_measurement={})
  a=simulate(StressScenario('a'),**args);b=simulate(StressScenario('b',flow_bias=2.),**args)
  self.assertEqual(a['metrics'],b['metrics'])
  c=SelectiveController(1.85);obs,belief=self.fixture(0)
  self.assertLessEqual(c.decide(replace(obs,pressure=100.),belief).command,4.44)

 def test_invalid_params_and_timing(self):
  for options in (dict(strength=1.1),dict(agreement=0),dict(mode='wrong'),dict(max_age=float('nan'))):
   with self.assertRaises(ValueError):SelectiveController(1.85,**options)
  c=SelectiveController(1.85);obs,b=self.fixture(0);c.decide(obs,b)
  with self.assertRaises(ValueError):c.decide(obs,b)

if __name__=='__main__':unittest.main()
