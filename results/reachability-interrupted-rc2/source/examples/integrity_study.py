"""Reference-bias experiment: screening and independent calibration ablations.

Synthetic engineering logs only. No paper drafts or prose results files.
"""
import argparse,csv,json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from perfusion_lab.simulation import simulate
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from continuity_study import patient,write_csv
from simc_benchmark import digest,dumps,METRICS as PHYSICAL
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/integrity-study'
DETECT=('reference_bad_total','reference_bad_rejected','reference_good_total','reference_good_rejected','quarantine_s')
METRICS=tuple(PHYSICAL)+DETECT
PHYS={'clean':{},'combined':dict(drainage=.3,event_start=.28,event_end=.75,level_profile='ramp',reservoir_bias=.6,drift_duration=.22,venous_bias=.75,flow_bias=1.3,hb_bias=2.4,dilution=2.4,noise_scale=4.,dropout=True)}
PLANTS={'nominal':{},'slow':dict(actuator_tau=8.),'lagged':dict(actuator_tau=5.,drainage_tau=20.,venous_nonlinearity=.08)}
FAULTS={'clean':{},'positive_start':dict(fault_bias=.22),'negative_start':dict(fault_bias=-.22),
 'step':dict(profile='step',fault_bias=.28,start=210.),
 'ramp':dict(profile='ramp',fault_bias=.28,start=150.,ramp_duration=180.),
 'shared_inline':dict(common_mode_fraction=1.),'spike':dict(profile='spike',fault_bias=.3,start=300.,end=360.)}
CALIBRATIONS={'good':dict(period=120.,delay=6.,noise_sd=.01),
 'missing':dict(period=120.,delay=6.,noise_sd=.01,dropout_prob=1.),
 'biased':dict(period=120.,delay=6.,noise_sd=.01,fault_bias=.22),
 'shared':dict(period=120.,delay=6.,noise_sd=.01)}
REPLAYS=('clean__nominal__clean__good','clean__nominal__positive_start__good',
 'combined__lagged__step__good','combined__lagged__ramp__good',
 'combined__slow__positive_start__missing','combined__nominal__positive_start__shared')
DEFAULT_GUARD=dict(base_uncertainty=.04,drift_allowance=.001,audit_tolerance=.06)
SOURCES=('src/perfusion_lab/integrity.py','src/perfusion_lab/simulation.py','src/perfusion_lab/reference.py','src/perfusion_lab/simc.py','src/perfusion_lab/braking.py','src/perfusion_lab/model.py','src/perfusion_lab/stress.py','src/perfusion_lab/sensing.py','examples/continuity_study.py','examples/integrity_study.py')

def guards():return [dict(base_uncertainty=b,drift_allowance=d,audit_tolerance=t) for b in (.03,.06) for d in (.001,.004) for t in (.06,.12)]
def candidates():
 result=[]
 for i,g in enumerate(guards()):
  for kind in ('hybrid','pi'):result.append(dict(id=f'guard_{i}_{kind}',family=kind,kind='integrity_'+kind,guard=g,options={}))
 for tau in (1.5,5.,10.,20.):
  for level in (.35,.45,.55,.65):result.append(dict(id=f'calpi_{tau}_{level}',family='calpi',kind='simc',guard=DEFAULT_GUARD,options=dict(tau_c=tau,target_level=level),mode='calibration_only'))
 return result

def run(phase,phys,plant,fault,cal,seed,method,dt=1.):
 params=dict(PHYS[phys]);bias=params.pop('venous_bias',0.)
 if phase=='development' and phys=='combined':params.update(drainage=.4,reservoir_bias=.4,noise_scale=2.)
 faults=dict(FAULTS[fault])
 if phase=='development' and fault=='positive_start':faults=dict(fault_bias=.18)
 calibration=dict(CALIBRATIONS[cal])
 if cal=='shared':calibration.update(faults)
 return simulate(StressScenario(phys,**params),'sentinel',seed=seed,duration=600.,dt=dt,
  patient=patient(seed,'evaluation'),controller_kind=method['kind'],controller_options=method['options'],
  plant_options=PLANTS[plant],venous_measurement=dict(noise_sd=.015,bias=bias),
  level_mode=method.get('mode','screened'),level_reference_options=dict(period=60.,delay=4.,noise_sd=.01),
  reference_fault_options=faults,calibration_options=calibration,reference_guard_options=method['guard'])

