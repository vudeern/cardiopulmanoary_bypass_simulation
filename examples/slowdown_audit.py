"""Post-result slowdown audit. No controller tuning or paper drafts."""
import argparse,csv,json
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
import numpy as np
import scipy
from perfusion_lab.audit import witness,physical_bound
from perfusion_lab.decision_audit import audit_run
from perfusion_lab.stress import StressScenario
from perfusion_lab.benchmark import paired_interval
from integrity_study import run,patient,PHYS,PLANTS,write_csv
from simc_benchmark import digest,dumps,METRICS
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/slowdown-audit'
SOURCE=ROOT/'results/integrity-study'
CELLS=('clean__nominal__clean__good','clean__nominal__positive_start__good',
 'combined__lagged__step__good','combined__lagged__ramp__good',
 'combined__slow__positive_start__missing','combined__nominal__positive_start__shared',
 'combined__nominal__negative_start__biased','combined__nominal__clean__good')
SOURCES=('src/perfusion_lab/audit.py','src/perfusion_lab/decision_audit.py','src/perfusion_lab/integrity.py','src/perfusion_lab/simulation.py','src/perfusion_lab/stress.py','src/perfusion_lab/model.py','src/perfusion_lab/simc.py','src/perfusion_lab/sensing.py','src/perfusion_lab/reference.py','src/perfusion_lab/braking.py','examples/integrity_study.py','examples/continuity_study.py','examples/slowdown_audit.py')


def scenario(name):
 params=dict(PHYS[name]);params.pop('venous_bias',None);return StressScenario(name,**params)


def freeze():
 OUT.mkdir(parents=True,exist_ok=True)
 p=dict(status='post_result_diagnostic_no_retuning',patient_seeds=list(range(34000,34016)),cells=CELLS,
  physical_benchmark_cells='All 16 prior patient seeds x 2 physiology cases x 3 plants = 96; reference faults do not alter the physical plant inputs.',
  decision_cases='8 declared replay/stress cells x 16 patients; 3 existing controllers and 2 diagnostic closed-loop hybrid ablations = 640 runs. Only observed hybrid decisions are locally forked.',
  observed_methods=['hybrid','matched_pi','calibration_pi'],ablations=['margin_removed','true_volume'],
  witness='Best feasible of two fixed finite-grid heuristics: maximal certified command, with or without a true oxygen-demand cap. Nine commands per interval, 60-second exact future emergency rollout and analytic residual-flow tail bound. Receives true state, parameters and future disturbance schedule; not a realizable sensor-based policy or global optimum.',
  lower_bound='LP: optimistic drainage at reservoir floor and unlimited relaxed buffer, exact command slew/pump lag/pressure dynamics and true oxygen content. Primal residual and sign-clipped dual checked with a finite-box stationarity correction and 1e-7 outward subtraction. Numerical bound, not interval arithmetic. LP trajectory is not a feasible controller.',
  constraints='Reservoir >=0.25L, no empty requests, command0..7 L/min and slew0.15 L/min/s. Pressure <=95 mmHg except an explicit minimum-reachable initial-pressure envelope. Witness uses an extra 0.00001L numerical reservoir margin. No hidden removal of initial violations.',
  local_probes='Fork the identical pre-decision controller and true plant state. Test removing the interval, exact volume, enabling support, or a higher admissible command. Verify a particular emergency continuation plus true immediate oxygen gain. Counts overlap, gains cannot be summed as a jointly achievable trajectory, failed probes do not prove necessity.',
  interpretation='LP bound <= unknown feasible optimum <= feasible witness. Witness-minus-bound remains unresolved. No fresh held-out performance claim; all audited observations were previously evaluated. Counterfactual ablations may deplete or violate pressure and are never deployable recommendations.',
  controller_source_hashes_unchanged=True,source_protocol_sha256=digest(SOURCE/'protocol.json'),source_selection_sha256=digest(SOURCE/'selection.json'),source_evaluation_sha256=digest(SOURCE/'evaluation.csv'),
  source_hashes={n:digest(ROOT/n) for n in SOURCES},solver_version=scipy.__version__)
 (OUT/'protocol.json').write_text(dumps(p));print('Audit scope and source frozen. No controller changes or retuning.')


