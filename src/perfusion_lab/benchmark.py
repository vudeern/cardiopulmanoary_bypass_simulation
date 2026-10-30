"""Paired virtual-patient experiments with seed-level bootstrap intervals."""
import csv
import json
from pathlib import Path
import numpy as np
from .model import SCENARIOS
from .control import POLICIES
from .simulation import simulate


def paired_interval(differences, seed=2026, repetitions=2000):
    """Percentile bootstrap of paired patient differences (candidate-baseline).

    This quantifies Monte Carlo variability for our synthetic parameter sampler;
    it is not a clinical confidence interval or a multiple-testing correction.
    """
    x = np.asarray(differences, dtype=float)
    if len(x)==0:
        raise ValueError('At least one paired observation is required')
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(repetitions, len(x)))].mean(axis=1)
    return dict(mean=float(x.mean()), low=float(np.quantile(means,.025)),
                high=float(np.quantile(means,.975)), n=len(x))


def benchmark(out, n=24, start_seed=100, duration=1200., dt=2., target=280.):
    """Prespecified scenario grid; all seeds and all policies retained."""
    if n<2:
        raise ValueError('Use at least two patients for a benchmark')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    records, trajectories = [], {}
    for scenario in SCENARIOS:
        for seed in range(start_seed, start_seed+n):
            for policy in POLICIES:
                result = simulate(scenario, policy, seed, duration, dt, target)
                records.append(dict(scenario=scenario, seed=seed, policy=policy, **result['metrics']))
                if seed==start_seed:
                    # Viewer has full temporal resolution for this explicitly
                    # labeled representative seed, independent of aggregate tests.
                    trajectories[f'{scenario}/{policy}'] = result
    with (out/'metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)
    comparisons = []
    for scenario in SCENARIOS:
        for policy in POLICIES:
            if policy=='reactive':
                continue
            a = [r for r in records if r['scenario']==scenario and r['policy']==policy]
            b = [r for r in records if r['scenario']==scenario and r['policy']=='reactive']
            assert [r['seed'] for r in a]==[r['seed'] for r in b]
            for metric in ('deficit_auc','low_reservoir_s','false_reassurance_s','mean_flow'):
                estimate = paired_interval([x[metric]-y[metric] for x,y in zip(a,b)])
                comparisons.append(dict(scenario=scenario, policy=policy,
                                        baseline='reactive', metric=metric, **estimate))
    summary = dict(protocol=dict(n=n, start_seed=start_seed, duration=duration,
                                dt=dt, target=target, policies=list(POLICIES),
                                scenarios=list(SCENARIOS), bootstrap_seed=2026,
                                bootstrap_repetitions=2000), comparisons=comparisons)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (out/'trajectories.json').write_text(json.dumps(trajectories, separators=(',',':'))+'\n')
    return summary
