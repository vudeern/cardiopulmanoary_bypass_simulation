"""V1 closure: analytic relaxation for a fixed recorded command-ceiling stream.

This is NOT a bound for controllers that change future protection ceilings.
"""
import csv
import argparse
import hashlib
import json
import math
from pathlib import Path
import calibrated_pump_study as study
from continuity_study import patient
from perfusion_lab.model import delivery
from perfusion_lab.stress import StressScenario

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/v1-closure'


def compute():
    records=json.loads((ROOT/'results/feedback-pilot/runs.json').read_text());cases=[]
    for record in records:
        if record['method']!='pi':continue
        seed,phys,plant=record['seed'],record['physiology'],record['plant']
        p=patient(seed,'evaluation');settings=dict(study.first.previous.previous.PHYS[phys]);settings.pop('venous_bias',None)
        scenario=StressScenario(phys,**settings)
        tau=study.first.previous.previous.PLANTS[plant].get('actuator_tau',2.)
        alpha=math.exp(-1./tau);q=2.4*p.bsa;bound=0.
        with (ROOT/f'results/feedback-pilot/{seed}-{phys}-{plant}-pi.csv').open() as f:
            trace=list(csv.DictReader(f))
        for row in trace:
            cap=float(row['decision_cap']);old=q
            # Positive recurrence: u<=cap implies q_next <= alpha*q+(1-alpha)*cap.
            # Generous outward numerical allowance, far above binary64 errors
            # for the declared 0..7 L/min command range and tau=2 or 6 seconds.
            q=math.nextafter(alpha*q+(1.-alpha)*cap+1e-9,math.inf)
            flow=math.nextafter((old+q)/2.+1e-9,math.inf)
            inputs=scenario.inputs(float(row['observation_time']),600.)
            oxygen=delivery(flow,p.hb-inputs['hb_loss'],inputs['sao2'],p.bsa)+1e-8
            bound+=max(0.,280.-oxygen)/60.
        assert bound<=record['deficit_auc']+1e-6
        cases.append(dict(seed=seed,physiology=phys,plant=plant,pi_deficit_auc=record['deficit_auc'],
            relaxed_lower_deficit_auc=bound))
    mean_pi=sum(r['pi_deficit_auc'] for r in cases)/len(cases)
    mean_bound=sum(r['relaxed_lower_deficit_auc'] for r in cases)/len(cases)
    return dict(version_line='v1',cases=cases,mean_pi_deficit_auc=mean_pi,
        relaxed_lower_deficit_auc=mean_bound,maximum_reduction_fraction=1.-mean_bound/mean_pi,
        fixed_ceiling_10_percent_ruled_out=mean_bound>.9*mean_pi,
        universal_mpc_impossibility_proven=False,
        assumptions='The exact 16 PI replay cases, initial pump flow, positive first-order discrete pump dynamics, scripted oxygen content and pointwise command ceilings are held fixed. Ignore reservoir depletion, pressure and slew restrictions to give any controller an optimistic relaxation. Future state-dependent ceilings are NOT covered.',
        mathematical_argument='Positive pump dynamics imply by induction that the cap-command sequence upper-bounds requested pump flow for every sequence u[k]<=cap[k]. Empty-reservoir limiting can only reduce delivered flow. Oxygen content is exogenous and positive; therefore the relaxed cap sequence lower-bounds oxygen-deficit AUC for that fixed stream. This covers any algorithm, including MPC, within the fixed-ceiling class.',
        numerical_allowance='Add 1e-9 L/min to each pump recurrence and interval flow upper bound, and 1e-8 indexed oxygen units before computing the deficit lower bound.',
        scope_warning='The actual feedback MPC has a different state-dependent cap stream and already improves more than this fixed-PI-stream limit. The bound must not be presented as proof that MPC in general cannot reach 10%.',
        confirmation_seeds_executed=[])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    value=compute();OUT.mkdir(parents=True,exist_ok=True)
    if args.check:
        saved=json.loads((OUT/'fixed-ceiling-bound.json').read_text())
        assert not saved['universal_mpc_impossibility_proven'] and saved['fixed_ceiling_10_percent_ruled_out']
        assert abs(saved['maximum_reduction_fraction']-value['maximum_reduction_fraction'])<1e-10
        assert len(saved['cases'])==len(value['cases'])==16
        for a,b in zip(saved['cases'],value['cases']):assert abs(a['relaxed_lower_deficit_auc']-b['relaxed_lower_deficit_auc'])<1e-7
    else:(OUT/'fixed-ceiling-bound.json').write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='cases'},indent=2))