def check_sources():
 p=json.loads((OUT/'protocol.json').read_text())
 for n,h in p['source_hashes'].items():assert digest(ROOT/n)==h,n
 assert digest(SOURCE/'protocol.json')==p['source_protocol_sha256']
 assert digest(SOURCE/'selection.json')==p['source_selection_sha256']
 assert digest(SOURCE/'evaluation.csv')==p['source_evaluation_sha256']
 return p


def physical_worker(task):
 seed,phys,plant=task;p=patient(seed,'evaluation');sc=scenario(phys)
 choices={name:witness(p,sc,PLANTS[plant],oxygen_cap=cap) for name,cap in (('oxygen_capped',True),('uncapped',False))}
 feasible=[name for name,v in choices.items() if v['feasible']]
 chosen=min(feasible or list(choices),key=lambda name:choices[name]['metrics']['deficit_auc'])
 w=choices[chosen]
 value=dict(seed=seed,phys=phys,plant=plant,selected=chosen,feasible=w['feasible'],
  metrics=w['metrics'],candidates={name:dict(feasible=v['feasible'],metrics=v['metrics'],no_verified_continuation_steps=v['no_verified_continuation_steps']) for name,v in choices.items()})
 if seed==34000:value['rows']=w['rows']
 return '__'.join((str(seed),phys,plant)),value


def benchmarks():
 p=check_sources();tasks=[(seed,phys,plant) for seed in p['patient_seeds'] for phys in PHYS for plant in PLANTS];values={}
 # Witness subprocesses do not initialize LP solver thread pools. LPs are then
 # solved serially in the parent to avoid nested solver oversubscription.
 with ProcessPoolExecutor(max_workers=4,mp_context=get_context('spawn')) as pool:
  for i,(key,v) in enumerate(pool.map(physical_worker,tasks)):
   values[key]=v
   if (i+1)%12==0:print('Full-plant witness cases:',i+1,'/96',flush=True)
 for i,(key,v) in enumerate(values.items()):
  v['lp']=physical_bound(patient(v['seed'],'evaluation'),scenario(v['phys']),PLANTS[v['plant']])
  if v['lp']['success'] and v['feasible']:assert v['lp']['lower_bound']<=v['metrics']['deficit_auc']+1e-5
  if (i+1)%12==0:print('Numerically checked LP cases:',i+1,'/96',flush=True)
 (OUT/'benchmarks.json').write_text(dumps(values))


def trace(result):
 rows=result['rows'][::3]
 if rows[-1] is not result['rows'][-1]:rows.append(result['rows'][-1])
 fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
 return {**{k:[r[f] for r in rows] for k,f in fields.items()},'metrics':result['metrics']}


def decision_worker(seed):
 methods=json.loads((SOURCE/'summary.json').read_text())['methods'];records=[];counters=[];traces={};events={}
 for cell in CELLS:
  phys,plant,fault,cal=cell.split('__');p=patient(seed,'evaluation');sc=scenario(phys)
  for name in ('hybrid','matched_pi','calibration_pi','margin_removed','true_volume'):
   method=methods[name if name in methods else 'hybrid'];mode=name if name in ('margin_removed','true_volume') else 'observed'
   f=lambda:run('evaluation',phys,plant,fault,cal,seed,method)
   result=audit_run(f,p,sc,PLANTS[plant],mode=mode,record_decisions=name=='hybrid')
   records.append(dict(cell=cell,seed=seed,method=name,**{k:result['metrics'][k] for k in METRICS},minimum_reservoir=result['metrics']['minimum_reservoir'],audit_feasible=result['audit_feasible'],pressure_envelope_excess_s=result['pressure_envelope_excess_s']))
   if name=='hybrid':counters.append(dict(cell=cell,seed=seed,**result['audit_counters']))
   if seed==34000:
    traces[cell+'/'+name]=trace(result)
    if name=='hybrid':events[cell]=result['audit_events']
 return records,counters,traces,events


def decisions():
 p=check_sources();rows=[];counters=[];runs={};events={}
 with ProcessPoolExecutor(max_workers=4,mp_context=get_context('spawn')) as pool:
  for seed,result in zip(p['patient_seeds'],pool.map(decision_worker,p['patient_seeds'])):
   r,c,t,e=result;rows.extend(r);counters.extend(c);runs.update(t);events.update(e);print('Decision audit patient:',seed,flush=True)
 write_csv(OUT/'runs.csv',rows);write_csv(OUT/'decision-counts.csv',counters)
 (OUT/'replays.json').write_text(dumps(runs));(OUT/'local-events.json').write_text(dumps(events))


