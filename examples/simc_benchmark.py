"""Frozen, simulation-only comparison against a verified general PI reference.

All output stays as engineering logs and replay data. No paper draft is written.
"""
import csv
import hashlib
import json
from pathlib import Path
from dataclasses import asdict
import numpy as np
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate
from perfusion_lab.benchmark import paired_interval

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/simc-benchmark'
METRICS=('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s','flow_variation','mean_flow')
DEV_CASES={
    'clean':dict(dilution=0.,drainage=1.),
    'drainage':dict(drainage=.5),
    'level_drift':dict(level_profile='ramp',reservoir_bias=.3,drift_duration=.3),
    'hb_bias':dict(drainage=1.,hb_bias=1.8,dilution=1.8)}
FINAL_CASES={
    'clean':dict(dilution=0.,drainage=1.),
    'drainage':dict(drainage=.35,event_start=.32,event_end=.73),
    'hb_bias':dict(drainage=1.,hb_bias=2.4,dilution=2.2),
    'level_drift':dict(level_profile='ramp',reservoir_bias=.5,drift_duration=.2),
    'level_initial':dict(level_profile='initial',reservoir_bias=.5),
    'arterial_flow_bias':dict(drainage=1.,flow_bias=1.1),
    'venous_flow_bias':dict(drainage=1.,venous_bias=.6),
    'combined':dict(level_profile='ramp',reservoir_bias=.5,drift_duration=.2,
        flow_bias=1.1,venous_bias=.6,drainage=.35,hb_bias=2.4,dilution=2.2,dropout=True,noise_scale=4.)}
DEV_PLANTS={'nominal':{},'slow':dict(actuator_tau=6.)}
FINAL_PLANTS={'nominal':{},'slow':dict(actuator_tau=7.),
              'lagged':dict(actuator_tau=5.,drainage_tau=18.,venous_nonlinearity=.06)}
REFS={'good':dict(period=60.,delay=4.,noise_sd=.01),
      'delayed_loss':dict(period=90.,delay=30.,noise_sd=.02,dropout_prob=.25,outage_start=180.,outage_end=420.)}
REPLAYS=('clean__nominal__good','drainage__nominal__good','venous_flow_bias__nominal__good',
         'level_initial__slow__good','combined__lagged__good','combined__lagged__delayed_loss')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dumps(value):
    def default(x):
        if isinstance(x,np.generic):return x.item()
        raise TypeError(type(x).__name__)
    return json.dumps(value,indent=2,allow_nan=False,default=default)+'\n'


def candidates():
    return ([dict(id=f'simc_{tau}_{level}',family='simc',kind='simc',
                options=dict(tau_c=tau,target_level=level))
            for tau in (5.,10.,20.,40.) for level in (.45,.65)] +
            [dict(id=f'forecast_{margin:.1f}',family='forecast',kind='matched_forecast',
                options=dict(reserve_margin=margin/10.)) for margin in range(8)])


def final_patient(seed):
    # Deliberately wider synthetic ranges, never a fitted clinical population.
    rng=np.random.default_rng(seed+90000)
    return Patient(bsa=float(rng.uniform(1.4,2.3)),hb=float(rng.uniform(7.8,11.)),
                   resistance=float(rng.uniform(10.,20.)),compliance=float(rng.uniform(.0012,.0025)),
                   venous_compliance=float(rng.uniform(.09,.15)),
                   venous_resistance=float(rng.uniform(.75,1.1)))


def run(phase,case,plant,reference,seed,method,dt=1.):
    conf=dict((DEV_CASES if phase=='development' else FINAL_CASES)[case]);bias=conf.pop('venous_bias',0.)
    sc=StressScenario(case,**conf)
    patient=Patient.sampled(seed) if phase=='development' else final_patient(seed)
    plants=DEV_PLANTS if phase=='development' else FINAL_PLANTS
    return simulate(sc,'sentinel',seed=seed,duration=600.,dt=dt,patient=patient,
        controller_kind=method['kind'],controller_options=method['options'],
        plant_options=plants[plant],venous_measurement=dict(noise_sd=.015,bias=bias),
        level_mode='hold',level_reference_options=REFS[reference])


def aggregate(records):return {k:float(np.mean([float(r[k]) for r in records])) for k in METRICS}

def choose(records,family):
    values=[v for v in candidates() if v['family']==family]
    means={v['id']:aggregate([r for r in records if r['method']==v['id']]) for v in values}
    eligible=[v for v in values if means[v['id']]['low_reservoir_s']<=1.
              and means[v['id']]['empty_request_s']<=1. and means[v['id']]['high_pressure_s']<=5.]
    def rank(v):
        m=means[v['id']]
        return ((m['deficit_auc'],values.index(v)) if eligible else
            (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],values.index(v)))
    return dict(method=min(eligible or values,key=rank),matched_development_budget=bool(eligible),means=means)


def comparisons(records,seeds):
    output=[]
    for ref in REFS:
        for metric in METRICS:
            # Resample patient blocks, preserving all artificial cases/plants.
            differences=[]
            for seed in seeds:
                a=[r for r in records if r['reference']==ref and r['seed']==seed and r['method']=='forecast']
                b=[r for r in records if r['reference']==ref and r['seed']==seed and r['method']=='simc']
                differences.append(np.mean([r[metric] for r in a])-np.mean([r[metric] for r in b]))
            output.append(dict(reference=ref,metric=metric,**paired_interval(differences)))
    return output


