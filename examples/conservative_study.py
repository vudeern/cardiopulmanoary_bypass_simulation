"""Select simple comparators on tuning seeds, then lock them for evaluation.

Run from the repository root. No candidate is selected using evaluation data.
All tuning candidates, selected failures, tradeoffs and map cells are retained.
This repeats the existing model and faults with new seeds; it is not independent
experimental validation, unfamiliar-plant testing or a clinical study.
"""
import csv
import json
import platform
from pathlib import Path
import sys
import numpy as np

from perfusion_lab.benchmark import paired_interval
from perfusion_lab.model import SCENARIOS, Scenario
from perfusion_lab.simulation import simulate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/conservative-comparison'
METRICS = ('low_reservoir_s', 'empty_request_s', 'deficit_auc', 'high_pressure_s',
           'false_reassurance_s', 'mean_flow', 'flow_variation', 'infeasible_s')


def candidates(pilot=False):
    items = [dict(id='original', family='original', policy='sentinel', options={}),
             dict(id='guarded', family='guarded', policy='sentinel_guarded', options={})]
    margins = (.1, .2, .3, .4, .5, .6) if pilot else tuple(i/100 for i in range(5,61,5))
    caps = (1.4, 1.6, 1.8, 2., 2.2, 2.4) if pilot else tuple(i/10 for i in range(14,47,2))
    for margin in margins:
        label = f'{margin:.1f}' if pilot else f'{margin:.2f}'
        items.append(dict(id=f'reserve_{label}', family='reserve', policy='sentinel',
                          options=dict(reserve_margin=margin)))
    for cap in caps:
        items.append(dict(id=f'cap_{cap:.1f}', family='flow_cap', policy='sentinel',
                          options=dict(flow_cap_index=cap)))
    return items


def means(rows):
    return {m:float(np.mean([r[m] for r in rows])) for m in METRICS}


def select(tuning, variants):
    """Match guard's tuning depletion/empty-request budgets, minimize deficit.

    Tie-break by reserve/cap value and id via candidate order. If no candidate
    meets both budgets, retain the least-exposure candidate and label unmatched.
    Scenarios are equally weighted artificial challenges, not event frequencies.
    """
    aggregates = {v['id']:means([r for r in tuning if r['variant']==v['id']]) for v in variants}
    budget = aggregates['guarded']
    selected = []
    for family in ('reserve', 'flow_cap'):
        choices = [v for v in variants if v['family']==family]
        feasible = [v for v in choices if all(aggregates[v['id']][m]<=budget[m]+1e-9
                    for m in ('low_reservoir_s', 'empty_request_s'))]
        pool = feasible or choices
        score = (lambda v:(aggregates[v['id']]['deficit_auc'], choices.index(v))) if feasible else (
            lambda v:(aggregates[v['id']]['low_reservoir_s'],
                      aggregates[v['id']]['empty_request_s'],
                      aggregates[v['id']]['deficit_auc'], choices.index(v)))
        winner = min(pool, key=score)
        selected.append(dict(**winner, matched_tuning_budget=bool(feasible)))
    return dict(guard_budget=budget, candidate_means=aggregates, selected=selected)


