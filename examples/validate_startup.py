"""Independent rc.5 grid, startup accounting, selection and reference checks."""
import argparse
import json
import math
import numpy as np
import startup_study as study
from perfusion_lab.benchmark import paired_interval


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8), (a, b)


def validate(replay=False):
    p = json.loads(study.dumps(study.protocol()))
    s = json.loads((study.OUT/'summary.json').read_text()); rows = study.read_rows()
    assert s['version'] == '2.0.0rc5' and s['patients'] == 32 and s['runs'] == 2048
    assert not s['version2_ready'] and s['qualifying_confirmation_cohorts'] == 0
    assert s['confirmation_seeds_executed'] == p['confirmation_seeds_executed'] == []
    assert p['seeds'] == list(range(37000, 37032))
    assert s['protocol_sha256'] == study.digest(study.OUT/'protocol.json')
    for path, sha in p['source_hashes'].items(): assert study.digest(study.ROOT/path) == sha, path
    expected = {(seed, *cell, name) for seed in study.SEEDS for cell in study.previous.cells() for name in study.methods()}
    actual = [(r['seed'], r['stage'], r['phys'], r['plant'], r['fault'], r['calibration'], r['method']) for r in rows]
    assert len(actual) == len(set(actual)) == len(expected) and set(actual) == expected
    for r in rows:
        for m in study.METRICS: assert math.isfinite(r[m]) and r[m] >= 0
        close(r['startup_deficit_auc']+r['later_deficit_auc'], r['deficit_auc'])
        assert r['startup_unsupported_s'] <= min(126., r['protection_unsupported_s'])
        for m in ('low_reservoir_s','empty_request_s','high_pressure_s','protection_active_s','protection_unsupported_s','single_anchor_supported_s','lower_undercoverage_s'):
            assert r[m] <= 600.
    old_rows = study.previous.read_rows()
    archived = [r for r in old_rows if r['method'] == 'eligible_pi' and r['stage'] == 'primary']
    assert len(archived) == s['archived_pi_runs'] == 512
    assert s['archived_pi_protocol_sha256'] == study.digest(study.previous.OUT/'protocol.json')
    for group, stats in s['groups'].items():
        for name, reported in stats.items():
            source = archived if name == 'archived_pi' else [r for r in rows if r['method'] == name]
            block = [r for r in source if study.previous.belongs(r, group)]
            assert reported['runs'] == len(block)
            for m, value in reported['means'].items(): close(value, np.mean([r[m] for r in block]))
            assert reported['floor_crossing_cases'] == sum(r['low_reservoir_s'] > 0 for r in block)
            assert reported['empty_cases'] == sum(r['empty_request_s'] > 0 for r in block)
            close(reported['worst_minimum_L'], min(r['minimum_reservoir'] for r in block))
            close(reported['worst_floor_exposure_s'], max(r['low_reservoir_s'] for r in block))
    comparison_keys = {(b,g,m) for b in ('rc4','archived_pi') for g in ('clean','bias','outage') for m in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s')}
    actual_keys = [(c['baseline'],c['group'],c['metric']) for c in s['comparisons']]
    assert len(actual_keys) == len(set(actual_keys)) == len(comparison_keys) and set(actual_keys) == comparison_keys
    for c in s['comparisons']:
        differences = []
        for seed in study.SEEDS:
            a = [r for r in rows if r['seed'] == seed and r['method'] == 'single_anchor' and study.previous.belongs(r,c['group'])]
            reference = archived if c['baseline'] == 'archived_pi' else [r for r in rows if r['method'] == 'rc4']
            b = [r for r in reference if r['seed'] == seed and study.previous.belongs(r,c['group'])]
            differences.append(np.mean([r[c['metric']] for r in a])-np.mean([r[c['metric']] for r in b]))
        interval = paired_interval(differences)
        for k in ('mean','low','high','n'): close(c[k],interval[k])
    candidate = [r for r in rows if r['method'] == 'single_anchor']
    protected = all(r['low_reservoir_s'] == r['empty_request_s'] == 0 for r in candidate if r['stage'] in ('primary','abrupt_stop'))
    selected = 'single_anchor' if protected and s['groups']['primary']['single_anchor']['means']['deficit_auc'] < s['groups']['primary']['rc4']['means']['deficit_auc'] else None
    assert s['selected_candidate'] == selected
    gates = {}
    for g in ('clean','bias','outage'):
        a = [r for r in candidate if study.previous.belongs(r,g)]; b = [r for r in archived if study.previous.belongs(r,g)]
        intervals = {c['metric']:c for c in s['comparisons'] if c['baseline'] == 'archived_pi' and c['group'] == g}
        gates[g] = dict(oxygen_mean_10_percent=np.mean([r['deficit_auc'] for r in a]) <= .9*np.mean([r['deficit_auc'] for r in b]),
            oxygen_paired_interval=intervals['deficit_auc']['high'] < 0,
            mean_low_reservoir=np.mean([r['low_reservoir_s'] for r in a]) <= 1., zero_empty_requests=all(r['empty_request_s'] == 0 for r in a),
            extra_low_reservoir=intervals['low_reservoir_s']['high'] <= 1., extra_empty_requests=intervals['empty_request_s']['high'] <= 1., extra_high_pressure=intervals['high_pressure_s']['high'] <= 5.)
    assert gates == s['development_gates']
    assert s['development_joint_success'] == bool(selected and all(all(v.values()) for v in gates.values()))
    references = {(r['seed'],r['stage'],r['phys'],r['plant'],r['fault'],r['calibration']):r for r in old_rows if r['method'] == 'credit_15'}
    checked = 0
    for r in rows:
        if r['method'] != 'rc4': continue
        old = references[tuple(r[k] for k in ('seed','stage','phys','plant','fault','calibration'))]
        for m in study.previous.METRICS: close(r[m],old[m])
        checked += 1
    assert checked == 1024
    missing = {tuple(r[k] for k in ('seed','phys','plant')):r for r in candidate if r['calibration'] == 'missing'}
    for r in rows:
        if r['method'] == 'rc4' and r['calibration'] == 'missing':
            for m in study.METRICS: close(r[m], missing[tuple(r[k] for k in ('seed','phys','plant'))][m])
    original = (study.ROOT/'src/perfusion_candidates/simulation.py').read_text()
    adapter = original.replace('Finite-return candidate adapter; frozen physiology and timing.','Single-anchor startup adapter; frozen physiology and timing.').replace('def simulate_finite_return(','def simulate_startup(').replace('from perfusion_candidates.finite_return import FiniteReturnRuntime as ControllerRuntime','from perfusion_candidates.startup import StartupRuntime as ControllerRuntime')
    assert adapter == (study.ROOT/'src/perfusion_candidates/startup_simulation.py').read_text()
    if replay:
        for stage in ('primary','abrupt_stop'):
            for name in study.methods():
                fault = 'positive_start' if stage == 'primary' else 'clean'
                result = study.run(37014,stage,'combined','slow',fault,'good',name,study.methods()[name])
                metrics = study.measured_metrics(result)
                expected_row = next(r for r in rows if tuple(r[k] for k in ('seed','stage','phys','plant','fault','calibration','method')) == (37014,stage,'combined','slow',fault,'good',name))
                for m in study.METRICS: close(metrics[m],expected_row[m])
    print('PASS: 2,048 records, exact grid/source hashes, startup partition, 24 paired intervals, selection/gates, 1,024 rc.4 matches and missing-calibration parity'+(' and four replays.' if replay else '.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--replay',action='store_true')
    validate(parser.parse_args().replay)
