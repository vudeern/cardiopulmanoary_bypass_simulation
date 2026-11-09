"""Frozen PI-override experiment with component ablations and fresh seeds.

Engineering simulation logs only; no paper drafts are produced.
"""
import argparse,csv,json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from perfusion_lab.simulation import simulate
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from continuity_study import patient,write_csv,mean,FINAL_CASES,FINAL_PLANTS,REFS,REPLAYS
from simc_benchmark import digest,dumps,METRICS
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/selective-study'
DEV_CASES={**FINAL_CASES}
DEV_CASES['combined']={**DEV_CASES['combined'],'drainage':.4,'noise_scale':2.,'reservoir_bias':.4,'venous_bias':.5}
DEV_PLANTS={'nominal':{},'slow':dict(actuator_tau=6.)}
FAST_PI=dict(id='fast_pi',kind='simc',options=dict(tau_c=1.5,target_level=.45))
SOURCES=('src/perfusion_lab/selective.py','src/perfusion_lab/simulation.py','src/perfusion_lab/sensing.py','src/perfusion_lab/reference.py','src/perfusion_lab/simc.py','src/perfusion_lab/braking.py','src/perfusion_lab/stress.py','src/perfusion_lab/model.py','examples/continuity_study.py','examples/selective_study.py')

def candidates():
 return ([dict(id=f'selective_{base}_{gate}_{age}_{strength}',family='selective',kind='selective',options=dict(base_allowance=base,agreement=gate,max_age=age,strength=strength))
  for base in (.04,.1) for gate in (.08,.2) for age in (90.,180.) for strength in (.25,1.)]+[
  dict(id=f'simc_{tau}_{level}',family='simc',kind='simc',options=dict(tau_c=tau,target_level=level))
  for tau in (1.5,5.,10.,20.) for level in (.35,.45,.55,.65)])

def run(phase,case,plant,ref,seed,method,dt=1.):
 params=dict((DEV_CASES if phase=='development' else FINAL_CASES)[case]);bias=params.pop('venous_bias',0.)
 return simulate(StressScenario(case,**params),'sentinel',seed=seed,duration=600.,dt=dt,
  patient=patient(seed,'evaluation'),controller_kind=method['kind'],controller_options=method['options'],
  plant_options=(DEV_PLANTS if phase=='development' else FINAL_PLANTS)[plant],
  venous_measurement=dict(noise_sd=.015,bias=bias),level_mode='hold',level_reference_options=REFS[ref])

def choose(rows,family):
 vals=[v for v in candidates() if v['family']==family]
 means={v['id']:mean([r for r in rows if r['method']==v['id']]) for v in vals}
 by_reference={v['id']:{ref:mean([r for r in rows if r['method']==v['id'] and r['reference']==ref]) for ref in ('good','delayed_loss')} for v in vals}
 eligible=[v for v in vals if all(by_reference[v['id']][ref][k]<=lim for ref in ('good','delayed_loss') for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())]
 def rank(v):
  m=means[v['id']]
  return (m['deficit_auc'],vals.index(v)) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],vals.index(v))
 return dict(method=min(eligible or vals,key=rank),eligible=bool(eligible),means=means,by_reference=by_reference)

def worker(task):
 phase,seed,methods=task;rows=[]
 for case in (DEV_CASES if phase=='development' else FINAL_CASES):
  for plant in (DEV_PLANTS if phase=='development' else FINAL_PLANTS):
   for ref in (('good','delayed_loss') if phase=='development' else REFS):
    for label,method in methods.items():
     result=run(phase,case,plant,ref,seed,method)
     rows.append(dict(phase=phase,case=case,plant=plant,reference=ref,seed=seed,method=label,**{k:result['metrics'][k] for k in METRICS}))
 return rows

def grid(phase,seeds,methods):
 rows=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for seed,block in zip(seeds,pool.map(worker,[(phase,seed,methods) for seed in seeds])):
   rows.extend(block);print(phase,'seed complete:',seed,flush=True)
 return rows

