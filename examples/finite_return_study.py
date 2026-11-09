"""rc.4 finite-return development experiment; fixed before any outcome runs."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import csv
import json
from multiprocessing import get_context
from pathlib import Path
import numpy as np
from perfusion_candidates.simulation import simulate_finite_return
from perfusion_lab.depletion_simulation import simulate_depletion
from perfusion_lab.reachability_simulation import simulate_reachability
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
import depletion_study as previous
from continuity_study import patient, write_csv
from simc_benchmark import digest, dumps

ROOT = previous.ROOT
OUT = ROOT/'results/finite-return-development'
SEEDS = previous.SEEDS
METRICS = previous.METRICS
CANDIDATES = ('credit_15', 'credit_30', 'credit_60')


def methods():
    frozen = previous.methods()
    result = {name: deepcopy(frozen['protected']) for name in CANDIDATES}
    for name, horizon in zip(CANDIDATES, (15., 30., 60.)):
        result[name]['options'].update(return_fraction=.5, return_horizon_s=horizon)
    result.update(zero_return=frozen['protected'], rc2=frozen['rc2'], eligible_pi=frozen['eligible_pi'])
    return result


def cells():
    yield from previous.cells()
    for phys in previous.PHYS:
        for plant in previous.PLANTS:
            yield 'abrupt_stop', phys, plant, 'clean', 'good'


def protocol():
    # Explicit source scope preserves every earlier frozen protocol when new
    # candidate packages are added in later iterations.
    sources = list(json.loads((previous.OUT/'protocol.json').read_text())['source_hashes'])
    sources += ['src/perfusion_candidates/__init__.py', 'src/perfusion_candidates/finite_return.py',
                'src/perfusion_candidates/simulation.py', 'examples/finite_return_study.py',
                'results/depletion-development/summary.json']
    value = dict(version='2.0.0rc4', stage='development_only', seeds=list(SEEDS),
        confirmation_seeds_executed=[], methods=methods(), cells=list(cells()),
        duration_s=600., dt_s=1., primary_runs=3072, secondary_runs=2304, abrupt_stop_runs=768,
        assumption='Future venous return is at least half of max(0, current measured venous flow minus observer bias upper bound minus fixed flow allowance) for 15/30/60 whole seconds, then zero forever. This is a testable engineering assumption, not a known fact or a prediction. Same all-model stopping bank and unsupported-calibration braking as rc3.',
        selection='No adaptive tuning. Among three candidates require zero floor-crossing and empty-request cases in primary AND abrupt-stop grids, then minimize primary mean deficit. If none qualify, report no selected candidate. Existing independently tuned eligible PI remains fixed; new comparator tuning is deferred until a candidate is ready to freeze. No secondary-based selection.',
        abrupt_stop='Additional assumption-violation challenge, not primary confirmation: drainage factor zero abruptly from t=168 to 213s in both physiology and plant families. Controller receives causal current measurements only, never future event timing. All challenge failures retained.',
        limitations='Same 32 development patients, known synthetic distributions and scenario families. Shared absolute calibration bias is unidentifiable and pump dynamics outside the grid can invalidate reserve. No clinical/hardware validation, safety guarantee or final superiority claim.',
        source_hashes={p: digest(ROOT/p) for p in sources})
    path = OUT/'protocol.json'
    if path.exists():
        assert json.loads(path.read_text()) == json.loads(dumps(value)), 'Frozen protocol changed'
    else:
        OUT.mkdir(parents=True, exist_ok=True); path.write_text(dumps(value))
    return value


def run(seed, stage, phys, plant, fault, calibration, name, method):
    params = dict(previous.PHYS[phys]); bias = params.pop('venous_bias', 0.)
    if stage == 'abrupt_stop':
        params.update(drainage=0., event_start=.28, event_end=.355)
    cal = dict(previous.CALIBRATIONS[calibration])
    if calibration == 'shared': cal.update(previous.FAULTS[fault])
    engine = simulate_finite_return if name in CANDIDATES else simulate_depletion if name == 'zero_return' else simulate_reachability
    return engine(StressScenario(phys, **params), 'sentinel', seed=seed, duration=600., dt=1.,
        patient=patient(seed, 'evaluation'), controller_kind=method['kind'],
        controller_options=method['options'], reference_guard_options=method['guard'],
        plant_options=previous.PLANTS[plant], venous_measurement=dict(noise_sd=.015, bias=bias),
        level_mode=method.get('mode', 'screened'),
        level_reference_options=dict(period=60., delay=4., noise_sd=.01),
        reference_fault_options=dict(previous.FAULTS[fault]), calibration_options=cal)


def worker(seed):
    records = []
    for stage, phys, plant, fault, calibration in cells():
        for name, method in methods().items():
            result = run(seed, stage, phys, plant, fault, calibration, name, method)
            metrics = result['metrics']
            for key in ('protection_active', 'protection_unsupported'):
                metrics[key+'_s'] = sum(r.get(key, False) for r in result['rows'])
            records.append(dict(seed=seed, stage=stage, phys=phys, plant=plant,
                fault=fault, calibration=calibration, method=name,
                **{m: metrics[m] for m in METRICS}))
    return records


def read_rows():
    rows = []
    for seed in SEEDS:
        with (OUT/f'{seed}.csv').open() as stream:
            for row in csv.DictReader(stream):
                row['seed'] = int(row['seed'])
                for m in METRICS: row[m] = float(row[m])
                rows.append(row)
    return rows


def belongs(row, group):
    if group in ('primary', 'abrupt_stop'): return row['stage'] == group
    if group in ('missing', 'biased', 'shared'): return row['calibration'] == group
    return row['stage'] == 'primary' and (row['fault'] in ('positive_start', 'step') if group == 'bias' else row['fault'] == group)


def summarize():
    protocol(); rows = read_rows(); groups = {}
    for group in ('primary', 'clean', 'bias', 'outage', 'missing', 'biased', 'shared', 'abrupt_stop'):
        block = [r for r in rows if belongs(r, group)]; stats = {}
        for name in methods():
            selected = [r for r in block if r['method'] == name]
            stats[name] = dict(runs=len(selected), means={m: float(np.mean([r[m] for r in selected])) for m in METRICS},
                worst_minimum_L=min(r['minimum_reservoir'] for r in selected),
                floor_crossing_cases=sum(r['low_reservoir_s'] > 0 for r in selected),
                empty_cases=sum(r['empty_request_s'] > 0 for r in selected),
                worst_floor_exposure_s=max(r['low_reservoir_s'] for r in selected))
        groups[group] = stats
    eligible = [name for name in CANDIDATES if all(groups[g][name]['floor_crossing_cases'] == groups[g][name]['empty_cases'] == 0 for g in ('primary', 'abrupt_stop'))]
    selected = min(eligible, key=lambda n: groups['primary'][n]['means']['deficit_auc']) if eligible else None
    paired = []
    for name in CANDIDATES:
        for baseline in ('zero_return', 'eligible_pi'):
            for group in ('clean', 'bias', 'outage'):
                for metric in ('deficit_auc', 'low_reservoir_s', 'empty_request_s', 'high_pressure_s'):
                    differences = []
                    for seed in SEEDS:
                        block = [r for r in rows if r['seed'] == seed and belongs(r, group)]
                        differences.append(np.mean([r[metric] for r in block if r['method'] == name])-np.mean([r[metric] for r in block if r['method'] == baseline]))
                    paired.append(dict(candidate=name, baseline=baseline, group=group, metric=metric, **paired_interval(differences)))
    gates = {}
    if selected:
        for g in ('clean', 'bias', 'outage'):
            a = groups[g][selected]; b = groups[g]['eligible_pi']
            interval = {r['metric']: r for r in paired if r['candidate'] == selected and r['baseline'] == 'eligible_pi' and r['group'] == g}
            gates[g] = dict(oxygen_mean_10_percent=a['means']['deficit_auc'] <= .9*b['means']['deficit_auc'],
                oxygen_paired_interval=interval['deficit_auc']['high'] < 0,
                mean_low_reservoir=a['means']['low_reservoir_s'] <= 1., zero_empty_requests=a['empty_cases'] == 0,
                extra_low_reservoir=interval['low_reservoir_s']['high'] <= 1., extra_empty_requests=interval['empty_request_s']['high'] <= 1.,
                extra_high_pressure=interval['high_pressure_s']['high'] <= 5.)
    summary = dict(version='2.0.0rc4', patients=32, runs=len(rows), groups=groups, eligible_candidates=eligible,
        selected_candidate=selected, comparisons=paired, development_gates=gates,
        development_joint_success=bool(selected and all(all(v.values()) for v in gates.values())),
        version2_ready=False, qualifying_confirmation_cohorts=0, confirmation_seeds_executed=[],
        protocol_sha256=digest(OUT/'protocol.json'))
    (OUT/'summary.json').write_text(dumps(summary))
    print(dumps(dict(selected=selected, primary=groups['primary'], abrupt_stop=groups['abrupt_stop'], development_gates=gates)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--stage', choices=('run', 'summarize'), required=True)
    args = parser.parse_args(); protocol()
    if args.stage == 'run':
        with ProcessPoolExecutor(max_workers=4, mp_context=get_context('spawn')) as pool:
            pending = [seed for seed in SEEDS if not (OUT/f'{seed}.csv').exists()]
            tasks = {pool.submit(worker, seed): seed for seed in pending}
            for future in as_completed(tasks):
                seed = tasks[future]; write_csv(OUT/f'{seed}.csv', future.result())
                print('finite return patient complete', seed, flush=True)
    summarize()
