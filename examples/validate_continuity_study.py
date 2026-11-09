"""Independent audit of frozen continuity study, criteria and causal replays."""
import csv,json,math
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from continuity_study import run,candidates
from simc_benchmark import digest,METRICS
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/continuity-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text())
dev=list(csv.DictReader((OUT/'development.csv').open()));rows=list(csv.DictReader((OUT/'evaluation.csv').open()))
assert len(dev)==3072 and len(rows)==6144
assert len({tuple(r[k] for k in ('case','plant','reference','seed','method')) for r in rows})==6144
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds'])
assert set(map(int,[r['seed'] for r in dev]))==set(p['development_seeds'])
assert set(map(int,[r['seed'] for r in rows]))==set(p['evaluation_seeds'])
assert p['candidates']==candidates()
for name,value in p['source_hashes'].items():
 path=ROOT/name
 if name=='src/perfusion_lab/simulation.py' and digest(path)!=value:path=ROOT/'data/continuity-history/frozen-v1.10/simulation.py'
 assert digest(path)==value,name
assert digest(OUT/'selection.json')==s['selection_sha256'] and digest(OUT/'protocol.json')==s['protocol_sha256']

def same(a,b):
 if isinstance(a,dict):
  assert a.keys()==b.keys(),(a.keys(),b.keys())
  for k in a:same(a[k],b[k])
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):same(x,y)
 elif isinstance(a,(str,bool)) or a is None:assert a==b
 else:assert abs(float(a)-float(b))<1e-8,(a,b)

def mean(rec):return {k:float(np.mean([float(r[k]) for r in rec])) for k in METRICS}
def group(g):
 if g=='primary':return [r for r in rows if r['reference'] in ('good','delayed_loss') and r['plant']!='outside_lag_bound']
 if g in ('good','delayed_loss'):return [r for r in rows if r['reference']==g and r['plant']!='outside_lag_bound']
 return [r for r in rows if (r['plant']=='outside_lag_bound' if g=='outside_lag_bound' else r['reference']==g)]
for family in ('continuity','simc'):
 vals=[v for v in candidates() if v['family']==family];assert len(vals)==16
 means={v['id']:mean([r for r in dev if r['method']==v['id']]) for v in vals}
 same(means,selection[family]['means'])
 eligible=[v for v in vals if all(means[v['id']][k]<=limit for k,limit in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())]
 def rank(v):
  m=means[v['id']]
  return (m['deficit_auc'],vals.index(v)) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v))
 same(min(eligible or vals,key=rank),s['methods'][family]);assert selection[family]['matched_development_budget']==bool(eligible)
assert len(s['cell_means'])==128
for cell,methods in s['cell_means'].items():
 case,plant,reference=cell.split('__')
 for method,value in methods.items():
  rec=[r for r in rows if (r['case'],r['plant'],r['reference'],r['method'])==(case,plant,reference,method)]
  assert len(rec)==16;same(mean(rec),value)
for g,methods in s['group_means'].items():
 for method,value in methods.items():same(mean([r for r in group(g) if r['method']==method]),value)
for c in s['comparisons']:
 differences=[]
 for seed in p['evaluation_seeds']:
  rec=[r for r in group(c['group']) if int(r['seed'])==seed]
  differences.append(mean([r for r in rec if r['method']==c['method']])[c['metric']]-mean([r for r in rec if r['method']=='simc'])[c['metric']])
 same({k:c[k] for k in ('mean','low','high','n')},paired_interval(differences))
checks={}
for g in ('good','delayed_loss'):
 c={c['metric']:c for c in s['comparisons'] if c['group']==g and c['method']=='continuity'}
 checks[g]=dict(protection_passed=all(c[k]['high']<=limit for k,limit in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items()),oxygen_passed=c['deficit_auc']['high']<0.)
same(checks,s['primary']['groups']);assert s['primary']['demonstrated_joint_advantage']==all(all(v.values()) for v in checks.values())
assert not s['clinical_validation'] and not s['novelty_established']
for r in dev+rows:
 assert all(np.isfinite(float(r[k])) and float(r[k])>=0 for k in METRICS)
 assert all(float(r[k])<=600 for k in ('low_reservoir_s','empty_request_s','high_pressure_s'))
runs=json.loads((OUT/'replays.json').read_text());assert len(runs)==18
fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir')
for name,trace in runs.items():
 cell,method=name.split('/');case,plant,reference=cell.split('__')
 rebuilt=run('evaluation',case,plant,reference,28000,s['methods'][method]);same(trace['metrics'],rebuilt['metrics'])
 sampled=rebuilt['rows'][::3]
 if sampled[-1] is not rebuilt['rows'][-1]:sampled.append(rebuilt['rows'][-1])
 for k,f in fields.items():same(trace[k],[r[f] for r in sampled])
 field='control_level_lower' if method in ('continuity','previous_braking') else 'level_reference_lower'
 same(trace['level_lower'],[r[field] for r in sampled])
 if method=='continuity':
  previous=2.4*rebuilt['patient']['bsa']
  for r in rebuilt['rows']:
   assert abs(r['command']-previous)<=.15+1e-10;previous=r['command']
   if r['braking_feasible']:assert r['braking_volume']<=r['braking_budget']+1e-8
   if r['balance_reference_age'] is not None:assert r['balance_reference_age']>=0
# Numerical refinement remains descriptive; do not turn it into a retuning gate.
for cell in ('drainage__slow__good','combined__lagged__delayed_loss'):
 case,plant,reference=cell.split('__')
 for dt in (1.,.5):
  rec=run('evaluation',case,plant,reference,28000,s['methods']['continuity'],dt=dt)
  assert all(math.isfinite(rec['metrics'][m]) for m in METRICS)
pilot=ROOT/'results/continuity-pilot-1'
old=json.loads((pilot/'protocol.json').read_text())
assert len(list(csv.DictReader((pilot/'development.csv').open())))==3072
assert not (pilot/'evaluation.csv').exists()
for name,value in old['source_hashes'].items():assert digest(ROOT/'data/continuity-history/pilot1'/Path(name).name)==value
# Ensure the portfolio table reports the actual frozen group means.
import re
html=(ROOT/'web/index.html').read_text()
section=html[html.index('data-study="continuity"'):]
tbody=section.split('<tbody>',1)[1].split('</tbody>',1)[0]
actual=[re.findall(r'<td>([^<]+)</td>',row) for row in re.findall(r'<tr>(.*?)</tr>',tbody)]
expected=[[f"{s['group_means'][g][m][k]:.2f}" for k in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s')]
 for g in ('good','delayed_loss') for m in ('continuity','simc','previous_braking')]
assert actual==expected,'Published table differs from frozen study'
print('PASS: retained development-only pilot, 3072 development + 6144 evaluation runs, frozen selection/source, 128 cells, both co-primary criteria, paired intervals, 18 independently rerun traces and numerical-refinement smoke checks.')
