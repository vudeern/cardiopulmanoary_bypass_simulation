"""Independent validation of the adaptive rc.5 four-arm comparison."""
import argparse
import json
import math
import numpy as np
import calibrated_pump_study as study
import validate_startup
from perfusion_lab.benchmark import paired_interval


def close(a,b): assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),(a,b)


def validate(replay=False):
    validate_startup.validate(False)
    p = json.loads(study.dumps(study.protocol())); s = json.loads((study.OUT/'summary.json').read_text())
    rows = study.read_rows(); names = ('rc4','single_anchor')+study.NAMES
    assert s['runs'] == 4096 and s['new_runs_this_stage'] == 2048 and s['patients'] == 32
    assert not s['version2_ready'] and s['qualifying_confirmation_cohorts'] == 0
    assert s['confirmation_seeds_executed'] == p['confirmation_seeds_executed'] == []
    assert s['protocol_sha256'] == study.digest(study.OUT/'protocol.json')
    assert s['first_stage_summary_sha256'] == study.digest(study.first.OUT/'summary.json')
    for path,sha in p['source_hashes'].items(): assert study.digest(study.ROOT/path) == sha,path
    expected = {(seed,*cell,n) for seed in study.SEEDS for cell in study.first.previous.cells() for n in names}
    actual = [tuple(r[k] for k in ('seed','stage','phys','plant','fault','calibration','method')) for r in rows]
    assert len(actual) == len(set(actual)) == len(expected) and set(actual) == expected
    for r in rows:
        for m in study.METRICS: assert math.isfinite(r[m]) and r[m] >= 0
        close(r['startup_deficit_auc']+r['later_deficit_auc'],r['deficit_auc'])
        assert r['startup_unsupported_s'] <= min(126.,r['protection_unsupported_s'])
    archived = [r for r in study.first.previous.read_rows() if r['method'] == 'eligible_pi' and r['stage'] == 'primary']
    assert len(archived) == 512
    for g,stats in s['groups'].items():
        for name,reported in stats.items():
            source = archived if name == 'archived_pi' else [r for r in rows if r['method'] == name]
            block = [r for r in source if study.first.previous.belongs(r,g)]
            assert reported['runs'] == len(block)
            for m,v in reported['means'].items(): close(v,np.mean([r[m] for r in block]))
            close(reported['worst_minimum_L'],min(r['minimum_reservoir'] for r in block))
            close(reported['worst_floor_exposure_s'],max(r['low_reservoir_s'] for r in block))
            assert reported['floor_crossing_cases'] == sum(r['low_reservoir_s'] > 0 for r in block)
            assert reported['empty_cases'] == sum(r['empty_request_s'] > 0 for r in block)
    eligible = [name for name in names if all(r['low_reservoir_s'] == r['empty_request_s'] == 0 for r in rows if r['method'] == name and r['stage'] in ('primary','abrupt_stop'))]
    assert eligible == s['eligible_candidates']
    winner = min(eligible,key=lambda n:s['groups']['primary'][n]['means']['deficit_auc']) if eligible else None
    selected = winner if winner != 'rc4' else None
    assert selected == s['selected_candidate']
    expected_c = {(n,b,g,m) for n in ('single_anchor',)+study.NAMES for b in ('rc4','archived_pi') for g in ('clean','bias','outage') for m in ('deficit_auc','low_reservoir_s','empty_request_s','high_pressure_s')}
    actual_c = [(c['candidate'],c['baseline'],c['group'],c['metric']) for c in s['comparisons']]
    assert len(actual_c) == len(set(actual_c)) == len(expected_c) and set(actual_c) == expected_c
    for c in s['comparisons']:
        differences=[]
        for seed in study.SEEDS:
            a=[r for r in rows if r['seed']==seed and r['method']==c['candidate'] and study.first.previous.belongs(r,c['group'])]
            source=archived if c['baseline']=='archived_pi' else [r for r in rows if r['method']=='rc4']
            b=[r for r in source if r['seed']==seed and study.first.previous.belongs(r,c['group'])]
            differences.append(np.mean([r[c['metric']] for r in a])-np.mean([r[c['metric']] for r in b]))
        interval=paired_interval(differences)
        for k in ('mean','low','high','n'): close(c[k],interval[k])
    gates={}
    if selected:
        for g in ('clean','bias','outage'):
            a=s['groups'][g][selected];b=s['groups'][g]['archived_pi']
            intervals={c['metric']:c for c in s['comparisons'] if c['candidate']==selected and c['baseline']=='archived_pi' and c['group']==g}
            gates[g]=dict(oxygen_mean_10_percent=a['means']['deficit_auc']<=.9*b['means']['deficit_auc'],oxygen_paired_interval=intervals['deficit_auc']['high']<0,
                mean_low_reservoir=a['means']['low_reservoir_s']<=1.,zero_empty_requests=a['empty_cases']==0,
                extra_low_reservoir=intervals['low_reservoir_s']['high']<=1.,extra_empty_requests=intervals['empty_request_s']['high']<=1.,extra_high_pressure=intervals['high_pressure_s']['high']<=5.)
    assert gates==s['development_gates']
    assert s['development_joint_success']==bool(selected and all(all(v.values()) for v in gates.values()))
    missing={}
    for row in rows:
        if row['calibration']!='missing':continue
        key=tuple(row[k] for k in ('seed','phys','plant'))
        if key not in missing:missing[key]=row
        else:
            for m in study.METRICS:close(row[m],missing[key][m])
    original=(study.ROOT/'src/perfusion_candidates/startup_simulation.py').read_text()
    expected_adapter=original.replace('Single-anchor startup adapter; frozen physiology and timing.','Calibrated-pump candidate adapter; frozen physiology and timing.').replace('def simulate_startup(','def simulate_calibrated_pump(').replace('from perfusion_candidates.startup import StartupRuntime as ControllerRuntime','from perfusion_candidates.calibrated_pump import CalibratedPumpRuntime as ControllerRuntime')
    assert expected_adapter==(study.ROOT/'src/perfusion_candidates/calibrated_pump_simulation.py').read_text()
    if replay:
        for stage in ('primary','abrupt_stop'):
            for name in study.NAMES:
                fault='positive_start' if stage=='primary' else 'clean'
                result=study.run(37014,stage,'combined','slow',fault,'good',name,study.methods()[name])
                metrics=study.first.measured_metrics(result)
                row=next(r for r in rows if tuple(r[k] for k in ('seed','stage','phys','plant','fault','calibration','method'))==(37014,stage,'combined','slow',fault,'good',name))
                for m in study.METRICS:close(metrics[m],row[m])
    print('PASS: 4,096 four-arm records, both frozen protocols, aggregates, 72 paired intervals, selection/gates and fallback parity'+(' and four follow-up replays.' if replay else '.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--replay',action='store_true')
    validate(parser.parse_args().replay)
