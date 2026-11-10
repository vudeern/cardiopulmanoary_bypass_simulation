"""Check applied feedback traces, paired results and a small reproduction pair."""
import csv
import json
import math
import numpy as np
from continuity_study import patient
from feedback_study import ROOT,OUT,SEEDS,methods,digest,run


def main():
    protocol=json.loads((OUT/'protocol.json').read_text());summary=json.loads((OUT/'summary.json').read_text())
    records=json.loads((OUT/'runs.json').read_text());hashes=json.loads((OUT/'checksums.json').read_text())
    assert protocol['seeds']==list(SEEDS) and not protocol['confirmation_seeds_executed']
    assert not summary['version2_ready'] and not summary['confirmation_seeds_executed']
    for p,sha in protocol['source_hashes'].items():assert digest(ROOT/p)==sha,p
    assert set(hashes)=={p.name for p in OUT.iterdir() if p.name!='checksums.json'}
    for p,sha in hashes.items():assert digest(OUT/p)==sha,p
    expected={(s,p,m,n) for s in SEEDS for p in ('clean','combined') for m in ('nominal','slow') for n in methods()}
    assert len(records)==len(expected)==48
    assert {(r['seed'],r['physiology'],r['plant'],r['method']) for r in records}==expected
    for r in records:
        with (OUT/f"{r['seed']}-{r['physiology']}-{r['plant']}-{r['method']}.csv").open() as f:trace=list(csv.DictReader(f))
        assert [float(t['observation_time']) for t in trace]==list(range(600))
        deficit=sum(max(0.,280.-float(t['do2'])) for t in trace)/60.
        assert abs(deficit-r['deficit_auc'])<1e-8
        assert sum(float(t['reservoir'])<.25 for t in trace)==r['low_reservoir_s']
        assert min(float(t['reservoir']) for t in trace)==r['minimum_reservoir']
        assert sum(float(t['pressure'])>95. for t in trace)==r['high_pressure_s']
        previous=2.4*patient(r['seed'],'evaluation').bsa
        for t in trace:
            u=float(t['command']);assert 0<=u<=7.;assert abs(u-previous)<=.1500001;previous=u
            if r['method']!='rc5':assert u<=float(t['decision_cap'])+1e-7
        assert r['cap_violations']==0
        assert r['mpc_accepted_s']==sum(t['mpc_accepted']=='True' for t in trace)
        assert r['action_changed_s']==sum(t['action_changed']=='True' for t in trace)
        assert sum(r['statuses'].values())==600
        for metric in ('deficit_auc','low_reservoir_s','empty_request_s','minimum_reservoir'):
            assert math.isfinite(r[metric]) and r[metric]>=0
    assert summary['runs']==48
    for name,g in summary['groups'].items():
        rows=[r for r in records if r['method']==name]
        assert g['runs']==len(rows)==16
        assert abs(g['mean_deficit_auc']-np.mean([r['deficit_auc'] for r in rows]))<1e-9
        assert g['floor_cases']==sum(r['low_reservoir_s']>0 for r in rows)
        assert g['empty_cases']==sum(r['empty_request_s']>0 for r in rows)
        assert g['mpc_accepted_s']==sum(r['mpc_accepted_s'] for r in rows)
        assert g['action_changed_s']==sum(r['action_changed_s'] for r in rows)
        assert g['cap_violations']==0
    ratio=1-summary['groups']['mpc']['mean_deficit_auc']/summary['groups']['pi']['mean_deficit_auc']
    assert abs(summary['mpc_reduction_fraction']-ratio)<1e-12
    for row in summary['paired_patient_differences']:
        pi=np.mean([r['deficit_auc'] for r in records if r['seed']==row['seed'] and r['method']=='pi'])
        mpc=np.mean([r['deficit_auc'] for r in records if r['seed']==row['seed'] and r['method']=='mpc'])
        assert abs(row['difference']-(mpc-pi))<1e-9
    assert summary['protocol_sha256']==digest(OUT/'protocol.json')
    # A paired 600-second replay verifies actual feedback, not nominal snapshots.
    for name in ('pi','mpc'):
        result=run(37000,'clean','nominal',name,methods()[name])
        original=next(r for r in records if (r['seed'],r['physiology'],r['plant'],r['method'])==(37000,'clean','nominal',name))
        assert abs(result['metrics']['deficit_auc']-original['deficit_auc'])<1e-4
        assert result['metrics']['empty_request_s']==original['empty_request_s']
        with (OUT/f'37000-clean-nominal-{name}.csv').open() as f:trace=list(csv.DictReader(f))
        assert max(abs(a['command']-float(b['command'])) for a,b in zip(result['rows'],trace))<1e-5
    print('PASS: 48 applied-feedback runs, complete 600-step traces, shared cap/slew checks, paired aggregates, hashes and two closed-loop replays. Stable v2.0 unqualified.')


if __name__=='__main__':main()
