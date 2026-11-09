"""v1.14 causal model-bank experiment. No truth supplied to control decisions."""
import argparse,csv,json
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
import numpy as np
from perfusion_lab.simulation import simulate
from perfusion_lab.model_simulation import simulate_model
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from continuity_study import patient,write_csv
from integrity_study import PHYS,FAULTS,CALIBRATIONS,DEFAULT_GUARD
from simc_benchmark import digest,dumps,METRICS as BASE
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/model-bank-study'
FAULTS={**FAULTS,'outage':dict(dropout_prob=.25,outage_start=150.,outage_end=480.)}
PLANTS={'nominal':dict(actuator_tau=3.),'slow':dict(actuator_tau=9.),'lagged':dict(actuator_tau=6.5,drainage_tau=18.,venous_nonlinearity=.08)}
DEV_PLANTS={'nominal':{},'slow':dict(actuator_tau=6.)}
OLD_GUARD=dict(base_uncertainty=.06,drift_allowance=.004,audit_tolerance=.12)
OLD_CALPI=json.loads((ROOT/'results/integrity-study/selection.json').read_text())['calpi']
METRICS=tuple(BASE)+('volume_mae_L','lower_undercoverage_s','mean_halfwidth_L','bank_supported_s','bank_conflict_s')
REPLAYS=('clean__nominal__clean__good','clean__nominal__positive_start__good','combined__slow__step__good','combined__lagged__ramp__good','combined__lagged__outage__good','combined__slow__positive_start__missing','combined__nominal__positive_start__shared','combined__nominal__negative_start__biased')
SOURCES=('src/perfusion_lab/model_bank.py','src/perfusion_lab/model_simulation.py','src/perfusion_lab/integrity.py','src/perfusion_lab/simulation.py','src/perfusion_lab/reference.py','src/perfusion_lab/simc.py','src/perfusion_lab/braking.py','src/perfusion_lab/model.py','src/perfusion_lab/stress.py','src/perfusion_lab/sensing.py','examples/continuity_study.py','examples/model_bank_study.py')

def configurations():
 return [dict(guard={**OLD_GUARD,'calibration_error':e,'model_error_flow':rate},options=dict(recovery_floor=floor)) for e in (.02,.04) for rate in (.03,.1) for floor in (.45,.6)]

def candidates():
 result=[]
 for i,c in enumerate(configurations()):
  for kind in ('hybrid','pi'):result.append(dict(id=f'model_{i}_{kind}',family=kind,engine='model',kind='integrity_'+kind,**c))
 for tau in (1.5,5.,10.,20.):
  for level in (.35,.45,.55,.65):result.append(dict(id=f'calpi_{tau}_{level}',family='calpi',engine='old',kind='simc',guard=DEFAULT_GUARD,options=dict(tau_c=tau,target_level=level),mode='calibration_only'))
 return result

def run(phase,phys,plant,fault,cal,seed,method,dt=1.):
 params=dict(PHYS[phys]);bias=params.pop('venous_bias',0.)
 if phase=='development' and phys=='combined':params.update(drainage=.4,reservoir_bias=.4,noise_scale=2.)
 faults=dict(FAULTS[fault]);calibration=dict(CALIBRATIONS[cal])
 if cal=='shared':calibration.update(faults)
 engine=simulate_model if method['engine']=='model' else simulate
 result=engine(StressScenario(phys,**params),'sentinel',seed=seed,duration=600.,dt=dt,
  patient=patient(seed,'evaluation'),controller_kind=method['kind'],controller_options=method['options'],
  plant_options=(DEV_PLANTS if phase=='development' else PLANTS)[plant],venous_measurement=dict(noise_sd=.015,bias=bias),level_mode=method.get('mode','screened'),
  level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),reference_fault_options=faults,calibration_options=calibration,reference_guard_options=method['guard'])
 truth=.85;errors=[];under=0;half=[]
 for r in result['rows']:
  errors.append(abs(r['level_reference_estimate']-truth));under+=r['level_reference_lower']>truth+1e-9;half.append(r['reference_uncertainty']);truth=r['reservoir']
 result['metrics'].update(volume_mae_L=float(np.mean(errors)),lower_undercoverage_s=under*dt,mean_halfwidth_L=float(np.mean(half)),bank_supported_s=sum(r.get('bank_supported',False) for r in result['rows'])*dt,bank_conflict_s=sum(r.get('bank_conflict',False) for r in result['rows'])*dt)
 return result

