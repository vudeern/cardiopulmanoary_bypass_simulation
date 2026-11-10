"""Validate exact grid, source provenance, aggregates, trace parity and LP replays."""
import hashlib
import json
import math
import numpy as np
import calibrated_pump_study as old
from horizon_study import ROOT,OUT,SEEDS,TIMES,REASONS,methods,digest
from perfusion_research.horizon import HorizonSolver,formulate,validate_plan


def main():
    protocol=json.loads((OUT/'protocol.json').read_text());summary=json.loads((OUT/'summary.json').read_text())
    assert protocol['seeds']==list(SEEDS)
    assert not protocol['confirmation_seeds_executed'] and not summary['confirmation_seeds_executed']
    assert not summary['version2_ready']
    for name,sha in protocol['source_hashes'].items():assert digest(ROOT/name)==sha,name
    hashes=json.loads((OUT/'checksums.json').read_text())
    assert set(hashes)=={p.name for p in OUT.glob('*.json') if p.name!='checksums.json'}
    for name,sha in hashes.items():assert digest(OUT/name)==sha,name
    cases=[]
    for seed in SEEDS:
        for phys in ('clean','combined'):
            for plant in ('nominal','slow'):
                for name in methods():
                    c=json.loads((OUT/f'{seed}-{phys}-{plant}-{name}.json').read_text())
                    assert (c['seed'],c['physiology'],c['plant'],c['method'])==(seed,phys,plant,name)
                    assert set(c['reasons'])==set(REASONS)
                    assert sum(b['seconds'] for b in c['reasons'].values())==600
                    assert abs(sum(b['deficit_auc'] for b in c['reasons'].values())-c['metrics']['deficit_auc'])<1e-8
                    expected={(t,f) for t in TIMES for f in ('measured_constant','protected_constant')} if name=='rc5' else set()
                    assert {(p['time'],p['forecast']) for p in c['snapshots']}==expected
                    for snapshot in c['snapshots']:
                        if snapshot['accepted']:
                            p=formulate(snapshot['initial'],snapshot['previous'],np.full(15,snapshot['inflow']),
                                np.full(15,snapshot['conversion']),np.full(15,280.))
                            check=validate_plan(p,snapshot['vector']);assert check['valid']
                            assert snapshot['elapsed_s']<=snapshot['deadline_s']
                        else:assert snapshot['command'] is None and snapshot['vector'] is None
                    cases.append(c)
    assert summary['baseline_runs']==len(cases)==384
    assert summary['snapshot_plans']==sum(len(c['snapshots']) for c in cases)==1024
    assert summary['protocol_sha256']==digest(OUT/'protocol.json')
    for name,stats in summary['groups'].items():
        group=[c for c in cases if c['method']==name]
        assert len(group)==stats['runs']==128
        total=sum(c['metrics']['deficit_auc'] for c in group)
        assert abs(total/128-stats['mean_deficit_auc'])<1e-9
        assert stats['floor_cases']==sum(c['metrics']['low_reservoir_s']>0 for c in group)
        assert stats['empty_cases']==sum(c['metrics']['empty_request_s']>0 for c in group)
        for reason,b in stats['reasons'].items():
            seconds=sum(c['reasons'][reason]['seconds'] for c in group)
            assert b['seconds']==seconds
            assert abs(b['deficit_fraction']-sum(c['reasons'][reason]['deficit_auc'] for c in group)/total)<1e-12
    for forecast,stats in summary['snapshots'].items():
        snapshots=[s for c in cases for s in c['snapshots'] if s['forecast']==forecast]
        assert stats['plans']==len(snapshots)==512
        assert stats['accepted']==sum(s['accepted'] for s in snapshots)
        assert stats['rejected']==sum(not s['accepted'] for s in snapshots)
        assert stats['over_2ms']==sum(s['elapsed_s']>.002 for s in snapshots)
        assert stats['statuses']=={s:sum(p['status']==s for p in snapshots) for s in {p['status'] for p in snapshots}}
    # Re-run original, uninstrumented source on four cases: instrumentation must
    # not change any applied command or metric. No confirmation seed is used.
    checks=((37000,'clean','nominal','rc5'),(37014,'combined','slow','rc5'),
            (37031,'clean','slow','pi_standard'),(37031,'combined','nominal','pi_fast'))
    for seed,phys,plant,name in checks:
        c=next(c for c in cases if (c['seed'],c['physiology'],c['plant'],c['method'])==(seed,phys,plant,name))
        result=old.run(seed,'primary',phys,plant,'clean','good',name,methods()[name])
        commands=np.asarray([r['command'] for r in result['rows']],dtype='<f8')
        assert hashlib.sha256(commands.tobytes()).hexdigest()==c['commands_sha256']
        for metric,value in result['metrics'].items():assert abs(value-c['metrics'][metric])<1e-9,metric
        if name=='rc5':
            for snapshot in c['snapshots']:
                if not snapshot['accepted']:continue
                p=formulate(snapshot['initial'],snapshot['previous'],np.full(15,snapshot['inflow']),
                    np.full(15,snapshot['conversion']),np.full(15,280.))
                replay=HorizonSolver().solve(p);assert replay['accepted']
                assert abs(replay['checks']['objective']-snapshot['checks']['objective'])<1e-6
    print('PASS: 384 measured runs; 1024 offline snapshots; source hashes/checksums, physical plan checks, aggregates and four uninstrumented command replays. No MPC performance qualification.')


if __name__=='__main__':main()
