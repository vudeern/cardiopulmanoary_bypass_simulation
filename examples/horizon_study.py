"""Measured-controller bottleneck audit and offline nominal LP snapshots."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import scipy
import calibrated_pump_study as old
import perfusion_candidates.calibrated_pump as controller_module
from perfusion_research.bottleneck import TracedController
from perfusion_research.horizon import HorizonSolver,formulate
from perfusion_lab.model import oxygen_content

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/horizon-foundation'
SEEDS=tuple(range(37000,37032));TIMES=(30.,126.,300.,510.)
REASONS=('unsupported_calibration','pressure_slowdown','stopping_reserve','oxygen_cap','up_slew','down_slew','controller_choice')


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,value):p.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def methods():
    result={'rc5':deepcopy(old.methods()['retained_single_anchor'])}
    for name,tau,level in (('pi_standard',5.,.35),('pi_fast',.2,.25)):
        m=deepcopy(result['rc5']);m['kind']='integrity_pi';m['options'].update(tau_c=tau,target_level=level)
        result[name]=m
    return result


def protocol():
    paths=set(json.loads((old.OUT/'protocol.json').read_text())['source_hashes'])
    paths.update(('examples/calibrated_pump_study.py','examples/horizon_study.py',
        'src/perfusion_research/horizon.py','src/perfusion_research/bottleneck.py','data/version2-gates.json'))
    value=dict(stage='offline_horizon_foundation',seeds=list(SEEDS),confirmation_seeds_executed=[],
        methods=methods(),physiology=['clean','combined'],plants=['nominal','slow'],
        routine='clean',calibration='good',duration_s=600.,dt_s=1.,baseline_runs=384,
        snapshot_times_s=TIMES,forecasts=['measured_constant','protected_constant'],snapshot_method='rc5',
        nominal=dict(horizon=15,tau=2.,resistance=14.,compliance=.0018,floor=.29,ceiling=5.8,
            max_command=7.,slew=.15,pressure_limit=95.,deadline_s=1.),
        forecast_contract='Offline only. Volume point estimate from existing calibration guard; generic 2-second pump hypothesis propagated from applied commands; measured pressure; current Hb lower estimate and saturation held constant. Return is either current measured flow or current protective return credit, held for 15s; appended backup assumes zero return. No true state, patient resistance/compliance/lag, future events or future Hb enter snapshots.',
        interpretation='Three measured controller arms share existing rc.5 observer/protection. Two PI settings are illustrative, not an exhaustive retuning or a newly qualified strongest comparator. Limiting reasons use declared priority, not causal attribution. Snapshot plans are NEVER applied and cannot establish oxygen improvement, robust protection, or a runtime deadline guarantee.',
        nominal_backup='Append enough nonincreasing normal-slew commands to reach zero; enforce predicted V/Q/pressure bounds throughout; final zero-command analytic tail. No emergency authority. This nominal path is not a robust invariant set.',
        source_hashes={p:digest(ROOT/p) for p in sorted(paths)})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen protocol changed'
    else:save(p,value)
    return value


@contextmanager
def tracing():
    original=controller_module.CalibratedPumpController
    controller_module.CalibratedPumpController=TracedController
    try:yield
    finally:controller_module.CalibratedPumpController=original


def run_case(seed,phys,plant,name,method):
    if seed not in SEEDS:raise ValueError('Confirmation seeds locked')
    with tracing():
        result=old.run(seed,'primary',phys,plant,'clean','good',name,method)
    reasons={r:dict(seconds=0,deficit_auc=0.,headroom_sum=0.) for r in REASONS}
    snapshots=[]
    for row in result['rows']:
        bucket=reasons[row['limit_reason']];bucket['seconds']+=1
        bucket['deficit_auc']+=max(0.,280.-row['do2'])/60.
        bucket['headroom_sum']+=row['command_headroom']
        if name=='rc5' and row['observation_time'] in TIMES:
            for forecast in ('measured_constant','protected_constant'):
                inflow=row['measured_return_start'] if forecast=='measured_constant' else row['protection_inflow_floor']
                conversion=10.*oxygen_content(row['hb_lower'],row['sao2'])/result['patient']['bsa']
                initial=[row['point_volume_start'],row['nominal_flow_start'],row['measured_pressure_start']]
                try:
                    p=formulate(initial,row['previous_command'],np.full(15,inflow),np.full(15,conversion),np.full(15,280.))
                    plan=HorizonSolver('highs',deadline_s=1.).solve(p)
                except ValueError:
                    plan=dict(accepted=False,command=None,status='invalid_input',elapsed_s=0.,deadline_s=1.,
                        checks=dict(valid=False,reason='invalid_input'),vector=None)
                snapshots.append(dict(time=row['observation_time'],forecast=forecast,initial=initial,
                    previous=row['previous_command'],inflow=inflow,conversion=conversion,actual_command=row['command'],
                    observed_controller_cap=row['decision_cap'],**plan))
    commands=[r['command'] for r in result['rows']]
    value=dict(seed=seed,physiology=phys,plant=plant,method=name,metrics=result['metrics'],
        reasons=reasons,snapshots=snapshots,commands_sha256=hashlib.sha256(np.asarray(commands,dtype='<f8').tobytes()).hexdigest())
    save(OUT/f'{seed}-{phys}-{plant}-{name}.json',value)


def summarize():
    cases=[json.loads((OUT/f'{s}-{p}-{m}-{n}.json').read_text()) for s in SEEDS
           for p in ('clean','combined') for m in ('nominal','slow') for n in methods()]
    groups={}
    for name in methods():
        rows=[r for r in cases if r['method']==name];total=sum(r['metrics']['deficit_auc'] for r in rows)
        groups[name]=dict(runs=len(rows),mean_deficit_auc=total/len(rows),
            floor_cases=sum(r['metrics']['low_reservoir_s']>0 for r in rows),
            empty_cases=sum(r['metrics']['empty_request_s']>0 for r in rows),
            reasons={why:dict(seconds=sum(r['reasons'][why]['seconds'] for r in rows),
                deficit_fraction=sum(r['reasons'][why]['deficit_auc'] for r in rows)/total,
                mean_headroom=sum(r['reasons'][why]['headroom_sum'] for r in rows)/max(1,sum(r['reasons'][why]['seconds'] for r in rows))) for why in REASONS})
    snapshots={}
    for forecast in ('measured_constant','protected_constant'):
        rows=[p for c in cases for p in c['snapshots'] if p['forecast']==forecast]
        accepted=[p for p in rows if p['accepted']]
        times=[p['elapsed_s']*1000 for p in rows]
        snapshots[forecast]=dict(plans=len(rows),accepted=len(accepted),rejected=len(rows)-len(accepted),
            statuses={s:sum(p['status']==s for p in rows) for s in sorted({p['status'] for p in rows})},
            median_total_ms=float(np.median(times)),p99_total_ms=float(np.percentile(times,99)),
            over_2ms=sum(t>2 for t in times),
            max_rollout_error=max((p['checks']['rollout_error'] for p in accepted),default=None))
    value=dict(baseline_runs=len(cases),snapshot_plans=sum(v['plans'] for v in snapshots.values()),
        groups=groups,snapshots=snapshots,version2_ready=False,confirmation_seeds_executed=[],
        runtime=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,backend='HiGHS'),
        interpretation='Offline snapshots, never applied; no MPC/PI performance improvement established.',protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',value)
    save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.glob('*.json')) if p.name!='checksums.json'})
    print(json.dumps(value,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seed',type=int,choices=SEEDS)
    parser.add_argument('--summarize',action='store_true');args=parser.parse_args();protocol()
    if args.summarize:summarize()
    else:
        for seed in ([args.seed] if args.seed is not None else SEEDS):
            for phys in ('clean','combined'):
                for plant in ('nominal','slow'):
                    for name,method in methods().items():run_case(seed,phys,plant,name,method)
            print(f'Completed patient {seed}',flush=True)
        if args.seed is None:summarize()
