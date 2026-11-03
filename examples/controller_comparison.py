"""Exploratory, source-informed adaptation comparison; no publication report.

An exact published-controller comparison remains gated by reproduction status.
This script cannot label an adaptation as the authors' validated controller.
"""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/controller-comparison'
SCENARIOS={
    'clean':dict(level_profile='none',drainage=1.,dilution=0.),
    'drainage':dict(level_profile='none',drainage=.45),
    'hb_bias':dict(level_profile='none',drainage=1.,hb_bias=2.),
    'level_drift':dict(level_profile='ramp',reservoir_bias=.4,drift_duration=.3),
    'arterial_flow_bias':dict(level_profile='none',flow_bias=.75),
    'combined':dict(level_profile='ramp',reservoir_bias=.4,drift_duration=.3,flow_bias=.75)}
DEV_PLANTS={'reference':{},'slow_pump':dict(actuator_tau=6.)}
FINAL_PLANTS={**DEV_PLANTS,'lagged_drainage':dict(drainage_tau=12.,venous_nonlinearity=.04)}
METRICS=('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s','flow_variation',
         'minimum_reservoir','mean_flow','venous_tracking_mae_l_min','level_mae_l')


def json_default(value):
    if isinstance(value,np.generic):return value.item()
    raise TypeError(f'Unsupported JSON value: {type(value).__name__}')


def candidates():
    adapted=[dict(id=f'adapted_{kp}_{ki}_{kd}',family='adapted',kind='published_adapted',
        options=dict(kp=kp,ki=ki,kd=kd))
        for kp in (2.,4.) for ki in (.02,.08) for kd in (0.,.5)]
    sentinel=[dict(id=f'sentinel_{m:.1f}',family='sentinel',kind='forecast',
        options=dict(reserve_margin=float(m))) for m in np.arange(8)/10.]
    return adapted+sentinel


def run(case,plant,seed,method,*,venous_bias=0.):
    scenario=StressScenario(case,**SCENARIOS[case])
    measured=None if method.get('legacy') else dict(noise_sd=.015,bias=venous_bias)
    result=simulate(scenario,'sentinel',seed=seed,duration=600.,dt=1.,patient=Patient.sampled(seed),
        controller_kind=method['kind'],controller_options=method['options'],
        plant_options=plant,venous_measurement=measured,
        level_mode='hold',level_reference_options=dict(period=60.,delay=4.,noise_sd=.01))
    rows=result['rows'];m=result['metrics']
    m['venous_tracking_mae_l_min']=float(np.mean([abs(r['flow']-r['qv']) for r in rows]))
    m['level_mae_l']=float(np.mean([abs(r['reservoir']-.45) for r in rows]))
    return result


def aggregate(rows):
    return {key:float(np.mean([float(r[key]) for r in rows])) for key in METRICS}


def select(records,values):
    means={v['id']:aggregate([r for r in records if r['method']==v['id']]) for v in values}
    eligible=[v for v in values if means[v['id']]['low_reservoir_s']<=1.
              and means[v['id']]['empty_request_s']<=1. and means[v['id']]['high_pressure_s']<=5.]
    def key(v):
        m=means[v['id']]
        return ((m['deficit_auc'],values.index(v)) if eligible else
                (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],values.index(v)))
    chosen=min(eligible or values,key=key)
    return dict(method=chosen,matched_development_budget=bool(eligible),means=means)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(status='exploratory_adaptation_not_exact_reproduction',
        development_seeds=list(range(13000,13004)),evaluation_seeds=list(range(14000,14012)),
        candidates=candidates(),scenarios=SCENARIOS,development_plants=DEV_PLANTS,
        evaluation_plants=FINAL_PLANTS,duration_s=600.,dt_s=1.,
        information='Measured venous flow is available to adapted and matched Sentinel arms; legacy Sentinel uses the original inferred channel. All share Hb/level references, noise innovations and plant/actuator constraints.',
        objectives='Adapted reference tracks measured venous flow and a 0.45 L level target. Sentinel prioritizes an oxygen target and reservoir floor. Report all metrics; objective differences prevent an unqualified ranking.',
        tuning='8 candidates per family, same development cases and seeds; choose lowest oxygen deficit among methods meeting engineering mean exposure budgets. If none qualify, lexicographic reservoir/empty/pressure/oxygen ordering; declare unmatched.',
        final_extra_case='Venous sensor bias +0.5 L/min is evaluated separately for all six scenarios.',
        final_settings_changed='Only selected settings carry forward; final lagged-drainage plant and venous-bias regime were not used for tuning.',
        exposure_budgets=dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.),
        reproduction_manifest='data/controller-reference/reproduction.json')
    # Persist protocol before any evaluation and selection before final runs.
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    records=[]
    for seed in protocol['development_seeds']:
        for case in SCENARIOS:
            for plant_name,plant in DEV_PLANTS.items():
                for v in candidates():
                    result=run(case,plant,seed,v)
                    records.append(dict(phase='development',case=case,plant=plant_name,seed=seed,
                        method=v['id'],venous_bias=0.,**{k:result['metrics'][k] for k in METRICS}))
    selected={f:select(records,[v for v in candidates() if v['family']==f]) for f in ('adapted','sentinel')}
    (OUT/'selection.json').write_text(json.dumps(selected,indent=2)+'\n')
    methods={f:dict(v['method']) for f,v in selected.items()}
    methods['legacy_sentinel']=dict(methods['sentinel'],legacy=True)
    methods['legacy_sentinel']['id']='legacy_sentinel'
    for seed in protocol['evaluation_seeds']:
        for case in SCENARIOS:
            for plant_name,plant in FINAL_PLANTS.items():
                for bias in (0.,.5):
                    for label,v in methods.items():
                        result=run(case,plant,seed,v,venous_bias=bias)
                        records.append(dict(phase='evaluation',case=case,plant=plant_name,seed=seed,
                            method=label,venous_bias=bias,**{k:result['metrics'][k] for k in METRICS}))
    with (OUT/'metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    final=[r for r in records if r['phase']=='evaluation']
    manifest=json.loads((ROOT/'data/controller-reference/reproduction.json').read_text())
    summary=dict(status=protocol['status'],development_runs=len(records)-len(final),evaluation_runs=len(final),
        methods=methods,exact_reproduction_completed=False,authors_results_reproduced=False,
        can_claim_advantage_over_published_controller=False,
        blockers=manifest['unresolved'],selection_sha256=hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest(),
        group_means={str(bias):{label:aggregate([r for r in final if r['method']==label and r['venous_bias']==bias])
            for label in methods} for bias in (0.,.5)})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Two prespecified cases, one seed, all methods retained as raw debug traces.
    traces={}
    for case in ('clean','combined'):
        for label,method in methods.items():
            result=run(case,{},14000,method)
            keys=('time','observation_time','flow','qv','reservoir','pressure','command',
                  'observed_venous_flow','observed_flow','observed_reservoir','do2','empty_request')
            traces[case+'/'+label]=dict(seed=result['seed'],dt=result['dt'],metrics=result['metrics'],
                rows=[{key:r[key] for key in keys} for r in result['rows']])
    (OUT/'debug-traces.json').write_text(json.dumps(traces,separators=(',',':'),default=json_default)+'\n')
    print(f'Wrote {len(records)} exploratory runs; exact-reproduction gate remains blocked.')


if __name__=='__main__':main()
