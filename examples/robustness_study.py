"""Frozen v1.2 policies under unfamiliar sensing and plant assumptions.

No tuning or policy selection occurs here. All 45 challenge cells are retained.
Six replay cells and seed 8000 are fixed before running the study. These are
synthetic assumption tests, not independently measured physiology.
"""
import hashlib
import json
import csv
import platform
import sys
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate
from perfusion_lab.benchmark import paired_interval

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/robustness'
SENSORS={
    'clean':dict(level_profile='none'),
    'step':dict(level_profile='step',reservoir_bias=.4),
    'drift':dict(level_profile='ramp',reservoir_bias=.4),
    'initial':dict(level_profile='initial',reservoir_bias=.4),
    'small_step':dict(level_profile='step',reservoir_bias=.1),
    'flow_high':dict(level_profile='none',flow_bias=.75),
    'flow_low':dict(level_profile='none',flow_bias=-.75),
    'drift_flow':dict(level_profile='ramp',reservoir_bias=.4,flow_bias=.75),
    'noisy':dict(level_profile='none',noise_scale=10.),
}
PLANTS={
    'reference':{},
    'slow_pump':dict(actuator_tau=8.),
    'lagged_nonlinear':dict(drainage_tau=12.,venous_nonlinearity=.04),
    'cap_violation':dict(max_drainage=9.),
    'varied_storage':{},
}
REPLAYS=['clean__reference','drift__reference','initial__reference',
         'flow_high__reference','step__slow_pump','clean__cap_violation']
METRICS=('low_reservoir_s','empty_request_s','deficit_auc','high_pressure_s',
         'false_reassurance_s','mean_flow','flow_variation','level_alarm_ever')


def case_parameters(seed,plant):
    rng=np.random.default_rng(seed+25000)
    start=float(rng.uniform(.25,.5));end=start+float(rng.uniform(.15,.25))
    patient=Patient.sampled(seed)
    if plant=='varied_storage':
        rng=np.random.default_rng(seed+30000)
        patient=replace(patient,venous_compliance=float(rng.uniform(.09,.15)),
                        venous_resistance=float(rng.uniform(.7,1.1)))
    return patient,start,end


