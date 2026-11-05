"""Show individual depletion failures alongside passing development mean gates."""
import argparse
import csv
import json
import math
from pathlib import Path
from reachability_base_study import OUT,ROOT
from reachability_study import OUT as FIRST_OUT,run
from simc_benchmark import digest,dumps


def outputs():
    selection=json.loads((OUT/'selection.json').read_text());name=selection['candidate']
    catalog={**json.loads((FIRST_OUT/'protocol.json').read_text())['methods'],**json.loads((OUT/'protocol.json').read_text())['methods']}
    rows=[]
    for directory in (FIRST_OUT,OUT):
        for path in sorted((directory/'primary').glob('*.csv')):
            with path.open() as f:rows.extend(csv.DictReader(f))
    statistics={}
    for method in (name,selection['comparator'],'frozen_v1'):
        block=[r for r in rows if r['method']==method]
        low=[r for r in block if float(r['low_reservoir_s'])>0]
        worst=min(block,key=lambda r:(float(r['minimum_reservoir']),int(r['seed']),r['phys'],r['plant'],r['fault']))
        statistics[method]=dict(primary_cases=len(block),low_reservoir_cases=len(low),
            patients_with_low_reservoir=len({int(r['seed']) for r in low}),
            maximum_low_reservoir_s=max(float(r['low_reservoir_s']) for r in block),
            empty_request_cases=sum(float(r['empty_request_s'])>0 for r in block),
            minimum_reservoir_L=float(worst['minimum_reservoir']),
            lowest_case={k:(int(worst[k]) if k=='seed' else worst[k]) for k in ('seed','phys','plant','fault','calibration')})
    worst=statistics[name]['lowest_case'];case=tuple(worst[k] for k in ('phys','plant','fault','calibration'))
    key='worst_primary__seed_'+str(worst['seed'])+'__'+'__'.join(case)
    replay={};point=None
    for method in (name,selection['comparator'],'frozen_v1'):
        result=run(worst['seed'],*case,catalog[method]);sample=result['rows'][::3]+[result['rows'][-1]]
        fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
        replay[key+'/'+method]={k:[r[v] for r in sample] for k,v in fields.items()}
        replay[key+'/'+method]['metrics']=result['metrics']
        if method==name:
            lowest=min(result['rows'],key=lambda r:r['reservoir'])
            point={k:lowest.get(k) for k in ('time','observation_time','reservoir','command','bank_supported','calibration_count','calibration_age','control_level_lower','predictive_feasible','braking_budget','braking_volume')}
    risk=dict(stage='post_result_development_diagnostic',selected_candidate=name,
        statistics=statistics,worst_replay_key=key,worst_seed=worst['seed'],worst_cell=list(case),minimum_time_diagnostic=point,
        limitation='Mean exposure gates are not guarantees for individual trajectories. This worst case was selected after inspecting development results. It is not independent confirmation or a validated patient prediction.',
        summary_sha256=digest(OUT/'summary.json'),source_sha256=digest(Path(__file__)))
    return {'risk-summary.json':dumps(risk),'risk-replays.json':dumps(replay)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for name,value in outputs().items():
        path=OUT/name
        if args.check:
            def same(a,b):
                if isinstance(a,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
                if isinstance(a,list):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
                if isinstance(a,float):return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8)
                return a==b
            assert same(json.loads(path.read_text()),json.loads(value)),name
        else:path.write_text(value)
    print('PASS: all primary failure counts/extrema and three rerun worst-case views match raw development logs.')
