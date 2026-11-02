"""Check benchmark pairing, units, replay export and file links independently."""
import csv
import json
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((ROOT/'results/metrics.csv').open()))
assert len(rows)==1008
assert all(v==6 for v in Counter((r['scenario'],r['seed']) for r in rows).values())
for r in rows:
    assert 0<=float(r['hb_bound_coverage'])<=1
    assert float(r['false_reassurance_margin_s'])<=float(r['false_reassurance_s'])<=1200
    assert float(r['concealed_deficit_auc'])<=float(r['deficit_auc'])+1e-8
    assert float(r['low_reservoir_s'])<=1200
summary=json.loads((ROOT/'results/summary.json').read_text())
assert len(summary['comparisons'])==140
for c in summary['comparisons']:
    paired={r['seed']:float(r[c['metric']]) for r in rows if r['scenario']==c['scenario'] and r['policy']==c['policy']}
    baseline={r['seed']:float(r[c['metric']]) for r in rows if r['scenario']==c['scenario'] and r['policy']=='reactive'}
    mean=sum(paired[s]-baseline[s] for s in paired)/len(paired)
    assert abs(mean-c['mean'])<1e-8
for p in (ROOT/'docs').glob('*.svg'):
    ElementTree.parse(p)
# Relative Markdown destinations must resolve to an existing deliverable.
for p in [ROOT/'README.md',*(ROOT/'docs').glob('*.md')]:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        if '://' not in target and not target.startswith('#'):
            assert (p.parent/target.split('#')[0]).exists(),f'{p.name}: {target}'
web=(ROOT/'web/index.html').read_text()
for target in re.findall(r'(?:src|href)="([^"#]+)"',web):
    if '://' not in target:
        assert (ROOT/'web'/target).exists(),target
print('PASS: 1008 paired records, 140 independently recalculated differences, metric bounds, SVG XML and local links.')

