"""Independent audit of causal model-bank selection, intervals and paired results."""
import csv,json
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from model_bank_study import configurations,candidates,run,group,METRICS
from simc_benchmark import digest
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/model-bank-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text());sel=json.loads((OUT/'selection.json').read_text())
dev=list(csv.DictReader((OUT/'development.csv').open()));rows=list(csv.DictReader((OUT/'evaluation.csv').open()))
assert len(dev)==4096 and len(rows)==15360 and len(s['cell_means'])==192
for records in (dev,rows):assert len({tuple(r[k] for k in ('phys','plant','fault','calibration','seed','method')) for r in records})==len(records)
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds']) and p['candidates']==candidates()
for n,h in p['source_hashes'].items():assert digest(ROOT/n)==h,n
assert digest(OUT/'protocol.json')==s['protocol_sha256'] and digest(OUT/'selection.json')==s['selection_sha256']

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
values=[]
for i,cfg in enumerate(configurations()):
 h=mean([r for r in dev if r['method']==f'model_{i}_hybrid' and r['calibration']=='good']);b=mean([r for r in dev if r['method']==f'model_{i}_pi' and r['calibration']=='good'])
 values.append(dict(index=i,configuration=cfg,hybrid=h,pi=b,eligible=all(m[k]<=lim for m in (h,b) for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())))
same(values,sel['grid']);eligible=[v for v in values if v['eligible']]
def rank(v):
 m=v['hybrid'];return (m['deficit_auc'],v['index']) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],v['index'])
same(min(eligible or values,key=rank),sel['selected'])
vals=[v for v in candidates() if v['family']=='calpi'];means={v['id']:mean([r for r in dev if r['method']==v['id'] and r['calibration']=='good']) for v in vals};same(means,sel['calpi_means'])
good=[v for v in vals if all(means[v['id']][k]<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())]
def cr(v):
 m=means[v['id']];return (m['deficit_auc'],vals.index(v)) if good else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v))
same(min(good or vals,key=cr),sel['calpi']);assert sel['calpi_eligible']==bool(good)
same(s['methods']['hybrid']['guard'],s['methods']['matched_pi']['guard']);same(s['methods']['hybrid']['options'],s['methods']['matched_pi']['options'])
for cell,methods in s['cell_means'].items():
 phys,plant,fault,cal=cell.split('__')
 for method,value in methods.items():
  rec=[r for r in rows if (r['phys'],r['plant'],r['fault'],r['calibration'],r['method'])==(phys,plant,fault,cal,method)]
  assert len(rec)==16;same(mean(rec),value)
for r in rows:r['seed']=int(r['seed'])
# Missing calibration must preserve the matched PI physical fallback per run.
lookup={(r['phys'],r['plant'],r['fault'],r['calibration'],r['seed'],r['method']):r for r in rows}
for r in rows:
 if r['calibration']=='missing' and r['method']=='hybrid':
  for method in ('matched_pi','previous_hybrid'):
   other=lookup[(r['phys'],r['plant'],r['fault'],r['calibration'],r['seed'],method)]
   for metric in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s','flow_variation','mean_flow'):same(float(r[metric]),float(other[metric]))
for g,methods in s['group_means'].items():
 for method,value in methods.items():same(mean([r for r in rows if group(r,g) and r['method']==method]),value)
for c in s['comparisons']:
 differences=[]
 for seed in p['evaluation_seeds']:
  block=[r for r in rows if r['seed']==seed and group(r,c['group'])]
  differences.append(mean([r for r in block if r['method']=='hybrid'])[c['metric']]-mean([r for r in block if r['method']==c['baseline']])[c['metric']])
 same({k:c[k] for k in ('mean','low','high','n')},paired_interval(differences))
checks={}
for g in ('clean','bias','outage'):
 checks[g]={}
 for b in ('matched_pi','calibration_pi'):
  c={r['metric']:r for r in s['comparisons'] if r['group']==g and r['baseline']==b}
  checks[g][b]=dict(oxygen_passed=c['deficit_auc']['high']<0 and s['group_means'][g]['hybrid']['deficit_auc']<=.9*s['group_means'][g][b]['deficit_auc'],protection_passed=all(c[k]['high']<=v for k,v in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items()))
same(checks,s['primary']['checks']);assert s['primary']['joint_success']==all(all(v.values()) for b in checks.values() for v in b.values())
assert not s['version2_ready'] and not s['clinical_validation'] and not s['novelty_established']
for r in rows+dev:
 assert all(np.isfinite(float(r[k])) and float(r[k])>=0 for k in METRICS)
 assert all(float(r[k])<=600 for k in ('low_reservoir_s','empty_request_s','high_pressure_s','lower_undercoverage_s','bank_supported_s','bank_conflict_s'))
runs=json.loads((OUT/'replays.json').read_text());assert len(runs)==40
fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
for name,tr in runs.items():
 cell,m=name.split('/');phys,plant,fault,cal=cell.split('__');r=run('evaluation',phys,plant,fault,cal,36000,s['methods'][m]);same(tr['metrics'],r['metrics'])
 selected=r['rows'][::3]
 if selected[-1] is not r['rows'][-1]:selected.append(r['rows'][-1])
 for k,f in fields.items():same(tr[k],[v[f] for v in selected])
 truth=.85;err=[];miss=0
 for v in r['rows']:
  err.append(abs(v['level_reference_estimate']-truth));miss+=v['level_reference_lower']>truth+1e-9;truth=v['reservoir']
  if m in ('hybrid','matched_pi','single_model'):
   if not v['bank_supported']:assert v['override_delta']<=1e-12
   if m=='hybrid' and v['override_eligible'] and v['predictive_feasible']:assert v['braking_volume']<=v['braking_budget']+1e-8
 same(float(np.mean(err)),r['metrics']['volume_mae_L']);same(miss,r['metrics']['lower_undercoverage_s'])
import re
html=(ROOT/'web/index.html').read_text();section=html[html.index('data-study="model-bank"'):];tbody=section.split('<tbody>',1)[1].split('</tbody>',1)[0]
actual=[re.findall(r'<td>([^<]+)</td>',r) for r in re.findall(r'<tr>(.*?)</tr>',tbody)]
expected=[]
for g in ('clean','bias','outage'):
 for m in ('hybrid','matched_pi','calibration_pi','previous_hybrid'):
  v=s['group_means'][g][m]
  expected.append([f"{v[k]:.2f}" for k in ('deficit_auc','low_reservoir_s','empty_request_s')]+[f"{1000*v['volume_mae_L']:.2f}"])

assert actual==expected
print('PASS: 4096 development + 15360 evaluation runs, frozen causal model bank, matched-input PI, 192 cells, paired criteria, volume-error timing and all 40 rerun replays; v2 not claimed.')
