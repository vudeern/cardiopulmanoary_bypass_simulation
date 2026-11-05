"""Adaptive development follow-up: change the hybrid's PI base, hold protection.

Stage one found no oxygen advantage over independently tuned eligible PI. This
four-setting follow-up is frozen before running, on the same development seeds.
It is exploratory reuse, never confirmation. Stage-one results remain intact.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import csv
import json
from multiprocessing import get_context
from pathlib import Path
import numpy as np
import reachability_study as first
from perfusion_lab.benchmark import paired_interval
from simc_benchmark import digest,dumps

ROOT=first.ROOT;OUT=ROOT/'results/reachability-base-development'
METRICS=first.METRICS;SEEDS=first.SEEDS


def methods():
    selection=json.loads((first.OUT/'selection.json').read_text())
    catalog=json.loads((first.OUT/'protocol.json').read_text())['methods']
    base=catalog[selection['comparator']]['options']
    assert selection['comparator_eligible']
    # The winner's gain and setpoint, plus the already-declared lowest PI
    # setpoint, test whether the high legacy PI level was limiting recovery.
    result={}
    for observer in ('legacy','consistent'):
        for label,level in (('matched',base['target_level']),('aggressive',.35)):
            method=deepcopy(catalog['reserve_only' if observer=='legacy' else 'combined'])
            method['options'].update(tau_c=base['tau_c'],target_level=level)
            result[f'{label}_{observer}']=method
    return result


def protocol():
    selection=json.loads((first.OUT/'selection.json').read_text())
    value=dict(version='2.0.0rc2',stage='adaptive_development_followup',
        development_seeds=list(SEEDS),confirmation_seeds_executed=[],duration_s=600.,dt_s=1.,
        methods=methods(),comparator=selection['comparator'],stage_one_candidate=selection['candidate'],
        primary_runs=2048,secondary_runs=1536,
        rationale='After inspecting stage-one primary development results, keep the same joint reserve, observer allowances, recovery floor, limits and sensor channels; test PI base gain/setpoint from the independently selected eligible PI and the already-declared aggressive .35L PI setpoint. Two observers x two base levels. Reuse all 32 development patients; results are selection-biased and not confirmation.',
        selection='Candidate among these four settings and the stage-one selected candidate: separately clean/bias/outage mean low-reservoir <=1s and zero primary empty requests, then lowest overall deficit; otherwise lexicographic low/empty/deficit marked ineligible. Comparator remains stage-one independently selected PI. All four candidates get secondary missing/biased/shared-calibration tests, with no secondary selection.',
        stage_one_protocol_sha256=digest(first.OUT/'protocol.json'),
        stage_one_selection_sha256=digest(first.OUT/'selection.json'),
        source_hashes={**{n:digest(ROOT/n) for n in first.SOURCES},'examples/reachability_base_study.py':digest(Path(__file__))})
    path=OUT/'protocol.json'
    if path.exists():assert json.loads(path.read_text())==json.loads(dumps(value)),'Follow-up protocol changed'
    else:OUT.mkdir(parents=True,exist_ok=True);path.write_text(dumps(value))
    return value


def grid(stage):
    p=protocol();directory=OUT/stage;directory.mkdir(exist_ok=True)
    pending=[seed for seed in SEEDS if not (directory/f'{seed}.csv').exists()]
    with ProcessPoolExecutor(max_workers=4,mp_context=get_context('spawn')) as pool:
        tasks={pool.submit(first.worker,(stage,seed,p['methods'])):seed for seed in pending}
        for future in as_completed(tasks):
            seed=tasks[future];rows=future.result();first.write_csv(directory/f'{seed}.csv',rows)
            print('base',stage,'patient complete',seed,'runs',len(rows),flush=True)


def records(stage):
    rows=[]
    for directory in (first.OUT,OUT):
        for seed in SEEDS:
            with (directory/stage/f'{seed}.csv').open() as f:
                for row in csv.DictReader(f):
                    row['seed']=int(row['seed'])
                    for m in METRICS:row[m]=float(row[m])
                    rows.append(row)
    return rows


def summarize():
    p=protocol();rows=records('primary')
    names=list(p['methods'])+[p['stage_one_candidate']]
    compare=list(dict.fromkeys(names+[p['comparator'],'frozen_v1']))
    stats={}
    for name in compare:
        block=[r for r in rows if r['method']==name]
        groups={g:first.means([r for r in block if first.group(r,g)]) for g in ('clean','bias','outage')}
        stats[name]=dict(means=first.means(block),groups=groups,
            eligible=all(v['low_reservoir_s']<=1 for v in groups.values()) and all(r['empty_request_s']==0 for r in block))
    eligible=[n for n in names if stats[n]['eligible']]
    def rank(n):
        m=stats[n]['means']
        return (m['deficit_auc'],names.index(n)) if eligible else (m['low_reservoir_s'],m['empty_request_s'],m['deficit_auc'],names.index(n))
    selected=min(eligible or names,key=rank);comparisons=[]
    for baseline in compare:
        if baseline==selected:continue
        for g in ('clean','bias','outage'):
            for metric in METRICS:
                diffs=[]
                for seed in SEEDS:
                    block=[r for r in rows if r['seed']==seed and first.group(r,g)]
                    diffs.append(first.means([r for r in block if r['method']==selected])[metric]-first.means([r for r in block if r['method']==baseline])[metric])
                comparisons.append(dict(baseline=baseline,group=g,metric=metric,**paired_interval(diffs)))
    gates={}
    for g in ('clean','bias','outage'):
        a=stats[selected]['groups'][g];b=stats[p['comparator']]['groups'][g]
        c={v['metric']:v for v in comparisons if v['baseline']==p['comparator'] and v['group']==g}
        gates[g]=dict(oxygen_mean_10_percent=a['deficit_auc']<=.9*b['deficit_auc'],oxygen_paired_interval=c['deficit_auc']['high']<0,
            mean_low_reservoir=a['low_reservoir_s']<=1,zero_empty_requests=all(r['empty_request_s']==0 for r in rows if r['method']==selected and first.group(r,g)),
            extra_low_reservoir=c['low_reservoir_s']['high']<=1,extra_empty_requests=c['empty_request_s']['high']<=1,extra_high_pressure=c['high_pressure_s']['high']<=5)
    secondary=records('secondary') if (OUT/'secondary/37031.csv').exists() else []
    secondary_means={cal:{n:first.means([r for r in secondary if r['calibration']==cal and r['method']==n]) for n in compare if any(r['method']==n for r in secondary)} for cal in ('missing','biased','shared')} if secondary else {}
    selection=dict(candidate=selected,comparator=p['comparator'],candidate_eligible=stats[selected]['eligible'],comparator_eligible=stats[p['comparator']]['eligible'],all_methods=stats)
    (OUT/'selection.json').write_text(dumps(selection))
    summary=dict(version='2.0.0rc2',stage='adaptive_development_only',patients=32,
        primary_runs_this_stage=2048,secondary_runs_this_stage=1536 if secondary else 0,
        total_primary_runs=len(rows),total_secondary_runs=len(secondary),candidate=selected,comparator=p['comparator'],
        candidate_eligible=selection['candidate_eligible'],comparator_eligible=selection['comparator_eligible'],
        method_means=stats,secondary_means=secondary_means,comparisons=comparisons,development_gates=gates,
        development_joint_success=selection['candidate_eligible'] and selection['comparator_eligible'] and all(all(v.values()) for v in gates.values()),
        version2_ready=False,qualifying_confirmation_cohorts=0,confirmation_seeds_executed=[],clinical_validation=False,novelty_established=False,
        protocol_sha256=digest(OUT/'protocol.json'),selection_sha256=digest(OUT/'selection.json'))
    (OUT/'summary.json').write_text(dumps(summary))
    print(dumps({k:summary[k] for k in ('candidate','comparator','candidate_eligible','development_gates','development_joint_success')}),flush=True)


def replays():
    selection=json.loads((OUT/'selection.json').read_text());catalog={**first.methods(),**methods()};runs={}
    names=list(dict.fromkeys((selection['candidate'],selection['comparator'],'frozen_v1')))
    for cell in first.REPLAY_CELLS:
        for name in names:
            result=first.run(37000,*cell,catalog[name]);sample=result['rows'][::3]+[result['rows'][-1]]
            fields=dict(t='time',do2='do2',monitor='measured_do2',reservoir='reservoir',pressure='pressure',infeasible='infeasible',fault='fault',level_fault='level_fault',level_sensor='observed_reservoir',level_lower='level_reference_lower')
            runs['__'.join(cell)+'/'+name]={k:[r[v] for r in sample] for k,v in fields.items()}
            runs['__'.join(cell)+'/'+name]['metrics']=result['metrics']
    (OUT/'replays.json').write_text(dumps(runs))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=('primary','secondary','summarize','replays'),required=True);args=parser.parse_args()
    if args.stage in ('primary','secondary'):grid(args.stage);summarize()
    elif args.stage=='replays':replays()
    else:summarize()
