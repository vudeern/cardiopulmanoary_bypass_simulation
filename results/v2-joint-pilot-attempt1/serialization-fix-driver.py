"""Locked v2 joint-hypothesis protection comparison on reused development cases."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import csv
import json
import numpy as np
import recovery_v2_study as previous
from recovery_v2_study import ROOT,SEEDS,digest,save,old,patient,runtime_module,simulate_calibrated_pump
from perfusion_lab.stress import StressScenario
from perfusion_research.joint_v2 import JointRuntime

OUT=ROOT/'results/v2-joint-pilot'
CASES=('normal','single','repeated','repeated_bias','repeated_noise')
def save(p,x):
    previous.save(p,json.loads(json.dumps(x,default=lambda v:v.item())))

FIELDS=('observation_time','command','flow','do2','reservoir','pressure','empty_request',
    'aggregate_cap','joint_cap','decision_cap','joint_supported','joint_action_changed',
    'hypothesis_margin','predictive_feasible','applied_within_shared_cap')

@dataclass(frozen=True)
class ReturnChallenge(StressScenario):
    windows:tuple=()
    def inputs(self,t,duration):
        values=super().inputs(t,duration)
        values['drainage']=0. if any(start<=t<end for start,end in self.windows) else 1.
        return values

def windows(case):
    return () if case=='normal' else ((168.,213.),) if case=='single' else ((168.,213.),(228.,243.),(258.,288.))

def methods():
    template=deepcopy(old.methods()['retained_single_anchor']);template['kind']='integrity_pi'
    template['options'].update(tau_c=.2,target_level=.25)
    result={}
    for name,enabled in (('aggregate_pi',False),('joint_pi',True)):
        result[name]=deepcopy(template);result[name]['options']['joint_enabled']=enabled
    return result

@contextmanager
def joint_runtime():
    original=runtime_module.CalibratedPumpRuntime;runtime_module.CalibratedPumpRuntime=JointRuntime
    try:yield
    finally:runtime_module.CalibratedPumpRuntime=original

def run(seed,plant,case,method):
    if seed not in SEEDS or case not in CASES:raise ValueError('Only locked development cases allowed')
    with joint_runtime():
        return simulate_calibrated_pump(ReturnChallenge(case,windows=windows(case)),'sentinel',seed=seed,
            duration=600.,dt=1.,patient=patient(seed,'evaluation'),controller_kind='integrity_pi',
            controller_options=method['options'],reference_guard_options=method['guard'],
            plant_options=old.first.previous.previous.PLANTS[plant],
            venous_measurement=dict(noise_sd=.15 if case=='repeated_noise' else .015,
                bias=.8 if case=='repeated_bias' else 0.),level_mode='screened',
            level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),reference_fault_options={},
            calibration_options=dict(period=120.,delay=6.,noise_sd=.01))

def protocol():
    sources=set(json.loads((previous.OUT/'protocol.json').read_text())['source_hashes'])
    sources.update(('src/perfusion_research/joint_v2.py','examples/joint_v2_study.py'))
    value=dict(version_line='v2',version='2.0.0rc2',stage='joint_hypothesis_development_pilot',seeds=SEEDS,
        methods=methods(),cases=CASES,plants=['nominal','slow'],runs=40,duration_s=600.,dt_s=1.,
        windows_s={c:windows(c) for c in CASES},recovery_analysis_window_s=[213.,348.],
        mechanism='Both arms receive identical full model-associated volume bounds and venous-bias upper bounds from the same causal calibration observer. Aggregate PI uses min volume and max bias across all models plus worst pump reserve; joint PI requires the existing reserve inequality separately for EVERY retained model with that model volume lower and bias upper. Within-model volume/bias extrema remain conservative; no vertex-only relaxation.',
        fixed_constraints='Same .29 L stopping-budget floor, .25 L outcome floor, .15 L/min/s slew, 7 L/min limit, 50% finite-return credit for 15 seconds, calibration/model-error allowances, point-estimate fast PI and measurement channels. No changed future-return assumptions or pruning.',
        interpretation='Less conservative combination of existing conditional hypotheses, not absolute safety or a guarantee of future inflow. Healthy independent calibration throughout. Biased/noisy venous channels challenge assumptions. Retain every failure and unsupported step.',
        confirmation_seeds_executed=[],v2_milestone_passed=False,
        source_hashes={p:digest(ROOT/p) for p in sorted(sources)})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen protocol changed'
    else:save(p,value)

def execute():
    records=[]
    for seed in SEEDS:
        for plant in ('nominal','slow'):
            for case in CASES:
                for name,method in methods().items():
                    result=run(seed,plant,case,method);rows=result['rows']
                    record=dict(seed=seed,plant=plant,case=case,method=name,**result['metrics'],
                        recovery_deficit_auc=sum(max(0.,280.-r['do2']) for r in rows if 213<=r['observation_time']<348)/60.,
                        changed_action_s=sum(r['joint_action_changed'] for r in rows),
                        unsupported_s=sum(not r['joint_supported'] for r in rows),
                        cap_violations=sum(not r['applied_within_shared_cap'] for r in rows),
                        feasible_margin_violations=sum(r['hypothesis_margin'] is not None and r['predictive_feasible'] and r['hypothesis_margin'] < -1e-7 for r in rows),
                        widened_cap_s=sum(r['joint_cap']>r['aggregate_cap']+1e-6 for r in rows))
                    records.append(record)
                    with (OUT/f'{seed}-{plant}-{case}-{name}.csv').open('w',newline='') as f:
                        w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in FIELDS} for r in rows)
                print(f'Completed joint pilot {seed} {plant} {case}',flush=True)
    save(OUT/'runs.json',records);groups={}
    for case in CASES:
        groups[case]={}
        for name in methods():
            rows=[r for r in records if r['method']==name and r['case']==case]
            groups[case][name]=dict(runs=len(rows),mean_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
                mean_recovery_deficit_auc=float(np.mean([r['recovery_deficit_auc'] for r in rows])),
                floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
                worst_minimum_reservoir_L=min(r['minimum_reservoir'] for r in rows),
                high_pressure_cases=sum(r['high_pressure_s']>0 for r in rows),
                changed_action_s=sum(r['changed_action_s'] for r in rows),widened_cap_s=sum(r['widened_cap_s'] for r in rows),
                cap_violations=sum(r['cap_violations'] for r in rows),feasible_margin_violations=sum(r['feasible_margin_violations'] for r in rows))
        groups[case]['reduction_fraction']=1-groups[case]['joint_pi']['mean_deficit_auc']/groups[case]['aggregate_pi']['mean_deficit_auc']
    summary=dict(version_line='v2',runs=len(records),groups=groups,v2_milestone_passed=False,
        confirmation_seeds_executed=[],protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',summary);save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.name!='checksums.json'})
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':protocol();execute()
