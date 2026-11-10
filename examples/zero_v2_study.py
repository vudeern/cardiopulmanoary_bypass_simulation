"""V2 zero-return stopping study: 40 new runs and 40 retained credit references."""
from copy import deepcopy
import csv
import json
import numpy as np
import joint_v2_study as previous
from joint_v2_study import ROOT,SEEDS,CASES,FIELDS,digest,save,patient

OUT=ROOT/'results/v2-zero-pilot'
NAMES=('aggregate_zero','joint_zero','aggregate_credit','joint_credit')


def methods():
    old=previous.methods();result={}
    for name in NAMES:
        original='joint_pi' if name.startswith('joint') else 'aggregate_pi'
        result[name]=deepcopy(old[original])
        if name.endswith('zero'):result[name]['options']['return_horizon_s']=0.
    return result


def run(seed,plant,case,method):return previous.run(seed,plant,case,method)


def protocol():
    sources=set(json.loads((previous.OUT/'protocol.json').read_text())['source_hashes'])
    sources.add('examples/zero_v2_study.py')
    value=dict(version_line='v2',version='2.0.0rc3',stage='zero_return_joint_development_pilot',
        seeds=SEEDS,cases=CASES,plants=['nominal','slow'],methods=methods(),
        evaluations=80,new_simulations=40,retained_reference_runs=40,duration_s=600.,dt_s=1.,
        windows_s={c:previous.windows(c) for c in CASES},recovery_analysis_window_s=[213.,348.],
        mechanism='Fixed 2x2: aggregate/joint model association crossed with zero/15-second future-return credit. Zero arms enforce stopping reserve with no credited future inflow; finite_return_reserve(horizon=0) equals full zero-return braking reserve. No new sensing, gains, pruning, slew authority, floor or error allowances. All retained models must pass in joint arms.',
        fairness='Same point-estimate fast PI, identical measurements, causal observer and starting state for all arms. Credit arms are the 40 already published exact configurations/cases, reused by hashed trace reference; not new simulations or independent replication.',
        limits='Zero-return reserve eliminates the future-inflow assumption only. Conditional calibration/model retention and bounds, initial/unsupported state, pressure and actual dynamics can still invalidate protection. Two reused development patients; no general safety or clinical/hardware claim.',
        confirmation_seeds_executed=[],v2_milestone_passed=False,
        source_hashes={p:digest(ROOT/p) for p in sorted(sources)},
        retained_hashes={str((previous.OUT/p).relative_to(ROOT)):sha for p,sha in json.loads((previous.OUT/'checksums.json').read_text()).items()})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen protocol changed'
    else:save(p,value)


def execute():
    records=[]
    for old in json.loads((previous.OUT/'runs.json').read_text()):
        row=dict(old);row['method']='joint_credit' if old['method']=='joint_pi' else 'aggregate_credit'
        row['origin']='retained_v2_joint_pilot'
        row['trace_path']=str((previous.OUT/f"{old['seed']}-{old['plant']}-{old['case']}-{old['method']}.csv").relative_to(ROOT))
        records.append(row)
    for seed in SEEDS:
        for plant in ('nominal','slow'):
            for case in CASES:
                for name in ('aggregate_zero','joint_zero'):
                    result=run(seed,plant,case,methods()[name]);rows=result['rows']
                    trace=OUT/f'{seed}-{plant}-{case}-{name}.csv'
                    with trace.open('w',newline='') as f:
                        w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in FIELDS} for r in rows)
                    records.append(dict(seed=seed,plant=plant,case=case,method=name,origin='new_zero_return_simulation',
                        trace_path=str(trace.relative_to(ROOT)),**result['metrics'],
                        recovery_deficit_auc=sum(max(0.,280.-r['do2']) for r in rows if 213<=r['observation_time']<348)/60.,
                        changed_action_s=sum(r['joint_action_changed'] for r in rows),
                        unsupported_s=sum(not r['joint_supported'] for r in rows),
                        cap_violations=sum(not r['applied_within_shared_cap'] for r in rows),
                        feasible_margin_violations=sum(r['hypothesis_margin'] is not None and r['predictive_feasible'] and r['hypothesis_margin'] < -1e-7 for r in rows),
                        widened_cap_s=sum(r['joint_cap']>r['aggregate_cap']+1e-6 for r in rows)))
                    save(OUT/'runs.json',records)
                print(f'Completed zero-return {seed} {plant} {case}',flush=True)
    groups={}
    for case in CASES:
        g=groups[case]={}
        for name in NAMES:
            rows=[r for r in records if r['case']==case and r['method']==name]
            g[name]=dict(runs=len(rows),mean_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
                mean_recovery_deficit_auc=float(np.mean([r['recovery_deficit_auc'] for r in rows])),
                floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
                high_pressure_cases=sum(r['high_pressure_s']>0 for r in rows),
                minimum_reservoir_L=min(r['minimum_reservoir'] for r in rows),
                unsupported_s=sum(r['unsupported_s'] for r in rows),
                cap_violations=sum(r['cap_violations'] for r in rows),feasible_margin_violations=sum(r['feasible_margin_violations'] for r in rows))
        g['zero_joint_reduction_fraction']=1-g['joint_zero']['mean_deficit_auc']/g['aggregate_zero']['mean_deficit_auc']
    totals={}
    for name in NAMES:
        rows=[r for r in records if r['method']==name]
        totals[name]=dict(runs=len(rows),mean_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
            floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
            high_pressure_cases=sum(r['high_pressure_s']>0 for r in rows),
            minimum_reservoir_L=min(r['minimum_reservoir'] for r in rows))
    summary=dict(version_line='v2',evaluations=len(records),new_simulations=40,retained_reference_runs=40,
        groups=groups,totals=totals,zero_joint_reduction_fraction=1-totals['joint_zero']['mean_deficit_auc']/totals['aggregate_zero']['mean_deficit_auc'],
        v2_milestone_passed=False,confirmation_seeds_executed=[],protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',summary);save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.name!='checksums.json'})
    print((OUT/'summary.json').read_text(),flush=True)


if __name__=='__main__':protocol();execute()
