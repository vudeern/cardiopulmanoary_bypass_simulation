"""Independently check the adaptive PI-base follow-up; no confirmation claims."""
import csv
import itertools
import json
import math
import numpy as np
from reachability_base_study import OUT,ROOT
from reachability_study import OUT as FIRST_OUT,REPLAY_CELLS,run,METRICS
from simc_benchmark import digest


def close(a,b):assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),(a,b)


def main():
    p=json.loads((OUT/'protocol.json').read_text())
    parent=json.loads((FIRST_OUT/'protocol.json').read_text())
    parent_selection=json.loads((FIRST_OUT/'selection.json').read_text())
    assert p['stage_one_protocol_sha256']==digest(FIRST_OUT/'protocol.json')
    assert p['stage_one_selection_sha256']==digest(FIRST_OUT/'selection.json')
    assert p['development_seeds']==list(range(37000,37032)) and p['confirmation_seeds_executed']==[]
    for name,sha in p['source_hashes'].items():assert digest(ROOT/name)==sha,name
    assert p['comparator']==parent_selection['comparator']
    assert len(p['methods'])==4
    base=parent['methods'][p['comparator']]['options']
    for name,method in p['methods'].items():
        observer='legacy' if name.endswith('legacy') else 'consistent'
        expected=parent['methods']['reserve_only' if observer=='legacy' else 'combined']
        assert method['guard']==expected['guard']
        assert method['options']['reserve_mode']=='joint'
        assert method['options']['recovery_floor']==.45
        assert method['options']['tau_c']==base['tau_c']
        assert method['options']['target_level']==(base['target_level'] if name.startswith('matched') else .35)
    records={stage:[] for stage in ('primary','secondary')}
    for directory in (FIRST_OUT,OUT):
        for stage in records:
            for seed in range(37000,37032):
                with (directory/stage/f'{seed}.csv').open() as f:rows=list(csv.DictReader(f))
                if directory==OUT:
                    cases=list(itertools.product(parent['physiology'],parent['plants'],parent['primary_faults'],('good',),p['methods'])) if stage=='primary' else list(itertools.product(parent['physiology'],parent['plants'],('positive_start',),('missing','biased','shared'),p['methods']))
                    actual=[tuple(r[k] for k in ('phys','plant','fault','calibration','method')) for r in rows]
                    assert len(actual)==len(set(actual))==len(cases) and set(actual)==set(cases)
                for row in rows:
                    assert int(row['seed'])==seed
                    row['seed']=seed
                    for metric in METRICS:row[metric]=float(row[metric]);assert math.isfinite(row[metric])
                    records[stage].append(row)
    assert len(records['primary'])==17408 and len(records['secondary'])==4608
    selection=json.loads((OUT/'selection.json').read_text());s=json.loads((OUT/'summary.json').read_text())
    assert s['protocol_sha256']==digest(OUT/'protocol.json') and s['selection_sha256']==digest(OUT/'selection.json')
    assert s['total_primary_runs']==17408 and s['total_secondary_runs']==4608
    assert not s['version2_ready'] and s['qualifying_confirmation_cohorts']==0 and s['confirmation_seeds_executed']==[]
    assert s['comparator']==p['comparator']
    def group(row,g):return row['fault']=='clean' if g=='clean' else row['fault']=='outage' if g=='outage' else row['fault'] in ('positive_start','step')
    def avg(rows,m):return sum(r[m] for r in rows)/len(rows)
    for name,actual in s['method_means'].items():
        rows=[r for r in records['primary'] if r['method']==name]
        eligible=not any(r['empty_request_s'] for r in rows)
        for g in ('clean','bias','outage'):
            subset=[r for r in rows if group(r,g)]
            eligible &= avg(subset,'low_reservoir_s')<=1
            for m in METRICS:close(avg(subset,m),actual['groups'][g][m])
        assert bool(eligible)==actual['eligible']
        for m in METRICS:close(avg(rows,m),actual['means'][m])
    candidates=list(p['methods'])+[p['stage_one_candidate']]
    stats=s['method_means'];good=[n for n in candidates if stats[n]['eligible']]
    def rank(n):
        values=stats[n]['means']
        return (values['deficit_auc'],candidates.index(n)) if good else (values['low_reservoir_s'],values['empty_request_s'],values['deficit_auc'],candidates.index(n))
    assert min(good or candidates,key=rank)==s['candidate']==selection['candidate']
    for c in s['comparisons']:
        differences=[]
        for seed in range(37000,37032):
            rows=[r for r in records['primary'] if r['seed']==seed and group(r,c['group'])]
            differences.append(avg([r for r in rows if r['method']==s['candidate']],c['metric'])-avg([r for r in rows if r['method']==c['baseline']],c['metric']))
        x=np.asarray(differences);rng=np.random.default_rng(2026)
        estimates=x[rng.integers(0,32,size=(2000,32))].mean(axis=1)
        close(float(x.mean()),c['mean']);close(float(np.quantile(estimates,.025)),c['low']);close(float(np.quantile(estimates,.975)),c['high'])
        assert c['n']==32
    for g,checks in s['development_gates'].items():
        a=stats[s['candidate']]['groups'][g];b=stats[s['comparator']]['groups'][g]
        c={v['metric']:v for v in s['comparisons'] if v['baseline']==s['comparator'] and v['group']==g}
        assert checks==dict(oxygen_mean_10_percent=a['deficit_auc']<=.9*b['deficit_auc'],oxygen_paired_interval=c['deficit_auc']['high']<0,
            mean_low_reservoir=a['low_reservoir_s']<=1,zero_empty_requests=all(r['empty_request_s']==0 for r in records['primary'] if r['method']==s['candidate'] and group(r,g)),
            extra_low_reservoir=c['low_reservoir_s']['high']<=1,extra_empty_requests=c['empty_request_s']['high']<=1,extra_high_pressure=c['high_pressure_s']['high']<=5)
    assert s['development_joint_success']==(s['candidate_eligible'] and s['comparator_eligible'] and all(all(v.values()) for v in s['development_gates'].values()))
    for cal,methods in s['secondary_means'].items():
        for name,values in methods.items():
            rows=[r for r in records['secondary'] if r['method']==name and r['calibration']==cal]
            for metric in METRICS:close(avg(rows,metric),values[metric])
    stored=json.loads((OUT/'replays.json').read_text());catalog={**parent['methods'],**p['methods']}
    names=(s['candidate'],s['comparator'],'frozen_v1');assert len(stored)==18
    fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
    for cell in REPLAY_CELLS:
        for name in names:
            result=run(37000,*cell,catalog[name]);actual=stored['__'.join(cell)+'/'+name]
            rows=result['rows'][::3]+[result['rows'][-1]]
            for key,field in fields.items():
                for row,value in zip(rows,actual[key]):
                    if isinstance(value,bool):assert row[field]==value
                    else:close(row[field],value)
            source=next(r for r in records['primary' if cell[-1]=='good' else 'secondary'] if r['seed']==37000 and tuple(r[k] for k in ('phys','plant','fault','calibration','method'))==(*cell,name))
            for metric in METRICS:close(result['metrics'][metric],actual['metrics'][metric]);close(result['metrics'][metric],source[metric])
    print('PASS: adaptive follow-up adds 2048 primary +1536 secondary runs; all 22016 development runs accounted for, selection/gates/paired intervals and 18 replays verified; confirmation untouched.')


if __name__=='__main__':main()
