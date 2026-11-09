"""Independent rc.4 accounting, selection, paired analysis and replay checks."""
import argparse
import csv
import json
import math
import numpy as np
import finite_return_study as study
from perfusion_lab.benchmark import paired_interval


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8), (a, b)


def validate(replay=False):
    p = json.loads(study.dumps(study.protocol()))
    summary = json.loads((study.OUT/'summary.json').read_text())
    rows = study.read_rows()
    assert summary['version'] == '2.0.0rc4' and summary['runs'] == 6144 and summary['patients'] == 32
    assert not summary['version2_ready'] and summary['qualifying_confirmation_cohorts'] == 0
    assert summary['confirmation_seeds_executed'] == p['confirmation_seeds_executed'] == []
    assert p['seeds'] == list(range(37000, 37032))
    assert summary['protocol_sha256'] == study.digest(study.OUT/'protocol.json')
    for path, sha in p['source_hashes'].items(): assert study.digest(study.ROOT/path) == sha, path
    expected = {(seed, *cell, name) for seed in study.SEEDS for cell in study.cells() for name in study.methods()}
    actual = [(r['seed'], r['stage'], r['phys'], r['plant'], r['fault'], r['calibration'], r['method']) for r in rows]
    assert len(actual) == len(set(actual)) == len(expected) and set(actual) == expected
    for row in rows:
        for metric in study.METRICS: assert math.isfinite(row[metric]) and row[metric] >= 0
        for metric in ('low_reservoir_s', 'empty_request_s', 'high_pressure_s', 'protection_active_s', 'protection_unsupported_s'):
            assert row[metric] <= 600.
    for group, stats in summary['groups'].items():
        for name in study.methods():
            block = [r for r in rows if study.belongs(r, group) and r['method'] == name]
            reported = stats[name]
            assert reported['runs'] == len(block)
            for metric in study.METRICS: close(reported['means'][metric], np.mean([r[metric] for r in block]))
            close(reported['worst_minimum_L'], min(r['minimum_reservoir'] for r in block))
            close(reported['worst_floor_exposure_s'], max(r['low_reservoir_s'] for r in block))
            assert reported['floor_crossing_cases'] == sum(r['low_reservoir_s'] > 0 for r in block)
            assert reported['empty_cases'] == sum(r['empty_request_s'] > 0 for r in block)
    eligible = []
    for name in study.CANDIDATES:
        block = [r for r in rows if r['method'] == name and r['stage'] in ('primary', 'abrupt_stop')]
        if all(r['low_reservoir_s'] == r['empty_request_s'] == 0 for r in block): eligible.append(name)
    assert eligible == summary['eligible_candidates']
    selected = min(eligible, key=lambda n: summary['groups']['primary'][n]['means']['deficit_auc']) if eligible else None
    assert selected == summary['selected_candidate']
    expected_comparisons = {(n, b, g, m) for n in study.CANDIDATES for b in ('zero_return', 'eligible_pi') for g in ('clean', 'bias', 'outage') for m in ('deficit_auc', 'low_reservoir_s', 'empty_request_s', 'high_pressure_s')}
    actual_comparisons = [(c['candidate'], c['baseline'], c['group'], c['metric']) for c in summary['comparisons']]
    assert len(actual_comparisons) == len(set(actual_comparisons)) == len(expected_comparisons)
    assert set(actual_comparisons) == expected_comparisons
    for c in summary['comparisons']:
        differences = []
        for seed in study.SEEDS:
            block = [r for r in rows if r['seed'] == seed and study.belongs(r, c['group'])]
            differences.append(np.mean([r[c['metric']] for r in block if r['method'] == c['candidate']])-np.mean([r[c['metric']] for r in block if r['method'] == c['baseline']]))
        expected_interval = paired_interval(differences)
        for key in ('mean', 'low', 'high', 'n'): close(c[key], expected_interval[key])
    gates = {}
    if selected:
        for g in ('clean', 'bias', 'outage'):
            block = [r for r in rows if study.belongs(r, g)]
            a = [r for r in block if r['method'] == selected]; b = [r for r in block if r['method'] == 'eligible_pi']
            intervals = {c['metric']: c for c in summary['comparisons'] if c['candidate'] == selected and c['baseline'] == 'eligible_pi' and c['group'] == g}
            gates[g] = dict(oxygen_mean_10_percent=np.mean([r['deficit_auc'] for r in a]) <= .9*np.mean([r['deficit_auc'] for r in b]),
                oxygen_paired_interval=intervals['deficit_auc']['high'] < 0,
                mean_low_reservoir=np.mean([r['low_reservoir_s'] for r in a]) <= 1., zero_empty_requests=all(r['empty_request_s'] == 0 for r in a),
                extra_low_reservoir=intervals['low_reservoir_s']['high'] <= 1., extra_empty_requests=intervals['empty_request_s']['high'] <= 1., extra_high_pressure=intervals['high_pressure_s']['high'] <= 5.)
    assert gates == summary['development_gates']
    assert summary['development_joint_success'] == bool(selected and all(all(v.values()) for v in gates.values()))
    old = {}
    for seed in study.SEEDS:
        with (study.previous.OUT/f'{seed}.csv').open() as handle:
            for row in csv.DictReader(handle):
                key = (int(row['seed']), row['stage'], row['phys'], row['plant'], row['fault'], row['calibration'], 'zero_return' if row['method'] == 'protected' else row['method'])
                old[key] = row
    checked = 0
    for row, key in zip(rows, actual):
        if row['method'] in study.CANDIDATES or row['stage'] == 'abrupt_stop': continue
        for metric in study.METRICS: close(row[metric], float(old[key][metric]))
        checked += 1
    assert checked == 2688
    original = (study.ROOT/'src/perfusion_lab/depletion_simulation.py').read_text()
    expected_adapter = original.replace('Conservative depletion simulation; timing and metrics mirror the rc.2 adapter.', 'Finite-return candidate adapter; frozen physiology and timing.').replace('def simulate_depletion(', 'def simulate_finite_return(').replace('from .', 'from perfusion_lab.').replace('from perfusion_lab.depletion import DepletionRuntime as ControllerRuntime', 'from perfusion_candidates.finite_return import FiniteReturnRuntime as ControllerRuntime')
    assert expected_adapter == (study.ROOT/'src/perfusion_candidates/simulation.py').read_text()
    if replay:
        for stage in ('primary', 'abrupt_stop'):
            fault = 'positive_start' if stage == 'primary' else 'clean'
            for name in (selected or 'credit_15', 'zero_return', 'eligible_pi'):
                result = study.run(37014, stage, 'combined', 'slow', fault, 'good', name, study.methods()[name])
                row = next(r for r in rows if (r['seed'], r['stage'], r['phys'], r['plant'], r['fault'], r['calibration'], r['method']) == (37014, stage, 'combined', 'slow', fault, 'good', name))
                for metric in study.METRICS[:7]: close(result['metrics'][metric], row[metric])
    print('PASS: 6,144 records, frozen sources/grid, all aggregates and 72 paired intervals, selection/gates, 2,688 baseline matches'+(' and six replays.' if replay else '.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--replay', action='store_true')
    validate(parser.parse_args().replay)
