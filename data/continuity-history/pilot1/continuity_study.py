"""Development and frozen evaluation of the reference-continuity controller.

Engineering logs only. No paper drafts or prose result files are generated.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate
from perfusion_lab.benchmark import paired_interval
from simc_benchmark import dumps,digest,METRICS

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/continuity-study'
DEV_CASES={
 'clean':dict(), 'drainage':dict(drainage=.4,event_start=.3,event_end=.7),
 'drift':dict(level_profile='ramp',reservoir_bias=.4,drift_duration=.25),
 'initial':dict(level_profile='initial',reservoir_bias=.4),
 'venous_bias':dict(venous_bias=.5),
 'combined':dict(drainage=.4,level_profile='ramp',reservoir_bias=.4,drift_duration=.25,
                 venous_bias=.5,flow_bias=.9,hb_bias=1.8,dilution=1.8,noise_scale=2.)}
FINAL_CASES={
 'clean':dict(), 'drainage':dict(drainage=.3,event_start=.28,event_end=.75),
 'drift':dict(level_profile='ramp',reservoir_bias=.6,drift_duration=.22),
 'initial':dict(level_profile='initial',reservoir_bias=.6),
 'venous_bias':dict(venous_bias=.75), 'arterial_bias':dict(flow_bias=1.3),
 'combined':dict(drainage=.3,event_start=.28,event_end=.75,level_profile='ramp',reservoir_bias=.6,
    drift_duration=.22,venous_bias=.75,flow_bias=1.3,hb_bias=2.4,dilution=2.4,noise_scale=4.,dropout=True),
 'negative_venous_bias':dict(venous_bias=-.75)}
DEV_PLANTS={'nominal':{},'slow':dict(actuator_tau=6.)}
FINAL_PLANTS={'nominal':{},'slow':dict(actuator_tau=8.),
 'lagged':dict(actuator_tau=5.,drainage_tau=20.,venous_nonlinearity=.08),
 'outside_lag_bound':dict(actuator_tau=12.)}
REFS={'good':dict(period=60.,delay=4.,noise_sd=.01),
 'delayed_loss':dict(period=75.,delay=25.,noise_sd=.02,dropout_prob=.2,outage_start=120.,outage_end=540.),
 'biased':dict(period=60.,delay=4.,noise_sd=.02,bias=.18),
 'never':dict(period=60.,delay=4.,noise_sd=.01,dropout_prob=1.)}
REPLAYS=('clean__nominal__good','drainage__slow__good','venous_bias__nominal__good',
 'combined__lagged__good','combined__lagged__delayed_loss','initial__outside_lag_bound__biased')


def candidates():
 return ([dict(id=f'continuity_{q}_{base}_{tau}',family='continuity',kind='continuity',
           options=dict(venous_allowance=q,base_allowance=base,nominal_tau=tau,age_allowance=.0001))
          for q in (.05,.2) for base in (.02,.06) for tau in (2.,4.,6.,8.)] +
         [dict(id=f'simc_{tau}_{level}',family='simc',kind='simc',options=dict(tau_c=tau,target_level=level))
          for tau in (1.5,5.,10.,20.) for level in (.35,.45,.55,.65)])


def patient(seed,phase):
 if phase=='development':return Patient.sampled(seed)
 rng=np.random.default_rng(seed+90000)
 return Patient(bsa=float(rng.uniform(1.35,2.35)),hb=float(rng.uniform(7.6,11.2)),
  resistance=float(rng.uniform(9.5,20.5)),compliance=float(rng.uniform(.0011,.0026)),
  venous_compliance=float(rng.uniform(.085,.16)),venous_resistance=float(rng.uniform(.7,1.15)))


def run(phase,case,plant,reference,seed,method,dt=1.):
 params=dict((DEV_CASES if phase=='development' else FINAL_CASES)[case]);bias=params.pop('venous_bias',0.)
 return simulate(StressScenario(case,**params),'sentinel',seed=seed,duration=600.,dt=dt,
  patient=patient(seed,phase),controller_kind=method['kind'],controller_options=method['options'],
  plant_options=(DEV_PLANTS if phase=='development' else FINAL_PLANTS)[plant],
  venous_measurement=dict(noise_sd=.015,bias=bias),level_mode='hold',level_reference_options=REFS[reference])


def mean(rows):return {k:float(np.mean([float(r[k]) for r in rows])) for k in METRICS}

def choose(rows,family):
 values=[v for v in candidates() if v['family']==family]
 means={v['id']:mean([r for r in rows if r['method']==v['id']]) for v in values}
 eligible=[v for v in values if means[v['id']]['low_reservoir_s']<=1.
           and means[v['id']]['empty_request_s']<=1. and means[v['id']]['high_pressure_s']<=5.]
 def rank(v):
  m=means[v['id']]
  return ((m['deficit_auc'],values.index(v)) if eligible else
     (m['low_reservoir_s'],m['empty_request_s'],m['high_pressure_s'],m['deficit_auc'],values.index(v)))
 return dict(method=min(eligible or values,key=rank),matched_development_budget=bool(eligible),means=means)


def write_csv(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def develop():
 OUT.mkdir(parents=True,exist_ok=True)
 protocol=dict(development_seeds=list(range(27000,27004)),evaluation_seeds=list(range(28000,28016)),
  duration_s=600.,dt_s=1.,candidates=candidates(),development_cases=DEV_CASES,final_cases=FINAL_CASES,
  development_plants=DEV_PLANTS,final_plants=FINAL_PLANTS,references=REFS,replay_cells=list(REPLAYS),
  development_references=['good','delayed_loss'],
  primary_scope='Two co-primary groups: good and delayed_loss references, nominal/slow/lagged plants. Biased/never references and tau12 are secondary.',
  primary='Continuity minus SIMC in EACH co-primary group: upper paired CI <=1s low reservoir, <=1s empty requests, <=5s high pressure, and oxygen deficit upper CI <0. Joint success requires both groups.',
  selection='16 candidates/family, same 3072-run development budget; lowest mean deficit with mean low/empty <=1s and pressure <=5s, else lexicographic low/empty/pressure/deficit; mark unmatched.',
  assumptions='Reference-acquisition-anchored integration, nominal first-order pump model, venous bias fitted from consecutive references and bounded to +/-2 L/min. Residual model error allowance grows linearly with reference age. None is a guaranteed statistical bound. Constant bias in references and no reference at all can invalidate the estimate.',
  shared='Same sensor/reference channels, common Hb observer, oxygen cap, pressure slowdown90, flow0..7 and slew.15. The continuity method directly buffers the same delivered reference samples; PI uses their held inline correction.',
  context='v1.9 braking settings retained as fixed context; not retuned. Previous evaluation informed this architecture and scenario families are reused; only final patient/noise seeds are fresh. This is not independent clinical/model validation.',
  source_hashes={p:digest(ROOT/p) for p in ('src/perfusion_lab/continuity.py','src/perfusion_lab/braking.py','src/perfusion_lab/simulation.py','src/perfusion_lab/sensing.py','src/perfusion_lab/reference.py','src/perfusion_lab/simc.py','src/perfusion_lab/stress.py','src/perfusion_lab/model.py','examples/continuity_study.py')})
 (OUT/'protocol.json').write_text(dumps(protocol));rows=[]
 for seed in protocol['development_seeds']:
  for case in DEV_CASES:
   for plant in DEV_PLANTS:
    for reference in ('good','delayed_loss'):
     for method in candidates():
      result=run('development',case,plant,reference,seed,method)
      rows.append(dict(phase='development',case=case,plant=plant,reference=reference,seed=seed,
        method=method['id'],**{k:result['metrics'][k] for k in METRICS}))
  print('Development seed complete:',seed,flush=True)
 write_csv(OUT/'development.csv',rows)
 selection={family:choose(rows,family) for family in ('continuity','simc')}
 (OUT/'selection.json').write_text(dumps(selection))
 print(dumps({family:{'method':s['method'],'eligible':s['matched_development_budget'],
    'metrics':s['means'][s['method']['id']]} for family,s in selection.items()}),flush=True)


def evaluate():
 p=json.loads((OUT/'protocol.json').read_text());selection=json.loads((OUT/'selection.json').read_text())
 for name,value in p['source_hashes'].items():assert digest(ROOT/name)==value,'Source changed after development: '+name
 methods={f:v['method'] for f,v in selection.items()}
 methods['previous_braking']=dict(id='previous_braking',kind='braking',options=dict(venous_allowance=.4,base_allowance=.12,drift_allowance=.0005,rate_multiplier=1.))
 selection_hash=digest(OUT/'selection.json');rows=[]
 for seed in p['evaluation_seeds']:
  for case in FINAL_CASES:
   for plant in FINAL_PLANTS:
    for reference in REFS:
     for label,method in methods.items():
      result=run('evaluation',case,plant,reference,seed,method)
      rows.append(dict(phase='evaluation',case=case,plant=plant,reference=reference,seed=seed,
        method=label,**{k:result['metrics'][k] for k in METRICS}))
  print('Evaluation seed complete:',seed,flush=True)
 write_csv(OUT/'evaluation.csv',rows)
 def in_group(r,g):
  if g=='primary':return r['reference'] in ('good','delayed_loss') and r['plant']!='outside_lag_bound'
  if g in ('good','delayed_loss'):return r['reference']==g and r['plant']!='outside_lag_bound'
  return r['plant']=='outside_lag_bound' if g=='outside_lag_bound' else r['reference']==g
 comparisons=[]
 groups=('primary','good','delayed_loss','biased','never','outside_lag_bound')
 for group in groups:
  filtered=[r for r in rows if in_group(r,group)]
  for label in ('continuity','previous_braking'):
   for metric in METRICS:
    diffs=[]
    for seed in p['evaluation_seeds']:
     block=[r for r in filtered if r['seed']==seed]
     diffs.append(mean([r for r in block if r['method']==label])[metric]-mean([r for r in block if r['method']=='simc'])[metric])
    comparisons.append(dict(group=group,method=label,metric=metric,**paired_interval(diffs)))
 tests={}
 for group in ('good','delayed_loss'):
  c={c['metric']:c for c in comparisons if c['group']==group and c['method']=='continuity'}
  protection=all(c[k]['high']<=limit for k,limit in dict(low_reservoir_s=1.,empty_request_s=1.,high_pressure_s=5.).items())
  tests[group]=dict(protection_passed=protection,oxygen_passed=c['deficit_auc']['high']<0.)
 cells={}
 for case in FINAL_CASES:
  for plant in FINAL_PLANTS:
   for reference in REFS:
    cells[case+'__'+plant+'__'+reference]={m:mean([r for r in rows if r['case']==case and r['plant']==plant and r['reference']==reference and r['method']==m]) for m in methods}
 group_means={g:{m:mean([r for r in rows if in_group(r,g) and r['method']==m]) for m in methods} for g in groups}
 summary=dict(status='completed_frozen_continuity_comparison',development_runs=3072,evaluation_runs=len(rows),
  methods=methods,selection_sha256=selection_hash,protocol_sha256=digest(OUT/'protocol.json'),
  cell_means=cells,group_means=group_means,comparisons=comparisons,
  primary=dict(groups=tests,demonstrated_joint_advantage=all(all(v.values()) for v in tests.values())),
  clinical_validation=False,novelty_established=False)
 (OUT/'summary.json').write_text(dumps(summary));runs={}
 for cell in REPLAYS:
  case,plant,reference=cell.split('__')
  for label,method in methods.items():
   result=run('evaluation',case,plant,reference,28000,method)
   fields={'t':'time','do2':'do2','monitor':'measured_do2','reservoir':'reservoir','pressure':'pressure',
     'infeasible':'infeasible','fault':'fault','level_fault':'level_fault','level_sensor':'observed_reservoir',
     'level_lower':'control_level_lower' if label in ('continuity','previous_braking') else 'level_reference_lower'}
   selected=result['rows'][::3]
   if selected[-1] is not result['rows'][-1]:selected.append(result['rows'][-1])
   runs[cell+'/'+label]={k:[r[v] for r in selected] for k,v in fields.items()};runs[cell+'/'+label]['metrics']=result['metrics']
 (OUT/'replays.json').write_text(dumps(runs))
 print(dumps(dict(primary=summary['primary'],means=group_means['primary'])),flush=True)


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('develop','evaluate'),required=True)
 args=parser.parse_args();develop() if args.stage=='develop' else evaluate()
