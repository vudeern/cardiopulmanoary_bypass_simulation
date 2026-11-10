"""First v2 recovery-aware feedback experiment; fixed development pilot."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import calibrated_pump_study as old
from continuity_study import patient
import perfusion_candidates.calibrated_pump as runtime_module
from perfusion_candidates.calibrated_pump_simulation import simulate_calibrated_pump
from perfusion_lab.stress import StressScenario
from perfusion_research.recovery_v2 import RecoveryRuntime

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/v2-recovery-pilot'
SEEDS=(37000,37014)


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')


def methods():
    template=deepcopy(old.methods()['retained_single_anchor']);template['kind']='integrity_pi'
    values={}
    for name,tau,level,enabled in (('pi_standard',5.,.35,False),('pi_fast',.2,.25,False),('recovery',.2,.25,True)):
        v=deepcopy(template);v['options'].update(tau_c=tau,target_level=level,recovery_enabled=enabled);values[name]=v
    return values


@contextmanager
def recovery_runtime():
    original=runtime_module.CalibratedPumpRuntime;runtime_module.CalibratedPumpRuntime=RecoveryRuntime
    try:yield
    finally:runtime_module.CalibratedPumpRuntime=original


def run(seed,plant,case,method):
    if seed not in SEEDS:raise ValueError('Only locked reused development seeds allowed')
    scenario=StressScenario(case,drainage=0. if case=='interruption' else 1.,event_start=.28,event_end=.355)
    with recovery_runtime():
        return simulate_calibrated_pump(scenario,'sentinel',seed=seed,duration=600.,dt=1.,
            patient=patient(seed,'evaluation'),controller_kind='integrity_pi',controller_options=method['options'],
            reference_guard_options=method['guard'],plant_options=old.first.previous.previous.PLANTS[plant],
            venous_measurement=dict(noise_sd=.015,bias=0.),level_mode='screened',
            level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),reference_fault_options={},
            calibration_options=dict(period=120.,delay=6.,noise_sd=.01))


def protocol():
    sources=set(json.loads((old.OUT/'protocol.json').read_text())['source_hashes'])
    sources.update(('src/perfusion_research/feedback.py','src/perfusion_research/horizon.py',
        'src/perfusion_research/bottleneck.py','src/perfusion_research/recovery_v2.py','examples/recovery_v2_study.py'))
    value=dict(version_line='v2',version='2.0.0rc1',stage='recovery_development_pilot',seeds=SEEDS,
        methods=methods(),plants=['nominal','slow'],cases=['normal','interruption'],runs=24,
        duration_s=600.,dt_s=1.,recovery_window_s=[213.,273.],interruption_window_s=[168.,213.],
        detection='No event schedule enters the controller. Require supported independent calibration and two anchors, then 20 measured-return samples. Two consecutive readings below .65 of prior median indicate interruption; two above .8 of its frozen baseline indicate recovery. Recovery request uses current permitted cap for 30 seconds, with normal slew and unchanged protection.',
        fairness='Fast PI and recovery use identical gains, point-volume estimate, measurements, phase classifier and independent protection; only recovery-phase request override differs. Standard PI is an additional reference. No new sensor or emergency authority.',
        evaluation='Compare 60-second post-return deficit against fast PI and retain standard PI, total-run deficit, detection/recovery latency, false alarms, floor/empty and cap/slew outcomes. Normal cases use the same sham analysis window. Recovery-specific improvement is not full v2 release qualification.',
        confirmation_seeds_executed=[],v2_milestone_passed=False,
        source_hashes={p:digest(ROOT/p) for p in sorted(sources)})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen v2 protocol changed'
    else:save(p,value)


def execute():
    records=[];fields=('observation_time','command','flow','do2','reservoir','pressure','recovery_phase',
        'recovery_action_changed','decision_cap','applied_within_shared_cap')
    for seed in SEEDS:
        for plant in ('nominal','slow'):
            for case in ('normal','interruption'):
                for name,method in methods().items():
                    result=run(seed,plant,case,method);rows=result['rows'];phase='warming';alarms=0
                    for r in rows:
                        if r['recovery_phase']=='interrupted' and phase!='interrupted' and not (case=='interruption' and 168<=r['observation_time']<213):alarms+=1
                        phase=r['recovery_phase']
                    detected=[r['observation_time'] for r in rows if r['recovery_phase']=='interrupted' and 168<=r['observation_time']<213]
                    recovered=[r['observation_time'] for r in rows if r['recovery_phase']=='recovering' and 213<=r['observation_time']<273]
                    record=dict(seed=seed,plant=plant,case=case,method=name,**result['metrics'],
                        recovery_deficit_auc=sum(max(0.,280.-r['do2']) for r in rows if 213<=r['observation_time']<273)/60.,
                        detection_delay_s=min(detected)-168 if case=='interruption' and detected else None,
                        recovery_delay_s=min(recovered)-213 if case=='interruption' and recovered else None,
                        false_alarms=alarms,changed_action_s=sum(r['recovery_action_changed'] for r in rows),
                        cap_violations=sum(not r['applied_within_shared_cap'] for r in rows))
                    records.append(record)
                    with (OUT/f'{seed}-{plant}-{case}-{name}.csv').open('w',newline='') as f:
                        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in fields} for r in rows)
                print(f'Completed v2 {seed} {plant} {case}',flush=True)
    save(OUT/'runs.json',records);groups={}
    for name in methods():
        groups[name]={}
        for case in ('normal','interruption'):
            rows=[r for r in records if r['method']==name and r['case']==case]
            groups[name][case]=dict(runs=len(rows),mean_recovery_deficit_auc=float(np.mean([r['recovery_deficit_auc'] for r in rows])),
                mean_total_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
                floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
                false_alarms=sum(r['false_alarms'] for r in rows),changed_action_s=sum(r['changed_action_s'] for r in rows),cap_violations=sum(r['cap_violations'] for r in rows))
    pi=groups['pi_fast']['interruption']['mean_recovery_deficit_auc'];new=groups['recovery']['interruption']['mean_recovery_deficit_auc']
    summary=dict(version_line='v2',runs=len(records),groups=groups,recovery_reduction_fraction_vs_fast_pi=1-new/pi,
        v2_milestone_passed=False,confirmation_seeds_executed=[],protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',summary);save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.name!='checksums.json'})
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args();protocol();execute()
