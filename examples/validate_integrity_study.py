"""Independent audit of reference decisions, paired comparisons and source freeze."""
import csv,json
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from integrity_study import run,candidates,guards,in_group,METRICS
from simc_benchmark import digest
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/integrity-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text());sel=json.loads((OUT/'selection.json').read_text())
dev=list(csv.DictReader((OUT/'development.csv').open()));rows=list(csv.DictReader((OUT/'evaluation.csv').open()))
assert len(dev)==3072 and len(rows)==10752
for records in (dev,rows):assert len({tuple(r[k] for k in ('phys','plant','fault','calibration','seed','method')) for r in records})==len(records)
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds']);assert p['candidates']==candidates()
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
common=[]
for i,g in enumerate(guards()):
 h=mean([r for r in dev if r['method']==f'guard_{i}_hybrid' and r['calibration']=='good'])
 b=mean([r for r in dev if r['method']==f'guard_{i}_pi' and r['calibration']=='good'])
 common.append(dict(index=i,guard=g,hybrid=h,pi=b,eligible=all(v[k]<=lim for v in (h,b) for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())))
same(common,sel['common_grid']);eligible=[v for v in common if v['eligible']]
def rank(v):
 h=v['hybrid'];return (h['deficit_auc'],v['index']) if eligible else (h['low_reservoir_s'],h['empty_request_s'],h['high_pressure_s'],h['deficit_auc'],v['index'])
same(min(eligible or common,key=rank),sel['common'])
vals=[v for v in candidates() if v['family']=='calpi'];means={v['id']:mean([r for r in dev if r['method']==v['id'] and r['calibration']=='good']) for v in vals};same(means,sel['calpi_means'])
good=[v for v in vals if all(means[v['id']][k]<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())]
def key(v):
 m=means[v['id']];return (m['deficit_auc'],vals.index(v)) if good else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v))
same(min(good or vals,key=key),sel['calpi']);assert sel['calpi_eligible']==bool(good)
same(s['methods']['hybrid']['guard'],s['methods']['matched_pi']['guard']);same(s['methods']['hybrid']['guard'],sel['common']['guard'])
same(s['methods']['unscreened']['guard'],{**sel['common']['guard'],'screen':False})
same(s['methods']['calibration_pi'],sel['calpi'])
assert len(s['cell_means'])==168
for cell,methods in s['cell_means'].items():
 phys,plant,fault,cal=cell.split('__')
 for method,value in methods.items():
  rec=[r for r in rows if (r['phys'],r['plant'],r['fault'],r['calibration'],r['method'])==(phys,plant,fault,cal,method)]
  assert len(rec)==16;same(mean(rec),value)
for r in rows:r['seed']=int(r['seed'])
for g,methods in s['group_means'].items():
 for method,value in methods.items():same(mean([r for r in rows if in_group(r,g) and r['method']==method]),value)
for c in s['comparisons']:
 diffs=[]
 for seed in p['evaluation_seeds']:
  block=[r for r in rows if r['seed']==seed and in_group(r,c['group'])]
  diffs.append(mean([r for r in block if r['method']=='hybrid'])[c['metric']]-mean([r for r in block if r['method']==c['baseline']])[c['metric']])
 same({k:c[k] for k in ('mean','low','high','n')},paired_interval(diffs))
checks={}
for g in ('good_cal_faults','good_cal_clean'):
 checks[g]={}
 for baseline in ('matched_pi','calibration_pi'):
  c={r['metric']:r for r in s['comparisons'] if r['group']==g and r['baseline']==baseline}
  checks[g][baseline]=all(c[k]['high']<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.,deficit_auc=5.).items())
same(checks,s['primary']['noninferiority'])
benefit=next(c['high'] for c in s['comparisons'] if c['group']=='good_cal_faults' and c['baseline']=='unscreened' and c['metric']=='low_reservoir_s')<0.
assert benefit==s['primary']['screening_reservoir_benefit']
assert s['primary']['joint_success']==(benefit and all(all(b.values()) for b in checks.values()))
assert not s['clinical_validation'] and not s['novelty_established']
for r in dev+rows:
 assert all(np.isfinite(float(r[k])) and float(r[k])>=0 for k in METRICS)
 assert float(r['reference_bad_rejected'])<=float(r['reference_bad_total'])
 assert float(r['reference_good_rejected'])<=float(r['reference_good_total'])
 assert all(float(r[k])<=600 for k in ('low_reservoir_s','empty_request_s','high_pressure_s','quarantine_s'))
runs=json.loads((OUT/'replays.json').read_text());assert len(runs)==24
decisions=json.loads((OUT/'decisions.json').read_text());assert decisions.keys()==runs.keys()
fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
for name,trace in runs.items():
 cell,method=name.split('/');phys,plant,fault,cal=cell.split('__');r=run('evaluation',phys,plant,fault,cal,34000,s['methods'][method]);same(trace['metrics'],r['metrics'])
 selected=r['rows'][::3]
 if selected[-1] is not r['rows'][-1]:selected.append(r['rows'][-1])
 for k,f in fields.items():same(trace[k],[a[f] for a in selected])
 expected=[{k:a.get(k) for k in ('observation_time','reference_events','reference_quarantined','reference_uncertainty','calibration_age','calibration_count','recovery_supported','override_delta')} for a in r['rows'] if a['reference_events'] or a['observation_time']%60==0]
 same(decisions[name],expected)
 events=[e for a in r['rows'] for e in a['reference_events']]
 bad=[e for e in events if abs(e['injected_bias_for_analysis'])>.04];good_events=[e for e in events if abs(e['injected_bias_for_analysis'])<=.04]
 assert len(bad)==r['metrics']['reference_bad_total'] and sum(not e['accepted'] for e in bad)==r['metrics']['reference_bad_rejected']
 assert len(good_events)==r['metrics']['reference_good_total'] and sum(not e['accepted'] for e in good_events)==r['metrics']['reference_good_rejected']
 for a in r['rows']:
  if a['calibration_acquired'] is not None:assert a['calibration_acquired']<=a['calibration_delivered']<=a['observation_time']
  for e in a['reference_events']:assert e['acquired']<=e['delivered']<=e['decision_time']<=a['observation_time']
  if method=='hybrid' and not a['recovery_supported']:assert a['override_delta']<=1e-12
pilot=ROOT/'results/integrity-pilot-1';old=json.loads((pilot/'protocol.json').read_text())
assert len(list(csv.DictReader((pilot/'development.csv').open())))==3072 and not (pilot/'evaluation.csv').exists()
for n,h in old['source_hashes'].items():assert digest(ROOT/'data/integrity-history/pilot1'/Path(n).name)==h
import re
html=(ROOT/'web/index.html').read_text();section=html[html.index('data-study="integrity"'):];tbody=section.split('<tbody>',1)[1].split('</tbody>',1)[0]
actual=[re.findall(r'<td>([^<]+)</td>',r) for r in re.findall(r'<tr>(.*?)</tr>',tbody)]
expected=[[f"{s['group_means'][g][m][k]:.2f}" for k in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s')] for g in ('good_cal_faults','good_cal_clean') for m in ('hybrid','matched_pi','calibration_pi','unscreened')]
assert actual==expected
print('PASS: retained pilot, 3072 development + 10752 evaluation runs, shared-input ablation, source/selection freeze, 168 cells, paired criteria, 24 rerun traces, reference classifications and published table.')
