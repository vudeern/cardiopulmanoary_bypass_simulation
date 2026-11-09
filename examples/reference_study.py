"""Test whether reference credibility adds value beyond simple correction.

The simple correction is selected on development seeds only. Final fault
magnitudes, timings and plant settings differ from development. Reference
regimes include deliberate violations of independence and calibration.
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

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/reference-study'
METRICS=('low_reservoir_s','empty_request_s','deficit_auc','high_pressure_s',
         'false_reassurance_s','mean_flow')
DEVELOPMENT_SENSORS={
 'clean':dict(level_profile='none'), 'step':dict(level_profile='step',reservoir_bias=.4),
 'drift':dict(level_profile='ramp',reservoir_bias=.4),
 'initial':dict(level_profile='initial',reservoir_bias=.4),
 'small_step':dict(level_profile='step',reservoir_bias=.1),
 'flow_high':dict(level_profile='none',flow_bias=.75),
 'flow_low':dict(level_profile='none',flow_bias=-.75),
 'drift_flow':dict(level_profile='ramp',reservoir_bias=.4,flow_bias=.75),
 'noisy':dict(level_profile='none',noise_scale=10.)}
FINAL_SENSORS={
 'clean':dict(level_profile='none'), 'step':dict(level_profile='step',reservoir_bias=.5),
 'drift':dict(level_profile='ramp',reservoir_bias=.5,drift_duration=.2),
 'initial':dict(level_profile='initial',reservoir_bias=.5),
 'flow_high':dict(level_profile='none',flow_bias=.9),
 'drift_flow':dict(level_profile='ramp',reservoir_bias=.5,drift_duration=.2,flow_bias=.9),
 'noisy':dict(level_profile='none',noise_scale=12.)}
DEVELOPMENT_PLANTS={'reference':{},'slow_pump':dict(actuator_tau=8.)}
FINAL_PLANTS={'reference':{},'slow_pump':dict(actuator_tau=6.),
              'lagged':dict(drainage_tau=18.,venous_nonlinearity=.06)}
REFERENCES={
 'good':dict(period=60.,delay=4.,noise_sd=.01),
 'noisy':dict(period=60.,delay=4.,noise_sd=.05),
 'delayed':dict(period=90.,delay=30.,noise_sd=.01),
 'dropout':dict(period=60.,delay=4.,noise_sd=.01,dropout_prob=.25,
                outage_start=360.,outage_end=840.),
 'biased':dict(period=60.,delay=4.,noise_sd=.01,bias=.15),
 'common_mode':dict(period=60.,delay=4.,noise_sd=.01,common_mode_fraction=1.)}
OBSERVER=dict(base_allowance=.04,drift_allowance=.003,max_age=180.)
REPLAYS=['initial__reference__good','drift__lagged__good','flow_high__reference__good',
         'drift__reference__dropout','initial__reference__biased','drift__reference__common_mode']


def method(vid,label,mode='ignore',margin=0.,policy='sentinel'):
    return dict(id=vid,label=label,family='reference',level_mode=mode,policy=policy,
                options=dict(reserve_margin=margin) if margin else {})


def parameters(seed,final):
    rng=np.random.default_rng(seed+40000)
    start=float(rng.uniform(.2,.55) if final else rng.uniform(.25,.5))
    end=start+float(rng.uniform(.18,.3) if final else rng.uniform(.15,.25))
    return dict(patient=vars(Patient.sampled(seed)),event_start=start,event_end=end)


def run(seed,sensor,plant,reference,variant,final):
    param=parameters(seed,final)
    scenario=StressScenario(sensor,dilution=1.8,drainage=.4 if final else .45,
        event_start=param['event_start'],event_end=param['event_end'],
        **(FINAL_SENSORS if final else DEVELOPMENT_SENSORS)[sensor])
    return simulate(scenario,variant['policy'],seed,patient=Patient(**param['patient']),
        plant_options=(FINAL_PLANTS if final else DEVELOPMENT_PLANTS)[plant],
        controller_options=variant['options'],level_mode=variant['level_mode'],
        level_reference_options=REFERENCES[reference],level_observer_options=OBSERVER)


def averages(rows):return {m:float(np.mean([float(r[m]) for r in rows])) for m in METRICS}


def choose_simple(rows,candidates):
    stats={v['id']:averages([r for r in rows if r['variant']==v['id']]) for v in candidates}
    budget=stats['bounded_reference']
    simple=[v for v in candidates if v['level_mode']=='hold']
    eligible=[v for v in simple if all(stats[v['id']][m]<=budget[m]+1e-9
              for m in ('low_reservoir_s','empty_request_s'))]
    key=(lambda v:(stats[v['id']]['deficit_auc'],simple.index(v))) if eligible else (
        lambda v:(stats[v['id']]['low_reservoir_s'],stats[v['id']]['empty_request_s'],
                  stats[v['id']]['deficit_auc'],simple.index(v)))
    return dict(candidate_means=stats,budget=budget,matched_development_budget=bool(eligible),
                selected=min(eligible or simple,key=key))


def evaluate_verdict(comparisons):
    # Comparisons are simple minus bounded, so negating swaps direction.
    primary={c['metric']:c for c in comparisons if c['group']=='good' and c['variant']=='simple_reference'}
    risk=all(-primary[m]['low']<=1. for m in ('low_reservoir_s','empty_request_s'))
    deficit=primary['deficit_auc']['low']>0.
    return dict(question='Does age-based credibility outperform a tuned simple reference correction?',
        primary_group='good',risk_upper_difference_tolerance_s=1.,
        risk_criterion_pass=risk,deficit_criterion_pass=deficit,
        demonstrated=risk and deficit,
        answer='demonstrated_on_primary_synthetic_test' if risk and deficit else 'not_demonstrated',
        criteria='Bounded minus simple upper 95% paired interval <= 1 s for both low reservoir and empty requests; simple minus bounded lower interval > 0 for deficit AUC. One primary test; other comparisons descriptive.')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    bounded=method('bounded_reference','Age-based reference bound','bounded')
    candidates=[method(f'hold_{m:.2f}',f'Simple reference +{m:.2f} L','hold',m)
                for m in (0.,.05,.1,.2,.3,.4)]+[bounded]
    protocol=dict(version='1.4.0',development_seeds=list(range(9000,9008)),
        evaluation_seeds=list(range(10000,10012)),development_sensors=DEVELOPMENT_SENSORS,
        final_sensors=FINAL_SENSORS,development_plants=DEVELOPMENT_PLANTS,final_plants=FINAL_PLANTS,
        references=REFERENCES,observer=OBSERVER,candidates=candidates,
        development_reference='good',primary_reference='good',duration=1200.,dt=2.,
        development_runs=1008,evaluation_runs=7560,total_runs=8568,
        selection='Select simple reference margin with lowest development deficit among those meeting bounded low-reservoir/empty-request means. If unmatched, rank by low reservoir, empty requests, deficit, declared order. No selection uses final data.',
        primary_question='Does age-based credibility beat a tuned simple correction with the same references?',
        primary_criteria='For good references, bounded minus simple upper 95% paired interval <= 1 s for both depletion metrics, and simple minus bounded lower interval > 0 for oxygen deficit.',
        weighting='Equal cell weights within reference regime; not clinical prevalence',
        bootstrap=dict(repetitions=2000,seed=2026,unit='paired patient seed after within-seed averaging'),
        replay_cells=REPLAYS,replay_seed=10000,
        measurement_fairness='All methods receive the same reference sampling schedule/noise/dropout for each paired case. Ignore modes are explicit information ablations; both reference-aware methods use identical acquisitions.',
        final_changes='New seeds, sensor amplitudes, onset/window distribution, restriction severity, pump and drainage constants differ from development.',
        limitations=['Simulated reference hardware; no real accuracy or availability demonstrated.',
            'Engineering allowance is not a calibrated confidence bound.',
            'Common-mode and biased references deliberately violate independence/calibration.',
            'No claim of clinical effectiveness, scientific priority, patentability or market demand.'])
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    params={'development':{str(seed):parameters(seed,False) for seed in protocol['development_seeds']},
            'evaluation':{str(seed):parameters(seed,True) for seed in protocol['evaluation_seeds']}}
    (OUT/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    records=[];development=[]
    def record(result,phase,sensor,plant,reference,seed,vid):
        row=dict(phase=phase,sensor_case=sensor,plant_case=plant,reference_case=reference,
            seed=seed,variant=vid,**result['metrics'],
            level_reference_count=sum(r['level_reference'] is not None for r in result['rows']),
            level_reference_unknown_s=sum(r['level_reference_unknown'] is True for r in result['rows'])*2.)
        records.append(row);return row
    for sensor in DEVELOPMENT_SENSORS:
        for plant in DEVELOPMENT_PLANTS:
            for seed in protocol['development_seeds']:
                for v in candidates:
                    result=run(seed,sensor,plant,'good',v,False)
                    development.append(record(result,'development',sensor,plant,'good',seed,v['id']))
        print('Development:',sensor,flush=True)
    selection=choose_simple(development,candidates)
    (OUT/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    selected=dict(selection['selected']);selected['id']='simple_reference'
    variants=[method('original','Original · ignores level reference'),
              method('reserve','Fixed reserve +0.40 L · ignores reference',margin=.4),
              method('old_guard','Step guard · ignores reference',policy='sentinel_guarded'),selected,bounded]
    (OUT/'methods.json').write_text(json.dumps(variants,indent=2)+'\n')
    frozen=hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()
    replay={};labels={};descriptions={}
    for reference in REFERENCES:
        for sensor in FINAL_SENSORS:
            for plant in FINAL_PLANTS:
                cell=f'{sensor}__{plant}__{reference}'
                labels[cell]=f'{sensor.replace("_"," ")} · {plant.replace("_"," ")} · {reference.replace("_"," ")} ref'
                descriptions[cell]=(f'{sensor.replace("_"," ")} sensing with {plant.replace("_"," ")} dynamics '
                    f'and a {reference.replace("_"," ")} level reference. Reference acquisitions have their own '
                    'noise, time stamps and delivery times. All methods are locked before this evaluation.')
                for seed in protocol['evaluation_seeds']:
                    for v in variants:
                        result=run(seed,sensor,plant,reference,v,True)
                        record(result,'evaluation',sensor,plant,reference,seed,v['id'])
                        if cell in REPLAYS and seed==protocol['replay_seed']:
                            indices=sorted(set(range(0,len(result['rows']),3))|{len(result['rows'])-1})
                            fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',
                                pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',
                                level_sensor='observed_reservoir',level_lower='level_reference_lower')
                            view={key:[round(result['rows'][i][field],4) if isinstance(result['rows'][i][field],float)
                                else result['rows'][i][field] for i in indices] for key,field in fields.items()}
                            view['metrics']=result['metrics'];replay[cell+'/'+v['id']]=view
        print('Final reference regime:',reference,flush=True)
    assert len(records)==protocol['total_runs']
    assert hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest()==frozen
    with (OUT/'metrics.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(records)
    evaluation=[r for r in records if r['phase']=='evaluation']
    cell_means={f'{sensor}__{plant}__{reference}':{v['id']:averages([r for r in evaluation if
        r['sensor_case']==sensor and r['plant_case']==plant and r['reference_case']==reference and r['variant']==v['id']])
        for v in variants} for reference in REFERENCES for sensor in FINAL_SENSORS for plant in FINAL_PLANTS}
    group_means={group:{v['id']:averages([r for r in evaluation if r['variant']==v['id'] and
        (group=='pooled' or r['reference_case']==group)]) for v in variants} for group in [*REFERENCES,'pooled']}
    comparisons=[]
    for group in [*REFERENCES,'pooled']:
        rows=[r for r in evaluation if group=='pooled' or r['reference_case']==group]
        for v in variants:
            if v['id']=='bounded_reference':continue
            for metric in METRICS:
                def blocks(vid):
                    return [float(np.mean([r[metric] for r in rows if r['seed']==seed and r['variant']==vid]))
                            for seed in protocol['evaluation_seeds']]
                differences=[a-b for a,b in zip(blocks(v['id']),blocks('bounded_reference'))]
                comparisons.append(dict(group=group,variant=v['id'],baseline='bounded_reference',
                    metric=metric,**paired_interval(differences)))
    summary=dict(methods=variants,cell_means=cell_means,group_means=group_means,comparisons=comparisons,
                 verdict=evaluate_verdict(comparisons),selection_sha256=frozen)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (OUT/'environment.json').write_text(json.dumps(dict(python=sys.version,numpy=np.__version__,
        platform=platform.platform()),indent=2)+'\n')
    # Viewer cohort intervals are per selected replay cell, not group-wide.
    web_comparisons=[]
    for cell in REPLAYS:
        sensor,plant,reference=cell.split('__')
        rows=[r for r in evaluation if r['sensor_case']==sensor and r['plant_case']==plant and r['reference_case']==reference]
        for v in variants:
            if v['id']=='bounded_reference':continue
            a={r['seed']:r['deficit_auc'] for r in rows if r['variant']==v['id']}
            b={r['seed']:r['deficit_auc'] for r in rows if r['variant']=='bounded_reference'}
            web_comparisons.append(dict(scenario=cell,variant=v['id'],metric='deficit_auc',
                **paired_interval([a[seed]-b[seed] for seed in protocol['evaluation_seeds']])))
    web=dict(protocol=dict(n=12,start_seed=10000,scenarios=REPLAYS,default_policy='bounded_reference',
        baseline_label='Age-based reference bound'),variants=variants,
        labels={cell:labels[cell] for cell in REPLAYS},descriptions={cell:descriptions[cell] for cell in REPLAYS},
        comparisons=web_comparisons,runs={})
    (ROOT/'web/reference-data.js').write_text('/* Generated frozen evaluation. */\nconst REFERENCE_STUDY = '+json.dumps(web,separators=(',',':'))+';\n')
    for cell in REPLAYS:
        subset={key:value for key,value in replay.items() if key.startswith(cell+'/')}
        (ROOT/f'web/reference-{cell}.js').write_text('/* Prespecified seed 10000. */\nObject.assign(REFERENCE_STUDY.runs,'+json.dumps(subset,separators=(',',':'))+');\n')
    print('Completed',len(records),'runs. Selected margin:',selected['options'],'Answer:',summary['verdict'],flush=True)


if __name__=='__main__':main()