def develop():
 OUT.mkdir(parents=True,exist_ok=True)
 p=dict(development_seeds=list(range(30000,30004)),evaluation_seeds=list(range(31000,31016)),duration_s=600.,dt_s=1.,candidates=candidates(),development_cases=DEV_CASES,final_cases=FINAL_CASES,development_plants=DEV_PLANTS,final_plants=FINAL_PLANTS,references=REFS,replay_cells=REPLAYS,
  selection='16 candidates per family. Minimum pooled oxygen deficit among candidates meeting <=1s mean low/empty and <=5s pressure separately in both development reference groups; otherwise lexicographic low/empty/pressure/deficit, marked ineligible.',
  primary='Hybrid minus each of selected SIMC and fixed fast PI, separately for good and delayed_loss references and in-range plants: paired upper95 CI <=1s low reservoir, <=1s empty, <=5s pressure, and oxygen deficit upper95 CI <0. All four comparisons must pass.',
  ablations='Selected hybrid parameters with brake_only or boost_only; no further tuning. Development and final outputs retained separately. Disabled-override unit test must reproduce identical PI numerics.',
  gate='At least two distinct delivered reference acquisitions, age within configured limit, and mass-balance/held-inline disagreement within configured allowance. Weight changes at most 0.1 per second. PI tracks actual applied command. Agreement does not certify correctness or clinical safety; blended action is not a hard braking bound.',
  fairness='Same information channels, oxygen/pressure limits and pump constraints. Hybrid has fixed internal SIMC settings tau_c1.5 and target0.45; its 16 choices tune only the override. PI has 16 gain/setpoint choices. Earlier architectures informed this design; equal total research effort is not claimed. Fresh seeds do not make scenario families or model independent.',
  development_population='Same wide synthetic parameter ranges used in final evaluation, with disjoint patient/noise seeds; no clinical population calibration.',
  source_hashes={n:digest(ROOT/n) for n in SOURCES})
 (OUT/'protocol.json').write_text(dumps(p))
 rows=grid('development',p['development_seeds'],{v['id']:v for v in candidates()});write_csv(OUT/'development.csv',rows)
 selection={f:choose(rows,f) for f in ('selective','simc')};(OUT/'selection.json').write_text(dumps(selection))
 method=selection['selective']['method'];ablations={mode:dict(id=mode,kind='selective',options={**method['options'],'mode':mode}) for mode in ('brake_only','boost_only')}
 ablated=grid('development',p['development_seeds'],ablations);write_csv(OUT/'development-ablations.csv',ablated)
 (OUT/'development-ablation-summary.json').write_text(dumps({m:mean([r for r in ablated if r['method']==m]) for m in ablations}))
 print(dumps({f:dict(method=v['method'],eligible=v['eligible'],means=v['means'][v['method']['id']]) for f,v in selection.items()}),flush=True)

def in_group(r,g):
 if g=='primary':return r['reference'] in ('good','delayed_loss') and r['plant']!='outside_lag_bound'
 if g in ('good','delayed_loss'):return r['reference']==g and r['plant']!='outside_lag_bound'
 return r['plant']=='outside_lag_bound' if g=='outside_lag_bound' else r['reference']==g

def evaluate():
 p=json.loads((OUT/'protocol.json').read_text());sel=json.loads((OUT/'selection.json').read_text())
 for n,h in p['source_hashes'].items():assert digest(ROOT/n)==h,n
 methods=dict(hybrid=sel['selective']['method'],simc=sel['simc']['method'],fast_pi=FAST_PI)
 for mode in ('brake_only','boost_only'):methods[mode]=dict(id=mode,kind='selective',options={**methods['hybrid']['options'],'mode':mode})
 selection_hash=digest(OUT/'selection.json');rows=grid('evaluation',p['evaluation_seeds'],methods);write_csv(OUT/'evaluation.csv',rows)
 groups=('primary','good','delayed_loss','biased','never','outside_lag_bound');comparisons=[]
 for g in groups:
  for baseline in ('simc','fast_pi'):
   for method in ('hybrid','brake_only','boost_only'):
    for metric in METRICS:
     diffs=[]
     for seed in p['evaluation_seeds']:
      block=[r for r in rows if r['seed']==seed and in_group(r,g)]
      diffs.append(mean([r for r in block if r['method']==method])[metric]-mean([r for r in block if r['method']==baseline])[metric])
     comparisons.append(dict(group=g,baseline=baseline,method=method,metric=metric,**paired_interval(diffs)))
 tests={}
 for g in ('good','delayed_loss'):
  tests[g]={}
  for baseline in ('simc','fast_pi'):
   c={c['metric']:c for c in comparisons if c['group']==g and c['baseline']==baseline and c['method']=='hybrid'}
   tests[g][baseline]=dict(protection_passed=all(c[k]['high']<=lim for k,lim in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items()),oxygen_passed=c['deficit_auc']['high']<0.)
 cells={}
 for case in FINAL_CASES:
  for plant in FINAL_PLANTS:
   for ref in REFS:
    cells[case+'__'+plant+'__'+ref]={m:mean([r for r in rows if (r['case'],r['plant'],r['reference'],r['method'])==(case,plant,ref,m)]) for m in methods}
 summary=dict(status='completed_frozen_selective_pi_comparison',development_runs=4096,development_ablation_runs=256,evaluation_runs=len(rows),methods=methods,protocol_sha256=digest(OUT/'protocol.json'),selection_sha256=selection_hash,
  cell_means=cells,group_means={g:{m:mean([r for r in rows if in_group(r,g) and r['method']==m]) for m in methods} for g in groups},comparisons=comparisons,
  primary=dict(tests=tests,demonstrated_joint_advantage=all(all(v.values()) for b in tests.values() for v in b.values())),clinical_validation=False,novelty_established=False)
 (OUT/'summary.json').write_text(dumps(summary));runs={}
 for cell in REPLAYS:
  case,plant,ref=cell.split('__')
  for label,method in methods.items():
   result=run('evaluation',case,plant,ref,31000,method)
   selected=result['rows'][::3]
   if selected[-1] is not result['rows'][-1]:selected.append(result['rows'][-1])
   fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='control_level_lower' if method['kind']=='selective' else 'level_reference_lower')
   runs[cell+'/'+label]={k:[r[f] for r in selected] for k,f in fields.items()};runs[cell+'/'+label]['metrics']=result['metrics']
 (OUT/'replays.json').write_text(dumps(runs))
 print(dumps(dict(primary=summary['primary'],group_means=summary['group_means'])),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('develop','evaluate'),required=True);args=parser.parse_args()
 develop() if args.stage=='develop' else evaluate()
