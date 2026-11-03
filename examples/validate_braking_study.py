"""Independent audit of development history, frozen selection and evaluation."""
import csv,json
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from braking_study import candidates,run
from simc_benchmark import METRICS,digest

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/braking-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text())
dev=list(csv.DictReader((OUT/'development.csv').open()));rows=list(csv.DictReader((OUT/'evaluation.csv').open()))
assert len(dev)==1536 and len(rows)==4608
assert len({tuple(r[k] for k in ('case','plant','reference','seed','method')) for r in rows})==4608
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds'])
assert p['candidates']==candidates()
for name,value in p['source_hashes'].items():assert digest(ROOT/name)==value,name
assert s['selection_sha256']==digest(OUT/'selection.json') and s['protocol_sha256']==digest(OUT/'protocol.json')

def same(a,b):
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:same(a[k],b[k])
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):same(x,y)
 elif isinstance(a,(str,bool)) or a is None:assert a==b
 else:assert abs(float(a)-float(b))<1e-8,(a,b)

def mean(records):return {k:float(np.mean([float(r[k]) for r in records])) for k in METRICS}
def group(g):
 return [r for r in rows if r['reference']=='good' and r['plant']!='outside_lag_bound'] if g=='primary' else [r for r in rows if (r['plant']=='outside_lag_bound' if g=='outside_lag_bound' else r['reference']==g)]
for family in ('braking','simc'):
 vals=[v for v in candidates() if v['family']==family];assert len(vals)==16
 means={v['id']:mean([r for r in dev if r['method']==v['id']]) for v in vals}
 for name,m in means.items():same(m,selection[family]['means'][name])
 eligible=[v for v in vals if means[v['id']]['low_reservoir_s']<=1. and means[v['id']]['empty_request_s']<=1. and means[v['id']]['high_pressure_s']<=5.]
 def key(v):
  m=means[v['id']]
  return ((m['deficit_auc'],vals.index(v)) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v)))
 same(min(eligible or vals,key=key),s['methods'][family])
 assert selection[family]['matched_development_budget']==bool(eligible)
assert len(s['cell_means'])==96
for cell,methods in s['cell_means'].items():
 case,plant,ref=cell.split('__')
 for method,value in methods.items():
  rec=[r for r in rows if (r['case'],r['plant'],r['reference'],r['method'])==(case,plant,ref,method)]
  assert len(rec)==16;same(mean(rec),value)
for g,methods in s['group_means'].items():
 for method,value in methods.items():same(mean([r for r in group(g) if r['method']==method]),value)
for c in s['comparisons']:
 diffs=[]
 for seed in p['evaluation_seeds']:
  block=[r for r in group(c['group']) if int(r['seed'])==seed]
  diffs.append(mean([r for r in block if r['method']==c['method']])[c['metric']]-mean([r for r in block if r['method']=='simc'])[c['metric']])
 same({k:c[k] for k in ('mean','low','high','n')},paired_interval(diffs))
primary={c['metric']:c for c in s['comparisons'] if c['group']=='primary' and c['method']=='braking'}
protection=all(primary[k]['high']<=v for k,v in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())
assert s['primary']['protection_passed']==protection
assert s['primary']['oxygen_passed']==(primary['deficit_auc']['high']<0.)
assert s['primary']['demonstrated_joint_advantage']==(protection and primary['deficit_auc']['high']<0.)
assert not s['clinical_validation'] and not s['novelty_established']
for r in rows+dev:
 assert all(np.isfinite(float(r[k])) and float(r[k])>=0 for k in METRICS)
 assert all(float(r[k])<=600 for k in ('low_reservoir_s','empty_request_s','high_pressure_s'))
runs=json.loads((OUT/'replays.json').read_text());assert len(runs)==18
fields={'t':'time','do2':'do2','monitor':'measured_do2','reservoir':'reservoir','pressure':'pressure',
 'infeasible':'infeasible','fault':'fault','level_fault':'level_fault','level_sensor':'observed_reservoir'}
for name,trace in runs.items():
 cell,method=name.split('/');case,plant,ref=cell.split('__')
 rebuilt=run('evaluation',case,plant,ref,25000,s['methods'][method]);same(trace['metrics'],rebuilt['metrics'])
 sampled=rebuilt['rows'][::3]
 if sampled[-1] is not rebuilt['rows'][-1]:sampled.append(rebuilt['rows'][-1])
 for k,f in fields.items():same(trace[k],[r[f] for r in sampled])
 field='control_level_lower' if method=='braking' else 'level_reference_lower'
 same(trace['level_lower'],[r[field] for r in sampled])
 if method=='braking':
  for r in rebuilt['rows']:
   if r['braking_feasible']:assert r['braking_volume']<=r['braking_budget']+1e-8
# Retain development-only attempts and verify their actual archived source.
for number in (1,2):
 folder=ROOT/f'results/braking-pilot-{number}';old=json.loads((folder/'protocol.json').read_text())
 assert len(list(csv.DictReader((folder/'development.csv').open())))==1536
 assert not (folder/'evaluation.csv').exists()
 for name,value in old['source_hashes'].items():
  suffix='study.py' if name.startswith('examples/') else Path(name).name
  assert digest(ROOT/f'data/braking-history/pilot{number}_{suffix}')==value
print('PASS: two retained development pilots, 1536 final-development and 4608 evaluation runs, 96 cells, frozen settings, paired intervals and 18 independently rerun replays.')