def mean(rows):return {k:float(np.mean([float(r[k]) for r in rows])) for k in METRICS}
def worker(task):
 phase,seed,methods=task;rows=[]
 for phys in PHYS:
  for plant in (('nominal','slow') if phase=='development' else PLANTS):
   for fault in (('clean','positive_start','step') if phase=='development' else FAULTS):
    for cal in (('good','missing') if phase=='development' else CALIBRATIONS):
     for name,method in methods.items():
      r=run(phase,phys,plant,fault,cal,seed,method)
      rows.append(dict(phase=phase,phys=phys,plant=plant,fault=fault,calibration=cal,seed=seed,method=name,**{k:r['metrics'][k] for k in METRICS}))
 return rows

def grid(phase,seeds,methods):
 rows=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for seed,block in zip(seeds,pool.map(worker,[(phase,s,methods) for s in seeds])):
   rows.extend(block);print(phase,'seed complete:',seed,flush=True)
 return rows

def choose(rows):
 common=[]
 for i,g in enumerate(guards()):
  h=mean([r for r in rows if r['method']==f'guard_{i}_hybrid' and r['calibration']=='good'])
  b=mean([r for r in rows if r['method']==f'guard_{i}_pi' and r['calibration']=='good'])
  eligible=all(v[k]<=lim for v in (h,b) for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())
  common.append(dict(index=i,guard=g,hybrid=h,pi=b,eligible=eligible))
 eligible=[v for v in common if v['eligible']]
 def rank(v):
  h=v['hybrid'];return (h['deficit_auc'],v['index']) if eligible else (h['low_reservoir_s'],h['empty_request_s'],h['high_pressure_s'],h['deficit_auc'],v['index'])
 chosen=min(eligible or common,key=rank)
 vals=[v for v in candidates() if v['family']=='calpi'];means={v['id']:mean([r for r in rows if r['method']==v['id'] and r['calibration']=='good']) for v in vals}
 good=[v for v in vals if all(means[v['id']][k]<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())]
 def key(v):
  m=means[v['id']];return (m['deficit_auc'],vals.index(v)) if good else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v))
 return dict(common=chosen,common_grid=common,calpi=min(good or vals,key=key),calpi_eligible=bool(good),calpi_means=means)

def develop():
 OUT.mkdir(parents=True,exist_ok=True)
 p=dict(development_seeds=list(range(33000,33004)),evaluation_seeds=list(range(34000,34016)),duration_s=600.,dt_s=1.,candidates=candidates(),physiology=PHYS,plants=PLANTS,faults=FAULTS,calibrations=CALIBRATIONS,replay_cells=REPLAYS,
  design='8 guard settings each tested with hybrid and matched PI; 16 calibration-only PI tunings. Common guard selected jointly on good-calibration development runs only. Missing calibration remains development stress, not a selection gate. No equal total architecture-search budget claimed.',
  selection='Common guard: both matched controllers mean low/empty <=1s and pressure<=5s, then lowest hybrid oxygen deficit; else lexicographic hybrid low/empty/pressure/deficit and mark ineligible. Calibration-only PI uses the same thresholds, lowest oxygen deficit; else same lexicographic fallback.',
  primary='Good independent calibration, nonclean reference-fault profiles: hybrid low-reservoir difference vs screening-disabled ablation upper95CI<0; versus both matched screened PI and tuned calibration-only PI, upper95CI <=1s low/empty, <=5s pressure, <=5 mL O2/m2 oxygen-deficit AUC. Same non-inferiority checks under clean references. All requirements needed for joint success. Margins are engineering choices, not clinical equivalence.',
  scope='No independent calibration, biased calibration and shared corruption are secondary; no guarantee that bias is identifiable. Sensor noise is independent but fault regimes can corrupt both channels.',
  screening='Routine samples wait up to 8s for a same-acquisition calibration. Paired audits precede correction. Unpaired samples require consistency with the last calibration/inline history and, after two calibrations, mass prediction. Rejection quarantines the source and restores independent calibration correction. Engineering age allowances expand the level interval. No future/ground-truth fault magnitude enters any decision.',
  truth_labels='Only evaluation joins injected sensor bias to decisions: abs(bias)>0.04L defines a bad delivered routine sample. Fractions are observed synthetic classifications, not clinical sensitivity/specificity. Pending samples at experiment end are not counted as decided.',
  source_hashes={n:digest(ROOT/n) for n in SOURCES})
 (OUT/'protocol.json').write_text(dumps(p));rows=grid('development',p['development_seeds'],{v['id']:v for v in candidates()});write_csv(OUT/'development.csv',rows)
 selection=choose(rows);(OUT/'selection.json').write_text(dumps(selection));print(dumps(dict(common=selection['common'],calpi=selection['calpi'],calpi_eligible=selection['calpi_eligible'])),flush=True)

