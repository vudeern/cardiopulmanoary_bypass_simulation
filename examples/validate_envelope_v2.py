"""Validate both envelope implementation stages without erasing uncertified states."""
import csv
import hashlib
from io import StringIO
import json
import math
import zipfile
import numpy as np
import envelope_v2_study as initial
import envelope_carry_study as final


def trace(root,r):
    if 'trace_path' in r:return list(csv.DictReader((root/r['trace_path']).open()))
    with zipfile.ZipFile(root/r['trace_archive']) as z:content=z.read(r['trace_member'])
    assert hashlib.sha256(content).hexdigest()==r['trace_sha256']
    return list(csv.DictReader(StringIO(content.decode())))


def group(g,rows,new=False,followup=False):
    assert g['runs']==len(rows)
    assert abs(g['mean_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
    for key,field in (('floor_cases','low_reservoir_s'),('empty_cases','empty_request_s'),('high_pressure_cases','high_pressure_s')):assert g[key]==sum(r[field]>0 for r in rows)
    assert g['minimum_reservoir_L']==min(r['minimum_reservoir'] for r in rows)
    if new:
        for field in ('envelope_unavailable_s','envelope_uncertified_s','envelope_clipped_s','envelope_bound_failures_s','cap_violations','certified_margin_violations'):assert g[field]==sum(r[field] for r in rows)
        assert g['initially_uncertified_runs']==sum(not r['initial_stop_feasible'] for r in rows)
        if followup:
            assert g['post_first_uncertified_s']==sum(r['post_first_uncertified_s'] for r in rows)
            assert g['never_feasible_runs']==sum(r['never_feasible'] for r in rows)


def check(module,followup=False):
    root=module.ROOT;out=module.OUT;p=json.loads((out/'protocol.json').read_text());s=json.loads((out/'summary.json').read_text())
    records=json.loads((out/'runs.json').read_text());checks=json.loads((out/'checksums.json').read_text())
    assert p['version']=='2.0.0rc5' and p['version_line']==s['version_line']=='v2'
    assert p['new_simulations']==s['new_simulations']==72 and p['retained_reference_runs']==s['retained_reference_runs']==64
    assert not p['confirmation_seeds_executed'] and not s['confirmation_seeds_executed'] and not s['v2_milestone_passed']
    for path,sha in {**p['source_hashes'],**p['retained_hashes'],**p.get('initial_stage_hashes',{})}.items():assert module.digest(root/path)==sha,path
    # Retained rc4 records contain eight transitive rc3 CSV references.
    old_protocol=json.loads((module.previous.OUT/'protocol.json').read_text())
    for path,sha in old_protocol['retained_hashes'].items():assert module.digest(root/path)==sha,path
    assert set(checks)=={f.name for f in out.iterdir() if f.name!='checksums.json'}
    for path,sha in checks.items():assert module.digest(out/path)==sha,path
    expected={(origin,seed,plant,condition,name) for origin in ('retained_rc4_reference','new_envelope_simulation') for seed in module.SEEDS for plant in module.PLANTS for condition in module.CALS for name in module.NAMES}
    expected|={('new_envelope_simulation',seed,'nominal',condition,name) for seed in module.SEEDS for condition in module.EXTRAS for name in module.NAMES}
    assert len(records)==len(expected)==s['evaluations']==136
    assert {(r['origin'],r['seed'],r['plant'],r['condition'],r['method']) for r in records}==expected
    old=json.loads((module.previous.OUT/'runs.json').read_text());members={plant:set() for plant in module.PLANTS};post_first=0
    for r in records:
        rows=trace(root,r);assert [float(t['observation_time']) for t in rows]==list(range(600))
        assert abs(sum(max(0.,280.-float(t['do2'])) for t in rows)/60.-r['deficit_auc'])<1e-8
        for field,predicate in (('low_reservoir_s',lambda t:float(t['reservoir'])<.25),('empty_request_s',lambda t:t['empty_request']=='True'),('high_pressure_s',lambda t:float(t['pressure'])>95)):
            assert sum(predicate(t) for t in rows)==r[field]
        assert abs(min(float(t['reservoir']) for t in rows)-r['minimum_reservoir'])<1e-12
        if r['origin']=='retained_rc4_reference':
            original=next(a for a in old if (a['seed'],a['plant'],a['calibration'],a['method'])==(r['seed'],r['plant'],r['condition'],r['method']))
            assert all(r[k]==v for k,v in original.items() if k!='origin');continue
        members[r['plant']].add(r['trace_member']);budget=module.methods(r['condition'])[r['method']]['options']['envelope_budget']
        previous=2.4*module.patient(r['seed'],'evaluation').bsa;motor=previous;truth=.85;history={};bound_fail=0;seen=False;post=0
        tau=module.PLANTS[r['plant']].get('actuator_tau',2.)
        for t in rows:
            time=float(t['observation_time']);history[round(time,9)]=truth;u=float(t['command'])
            assert 0<=u<=7.+1e-7 and u<=float(t['decision_cap'])+1e-7
            assert abs(u-previous)<=.1500001
            assert motor<=float(t['envelope_flow_upper'])+1e-8
            lower=None if t['envelope_lower']=='' else float(t['envelope_lower'])
            if lower is not None and lower>truth+1e-8:bound_fail+=1
            if budget['inline_error_L'] is not None:assert abs(float(t['observed_reservoir'])-truth)<=budget['inline_error_L']+1e-8
            if t['calibration_value'] and budget['anchor_error_L'] is not None:
                actual=history[round(float(t['calibration_acquired']),9)]
                assert abs(float(t['calibration_value'])-actual)<=budget['anchor_error_L']+1e-8
            feasible=t['envelope_feasible']=='True'
            if feasible:
                assert float(t['envelope_margin'])>=-1e-7
                # Independent actual-plant stop check: use analysis-only true lag
                # and reconstructed motor state, never supplied to controller.
                n=math.ceil(u/.15);command_sum=n*u-.15*n*(n-1)/2.
                actual_stop=command_sum/60.+motor/(120.*math.tanh(1./(2.*tau)))
                assert truth-.29-actual_stop>=-1e-7
            else:assert abs(u-max(0.,previous-.15))<1e-8
            if seen and not feasible:post+=1
            seen=seen or feasible;previous=u
            motor=u+(motor-u)*math.exp(-1./tau);truth=float(t['reservoir'])
        post_first+=post
        assert bound_fail==r['envelope_bound_failures_s']==0
        assert sum(t['envelope_contract_available']=='False' for t in rows)==r['envelope_unavailable_s']
        assert sum(t['envelope_feasible']=='False' for t in rows)==r['envelope_uncertified_s']
        assert sum(t['envelope_clipped']=='True' for t in rows)==r['envelope_clipped_s']
        assert (rows[0]['envelope_feasible']=='True')==r['initial_stop_feasible']
        assert r['cap_violations']==r['certified_margin_violations']==0
        if followup:assert post==r['post_first_uncertified_s']==0 and (not seen)==r['never_feasible']
        if r['condition']=='no_contract':assert r['envelope_unavailable_s']==600 and not seen
    for plant,expected_members in members.items():
        with zipfile.ZipFile(out/f'traces-{plant}.zip') as z:assert z.testzip() is None and set(z.namelist())==expected_members
    for origin,g in s['primary_totals'].items():
        for name,value in g.items():group(value,[r for r in records if r['origin']==origin and r['method']==name and r['regime']=='primary'],origin=='new_envelope_simulation',followup)
    for condition,g in s['new_by_condition'].items():
        for name,value in g.items():group(value,[r for r in records if r['origin']=='new_envelope_simulation' and r['condition']==condition and r['method']==name],True,followup)
    g=s['primary_totals']['new_envelope_simulation'];assert abs(s['joint_reduction_fraction']-(1-g['joint_zero']['mean_deficit_auc']/g['aggregate_zero']['mean_deficit_auc']))<1e-12
    assert s['protocol_sha256']==module.digest(out/'protocol.json')
    replay_cases=(('outside','shared','joint_zero'),('nominal','no_contract','aggregate_zero')) if followup else (('nominal','inline_shared','joint_zero'),)
    for plant,condition,name in replay_cases:
        result=module.run(37014,plant,condition,name);saved=next(r for r in records if (r['origin'],r['seed'],r['plant'],r['condition'],r['method'])==('new_envelope_simulation',37014,plant,condition,name))
        assert abs(result['metrics']['deficit_auc']-saved['deficit_auc'])<1e-6
        assert result['metrics']['low_reservoir_s']==saved['low_reservoir_s']
    print(f'PASS: {out.name}; 72 new + 64 retained records, full trace/source/reference integrity, actual-stop checks, bounds/caps/slew, aggregates and replay; post-first-feasible uncertified steps={post_first}.')


if __name__=='__main__':check(initial);check(final,True)
