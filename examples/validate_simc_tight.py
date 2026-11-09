"""Validate the post-result canonical-rule sensitivity without changing primary."""
import csv
import json
from pathlib import Path
import numpy as np
from simc_benchmark import run,METRICS

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/simc-benchmark'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'canonical-summary.json').read_text())
c=json.loads((OUT/'canonical-protocol.json').read_text());selection=json.loads((OUT/'selection.json').read_text())
rows=list(csv.DictReader((OUT/'canonical-metrics.csv').open()))
assert len(rows)==s['runs']==768
assert len({tuple(r[k] for k in ('case','plant','reference','seed','method')) for r in rows})==768
assert s['status']==c['status']=='post_result_descriptive_sensitivity'
assert s['primary_changed'] is False and s['tuning_selected_on_final_data'] is False
assert s['method']==c['method']
assert s['method']['options']['tau_c']==c['design_theta_s']==1.5
assert s['method']['options']['target_level']==selection['simc']['method']['options']['target_level']
for ref in p['references']:
    selected=[r for r in rows if r['reference']==ref];assert len(selected)==384
    for metric in METRICS:
        value=float(np.mean([float(r[metric]) for r in selected]))
        assert abs(value-s['group_means'][ref][metric])<1e-9
for cell in p['replay_cells']:
    case,plant,ref=cell.split('__')
    result=run('evaluation',case,plant,ref,16000,s['method'])
    stored=next(r for r in rows if (r['case'],r['plant'],r['reference'],int(r['seed']))==(case,plant,ref,16000))
    for metric in METRICS:assert abs(float(stored[metric])-result['metrics'][metric])<1e-9
print('PASS: 768 explicitly secondary canonical checks, fixed source rule and six fresh reruns; primary unchanged.')
