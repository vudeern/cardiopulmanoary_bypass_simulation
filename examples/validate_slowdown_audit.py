"""Check stored witnesses through the full plant, LP bounds and audit evidence."""
import csv,json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from perfusion_lab.audit import relaxation,dual_lower_bound
from perfusion_lab.stress import StressPlant
from perfusion_lab.model import delivery
from perfusion_lab.benchmark import paired_interval
from slowdown_audit import OUT,ROOT,SOURCE,CELLS,patient,scenario,PLANTS,check_sources
from simc_benchmark import digest,METRICS
p=check_sources();s=json.loads((OUT/'summary.json').read_text());bench=json.loads((OUT/'benchmarks.json').read_text())
rows=list(csv.DictReader((OUT/'runs.csv').open()));counts=list(csv.DictReader((OUT/'decision-counts.csv').open()))
assert len(rows)==640 and len(counts)==128 and len(bench)==96
assert len({(r['cell'],r['seed'],r['method']) for r in rows})==640
assert not s['controller_changed'] and not s['mathematical_optimum_found'] and not s['clinical_validation']
assert p['status']=='post_result_diagnostic_no_retuning'
source_protocol=json.loads((SOURCE/'protocol.json').read_text())
for name,value in source_protocol['source_hashes'].items():assert digest(ROOT/name)==value,'Original controller changed: '+name
stored=json.loads((OUT/'witness-commands.json').read_text());assert stored['benchmark_sha256']==digest(OUT/'benchmarks.json')
assert stored['generator_sha256']==digest(ROOT/'examples/export_slowdown_witnesses.py')
assert stored['commands'].keys()==bench.keys()

def same(a,b,tol=1e-8):
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:same(a[k],b[k],tol)
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):same(x,y,tol)
 elif isinstance(a,(str,bool)) or a is None:assert a==b
 else:assert abs(float(a)-float(b))<=tol,(a,b)

for key,b in bench.items():
 person=patient(b['seed'],'evaluation');sc=scenario(b['phys']);plant=StressPlant(person,**PLANTS[b['plant']]);u_prev=plant.flow
 q=relaxation(person,sc,PLANTS[b['plant']]);physical=[];ends=[];relaxed_volume=.85;relaxed=[];initial=plant.flow
 for k,u in enumerate(stored['commands'][key]):
  assert 0<=u<=7 and abs(u-u_prev)<=.15+1e-9;u_prev=u
  inp=sc.inputs(k,600.);step=plant.step(u,inp['drainage'],1.)
  do2=delivery(step['flow'],person.hb-inp['hb_loss'],inp['sao2'],person.bsa)
  physical.append(dict(command=u,do2=do2,**step));ends.append(plant.flow)
  relaxed_volume+=(q['drainage_upper'][k]-step['flow'])/60.;relaxed.append(relaxed_volume)
 assert len(physical)==600
 feasible=all(r['reservoir']>=.25-1e-9 and not r['empty_request'] and r['pressure']<=q['pressure_envelope'][k]+1e-8 for k,r in enumerate(physical))
 assert b['feasible']==feasible
 actual=dict(deficit_auc=sum(max(0.,280.-r['do2']) for r in physical)/60.,low_reservoir_s=sum(r['reservoir']<.25 for r in physical),empty_request_s=sum(r['empty_request'] for r in physical),high_pressure_s=sum(r['pressure']>95. for r in physical),pressure_envelope_excess_s=sum(r['pressure']>q['pressure_envelope'][k]+1e-8 for k,r in enumerate(physical)),minimum_reservoir=min(r['reservoir'] for r in physical),mean_flow=float(np.mean([r['flow'] for r in physical])),flow_variation=sum(abs(b['command']-a['command']) for a,b in zip(physical,physical[1:])),below_target_s=sum(r['do2']<280. for r in physical))
 same(actual,b['metrics'])
 if feasible:
  v=np.r_[stored['commands'][key],ends,[r['pressure'] for r in physical],relaxed,[max(0.,280.-r['do2']) for r in physical]]
  assert np.max(np.abs(q['A_eq']@v-q['b_eq']))<1e-6
  assert np.max(q['A_ub']@v-q['b_ub'])<1e-6
  assert np.all(v>=q['lb']-1e-6) and np.all(v<=q['ub']+1e-6)
 result=linprog(q['c'],A_eq=q['A_eq'],b_eq=q['b_eq'],A_ub=q['A_ub'],b_ub=q['b_ub'],bounds=list(zip(q['lb'],q['ub'])),method='highs')
 assert result.success==b['lp']['success']
 if result.success:
  check=dual_lower_bound(q,result);assert check['primal_residual_max']<1e-6
  same(check['objective'],b['lp']['objective'],1e-4)
  assert b['lp']['lower_bound']<=check['objective']+1e-5
  assert b['lp']['objective']-b['lp']['lower_bound']<1e-4
  if feasible:assert b['lp']['lower_bound']<=actual['deficit_auc']+1e-5