def mean(rows):return {k:float(np.mean([float(r[k]) for r in rows])) for k in METRICS}

def worker(task):
 phase,seed,methods=task;rows=[]
 for phys in PHYS:
  for plant in (DEV_PLANTS if phase=='development' else PLANTS):
   for fault in (('clean','positive_start','step','outage') if phase=='development' else FAULTS):
    for cal in (('good','missing') if phase=='development' else CALIBRATIONS):
     for label,method in methods.items():
      r=run(phase,phys,plant,fault,cal,seed,method)
      rows.append(dict(phase=phase,phys=phys,plant=plant,fault=fault,calibration=cal,seed=seed,method=label,**{k:r['metrics'][k] for k in METRICS}))
 return rows

def grid(phase,seeds,methods):
 rows=[]
 with ProcessPoolExecutor(max_workers=4,mp_context=get_context('spawn')) as pool:
  for seed,block in zip(seeds,pool.map(worker,[(phase,s,methods) for s in seeds])):rows.extend(block);print(phase,'seed complete:',seed,flush=True)
 return rows

def choose(rows):
 values=[]
 for i,c in enumerate(configurations()):
  h=mean([r for r in rows if r['method']==f'model_{i}_hybrid' and r['calibration']=='good'])
  p=mean([r for r in rows if r['method']==f'model_{i}_pi' and r['calibration']=='good'])
  eligible=all(m[k]<=lim for m in (h,p) for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())
  values.append(dict(index=i,configuration=c,hybrid=h,pi=p,eligible=eligible))
 good=[v for v in values if v['eligible']]
 def key(v):
  m=v['hybrid'];return (m['deficit_auc'],v['index']) if good else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],v['index'])
 selected=min(good or values,key=key)
 vals=[v for v in candidates() if v['family']=='calpi'];means={v['id']:mean([r for r in rows if r['method']==v['id'] and r['calibration']=='good']) for v in vals}
 eligible=[v for v in vals if all(means[v['id']][k]<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())]
 def rank(v):
  m=means[v['id']];return (m['deficit_auc'],vals.index(v)) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v))
 return dict(selected=selected,grid=values,calpi=min(eligible or vals,key=rank),calpi_means=means,calpi_eligible=bool(eligible))

def develop():
 OUT.mkdir(parents=True,exist_ok=True)
 p=dict(status='frozen_v114_causal_model_bank',development_seeds=list(range(35000,35004)),evaluation_seeds=list(range(36000,36016)),duration_s=600.,dt_s=1.,candidates=candidates(),faults=FAULTS,physiology=PHYS,development_plants=DEV_PLANTS,final_plants=PLANTS,calibrations=CALIBRATIONS,replay_cells=REPLAYS,
  model='Fixed generic tau grid1,2,4,8,12s; last four delivered independent calibrations fit affine mass-balance residuals. All retained model predictions define an engineering interval. Routine quarantine permits independent-calibration/model-only operation. Disjoint interval conflicts disable recovery and use a union interval. No true volume, plant tau, fault label or future disturbance is supplied.',
  reserve='Discrete first-order initial excess tail plus exact discrete command-ramp area. Reserve uses worst retained pump state and upper venous-bias allowance. Validity depends on retained model/inflow/error assumptions; finite model grid is not a proof of an unknown true lag bound. Recovery is tapered above a development-selected minimum volume. Partial blending cannot weaken the conditional reserve cap.',
  selection='8 paired observer/reserve settings plus16 calibration-only PI tunings. Good-calibration development means for both model controllers <=1s low/empty, <=5s pressure, then lowest hybrid oxygen deficit; fallback lexicographic low/empty/pressure/deficit, explicitly ineligible. Missing calibration is retained development stress. Total research budgets not claimed equal.',
  primary='Healthy independent calibration, separately clean/bias/outage routine-reference groups: hybrid vs both matched model PI and retuned calibration-only PI must reduce mean oxygen deficit >=10%, paired95 difference upper<0, extra low/empty upper<=1s and pressure upper<=5s. Comparison with frozen v1.12 hybrid retained. All groups/baselines needed for joint success.',
  scope='New patient/noise seeds and pump responses3,9,6.5s differ from development and prior audit. Scenario families and wide synthetic parameter ranges are reused. Missing, biased and shared-corruption calibration are secondary failure regimes, not guaranteed identifiable.',
  version2='This single16-patient cohort cannot qualify for v2.0; two distinct future cohorts with >=32 patients each and all declared version2 gates are required.',
  source_hashes={n:digest(ROOT/n) for n in SOURCES})
 (OUT/'protocol.json').write_text(dumps(p));rows=grid('development',p['development_seeds'],{v['id']:v for v in candidates()});write_csv(OUT/'development.csv',rows)
 sel=choose(rows);(OUT/'selection.json').write_text(dumps(sel));print(dumps(dict(selected=sel['selected'],calpi=sel['calpi'],calpi_eligible=sel['calpi_eligible'])),flush=True)

