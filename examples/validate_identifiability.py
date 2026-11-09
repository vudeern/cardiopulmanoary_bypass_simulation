"""Check frozen evidence, exact grids, source provenance and selected replays."""
import csv
import json
from pathlib import Path
import numpy as np
from identifiability_study import ROOT, OUT, SEEDS, CUTOFFS, digest
from perfusion_lab.identifiability import MODES, trajectory, sensitivity, diagnose
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
import calibrated_pump_study as baseline


def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    summary=json.loads((OUT/'summary.json').read_text())
    assert protocol['seeds']==list(SEEDS)
    assert not protocol['confirmation_seeds_executed'] and not summary['confirmation_seeds_executed']
    assert not summary['version2_ready']
    for path, sha in protocol['source_hashes'].items():
        assert digest(ROOT/path)==sha, f'Changed protocol source: {path}'
    hashes=json.loads((OUT/'checksums.json').read_text())
    assert set(hashes)=={p.name for p in OUT.iterdir() if p.suffix in ('.json','.csv') and p.name!='checksums.json'}
    for path, sha in hashes.items():assert digest(OUT/path)==sha, path
    cases=[]
    for seed in SEEDS:
        for phys in ('clean','combined'):
            for plant in ('nominal','slow'):
                case=json.loads((OUT/f'{seed}-{phys}-{plant}.json').read_text())
                assert (case['seed'],case['physiology'],case['plant'])==(seed,phys,plant)
                assert len(case['analyses'])==16
                assert {(r['mode'],r['cutoff_s']) for r in case['analyses']}=={(m,c) for m in MODES for c in CUTOFFS}
                assert case['replay_parity_max_error']<1e-10
                assert case['gauge_max_measurement_error']<1e-10
                cases.append(case)
    assert summary['baseline_runs']==len(cases)==128
    assert summary['forward_replays']==31*len(cases)==3968
    assert summary['analyses']==16*len(cases)==2048
    assert summary['protocol_sha256']==digest(OUT/'protocol.json')
    assert summary['gauge_max_error']==max(c['gauge_max_measurement_error'] for c in cases)
    assert summary['max_relative_half_step_change']==max(c['relative_jacobian_half_step_change'] for c in cases)
    assert len(summary['groups'])==16
    for group in summary['groups']:
        rows=[r for c in cases for r in c['analyses'] if r['mode']==group['mode'] and r['cutoff_s']==group['cutoff_s']]
        assert group['cases']==len(rows)==128
        assert group['full_rank_cases']==sum(r['locally_full_rank'] for r in rows)
        assert group['rank_min']==min(r['numerical_rank'] for r in rows)
        assert group['rank_max']==max(r['numerical_rank'] for r in rows)
        assert group['parameters']==rows[0]['parameter_count']
        assert group['half_step_rank_disagreements']==sum(r['numerical_rank']!=r['half_step_rank'] for r in rows)
        assert group['smallest_sensitivity_min']==min(r['smallest_scaled_sensitivity'] for r in rows)
    # Four independent checks from saved commands, rather than rerunning control.
    for seed,phys,plant in ((37000,'clean','nominal'),(37014,'combined','slow'),
                            (37031,'clean','slow'),(37031,'combined','nominal')):
        case=next(c for c in cases if (c['seed'],c['physiology'],c['plant'])==(seed,phys,plant))
        with (OUT/f'{seed}-{phys}-{plant}-commands.csv').open() as stream:
            commands=list(csv.DictReader(stream))
        assert [float(r['time_s']) for r in commands]==list(range(600))
        commands=[float(r['command_L_min']) for r in commands]
        params=dict(baseline.first.previous.previous.PHYS[phys]);vb=params.pop('venous_bias',0.)
        p=Patient(**case['patient']);scenario=StressScenario(phys,**params)
        records,jac=sensitivity(p,scenario,commands,tau=case['actuator_tau_s'],venous_bias=vb)
        for old in case['analyses']:
            new=diagnose(records,jac,old['mode'],old['cutoff_s'])
            assert new['numerical_rank']==old['numerical_rank']
            np.testing.assert_allclose(new['singular_values'],old['singular_values'],rtol=1e-7,atol=1e-7)
    print('PASS: 128 cases, 3968 offline forward replays, 2048 local audits; checksums, source hashes and four replays agree. Confirmation untouched; v2.0 remains unqualified.')


if __name__=='__main__':main()
