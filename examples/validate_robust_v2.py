"""Validate boundary matrix, lossless archived traces and fault replay."""
import csv
import hashlib
from io import StringIO
import json
import zipfile
import numpy as np
from robust_v2_study import ROOT,OUT,SEEDS,PLANTS,CALS,NAMES,methods,digest,run,previous,patient


def read_trace(r):
    if r['origin']=='retained_rc3_reference':return list(csv.DictReader((ROOT/r['trace_path']).open()))
    with zipfile.ZipFile(ROOT/r['trace_archive']) as z:content=z.read(r['trace_member'])
    assert hashlib.sha256(content).hexdigest()==r['trace_sha256']
    return list(csv.DictReader(StringIO(content.decode())))


def validate_group(g,rows):
    assert g['runs']==len(rows)
    assert abs(g['mean_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
    for key,metric in (('floor_cases','low_reservoir_s'),('empty_cases','empty_request_s'),('high_pressure_cases','high_pressure_s')):assert g[key]==sum(r[metric]>0 for r in rows)
    assert g['minimum_reservoir_L']==min(r['minimum_reservoir'] for r in rows)
    assert g['unsupported_s']==sum(r['unsupported_s'] for r in rows)
    assert g['cap_violations']==g['feasible_margin_violations']==0


def main():
    p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
    records=json.loads((OUT/'runs.json').read_text());hashes=json.loads((OUT/'checksums.json').read_text())
    assert p['version']=='2.0.0rc4' and p['version_line']==s['version_line']=='v2'
    assert p['new_simulations']==s['new_simulations']==56 and p['retained_reference_runs']==s['retained_reference_runs']==8
    assert not p['confirmation_seeds_executed'] and not s['confirmation_seeds_executed'] and not s['v2_milestone_passed']
    for path,sha in {**p['source_hashes'],**p['retained_hashes']}.items():assert digest(ROOT/path)==sha,path
    assert set(hashes)=={f.name for f in OUT.iterdir() if f.name!='checksums.json'}
    for path,sha in hashes.items():assert digest(OUT/path)==sha,path
    assert all(methods()[n]['options']['return_horizon_s']==0. for n in NAMES)
    expected={(seed,plant,cal,name) for seed in SEEDS for plant in PLANTS for cal in CALS for name in NAMES}
    assert len(records)==s['evaluations']==len(expected)==64
    assert {(r['seed'],r['plant'],r['calibration'],r['method']) for r in records}==expected
    assert sum(r['origin']=='new_boundary_simulation' for r in records)==56
    old=json.loads((previous.OUT/'runs.json').read_text());archive_members={plant:set() for plant in PLANTS}
    diagnostics={}
    for r in records:
        if r['origin']=='retained_rc3_reference':
            saved=next(a for a in old if (a['seed'],a['plant'],a['case'],a['method'])==(r['seed'],r['plant'],'repeated',r['method']))
            assert r['calibration']=='healthy' and r['trace_path'] in p['retained_hashes']
            assert all(r[k]==v for k,v in saved.items() if k!='origin')
        else:archive_members[r['plant']].add(r['trace_member'])
        trace=read_trace(r);assert [float(t['observation_time']) for t in trace]==list(range(600))
        assert abs(sum(max(0.,280.-float(t['do2'])) for t in trace)/60.-r['deficit_auc'])<1e-8
        for key,truth in (('low_reservoir_s',lambda t:float(t['reservoir'])<.25),('empty_request_s',lambda t:t['empty_request']=='True'),('high_pressure_s',lambda t:float(t['pressure'])>95)):
            assert sum(truth(t) for t in trace)==r[key]
        assert abs(min(float(t['reservoir']) for t in trace)-r['minimum_reservoir'])<1e-12
        assert sum(t['joint_supported']=='False' for t in trace)==r['unsupported_s']
        previous_u=2.4*patient(r['seed'],'evaluation').bsa;true_start=.85;covered=0;supported=0
        for t in trace:
            u=float(t['command']);assert 0<=u<=7.+1e-7 and u<=float(t['decision_cap'])+1e-7
            assert abs(u-previous_u)<=.1500001;previous_u=u
            if t['joint_supported']=='True' and t['predictive_feasible']=='True':assert float(t['hypothesis_margin'])>=-1e-7
            if 'bank_supported' in t and t['bank_supported']=='True':
                supported+=1;covered+=float(t['bank_lower'])-1e-8<=true_start<=float(t['bank_upper'])+1e-8
            true_start=float(t['reservoir'])
        assert r['cap_violations']==r['feasible_margin_violations']==0
        if r['origin']=='new_boundary_simulation':
            diagnostics[f"{r['seed']}-{r['plant']}-{r['calibration']}-{r['method']}"]=dict(supported_s=supported,truth_outside_bank_s=supported-covered)
    for plant in PLANTS:
        with zipfile.ZipFile(OUT/f'traces-{plant}.zip') as z:
            assert z.testzip() is None and set(z.namelist())==archive_members[plant]
    for plant in PLANTS:
        for cal in CALS:
            g=s['cells'][plant+'__'+cal]
            for n in NAMES:validate_group(g[n],[r for r in records if r['plant']==plant and r['calibration']==cal and r['method']==n])
            assert abs(g['joint_reduction_fraction']-(1-g['joint_zero']['mean_deficit_auc']/g['aggregate_zero']['mean_deficit_auc']))<1e-12
    for cal in CALS:
        for n in NAMES:validate_group(s['by_calibration'][cal][n],[r for r in records if r['calibration']==cal and r['method']==n])
    for n in NAMES:validate_group(s['totals'][n],[r for r in records if r['method']==n])
    assert s['protocol_sha256']==digest(OUT/'protocol.json')
    for plant,cal,name in (('outside','shared','joint_zero'),('lagged','biased','aggregate_zero')):
        replay=run(37014,plant,cal,name);saved=next(r for r in records if (r['seed'],r['plant'],r['calibration'],r['method'])==(37014,plant,cal,name))
        assert abs(replay['metrics']['deficit_auc']-saved['deficit_auc'])<1e-6
        assert replay['metrics']['low_reservoir_s']==saved['low_reservoir_s']
    print('PASS: 56 new + 8 retained boundary runs; ZIP members, source/reference/trace hashes, metrics, caps/slew/margins, aggregates and fault pair replay. Failure outcomes remain allowed research results, not release qualification.')
    print('Post-result diagnostic: supported steps with true start-volume outside bank bounds (new traces only):',sum(v['truth_outside_bank_s'] for v in diagnostics.values()))


if __name__=='__main__':main()
