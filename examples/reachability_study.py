"""rc.2 development only; never reads or executes reserved confirmation seeds."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import csv
import itertools
import json
from multiprocessing import get_context
from pathlib import Path
import numpy as np
from perfusion_lab.reachability_simulation import simulate_reachability
from perfusion_lab.model_simulation import simulate_model
from perfusion_lab.simulation import simulate
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from continuity_study import patient,write_csv
from integrity_study import PHYS,CALIBRATIONS,DEFAULT_GUARD
from model_bank_study import FAULTS,OLD_GUARD,DEV_PLANTS
from simc_benchmark import digest,dumps

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/reachability-development'
SEEDS=tuple(range(37000,37032))
PRIMARY_FAULTS=('clean','positive_start','step','outage')
METRICS=('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s',
 'minimum_reservoir','flow_variation','mean_flow','volume_mae_L',
 'lower_undercoverage_s','mean_halfwidth_L','bank_supported_s','bank_conflict_s')
SOURCES=('src/perfusion_lab/reachability.py','src/perfusion_lab/reachability_runtime.py',
 'src/perfusion_lab/reachability_simulation.py','src/perfusion_lab/runtime.py',
 'src/perfusion_lab/runtime_simulation.py','src/perfusion_lab/model_bank.py',
 'src/perfusion_lab/model_simulation.py','src/perfusion_lab/integrity.py',
 'src/perfusion_lab/simulation.py','src/perfusion_lab/model.py','src/perfusion_lab/stress.py',
 'src/perfusion_lab/sensing.py','src/perfusion_lab/reference.py','src/perfusion_lab/simc.py',
 'src/perfusion_lab/braking.py','examples/continuity_study.py','examples/integrity_study.py',
 'examples/model_bank_study.py','examples/reachability_study.py')
REPLAY_CELLS=(('clean','nominal','clean','good'),('combined','slow','step','good'),
 ('combined','slow','outage','good'),('combined','nominal','positive_start','missing'),
 ('combined','nominal','positive_start','biased'),('combined','nominal','positive_start','shared'))


def methods():
    common={**OLD_GUARD,'calibration_error':.04,'model_error_flow':.03}
    result={}
    for name,interval,reserve in (('legacy_common','legacy','legacy'),
        ('interval_only','consistent','legacy'),('reserve_only','legacy','joint'),
        ('combined','consistent','joint')):
        result[name]=dict(engine='reach',kind='integrity_hybrid',
            guard={**common,'interval_mode':interval},
            options=dict(recovery_floor=.45,reserve_mode=reserve),family='candidate')
    for observer in ('legacy','consistent'):
        for tau,level in itertools.product((1.5,5.,20.),(.35,.5,.65,.8)):
            result[f'pi_{observer}_{tau}_{level}']=dict(engine='reach',kind='integrity_pi',
                guard={**common,'interval_mode':observer},
                options=dict(tau_c=tau,target_level=level,reserve_mode='legacy'),family='pi',observer=observer)
    previous=json.loads((ROOT/'results/model-bank-study/selection.json').read_text())
    result['frozen_v1']=dict(engine='v1',kind='integrity_hybrid',family='reference',**previous['selected']['configuration'])
    result['frozen_calibration_pi']={**previous['calpi'],'family':'pi','observer':'calibration_only'}
    return result


def run(seed,phys,plant,fault,cal,method):
    params=dict(PHYS[phys]);bias=params.pop('venous_bias',0.)
    calibration=dict(CALIBRATIONS[cal])
    if cal=='shared':calibration.update(FAULTS[fault])
    engine={'reach':simulate_reachability,'v1':simulate_model,'old':simulate}[method['engine']]
    result=engine(StressScenario(phys,**params),'sentinel',seed=seed,duration=600.,dt=1.,
        patient=patient(seed,'evaluation'),controller_kind=method['kind'],
        controller_options=method['options'],reference_guard_options=method['guard'],
        plant_options=DEV_PLANTS[plant],venous_measurement=dict(noise_sd=.015,bias=bias),
        level_mode=method.get('mode','screened'),
        level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),
        reference_fault_options=dict(FAULTS[fault]),calibration_options=calibration)
    truth=.85;errors=[];under=0
    for row in result['rows']:
        errors.append(abs(row['level_reference_estimate']-truth))
        under+=row['level_reference_lower']>truth+1e-9
        truth=row['reservoir']
    result['metrics'].update(volume_mae_L=float(np.mean(errors)),lower_undercoverage_s=float(under),
        mean_halfwidth_L=float(np.mean([r['reference_uncertainty'] for r in result['rows']])),
        bank_supported_s=float(sum(r.get('bank_supported',False) for r in result['rows'])),
        bank_conflict_s=float(sum(r.get('bank_conflict',False) for r in result['rows'])))
    return result


def protocol():
    value=dict(version='2.0.0rc2',stage='development_only',development_seeds=list(SEEDS),
        confirmation_seeds_executed=[],duration_s=600.,dt_s=1.,
        physiology=PHYS,plants=DEV_PLANTS,primary_faults={f:FAULTS[f] for f in PRIMARY_FAULTS},
        calibrations=CALIBRATIONS,methods=methods(),metrics=list(METRICS),replay_cells=REPLAY_CELLS,
        primary_runs=15360,secondary_runs=3072,
        mechanism='Four paired arms hold calibration_error=.04, model_error_flow=.03, recovery_floor=.45 fixed: legacy, interval only, joint reserve only, both. Frozen selected v1 (.02 calibration allowance) is an additional reference, not the isolation control.',
        information='Measurement-only runtime. Feasible (offset, constant venous bias) polygons per generic pump model from at most four delivered calibration anchors. Allowed model-flow error grows with anchor separation and forecast age. Inline overlap does not trim the independent set; disjoint unquarantined information disables recovery and widens to a union. Missing/stale/inconsistent calibration falls back to PI.',
        reserve='Maximum cumulative net volume loss over one candidate command followed by full slew-limited braking to zero, including an exact geometric infinite tail, maximized over retained pump hypotheses. Conditional on a retained correct model and future inflow >= causal lower estimate. No future drainage supplied.',
        selection='Eligibility separately in clean/bias/outage groups: mean low-reservoir <=1s and zero empty requests across primary runs. Candidate chosen among four mechanism arms by lowest overall oxygen deficit, or lexicographic low/empty/deficit marked ineligible. PI independently tuned on 24 settings (two observers x three gains x four setpoints), plus frozen calibration-only PI; same eligibility and oxygen ranking. Retain every result. Paired intervals use patient-level cell means; development selection makes them exploratory.',
        secondary='After development selection, all five hybrid/reference arms plus selected PI for each of three observer families on missing, biased and shared calibration; positive-start routine bias, both physiology/plant families, all 32 development seeds. Secondary results never determine selection.',
        raw_reference_convention='Reference samples preserve signed finite Gaussian readings, including small negative values near an empty reservoir; they are measurements, not physical true volumes. The new runtime validates timestamps and finiteness while allowing those signed raw readings. An earlier interrupted run, its 12 complete patients and frozen sources are archived in results/reachability-interrupted-rc2; the full rerun uses the same seeds, methods, settings and gates.',
        limitations='This is a development experiment using known scenario/model families and new seeds, not a fresh confirmation or validated patient population. Gaussian errors are unbounded, generic pump grid may miss the true dynamics, venous bias may change, and shared corruption can invalidate the sets. No guaranteed coverage, clinical validation, novelty or overall superiority is assumed.',
        source_hashes={n:digest(ROOT/n) for n in SOURCES})
    path=OUT/'protocol.json'
    if path.exists():assert json.loads(path.read_text())==json.loads(dumps(value)),'Frozen development protocol changed; archive before revising'
    else:OUT.mkdir(parents=True,exist_ok=True);path.write_text(dumps(value))
    return value


def worker(task):
    stage,seed,chosen=task;rows=[]
    for phys,plant in itertools.product(PHYS,DEV_PLANTS):
        cells=((f,'good') for f in PRIMARY_FAULTS) if stage=='primary' else (('positive_start',c) for c in ('missing','biased','shared'))
        for fault,cal in cells:
            for name,method in chosen.items():
                result=run(seed,phys,plant,fault,cal,method)
                rows.append(dict(seed=seed,phys=phys,plant=plant,fault=fault,calibration=cal,method=name,
                    **{m:result['metrics'][m] for m in METRICS}))
    return rows


def grid(stage,chosen):
    protocol();directory=OUT/stage;directory.mkdir(exist_ok=True)
    pending=[seed for seed in SEEDS if not (directory/f'{seed}.csv').exists()]
    with ProcessPoolExecutor(max_workers=4,mp_context=get_context('spawn')) as pool:
        futures={pool.submit(worker,(stage,seed,chosen)):seed for seed in pending}
        for future in as_completed(futures):
            seed=futures[future];rows=future.result()
            write_csv(directory/f'{seed}.csv',rows)
            print(stage,'patient complete',seed,'runs',len(rows),flush=True)


def read_rows(stage):
    rows=[]
    for seed in SEEDS:
        path=OUT/stage/f'{seed}.csv'
        with path.open() as handle:
            for row in csv.DictReader(handle):
                row['seed']=int(row['seed'])
                for m in METRICS:row[m]=float(row[m])
                rows.append(row)
    return rows


def group(row,name):
    return row['calibration']=='good' and (row['fault']=='clean' if name=='clean' else row['fault']=='outage' if name=='outage' else row['fault'] in ('positive_start','step'))


def means(rows):
    return {m:float(np.mean([r[m] for r in rows])) for m in METRICS}


def select(rows):
    catalog=methods();stats={}
    for name in catalog:
        block=[r for r in rows if r['method']==name]
        grouped={g:means([r for r in block if group(r,g)]) for g in ('clean','bias','outage')}
        stats[name]=dict(means=means(block),groups=grouped,
            eligible=all(v['low_reservoir_s']<=1. for v in grouped.values()) and all(r['empty_request_s']==0 for r in block))
    def choose(names):
        eligible=[n for n in names if stats[n]['eligible']]
        def rank(n):
            m=stats[n]['means']
            return (m['deficit_auc'],names.index(n)) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['deficit_auc'],names.index(n))
        return min(eligible or names,key=rank)
    candidate=choose([n for n,m in catalog.items() if m['family']=='candidate'])
    comparator=choose([n for n,m in catalog.items() if m['family']=='pi'])
    by_observer={o:choose([n for n,m in catalog.items() if m.get('observer')==o]) for o in ('legacy','consistent','calibration_only')}
    return dict(candidate=candidate,comparator=comparator,pi_by_observer=by_observer,
        candidate_eligible=stats[candidate]['eligible'],comparator_eligible=stats[comparator]['eligible'],all_methods=stats)


def summarize():
    p=protocol();primary=read_rows('primary');selection=select(primary)
    (OUT/'selection.json').write_text(dumps(selection))
    comparisons=[]
    for name in ('legacy_common','interval_only','reserve_only','combined',selection['comparator']):
        if name==selection['candidate']:continue
        for g in ('clean','bias','outage'):
            for metric in METRICS:
                diffs=[]
                for seed in SEEDS:
                    block=[r for r in primary if r['seed']==seed and group(r,g)]
                    a=means([r for r in block if r['method']==selection['candidate']])[metric]
                    b=means([r for r in block if r['method']==name])[metric]
                    diffs.append(a-b)
                comparisons.append(dict(baseline=name,group=g,metric=metric,**paired_interval(diffs)))
    gates={}
    for g in ('clean','bias','outage'):
        a=selection['all_methods'][selection['candidate']]['groups'][g]
        b=selection['all_methods'][selection['comparator']]['groups'][g]
        c={v['metric']:v for v in comparisons if v['baseline']==selection['comparator'] and v['group']==g}
        gates[g]=dict(oxygen_mean_10_percent=a['deficit_auc']<=.9*b['deficit_auc'],
            oxygen_paired_interval=c['deficit_auc']['high']<0,
            mean_low_reservoir=a['low_reservoir_s']<=1.,
            zero_empty_requests=all(r['empty_request_s']==0 for r in primary if r['method']==selection['candidate'] and group(r,g)),
            extra_low_reservoir=c['low_reservoir_s']['high']<=1.,
            extra_empty_requests=c['empty_request_s']['high']<=1.,
            extra_high_pressure=c['high_pressure_s']['high']<=5.)
    secondary=read_rows('secondary') if (OUT/'secondary/37031.csv').exists() else []
    secondary_means={cal:{n:means([r for r in secondary if r['calibration']==cal and r['method']==n]) for n in sorted({r['method'] for r in secondary})} for cal in ('missing','biased','shared')} if secondary else {}
    summary=dict(version='2.0.0rc2',stage='development_only',patients=32,
        primary_runs=len(primary),secondary_runs=len(secondary),candidate=selection['candidate'],
        comparator=selection['comparator'],candidate_eligible=selection['candidate_eligible'],comparator_eligible=selection['comparator_eligible'],
        development_gates=gates,development_joint_success=selection['candidate_eligible'] and selection['comparator_eligible'] and all(all(g.values()) for g in gates.values()),
        method_means=selection['all_methods'],secondary_means=secondary_means,comparisons=comparisons,
        version2_ready=False,qualifying_confirmation_cohorts=0,confirmation_seeds_executed=[],
        clinical_validation=False,novelty_established=False,
        protocol_sha256=digest(OUT/'protocol.json'),selection_sha256=digest(OUT/'selection.json'))
    (OUT/'summary.json').write_text(dumps(summary))
    print(dumps({k:summary[k] for k in ('candidate','comparator','candidate_eligible','comparator_eligible','development_gates','development_joint_success','primary_runs','secondary_runs')}),flush=True)
    return selection


def secondary():
    selection=summarize();catalog=methods()
    names=[n for n,m in catalog.items() if m['family'] in ('candidate','reference')]+list(selection['pi_by_observer'].values())
    grid('secondary',{n:catalog[n] for n in names});summarize()


def replays():
    selection=json.loads((OUT/'selection.json').read_text());catalog=methods();runs={}
    names=list(dict.fromkeys((selection['candidate'],selection['comparator'],'frozen_v1')))
    for phys,plant,fault,cal in REPLAY_CELLS:
        cell='__'.join((phys,plant,fault,cal))
        for name in names:
            result=run(37000,phys,plant,fault,cal,catalog[name]);rows=result['rows'][::3]
            if rows[-1] is not result['rows'][-1]:rows.append(result['rows'][-1])
            fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',
                infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
            runs[cell+'/'+name]={k:[r[v] for r in rows] for k,v in fields.items()}
            runs[cell+'/'+name]['metrics']=result['metrics']
    (OUT/'replays.json').write_text(dumps(runs))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('primary','secondary','summarize','replays'),required=True)
    args=parser.parse_args()
    if args.stage=='primary':grid('primary',methods());summarize()
    elif args.stage=='secondary':secondary()
    elif args.stage=='replays':replays()
    else:summarize()
