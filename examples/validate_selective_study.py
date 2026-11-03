"""Independent audit of selective PI selection, components and comparisons."""
import csv,json
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from selective_study import candidates,run,in_group
from simc_benchmark import digest,METRICS
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/selective-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text());selection=json.loads((OUT/'selection.json').read_text())
dev=list(csv.DictReader((OUT/'development.csv').open()));rows=list(csv.DictReader((OUT/'evaluation.csv').open()));ablation=list(csv.DictReader((OUT/'development-ablations.csv').open()))
assert len(dev)==4096 and len(rows)==10240 and len(ablation)==256
for records in (dev,rows,ablation):assert len({tuple(r[k] for k in ('case','plant','reference','seed','method')) for r in records})==len(records)
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds'])
assert p['candidates']==candidates()
for n,h in p['source_hashes'].items():assert digest(ROOT/n)==h,n
assert s['protocol_sha256']==digest(OUT/'protocol.json') and s['selection_sha256']==digest(OUT/'selection.json')

def same(a,b):
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:same(a[k],b[k])
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):same(x,y)
 elif isinstance(a,(str,bool)) or a is None:assert a==b
 else:assert abs(float(a)-float(b))<1e-8,(a,b)

def mean(rec):return {k:float(np.mean([float(r[k]) for r in rec])) for k in METRICS}
for family in ('selective','simc'):
 vals=[v for v in candidates() if v['family']==family];assert len(vals)==16
 means={v['id']:mean([r for r in dev if r['method']==v['id']]) for v in vals}
 refs={v['id']:{ref:mean([r for r in dev if r['method']==v['id'] and r['reference']==ref]) for ref in ('good','delayed_loss')} for v in vals}
 same(means,selection[family]['means']);same(refs,selection[family]['by_reference'])
 eligible=[v for v in vals if all(refs[v['id']][ref][k]<=lim for ref in ('good','delayed_loss') for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())]
 def rank(v):
  m=means[v['id']]
  return (m['deficit_auc'],vals.index(v)) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v))
 same(min(eligible or vals,key=rank),selection[family]['method']);assert selection[family]['eligible']==bool(eligible)
 same(selection[family]['method'],s['methods']['hybrid' if family=='selective' else 'simc'])
for mode in ('brake_only','boost_only'):
 same(s['methods'][mode]['options'],{**s['methods']['hybrid']['options'],'mode':mode})
 same(mean([r for r in ablation if r['method']==mode]),json.loads((OUT/'development-ablation-summary.json').read_text())[mode])
assert len(s['cell_means'])==128
for cell,methods in s['cell_means'].items():
 case,plant,ref=cell.split('__')
 for method,value in methods.items():
  rec=[r for r in rows if (r['case'],r['plant'],r['reference'],r['method'])==(case,plant,ref,method)]
  assert len(rec)==16;same(mean(rec),value)
# CSV seed strings must be converted before comparison with protocol integers.
for r in rows:r['seed']=int(r['seed'])
for g,methods in s['group_means'].items():
 for method,value in methods.items():same(mean([r for r in rows if in_group(r,g) and r['method']==method]),value)
for c in s['comparisons']:
 diffs=[]
 for seed in p['evaluation_seeds']:
  block=[r for r in rows if r['seed']==seed and in_group(r,c['group'])]
  diffs.append(mean([r for r in block if r['method']==c['method']])[c['metric']]-mean([r for r in block if r['method']==c['baseline']])[c['metric']])
 same({k:c[k] for k in ('mean','low','high','n')},paired_interval(diffs))
tests={}
for g in ('good','delayed_loss'):
 tests[g]={}
 for base in ('simc','fast_pi'):
  c={c['metric']:c for c in s['comparisons'] if c['group']==g and c['baseline']==base and c['method']=='hybrid'}
  tests[g][base]=dict(protection_passed=all(c[k]['high']<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items()),oxygen_passed=c['deficit_auc']['high']<0.)
same(tests,s['primary']['tests']);assert s['primary']['demonstrated_joint_advantage']==all(all(v.values()) for b in tests.values() for v in b.values())
assert not s['clinical_validation'] and not s['novelty_established']
for r in dev+rows+ablation:
 assert all(np.isfinite(float(r[k])) and float(r[k])>=0 for k in METRICS)
 assert all(float(r[k])<=600 for k in ('low_reservoir_s','empty_request_s','high_pressure_s'))
runs=json.loads((OUT/'replays.json').read_text());assert len(runs)==30
fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir')
for name,trace in runs.items():
 cell,method=name.split('/');case,plant,ref=cell.split('__')
 result=run('evaluation',case,plant,ref,31000,s['methods'][method]);same(trace['metrics'],result['metrics'])
 selected=result['rows'][::3]
 if selected[-1] is not result['rows'][-1]:selected.append(result['rows'][-1])
 for k,f in fields.items():same(trace[k],[r[f] for r in selected])
 field='control_level_lower' if s['methods'][method]['kind']=='selective' else 'level_reference_lower'
 same(trace['level_lower'],[r[field] for r in selected])
 if s['methods'][method]['kind']=='selective':
  last=2.4*result['patient']['bsa'];weight=0.
  for r in result['rows']:
   assert abs(r['command']-last)<=.15+1e-10;last=r['command']
   assert abs(r['override_weight']-weight)<=.1+1e-10;weight=r['override_weight']
   if r['reference_count']<2:assert weight==0.
   if r['override_eligible']:assert r['estimate_disagreement']<=s['methods'][method]['options']['agreement']+1e-9
   if r['override_weight']==0.:assert r['command']==r['pi_command']
   if r['observation_time']>=0 and r['pressure']<0:raise AssertionError('Negative pressure')
for number in (1,2):
 folder=ROOT/f'results/selective-pilot-{number}';old=json.loads((folder/'protocol.json').read_text())
 assert len(list(csv.DictReader((folder/'development.csv').open())))==4096
 assert not (folder/'evaluation.csv').exists()
 for name,value in old['source_hashes'].items():assert digest(ROOT/f'data/selective-history/pilot{number}'/Path(name).name)==value
# Independent web table consistency is checked against the frozen source means.
import re
html=(ROOT/'web/index.html').read_text();section=html[html.index('data-study="selective"'):];tbody=section.split('<tbody>',1)[1].split('</tbody>',1)[0]
actual=[re.findall(r'<td>([^<]+)</td>',r) for r in re.findall(r'<tr>(.*?)</tr>',tbody)]
expected=[[f"{s['group_means'][g][m][k]:.2f}" for k in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s')] for g in ('good','delayed_loss') for m in ('hybrid','simc','fast_pi')]
assert actual==expected
print('PASS: two retained development pilots, 4096 development + 256 component checks + 10240 evaluation runs, source/selection freeze, both PI baselines, paired criteria, 128 cells, 30 rerun replays and published table.')
