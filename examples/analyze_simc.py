"""Working machine-readable diagnostics only; no paper/result document generator."""
import csv
import json
from pathlib import Path
from simc_benchmark import METRICS,dumps

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/simc-benchmark'


def analysis():
    p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
    rows=list(csv.DictReader((OUT/'metrics.csv').open()))
    final=[r for r in rows if r['phase']=='evaluation']
    pairs=[]
    for plant in p['final_plants']:
        for ref in p['references']:
            for seed in p['evaluation_seeds']:
                base=next(r for r in final if r['method']=='simc' and r['case']=='clean' and r['plant']==plant and r['reference']==ref and int(r['seed'])==seed)
                for case in ('arterial_flow_bias','venous_flow_bias'):
                    fault=next(r for r in final if r['method']=='simc' and r['case']==case and r['plant']==plant and r['reference']==ref and int(r['seed'])==seed)
                    equal=all(float(base[k])==float(fault[k]) for k in METRICS)
                    pairs.append(dict(plant=plant,reference=ref,seed=seed,case=case,physical_metrics_exactly_equal=equal))
    contrasts={cell:{k:m['forecast'][k]-m['simc'][k] for k in METRICS} for cell,m in s['cell_means'].items()}
    selected=s['methods']['simc']['options']
    return dict(status='working_diagnostics',scope='Synthetic model only; no clinical effect or scientific priority claim.',
        primary=s['primary'],flow_sensor_invariance=dict(pairs=len(pairs),equal=sum(x['physical_metrics_exactly_equal'] for x in pairs),
            interpretation='The SIMC application consumes neither flow sensor in its decision. Its physical-output invariance is a construction property, not protection against level/reference faults.',checks=pairs),
        cell_differences_forecast_minus_simc=contrasts,
        descriptive_counts=dict(cells=len(contrasts),lower_oxygen_deficit=sum(x['deficit_auc']<0 for x in contrasts.values()),
            lower_reservoir_exposure=sum(x['low_reservoir_s']<0 for x in contrasts.values()),
            higher_reservoir_exposure=sum(x['low_reservoir_s']>0 for x in contrasts.values()),
            both_metrics_strictly_lower=sum(x['deficit_auc']<0 and x['low_reservoir_s']<0 for x in contrasts.values())),
        selection_limitations=dict(simc_selected_at_fast_grid_boundary=selected['tau_c']==5.,
            note='Finite equal candidate budgets, not proof that either family was optimally tuned. Final cases must not be reused for retuning as independent evidence.'),
        contribution_boundary='A reproducible comparison and counterexamples against a verified general PI baseline. The forecast does not demonstrate the declared joint advantage; a new clinical finding or novel control algorithm is not established.')


def main():
    (OUT/'diagnostics.json').write_text(dumps(analysis()));print('Wrote machine diagnostics; no docs or paper material generated.')


if __name__=='__main__':main()
