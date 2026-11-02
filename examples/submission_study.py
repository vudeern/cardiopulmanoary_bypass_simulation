"""Stronger baselines with frozen selection and untouched evaluation settings.

The primary test asks if a level PI baseline lowers oxygen deficit versus the
tuned forecast without worse reservoir/empty-request/pressure exposure.
It does not test clinical safety or scientific priority.
"""
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path
import numpy as np
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate
from perfusion_lab.benchmark import paired_interval

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/submission-study'
METRICS=('low_reservoir_s','empty_request_s','deficit_auc','high_pressure_s','mean_flow','flow_variation')
DEV_SENSORS={'clean':dict(level_profile='none'),
    'step':dict(level_profile='step',reservoir_bias=.5),'drift':dict(level_profile='ramp',reservoir_bias=.5,drift_duration=.2),
    'initial':dict(level_profile='initial',reservoir_bias=.5),'flow_high':dict(level_profile='none',flow_bias=.9),
    'drift_flow':dict(level_profile='ramp',reservoir_bias=.5,drift_duration=.2,flow_bias=.9),
    'noisy':dict(level_profile='none',noise_scale=12.)}
FINAL_SENSORS={**DEV_SENSORS,'step':dict(level_profile='step',reservoir_bias=.6),
    'drift':dict(level_profile='ramp',reservoir_bias=.6,drift_duration=.25),
    'initial':dict(level_profile='initial',reservoir_bias=.6),
    'flow_high':dict(level_profile='none',flow_bias=1.1),
    'drift_flow':dict(level_profile='ramp',reservoir_bias=.6,drift_duration=.25,flow_bias=1.1),
    'noisy':dict(level_profile='none',noise_scale=14.)}
DEV_PLANTS={'reference':{},'slow_pump':dict(actuator_tau=8.)}
FINAL_PLANTS={'reference':{},'slow_pump':dict(actuator_tau=5.),
              'lagged':dict(drainage_tau=20.,venous_nonlinearity=.08)}
REFERENCES={'good':dict(period=60.,delay=4.,noise_sd=.01),
    'delayed':dict(period=90.,delay=30.,noise_sd=.01),
    'dropout':dict(period=60.,delay=4.,noise_sd=.01,dropout_prob=.25,outage_start=360.,outage_end=840.),
    'biased':dict(period=60.,delay=4.,noise_sd=.01,bias=.15)}
REPLAYS=['flow_high__reference__good','drift_flow__lagged__good',
         'initial__slow_pump__good','drift__reference__dropout']


def candidates():
    values=[]
    for margin in (0.,.1,.2,.3,.4,.5):
        values.append(dict(id=f'forecast_{margin:.1f}',family='forecast',kind='forecast',
            label=f'Forecast +{margin:.1f} L',options=dict(reserve_margin=margin)))
    for target in (.4,.6):
        for kp in (2.,4.,8.):
            for ki in (.02,.08):
                values.append(dict(id=f'pi_{target}_{kp}_{ki}',family='pi',kind='pi',
                    label=f'Level PI · target {target:.1f} L',
                    options=dict(target_level=target,kp=kp,ki=ki)))
    for threshold in (.4,.6,.8,1.):
        values.append(dict(id=f'threshold_{threshold:.1f}',family='threshold',kind='threshold',
            label=f'Threshold slowdown · {threshold:.1f} L',options=dict(threshold=threshold)))
    return values


def averages(rows):return {m:float(np.mean([float(r[m]) for r in rows])) for m in METRICS}


def selection(rows,variants):
    stats={v['id']:averages([r for r in rows if r['variant']==v['id']]) for v in variants}
    chosen=[]
    for family in ('forecast','pi','threshold'):
        group=[v for v in variants if v['family']==family]
        eligible=[v for v in group if stats[v['id']]['low_reservoir_s']<=1. and
                  stats[v['id']]['empty_request_s']<=1.]
        key=(lambda v:(stats[v['id']]['deficit_auc'],group.index(v))) if eligible else (
            lambda v:(stats[v['id']]['low_reservoir_s'],stats[v['id']]['empty_request_s'],
                      stats[v['id']]['deficit_auc'],group.index(v)))
        winner=dict(min(eligible or group,key=key));winner['eligible_development_budget']=bool(eligible)
        winner['candidate_id']=winner['id'];winner['id']=family;chosen.append(winner)
    return dict(candidate_means=stats,selected=chosen)


