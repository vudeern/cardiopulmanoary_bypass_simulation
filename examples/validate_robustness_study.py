"""Recalculate every retained stress cell and the paired patient intervals."""
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

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/robustness'
p=json.loads((OUT/'protocol.json').read_text())
s=json.loads((OUT/'summary.json').read_text())
parameters=json.loads((OUT/'parameters.json').read_text())
rows=list(csv.DictReader((OUT/'metrics.csv').open()))
assert len(rows)==p['total_runs']==4320
assert p['no_tuning'] is True
source=ROOT/p['settings_source']
assert hashlib.sha256(source.read_bytes()).hexdigest()==p['settings_source_sha256']
assert s['variants']==json.loads(source.read_text())['selected']==p['variants']
assert {int(r['seed']) for r in rows}==set(p['seeds'])
assert len(s['cell_means'])==45
assert set(Counter(r['scenario'] for r in rows).values())=={96}
assert len({(r['scenario'],r['variant'],r['seed']) for r in rows})==4320
for name in ['conservative-comparison','conservative-pilot']:
    old=json.loads((ROOT/f'results/{name}/protocol.json').read_text())
    old_seeds=set(old['tuning_seeds']+old['evaluation_seeds']+old['map_seeds'])
    assert old_seeds.isdisjoint(p['seeds'])
metrics=tuple(s['pooled_means']['guarded'])
def same(runs,means):
    for metric,value in means.items():
        assert abs(np.mean([float(r[metric]) for r in runs])-value)<1e-9
for cell,policies in s['cell_means'].items():
    for vid,m in policies.items():
        runs=[r for r in rows if r['scenario']==cell and r['variant']==vid]
        assert len(runs)==24;same(runs,m)
for sensor,policies in s['sensor_means'].items():
    for vid,m in policies.items():same([r for r in rows if r['sensor_case']==sensor and r['variant']==vid],m)
for vid,m in s['pooled_means'].items():same([r for r in rows if r['variant']==vid],m)
assert len(s['comparisons'])==1104
for c in s['comparisons']:
    runs=[r for r in rows if c['scenario']=='pooled' or r['scenario']==c['scenario']]
    def blocks(vid):
        return [float(np.mean([float(r[c['metric']]) for r in runs if r['variant']==vid
                and int(r['seed'])==seed])) for seed in p['seeds']]
    estimate=paired_interval([a-b for a,b in zip(blocks(c['variant']),blocks('guarded'))])
    for key in ('mean','low','high','n'):assert abs(estimate[key]-c[key])<1e-9
for r in rows:
    for metric in ('low_reservoir_s','empty_request_s','high_pressure_s','level_fault_s'):
        assert 0<=float(r[metric])<=p['duration']
    assert int(r['level_alarm_ever']) in (0,1)
    assert (r['first_alarm_s']!='')==bool(int(r['level_alarm_ever']))
    assert int(r['level_fault_injected'])==int(r['sensor_case'] in ('step','drift','initial','small_step','drift_flow'))
    if not int(r['level_fault_injected']):
        assert int(r['alarm_before_level_bias'])==int(r['level_alarm_ever'])
# Re-run all 24 prespecified replay trajectories independently of the exporter.
for cell in p['replay_cells']:
    text=(ROOT/f'web/robustness-{cell}.js').read_text()
    runs=json.loads(text.split('Object.assign(ROBUSTNESS.runs,',1)[1].rsplit(');',1)[0])
    assert len(runs)==4
    sensor,plant=cell.split('__');seed=p['replay_seed']
    params=parameters[str(seed)][plant]
    scenario=StressScenario(cell,**p['common_challenge'],event_start=params['event_start'],
        event_end=params['event_end'],**p['sensor_cases'][sensor])
    for variant in p['variants']:
        record=next(r for r in rows if r['scenario']==cell and r['variant']==variant['id'] and int(r['seed'])==seed)
        result=simulate(scenario,variant['policy'],seed,patient=Patient(**params['patient']),
                        controller_options=variant['options'],plant_options=params['plant_options'])
        run=runs[cell+'/'+variant['id']]
        for metric,value in run['metrics'].items():
            assert abs(value-float(record[metric]))<1e-9
            assert abs(value-result['metrics'][metric])<1e-9
        indices=sorted(set(range(0,len(result['rows']),3))|{len(result['rows'])-1})
        for key,field in dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',
            pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',
            level_sensor='observed_reservoir',level_lower='reservoir_lower').items():
            expected=[round(result['rows'][i][field],4) if isinstance(result['rows'][i][field],float)
                      else result['rows'][i][field] for i in indices]
            assert run[key]==expected
print('PASS: 4320 stress records, immutable settings, 45 cells, 1104 paired intervals and 24 independently rerun replays.')
