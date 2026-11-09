"""Independently verify selection, primary answer, pairing and replay values."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/reference-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text());methods=json.loads((OUT/'methods.json').read_text())
params=json.loads((OUT/'parameters.json').read_text())
with (OUT/'metrics.csv').open() as f:rows=list(csv.DictReader(f))
assert len(rows)==8568==p['total_runs']
assert Counter(r['phase'] for r in rows)=={'development':1008,'evaluation':7560}
assert len({(r['phase'],r['sensor_case'],r['plant_case'],r['reference_case'],r['seed'],r['variant']) for r in rows})==8568
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds'])
old=json.loads((ROOT/'results/robustness/protocol.json').read_text())
assert set(old['seeds']).isdisjoint(p['development_seeds']+p['evaluation_seeds'])
assert hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()==s['selection_sha256']
metrics=tuple(s['group_means']['good']['bounded_reference'])
def means(records):return {m:float(np.mean([float(r[m]) for r in records])) for m in metrics}
def equal(a,b):
    assert a.keys()==b.keys();assert all(abs(a[k]-b[k])<1e-9 for k in a)
development=[r for r in rows if r['phase']=='development']
stats={v['id']:means([r for r in development if r['variant']==v['id']]) for v in p['candidates']}
for key,m in stats.items():equal(m,selection['candidate_means'][key])
simple=[v for v in p['candidates'] if v['level_mode']=='hold']
budget=stats['bounded_reference'];equal(budget,selection['budget'])
eligible=[v for v in simple if all(stats[v['id']][m]<=budget[m]+1e-9
          for m in ('low_reservoir_s','empty_request_s'))]
assert selection['matched_development_budget']==bool(eligible)
ranked=sorted(eligible or simple,key=lambda v:((stats[v['id']]['deficit_auc'],simple.index(v)) if eligible else
    (stats[v['id']]['low_reservoir_s'],stats[v['id']]['empty_request_s'],stats[v['id']]['deficit_auc'],simple.index(v))))
assert selection['selected']==ranked[0]
assert s['methods']==methods
selected=next(v for v in methods if v['id']=='simple_reference')
assert selected['options']==selection['selected']['options'] and selected['level_mode']=='hold'
evaluation=[r for r in rows if r['phase']=='evaluation']
assert {int(r['seed']) for r in evaluation}==set(p['evaluation_seeds'])
assert len(s['cell_means'])==126
for cell,variants in s['cell_means'].items():
    sensor,plant,reference=cell.split('__')
    for vid,m in variants.items():
        records=[r for r in evaluation if r['sensor_case']==sensor and r['plant_case']==plant
                 and r['reference_case']==reference and r['variant']==vid]
        assert len(records)==12;equal(means(records),m)
for group,variants in s['group_means'].items():
    for vid,m in variants.items():
        equal(means([r for r in evaluation if r['variant']==vid and
              (group=='pooled' or r['reference_case']==group)]),m)
assert len(s['comparisons'])==168
for c in s['comparisons']:
    subset=[r for r in evaluation if c['group']=='pooled' or r['reference_case']==c['group']]
    def blocks(vid):
        return [float(np.mean([float(r[c['metric']]) for r in subset if int(r['seed'])==seed
                and r['variant']==vid])) for seed in p['evaluation_seeds']]
    estimate=paired_interval([a-b for a,b in zip(blocks(c['variant']),blocks('bounded_reference'))])
    for key in ('mean','low','high','n'):assert abs(estimate[key]-c[key])<1e-9
primary={c['metric']:c for c in s['comparisons'] if c['group']=='good' and c['variant']=='simple_reference'}
expected_risk=all(primary[m]['low']>=-1. for m in ('low_reservoir_s','empty_request_s'))
expected_deficit=primary['deficit_auc']['low']>0.
assert s['verdict']['demonstrated']==(expected_risk and expected_deficit)
assert s['verdict']['risk_criterion_pass']==expected_risk
assert s['verdict']['deficit_criterion_pass']==expected_deficit
extra=json.loads((OUT/'secondary-contrast.json').read_text())
assert 'after seeing final results' in extra['status']
for c in extra['comparisons']:
    good_rows=[r for r in evaluation if r['reference_case']=='good']
    def secondary_blocks(vid):
        return [float(np.mean([float(r[c['metric']]) for r in good_rows if r['variant']==vid
                and int(r['seed'])==seed])) for seed in p['evaluation_seeds']]
    estimate=paired_interval([a-b for a,b in zip(secondary_blocks('simple_reference'),secondary_blocks('reserve'))])
    for key in ('mean','low','high','n'):assert abs(estimate[key]-c[key])<1e-9
# Sampling, dropout and delivered-reference counts are identical across paired methods.
counts={}
for row in evaluation:
    key=(row['sensor_case'],row['plant_case'],row['reference_case'],row['seed'])
    counts.setdefault(key,set()).add(row['level_reference_count'])
    assert 0<=float(row['low_reservoir_s'])<=1200
    assert 0<=float(row['empty_request_s'])<=1200
assert all(len(values)==1 for values in counts.values())
for cell in p['replay_cells']:
    sensor,plant,reference=cell.split('__');seed=p['replay_seed']
    text=(ROOT/f'web/reference-{cell}.js').read_text()
    runs=json.loads(text.split('Object.assign(REFERENCE_STUDY.runs,',1)[1].rsplit(');',1)[0])
    assert len(runs)==5
    param=params['evaluation'][str(seed)]
    scenario=StressScenario(sensor,dilution=1.8,drainage=.4,event_start=param['event_start'],
        event_end=param['event_end'],**p['final_sensors'][sensor])
    for v in methods:
        result=simulate(scenario,v['policy'],seed,patient=Patient(**param['patient']),
            plant_options=p['final_plants'][plant],controller_options=v['options'],level_mode=v['level_mode'],
            level_reference_options=p['references'][reference],level_observer_options=p['observer'])
        run=runs[cell+'/'+v['id']]
        record=next(r for r in evaluation if r['sensor_case']==sensor and r['plant_case']==plant
                    and r['reference_case']==reference and int(r['seed'])==seed and r['variant']==v['id'])
        for m,value in run['metrics'].items():
            assert abs(value-float(record[m]))<1e-9 and abs(value-result['metrics'][m])<1e-9
        indices=sorted(set(range(0,len(result['rows']),3))|{len(result['rows'])-1})
        for key,field in dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',
            pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',
            level_sensor='observed_reservoir',level_lower='level_reference_lower').items():
            expected=[round(result['rows'][i][field],4) if isinstance(result['rows'][i][field],float)
                      else result['rows'][i][field] for i in indices]
            assert run[key]==expected
print('PASS: 8568 records, development-only selection, 126 cells, 168 paired intervals, verdict and 30 independently rerun replays.')
