"""Adaptive rc.5 pump-hypothesis follow-up; development data only."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import csv
import json
from multiprocessing import get_context
import numpy as np
import startup_study as first
from perfusion_candidates.calibrated_pump_simulation import simulate_calibrated_pump
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from continuity_study import patient, write_csv
from simc_benchmark import digest, dumps

ROOT = first.ROOT
OUT = ROOT/'results/calibrated-pump-development'
SEEDS = first.SEEDS
METRICS = first.METRICS
NAMES = ('retained_two_anchor','retained_single_anchor')


def methods():
    method = first.methods()['rc4']; result = {}
    for name, count in zip(NAMES,(2,1)):
        config = deepcopy(method); config['guard']['startup_minimum_anchors'] = count
        result[name] = config
    return result


def protocol():
    sources = list(json.loads((first.OUT/'protocol.json').read_text())['source_hashes'])
    sources += ['src/perfusion_candidates/calibrated_pump.py','src/perfusion_candidates/calibrated_pump_simulation.py',
        'examples/calibrated_pump_study.py','results/startup-development/protocol.json','results/startup-development/summary.json']
    value = dict(version='2.0.0rc5', stage='adaptive_development_followup', seeds=list(SEEDS), confirmation_seeds_executed=[],
        methods=methods(), cells=list(first.previous.cells()), duration_s=600., dt_s=1., primary_runs=1024, secondary_runs=768, abrupt_stop_runs=256,
        rationale='Designed after inspection of first-stage development results (including partial outcomes before completion) and two illustrative retained-model replays. Earlier support alone scarcely changes delivery; the full-grid reserve remains binding. Freeze both follow-up settings before any follow-up outcomes. Same patients reused, never confirmation.',
        mechanism='Use only calibration-consistent pump hypotheses for the existing 15-second finite-return reserve. Keep observer allowances, controller gains, limits and measurement channels fixed. Cross with one/two-anchor support to complete a 2x2 mechanism comparison. Protection now relies on calibration/model-set retention; discarding the real response can invalidate reserve. Missing/conflicting support still brakes.',
        selection='Across four mechanism arms from both stages, require zero floor crossings and empty requests in primary AND abrupt-stop grids, then lowest primary mean deficit. rc4 is retained as an eligible reference; report no replacement if it wins. No calibration-failure-based selection. All candidates/failures retained. Archived rc4 PI remains the fixed project-gate comparator; retuning remains required before a freeze.',
        limitations='Adaptive design and selection reuse the same 32 development patients and known scenarios. No universal protection, shared-bias identifiability, clinical/hardware validation or independent confirmation is established.',
        source_hashes={p:digest(ROOT/p) for p in sources})
    path = OUT/'protocol.json'
    if path.exists(): assert json.loads(path.read_text()) == json.loads(dumps(value)), 'Frozen follow-up protocol changed'
    else: OUT.mkdir(parents=True,exist_ok=True); path.write_text(dumps(value))
    return value


def run(seed,stage,phys,plant,fault,calibration,name,method):
    params = dict(first.previous.previous.PHYS[phys]); bias = params.pop('venous_bias',0.)
    if stage == 'abrupt_stop': params.update(drainage=0.,event_start=.28,event_end=.355)
    cal = dict(first.previous.previous.CALIBRATIONS[calibration])
    if calibration == 'shared': cal.update(first.previous.previous.FAULTS[fault])
    return simulate_calibrated_pump(StressScenario(phys,**params),'sentinel',seed=seed,duration=600.,dt=1.,
        patient=patient(seed,'evaluation'),controller_kind=method['kind'],controller_options=method['options'],
        reference_guard_options=method['guard'],plant_options=first.previous.previous.PLANTS[plant],
        venous_measurement=dict(noise_sd=.015,bias=bias),level_mode=method.get('mode','screened'),
        level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),
        reference_fault_options=dict(first.previous.previous.FAULTS[fault]),calibration_options=cal)


def worker(seed):
    rows = []
    for stage,phys,plant,fault,cal in first.previous.cells():
        for name,method in methods().items():
            result = run(seed,stage,phys,plant,fault,cal,name,method)
            rows.append(dict(seed=seed,stage=stage,phys=phys,plant=plant,fault=fault,calibration=cal,method=name,**first.measured_metrics(result)))
    return rows


def read_rows():
    rows = first.read_rows()
    for seed in SEEDS:
        with (OUT/f'{seed}.csv').open() as handle:
            for row in csv.DictReader(handle):
                row['seed'] = int(row['seed'])
                for m in METRICS: row[m] = float(row[m])
                rows.append(row)
    return rows


def summarize():
    protocol(); rows = read_rows(); names = ('rc4','single_anchor')+NAMES
    archived = [r for r in first.previous.read_rows() if r['method'] == 'eligible_pi' and r['stage'] == 'primary']
    groups = {}
    for group in ('primary','clean','bias','outage','missing','biased','shared','abrupt_stop'):
        groups[group] = {name:first.aggregate([r for r in rows if r['method'] == name and first.previous.belongs(r,group)],METRICS) for name in names}
        if group in ('primary','clean','bias','outage'):
            groups[group]['archived_pi'] = first.aggregate([r for r in archived if first.previous.belongs(r,group)],first.previous.METRICS)
    eligible = [n for n in names if all(groups[g][n]['floor_crossing_cases'] == groups[g][n]['empty_cases'] == 0 for g in ('primary','abrupt_stop'))]
    winner = min(eligible,key=lambda n:groups['primary'][n]['means']['deficit_auc']) if eligible else None
    selected = winner if winner != 'rc4' else None
    comparisons = []
    for name in ('single_anchor',)+NAMES:
        for baseline in ('rc4','archived_pi'):
            for group in ('clean','bias','outage'):
                for metric in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s'):
                    differences = []
                    for seed in SEEDS:
                        a = [r for r in rows if r['seed'] == seed and r['method'] == name and first.previous.belongs(r,group)]
                        source = archived if baseline == 'archived_pi' else [r for r in rows if r['method'] == 'rc4']
                        b = [r for r in source if r['seed'] == seed and first.previous.belongs(r,group)]
                        differences.append(np.mean([r[metric] for r in a])-np.mean([r[metric] for r in b]))
                    comparisons.append(dict(candidate=name,baseline=baseline,group=group,metric=metric,**paired_interval(differences)))
    gates = {}
    if selected:
        for g in ('clean','bias','outage'):
            a = groups[g][selected]; b = groups[g]['archived_pi']
            intervals = {r['metric']:r for r in comparisons if r['candidate'] == selected and r['baseline'] == 'archived_pi' and r['group'] == g}
            gates[g] = dict(oxygen_mean_10_percent=a['means']['deficit_auc'] <= .9*b['means']['deficit_auc'],oxygen_paired_interval=intervals['deficit_auc']['high'] < 0,
                mean_low_reservoir=a['means']['low_reservoir_s'] <= 1.,zero_empty_requests=a['empty_cases'] == 0,
                extra_low_reservoir=intervals['low_reservoir_s']['high'] <= 1.,extra_empty_requests=intervals['empty_request_s']['high'] <= 1.,extra_high_pressure=intervals['high_pressure_s']['high'] <= 5.)
    result = dict(version='2.0.0rc5',patients=32,runs=len(rows),new_runs_this_stage=2048,groups=groups,
        eligible_candidates=eligible,selected_candidate=selected,comparisons=comparisons,development_gates=gates,
        development_joint_success=bool(selected and all(all(v.values()) for v in gates.values())),
        version2_ready=False,qualifying_confirmation_cohorts=0,confirmation_seeds_executed=[],
        protocol_sha256=digest(OUT/'protocol.json'),first_stage_summary_sha256=digest(first.OUT/'summary.json'))
    (OUT/'summary.json').write_text(dumps(result))
    print(dumps(dict(selected=selected,primary=groups['primary'],abrupt_stop=groups['abrupt_stop'])),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('run','summarize'),required=True)
    args = parser.parse_args();protocol()
    if args.stage == 'run':
        pending = [s for s in SEEDS if not (OUT/f'{s}.csv').exists()]
        with ProcessPoolExecutor(max_workers=4,mp_context=get_context('spawn')) as pool:
            tasks = {pool.submit(worker,s):s for s in pending}
            for future in as_completed(tasks):
                seed=tasks[future];write_csv(OUT/f'{seed}.csv',future.result());print('calibrated-pump patient complete',seed,flush=True)
    summarize()
