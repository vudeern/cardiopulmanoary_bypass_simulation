import math,unittest
from perfusion_lab.model_bank import ModelBankGuard,ModelBankController,discrete_reserve
from perfusion_lab.sensing import Observation,Belief
from perfusion_lab.reference import LevelSample


class ModelBankTests(unittest.TestCase):
 def obs(self,t,v):return Observation(t,4.44,v,60.,9.,.98,37.,None)

 def test_calibrated_bank_covers_volume_despite_inline_drift(self):
  g=ModelBankGuard(4.44,calibration_error=.04,model_error_flow=.03,drift_allowance=.004)
  true=.85;flow=4.44;queue=[]
  for t in range(241):
   if t%60==0:queue.append(LevelSample(t,t+6,true))
   delivered=[s for s in queue if s.delivered==t]
   state=g.update(self.obs(t,true+.6*t/240.),[],delivered)
   if t>=66:
    self.assertTrue(state['bank_supported'])
    self.assertLessEqual(state['lower'],true+1e-8)
    self.assertGreaterEqual(state['estimate']+state['uncertainty'],true-1e-8)
    self.assertGreaterEqual(state['venous_bias_upper'],.6-1e-8)
   g.advance(4.2,4.8)
   nxt=4.2+(flow-4.2)*math.exp(-1/4.)
   true+=(4.2-(flow+nxt)/2)/60.;flow=nxt
  self.assertLess(state['uncertainty'],.2)

 def test_no_calibration_and_duplicates_do_not_create_support(self):
  g=ModelBankGuard(4.44)
  for t in range(20):
   s=g.update(self.obs(t,.85),[],[LevelSample(0,0,.85)])
   g.advance(4.44,4.44)
   self.assertFalse(s['bank_supported'])
  self.assertEqual(len(g.samples),1)

 def test_future_calibration_rejected(self):
  g=ModelBankGuard(4.44)
  with self.assertRaises(ValueError):g.update(self.obs(0,.85),[],[LevelSample(0,2,.85)])

 def test_discrete_reserve_bounds_independent_rollout(self):
  for tau in (1.,2.,4.,9.,12.):
   for x,u,q in ((5.,5.,2.),(1.,4.,2.),(6.,1.,3.),(3.,3.,3.)):
    predicted=discrete_reserve(max(0.,x-q),tau,max(0.,u-q),.15,1.)
    total=0.;flow=x;command=u
    for k in range(1500):
     if k:command=max(q,command-.15) if u>q else min(u,q)
     nxt=command+(flow-command)*math.exp(-1/tau)
     total+=max(0.,(flow+nxt)/2.-q)/60.;flow=nxt
    self.assertLessEqual(total,predicted+1e-9)

 def test_discrete_reserve_zero_and_invalid_inputs(self):
  self.assertEqual(discrete_reserve(0.,2.,0.,.15,1.),0.)
  with self.assertRaises(ValueError):discrete_reserve(1.,0.,1.,.15,1.)
  with self.assertRaises(ValueError):ModelBankGuard(4.44,model_taus=())

 def test_pi_and_unsupported_hybrid_match(self):
  b=Belief(9.,8.7,9.3,4.44,False,False,0.)
  a=ModelBankController('hybrid',1.85);p=ModelBankController('pi',1.85)
  state=dict(bank_supported=False,venous_bias_upper=2.,pump_models=[])
  for t in range(20):
   for c in (a,p):c.set_reference_state(state)
   self.assertEqual(a.decide(self.obs(t,.7),b),p.decide(self.obs(t,.7),b))

 def test_hard_reserve_cap_is_not_weakened_by_blending(self):
  c=ModelBankController('hybrid',1.85);b=Belief(9.,8.7,9.3,2.,False,False,0.)
  c.set_reference_state(dict(bank_supported=True,venous_bias_upper=0.,pump_models=[(8.,4.44)]))
  d=c.decide(self.obs(0,.3),b)
  self.assertTrue(d.infeasible);self.assertAlmostEqual(d.command,4.29)

 def test_harness_preserves_existing_timing_when_old_factories_used(self):
  from unittest.mock import patch
  from perfusion_lab.simulation import simulate
  from perfusion_lab.model_simulation import simulate_model
  from perfusion_lab.integrity import ReferenceGuard,IntegrityController
  args=dict(duration=180.,dt=1.,controller_kind='integrity_hybrid',level_mode='screened',venous_measurement={},calibration_options=dict(period=60.,delay=6.))
  expected=simulate('compound',**args)
  with patch('perfusion_lab.model_bank.ModelBankGuard',ReferenceGuard),patch('perfusion_lab.model_bank.ModelBankController',IntegrityController):
   actual=simulate_model('compound',**args)
  self.assertEqual(expected['metrics'],actual['metrics'])
  self.assertEqual([r['command'] for r in expected['rows']],[r['command'] for r in actual['rows']])

if __name__=='__main__':unittest.main()