def summarize():
 check_sources();bench=json.loads((OUT/'benchmarks.json').read_text());rows=list(csv.DictReader((OUT/'runs.csv').open()));counts=list(csv.DictReader((OUT/'decision-counts.csv').open()))
 means={}
 for method in ('hybrid','matched_pi','calibration_pi','margin_removed','true_volume'):
  block=[r for r in rows if r['method']==method]
  means[method]={k:float(np.mean([float(r[k]) for r in block])) for k in METRICS}
  means[method]['feasible_runs']=sum(r['audit_feasible']=='True' for r in block);means[method]['runs']=len(block)
 bs=list(bench.values());selected=[]
 for r in rows:
  if r['method']!='hybrid':continue
  phys,plant,_,_=r['cell'].split('__');selected.append(bench['__'.join((str(r['seed']),phys,plant))])
 valid=[v for v in selected if v['feasible'] and v['lp']['success']]
 bounds=dict(physical_cells=len(bs),witness_feasible_cells=sum(v['feasible'] for v in bs),lp_success_cells=sum(v['lp']['success'] for v in bs),
  audit_weighted_witness_auc=float(np.mean([v['metrics']['deficit_auc'] for v in valid])),audit_weighted_lp_lower=float(np.mean([v['lp']['lower_bound'] for v in valid])),
  unresolved_witness_minus_bound=float(np.mean([v['metrics']['deficit_auc']-v['lp']['lower_bound'] for v in valid])))
 numeric=[k for k in counts[0] if k not in ('cell','seed')]
 totals={k:sum(float(r[k]) for r in counts) for k in numeric if k not in ('mean_guard_lower_error','mean_interval_width')}
 totals['mean_guard_lower_error']=float(np.mean([float(r['mean_guard_lower_error']) for r in counts]));totals['mean_interval_width']=float(np.mean([float(r['mean_interval_width']) for r in counts]))
 comparisons=[]
 for method in ('matched_pi','calibration_pi','margin_removed','true_volume'):
  for metric in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s'):
   diffs=[]
   for seed in range(34000,34016):
    a=[r for r in rows if int(r['seed'])==seed and r['method']==method];b=[r for r in rows if int(r['seed'])==seed and r['method']=='hybrid']
    diffs.append(float(np.mean([float(r[metric]) for r in a]))-float(np.mean([float(r[metric]) for r in b])))
   comparisons.append(dict(method=method,metric=metric,**paired_interval(diffs)))
 cohort=list(csv.DictReader((SOURCE/'evaluation.csv').open()));full={}
 for method in ('hybrid','matched_pi','calibration_pi','unscreened'):
  rec=[r for r in cohort if r['method']==method]
  witness_values=[bench['__'.join((r['seed'],r['phys'],r['plant']))]['metrics']['deficit_auc'] for r in rec]
  full[method]=dict(runs=len(rec),observed_deficit_auc=float(np.mean([float(r['deficit_auc']) for r in rec])),feasible_witness_auc=float(np.mean(witness_values)),
   caution='Existing cohort is reused; witness has perfect information. Observed floor/pressure violations are not excused or erased. No globally optimal controller is claimed.')
 summary=dict(status='completed_post_result_slowdown_audit',diagnostic_runs=len(rows),decision_runs=len(counts),old_cohort_runs=len(cohort),means=means,bounds=bounds,decision_counts=totals,comparisons=comparisons,old_cohort=full,
  mathematical_optimum_found=False,controller_changed=False,clinical_validation=False,
  interpretation='A feasible truth-informed witness demonstrates possibility within this model; the checked optimistic LP gives a lower bound only under its declared constraints. The remaining gap is unresolved. Removing uncertainty or supplying exact volume are diagnostic-only ablations and can violate protection. Local probe gains overlap and are not additive.')
 (OUT/'summary.json').write_text(dumps(summary));print(dumps(summary),flush=True)


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('freeze','benchmarks','decisions','summarize','all'),required=True);args=parser.parse_args()
 if args.stage=='freeze':freeze()
 elif args.stage=='benchmarks':benchmarks()
 elif args.stage=='decisions':decisions()
 elif args.stage=='summarize':summarize()
 else:freeze();benchmarks();decisions();summarize()
