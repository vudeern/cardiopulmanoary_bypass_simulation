"""Independent checks of stronger-baseline selection, verdict and mechanism."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/submission-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text());params=json.loads((OUT/'parameters.json').read_text())
with (OUT/'metrics.csv').open() as handle:rows=list(csv.DictReader(handle))
assert len(rows)==6496 and sum(r['phase']=='development' for r in rows)==2464
assert sum(r['phase']=='evaluation' for r in rows)==4032
assert len({(r['phase'],r['sensor_case'],r['plant_case'],r['reference_case'],r['seed'],r['variant']) for r in rows})==6496
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds'])
old=json.loads((ROOT/'results/reference-study/protocol.json').read_text())
assert set(p['development_seeds']+p['evaluation_seeds']).isdisjoint(old['development_seeds']+old['evaluation_seeds'])
assert hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()==s['selection_sha256']
metrics=tuple(s['group_means']['good']['forecast'])
def means(records):return {m:float(np.mean([float(r[m]) for r in records])) for m in metrics}
def same(a,b):
    assert a.keys()==b.keys();assert all(abs(a[m]-b[m])<1e-9 for m in a)
development=[r for r in rows if r['phase']=='development']
stats={v['id']:means([r for r in development if r['variant']==v['id']]) for v in p['candidates']}
for vid,m in stats.items():same(m,selection['candidate_means'][vid])
for selected in selection['selected']:
    family=[v for v in p['candidates'] if v['family']==selected['family']]
    eligible=[v for v in family if stats[v['id']]['low_reservoir_s']<=1. and stats[v['id']]['empty_request_s']<=1.]
    ranked=sorted(eligible or family,key=lambda v:((stats[v['id']]['deficit_auc'],family.index(v)) if eligible else
        (stats[v['id']]['low_reservoir_s'],stats[v['id']]['empty_request_s'],stats[v['id']]['deficit_auc'],family.index(v))))
    assert selected['candidate_id']==ranked[0]['id']
    assert selected['options']==ranked[0]['options']
    assert selected['eligible_development_budget']==bool(eligible)
assert s['methods']==selection['selected']
evaluation=[r for r in rows if r['phase']=='evaluation']
assert len(s['cell_means'])==84
for cell,methods in s['cell_means'].items():
    sensor,plant,reference=cell.split('__')
    for vid,m in methods.items():
        records=[r for r in evaluation if r['sensor_case']==sensor and r['plant_case']==plant
            and r['reference_case']==reference and r['variant']==vid]
        assert len(records)==16;same(means(records),m)
for group,methods in s['group_means'].items():
    for vid,m in methods.items():same(means([r for r in evaluation if r['variant']==vid and
        (group=='pooled' or r['reference_case']==group)]),m)
assert len(s['comparisons'])==60
for c in s['comparisons']:
    records=[r for r in evaluation if c['group']=='pooled' or r['reference_case']==c['group']]
    def blocks(vid):return [float(np.mean([float(r[c['metric']]) for r in records if
        r['variant']==vid and int(r['seed'])==seed])) for seed in p['evaluation_seeds']]
    estimate=paired_interval([a-b for a,b in zip(blocks(c['variant']),blocks('forecast'))])
    for key in ('mean','low','high','n'):assert abs(estimate[key]-c[key])<1e-9
primary={c['metric']:c for c in s['comparisons'] if c['group']=='good' and c['variant']=='pi'}
protected=all(primary[m]['high']<=limit for m,limit in p['primary_tolerances'].items())
assert s['verdict']['demonstrated']==(protected and primary['deficit_auc']['high']<0.)
# Complete final-cell sensor-only counterfactuals: changing flow bias must not
# change true outcomes of controllers that ignore that channel.
for plant in p['final_plants']:
    for reference in p['references']:
        for seed in p['evaluation_seeds']:
            for vid in ('pi','threshold'):
                a=next(r for r in evaluation if r['sensor_case']=='clean' and r['plant_case']==plant
                    and r['reference_case']==reference and int(r['seed'])==seed and r['variant']==vid)
                b=next(r for r in evaluation if r['sensor_case']=='flow_high' and r['plant_case']==plant
                    and r['reference_case']==reference and int(r['seed'])==seed and r['variant']==vid)
                for metric in metrics:assert a[metric]==b[metric]
for cell in p['replay_cells']:
    sensor,plant,reference=cell.split('__');seed=p['replay_seed'];param=params['evaluation'][str(seed)]
    scenario=StressScenario(sensor,dilution=1.8,drainage=.35,event_start=param['event_start'],
        event_end=param['event_end'],**p['final_sensors'][sensor])
    text=(ROOT/f'web/submission-{cell}.js').read_text()
    runs=json.loads(text.split('Object.assign(SUBMISSION_STUDY.runs,',1)[1].rsplit(');',1)[0])
    assert len(runs)==3
    for v in s['methods']:
        result=simulate(scenario,'sentinel',seed,patient=Patient(**param['patient']),
            plant_options=p['final_plants'][plant],controller_kind=v['kind'],controller_options=v['options'],
            level_mode='hold',level_reference_options=p['references'][reference])
        run=runs[cell+'/'+v['id']]
        record=next(r for r in evaluation if r['sensor_case']==sensor and r['plant_case']==plant
            and r['reference_case']==reference and int(r['seed'])==seed and r['variant']==v['id'])
        for metric,value in run['metrics'].items():
            assert abs(value-float(record[metric]))<1e-9 and abs(value-result['metrics'][metric])<1e-9
        indices=sorted(set(range(0,len(result['rows']),3))|{len(result['rows'])-1})
        for key,field in dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',
            pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',
            level_sensor='observed_reservoir',level_lower='level_reference_lower').items():
            assert run[key]==[round(result['rows'][i][field],4) if isinstance(result['rows'][i][field],float)
                else result['rows'][i][field] for i in indices]
with (ROOT/'results/mechanism-audit/equilibria.csv').open() as handle:theory=list(csv.DictReader(handle))
assert len(theory)==160
for r in theory:
    expected=.25+float(r['margin_L'])-float(r['residual_level_bias_L'])-float(r['horizon_s'])*float(r['flow_bias_L_min'])/60.
    assert abs(float(r['predicted_equilibrium_L'])-expected)<1e-12
    assert abs(float(r['numerical_equilibrium_L'])-expected)<1e-9
audit=json.loads((ROOT/'results/mechanism-audit/summary.json').read_text())
assert audit['external_validation_completed'] is False
print('PASS: 6496 records, locked selection, 60 paired intervals, 384 flow-bias-invariant pairs, 12 rerun replays and 160 scalar equilibria.')
