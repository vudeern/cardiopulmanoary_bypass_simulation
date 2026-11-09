"""Recalculate rc.2 development accounting, selection, paired statistics and replays."""
import csv
import itertools
import json
import math
from pathlib import Path
import numpy as np
from reachability_study import OUT,ROOT,METRICS,REPLAY_CELLS,run
from simc_benchmark import digest


def close(a,b):
    assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),(a,b)


def main():
    interrupted=ROOT/'results/reachability-interrupted-rc2'
    old=json.loads((interrupted/'protocol.json').read_text())
    assert json.loads((interrupted/'status.json').read_text())['status']=='interrupted_not_complete_evidence'
    for name,sha in old['source_hashes'].items():assert digest(interrupted/'source'/name)==sha,name
    assert len(list((interrupted/'primary').glob('*.csv')))==12
    p=json.loads((OUT/'protocol.json').read_text())
    correction=OUT/'runner-correction'
    original=json.loads((correction/'protocol.json').read_text())
    note=json.loads((correction/'correction.json').read_text())
    assert digest(correction/'reachability_study.py')==note['old_runner_sha256']
    assert digest(ROOT/'examples/reachability_study.py')==note['new_runner_sha256']
    original['source_hashes']['examples/reachability_study.py']=note['new_runner_sha256']
    assert original==p,'Runner correction changed experiment settings'
    for name,sha in note['primary_csv_sha256'].items():assert digest(OUT/'primary'/name)==sha
    for name,sha in p['source_hashes'].items():assert digest(ROOT/name)==sha,name
    assert p['development_seeds']==list(range(37000,37032))
    assert p['confirmation_seeds_executed']==[] and p['stage']=='development_only'
    catalog=p['methods'];seeds=p['development_seeds'];blocks={};counts={}
    selection=json.loads((OUT/'selection.json').read_text())
    secondary_methods=[n for n,m in catalog.items() if m['family'] in ('candidate','reference')]+list(selection['pi_by_observer'].values())
    for stage in ('primary','secondary'):
        counts[stage]=0
        for seed in seeds:
            with (OUT/stage/f'{seed}.csv').open() as handle:rows=list(csv.DictReader(handle))
            expected=set(itertools.product(p['physiology'],p['plants'],p['primary_faults'],('good',),catalog)) if stage=='primary' else set(itertools.product(p['physiology'],p['plants'],('positive_start',),('missing','biased','shared'),secondary_methods))
            seen=set()
            for r in rows:
                assert int(r['seed'])==seed
                key=(r['phys'],r['plant'],r['fault'],r['calibration'],r['method'])
                assert key in expected and key not in seen,key
                seen.add(key)
                for m in METRICS:r[m]=float(r[m]);assert math.isfinite(r[m]),(key,m)
                for m in ('low_reservoir_s','empty_request_s','high_pressure_s','lower_undercoverage_s','bank_supported_s','bank_conflict_s'):assert 0<=r[m]<=600
                assert min(r[m] for m in ('deficit_auc','volume_mae_L','mean_halfwidth_L','minimum_reservoir'))>=0
                blocks[(seed,*key)]=r
            assert seen==expected,(stage,seed,len(seen),len(expected))
            counts[stage]+=len(rows)
    assert counts==dict(primary=p['primary_runs'],secondary=p['secondary_runs'])
    # The input-domain correction changes none of the already completed runs.
    for old_csv in (interrupted/'primary').glob('*.csv'):
        assert digest(old_csv)==digest(OUT/'primary'/old_csv.name),old_csv.name
    primary=[r for key,r in blocks.items() if key[-2]=='good']
    def in_group(r,g):return r['fault']=='clean' if g=='clean' else r['fault']=='outage' if g=='outage' else r['fault'] in ('positive_start','step')
    def average(rows,metric):return sum(r[metric] for r in rows)/len(rows)
    stats={}
    for name in catalog:
        rows=[r for r in primary if r['method']==name]
        groups={g:{m:average([r for r in rows if in_group(r,g)],m) for m in METRICS} for g in ('clean','bias','outage')}
        eligible=all(v['low_reservoir_s']<=1 for v in groups.values()) and not any(r['empty_request_s'] for r in rows)
        actual=selection['all_methods'][name]
        assert eligible==actual['eligible']
        for m in METRICS:
            close(average(rows,m),actual['means'][m])
            for g in groups:close(groups[g][m],actual['groups'][g][m])
        stats[name]=(eligible,{m:average(rows,m) for m in METRICS})
    def choose(names):
        good=[n for n in names if stats[n][0]]
        return min(good or names,key=lambda n:(stats[n][1]['deficit_auc'],names.index(n)) if good else (stats[n][1]['low_reservoir_s'],stats[n][1]['empty_request_s'],stats[n][1]['deficit_auc'],names.index(n)))
    assert choose([n for n,m in catalog.items() if m['family']=='candidate'])==selection['candidate']
    assert choose([n for n,m in catalog.items() if m['family']=='pi'])==selection['comparator']
    for observer,name in selection['pi_by_observer'].items():assert choose([n for n,m in catalog.items() if m.get('observer')==observer])==name
    summary=json.loads((OUT/'summary.json').read_text())
    assert summary['protocol_sha256']==digest(OUT/'protocol.json')
    assert summary['selection_sha256']==digest(OUT/'selection.json')
    assert summary['primary_runs']==counts['primary'] and summary['secondary_runs']==counts['secondary']
    assert not summary['version2_ready'] and summary['qualifying_confirmation_cohorts']==0 and summary['confirmation_seeds_executed']==[]
    for c in summary['comparisons']:
        values=[]
        for seed in seeds:
            rows=[r for key,r in blocks.items() if key[0]==seed and key[-2]=='good' and in_group(r,c['group'])]
            values.append(average([r for r in rows if r['method']==selection['candidate']],c['metric'])-average([r for r in rows if r['method']==c['baseline']],c['metric']))
        rng=np.random.default_rng(2026);data=np.array(values)
        estimates=data[rng.integers(0,32,size=(2000,32))].mean(axis=1)
        close(float(data.mean()),c['mean']);close(float(np.quantile(estimates,.025)),c['low']);close(float(np.quantile(estimates,.975)),c['high']);assert c['n']==32
    for cal,methods in summary['secondary_means'].items():
        for name,values in methods.items():
            rows=[r for key,r in blocks.items() if key[-2]==cal and key[-1]==name]
            for metric in METRICS:close(average(rows,metric),values[metric])
    for g,checks in summary['development_gates'].items():
        a=selection['all_methods'][selection['candidate']]['groups'][g]
        b=selection['all_methods'][selection['comparator']]['groups'][g]
        c={x['metric']:x for x in summary['comparisons'] if x['baseline']==selection['comparator'] and x['group']==g}
        assert checks==dict(oxygen_mean_10_percent=a['deficit_auc']<=.9*b['deficit_auc'],oxygen_paired_interval=c['deficit_auc']['high']<0,
            mean_low_reservoir=a['low_reservoir_s']<=1,zero_empty_requests=all(r['empty_request_s']==0 for r in primary if r['method']==selection['candidate'] and in_group(r,g)),
            extra_low_reservoir=c['low_reservoir_s']['high']<=1,extra_empty_requests=c['empty_request_s']['high']<=1,extra_high_pressure=c['high_pressure_s']['high']<=5)
    assert summary['development_joint_success']==(selection['candidate_eligible'] and selection['comparator_eligible'] and all(all(v.values()) for v in summary['development_gates'].values()))
    replay=json.loads((OUT/'replays.json').read_text())
    names=list(dict.fromkeys((selection['candidate'],selection['comparator'],'frozen_v1')))
    assert len(replay)==len(REPLAY_CELLS)*len(names)
    fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
    for cell in REPLAY_CELLS:
        for name in names:
            result=run(37000,*cell,catalog[name]);stored=replay['__'.join(cell)+'/'+name]
            rows=result['rows'][::3]+[result['rows'][-1]]
            for metric in METRICS:close(result['metrics'][metric],stored['metrics'][metric])
            for key,field in fields.items():
                for row,value in zip(rows,stored[key]):
                    if isinstance(value,bool):assert row[field]==value
                    else:close(row[field],value)
            actual=blocks[(37000,*cell,name)]
            for metric in METRICS:close(actual[metric],result['metrics'][metric])
    print(f'PASS: {counts["primary"]} primary + {counts["secondary"]} secondary development runs, 32 patients, independent selection/paired statistics, {len(replay)} rerun replays; confirmation untouched.')


if __name__=='__main__':main()