def means(rows):
    return {m:float(np.mean([r[m] for r in rows])) for m in METRICS}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    settings_file=ROOT/'results/conservative-comparison/summary.json'
    settings_bytes=settings_file.read_bytes()
    variants=json.loads(settings_bytes)['selected']
    assert [v['id'] for v in variants]==['original','guarded','reserve_0.40','cap_2.4']
    protocol=dict(version='1.3.0',seeds=list(range(8000,8024)),variants=variants,
        settings_source='results/conservative-comparison/summary.json',
        settings_source_sha256=hashlib.sha256(settings_bytes).hexdigest(),
        sensor_cases=SENSORS,plant_cases=PLANTS,duration=1200.,dt=2.,target=280.,
        event_start_fraction=[.25,.5],event_duration_fraction=[.15,.25],
        event_timing_seed_offset=25000,storage_seed_offset=30000,
        varied_storage=dict(venous_compliance_L_mmHg=[.09,.15],
                            venous_resistance_mmHg_min_L=[.7,1.1]),
        drift_duration_fraction=.25,level_faults_persist=True,
        common_challenge=dict(dilution=1.8,drainage=.45),
        total_runs=4320,cells=45,patients_per_cell=24,
        primary_metrics=['low_reservoir_s','deficit_auc'],
        diagnostic='level_alarm_ever is any latched level flag; it is not proof of correct fault identification. No level fault is injected in clean/flow_high/flow_low/noisy cases.',
        bootstrap=dict(repetitions=2000,seed=2026,unit='paired patient seed; pooled cells averaged within seed'),
        replay_cells=REPLAYS,replay_seed=8000,
        no_tuning=True,weighting='Equal weight per synthetic cell; not clinical prevalence',
        scope='Internal structural-assumption stress tests, not external validation',
        limitations=['All new plant and fault magnitudes are engineering assumptions.',
                     'Altered drainage and pump response are not clinical calibration.',
                     'Fixed baseline settings are carried from v1.2, not retuned to this grid.',
                     'No noisy independent redundant level reference is added.',
                     'No scientific novelty or commercial readiness established.'])
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    parameters={}
    for seed in protocol['seeds']:
        parameters[str(seed)]={}
        for plant in PLANTS:
            patient,start,end=case_parameters(seed,plant)
            parameters[str(seed)][plant]=dict(patient=asdict(patient),event_start=start,
                event_end=end,plant_options=PLANTS[plant])
    (OUT/'parameters.json').write_text(json.dumps(parameters,indent=2)+'\n')
    records=[];replay={};descriptions={};labels={}
    for sensor,config in SENSORS.items():
        for plant,plant_options in PLANTS.items():
            cell=f'{sensor}__{plant}'
            labels[cell]=sensor.replace('_',' ')+' · '+plant.replace('_',' ')
            descriptions[cell]=(f"Synthetic {sensor.replace('_',' ')} sensing challenge with "
                f"{plant.replace('_',' ')} dynamics. Dilution is 1.8 g/dL; a drainage restriction "
                'starts at a seed-dependent time. All policies and thresholds are frozen from v1.2. '
                'The case is an engineering assumption test, not calibrated physiology.')
            for seed in protocol['seeds']:
                patient,start,end=case_parameters(seed,plant)
                scenario=StressScenario(cell,dilution=1.8,drainage=.45,
                    event_start=start,event_end=end,**config)
                for variant in variants:
                    result=simulate(scenario,variant['policy'],seed,patient=patient,
                                    controller_options=variant['options'],plant_options=plant_options)
                    alarm_times=[r['observation_time'] for r in result['rows'] if r['level_fault']]
                    injections=[r['observation_time'] for r in result['rows'] if r['injected_level_bias']!=0.]
                    records.append(dict(sensor_case=sensor,plant_case=plant,scenario=cell,
                        seed=seed,variant=variant['id'],**result['metrics'],
                        level_alarm_ever=int(bool(alarm_times)),
                        level_fault_injected=int(bool(injections)),
                        first_alarm_s=alarm_times[0] if alarm_times else None,
                        first_level_bias_s=injections[0] if injections else None,
                        alarm_before_level_bias=int(bool(alarm_times and
                            (not injections or alarm_times[0]<injections[0])))))
                    if seed==protocol['replay_seed'] and cell in REPLAYS:
                        indices=sorted(set(range(0,len(result['rows']),3))|{len(result['rows'])-1})
                        fields=dict(t='time',do2='do2',monitor='measured_do2',
                            reservoir='reservoir',pressure='pressure',infeasible='infeasible',
                            fault='fault',level_fault='level_fault',
                            level_sensor='observed_reservoir',level_lower='reservoir_lower')
                        run={key:[round(result['rows'][i][field],4) if
                            isinstance(result['rows'][i][field],float) else result['rows'][i][field]
                            for i in indices] for key,field in fields.items()}
                        run['metrics']=result['metrics']
                        replay[f"{cell}/{variant['id']}"]=run
        print('Completed all plant challenges for:',sensor,flush=True)
    assert len(records)==protocol['total_runs']
    assert settings_file.read_bytes()==settings_bytes,'Frozen settings changed during evaluation'
    with (OUT/'metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(records)
    cells={f'{sensor}__{plant}':{v['id']:means([r for r in records if
        r['sensor_case']==sensor and r['plant_case']==plant and r['variant']==v['id']])
        for v in variants} for sensor in SENSORS for plant in PLANTS}
    pooled={v['id']:means([r for r in records if r['variant']==v['id']]) for v in variants}
    sensor_means={sensor:{v['id']:means([r for r in records if r['sensor_case']==sensor
        and r['variant']==v['id']]) for v in variants} for sensor in SENSORS}
    comparisons=[]
    for cell in [*cells,'pooled']:
        runs=[r for r in records if cell=='pooled' or r['scenario']==cell]
        for variant in variants:
            if variant['id']=='guarded':continue
            for metric in METRICS:
                def values(vid):
                    return [float(np.mean([r[metric] for r in runs if r['seed']==seed
                        and r['variant']==vid])) for seed in protocol['seeds']]
                a,b=values(variant['id']),values('guarded')
                comparisons.append(dict(scenario=cell,variant=variant['id'],baseline='guarded',
                    metric=metric,**paired_interval([x-y for x,y in zip(a,b)])))
    summary=dict(variants=variants,cell_means=cells,sensor_means=sensor_means,
                 pooled_means=pooled,comparisons=comparisons)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (OUT/'environment.json').write_text(json.dumps(dict(python=sys.version,numpy=np.__version__,
        platform=platform.platform()),indent=2)+'\n')
    web=dict(protocol=dict(n=24,start_seed=8000,scenarios=REPLAYS,
        policies=[v['id'] for v in variants]),variants=variants,
        labels={cell:labels[cell] for cell in REPLAYS},
        descriptions={cell:descriptions[cell] for cell in REPLAYS},
        comparisons=[c for c in comparisons if c['scenario'] in REPLAYS],runs={})
    (ROOT/'web/robustness-data.js').write_text('/* Generated frozen-policy stress study. */\nconst ROBUSTNESS = '+json.dumps(web,separators=(',',':'))+';\n')
    for cell in REPLAYS:
        subset={key:value for key,value in replay.items() if key.startswith(cell+'/')}
        (ROOT/f'web/robustness-{cell}.js').write_text('/* Prespecified seed 8000 replay. */\nObject.assign(ROBUSTNESS.runs,'+json.dumps(subset,separators=(',',':'))+');\n')
    print('Completed',len(records),'runs; all 45 cells and frozen settings retained.',flush=True)


if __name__=='__main__':main()
