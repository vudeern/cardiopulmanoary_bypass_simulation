"""Map where a reservoir forecast fails under unmodeled level-sensor bias.

Two policies, 49 disturbance cells, four paired virtual patients = 392 runs.
The 500-series seeds differ from the main benchmark; these are still synthetic
stress cases, not an independent clinical validation set. No tuning occurs here.
"""
import csv
import json
from pathlib import Path
import numpy as np
from perfusion_lab.model import Scenario
from perfusion_lab.simulation import simulate

ROOT = Path(__file__).resolve().parents[1]


def main():
    records = []
    for bias in np.linspace(0., .6, 7):
        for drainage in np.linspace(.3, 1., 7):
            scenario = Scenario('failure_map', dilution=1.8,
                                drainage=float(drainage), reservoir_bias=float(bias))
            for seed in range(500, 504):
                for policy in ('reactive', 'sentinel'):
                    result = simulate(scenario, policy, seed)
                    records.append(dict(level_bias_L=float(bias), drainage=float(drainage),
                                        seed=seed, policy=policy, **result['metrics']))
    out = ROOT/'results/failure-map.csv'
    with out.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(records)
    protocol = dict(seeds=list(range(500,504)), level_bias_L=np.linspace(0.,.6,7).tolist(),
                    drainage=np.linspace(.3,1.,7).tolist(), policies=['reactive','sentinel'],
                    duration=1200, dt=2, target=280, runs=len(records))
    (ROOT/'results/failure-map-protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    print(f'Wrote {len(records)} runs to {out.name}')

if __name__=='__main__':
    main()
