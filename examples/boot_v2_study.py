"""Fixed startup-admission comparison; rejections are not successful runs."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
from multiprocessing import get_context
import zipfile
import numpy as np
import envelope_carry_study as previous
from envelope_carry_study import ROOT,SEEDS,PLANTS,CALS,NAMES,digest,save,patient,base
from perfusion_research.boot_v2 import StartupRejected
from perfusion_research.boot_simulation import simulate_boot

OUT=ROOT/'results/v2-boot'
EXTRAS=('inline_shared','no_contract','hot_start','unprimed')
FIELDS=previous.FIELDS+('startup_authorized','startup_margin')


def methods(condition):
    effective=condition if condition in CALS+previous.EXTRAS else 'healthy'
    result=deepcopy(previous.methods(effective))
    for m in result.values():m['options']['startup_flow_error_lpm']=.10
    return result


def parameters(condition):
    effective=condition if condition in CALS+previous.EXTRAS else 'healthy'
    cal,inline=previous.parameters(effective)
    initial='hot' if condition=='hot_start' else 'unprimed' if condition=='unprimed' else 'cold'
    return cal,inline,initial


def run(seed,plant,condition,name):
    if seed not in SEEDS or plant not in PLANTS or name not in NAMES or condition not in CALS+EXTRAS:raise ValueError('Outside fixed matrix')
    if condition in EXTRAS and plant!='nominal':raise ValueError('Extras use nominal pump only')
    cal,inline,initial=parameters(condition);m=methods(condition)[name]
    return simulate_boot(base.ReturnChallenge(condition,windows=base.windows('repeated'),**inline),startup_state=initial,
        policy='sentinel',seed=seed,duration=600.,dt=1.,patient=patient(seed,'evaluation'),controller_kind='integrity_pi',
        controller_options=m['options'],reference_guard_options=m['guard'],plant_options=PLANTS[plant],
        venous_measurement=dict(noise_sd=.015,bias=0.),level_mode='screened',
        level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),
        reference_fault_options=dict(fault_bias=.22) if cal=='shared' else {},calibration_options=previous.previous.calibration_options(cal))


def protocol():
    sources=set(json.loads((previous.OUT/'protocol.json').read_text())['source_hashes'])
    sources.update(('src/perfusion_research/boot_v2.py','src/perfusion_research/boot_simulation.py','examples/boot_v2_study.py'))
    value=dict(version_line='v2',version='2.0.0rc6',stage='startup_interlock_development',seeds=SEEDS,
        plants=PLANTS,calibrations=CALS,extras={c:parameters(c) for c in EXTRAS},methods={c:methods(c) for c in CALS+EXTRAS},
        attempts=80,primary_attempts=64,extra_attempts=16,duration_s=600.,dt_s=1.,return_windows_s=base.windows('repeated'),
        initialization='New cold fixture starts actual motor/pressure at zero and reservoir .85 L in both arms. Optimizer command/integrator tracking starts at zero; observer motor point state starts from measured initial flow. Protection motor interval starts at measured flow +/- .10 L/min, using that measurement only at time zero. Hot fixture retains original 2.4*BSA motor flow; unprimed fixture uses .35 L and stopped motor.',
        admission='Before issuing any command, require a bounded level source and nonnegative independent held-zero stopping margin. Reject with reason/details and no issued command otherwise. Successful admission permits only normal .15 L/min/s ramp behind unchanged envelope and legacy caps. Above-request acknowledgement is recorded and latches an actuation-contract violation; no equipment stop or scheduler is implemented.',
        fairness='Same cold-start physics, PI settings, measurement channels, flow-read error budget and protection envelope in both arms. Starting state differs from warm rc5; historical warm results are provenance, not a fair delivery-improvement denominator. Explicitly count rejected attempts without assigning them zero deficit or zero floor exposure.',
        limits='Two reused development patients. Bounds remain illustrative, not validated hardware error coverage; Gaussian errors are unbounded. Admission does not solve undetectable out-of-contract shared bias, physically prime a circuit or stop an already moving rejected pump.',
        confirmation_seeds_executed=[],v2_milestone_passed=False,
        source_hashes={p:digest(ROOT/p) for p in sorted(sources)},
        warm_reference_hashes={str((previous.OUT/p).relative_to(ROOT)):sha for p,sha in json.loads((previous.OUT/'checksums.json').read_text()).items()})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen startup protocol changed'
    else:save(p,value)


def worker(plant):
    records=[];members={}
    for condition in CALS+(EXTRAS if plant=='nominal' else ()):
        for seed in SEEDS:
            for name in NAMES:
                key=dict(seed=seed,plant=plant,condition=condition,method=name,regime='extra' if condition in EXTRAS else 'primary')
                try:result=run(seed,plant,condition,name)
                except StartupRejected as rejected:
                    records.append(dict(**key,outcome='rejected_startup',reason=rejected.reason,details=rejected.details,issued_commands=0))
                    continue
                rows=result['rows'];member=f'{seed}-{plant}-{condition}-{name}.csv'
                stream=StringIO(newline='');w=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in FIELDS} for r in rows)
                content=stream.getvalue().encode();members[member]=content;truth=.85;bound_fail=0
                for r in rows:
                    if r['envelope_lower'] is not None and r['envelope_lower']>truth+1e-8:bound_fail+=1
                    truth=r['reservoir']
                records.append(dict(**key,outcome='completed',trace_archive=f'results/v2-boot/traces-{plant}.zip',trace_member=member,
                    trace_sha256=hashlib.sha256(content).hexdigest(),**result['metrics'],
                    initial_stop_feasible=bool(rows[0]['envelope_feasible']),startup_margin=rows[0]['startup_margin'],
                    first_positive_command_time=next((r['observation_time'] for r in rows if r['command']>1e-8),None),
                    envelope_uncertified_s=sum(not r['envelope_feasible'] for r in rows),
                    envelope_bound_failures_s=bound_fail,cap_violations=sum(not r['applied_within_shared_cap'] for r in rows)))
        print(f'Completed startup attempts {plant} {condition}',flush=True)
    with zipfile.ZipFile(OUT/f'traces-{plant}.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,content in sorted(members.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,content)
    return records


def aggregate(attempts):
    rows=[r for r in attempts if r['outcome']=='completed']
    g=dict(attempts=len(attempts),completed=len(rows),rejected=len(attempts)-len(rows))
    if not rows:return {**g,'mean_deficit_auc':None,'floor_cases':None,'empty_cases':None,'minimum_reservoir_L':None}
    return dict(**g,mean_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
        floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
        high_pressure_cases=sum(r['high_pressure_s']>0 for r in rows),minimum_reservoir_L=min(r['minimum_reservoir'] for r in rows),
        initially_uncertified_runs=sum(not r['initial_stop_feasible'] for r in rows),
        envelope_uncertified_s=sum(r['envelope_uncertified_s'] for r in rows),envelope_bound_failures_s=sum(r['envelope_bound_failures_s'] for r in rows))


def execute():
    records=[]
    with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
        futures=[pool.submit(worker,p) for p in PLANTS]
        for future in as_completed(futures):records.extend(future.result());save(OUT/'attempts.json',records)
    records.sort(key=lambda r:(r['plant'],r['condition'],r['seed'],r['method']));save(OUT/'attempts.json',records)
    primary={n:aggregate([r for r in records if r['regime']=='primary' and r['method']==n]) for n in NAMES}
    by_condition={c:{n:aggregate([r for r in records if r['condition']==c and r['method']==n]) for n in NAMES} for c in CALS+EXTRAS}
    summary=dict(version_line='v2',attempts=len(records),completed=sum(r['outcome']=='completed' for r in records),
        rejected=sum(r['outcome']=='rejected_startup' for r in records),primary=primary,by_condition=by_condition,
        joint_reduction_fraction=1-primary['joint_zero']['mean_deficit_auc']/primary['aggregate_zero']['mean_deficit_auc'],
        v2_milestone_passed=False,confirmation_seeds_executed=[],protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',summary);save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.name!='checksums.json'})
    print((OUT/'summary.json').read_text(),flush=True)


if __name__=='__main__':protocol();execute()
