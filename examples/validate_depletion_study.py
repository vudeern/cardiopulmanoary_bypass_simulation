"""Independent grid, source, aggregate and frozen-baseline checks for rc.3."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import depletion_study as study

ROOT = study.ROOT; OUT = study.OUT


def validate(replay=False):
    protocol = json.loads(study.dumps(study.protocol()))
    summary = json.loads((OUT/'summary.json').read_text())
    assert summary['runs'] == 2688 and summary['patients'] == 32
    assert not summary['version2_ready'] and summary['qualifying_confirmation_cohorts'] == 0
    assert summary['confirmation_seeds_executed'] == []
    assert summary['protocol_sha256'] == study.digest(OUT/'protocol.json')
    rows = study.read_rows()
    expected = {(seed, *cell, name) for seed in study.SEEDS for cell in study.cells() for name in study.methods()}
    actual = [(r['seed'], r['stage'], r['phys'], r['plant'], r['fault'], r['calibration'], r['method']) for r in rows]
    assert len(actual) == len(set(actual)) == len(expected) and set(actual) == expected
    for row in rows:
        for metric in study.METRICS:
            assert math.isfinite(row[metric]) and row[metric] >= 0, (row, metric)
        for metric in ('low_reservoir_s', 'empty_request_s', 'high_pressure_s', 'protection_active_s', 'protection_unsupported_s'):
            assert row[metric] <= 600
    for group, stats in summary['groups'].items():
        def belongs(r):
            if group == 'primary': return r['stage'] == 'primary'
            if group in ('missing', 'biased', 'shared'): return r['calibration'] == group
            return r['stage'] == 'primary' and (r['fault'] in ('positive_start', 'step') if group == 'bias' else r['fault'] == group)
        for name in study.methods():
            selected = [r for r in rows if belongs(r) and r['method'] == name]
            reported = stats[name]
            assert len(selected) == reported['runs']
            for metric in study.METRICS:
                assert abs(np.mean([r[metric] for r in selected])-reported['means'][metric]) < 1e-9
            assert min(r['minimum_reservoir'] for r in selected) == reported['worst_minimum_L']
            assert sum(r['low_reservoir_s'] > 0 for r in selected) == reported['floor_crossing_cases']
            assert sum(r['empty_request_s'] > 0 for r in selected) == reported['empty_cases']
            assert max(r['low_reservoir_s'] for r in selected) == reported['worst_floor_exposure_s']
    # Validate the local retrieval correction, including exact reconstruction of
    # each execution source. Every changed source differs by one final newline.
    correction = json.loads((OUT/'retrieval-normalization.json').read_text())
    executed = json.loads((OUT/'execution-protocol.json').read_text())
    assert {k:v for k,v in executed.items() if k != 'source_hashes'} == {k:v for k,v in protocol.items() if k != 'source_hashes'}
    for path, current_hash in protocol['source_hashes'].items():
        content = (ROOT/path).read_bytes()
        assert hashlib.sha256(content).hexdigest() == current_hash
        if path in correction['changes']:
            change = correction['changes'][path]
            assert change['python_ast_unchanged']
            assert current_hash == change['canonical_sha256']
            assert hashlib.sha256(content+b'\n').hexdigest() == executed['source_hashes'][path] == change['execution_sha256']
        else:
            assert executed['source_hashes'][path] == current_hash
    # All 1,024 repeated primary reference runs match published rc.2 numerics.
    historical = {}
    for directory, method in (('reachability-base-development', 'aggressive_consistent'),
                              ('reachability-development', 'pi_legacy_5.0_0.5')):
        for seed in study.SEEDS:
            with (ROOT/'results'/directory/'primary'/f'{seed}.csv').open() as stream:
                for r in csv.DictReader(stream):
                    if r['method'] == method:
                        historical[(int(r['seed']), r['phys'], r['plant'], r['fault'], method)] = r
    for r in rows:
        if r['stage'] != 'primary' or r['method'] == 'protected': continue
        old_name = 'aggressive_consistent' if r['method'] == 'rc2' else 'pi_legacy_5.0_0.5'
        old = historical[(r['seed'], r['phys'], r['plant'], r['fault'], old_name)]
        for metric in study.METRICS[:7]:
            assert abs(float(old[metric])-r[metric]) < 1e-9
    adapter = (ROOT/'src/perfusion_lab/reachability_simulation.py').read_text()
    expected_adapter = adapter.replace('Development simulation adapter for the calibration-set/joint-reserve runtime.',
        'Conservative depletion simulation; timing and metrics mirror the rc.2 adapter.').replace(
        'def simulate_reachability(', 'def simulate_depletion(').replace(
        'from .reachability_runtime import ReachabilityRuntime as ControllerRuntime',
        'from .depletion import DepletionRuntime as ControllerRuntime')
    assert expected_adapter.rstrip() == (ROOT/'src/perfusion_lab/depletion_simulation.py').read_text().rstrip()
    if replay:
        for name, method in study.methods().items():
            result = study.run(37014, 'combined', 'slow', 'positive_start', 'good', name, method)
            row = next(r for r in rows if r['seed'] == 37014 and r['phys'] == 'combined' and r['plant'] == 'slow' and r['fault'] == 'positive_start' and r['calibration'] == 'good' and r['method'] == name)
            for metric in study.METRICS[:7]:
                assert abs(result['metrics'][metric]-row[metric]) < 1e-9
    print('PASS: 2,688 records; exact grid, aggregates, source hashes, 1,024 frozen baseline matches'+('; three worst-case replays.' if replay else '.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', action='store_true')
    validate(parser.parse_args().replay)
