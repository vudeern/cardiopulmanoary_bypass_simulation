import copy,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
try:
 from scipy.sparse import csr_matrix
except ImportError:
 raise unittest.SkipTest("Install perfusion-sentinel[audit] for numerical audit tests")
from perfusion_lab.audit import relaxation,physical_bound,dual_lower_bound,witness,emergency_feasible,pressure_envelope
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario,StressPlant


class AuditTests(unittest.TestCase):
 def test_checked_dual_known_optimum_and_bad_multipliers(self):
  p=dict(c=np.array([1.]),A_eq=csr_matrix((0,1)),b_eq=np.array([]),A_ub=csr_matrix([[-1.]]),b_ub=np.array([-1.]),lb=np.array([0.]),ub=np.array([2.]))
  r=SimpleNamespace(x=np.array([1.]),fun=1.,eqlin=SimpleNamespace(marginals=np.array([])),ineqlin=SimpleNamespace(marginals=np.array([-1.])),lower=SimpleNamespace(marginals=np.array([0.])),upper=SimpleNamespace(marginals=np.array([0.])))
  self.assertAlmostEqual(dual_lower_bound(p,r)['lower_bound'],1.-1e-7)
  r.ineqlin.marginals=np.array([-2.])
  self.assertLessEqual(dual_lower_bound(p,r)['lower_bound'],1.)
  self.assertLess(dual_lower_bound(p,r)['dual_box_correction'],0.)

 def test_actual_feasible_paths_embed_in_relaxation(self):
  p=Patient();sc=StressScenario('drain',drainage=.4,event_start=.3,event_end=.7)
  for options in ({},dict(actuator_tau=8.,drainage_tau=20.,venous_nonlinearity=.08)):
   w=witness(p,sc,options,duration=120.);self.assertTrue(w['feasible'])
   q=relaxation(p,sc,options,duration=120.);n=q['n'];x=2.4*p.bsa;volume=.85;flows=[];volumes=[]
   for k,r in enumerate(w['rows']):
    x=r['command']+(x-r['command'])*np.exp(-1./options.get('actuator_tau',2.));flows.append(x)
    volume+=(q['drainage_upper'][k]-r['flow'])/60.;volumes.append(volume)
   v=np.r_[[r['command'] for r in w['rows']],flows,[r['pressure'] for r in w['rows']],volumes,[max(0.,280.-r['do2']) for r in w['rows']]]
   self.assertLess(np.max(np.abs(q['A_eq']@v-q['b_eq'])),1e-8)
   self.assertLessEqual(np.max(q['A_ub']@v-q['b_ub']),1e-8)
   self.assertTrue(np.all(v>=q['lb']-1e-8) and np.all(v<=q['ub']+1e-8))
   self.assertAlmostEqual(float(q['c']@v),w['metrics']['deficit_auc'])

 def test_bound_below_full_plant_witness(self):
  p=Patient(hb=6.);sc=StressScenario('hard',drainage=.1,event_start=.25,event_end=1.)
  b=physical_bound(p,sc,{},duration=120.);w=witness(p,sc,{},duration=120.)
  self.assertTrue(b['success']);self.assertGreater(b['lower_bound'],0.)
  self.assertTrue(w['feasible']);self.assertLessEqual(b['lower_bound'],w['metrics']['deficit_auc']+1e-6)

 def test_high_initial_pressure_has_explicit_minimum_envelope(self):
  p=Patient(resistance=22.,bsa=2.3);e=pressure_envelope(p,1.,60,8.)
  self.assertGreater(e[0],95.);self.assertAlmostEqual(e[-1],95.)
  w=witness(p,StressScenario('clean'),dict(actuator_tau=8.),duration=60.)
  self.assertTrue(w['feasible']);self.assertGreater(w['metrics']['high_pressure_s'],0.)
  self.assertEqual(w['metrics']['pressure_envelope_excess_s'],0.)

 def test_local_certificate_does_not_mutate_live_plant(self):
  p=Patient();plant=StressPlant(p);before=copy.copy(plant).__dict__.copy();sc=StressScenario('clean')
  inputs=[sc.inputs(t,120.) for t in range(120)];limits=pressure_envelope(p,1.,120,2.)
  self.assertTrue(emergency_feasible(plant,plant.flow,plant.flow,0,inputs,limits))
  self.assertEqual(plant.__dict__,before)
  plant.reservoir=.2
  self.assertFalse(emergency_feasible(plant,plant.flow,plant.flow,0,inputs,limits))

 def test_continuous_tail_would_falsely_accept_discrete_loss(self):
  p=Patient();plant=StressPlant(p,actuator_tau=8.);plant.flow=1.;plant.pressure=14.
  decay=np.exp(-1./8.)
  first=(1.+decay)/120.;continuous_tail=decay*8./60.
  plant.reservoir=.25+first+continuous_tail+2e-5
  inputs=[dict(drainage=0.) for _ in range(600)]
  limits=np.full(600,95.)
  self.assertFalse(emergency_feasible(plant,0.,0.,0,inputs,limits,horizon=1.,floor=.25))

 def test_disabled_cap_is_a_separate_feasible_heuristic(self):
  p=Patient();sc=StressScenario('clean')
  for cap in (True,False):
   w=witness(p,sc,{},duration=60.,oxygen_cap=cap)
   self.assertTrue(w['feasible']);self.assertGreaterEqual(w['metrics']['minimum_reservoir'],.25)

 def test_instrumented_replay_preserves_existing_numerics(self):
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'examples'))
  from integrity_study import run,PHYS,PLANTS,patient
  from perfusion_lab.decision_audit import audit_run
  root=Path(__file__).resolve().parents[1]
  method=json.loads((root/'results/integrity-study/summary.json').read_text())['methods']['hybrid']
  f=lambda:run('evaluation','clean','nominal','positive_start','good',34000,method)
  a=f();b=audit_run(f,patient(34000,'evaluation'),StressScenario('clean'),PLANTS['nominal'],record_decisions=True)
  self.assertEqual(a['metrics'],b['metrics'])
  self.assertEqual([r['command'] for r in a['rows']],[r['command'] for r in b['rows']])
  self.assertEqual(b['audit_counters']['decision_steps'],600)
  self.assertLessEqual(b['audit_counters']['slowdown_local_safe_higher_oxygen_steps'],b['audit_counters']['slowdown_steps'])

if __name__=='__main__':unittest.main()
