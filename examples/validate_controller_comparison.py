"""Check working logs and reproduction gates; never certify source equivalence."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from controller_comparison import candidates,run,METRICS

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/controller-comparison'
p=json.loads((OUT/'protocol.json').read_text())
s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text())
manifest=json.loads((ROOT/'data/controller-reference/reproduction.json').read_text())
rows=list(csv.DictReader((OUT/'metrics.csv').open()))
assert len(rows)==2064
assert len({tuple(r[k] for k in ('phase','case','plant','seed','method','venous_bias')) for r in rows})==2064
assert set(p['development_seeds']).isdisjoint(p['evaluation_seeds'])
assert p['candidates']==candidates()
assert s['selection_sha256']==hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()
for f in ('exact_reproduction_completed','authors_results_reproduced','can_claim_advantage_over_published_controller'):
    assert s[f] is False
assert manifest['exact_reproduction_completed'] is False
assert s['blockers']==manifest['unresolved'] and s['blockers']
assert s['development_runs']==768 and s['evaluation_runs']==1296

def means(records):return {key:float(np.mean([float(r[key]) for r in records])) for key in METRICS}
def same(a,b):
    assert set(a)==set(b)
    for key in a:assert abs(a[key]-b[key])<1e-9,(key,a[key],b[key])

dev=[r for r in rows if r['phase']=='development']
final=[r for r in rows if r['phase']=='evaluation']
for family in ('adapted','sentinel'):
    values=[v for v in p['candidates'] if v['family']==family]
    assert len(values)==8
    m={v['id']:means([r for r in dev if r['method']==v['id']]) for v in values}
    for name,value in m.items():same(value,selection[family]['means'][name])
    eligible=[v for v in values if all(m[v['id']][k]<=limit for k,limit in p['exposure_budgets'].items())]
    def key(v):
        x=m[v['id']]
        return ((x['deficit_auc'],values.index(v)) if eligible else
                (x['low_reservoir_s'],x['empty_request_s'],x['high_pressure_s'],x['deficit_auc'],values.index(v)))
    selected=min(eligible or values,key=key)
    assert selected==selection[family]['method']==s['methods'][family]
    assert selection[family]['matched_development_budget']==bool(eligible)
for bias in (0.,.5):
    for method in s['methods']:
        records=[r for r in final if r['method']==method and float(r['venous_bias'])==bias]
        assert len(records)==216
        same(means(records),s['group_means'][str(bias)][method])
# The venous sensor is ignored in the legacy arm: all physical outcomes must pair.
for case in p['scenarios']:
    for plant in p['evaluation_plants']:
        for seed in p['evaluation_seeds']:
            pair=[r for r in final if r['method']=='legacy_sentinel' and r['case']==case
                  and r['plant']==plant and int(r['seed'])==seed]
            assert len(pair)==2
            same({k:float(pair[0][k]) for k in METRICS},{k:float(pair[1][k]) for k in METRICS})
traces=json.loads((OUT/'debug-traces.json').read_text())
assert set(traces)=={case+'/'+method for case in ('clean','combined') for method in s['methods']}
for name,trace in traces.items():
    case,method=name.split('/')
    rebuilt=run(case,{},14000,s['methods'][method])
    same(trace['metrics'],rebuilt['metrics'])
    assert len(trace['rows'])==600
    previous=2.4*rebuilt['patient']['bsa']
    for a,b in zip(trace['rows'],rebuilt['rows']):
        for key in a:
            if a[key] is None:assert b[key] is None
            else:assert abs(float(a[key])-float(b[key]))<1e-9
        assert 0<=a['command']<=7.
        assert abs(a['command']-previous)<=.15+1e-9
        previous=a['command']
    recomputed={
        'deficit_auc':sum(max(0.,280-r['do2'])/60 for r in trace['rows']),
        'low_reservoir_s':sum(r['reservoir']<.25 for r in trace['rows']),
        'empty_request_s':sum(r['empty_request'] for r in trace['rows']),
        'high_pressure_s':sum(r['pressure']>95 for r in trace['rows']),
        'venous_tracking_mae_l_min':np.mean([abs(r['flow']-r['qv']) for r in trace['rows']]),
        'level_mae_l':np.mean([abs(r['reservoir']-.45) for r in trace['rows']])}
    for key,value in recomputed.items():assert abs(trace['metrics'][key]-value)<1e-9
print('PASS: 2064 exploratory runs, equal candidate budgets, frozen selection, information ablation, six rerun traces and unresolved reproduction gates.')