def criterion(comparison):
    selected={c['metric']:c for c in comparison if c['reference']=='good'}
    protection=all(selected[k]['high']<=v for k,v in
        dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())
    oxygen=selected['deficit_auc']['high']<0.
    return dict(protection_passed=protection,oxygen_passed=oxygen,
                demonstrated_joint_advantage=protection and oxygen,
                scope='Forecast minus SIMC under this frozen synthetic protocol. Engineering tolerances, not clinical margins.')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protocol=dict(reference='data/simc-reference/source.json',development_seeds=list(range(15000,15004)),
        evaluation_seeds=list(range(16000,16016)),duration_s=600.,dt_s=1.,candidates=candidates(),
        development_cases=DEV_CASES,final_cases=FINAL_CASES,development_plants=DEV_PLANTS,final_plants=FINAL_PLANTS,
        references=REFS,replay_cells=list(REPLAYS),
        primary='Good-reference regime: forecast must have upper paired CI <=+1 s low-reservoir, <=+1 s empty requests, <=+5 s high pressure, and deficit AUC upper CI <0.',
        selection='8 candidates/family, same development grid. Lowest deficit among candidates meeting mean exposure budgets (1 s low,1 s empty,5 s pressure). If none qualify, lexicographic low/empty/pressure/deficit and record unmatched.',
        paired_unit='Patient seed; cells are equally weighted artificial challenges, not clinical frequencies; 2000 bootstrap resamples, seed 2026.',
        final_patient_ranges='BSA1.4–2.3,Hb7.8–11,arterialR10–20,arterialC.0012–.0025,venousC.09–.15,venousR.75–1.1; synthetic choices.',
        shared='Sensors, observer/references, noisy measured venous flow, oxygen cap, direct pressure slowdown90, flow0–7,slew.15, initial2.4*BSA.',
        model_scope='General published PI tuning reproduced; synthetic CPB application adapted. No clinical controller/device equivalence.',
        source_hashes={name:digest(ROOT/name) for name in ('src/perfusion_lab/simc.py','src/perfusion_lab/simulation.py','data/simc-reference/source.json','examples/simc_benchmark.py')})
    (OUT/'protocol.json').write_text(dumps(protocol))
    records=[]
    for seed in protocol['development_seeds']:
        for case in DEV_CASES:
            for plant in DEV_PLANTS:
                for method in candidates():
                    result=run('development',case,plant,'good',seed,method)
                    records.append(dict(phase='development',case=case,plant=plant,reference='good',seed=seed,
                        method=method['id'],**{k:result['metrics'][k] for k in METRICS}))
    selection={f:choose(records,f) for f in ('simc','forecast')}
    (OUT/'selection.json').write_text(dumps(selection));selection_sha=digest(OUT/'selection.json')
    methods={f:s['method'] for f,s in selection.items()}
    for seed in protocol['evaluation_seeds']:
        for case in FINAL_CASES:
            for plant in FINAL_PLANTS:
                for reference in REFS:
                    for label,method in methods.items():
                        result=run('evaluation',case,plant,reference,seed,method)
                        records.append(dict(phase='evaluation',case=case,plant=plant,reference=reference,seed=seed,
                            method=label,**{k:result['metrics'][k] for k in METRICS}))
    with (OUT/'metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n');w.writeheader();w.writerows(records)
    final=[r for r in records if r['phase']=='evaluation']
    paired=comparisons(final,protocol['evaluation_seeds'])
    cells={}
    for case in FINAL_CASES:
        for plant in FINAL_PLANTS:
            for reference in REFS:
                cell=case+'__'+plant+'__'+reference
                cells[cell]={label:aggregate([r for r in final if r['case']==case and r['plant']==plant and r['reference']==reference and r['method']==label]) for label in methods}
    summary=dict(status='completed_frozen_simulation_comparison_against_verified_general_PI',
        development_runs=len(records)-len(final),evaluation_runs=len(final),selection_sha256=selection_sha,
        protocol_sha256=digest(OUT/'protocol.json'),methods=methods,
        group_means={ref:{label:aggregate([r for r in final if r['reference']==ref and r['method']==label]) for label in methods} for ref in REFS},
        cell_means=cells,comparisons=paired,primary=criterion(paired),
        general_PI_reference_verified=True,clinical_CPB_controller_reproduced=False,
        clinical_validation=False,novelty_established=False)
    (OUT/'summary.json').write_text(dumps(summary))
    runs={}
    for cell in REPLAYS:
        case,plant,reference=cell.split('__')
        for label,method in methods.items():
            result=run('evaluation',case,plant,reference,16000,method)
            fields={'t':'time','do2':'do2','monitor':'measured_do2','reservoir':'reservoir','pressure':'pressure',
                    'infeasible':'infeasible','fault':'fault','level_fault':'level_fault','level_sensor':'observed_reservoir','level_lower':'level_reference_lower'}
            selected=result['rows'][::3]
            if selected[-1] is not result['rows'][-1]:selected.append(result['rows'][-1])
            runs[cell+'/'+label]={k:[r[v] for r in selected] for k,v in fields.items()}
            runs[cell+'/'+label]['metrics']=result['metrics']
    (OUT/'replays.json').write_text(dumps(runs))
    # Source-independent timestep sensitivity: same selected settings, no retuning.
    refinement=[]
    for cell in REPLAYS:
        case,plant,reference=cell.split('__')
        for label,method in methods.items():
            for dt in (1.,.5):
                result=run('evaluation',case,plant,reference,16000,method,dt)
                refinement.append(dict(cell=cell,method=label,dt=dt,**{k:result['metrics'][k] for k in METRICS}))
    (OUT/'refinement.json').write_text(dumps(dict(
        scope='Sensitivity only. Sensor random draws/acquisition count change with dt; not a pure deterministic convergence proof.',rows=refinement)))
    print(f'Wrote {len(records)} runs; primary joint advantage={summary["primary"]["demonstrated_joint_advantage"]}.')


if __name__=='__main__':main()
