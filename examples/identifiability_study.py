"""Frozen-input local information audit on development patients only."""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
import calibrated_pump_study as baseline
from continuity_study import patient
from perfusion_research.identifiability import (
    PARAMETERS, SCALES, MODES, trajectory, sensitivity, diagnose)
from perfusion_lab.stress import StressScenario

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/identifiability-development'
SEEDS = tuple(range(37000, 37032))
CUTOFFS = (5., 30., 126., 599.)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def protocol():
    paths = set(json.loads((baseline.OUT/'protocol.json').read_text())['source_hashes'])
    paths.update(('src/perfusion_research/identifiability.py', 'src/perfusion_research/__init__.py', 'examples/identifiability_study.py',
                  'examples/calibrated_pump_study.py', 'data/version2-gates.json'))
    value = dict(stage='local_identifiability_development', seeds=list(SEEDS),
        confirmation_seeds_executed=[], baseline_commit='c92c7f2fe84bc00b7d81f283ee916a76f72bf347',
        physiology=['clean', 'combined'], plants=['nominal', 'slow'],
        baseline_method=baseline.methods()['retained_single_anchor'],
        baseline_reference_fault='clean', baseline_calibration='good',
        duration_s=600., dt_s=1., cutoffs_s=CUTOFFS, modes=MODES,
        parameters=PARAMETERS, scales=SCALES.tolist(), central_difference_steps=[1e-3, 5e-4],
        baseline_runs=128, forward_replays_per_case=31,
        input_contract='Commands from the released rc.5 measured controller, frozen across parameter perturbations and information masks. No artificial probe, controller update or confirmation execution.',
        information_contract='Expected measurement means for flow, venous flow, pressure, inline level and delayed references; whiten by configured sensor SD. Healthy routine/calibration offsets are fixed known zero. Missing calibration allows unknown common offset on remaining level channels. Shared-unknown allows common offset on all level channels. Outage removes routine acquisitions in [150,480), healthy calibration retained. No extra random reference dropouts in these local schedule ablations.',
        interpretation='Local numerical rank only; no structural-identifiability verdict from SVD, covariance guarantee, parameter fitting, performance improvement or safety certification. All other patient parameters and disturbance profiles fixed known: an optimistic information diagnostic. Independent-noise estimator validation is a later step.',
        source_hashes={p:digest(ROOT/p) for p in sorted(paths)})
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT/'protocol.json'
    if path.exists():
        assert json.loads(path.read_text()) == json.loads(json.dumps(value)), 'Protocol changed'
    else:
        save(path, value)
    return value


def run_case(seed, phys, plant_name):
    if seed not in SEEDS:
        raise ValueError('Only locked development seeds are permitted')
    p = patient(seed, 'evaluation')
    source = baseline.first.previous.previous
    params = dict(source.PHYS[phys])
    venous_bias = params.pop('venous_bias', 0.)
    scenario = StressScenario(phys, **params)
    tau = source.PLANTS[plant_name].get('actuator_tau', 2.)
    run = baseline.run(seed, 'primary', phys, plant_name, 'clean', 'good',
                       'retained_single_anchor', baseline.methods()['retained_single_anchor'])
    commands = np.array([r['command'] for r in run['rows']])
    records, jac = sensitivity(p, scenario, commands, tau=tau, venous_bias=venous_bias)
    _, half = sensitivity(p, scenario, commands, tau=tau, epsilon=5e-4, venous_bias=venous_bias)
    # Exact state-storage-offset gauge, where transfer clipping is inactive.
    shift = np.zeros(7)
    shift[0], shift[4], shift[5] = .02, -.02, -.02
    shifted = trajectory(p, scenario, commands, tau=tau, delta=shift, venous_bias=venous_bias)
    gauge_error = max(abs(a[3]-b[3]) for a, b in zip(records, shifted))
    # Replay parity checks the same start/end alignment as the controller harness.
    inline = [r[3] for r in records if r[2] == 'inline']
    expected = [.85]+[r['reservoir'] for r in run['rows'][:-1]]
    parity = max(abs(y-v-scenario.inputs(k,600.)['reservoir_bias'])
                 for k, (y,v) in enumerate(zip(inline, expected)))
    assert parity < 1e-10, 'Offline replay changed plant/timing'
    results = [diagnose(records, jac, mode, cutoff) for mode in MODES for cutoff in CUTOFFS]
    for r in results:
        check = diagnose(records, half, r['mode'], r['cutoff_s'])
        r['half_step_rank'] = check['numerical_rank']
    path = OUT/f'{seed}-{phys}-{plant_name}.json'
    save(path, dict(seed=seed, physiology=phys, plant=plant_name, patient=asdict(p),
        actuator_tau_s=tau, known_scripted_venous_bias=venous_bias,
        replay_parity_max_error=parity, gauge_max_measurement_error=gauge_error,
        relative_jacobian_half_step_change=float(np.linalg.norm(jac-half)/max(np.linalg.norm(half),1e-30)),
        baseline_metrics=run['metrics'], analyses=results))
    with (OUT/f'{seed}-{phys}-{plant_name}-commands.csv').open('w', newline='') as f:
        writer=csv.writer(f, lineterminator='\n');writer.writerow(('time_s','command_L_min'))
        writer.writerows(enumerate(commands.tolist()))


def summarize():
    records = [json.loads((OUT/f'{s}-{p}-{m}.json').read_text())
               for s in SEEDS for p in ('clean','combined') for m in ('nominal','slow')]
    groups = []
    for mode in MODES:
        for cutoff in CUTOFFS:
            rows = [r for case in records for r in case['analyses']
                    if r['mode'] == mode and r['cutoff_s'] == cutoff]
            groups.append(dict(mode=mode, cutoff_s=cutoff, cases=len(rows),
                full_rank_cases=sum(r['locally_full_rank'] for r in rows),
                rank_min=min(r['numerical_rank'] for r in rows),
                rank_max=max(r['numerical_rank'] for r in rows), parameters=rows[0]['parameter_count'],
                half_step_rank_disagreements=sum(r['numerical_rank'] != r['half_step_rank'] for r in rows),
                smallest_sensitivity_min=min(r['smallest_scaled_sensitivity'] for r in rows)))
    value = dict(baseline_runs=len(records), forward_replays=31*len(records),
        analyses=sum(len(r['analyses']) for r in records), groups=groups,
        gauge_max_error=max(r['gauge_max_measurement_error'] for r in records),
        replay_parity_max_error=max(r['replay_parity_max_error'] for r in records),
        max_relative_half_step_change=max(r['relative_jacobian_half_step_change'] for r in records),
        confirmation_seeds_executed=[], version2_ready=False,
        interpretation='Local, conditional information audit. No controller performance or safety claim.',
        protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json', value)
    hashes={p.name:digest(p) for p in sorted(OUT.iterdir()) if p.suffix in ('.json','.csv') and p.name != 'checksums.json'}
    save(OUT/'checksums.json', hashes)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, choices=SEEDS)
    parser.add_argument('--summarize', action='store_true')
    args=parser.parse_args()
    protocol()
    if args.summarize:
        summarize()
    else:
        for seed in ([args.seed] if args.seed is not None else SEEDS):
            for phys in ('clean','combined'):
                for plant in ('nominal','slow'):
                    run_case(seed, phys, plant)
            print(f'Completed development patient {seed}', flush=True)
        if args.seed is None:
            summarize()
