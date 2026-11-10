"""Fixed v2 zero-credit calibration/model-boundary development study."""
from copy import deepcopy
import csv
import hashlib
from io import StringIO
import json
import zipfile
import numpy as np
import zero_v2_study as previous
from zero_v2_study import ROOT,SEEDS,digest,save,patient
from integrity_study import CALIBRATIONS
base=previous.previous
OUT=ROOT/'results/v2-robustness'
PLANTS={'nominal':{},'slow':dict(actuator_tau=6.),'outside':dict(actuator_tau=20.),
    'lagged':dict(actuator_tau=5.,drainage_tau=20.,venous_nonlinearity=.08)}
CALS=('healthy','missing','biased','shared')
NAMES=('aggregate_zero','joint_zero')
FIELDS=base.FIELDS+('bank_supported','bank_conflict','active_models','calibration_count',
    'calibration_age','reference_quarantined','observed_venous_flow','bank_lower','bank_upper')


def methods():return {n:previous.methods()[n] for n in NAMES}


def calibration_options(cal):
    options=deepcopy(CALIBRATIONS['good' if cal=='healthy' else cal])
    if cal=='shared':options['fault_bias']=.22
    return options


def run(seed,plant,cal,name):
    if seed not in SEEDS or plant not in PLANTS or cal not in CALS or name not in NAMES:raise ValueError('Only fixed development cells allowed')
    m=methods()[name]
    with base.joint_runtime():
        return base.simulate_calibrated_pump(base.ReturnChallenge('repeated',windows=base.windows('repeated')),
            'sentinel',seed=seed,duration=600.,dt=1.,patient=patient(seed,'evaluation'),
            controller_kind='integrity_pi',controller_options=m['options'],reference_guard_options=m['guard'],
            plant_options=PLANTS[plant],venous_measurement=dict(noise_sd=.015,bias=0.),level_mode='screened',
            level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),
            reference_fault_options=dict(fault_bias=.22) if cal=='shared' else {},calibration_options=calibration_options(cal))


def protocol():
    sources=set(json.loads((previous.OUT/'protocol.json').read_text())['source_hashes'])
    sources.update(('examples/robust_v2_study.py','examples/integrity_study.py'))
    value=dict(version_line='v2',version='2.0.0rc4',stage='zero_return_boundary_development',seeds=SEEDS,
        plants=PLANTS,calibrations={c:calibration_options(c) for c in CALS},
        routine_faults={c:dict(fault_bias=.22) if c=='shared' else {} for c in CALS},methods=methods(),
        evaluations=64,new_simulations=56,retained_reference_runs=8,duration_s=600.,dt_s=1.,
        return_windows_s=base.windows('repeated'),
        fixed_design='Unchanged rc3 aggregate/joint zero-return controllers and observer allowances. Full four-plant by four-calibration matrix on the same two development patients, repeated interruptions in every case. The healthy nominal/slow cells reuse eight exact hashed rc3 runs; every other cell is newly simulated. No post-result retuning or selection.',
        interpretation='A boundary study, not confirmation. Shared +.22 L calibration/routine corruption can agree while wrong; tau=20 s is outside the retained 1..12 s pump grid. Slow tau=6 and lagged tau=5 also lack exact grid members. A zero-return stopping check remains conditional on correct bounds and retained dynamics. Count all unsupported states, floors and empty requests; do not infer safety from cap compliance.',
        confirmation_seeds_executed=[],v2_milestone_passed=False,
        source_hashes={p:digest(ROOT/p) for p in sorted(sources)},
        retained_hashes={str((previous.OUT/p).relative_to(ROOT)):sha for p,sha in json.loads((previous.OUT/'checksums.json').read_text()).items()})
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/'protocol.json'
    if p.exists():assert json.loads(p.read_text())==json.loads(json.dumps(value)),'Frozen boundary protocol changed'
    else:save(p,value)


def aggregate(rows):
    return dict(runs=len(rows),mean_deficit_auc=float(np.mean([r['deficit_auc'] for r in rows])),
        floor_cases=sum(r['low_reservoir_s']>0 for r in rows),empty_cases=sum(r['empty_request_s']>0 for r in rows),
        high_pressure_cases=sum(r['high_pressure_s']>0 for r in rows),minimum_reservoir_L=min(r['minimum_reservoir'] for r in rows),
        unsupported_s=sum(r['unsupported_s'] for r in rows),cap_violations=sum(r['cap_violations'] for r in rows),
        feasible_margin_violations=sum(r['feasible_margin_violations'] for r in rows))


def execute():
    records=[];old=json.loads((previous.OUT/'runs.json').read_text())
    for r in old:
        if r['case']=='repeated' and r['method'] in NAMES:
            records.append({**r,'calibration':'healthy','origin':'retained_rc3_reference'})
    assert len(records)==8
    for plant in PLANTS:
        members={}
        for cal in CALS:
            if plant in ('nominal','slow') and cal=='healthy':continue
            for seed in SEEDS:
                for name in NAMES:
                    result=run(seed,plant,cal,name);rows=result['rows'];filename=f'{seed}-{plant}-{cal}-{name}.csv'
                    stream=StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader()
                    writer.writerows({k:r[k] for k in FIELDS} for r in rows);content=stream.getvalue().encode();members[filename]=content
                    records.append(dict(seed=seed,plant=plant,case='repeated',calibration=cal,method=name,
                        origin='new_boundary_simulation',trace_archive=f'results/v2-robustness/traces-{plant}.zip',trace_member=filename,
                        trace_sha256=hashlib.sha256(content).hexdigest(),**result['metrics'],
                        unsupported_s=sum(not r['joint_supported'] for r in rows),
                        cap_violations=sum(not r['applied_within_shared_cap'] for r in rows),
                        feasible_margin_violations=sum(r['hypothesis_margin'] is not None and r['predictive_feasible'] and r['hypothesis_margin'] < -1e-7 for r in rows)))
                    save(OUT/'runs.json',records)
            print(f'Completed boundary {plant} {cal}',flush=True)
        with zipfile.ZipFile(OUT/f'traces-{plant}.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,content in sorted(members.items()):
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,content)
    cells={}
    for plant in PLANTS:
        for cal in CALS:
            key=plant+'__'+cal;g=cells[key]={}
            for name in NAMES:g[name]=aggregate([r for r in records if r['plant']==plant and r['calibration']==cal and r['method']==name])
            g['joint_reduction_fraction']=1-g['joint_zero']['mean_deficit_auc']/g['aggregate_zero']['mean_deficit_auc']
    by_cal={c:{n:aggregate([r for r in records if r['calibration']==c and r['method']==n]) for n in NAMES} for c in CALS}
    totals={n:aggregate([r for r in records if r['method']==n]) for n in NAMES}
    summary=dict(version_line='v2',evaluations=len(records),new_simulations=56,retained_reference_runs=8,
        cells=cells,by_calibration=by_cal,totals=totals,v2_milestone_passed=False,confirmation_seeds_executed=[],
        protocol_sha256=digest(OUT/'protocol.json'))
    save(OUT/'summary.json',summary);save(OUT/'checksums.json',{p.name:digest(p) for p in sorted(OUT.iterdir()) if p.name!='checksums.json'})
    print((OUT/'summary.json').read_text(),flush=True)


if __name__=='__main__':protocol();execute()
