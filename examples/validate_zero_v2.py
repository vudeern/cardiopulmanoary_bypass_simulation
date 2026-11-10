"""Independently validate zero-return factorial results and retained provenance."""
import csv
import json
import numpy as np
from zero_v2_study import ROOT,OUT,SEEDS,CASES,NAMES,methods,digest,run,previous,patient


def main():
    p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
    records=json.loads((OUT/'runs.json').read_text());hashes=json.loads((OUT/'checksums.json').read_text())
    assert p['version_line']==s['version_line']=='v2' and p['version']=='2.0.0rc3'
    assert p['new_simulations']==s['new_simulations']==40 and p['retained_reference_runs']==s['retained_reference_runs']==40
    assert not p['confirmation_seeds_executed'] and not s['confirmation_seeds_executed'] and not s['v2_milestone_passed']
    assert all(methods()[n]['options']['return_horizon_s']==(0. if n.endswith('zero') else 15.) for n in NAMES)
    for path,sha in {**p['source_hashes'],**p['retained_hashes']}.items():assert digest(ROOT/path)==sha,path
    assert set(hashes)=={f.name for f in OUT.iterdir() if f.name!='checksums.json'}
    for path,sha in hashes.items():assert digest(OUT/path)==sha,path
    expected={(seed,plant,case,n) for seed in SEEDS for plant in ('nominal','slow') for case in CASES for n in NAMES}
    assert len(records)==len(expected)==s['evaluations']==80
    assert {(r['seed'],r['plant'],r['case'],r['method']) for r in records}==expected
    old=json.loads((previous.OUT/'runs.json').read_text())
    for r in records:
        if r['method'].endswith('credit'):
            original='joint_pi' if r['method'].startswith('joint') else 'aggregate_pi'
            saved=next(a for a in old if (a['seed'],a['plant'],a['case'],a['method'])==(r['seed'],r['plant'],r['case'],original))
            assert r['origin']=='retained_v2_joint_pilot'
            assert {k:r[k] for k in saved if k!='method'}=={k:v for k,v in saved.items() if k!='method'}
            assert r['trace_path'] in p['retained_hashes']
        else:assert r['origin']=='new_zero_return_simulation' and r['trace_path'].startswith('results/v2-zero-pilot/')
        with (ROOT/r['trace_path']).open() as f:trace=list(csv.DictReader(f))
        assert [float(t['observation_time']) for t in trace]==list(range(600))
        for field,start,end in (('deficit_auc',0,600),('recovery_deficit_auc',213,348)):
            value=sum(max(0.,280.-float(t['do2'])) for t in trace if start<=float(t['observation_time'])<end)/60.
            assert abs(value-r[field])<1e-8
        for key,truth in (('low_reservoir_s',lambda t:float(t['reservoir'])<.25),('empty_request_s',lambda t:t['empty_request']=='True'),('high_pressure_s',lambda t:float(t['pressure'])>95)):
            assert sum(truth(t) for t in trace)==r[key]
        assert abs(min(float(t['reservoir']) for t in trace)-r['minimum_reservoir'])<1e-12
        command=2.4*patient(r['seed'],'evaluation').bsa
        for t in trace:
            u=float(t['command']);assert 0<=u<=7.+1e-7 and u<=float(t['decision_cap'])+1e-7
            assert abs(u-command)<=.1500001;command=u
            if t['joint_supported']=='True':
                assert float(t['joint_cap'])>=float(t['aggregate_cap'])-1e-4
                if t['predictive_feasible']=='True':assert float(t['hypothesis_margin'])>=-1e-7
        assert r['cap_violations']==r['feasible_margin_violations']==0
    for case in CASES:
        for n in NAMES:
            rows=[r for r in records if r['case']==case and r['method']==n];g=s['groups'][case][n]
            assert g['runs']==len(rows)==4
            assert abs(g['mean_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
            assert abs(g['mean_recovery_deficit_auc']-np.mean([r['recovery_deficit_auc'] for r in rows]))<1e-9
            for key,metric in (('floor_cases','low_reservoir_s'),('empty_cases','empty_request_s'),('high_pressure_cases','high_pressure_s')):assert g[key]==sum(r[metric]>0 for r in rows)
            assert g['minimum_reservoir_L']==min(r['minimum_reservoir'] for r in rows)
        g=s['groups'][case];assert abs(g['zero_joint_reduction_fraction']-(1-g['joint_zero']['mean_deficit_auc']/g['aggregate_zero']['mean_deficit_auc']))<1e-12
    for n in NAMES:
        rows=[r for r in records if r['method']==n];g=s['totals'][n]
        assert g['runs']==len(rows)==20
        assert abs(g['mean_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
        for key,metric in (('floor_cases','low_reservoir_s'),('empty_cases','empty_request_s'),('high_pressure_cases','high_pressure_s')):assert g[key]==sum(r[metric]>0 for r in rows)
        assert g['minimum_reservoir_L']==min(r['minimum_reservoir'] for r in rows)
    assert abs(s['zero_joint_reduction_fraction']-(1-s['totals']['joint_zero']['mean_deficit_auc']/s['totals']['aggregate_zero']['mean_deficit_auc']))<1e-12
    assert s['protocol_sha256']==digest(OUT/'protocol.json')
    for n in ('aggregate_zero','joint_zero'):
        result=run(37014,'slow','repeated_noise',methods()[n])
        saved=next(r for r in records if (r['seed'],r['plant'],r['case'],r['method'])==(37014,'slow','repeated_noise',n))
        assert abs(result['metrics']['deficit_auc']-saved['deficit_auc'])<1e-6
    print('PASS: 40 new zero-return runs + 40 exact retained references; full matrix, provenance, trace metrics, cap/slew/margins, group totals and noisy repeated-stop pair replay. No stable-v2 qualification.')


if __name__=='__main__':main()
