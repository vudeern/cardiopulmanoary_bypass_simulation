"""rc.5 controlled single-anchor startup experiment on development data only."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import csv
import json
from multiprocessing import get_context
import numpy as np
import finite_return_study as previous
from perfusion_candidates.startup_simulation import simulate_startup
from perfusion_candidates.simulation import simulate_finite_return
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from continuity_study import patient, write_csv
from simc_benchmark import digest, dumps

ROOT = previous.ROOT
OUT = ROOT/'results/startup-development'
SEEDS = previous.SEEDS
EXTRA = ('startup_deficit_auc', 'later_deficit_auc', 'startup_unsupported_s',
         'single_anchor_supported_s', 'lower_undercoverage_s')
METRICS = previous.METRICS+EXTRA


def methods():
    method = deepcopy(previous.methods()['credit_15'])
    early = deepcopy(method); early['guard']['startup_minimum_anchors'] = 1
    return {'single_anchor': early, 'rc4': method}


def protocol():
    sources = list(json.loads((previous.OUT/'protocol.json').read_text())['source_hashes'])
    sources += ['src/perfusion_candidates/startup.py', 'src/perfusion_candidates/startup_simulation.py',
                'examples/startup_study.py', 'results/finite-return-development/protocol.json',
                'results/finite-return-development/summary.json']
    value = dict(version='2.0.0rc5', stage='development_only', seeds=list(SEEDS),
        confirmation_seeds_executed=[], methods=methods(), cells=list(previous.cells()),
        duration_s=600., dt_s=1., primary_runs=1024, secondary_runs=768, abrupt_stop_runs=256,
        startup_cutoff_s=126.,
        mechanism='One delivered independent anchor initializes the same feasible offset/venous-bias set. Preserve full +/-2 L/min bias prior, .04 L calibration allowance, .03 L/min model-error growth, all five stopping hypotheses, .5 return credit for 15s, controller gains, limits and fallback. Missing/stale/conflicting support still brakes. No new measurement or future truth is supplied.',
        selection='One fixed candidate, no tuning: qualify only with zero floor crossings and empty requests in primary AND abrupt-stop grids, and lower primary mean oxygen deficit than rc4. Otherwise report no selected candidate. Secondary cases never select. Paired patient intervals remain exploratory. Archived eligible PI primary records from rc4 supply the unchanged project-gate comparison; no new PI tuning or confirmation.',
        limitations='Development-only reuse of the same 32 virtual patients, scenarios and abrupt-stop event. Bounded calibration error, constant venous bias and retained dynamics are engineering assumptions, not established confidence coverage or safety guarantees. Unknown shared absolute bias remains unidentifiable. No hardware/clinical validation.',
        metrics=list(METRICS), source_hashes={p: digest(ROOT/p) for p in sources})
    path = OUT/'protocol.json'
    if path.exists(): assert json.loads(path.read_text()) == json.loads(dumps(value)), 'Frozen startup protocol changed'
    else: OUT.mkdir(parents=True, exist_ok=True); path.write_text(dumps(value))
    return value


def run(seed, stage, phys, plant, fault, calibration, name, method):
    params = dict(previous.previous.PHYS[phys]); bias = params.pop('venous_bias', 0.)
    if stage == 'abrupt_stop': params.update(drainage=0., event_start=.28, event_end=.355)
    cal = dict(previous.previous.CALIBRATIONS[calibration])
    if calibration == 'shared': cal.update(previous.previous.FAULTS[fault])
    engine = simulate_startup if name == 'single_anchor' else simulate_finite_return
    return engine(StressScenario(phys, **params), 'sentinel', seed=seed, duration=600., dt=1.,
        patient=patient(seed, 'evaluation'), controller_kind=method['kind'],
        controller_options=method['options'], reference_guard_options=method['guard'],
        plant_options=previous.previous.PLANTS[plant], venous_measurement=dict(noise_sd=.015, bias=bias),
        level_mode=method.get('mode', 'screened'),
        level_reference_options=dict(period=60., delay=4., noise_sd=.01),
        reference_fault_options=dict(previous.previous.FAULTS[fault]), calibration_options=cal)


def measured_metrics(result):
    rows = result['rows']; metrics = dict(result['metrics'])
    for key in ('protection_active', 'protection_unsupported'):
        metrics[key+'_s'] = sum(r.get(key, False) for r in rows)
    metrics['startup_deficit_auc'] = sum(max(0., 280.-r['do2']) for r in rows if r['observation_time'] < 126.)/60.
    metrics['later_deficit_auc'] = sum(max(0., 280.-r['do2']) for r in rows if r['observation_time'] >= 126.)/60.
    metrics['startup_unsupported_s'] = sum(r['protection_unsupported'] for r in rows if r['observation_time'] < 126.)
    metrics['single_anchor_supported_s'] = sum(r['bank_supported'] and r['calibration_count'] == 1 for r in rows)
    truth = .85; under = 0
    for row in rows:
        under += row['level_reference_lower'] > truth+1e-9
        truth = row['reservoir']
    metrics['lower_undercoverage_s'] = under
    return {m: metrics[m] for m in METRICS}


def worker(seed):
    records = []
    for stage, phys, plant, fault, cal in previous.cells():
        for name, method in methods().items():
            result = run(seed, stage, phys, plant, fault, cal, name, method)
            records.append(dict(seed=seed, stage=stage, phys=phys, plant=plant,
                fault=fault, calibration=cal, method=name, **measured_metrics(result)))
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


def aggregate(block, metrics):
    return dict(runs=len(block), means={m: float(np.mean([r[m] for r in block])) for m in metrics},
        floor_crossing_cases=sum(r['low_reservoir_s'] > 0 for r in block),
        empty_cases=sum(r['empty_request_s'] > 0 for r in block),
        worst_minimum_L=min(r['minimum_reservoir'] for r in block),
        worst_floor_exposure_s=max(r['low_reservoir_s'] for r in block))


def summarize():
    protocol(); rows = read_rows(); archived = [r for r in previous.read_rows() if r['method'] == 'eligible_pi' and r['stage'] == 'primary']
    groups = {}
    for group in ('primary', 'clean', 'bias', 'outage', 'missing', 'biased', 'shared', 'abrupt_stop'):
        groups[group] = {name: aggregate([r for r in rows if previous.belongs(r, group) and r['method'] == name], METRICS) for name in methods()}
        if group in ('primary', 'clean', 'bias', 'outage'):
            groups[group]['archived_pi'] = aggregate([r for r in archived if previous.belongs(r, group)], previous.METRICS)
    comparisons = []
    for baseline in ('rc4', 'archived_pi'):
        for group in ('clean', 'bias', 'outage'):
            for metric in ('deficit_auc', 'low_reservoir_s', 'empty_request_s', 'high_pressure_s'):
                differences = []
                for seed in SEEDS:
                    block = [r for r in rows if r['seed'] == seed and previous.belongs(r, group)]
                    a = np.mean([r[metric] for r in block if r['method'] == 'single_anchor'])
                    reference = block if baseline == 'rc4' else [r for r in archived if r['seed'] == seed and previous.belongs(r, group)]
                    b = np.mean([r[metric] for r in reference if baseline != 'rc4' or r['method'] == 'rc4'])
                    differences.append(a-b)
                comparisons.append(dict(baseline=baseline, group=group, metric=metric, **paired_interval(differences)))
    protected = all(groups[g]['single_anchor']['floor_crossing_cases'] == groups[g]['single_anchor']['empty_cases'] == 0 for g in ('primary', 'abrupt_stop'))
    selected = 'single_anchor' if protected and groups['primary']['single_anchor']['means']['deficit_auc'] < groups['primary']['rc4']['means']['deficit_auc'] else None
    gates = {}
    for g in ('clean', 'bias', 'outage'):
        a = groups[g]['single_anchor']; b = groups[g]['archived_pi']
        intervals = {r['metric']:r for r in comparisons if r['baseline'] == 'archived_pi' and r['group'] == g}
        gates[g] = dict(oxygen_mean_10_percent=a['means']['deficit_auc'] <= .9*b['means']['deficit_auc'],
            oxygen_paired_interval=intervals['deficit_auc']['high'] < 0,
            mean_low_reservoir=a['means']['low_reservoir_s'] <= 1., zero_empty_requests=a['empty_cases'] == 0,
            extra_low_reservoir=intervals['low_reservoir_s']['high'] <= 1., extra_empty_requests=intervals['empty_request_s']['high'] <= 1., extra_high_pressure=intervals['high_pressure_s']['high'] <= 5.)
    summary = dict(version='2.0.0rc5', patients=32, runs=len(rows), groups=groups, comparisons=comparisons,
        selected_candidate=selected, development_gates=gates, development_joint_success=bool(selected and all(all(v.values()) for v in gates.values())),
        version2_ready=False, qualifying_confirmation_cohorts=0, confirmation_seeds_executed=[],
        archived_pi_runs=512, archived_pi_protocol_sha256=digest(previous.OUT/'protocol.json'), protocol_sha256=digest(OUT/'protocol.json'))
    (OUT/'summary.json').write_text(dumps(summary))
    print(dumps({k:summary[k] for k in ('selected_candidate','development_joint_success')}), flush=True)
    print(dumps(dict(primary=groups['primary'], abrupt_stop=groups['abrupt_stop'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--stage', choices=('run','summarize'), required=True)
    args = parser.parse_args(); protocol()
    if args.stage == 'run':
        pending = [seed for seed in SEEDS if not (OUT/f'{seed}.csv').exists()]
        with ProcessPoolExecutor(max_workers=4, mp_context=get_context('spawn')) as pool:
            tasks = {pool.submit(worker, seed):seed for seed in pending}
            for future in as_completed(tasks):
                seed = tasks[future]; write_csv(OUT/f'{seed}.csv', future.result()); print('startup patient complete',seed,flush=True)
    summarize()
