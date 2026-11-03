"""Reproduce the public single-case oxygen replay. No network or fitting needed."""
import csv
import hashlib
import io
import json
from pathlib import Path
from perfusion_lab.patient_replay import read_observations, replay_oxygen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'data/published-case'
OUT = ROOT/'results/published-case'


def artifacts():
    provenance = json.loads((SOURCE/'provenance.json').read_text())
    observations = read_observations(SOURCE/'observations.csv')
    rows = replay_oxygen(observations, provenance['bsa_m2'],
                         provenance['assumed_saturation_sensitivity'])
    k = provenance['source_coefficients']
    differences = []
    for r in rows:
        # Source equation sensitivity; saturation=1 is an assumption, not fitted.
        comparator = 10*r['flow_l_min']*(k['hb_capacity_ml_g']*r['hb_g_dl']
                        + k['dissolved_ml_dl_mmhg']*r['pao2_mmhg'])
        r['source_equation_saturation_1_ml_min'] = comparator
        differences.append(comparator-r['reported_do2_ml_min'])
    summary = dict(
        status='published_patient_oxygen_replay_only',
        patient_count=1, sample_count=len(rows),
        observed_times_min=[r['time_s']/60 for r in rows],
        raw_monitor_data_obtained=False, patient_dynamic_validation_completed=False,
        reservoir_validation_completed=False, counterfactual_controller_tested=False,
        held_out_prediction_tested=False, fitting_performed=False,
        measured_arterial_saturation_available=all(r['sao2_fraction'] is not None for r in rows),
        assumption='SaO2 sensitivity 0.98–1.00; not a measured or calibrated uncertainty interval',
        bsa_m2=provenance['bsa_m2'],
        missing_for_dynamic_validation=provenance['missing_for_dynamic_validation'],
        source_equation_max_abs_difference_ml_min=max(map(abs, differences)),
        source_equation_interpretation='Calculated quantity compared to another calculated quantity; arithmetic consistency, not independent accuracy validation. Rounded published inputs and unknown saturation preclude exact reconstruction.',
        measured_pao2_increment_do2i_range=[min(r['measured_pao2_increment_do2i'] for r in rows), max(r['measured_pao2_increment_do2i'] for r in rows)],
        inputs_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SOURCE.iterdir()) if p.is_file()},
        rows=rows)
    json_text=json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    csv_io=io.StringIO(newline='')
    fields=['time_s','flow_l_min','hb_g_dl','pao2_mmhg','sao2_fraction','temperature_c',
            'reported_do2_ml_min','reported_do2i','project_do2i_low','project_do2i_high',
            'fixed_pao2_150_do2i','measured_pao2_increment_do2i','saturation_status',
            'source_equation_saturation_1_ml_min']
    w=csv.DictWriter(csv_io,fieldnames=fields,extrasaction='ignore',lineterminator='\n')
    w.writeheader();w.writerows(rows)
    return {'results/published-case/replay.json':json_text,
            'results/published-case/replay.csv':csv_io.getvalue()}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for name,content in artifacts().items():
        path=ROOT/name
        if args.check:
            if path.read_text()!=content:
                raise SystemExit(f'Artifact differs: {name}')
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content)
    print('Published-patient replay: 1 case, 5 observations; artifacts '+('verified' if args.check else 'written')+'. No dynamic validation claimed.')


if __name__=='__main__':
    main()
