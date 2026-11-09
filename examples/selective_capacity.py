"""Analytic steady-state capacity screen, not a dynamic optimal controller.

Uses known synthetic parameters/faults only in this offline diagnostic. A lower
steady capacity cannot prove a finite-duration target infeasible: stored volume
and pressure transients can bridge intervals. It never changes success criteria.
"""
import argparse,json
from pathlib import Path
import numpy as np
from perfusion_lab.model import oxygen_content
from perfusion_lab.stress import StressScenario
from selective_study import patient,FINAL_CASES,FINAL_PLANTS,write_csv
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/selective-study'

def output():
 protocol=json.loads((OUT/'protocol.json').read_text());rows=[]
 for seed in protocol['evaluation_seeds']:
  p=patient(seed,'evaluation')
  for case,params in FINAL_CASES.items():
   params=dict(params);params.pop('venous_bias',None);scenario=StressScenario(case,**params)
   for name,plant in FINAL_PLANTS.items():
    capacities=[]
    for t in range(600):
     inputs=scenario.inputs(t,600.)
     filling=max(0.,(p.volume-.25-p.unstressed_volume)/p.venous_compliance)
     qv=min(plant.get('max_drainage',7.5),inputs['drainage']*filling/(p.venous_resistance*(1.+plant.get('venous_nonlinearity',0.)*filling)))
     q=min(7.,95./p.resistance,qv)
     capacities.append(10.*q*oxygen_content(p.hb-inputs['hb_loss'],inputs['sao2'])/p.bsa)
    rows.append(dict(seed=seed,case=case,plant=name,steady_capacity_below_target_s=sum(c<280. for c in capacities),steady_capacity_deficit_auc=float(sum(max(0.,280.-c) for c in capacities)/60.),minimum_steady_capacity=min(capacities)))
 return rows

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();rows=output()
 value=dict(status='offline_steady_state_capacity_screen',rows=len(rows),mean_capacity_below_target_s=float(np.mean([r['steady_capacity_below_target_s'] for r in rows])),fraction_cells_with_any_capacity_shortfall=float(np.mean([r['steady_capacity_below_target_s']>0 for r in rows])),finite_horizon_feasibility_proved=False,controller_oracle=False,primary_criterion_changed=False)
 path=OUT/'capacity-summary.json'
 if args.check:
  import csv
  old=list(csv.DictReader((OUT/'capacity.csv').open()));assert len(old)==len(rows)
  for a,b in zip(old,rows):
   for k,v in b.items():
    if isinstance(v,str):assert a[k]==v
    else:assert abs(float(a[k])-v)<1e-8
  assert value==json.loads(path.read_text());print('PASS: 512-cell offline steady-state capacity screen; no dynamic optimality or finite-horizon feasibility claim.')
 else:write_csv(OUT/'capacity.csv',rows);path.write_text(json.dumps(value,indent=2)+'\n');print(value)
