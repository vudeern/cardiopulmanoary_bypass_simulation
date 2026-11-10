"""Validate the first v2 recovery traces, scope and replay."""
import csv
import json
import numpy as np
from continuity_study import patient
from recovery_v2_study import ROOT,OUT,SEEDS,methods,digest,run


def main():
    protocol=json.loads((OUT/'protocol.json').read_text());summary=json.loads((OUT/'summary.json').read_text())
    records=json.loads((OUT/'runs.json').read_text());hashes=json.loads((OUT/'checksums.json').read_text())
    assert protocol['version_line']==summary['version_line']=='v2'
    assert not protocol['confirmation_seeds_executed'] and not summary['confirmation_seeds_executed']
    assert not summary['v2_milestone_passed']
    for p,sha in protocol['source_hashes'].items():assert digest(ROOT/p)==sha,p
    assert set(hashes)=={p.name for p in OUT.iterdir() if p.name!='checksums.json'}
    for p,sha in hashes.items():assert digest(OUT/p)==sha,p
    expected={(s,m,c,n) for s in SEEDS for m in ('nominal','slow') for c in ('normal','interruption') for n in methods()}
    assert len(records)==len(expected)==24
    assert {(r['seed'],r['plant'],r['case'],r['method']) for r in records}==expected
    for r in records:
        with (OUT/f"{r['seed']}-{r['plant']}-{r['case']}-{r['method']}.csv").open() as f:trace=list(csv.DictReader(f))
        assert [float(t['observation_time']) for t in trace]==list(range(600))
        total=sum(max(0.,280.-float(t['do2'])) for t in trace)/60.
        recovery=sum(max(0.,280.-float(t['do2'])) for t in trace if 213<=float(t['observation_time'])<273)/60.
        assert abs(total-r['deficit_auc'])<1e-8 and abs(recovery-r['recovery_deficit_auc'])<1e-8
        assert sum(float(t['reservoir'])<.25 for t in trace)==r['low_reservoir_s']
        assert sum(t['recovery_action_changed']=='True' for t in trace)==r['changed_action_s']
        previous=2.4*patient(r['seed'],'evaluation').bsa
        for t in trace:
            u=float(t['command']);assert 0<=u<=float(t['decision_cap'])+1e-7
            assert abs(u-previous)<=.1500001;previous=u
        assert r['cap_violations']==0
    for name,groups in summary['groups'].items():
        for case,g in groups.items():
            rows=[r for r in records if r['method']==name and r['case']==case]
            assert g['runs']==len(rows)==4
            assert abs(g['mean_recovery_deficit_auc']-np.mean([r['recovery_deficit_auc'] for r in rows]))<1e-9
            assert abs(g['mean_total_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
            assert g['floor_cases']==sum(r['low_reservoir_s']>0 for r in rows)
            assert g['empty_cases']==sum(r['empty_request_s']>0 for r in rows)
            assert g['false_alarms']==sum(r['false_alarms'] for r in rows)
    assert summary['protocol_sha256']==digest(OUT/'protocol.json')
    for name in ('pi_fast','recovery'):
        replay=run(37000,'slow','interruption',methods()[name])
        saved=next(r for r in records if (r['seed'],r['plant'],r['case'],r['method'])==(37000,'slow','interruption',name))
        assert abs(replay['metrics']['deficit_auc']-saved['deficit_auc'])<1e-6
    print('PASS: 24 v2 recovery runs; complete traces, independent cap/slew checks, aggregates and matched replay. Recovery-specific results do not qualify a stable v2 release.')


if __name__=='__main__':main()
