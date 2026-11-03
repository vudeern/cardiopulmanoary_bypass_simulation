"""Independent checks of the full benchmark, its pairing and stored replays."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from simc_benchmark import run,METRICS,candidates,digest
from analyze_simc import analysis

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/simc-benchmark'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text());rows=list(csv.DictReader((OUT/'metrics.csv').open()))
assert len(rows)==2048
for r in rows:
    assert all(np.isfinite(float(r[k])) and float(r[k])>=0 for k in METRICS)
    assert all(float(r[k])<=600 for k in ('low_reservoir_s','empty_request_s','high_pressure_s'))
assert len({tuple(r[k] for k in ('phase','case','plant','reference','seed','method')) for r in rows})==2048
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds'])
assert s['development_runs']==512 and s['evaluation_runs']==1536
assert s['protocol_sha256']==digest(OUT/'protocol.json')
assert s['selection_sha256']==digest(OUT/'selection.json')
assert p['candidates']==candidates()
for name,value in p['source_hashes'].items():assert digest(ROOT/name)==value,name

def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for key in a:same(a[key],b[key])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,bool) or isinstance(a,str) or a is None:assert a==b
    else:assert abs(float(a)-float(b))<1e-8,(a,b)

def mean(records):return {k:float(np.mean([float(r[k]) for r in records])) for k in METRICS}
dev=[r for r in rows if r['phase']=='development'];final=[r for r in rows if r['phase']=='evaluation']
for family in ('simc','forecast'):
    values=[v for v in p['candidates'] if v['family']==family];assert len(values)==8
    means={v['id']:mean([r for r in dev if r['method']==v['id']]) for v in values}
    for v in values:
        records=[r for r in dev if r['method']==v['id']]
        assert len(records)==32
        assert {int(r['seed']) for r in records}==set(p['development_seeds'])
        same(means[v['id']],selection[family]['means'][v['id']])
    eligible=[v for v in values if means[v['id']]['low_reservoir_s']<=1.
        and means[v['id']]['empty_request_s']<=1. and means[v['id']]['high_pressure_s']<=5.]
    def rank(v):
        m=means[v['id']]
        return ((m['deficit_auc'],values.index(v)) if eligible else
            (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],values.index(v)))
    same(min(eligible or values,key=rank),s['methods'][family])
    assert selection[family]['matched_development_budget']==bool(eligible)
assert len(s['cell_means'])==48
for cell,methods in s['cell_means'].items():
    case,plant,ref=cell.split('__')
    for method,value in methods.items():
        rec=[r for r in final if (r['case'],r['plant'],r['reference'],r['method'])==(case,plant,ref,method)]
        assert len(rec)==16 and {int(r['seed']) for r in rec}==set(p['evaluation_seeds'])
        same(mean(rec),value)
for ref,methods in s['group_means'].items():
    for method,value in methods.items():same(mean([r for r in final if r['reference']==ref and r['method']==method]),value)
for contrast in s['comparisons']:
    differences=[]
    for seed in p['evaluation_seeds']:
        filtered=[r for r in final if r['reference']==contrast['reference'] and int(r['seed'])==seed]
        differences.append(mean([r for r in filtered if r['method']=='forecast'])[contrast['metric']]-mean([r for r in filtered if r['method']=='simc'])[contrast['metric']])
    same({k:contrast[k] for k in ('mean','low','high','n')},paired_interval(differences))
primary={c['metric']:c for c in s['comparisons'] if c['reference']=='good'}
protection=all(primary[k]['high']<=limit for k,limit in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())
assert s['primary']['protection_passed']==protection
assert s['primary']['oxygen_passed']==(primary['deficit_auc']['high']<0.)
assert s['primary']['demonstrated_joint_advantage']==(protection and primary['deficit_auc']['high']<0.)
assert s['general_PI_reference_verified'] and not s['clinical_CPB_controller_reproduced'] and not s['clinical_validation']
runs=json.loads((OUT/'replays.json').read_text());assert len(runs)==12
fields={'t':'time','do2':'do2','monitor':'measured_do2','reservoir':'reservoir','pressure':'pressure',
        'infeasible':'infeasible','fault':'fault','level_fault':'level_fault','level_sensor':'observed_reservoir','level_lower':'level_reference_lower'}
for name,record in runs.items():
    cell,method=name.split('/');case,plant,ref=cell.split('__')
    rebuilt=run('evaluation',case,plant,ref,16000,s['methods'][method])
    selected=rebuilt['rows'][::3]
    if selected[-1] is not rebuilt['rows'][-1]:selected.append(rebuilt['rows'][-1])
    same(record['metrics'],rebuilt['metrics'])
    for key,field in fields.items():same(record[key],[r[field] for r in selected])
refinement=json.loads((OUT/'refinement.json').read_text());assert len(refinement['rows'])==24
for record in refinement['rows']:
    cell=record['cell'];case,plant,ref=cell.split('__')
    rebuilt=run('evaluation',case,plant,ref,16000,s['methods'][record['method']],record['dt'])
    same({k:record[k] for k in METRICS},{k:rebuilt['metrics'][k] for k in METRICS})
same(json.loads((OUT/'diagnostics.json').read_text()),analysis())
d=json.loads((OUT/'diagnostics.json').read_text());assert d['flow_sensor_invariance']['pairs']==192
assert d['flow_sensor_invariance']['equal']==192
print('PASS: 2048 runs, equal tuning budgets, 48 final cells, patient-block intervals, declared criterion, 12 replays, 24 refinement checks and 192 invariance pairs.')
