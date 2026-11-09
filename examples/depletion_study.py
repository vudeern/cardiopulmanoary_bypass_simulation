"""rc.3 fixed development comparison; no tuning or confirmation seeds."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import itertools
import json
from pathlib import Path
from multiprocessing import get_context
import numpy as np
from perfusion_lab.depletion_simulation import simulate_depletion
from perfusion_lab.reachability_simulation import simulate_reachability
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from continuity_study import patient, write_csv
from integrity_study import PHYS, CALIBRATIONS, FAULTS as BASE_FAULTS
from simc_benchmark import digest, dumps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/depletion-development'
SEEDS = tuple(range(37000, 37032))
PLANTS = {'nominal': {}, 'slow': dict(actuator_tau=6.)}
FAULTS = {**BASE_FAULTS, 'outage': dict(dropout_prob=.25, outage_start=150., outage_end=480.)}
METRICS = ('deficit_auc', 'low_reservoir_s', 'empty_request_s', 'high_pressure_s',
           'minimum_reservoir', 'flow_variation', 'mean_flow',
           'protection_active_s', 'protection_unsupported_s')


def methods():
    catalog = json.loads((ROOT/'results/reachability-development/protocol.json').read_text())['methods']
    selected = json.loads((ROOT/'results/reachability-base-development/selection.json').read_text())
    assert selected['candidate'] == 'aggressive_consistent'
    candidate = json.loads(json.dumps(catalog['combined']))
    pi = catalog[selected['comparator']]
    candidate['options'].update(tau_c=pi['options']['tau_c'], target_level=.35)
    return {'rc2': candidate, 'protected': candidate, 'eligible_pi': pi}


def cells():
    for phys, plant in itertools.product(PHYS, PLANTS):
        for fault in ('clean', 'positive_start', 'step', 'outage'):
            yield 'primary', phys, plant, fault, 'good'
        for calibration in ('missing', 'biased', 'shared'):
            yield 'secondary', phys, plant, 'positive_start', calibration


def protocol():
    sources = sorted(str(p.relative_to(ROOT)) for p in (ROOT/'src/perfusion_lab').glob('*.py'))
    sources += ['examples/depletion_study.py', 'examples/continuity_study.py',
                'examples/integrity_study.py', 'examples/simc_benchmark.py',
                'results/reachability-development/protocol.json',
                'results/reachability-base-development/selection.json']
    value = dict(version='2.0.0rc3', stage='development_only', seeds=list(SEEDS),
        confirmation_seeds_executed=[], duration_s=600., dt_s=1., methods=methods(),
        cells=list(cells()), primary_runs=1536, secondary_runs=1152,
        selection='No selection or tuning. Compare one conservative mechanism with frozen rc2 and independently selected rc2 eligible PI. All methods use identical measurement channels and slew limits.',
        mechanism='Zero future venous return reserve over ALL configured pump models; maximum permitted braking without independent model/calibration support. Hybrid PI settings unchanged from rc2.',
        limitations='Same 32 development patients and reused scenario families. Shared absolute calibration bias and omitted pump dynamics can invalidate protection. No clinical or hardware validation. Stopping may be infeasible at initialization. Report all oxygen costs and individual failures; no v2 success claim.',
        source_hashes={p: digest(ROOT/p) for p in sources})
    path = OUT/'protocol.json'
    if path.exists():
        assert json.loads(path.read_text()) == json.loads(dumps(value)), 'Frozen protocol changed'
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(value))
    return value


def run(seed, phys, plant, fault, calibration, name, method):
    params = dict(PHYS[phys]); bias = params.pop('venous_bias', 0.)
    cal = dict(CALIBRATIONS[calibration])
    if calibration == 'shared':
        cal.update(FAULTS[fault])
    engine = simulate_depletion if name == 'protected' else simulate_reachability
    return engine(StressScenario(phys, **params), 'sentinel', seed=seed, duration=600., dt=1.,
        patient=patient(seed, 'evaluation'), controller_kind=method['kind'],
        controller_options=method['options'], reference_guard_options=method['guard'],
        plant_options=PLANTS[plant], venous_measurement=dict(noise_sd=.015, bias=bias),
        level_mode=method.get('mode', 'screened'),
        level_reference_options=dict(period=60., delay=4., noise_sd=.01),
        reference_fault_options=dict(FAULTS[fault]), calibration_options=cal)


def worker(seed):
    records = []
    for stage, phys, plant, fault, calibration in cells():
        for name, method in methods().items():
            result = run(seed, phys, plant, fault, calibration, name, method)
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
                for m in METRICS:
                    row[m] = float(row[m])
                rows.append(row)
    return rows


def summarize():
    rows = read_rows(); summary = {}
    for group in ('primary', 'clean', 'bias', 'outage', 'missing', 'biased', 'shared'):
        def belongs(r):
            if group == 'primary': return r['stage'] == 'primary'
            if group in ('missing', 'biased', 'shared'): return r['calibration'] == group
            return r['stage'] == 'primary' and (r['fault'] in ('positive_start', 'step') if group == 'bias' else r['fault'] == group)
        block = [r for r in rows if belongs(r)]
        summary[group] = {}
        for name in methods():
            selected = [r for r in block if r['method'] == name]
            summary[group][name] = dict(runs=len(selected),
                means={m: float(np.mean([r[m] for r in selected])) for m in METRICS},
                worst_minimum_L=min(r['minimum_reservoir'] for r in selected),
                floor_crossing_cases=sum(r['low_reservoir_s'] > 0 for r in selected),
                empty_cases=sum(r['empty_request_s'] > 0 for r in selected),
                worst_floor_exposure_s=max(r['low_reservoir_s'] for r in selected))
        summary[group]['paired_deficit_vs_pi'] = paired_interval([
            np.mean([r['deficit_auc'] for r in block if r['seed'] == seed and r['method'] == 'protected']) -
            np.mean([r['deficit_auc'] for r in block if r['seed'] == seed and r['method'] == 'eligible_pi']) for seed in SEEDS])
    result = dict(version='2.0.0rc3', patients=32, runs=len(rows), groups=summary,
        version2_ready=False, qualifying_confirmation_cohorts=0, confirmation_seeds_executed=[],
        protocol_sha256=digest(OUT/'protocol.json'))
    (OUT/'summary.json').write_text(dumps(result))
    print(dumps(summary['primary']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('run', 'summarize'), required=True)
    args = parser.parse_args(); protocol()
    if args.stage == 'run':
        pending = [s for s in SEEDS if not (OUT/f'{s}.csv').exists()]
        with ProcessPoolExecutor(max_workers=4, mp_context=get_context('spawn')) as pool:
            tasks = {pool.submit(worker, s): s for s in pending}
            for future in as_completed(tasks):
                seed = tasks[future]
                write_csv(OUT/f'{seed}.csv', future.result())
                print('depletion patient complete', seed, flush=True)
    summarize()
