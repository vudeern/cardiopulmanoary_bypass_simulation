import math
import unittest
from dataclasses import replace
from perfusion_lab.braking import braking_volume,BrakingController
from perfusion_lab.sensing import Observation,Belief
from perfusion_lab.simulation import simulate


def observation(level=.85,age=4.,pressure=65.):
 return Observation(0.,4.5,level,pressure,9.4,.98,37.,9.4,age)

def belief(qv=4.5):return Belief(9.4,9.1,9.7,qv,False,False,0.)


class BrakingTests(unittest.TestCase):
 def test_units_and_zero_excess(self):
  self.assertEqual(braking_volume(4.,4.,4.5,10.,.15,1.),0.)
  self.assertAlmostEqual(braking_volume(5.,5.,4.,10.,.15,1.),(10+1+1/.3)/60.)

 def test_reserve_bounds_independent_numerical_braking(self):
  for initial,command,qin,tau in ((5.,5.,3.,2.),(5.,4.,3.,10.),(2.,5.,3.,8.),(6.,2.,3.,7.),(0.,4.,2.,1.)):
   h=.01;flow=initial;volume=0.
   # Actual controller brakes toward inflow after a one-second hold.
   for i in range(20000):
    t=i*h;u=command if t<1. else max(qin,command-.15*(t-1.))
    old=flow;flow=u+(flow-u)*math.exp(-h/tau)
    volume+=max(0.,(old+flow)/2-qin)*h/60.
   self.assertLessEqual(volume,braking_volume(initial,command,qin,10.,.15,1.)+1e-4)

 def test_command_history_bounds_actual_actuator_state(self):
  for tau in (1.,2.,5.,10.):
   c=BrakingController(1.85);flow=c.previous
   for step in range(100):
    obs=replace(observation(level=.7 if step<40 else 1.2),time=float(step))
    d=c.decide(obs,belief(3. if step<40 else 6.))
    flow=d.command+(flow-d.command)*math.exp(-1./tau)
    self.assertLessEqual(flow,c.flow_upper+1e-10)
    self.assertGreaterEqual(flow,c.flow_lower-1e-10)

 def test_unknown_reference_and_infeasible_braking_are_explicit(self):
  for obs in (observation(age=None),observation(level=.1)):
   c=BrakingController(1.85);previous=c.previous;d=c.decide(obs,belief())
   self.assertTrue(d.infeasible);self.assertAlmostEqual(d.command,previous-.15)
   self.assertFalse(c.last_debug['braking_feasible'])

 def test_age_and_bias_allowances_reduce_available_reserve(self):
  a=BrakingController(1.85);b=BrakingController(1.85)
  a.decide(observation(age=4.),belief());b.decide(observation(age=60.),belief())
  self.assertLess(b.last_debug['braking_budget'],a.last_debug['braking_budget'])
  self.assertAlmostEqual(a.last_debug['inflow_lower'],3.7)

 def test_unused_arterial_flow_measurement_cannot_change_decision(self):
  a=BrakingController(1.85);b=BrakingController(1.85)
  obs=observation();other=replace(obs,flow=obs.flow+3.)
  self.assertEqual(a.decide(obs,belief()),b.decide(other,belief()))

 def test_common_constraints_and_no_hidden_information(self):
  r=simulate('compound',seed=24000,duration=60.,dt=1.,controller_kind='braking',
    venous_measurement={},level_mode='hold',level_reference_options={})
  previous=2.4*r['patient']['bsa']
  for row in r['rows']:
   self.assertTrue(0<=row['command']<=7.)
   self.assertLessEqual(abs(row['command']-previous),.15+1e-9)
   if row['braking_feasible']:self.assertLessEqual(row['braking_volume'],row['braking_budget']+1e-8)
   previous=row['command']
  with self.assertRaises(ValueError):simulate(duration=10.,controller_kind='braking')

 def test_reference_bias_trend_updates_allowance_without_a_fake_volume_jump(self):
  c=BrakingController(1.85,drift_allowance=.0005,rate_multiplier=2.)
  c.decide(replace(observation(age=4.),time=4.),belief())
  # Raw reading is still .85; only the delivered correction changes by .12.
  obs=replace(observation(level=.73,age=4.),time=64.,level_reference_bias=.12)
  c.decide(obs,belief())
  self.assertAlmostEqual(c.last_debug['estimated_drift_rate'],.004)

 def test_invalid_allowances_rejected(self):
  for values in ({'venous_allowance':-1.},{'tau_upper':.5},{'drift_allowance':math.nan}):
   with self.assertRaises(ValueError):BrakingController(1.85,**values)


if __name__=='__main__':unittest.main()