def group(r,g):
 if g in ('clean','bias','outage'):
  return r['calibration']=='good' and (r['fault']=='clean' if g=='clean' else r['fault']=='outage' if g=='outage' else r['fault'] not in ('clean','outage'))
 return r['calibration']==g

def evaluate():
 p=json.loads((OUT/'protocol.json').read_text());sel=json.loads((OUT/'selection.json').read_text())
 for n,h in p['source_hashes'].items():assert digest(ROOT/n)==h,n
 cfg=sel['selected']['configuration'];methods=dict(hybrid=dict(engine='model',kind='integrity_hybrid',**cfg),matched_pi=dict(engine='model',kind='integrity_pi',**cfg),calibration_pi=sel['calpi'],previous_hybrid=dict(engine='old',kind='integrity_hybrid',options={},guard=OLD_GUARD),single_model=dict(engine='model',kind='integrity_hybrid',guard={**cfg['guard'],'model_taus':[2.]},options=cfg['options']))
 rows=grid('evaluation',p['evaluation_seeds'],methods);write_csv(OUT/'evaluation.csv',rows);comparisons=[];groups=('clean','bias','outage','missing','biased','shared')
 for g in groups:
  for baseline in ('matched_pi','calibration_pi','previous_hybrid','single_model'):
   for metric in METRICS:
    diffs=[]
    for seed in p['evaluation_seeds']:
     block=[r for r in rows if r['seed']==seed and group(r,g)]
     diffs.append(mean([r for r in block if r['method']=='hybrid'])[metric]-mean([r for r in block if r['method']==baseline])[metric])
    comparisons.append(dict(group=g,baseline=baseline,metric=metric,**paired_interval(diffs)))
 means={g:{m:mean([r for r in rows if group(r,g) and r['method']==m]) for m in methods} for g in groups};checks={}
 for g in ('clean','bias','outage'):
  checks[g]={}
  for base in ('matched_pi','calibration_pi'):
   c={c['metric']:c for c in comparisons if c['group']==g and c['baseline']==base}
   checks[g][base]=dict(oxygen_passed=c['deficit_auc']['high']<0. and means[g]['hybrid']['deficit_auc']<=.9*means[g][base]['deficit_auc'],protection_passed=all(c[k]['high']<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items()))
 cells={}
 for phys in PHYS:
  for plant in PLANTS:
   for fault in FAULTS:
    for cal in CALIBRATIONS:cells['__'.join((phys,plant,fault,cal))]={m:mean([r for r in rows if (r['phys'],r['plant'],r['fault'],r['calibration'],r['method'])==(phys,plant,fault,cal,m)]) for m in methods}
 s=dict(status='completed_frozen_v114_model_bank',development_runs=4096,evaluation_runs=len(rows),methods=methods,group_means=means,cell_means=cells,comparisons=comparisons,protocol_sha256=digest(OUT/'protocol.json'),selection_sha256=digest(OUT/'selection.json'),primary=dict(checks=checks,joint_success=all(all(v.values()) for b in checks.values() for v in b.values())),version2_ready=False,clinical_validation=False,novelty_established=False)
 (OUT/'summary.json').write_text(dumps(s));runs={}
 for cell in REPLAYS:
  phys,plant,fault,cal=cell.split('__')
  for name,method in methods.items():
   r=run('evaluation',phys,plant,fault,cal,36000,method);selected=r['rows'][::3]
   if selected[-1] is not r['rows'][-1]:selected.append(r['rows'][-1])
   fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
   runs[cell+'/'+name]={k:[a[f] for a in selected] for k,f in fields.items()};runs[cell+'/'+name]['metrics']=r['metrics']
 (OUT/'replays.json').write_text(dumps(runs));print(dumps(dict(primary=s['primary'],means=means)),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('develop','evaluate'),required=True);args=parser.parse_args();develop() if args.stage=='develop' else evaluate()
