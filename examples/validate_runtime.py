"""Exact adapter parity on retained v1.14 replay cells, not new evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import model_bank_study as study
from perfusion_lab.runtime_simulation import simulate_runtime

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'results/runtime-parity/summary.json'


def validate():
    protocol = json.loads((study.OUT/'protocol.json').read_text())
    for name, expected in protocol['source_hashes'].items():
        assert study.digest(ROOT/name) == expected, name
    selection = json.loads((study.OUT/'selection.json').read_text())
    config = selection['selected']['configuration']
    methods = dict(hybrid=dict(engine='model', kind='integrity_hybrid', **config),
                   pi=dict(engine='model', kind='integrity_pi', **config),
                   single_model=dict(engine='model', kind='integrity_hybrid',
                       guard={**config['guard'], 'model_taus':[2.]}, options=config['options']))
    checks = []
    for cell in study.REPLAYS:
        phys, plant, fault, cal = cell.split('__')
        for label, method in methods.items():
            args = ('evaluation', phys, plant, fault, cal, 36000, method)
            expected = study.run(*args)
            with patch.object(study, 'simulate_model', simulate_runtime):
                actual = study.run(*args)
            assert actual == expected, (cell, label)
            checks.append(dict(cell=cell, method=label, steps=len(actual['rows']),
                full_trajectory_and_metrics_identical=True))
    names = ('src/perfusion_lab/runtime.py','src/perfusion_lab/runtime_simulation.py',
             'examples/validate_runtime.py')
    return dict(version='2.0.0rc1', status='exact_v114_behavior_parity',
        paired_runs=len(checks), simulations=len(checks)*2,
        steps_each_side=sum(c['steps'] for c in checks), checks=checks,
        new_performance_evidence=False, qualifying_confirmation_cohorts=0,
        source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names},
        limitation='Retained v1.14 replay cases; no new population or controller tuning. Fixed-step Python interface, no hardware I/O, watchdog, real-time deadline or bounded-memory validation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    value = json.dumps(validate(), indent=2)+'\n'
    if args.check:
        assert OUTPUT.read_text() == value, 'Runtime parity artifact is stale'
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(value)
    print('PASS: 24 paired 600-step runs, every trajectory field and metric identical to frozen v1.14.')