def in_group(r,g):
 if g=='good_cal_faults':return r['calibration']=='good' and r['fault']!='clean'
 if g=='good_cal_clean':return r['calibration']=='good' and r['fault']=='clean'
 return r['calibration']==g

def evaluate():
 p=json.loads((OUT/'protocol.json').read_text());sel=json.loads((OUT/'selection.json').read_text())
 for n,h in p['source_hashes'].items():assert digest(ROOT/n)==h,n
 guard=sel['common']['guard'];methods=dict(hybrid=dict(kind='integrity_hybrid',options={},guard=guard),matched_pi=dict(kind='integrity_pi',options={},guard=guard),calibration_pi=sel['calpi'],unscreened=dict(kind='integrity_hybrid',options={},guard={**guard,'screen':False}))
 rows=grid('evaluation',p['evaluation_seeds'],methods);write_csv(OUT/'evaluation.csv',rows)
 groups=('good_cal_faults','good_cal_clean','missing','biased','shared');comparisons=[]
 for g in groups:
  for baseline in ('matched_pi','calibration_pi','unscreened'):
   for metric in PHYSICAL:
    diffs=[]
    for seed in p['evaluation_seeds']:
     block=[r for r in rows if r['seed']==seed and in_group(r,g)]
     diffs.append(mean([r for r in block if r['method']=='hybrid'])[metric]-mean([r for r in block if r['method']==baseline])[metric])
    comparisons.append(dict(group=g,baseline=baseline,metric=metric,**paired_interval(diffs)))
 checks={}
 for g in ('good_cal_faults','good_cal_clean'):
  checks[g]={}
  for baseline in ('matched_pi','calibration_pi'):
   c={r['metric']:r for r in comparisons if r['group']==g and r['baseline']==baseline}
   checks[g][baseline]=all(c[k]['high']<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.,deficit_auc=5.).items())
 benefit=next(c['high'] for c in comparisons if c['group']=='good_cal_faults' and c['baseline']=='unscreened' and c['metric']=='low_reservoir_s')<0.
 cells={}
 for phys in PHYS:
  for plant in PLANTS:
   for fault in FAULTS:
    for cal in CALIBRATIONS:
     key='__'.join((phys,plant,fault,cal));cells[key]={m:mean([r for r in rows if (r['phys'],r['plant'],r['fault'],r['calibration'],r['method'])==(phys,plant,fault,cal,m)]) for m in methods}
 summary=dict(status='completed_frozen_reference_integrity_study',development_runs=3072,evaluation_runs=len(rows),methods=methods,protocol_sha256=digest(OUT/'protocol.json'),selection_sha256=digest(OUT/'selection.json'),
  cell_means=cells,group_means={g:{m:mean([r for r in rows if in_group(r,g) and r['method']==m]) for m in methods} for g in groups},comparisons=comparisons,
  primary=dict(noninferiority=checks,screening_reservoir_benefit=benefit,joint_success=benefit and all(all(b.values()) for b in checks.values())),clinical_validation=False,novelty_established=False)
 (OUT/'summary.json').write_text(dumps(summary));runs={};decisions={}
 for cell in REPLAYS:
  phys,plant,fault,cal=cell.split('__')
  for name,method in methods.items():
   result=run('evaluation',phys,plant,fault,cal,34000,method);selected=result['rows'][::3]
   if selected[-1] is not result['rows'][-1]:selected.append(result['rows'][-1])
   fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
   runs[cell+'/'+name]={k:[r[f] for r in selected] for k,f in fields.items()};runs[cell+'/'+name]['metrics']=result['metrics']
   decisions[cell+'/'+name]=[{k:r.get(k) for k in ('observation_time','reference_events','reference_quarantined','reference_uncertainty','calibration_age','calibration_count','recovery_supported','override_delta')} for r in result['rows'] if r['reference_events'] or r['observation_time']%60==0]
 (OUT/'replays.json').write_text(dumps(runs));(OUT/'decisions.json').write_text(dumps(decisions));print(dumps(dict(primary=summary['primary'],group_means=summary['group_means'])),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('develop','evaluate'),required=True);args=parser.parse_args();develop() if args.stage=='develop' else evaluate()
