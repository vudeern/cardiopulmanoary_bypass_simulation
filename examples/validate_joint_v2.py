"""Validate joint-cap pilot integrity, independent metrics, parity and replay."""
import csv
import json
import numpy as np
from joint_v2_study import ROOT,OUT,SEEDS,CASES,methods,digest,run,previous,patient


def main():
    p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
    records=json.loads((OUT/'runs.json').read_text());hashes=json.loads((OUT/'checksums.json').read_text())
    assert p['version_line']==s['version_line']=='v2' and p['version']=='2.0.0rc2'
    assert not p['confirmation_seeds_executed'] and not s['confirmation_seeds_executed']
    assert not s['v2_milestone_passed']
    for path,sha in p['source_hashes'].items():assert digest(ROOT/path)==sha,path
    assert set(hashes)=={path.name for path in OUT.iterdir() if path.name!='checksums.json'}
    for path,sha in hashes.items():assert digest(OUT/path)==sha,path
    expected={(seed,plant,case,name) for seed in SEEDS for plant in ('nominal','slow') for case in CASES for name in methods()}
    assert len(records)==len(expected)==s['runs']==40
    assert {(r['seed'],r['plant'],r['case'],r['method']) for r in records}==expected
    for r in records:
        with (OUT/f"{r['seed']}-{r['plant']}-{r['case']}-{r['method']}.csv").open() as f:trace=list(csv.DictReader(f))
        assert [float(t['observation_time']) for t in trace]==list(range(600))
        deficit=sum(max(0.,280.-float(t['do2'])) for t in trace)/60.
        recovery=sum(max(0.,280.-float(t['do2'])) for t in trace if 213<=float(t['observation_time'])<348)/60.
        assert abs(deficit-r['deficit_auc'])<1e-8 and abs(recovery-r['recovery_deficit_auc'])<1e-8
        assert sum(float(t['reservoir'])<.25 for t in trace)==r['low_reservoir_s']
        assert sum(t['empty_request']=='True' for t in trace)==r['empty_request_s']
        assert abs(min(float(t['reservoir']) for t in trace)-r['minimum_reservoir'])<1e-12
        assert sum(float(t['pressure'])>95 for t in trace)==r['high_pressure_s']
        assert sum(t['joint_action_changed']=='True' for t in trace)==r['changed_action_s']
        assert sum(t['joint_supported']=='False' for t in trace)==r['unsupported_s']
        assert sum(float(t['joint_cap'])>float(t['aggregate_cap'])+1e-6 for t in trace)==r['widened_cap_s']
        command=2.4*patient(r['seed'],'evaluation').bsa
        for t in trace:
            u=float(t['command']);assert 0<=u<=7.+1e-7 and u<=float(t['decision_cap'])+1e-7
            assert abs(u-command)<=.1500001;command=u
            if t['joint_supported']=='True':
                assert float(t['joint_cap'])>=float(t['aggregate_cap'])-1e-4
                if t['predictive_feasible']=='True':assert float(t['hypothesis_margin'])>=-1e-7
        assert r['cap_violations']==r['feasible_margin_violations']==0
    for case in CASES:
        g=s['groups'][case]
        for name in methods():
            rows=[r for r in records if r['case']==case and r['method']==name];a=g[name]
            assert a['runs']==len(rows)==4
            assert abs(a['mean_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
            assert abs(a['mean_recovery_deficit_auc']-np.mean([r['recovery_deficit_auc'] for r in rows]))<1e-9
            for key,metric in (('floor_cases','low_reservoir_s'),('empty_cases','empty_request_s'),('high_pressure_cases','high_pressure_s')):
                assert a[key]==sum(r[metric]>0 for r in rows)
            assert a['worst_minimum_reservoir_L']==min(r['minimum_reservoir'] for r in rows)
        assert abs(g['reduction_fraction']-(1-g['joint_pi']['mean_deficit_auc']/g['aggregate_pi']['mean_deficit_auc']))<1e-12
    original_hashes=json.loads((ROOT/'results/v2-joint-pilot-attempt1/trace-sha256.json').read_text())
    assert len(original_hashes)==40
    for name,sha in original_hashes.items():assert digest(OUT/name)==sha,'Serialization rerun changed a numerical trace: '+name
    assert s['protocol_sha256']==digest(OUT/'protocol.json')
    # Verify instrumentation did not move the baseline; then replay both arms
    # on a noisy repeated-stop case without relying on saved aggregate metrics.
    baseline=run(37000,'slow','single',methods()['aggregate_pi'])
    original=previous.run(37000,'slow','interruption',previous.methods()['pi_fast'])
    assert baseline['metrics']==original['metrics']
    assert [r['command'] for r in baseline['rows']]==[r['command'] for r in original['rows']]
    for name in methods():
        replay=run(37014,'slow','repeated_noise',methods()[name])
        saved=next(r for r in records if (r['seed'],r['plant'],r['case'],r['method'])==(37014,'slow','repeated_noise',name))
        assert abs(replay['metrics']['deficit_auc']-saved['deficit_auc'])<1e-6
    print('PASS: 40 joint-cap runs, trace/source hashes, recomputed metrics, cap/slew/margins, unchanged original PI baseline and noisy repeated-stop pair replay. No stable-v2 qualification.')


if __name__=='__main__':main()
