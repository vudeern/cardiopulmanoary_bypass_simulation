"""Small fixed development comparison with MPC commands actually applied."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import calibrated_pump_study as old
import perfusion_candidates.calibrated_pump as runtime_module
from perfusion_research.feedback import FeedbackRuntime

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/feedback-pilot'
SEEDS=(37000,37007,37014,37031)
TRACE_FIELDS=('observation_time','command','flow','do2','reservoir','pressure','protected_pi_action',
    'mpc_accepted','mpc_status','mpc_elapsed_s','action_changed','applied_within_shared_cap','decision_cap')


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')


def methods():
    rc5=deepcopy(old.methods()['retained_single_anchor'])
    pi=deepcopy(rc5);pi['kind']='integrity_pi';pi['options'].update(tau_c=.2,target_level=.25,feedback_mode='pi')
    mpc=deepcopy(pi);mpc['options']['feedback_mode']='mpc'
    return {'rc5':rc5,'pi':pi,'mpc':mpc}


@contextmanager
def feedback_runtime():
    original=runtime_module.CalibratedPumpRuntime;runtime_module.CalibratedPumpRuntime=FeedbackRuntime
    try:yield
    finally:runtime_module.CalibratedPumpRuntime=original


def run(seed,phys,plant,name,method):
    if seed not in SEEDS:raise ValueError('Only the declared reused development seeds are allowed')
    if name=='rc5':return old.run(seed,'primary',phys,plant,'clean','good',name,method)
    with feedback_runtime():return old.run(seed,'primary',phys,plant,'clean','good',name,method)


def protocol():
    sources=set(json.loads((old.OUT/'protocol.json').read_text())['source_hashes'])
    sources.update(('src/perfusion_research/feedback.py','src/perfusion_research/horizon.py',
        'src/perfusion_research/bottleneck.py','examples/feedback_study.py','examples/calibrated_pump_study.py','data/version2-gates.json'))
    value=dict(stage='closed_loop_development_pilot',seeds=SEEDS,physiology=['clean','combined'],plants=['nominal','slow'],
        methods=methods(),duration_s=600.,dt_s=1.,runs=48,confirmation_seeds_executed=[],
        comparator='One predeclared fast PI setting; not an exhaustive retuning or strongest eligible comparator qualification.',
        feedback='Every MPC tick solves the existing 15-second nominal LP plus normal-slew zero-return braking continuation. Primary cost is oxygen-deficit AUC; secondary maximizes first command at the same primary optimum within 1e-8 AUC. The proposed first action is constrained and clamped by the exact same current rc.5 cap as PI. A rejected, late, unsupported or infeasible solve uses the shielded PI action. Commands are actually applied to the unchanged plant.',
        information='The same guard point-volume estimate feeds nominal PI and MPC; the same lower-volume estimate feeds their shared shield. Same calibration guard, Hb estimates, sensor streams, limits and normal .15 L/min/s authority for PI and MPC. Nominal prediction uses guard point volume, generic 2-second pump hypothesis propagated from applied commands, current measured pressure and constant measured return/Hb/saturation. Fixed nominal R=14,C=.0018; no true patient state, true lag or future event inputs. One-second diagnostic rejection timer, not a hard real-time guarantee.',
        limitations='Small reused four-patient development cohort, healthy routine references/calibration only; combined physiology retains existing inline/flow faults and drainage disturbance. Conditional existing shield assumptions remain. No hardware, clinical or full v2.0 qualification. Retain every outcome, including failures.',
        source_hashes={p:digest(ROOT/p) for p in sorted(sources)})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen feedback protocol changed'
    else:save(p,value)
    return value


def execute():
    records=[]
    for seed in SEEDS:
        for phys in ('clean','combined'):
            for plant in ('nominal','slow'):
                for name,method in methods().items():
                    result=run(seed,phys,plant,name,method);rows=result['rows'];mpc=[r for r in rows if r.get('mpc_accepted')]
                    row=dict(seed=seed,physiology=phys,plant=plant,method=name,**result['metrics'],
                        mpc_accepted_s=len(mpc),action_changed_s=sum(r.get('action_changed',False) for r in rows),
                        cap_violations=sum(not r.get('applied_within_shared_cap',True) for r in rows),
                        solver_calls=sum(r.get('mpc_status','') not in ('pi_mode','unsupported_or_infeasible_reserve','') for r in rows),
                        mean_solver_ms=float(np.mean([r.get('mpc_elapsed_s',0.)*1000 for r in rows])),
                        statuses={s:sum(r.get('mpc_status','reference')==s for r in rows) for s in sorted({r.get('mpc_status','reference') for r in rows})},
                        commands_sha256=hashlib.sha256(np.asarray([r['command'] for r in rows],dtype='<f8').tobytes()).hexdigest())
                    records.append(row)
                    # Keep all 600 applied actions and truth/diagnostic outcomes.
                    with (OUT/f'{seed}-{phys}-{plant}-{name}.csv').open('w',newline='') as f:
                        writer=csv.DictWriter(f,fieldnames=TRACE_FIELDS,lineterminator='\n');writer.writeheader()
                        writer.writerows({k:r.get(k,'') for k in TRACE_FIELDS} for r in rows)
                print(f'Completed {seed} {phys} {plant}',flush=True)
    save(OUT/'runs.json',records);summarize(records)


def summarize(records):
    groups={}
    for name in methods():
        rows=[r for r in records if r['method']==name]
        groups[name]=dict(runs=len(rows),mean_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
            floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
            minimum_L=min(r['minimum_reservoir'] for r in rows),mean_high_pressure_s=float(np.mean([r['high_pressure_s'] for r in rows])),
            mpc_accepted_s=sum(r['mpc_accepted_s'] for r in rows),action_changed_s=sum(r['action_changed_s'] for r in rows),
            cap_violations=sum(r['cap_violations'] for r in rows))
    paired=[]
    for s in SEEDS:
        pi=np.mean([r['deficit_auc'] for r in records if r['seed']==s and r['method']=='pi'])
        mpc=np.mean([r['deficit_auc'] for r in records if r['seed']==s and r['method']=='mpc'])
        paired.append(dict(seed=s,pi=pi,mpc=mpc,difference=mpc-pi))
    value=dict(groups=groups,paired_patient_differences=paired,
        mpc_reduction_fraction=1-groups['mpc']['mean_deficit_auc']/groups['pi']['mean_deficit_auc'],
        runs=len(records),version2_ready=False,confirmation_seeds_executed=[],protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',value)
    save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.name!='checksums.json'})
    print(json.dumps(value,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args();protocol();execute()