original=list(csv.DictReader((SOURCE/'evaluation.csv').open()))
lookup={(r['phys'],r['plant'],r['fault'],r['calibration'],r['seed'],r['method']):r for r in original}
for r in rows:
 assert r['cell'] in CELLS and int(r['seed']) in p['patient_seeds']
 if r['method'] in ('hybrid','matched_pi','calibration_pi'):
  phys,plant,fault,cal=r['cell'].split('__');o=lookup[(phys,plant,fault,cal,r['seed'],r['method'])]
  for k in METRICS:same(r[k],o[k])
 if r['audit_feasible']=='True':
  assert float(r['low_reservoir_s'])==0 and float(r['empty_request_s'])==0 and float(r['pressure_envelope_excess_s'])==0
  phys,plant,_,_=r['cell'].split('__');b=bench['__'.join((r['seed'],phys,plant))]
  if b['lp']['success']:assert b['lp']['lower_bound']<=float(r['deficit_auc'])+1e-5
for method,value in s['means'].items():
 block=[r for r in rows if r['method']==method]
 for k in METRICS:same(float(np.mean([float(r[k]) for r in block])),value[k])
 assert sum(r['audit_feasible']=='True' for r in block)==value['feasible_runs']
for c in s['comparisons']:
 diffs=[]
 for seed in p['patient_seeds']:
  a=[float(r[c['metric']]) for r in rows if int(r['seed'])==seed and r['method']==c['method']]
  b=[float(r[c['metric']]) for r in rows if int(r['seed'])==seed and r['method']=='hybrid']
  diffs.append(float(np.mean(a)-np.mean(b)))
 same({k:c[k] for k in ('mean','low','high','n')},paired_interval(diffs))
for k,value in s['decision_counts'].items():
 vals=[float(r[k]) for r in counts]
 same(float(np.mean(vals)) if k.startswith('mean_') else sum(vals),value)
assert s['decision_counts']['slowdown_local_safe_higher_oxygen_steps']<=s['decision_counts']['slowdown_steps']
assert s['decision_counts']['local_safe_higher_oxygen_steps']<=s['decision_counts']['below_target_steps']
# Rebuild every displayed original/ablation replay and its local counterfactuals.
from integrity_study import run as old_run
from perfusion_lab.decision_audit import audit_run
from slowdown_audit import trace
methods=json.loads((SOURCE/'summary.json').read_text())['methods'];runs=json.loads((OUT/'replays.json').read_text());events=json.loads((OUT/'local-events.json').read_text())
assert len(runs)==40
for cell in CELLS:
 phys,plant,fault,cal=cell.split('__')
 for name in ('hybrid','matched_pi','calibration_pi','margin_removed','true_volume'):
  method=methods[name if name in methods else 'hybrid'];f=lambda:old_run('evaluation',phys,plant,fault,cal,34000,method)
  result=audit_run(f,patient(34000,'evaluation'),scenario(phys),PLANTS[plant],mode=name if name in ('margin_removed','true_volume') else 'observed',record_decisions=name=='hybrid')
  same(trace(result),runs[cell+'/'+name])
  if name=='hybrid':
   same(result['audit_events'],events[cell]);record=next(r for r in counts if r['cell']==cell and r['seed']=='34000')
   for k,v in result['audit_counters'].items():same(float(record[k]),v)
old=ROOT/'data/slowdown-audit/tail-correction'
assert json.loads((old/'status.json').read_text())['not_valid_evidence']
assert digest(old/'audit.py')==json.loads((old/'protocol.json').read_text())['source_hashes']['src/perfusion_lab/audit.py']
import re
html=(ROOT/'web/index.html').read_text();section=html[html.index('data-study="slowdown"'):];tbody=section.split('<tbody>',1)[1].split('</tbody>',1)[0]
actual=[re.findall(r'<td>([^<]+)</td>',r) for r in re.findall(r'<tr>(.*?)</tr>',tbody)]
expected=[[f"{s['means'][m][k]:.2f}" for k in ('deficit_auc','low_reservoir_s','empty_request_s')] for m in ('hybrid','matched_pi','calibration_pi','margin_removed','true_volume')]
for entry,m in zip(expected,('hybrid','matched_pi','calibration_pi','margin_removed','true_volume')):entry.append(str(s['means'][m]['feasible_runs'])+'/128')
expected.append([f"{s['bounds']['audit_weighted_witness_auc']:.2f}",'0.00','0.00','128/128'])
assert actual==expected
print('PASS: unchanged controller hashes, 640 diagnostics, 128 decision audits, all 96 full-plant witness schedules, LP primal/dual checks and bounds, original-run parity, paired intervals, 40 replays, local forks and published table.')
