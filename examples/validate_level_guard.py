"""Independently recalculate guard report aggregates from all retained records."""
import csv
import json
from collections import Counter
from pathlib import Path
import numpy as np
from perfusion_lab.benchmark import paired_interval

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/level-guard'
protocol = json.loads((OUT/'protocol.json').read_text())
summary = json.loads((OUT/'summary.json').read_text())
rows = list(csv.DictReader((OUT/'metrics.csv').open()))
assert len(rows) == protocol['expected_runs'] == 1092
keys = [(r['experiment'], r['scenario'], r['seed'], r['level_bias_L'],
         r['drainage'], r['policy']) for r in rows]
assert len(set(keys)) == len(keys)
assert Counter(r['experiment'] for r in rows) == {'cohort':504, 'map':588}
assert set(r['policy'] for r in rows) == set(protocol['policies'])
for experiment, seed_key in [('cohort','cohort_seeds'), ('map','map_seeds')]:
    assert {int(r['seed']) for r in rows if r['experiment']==experiment} == set(protocol[seed_key])
for name, policies in summary['cohort_means'].items():
    for policy, means in policies.items():
        runs = [r for r in rows if r['experiment']=='cohort' and
                r['scenario']==name and r['policy']==policy]
        assert len(runs) == 24
        for metric, value in means.items():
            assert abs(np.mean([float(r[metric]) for r in runs])-value) < 1e-9
assert len(summary['comparisons']) == 112
for c in summary['comparisons']:
    runs = [r for r in rows if r['experiment']=='cohort' and r['scenario']==c['scenario']]
    a = {r['seed']:float(r[c['metric']]) for r in runs if r['policy']==c['policy']}
    b = {r['seed']:float(r[c['metric']]) for r in runs if r['policy']==c['baseline']}
    assert a.keys() == b.keys()
    estimate = paired_interval([a[s]-b[s] for s in sorted(a)])
    for field in ('mean','low','high','n'):
        assert abs(estimate[field]-c[field]) < 1e-9
assert len(summary['map']) == 49
for cell in summary['map']:
    for policy, means in cell['means'].items():
        runs = [r for r in rows if r['experiment']=='map' and r['policy']==policy and
                float(r['level_bias_L'])==cell['level_bias_L'] and
                float(r['drainage'])==cell['drainage']]
        assert len(runs) == 4
        for metric, value in means.items():
            assert abs(np.mean([float(r[metric]) for r in runs])-value) < 1e-9
print('PASS: all 1092 guard runs, 112 paired intervals, 49 map cells and all report means.')
