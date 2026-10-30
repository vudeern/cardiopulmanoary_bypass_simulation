"""Command-line entrypoints. Paths are user controlled; no network or devices."""
import argparse
import csv
import json
from pathlib import Path
from .simulation import simulate
from .benchmark import benchmark
from .model import SCENARIOS
from .control import POLICIES


def main():
    parser = argparse.ArgumentParser(description='Perfusion Sentinel synthetic research laboratory')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='Export one complete trajectory and its metrics')
    run.add_argument('--scenario', choices=SCENARIOS, default='compound')
    run.add_argument('--policy', choices=POLICIES, default='sentinel')
    run.add_argument('--seed', type=int, default=100)
    bench = sub.add_parser('benchmark', help='Run the paired scenario-policy grid')
    bench.add_argument('--patients', type=int, default=24)
    bench.add_argument('--start-seed', type=int, default=100)
    for cmd in (run, bench):
        cmd.add_argument('--out', type=Path, default=Path('results'))
        cmd.add_argument('--duration', type=float, default=1200.)
        cmd.add_argument('--dt', type=float, default=2.)
        cmd.add_argument('--target', type=float, default=280.)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.command=='run':
        result = simulate(args.scenario, args.policy, args.seed, args.duration, args.dt, args.target)
        (args.out/'run.json').write_text(json.dumps(result, indent=2)+'\n')
        with (args.out/'run.csv').open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(result['rows'][0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(result['rows'])
        print(json.dumps(result['metrics'], indent=2))
    else:
        summary = benchmark(args.out, args.patients, args.start_seed, args.duration, args.dt, args.target)
        print(json.dumps(summary['protocol'], indent=2))

if __name__=='__main__':
    main()
