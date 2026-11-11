"""Fixed independent-envelope implementation study; reused development cases."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from contextlib import contextmanager
from copy import deepcopy
import csv
from dataclasses import asdict
import hashlib
from io import StringIO
import json
from multiprocessing import get_context
import zipfile
import numpy as np
import robust_v2_study as previous
from robust_v2_study import ROOT,SEEDS,PLANTS,CALS,NAMES,digest,save,patient,base
from perfusion_research.envelope_v2 import EnvelopeBudget,EnvelopeRuntime

OUT=ROOT/'results/v2-envelope'
EXTRAS=('inline_shared','no_contract')
FIELDS=tuple(dict.fromkeys(previous.FIELDS+('observed_reservoir','observed_flow','calibration_value',
    'calibration_acquired','legacy_command','legacy_cap','envelope_cap','envelope_lower','envelope_flow_upper',
    'envelope_contract_available','envelope_feasible','envelope_margin','envelope_clipped')))


def methods(condition):
    result=deepcopy(previous.methods());budget=asdict(EnvelopeBudget())
    if condition=='no_contract':budget.update(inline_error_L=None,anchor_error_L=None)
    for m in result.values():m['options']['envelope_budget']=dict(budget)
    return result


def parameters(condition):
    cal='shared' if condition=='inline_shared' else 'missing' if condition=='no_contract' else condition
    return cal,dict(reservoir_bias=.22,level_profile='initial') if condition=='inline_shared' else {}


@contextmanager
def envelope_runtime():
    original=base.runtime_module.CalibratedPumpRuntime;base.runtime_module.CalibratedPumpRuntime=EnvelopeRuntime
    try:yield
    finally:base.runtime_module.CalibratedPumpRuntime=original


def run(seed,plant,condition,name):
    if seed not in SEEDS or plant not in PLANTS or name not in NAMES or condition not in CALS+EXTRAS:raise ValueError('Outside fixed development matrix')
    if condition in EXTRAS and plant!='nominal':raise ValueError('Extras are nominal-pump diagnostic cases')
    cal,inline=parameters(condition);m=methods(condition)[name]
    with envelope_runtime():
        return base.simulate_calibrated_pump(base.ReturnChallenge(condition,windows=base.windows('repeated'),**inline),
            'sentinel',seed=seed,duration=600.,dt=1.,patient=patient(seed,'evaluation'),controller_kind='integrity_pi',
            controller_options=m['options'],reference_guard_options=m['guard'],plant_options=PLANTS[plant],
            venous_measurement=dict(noise_sd=.015,bias=0.),level_mode='screened',
            level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),
            reference_fault_options=dict(fault_bias=.22) if cal=='shared' else {},calibration_options=previous.calibration_options(cal))


def protocol():
    sources=set(json.loads((previous.OUT/'protocol.json').read_text())['source_hashes'])
    sources.update(('src/perfusion_research/envelope_v2.py','examples/envelope_v2_study.py'))
    value=dict(version_line='v2',version='2.0.0rc5',stage='independent_envelope_development',seeds=SEEDS,
        primary_plants=PLANTS,primary_calibrations=CALS,extras={c:dict(plant='nominal',parameters=parameters(c)) for c in EXTRAS},
        methods={c:methods(c) for c in CALS+EXTRAS},budget=asdict(EnvelopeBudget()),
        evaluations=136,new_simulations=72,retained_reference_runs=64,duration_s=600.,dt_s=1.,
        return_windows_s=base.windows('repeated'),
        design='Freeze before outcome runs. Add identical independent clipping envelope to both existing aggregate and joint fast-PI arms. Do not retune gains or alter old observer. Repeat full rc4 matrix and add nominal-pump all-channel +.22 L bias and no-declared-channel-contract cases. Same two reused development patients. No event schedule or fault truth enters controller.',
        contract='Engineering assumptions, not validated sensor specs: absolute inline and calibration errors each <=.30 L when their contract is available; fixed first-order motor tau in [1,20] s; initial motor flow within .10 L/min of configured 2.4*BSA; nonnegative return; exact applied-command acknowledgements; normal .15 L/min/s braking. Gaussian simulation errors have no deterministic coverage guarantee.',
        mechanism='Independent raw-inline lower bound and zero-inflow propagation of delayed absolute anchors; command-only interval motor tracking over full lag range, no fit pruning; full ramp and analytic infinite tail. Max of individually valid lower bounds stays valid only if the declared contracts hold. No bounds means maximum permitted braking and explicit unavailable status.',
        fairness='Identical envelope and budgets in both new PI arms. Retained unshielded rc4 runs illustrate the architecture change, not a same-contract MPC superiority claim. New assumed absolute inline bound and expanded lag envelope are disclosed. No default controller promotion.',
        startup='Original simulator starts with motor already at 2.4*BSA and .85 L volume. Worst-case stopping may be infeasible immediately. Log initial and subsequent uncertified steps; fallback cannot guarantee stopping from an initially unviable state.',
        confirmation_seeds_executed=[],v2_milestone_passed=False,
        source_hashes={p:digest(ROOT/p) for p in sorted(sources)},
        retained_hashes={str((previous.OUT/p).relative_to(ROOT)):sha for p,sha in json.loads((previous.OUT/'checksums.json').read_text()).items()})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen envelope protocol changed'
    else:save(p,value)


def worker(plant):
    records=[];members={}
    for condition in CALS+(EXTRAS if plant=='nominal' else ()):
        for seed in SEEDS:
            for name in NAMES:
                result=run(seed,plant,condition,name);rows=result['rows'];member=f'{seed}-{plant}-{condition}-{name}.csv'
                stream=StringIO(newline='');w=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');w.writeheader()
                w.writerows({k:r[k] for k in FIELDS} for r in rows);content=stream.getvalue().encode();members[member]=content
                truth=.85;bound_failures=0
                for r in rows:
                    if r['envelope_lower'] is not None and r['envelope_lower']>truth+1e-8:bound_failures+=1
                    truth=r['reservoir']
                records.append(dict(seed=seed,plant=plant,condition=condition,regime='extra' if condition in EXTRAS else 'primary',
                    method=name,origin='new_envelope_simulation',trace_archive=f'results/v2-envelope/traces-{plant}.zip',trace_member=member,
                    trace_sha256=hashlib.sha256(content).hexdigest(),**result['metrics'],
                    envelope_unavailable_s=sum(not r['envelope_contract_available'] for r in rows),
                    envelope_uncertified_s=sum(not r['envelope_feasible'] for r in rows),
                    initial_stop_feasible=bool(rows[0]['envelope_feasible']),
                    envelope_clipped_s=sum(r['envelope_clipped'] for r in rows),
                    envelope_bound_failures_s=bound_failures,
                    cap_violations=sum(not r['applied_within_shared_cap'] for r in rows),
                    certified_margin_violations=sum(r['envelope_feasible'] and r['envelope_margin'] < -1e-7 for r in rows)))
        print(f'Completed envelope {plant} {condition}',flush=True)
    with zipfile.ZipFile(OUT/f'traces-{plant}.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,content in sorted(members.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,content)
    return records


def aggregate(rows,new=False):
    g=dict(runs=len(rows),mean_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
        floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
        high_pressure_cases=sum(r['high_pressure_s']>0 for r in rows),minimum_reservoir_L=min(r['minimum_reservoir'] for r in rows))
    if new:
        for field in ('envelope_unavailable_s','envelope_uncertified_s','envelope_clipped_s','envelope_bound_failures_s','cap_violations','certified_margin_violations'):g[field]=sum(r[field] for r in rows)
        g['initially_uncertified_runs']=sum(not r['initial_stop_feasible'] for r in rows)
    return g


def execute():
    records=[{**r,'origin':'retained_rc4_reference','condition':r['calibration'],'regime':'primary'} for r in json.loads((previous.OUT/'runs.json').read_text())]
    assert len(records)==64
    with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
        futures=[pool.submit(worker,p) for p in PLANTS]
        for future in as_completed(futures):records.extend(future.result());save(OUT/'runs.json',records)
    records.sort(key=lambda r:(r['origin'],r['plant'],r['condition'],r['seed'],r['method']));save(OUT/'runs.json',records)
    totals={}
    for origin in ('retained_rc4_reference','new_envelope_simulation'):
        totals[origin]={n:aggregate([r for r in records if r['origin']==origin and r['method']==n and r['regime']=='primary'],origin=='new_envelope_simulation') for n in NAMES}
    groups={c:{n:aggregate([r for r in records if r['origin']=='new_envelope_simulation' and r['condition']==c and r['method']==n],True) for n in NAMES} for c in CALS+EXTRAS}
    a=totals['new_envelope_simulation']['aggregate_zero']['mean_deficit_auc'];b=totals['new_envelope_simulation']['joint_zero']['mean_deficit_auc']
    summary=dict(version_line='v2',evaluations=len(records),new_simulations=72,retained_reference_runs=64,primary_totals=totals,
        new_by_condition=groups,joint_reduction_fraction=1-b/a,v2_milestone_passed=False,confirmation_seeds_executed=[],protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',summary);save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.name!='checksums.json'})
    print((OUT/'summary.json').read_text(),flush=True)


if __name__=='__main__':protocol();execute()
