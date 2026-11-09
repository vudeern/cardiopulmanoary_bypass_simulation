"""Recompute selection, evaluation, bootstrap and replay evidence from raw CSV."""
import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/conservative-comparison'
p = json.loads((OUT/'protocol.json').read_text())
selection = json.loads((OUT/'selection.json').read_text())
summary = json.loads((OUT/'summary.json').read_text())
rows = list(csv.DictReader((OUT/'metrics.csv').open()))
tuning = list(csv.DictReader((OUT/'tuning.csv').open()))
assert len(rows)==p['total_runs']==3192
assert Counter(r['experiment'] for r in rows)=={'tuning':1736,'evaluation':672,'map':784}
assert tuning==[r for r in rows if r['experiment']=='tuning']
keys = [(r['experiment'],r['scenario'],r['seed'],r['variant'],r['level_bias_L'],r['drainage']) for r in rows]
assert len(keys)==len(set(keys))
assert set(p['tuning_seeds']).isdisjoint(p['evaluation_seeds'])
assert set(p['evaluation_seeds']).isdisjoint(p['map_seeds'])
assert set(p['tuning_seeds']).isdisjoint(p['map_seeds'])
pilot=ROOT/'results/conservative-pilot'
pilot_protocol=json.loads((pilot/'protocol.json').read_text())
pilot_rows=list(csv.DictReader((pilot/'metrics.csv').open()))
assert len(pilot_rows)==2240
assert Counter(r['experiment'] for r in pilot_rows)=={'tuning':784,'evaluation':672,'map':784}
pilot_seeds=set(pilot_protocol['tuning_seeds']+pilot_protocol['evaluation_seeds']+pilot_protocol['map_seeds'])
assert pilot_seeds.isdisjoint(p['tuning_seeds']+p['evaluation_seeds']+p['map_seeds'])
metrics = tuple(summary['pooled_means']['guarded'])
def means(runs):
    return {m:float(np.mean([float(r[m]) for r in runs])) for m in metrics}
def same_means(a,b):
    assert a.keys()==b.keys()
    assert all(abs(a[k]-b[k])<1e-9 for k in a)
aggregates = {}
for variant in p['candidates']:
    selected = [r for r in tuning if r['variant']==variant['id']]
    assert len(selected)==7*8
    aggregates[variant['id']] = means(selected)
    same_means(aggregates[variant['id']], selection['candidate_means'][variant['id']])
same_means(aggregates['guarded'], selection['guard_budget'])
for winner in selection['selected']:
    family=[v for v in p['candidates'] if v['family']==winner['family']]
    eligible=[v for v in family if all(aggregates[v['id']][m]<=aggregates['guarded'][m]+1e-9
               for m in p['risk_metrics'])]
    assert winner['matched_tuning_budget']==bool(eligible)
    ordered=sorted(eligible or family, key=lambda v:
        ((aggregates[v['id']]['deficit_auc'],family.index(v)) if eligible else
         (aggregates[v['id']]['low_reservoir_s'],aggregates[v['id']]['empty_request_s'],
          aggregates[v['id']]['deficit_auc'],family.index(v))))
    assert winner['id']==ordered[0]['id']
    assert winner['options']==ordered[0]['options']
selected_ids={v['id'] for v in summary['selected']}
assert selected_ids=={'original','guarded',*(v['id'] for v in selection['selected'])}
evaluation=[r for r in rows if r['experiment']=='evaluation']
assert {r['variant'] for r in evaluation}==selected_ids
for experiment,seed_key in [('tuning','tuning_seeds'),('evaluation','evaluation_seeds'),('map','map_seeds')]:
    assert {int(r['seed']) for r in rows if r['experiment']==experiment}==set(p[seed_key])
for scenario,policies in summary['cohort_means'].items():
    for vid,m in policies.items():
        runs=[r for r in evaluation if r['variant']==vid and r['scenario']==scenario]
        assert len(runs)==24
        same_means(means(runs),m)
for vid,m in summary['pooled_means'].items():
    same_means(means([r for r in evaluation if r['variant']==vid]),m)
assert len(summary['comparisons'])==192
for c in summary['comparisons']:
    def blocks(vid):
        return [float(np.mean([float(r[c['metric']]) for r in evaluation if
                r['variant']==vid and int(r['seed'])==seed and
                (c['scenario']=='pooled' or r['scenario']==c['scenario'])]))
                for seed in p['evaluation_seeds']]
    a,b=blocks(c['variant']),blocks('guarded')
    estimate=paired_interval([x-y for x,y in zip(a,b)])
    for k in ('mean','low','high','n'):assert abs(c[k]-estimate[k])<1e-9
assert len(summary['map'])==49
for cell in summary['map']:
    for vid,m in cell['means'].items():
        runs=[r for r in rows if r['experiment']=='map' and r['variant']==vid and
              float(r['level_bias_L'])==cell['level_bias_L'] and float(r['drainage'])==cell['drainage']]
        assert len(runs)==4
        same_means(means(runs),m)
for r in rows:
    for key in ('low_reservoir_s','empty_request_s','high_pressure_s','level_fault_s'):
        assert 0<=float(r[key])<=p['duration']
    assert 0<=float(r['hb_bound_coverage'])<=1
    assert float(r['concealed_deficit_auc'])<=float(r['deficit_auc'])+1e-9
for scenario in p['scenarios']:
    text=(ROOT/f'web/comparison-{scenario}.js').read_text()
    runs=json.loads(text.split('Object.assign(COMPARISON.runs,',1)[1].rsplit(');',1)[0])
    assert len(runs)==4
    for name,run in runs.items():
        scenario_name,vid=name.split('/')
        record=next(r for r in evaluation if r['scenario']==scenario_name and
                    r['variant']==vid and int(r['seed'])==p['evaluation_seeds'][0])
        for m,value in run['metrics'].items():assert abs(value-float(record[m]))<1e-9
        assert run['t'][0]==2 and run['t'][-1]==1200 and len(run['t'])==201
        assert all(len(run[key])==201 for key in ('do2','monitor','reservoir','pressure','level_fault'))
print('PASS: 3192 final records, separate 2240-run pilot, tuning-only selection, 192 paired intervals, 49 map cells and 28 replay trajectories.')
