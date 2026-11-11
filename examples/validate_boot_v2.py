"""Validate admitted cold starts and retain explicit rejected-start denominators."""
import csv
import hashlib
from io import StringIO
import json
import math
import zipfile
import numpy as np
from boot_v2_study import ROOT,OUT,SEEDS,PLANTS,CALS,NAMES,EXTRAS,methods,digest,run,patient
from perfusion_research.boot_v2 import StartupRejected


def group(g,attempts):
    rows=[r for r in attempts if r['outcome']=='completed']
    assert g['attempts']==len(attempts) and g['completed']==len(rows) and g['rejected']==len(attempts)-len(rows)
    if not rows:
        assert all(g[k] is None for k in ('mean_deficit_auc','floor_cases','empty_cases','minimum_reservoir_L'));return
    assert abs(g['mean_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
    for key,field in (('floor_cases','low_reservoir_s'),('empty_cases','empty_request_s'),('high_pressure_cases','high_pressure_s')):assert g[key]==sum(r[field]>0 for r in rows)
    assert g['minimum_reservoir_L']==min(r['minimum_reservoir'] for r in rows)
    assert g['initially_uncertified_runs']==sum(not r['initial_stop_feasible'] for r in rows)==0
    for field in ('envelope_uncertified_s','envelope_bound_failures_s'):assert g[field]==sum(r[field] for r in rows)==0


def main():
    p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
    attempts=json.loads((OUT/'attempts.json').read_text());hashes=json.loads((OUT/'checksums.json').read_text())
    assert p['version']=='2.0.0rc6' and p['version_line']==s['version_line']=='v2'
    assert not p['confirmation_seeds_executed'] and not s['confirmation_seeds_executed'] and not s['v2_milestone_passed']
    for path,sha in {**p['source_hashes'],**p['warm_reference_hashes']}.items():assert digest(ROOT/path)==sha,path
    assert set(hashes)=={f.name for f in OUT.iterdir() if f.name!='checksums.json'}
    for path,sha in hashes.items():assert digest(OUT/path)==sha,path
    expected={(seed,plant,condition,name) for seed in SEEDS for plant in PLANTS for condition in CALS for name in NAMES}
    expected|={(seed,'nominal',condition,name) for seed in SEEDS for condition in EXTRAS for name in NAMES}
    assert len(attempts)==len(expected)==s['attempts']==80
    assert {(r['seed'],r['plant'],r['condition'],r['method']) for r in attempts}==expected
    assert sum(r['outcome']=='completed' for r in attempts)==s['completed']==68
    assert sum(r['outcome']=='rejected_startup' for r in attempts)==s['rejected']==12
    members={plant:set() for plant in PLANTS}
    for r in attempts:
        if r['condition'] in ('no_contract','hot_start','unprimed'):
            assert r['outcome']=='rejected_startup' and r['issued_commands']==0
            assert 'deficit_auc' not in r and 'low_reservoir_s' not in r and 'trace_member' not in r
            assert r['details']['observation_time']==0.
            if r['condition']=='no_contract':assert r['reason']=='no_bounded_level_source' and r['details']['held_zero_margin'] is None
            else:assert r['reason']=='held_zero_stop_infeasible' and r['details']['held_zero_margin']<0
            continue
        assert r['outcome']=='completed';members[r['plant']].add(r['trace_member'])
        with zipfile.ZipFile(ROOT/r['trace_archive']) as z:content=z.read(r['trace_member'])
        assert hashlib.sha256(content).hexdigest()==r['trace_sha256']
        rows=list(csv.DictReader(StringIO(content.decode())))
        assert [float(t['observation_time']) for t in rows]==list(range(600))
        assert abs(sum(max(0.,280.-float(t['do2'])) for t in rows)/60.-r['deficit_auc'])<1e-8
        for field,predicate in (('low_reservoir_s',lambda t:float(t['reservoir'])<.25),('empty_request_s',lambda t:t['empty_request']=='True'),('high_pressure_s',lambda t:float(t['pressure'])>95)):
            assert sum(predicate(t) for t in rows)==r[field]==0
        assert abs(min(float(t['reservoir']) for t in rows)-r['minimum_reservoir'])<1e-12
        assert r['initial_stop_feasible'] and r['startup_margin']>=0 and r['envelope_uncertified_s']==r['envelope_bound_failures_s']==r['cap_violations']==0
        truth=.85;motor=0.;previous=0.;history={};tau=PLANTS[r['plant']].get('actuator_tau',2.)
        budget=methods(r['condition'])[r['method']]['options']['envelope_budget']
        for t in rows:
            time=float(t['observation_time']);history[round(time,9)]=truth;u=float(t['command'])
            assert t['startup_authorized']==t['envelope_feasible']=='True' and float(t['startup_margin'])>=0
            assert float(t['envelope_lower'])<=truth+1e-8 and motor<=float(t['envelope_flow_upper'])+1e-8
            assert abs(float(t['observed_reservoir'])-truth)<=budget['inline_error_L']+1e-8
            if time==0:
                assert abs(float(t['observed_flow'])-motor)<=.1+1e-8
                assert abs(float(t['envelope_flow_upper'])-(float(t['observed_flow'])+.1))<1e-8
            if t['calibration_value']:
                assert abs(float(t['calibration_value'])-history[round(float(t['calibration_acquired']),9)])<=budget['anchor_error_L']+1e-8
            assert 0<=u<=7.+1e-7 and u<=float(t['decision_cap'])+1e-7 and abs(u-previous)<=.1500001
            assert float(t['envelope_margin'])>=-1e-7
            n=math.ceil(u/.15);stop=(n*u-.15*n*(n-1)/2.)/60.+motor/(120.*math.tanh(1./(2.*tau)))
            assert truth-.29-stop>=-1e-7
            motor=u+(motor-u)*math.exp(-1./tau);truth=float(t['reservoir']);previous=u
        first=next((float(t['observation_time']) for t in rows if float(t['command'])>1e-8),None)
        assert first==r['first_positive_command_time']
        if r['condition']=='missing':assert first is None and r['deficit_auc']==2800.
    for plant in PLANTS:
        with zipfile.ZipFile(OUT/f'traces-{plant}.zip') as z:assert z.testzip() is None and set(z.namelist())==members[plant]
    for name,g in s['primary'].items():group(g,[r for r in attempts if r['method']==name and r['regime']=='primary'])
    for condition,by_name in s['by_condition'].items():
        for name,g in by_name.items():group(g,[r for r in attempts if r['method']==name and r['condition']==condition])
    assert abs(s['joint_reduction_fraction']-(1-s['primary']['joint_zero']['mean_deficit_auc']/s['primary']['aggregate_zero']['mean_deficit_auc']))<1e-12
    assert s['protocol_sha256']==digest(OUT/'protocol.json')
    for plant,condition,name in (('outside','shared','joint_zero'),('nominal','missing','aggregate_zero')):
        replay=run(37014,plant,condition,name);saved=next(r for r in attempts if (r['seed'],r['plant'],r['condition'],r['method'])==(37014,plant,condition,name))
        assert abs(replay['metrics']['deficit_auc']-saved['deficit_auc'])<1e-6
    for condition in ('no_contract','hot_start','unprimed'):
        try:run(37014,'nominal',condition,'joint_zero')
        except StartupRejected as error:
            saved=next(r for r in attempts if (r['seed'],r['plant'],r['condition'],r['method'])==(37014,'nominal',condition,'joint_zero'))
            assert error.reason==saved['reason']
        else:raise AssertionError('Rejected case was silently admitted')
    print('PASS: 80 attempts, 68 certified-from-start completions and 12 explicit rejections; source/ZIP/member integrity, physical metrics, actual stopping checks, startup slew, all aggregates and admitted/rejected replay. Rejections have no fabricated safe-run metrics; no stable-v2 qualification.')


if __name__=='__main__':main()
