"""Evaluate the frozen step-fault hypothesis on fresh synthetic seeds.

Run from the repository root: PYTHONPATH=src python examples/level_guard_study.py
Writes the complete protocol before running simulations. No parameter tuning or
seed selection occurs here. These are internal synthetic tests, not external
validation or evidence of clinical benefit. The existing v1 artifacts remain.
"""
import csv
import json
from pathlib import Path
import platform
import sys
import numpy as np

from perfusion_lab.benchmark import paired_interval
from perfusion_lab.model import SCENARIOS, Scenario
from perfusion_lab.simulation import simulate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/level-guard'
POLICIES = ('reactive', 'sentinel', 'sentinel_guarded')
METRICS = ('low_reservoir_s', 'empty_request_s', 'deficit_auc', 'high_pressure_s',
           'false_reassurance_s', 'mean_flow', 'flow_variation', 'level_fault_s')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    protocol = dict(
        version='1.1.0', baseline_release='1.0.0',
        policies=list(POLICIES), scenarios=list(SCENARIOS),
        cohort_seeds=list(range(1000, 1024)), map_seeds=list(range(1500, 1504)),
        level_bias_L=np.linspace(0., .6, 7).tolist(),
        drainage=np.linspace(.3, 1., 7).tolist(), duration=1200, dt=2, target=280,
        detector=dict(max_drainage_L_min=7.5, jump_allowance_L=.03,
                      post_alarm_reserve_L=.08, alarm_latched=True),
        primary_metric='low_reservoir_s', comparators=['sentinel', 'reactive'],
        secondary_metrics=list(METRICS[1:]), bootstrap_seed=2026,
        bootstrap_repetitions=2000,
        scope='Internal synthetic evaluation; no clinical calibration or external validation',
        limitations=['Initial offsets and slow drift are unidentifiable.',
                     'Small jumps can remain inside the physical envelope.',
                     'Independent flow sensing and drainage cap are assumed.',
                     'Conservative flow reduction can worsen oxygen delivery.'],
        expected_runs=1092)
    (OUT/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    records = []
    for name in protocol['scenarios']:
        for seed in protocol['cohort_seeds']:
            for policy in POLICIES:
                r = simulate(name, policy, seed)
                records.append(dict(experiment='cohort', scenario=name, seed=seed,
                                    level_bias_L=SCENARIOS[name].reservoir_bias,
                                    drainage=SCENARIOS[name].drainage,
                                    policy=policy, **r['metrics']))
        print('Completed cohort:', name, flush=True)
    for bias in protocol['level_bias_L']:
        for drainage in protocol['drainage']:
            scenario = Scenario('level_guard_map', dilution=1.8, drainage=drainage,
                                reservoir_bias=bias)
            for seed in protocol['map_seeds']:
                for policy in POLICIES:
                    r = simulate(scenario, policy, seed)
                    records.append(dict(experiment='map', scenario=scenario.name,
                                        seed=seed, level_bias_L=bias, drainage=drainage,
                                        policy=policy, **r['metrics']))
        print('Completed map bias:', round(bias, 2), flush=True)
    assert len(records) == protocol['expected_runs']
    with (OUT/'metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(records)
    comparisons = []
    for name in protocol['scenarios']:
        runs = [r for r in records if r['experiment']=='cohort' and r['scenario']==name]
        for baseline in protocol['comparators']:
            a = {r['seed']: r for r in runs if r['policy']=='sentinel_guarded'}
            b = {r['seed']: r for r in runs if r['policy']==baseline}
            assert set(a) == set(b) == set(protocol['cohort_seeds'])
            for metric in METRICS:
                comparisons.append(dict(scenario=name, policy='sentinel_guarded',
                    baseline=baseline, metric=metric,
                    **paired_interval([a[s][metric]-b[s][metric] for s in sorted(a)])))
    cells = []
    for bias in protocol['level_bias_L']:
        for drainage in protocol['drainage']:
            runs = [r for r in records if r['experiment']=='map' and
                    r['level_bias_L']==bias and r['drainage']==drainage]
            means = {p: {m: float(np.mean([r[m] for r in runs if r['policy']==p]))
                         for m in METRICS} for p in POLICIES}
            cells.append(dict(level_bias_L=bias, drainage=drainage, means=means))
    means = {name: {p: {m: float(np.mean([r[m] for r in records if
                r['experiment']=='cohort' and r['scenario']==name and r['policy']==p]))
                for m in METRICS} for p in POLICIES} for name in protocol['scenarios']}
    (OUT/'summary.json').write_text(json.dumps(dict(cohort_means=means,
        comparisons=comparisons, map=cells), indent=2)+'\n')
    (OUT/'environment.json').write_text(json.dumps(dict(python=sys.version,
        numpy=np.__version__, platform=platform.platform()), indent=2)+'\n')
    print('Wrote', len(records), 'paired runs to', OUT, flush=True)


if __name__ == '__main__':
    main()