def save_csv(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def main(pilot=False):
    global OUT
    OUT = ROOT/('results/conservative-pilot' if pilot else 'results/conservative-comparison')
    OUT.mkdir(parents=True, exist_ok=True)
    variants = candidates(pilot)
    protocol = dict(version='1.2.0', candidates=variants,
        tuning_seeds=list(range(2000, 2008)) if pilot else list(range(5000, 5008)),
        evaluation_seeds=list(range(3000, 3024)) if pilot else list(range(6000, 6024)),
        map_seeds=list(range(4000, 4004)) if pilot else list(range(7000, 7004)),
        scenarios=list(SCENARIOS),
        duration=1200., dt=2., target=280.,
        level_bias_L=np.linspace(0., .6, 7).tolist(),
        drainage=np.linspace(.3, 1., 7).tolist(),
        primary_metric='deficit_auc', risk_metrics=['low_reservoir_s','empty_request_s'],
        weighting='Equal weight for each of seven artificial scenarios; not clinical prevalence',
        selection='Within each family, minimize tuning mean deficit among candidates meeting both guarded tuning mean risk budgets. If none match, choose lexicographically by low-reservoir exposure, empty requests, deficit, candidate order; label unmatched.',
        guard='Frozen v1.1 detector; no new guard tuning',
        paired_intervals='2000 percentile bootstrap resamples, seed 2026; pooled results resample patient seeds after averaging seven scenarios within each seed',
        replay='First evaluation seed, fixed before evaluation',
        tuning_runs=7*8*len(variants), evaluation_runs=672, map_runs=784,
        total_runs=7*8*len(variants)+672+784,
        design_revision=('Initial exploratory pilot' if pilot else
            'Expanded after the archived pilot selected the highest tested flow cap. Reserve grid refined to 0.05 L; cap range extended through an effectively inactive 4.6 L/min/m². All final tuning/evaluation/map seeds are new; the pilot is not confirmatory evidence.'),
        limitations=['Same structural plant and fault schedules as prior work.',
            'New seeds do not provide external validation.',
            'Finite simple-baseline grids do not exhaust existing methods.',
            'Tuning risk matching does not imply evaluation risk matching.',
            'No publication, patentability, clinical benefit or commercial demand established.'])
    (OUT/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    records, tuning = [], []

    def run(scenario, seed, variant, experiment, **extra):
        result = simulate(scenario, variant['policy'], seed,
                          controller_options=variant['options'])
        record = dict(experiment=experiment, scenario=result['scenario'], seed=seed,
            variant=variant['id'], family=variant['family'],
            level_bias_L=result['scenario_parameters']['reservoir_bias'],
            drainage=result['scenario_parameters']['drainage'], **result['metrics'])
        records.append(record)
        return record, result

    for name in protocol['scenarios']:
        for seed in protocol['tuning_seeds']:
            for variant in variants:
                record, _ = run(name, seed, variant, 'tuning')
                tuning.append(record)
        print('Tuning:', name, flush=True)
    save_csv(OUT/'tuning.csv', tuning)
    selection = select(tuning, variants)
    # Written before evaluation starts. Never overwritten using evaluation data.
    (OUT/'selection.json').write_text(json.dumps(selection, indent=2)+'\n')
    selected = variants[:2]+selection['selected']
    replay = {}
    for name in protocol['scenarios']:
        for seed in protocol['evaluation_seeds']:
            for variant in selected:
                record, result = run(name, seed, variant, 'evaluation')
                if seed==protocol['evaluation_seeds'][0]:
                    indices=sorted(set(range(0,len(result['rows']),3))|{len(result['rows'])-1})
                    fields=dict(t='time', do2='do2', monitor='measured_do2',
                        reservoir='reservoir', pressure='pressure',
                        infeasible='infeasible', fault='fault', level_fault='level_fault')
                    trajectory = {k:[round(result['rows'][i][field],4)
                        if isinstance(result['rows'][i][field],float)
                        else result['rows'][i][field] for i in indices] for k,field in fields.items()}
                    trajectory['metrics'] = result['metrics']
                    replay[f"{name}/{variant['id']}"] = trajectory
        print('Evaluation:', name, flush=True)
    for bias in protocol['level_bias_L']:
        for drainage in protocol['drainage']:
            scenario = Scenario('comparison_map', dilution=1.8,
                                reservoir_bias=bias, drainage=drainage)
            for seed in protocol['map_seeds']:
                for variant in selected:
                    run(scenario, seed, variant, 'map')
        print('Stress map bias:', round(bias,2), flush=True)
    assert len(records)==protocol['total_runs']
    save_csv(OUT/'metrics.csv', records)
    evaluation = [r for r in records if r['experiment']=='evaluation']
    cohort = {name:{v['id']:means([r for r in evaluation if r['scenario']==name and
              r['variant']==v['id']]) for v in selected} for name in protocol['scenarios']}
    pooled = {v['id']:means([r for r in evaluation if r['variant']==v['id']]) for v in selected}
    comparisons = []
    for name in protocol['scenarios']+['pooled']:
        for variant in selected:
            if variant['id']=='guarded': continue
            for metric in METRICS:
                def patient_values(vid):
                    return {seed:float(np.mean([r[metric] for r in evaluation if
                        r['variant']==vid and r['seed']==seed and
                        (name=='pooled' or r['scenario']==name)]))
                        for seed in protocol['evaluation_seeds']}
                a, b = patient_values(variant['id']), patient_values('guarded')
                comparisons.append(dict(scenario=name, variant=variant['id'],
                    baseline='guarded', metric=metric,
                    **paired_interval([a[seed]-b[seed] for seed in protocol['evaluation_seeds']])))
    cells=[]
    for bias in protocol['level_bias_L']:
        for drainage in protocol['drainage']:
            cells.append(dict(level_bias_L=bias, drainage=drainage,
                means={v['id']:means([r for r in records if r['experiment']=='map' and
                    r['level_bias_L']==bias and r['drainage']==drainage and
                    r['variant']==v['id']]) for v in selected}))
    summary=dict(selected=selected, cohort_means=cohort, pooled_means=pooled,
                 comparisons=comparisons, map=cells)
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (OUT/'environment.json').write_text(json.dumps(dict(python=sys.version,
        numpy=np.__version__, platform=platform.platform()), indent=2)+'\n')
    if pilot:
        print('Pilot reproduced; canonical web export unchanged.', flush=True)
        return
    web_protocol=dict(n=24, start_seed=protocol['evaluation_seeds'][0], policies=[v['id'] for v in selected],
                      scenarios=protocol['scenarios'])
    web=dict(protocol=web_protocol, variants=selected,
             comparisons=comparisons, runs={})
    (ROOT/'web/comparison-data.js').write_text('/* Generated synthetic comparison; frozen tuning selection. */\nconst COMPARISON = '+json.dumps(web,separators=(',',':'))+';\n')
    for name in protocol['scenarios']:
        subset={k:v for k,v in replay.items() if k.startswith(name+'/')}
        (ROOT/f'web/comparison-{name}.js').write_text('/* Generated synthetic evaluation replay. */\nObject.assign(COMPARISON.runs,'+json.dumps(subset,separators=(',',':'))+');\n')
    print('Completed', len(records), 'runs. Selected:', selection['selected'], flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true', help='Reproduce archived initial search and seeds')
    main(parser.parse_args().pilot)