def parameters(seed,final):
    rng=np.random.default_rng(seed+60000)
    start=float(rng.uniform(.15,.5) if final else rng.uniform(.2,.55))
    return dict(patient=vars(Patient.sampled(seed)),event_start=start,
        event_end=start+float(rng.uniform(.2,.32) if final else rng.uniform(.18,.3)))


def run(seed,sensor,plant,reference,variant,final):
    param=parameters(seed,final)
    scenario=StressScenario(sensor,dilution=1.8,drainage=.35 if final else .4,
        event_start=param['event_start'],event_end=param['event_end'],
        **(FINAL_SENSORS if final else DEV_SENSORS)[sensor])
    return simulate(scenario,'sentinel',seed,patient=Patient(**param['patient']),
        plant_options=(FINAL_PLANTS if final else DEV_PLANTS)[plant],
        controller_kind=variant['kind'],controller_options=variant['options'],
        level_mode='hold',level_reference_options=REFERENCES[reference])


def main():
    OUT.mkdir(parents=True,exist_ok=True);variants=candidates()
    protocol=dict(version='1.5.0',development_seeds=list(range(11000,11008)),
        evaluation_seeds=list(range(12000,12016)),candidates=variants,
        development_sensors=DEV_SENSORS,final_sensors=FINAL_SENSORS,
        development_plants=DEV_PLANTS,final_plants=FINAL_PLANTS,references=REFERENCES,
        development_runs=2464,evaluation_runs=4032,total_runs=6496,
        selection='Within each family select lowest mean deficit among candidates with development mean low reservoir <=1 s and empty requests <=1 s. If no candidate qualifies, retain least low-reservoir/empty-request/deficit in that order and mark unmatched. Ties follow candidate order.',
        primary='PI minus forecast on good reference: upper paired 95% intervals <=1 s for low reservoir/empty requests and <=5 s for high pressure, plus deficit upper interval <0.',
        primary_tolerances=dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.),
        scope='Engineering comparison tolerances, not clinical noninferiority/safety margins',
        common_information='All methods use identical reference schedules/noise/dropout and Hb/saturation/pressure. PI and threshold intentionally ignore measured flow/inferred drainage.',
        pressure_handling='Forecast predicts pressure using measured-flow resistance; feedback baselines slow down on direct pressure above 90 mmHg. High pressure outcome threshold remains 95 mmHg.',
        duration=1200.,dt=2.,weighting='Equal challenge weights, not clinical prevalence',
        bootstrap=dict(repetitions=2000,seed=2026,unit='paired patient seed after within-seed cell averaging'),
        replay_cells=REPLAYS,replay_seed=12000,
        limitations=['No novel PI/threshold algorithm claimed.',
            'No clinical data or reservoir bench time series used for validation.',
            'The formal reduced-model result is not a full-system safety proof.',
            'No assertion of journal acceptance or established scientific priority.'])
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    params={phase:{str(seed):parameters(seed,phase=='evaluation') for seed in protocol[key]}
            for phase,key in [('development','development_seeds'),('evaluation','evaluation_seeds')]}
    (OUT/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    records=[];development=[]
    def record(result,phase,sensor,plant,reference,seed,vid):
        row=dict(phase=phase,sensor_case=sensor,plant_case=plant,reference_case=reference,
                 seed=seed,variant=vid,**result['metrics'])
        records.append(row);return row
    for sensor in DEV_SENSORS:
        for plant in DEV_PLANTS:
            for seed in protocol['development_seeds']:
                for variant in variants:
                    r=run(seed,sensor,plant,'good',variant,False)
                    development.append(record(r,'development',sensor,plant,'good',seed,variant['id']))
        print('Development:',sensor,flush=True)
    chosen=selection(development,variants)
    (OUT/'selection.json').write_text(json.dumps(chosen,indent=2)+'\n')
    frozen=hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()
    selected=chosen['selected'];replay={};labels={};descriptions={}
    for reference in REFERENCES:
        for sensor in FINAL_SENSORS:
            for plant in FINAL_PLANTS:
                cell=f'{sensor}__{plant}__{reference}'
                labels[cell]=f'{sensor.replace("_"," ")} · {plant} · {reference} ref'
                descriptions[cell]=('Frozen stronger-baseline test: '+labels[cell]+
                    '. Every controller receives the same reference channel. PI and threshold '
                    'use level/Hb/saturation/direct pressure and do not read flow measurement or inferred drainage.')
                for seed in protocol['evaluation_seeds']:
                    for variant in selected:
                        r=run(seed,sensor,plant,reference,variant,True)
                        record(r,'evaluation',sensor,plant,reference,seed,variant['id'])
                        if cell in REPLAYS and seed==protocol['replay_seed']:
                            indices=sorted(set(range(0,len(r['rows']),3))|{len(r['rows'])-1})
                            fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',
                                pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',
                                level_sensor='observed_reservoir',level_lower='level_reference_lower')
                            view={key:[round(r['rows'][i][field],4) if isinstance(r['rows'][i][field],float)
                                else r['rows'][i][field] for i in indices] for key,field in fields.items()}
                            view['metrics']=r['metrics'];replay[cell+'/'+variant['id']]=view
        print('Final reference regime:',reference,flush=True)
    assert len(records)==6496
    assert hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()==frozen
    with (OUT/'metrics.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(records)
    evaluation=[r for r in records if r['phase']=='evaluation']
    groups={group:{v['id']:averages([r for r in evaluation if r['variant']==v['id'] and
        (group=='pooled' or r['reference_case']==group)]) for v in selected} for group in [*REFERENCES,'pooled']}
    cells={f'{sensor}__{plant}__{reference}':{v['id']:averages([r for r in evaluation if
        r['variant']==v['id'] and r['sensor_case']==sensor and r['plant_case']==plant and r['reference_case']==reference])
        for v in selected} for reference in REFERENCES for sensor in FINAL_SENSORS for plant in FINAL_PLANTS}
    comparisons=[]
    for group in [*REFERENCES,'pooled']:
        subset=[r for r in evaluation if group=='pooled' or r['reference_case']==group]
        for vid in ('pi','threshold'):
            for metric in METRICS:
                def blocks(method):return [float(np.mean([r[metric] for r in subset if
                    r['variant']==method and r['seed']==seed])) for seed in protocol['evaluation_seeds']]
                comparisons.append(dict(group=group,variant=vid,baseline='forecast',metric=metric,
                    **paired_interval([a-b for a,b in zip(blocks(vid),blocks('forecast'))])))
    primary={c['metric']:c for c in comparisons if c['group']=='good' and c['variant']=='pi'}
    protected=all(primary[m]['high']<=tolerance for m,tolerance in protocol['primary_tolerances'].items())
    oxygen=primary['deficit_auc']['high']<0.
    summary=dict(methods=selected,group_means=groups,cell_means=cells,comparisons=comparisons,
        selection_sha256=frozen,verdict=dict(primary='pi versus forecast on good reference',
        protection_criterion=protected,oxygen_criterion=oxygen,demonstrated=protected and oxygen,
        answer='demonstrated_in_this_synthetic_test' if protected and oxygen else 'not_demonstrated'))
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (OUT/'environment.json').write_text(json.dumps(dict(python=sys.version,numpy=np.__version__,platform=platform.platform()),indent=2)+'\n')
    web_comparisons=[]
    for cell in REPLAYS:
        sensor,plant,reference=cell.split('__')
        subset=[r for r in evaluation if r['sensor_case']==sensor and r['plant_case']==plant and r['reference_case']==reference]
        for vid in ('pi','threshold'):
            a={r['seed']:r['deficit_auc'] for r in subset if r['variant']==vid}
            b={r['seed']:r['deficit_auc'] for r in subset if r['variant']=='forecast'}
            web_comparisons.append(dict(scenario=cell,variant=vid,metric='deficit_auc',
                **paired_interval([a[seed]-b[seed] for seed in protocol['evaluation_seeds']])))
    web=dict(protocol=dict(n=16,start_seed=12000,scenarios=REPLAYS,default_policy='pi',baseline_label='Tuned forecast'),
        variants=selected,labels={c:labels[c] for c in REPLAYS},descriptions={c:descriptions[c] for c in REPLAYS},
        comparisons=web_comparisons,runs={})
    (ROOT/'web/submission-data.js').write_text('/* Generated frozen comparison. */\nconst SUBMISSION_STUDY = '+json.dumps(web,separators=(',',':'))+';\n')
    for cell in REPLAYS:
        subset={key:value for key,value in replay.items() if key.startswith(cell+'/')}
        (ROOT/f'web/submission-{cell}.js').write_text('/* Prespecified seed 12000. */\nObject.assign(SUBMISSION_STUDY.runs,'+json.dumps(subset,separators=(',',':'))+');\n')
    print('Completed',len(records),'runs. Verdict:',summary['verdict'],flush=True)

if __name__=='__main__':main()
