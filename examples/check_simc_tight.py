"""Post-result sensitivity to the source's canonical tau_c=theta choice.

This does not retune or replace the frozen primary comparison. It reuses final
cases and is explicitly descriptive, prompted by a boundary-selected setting.
"""
import csv
import json
from pathlib import Path
import numpy as np
from simc_benchmark import run,METRICS,dumps

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/simc-benchmark'


def main():
    p=json.loads((OUT/'protocol.json').read_text());selection=json.loads((OUT/'selection.json').read_text())
    target=selection['simc']['method']['options']['target_level']
    method=dict(id='canonical_tight',family='simc',kind='simc',options=dict(tau_c=1.5,target_level=target))
    protocol=dict(status='post_result_descriptive_sensitivity',reason='Primary SIMC selection at fast grid boundary; include canonical source tau_c=theta.',
        method=method,design_theta_s=1.5,source='data/simc-reference/source.json',
        data_reused='Original final cases and patient seeds; no independent confirmation or replacement primary test.',
        no_retuning=True)
    (OUT/'canonical-protocol.json').write_text(dumps(protocol))
    rows=[]
    for seed in p['evaluation_seeds']:
        for case in p['final_cases']:
            for plant in p['final_plants']:
                for reference in p['references']:
                    result=run('evaluation',case,plant,reference,seed,method)
                    rows.append(dict(case=case,plant=plant,reference=reference,seed=seed,
                        method='canonical_tight',**{k:result['metrics'][k] for k in METRICS}))
    with (OUT/'canonical-metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    summary=dict(status=protocol['status'],runs=len(rows),method=method,
        group_means={ref:{k:float(np.mean([r[k] for r in rows if r['reference']==ref])) for k in METRICS} for ref in p['references']},
        primary_changed=False,tuning_selected_on_final_data=False,
        interpretation='One fixed tighter rule check; both primary and canonical baseline are retained. No optimal-tuning or clinical claim.')
    (OUT/'canonical-summary.json').write_text(dumps(summary))
    print(f'Wrote {len(rows)} explicitly post-result canonical-rule checks; primary unchanged.')


if __name__=='__main__':main()
