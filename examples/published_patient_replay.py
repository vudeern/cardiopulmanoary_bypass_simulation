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
    table='\n'.join(f"| {r['time_s']/60:.0f} | {r['flow_l_min']:.2f} | {r['hb_g_dl']:.2f} | {r['pao2_mmhg']:.0f} | {r['reported_do2i']:.2f} | {r['project_do2i_low']:.2f}–{r['project_do2i_high']:.2f} |" for r in rows)
    a,b=summary['measured_pao2_increment_do2i_range']
    report=f'''# Published-patient oxygen replay

## What was actually done

One actual published CPB case is now replayed at its five reported observation times, using recorded flow, Hb and PaO2 and the reported BSA. This is an **oxygen-equation replay**, not a fitted digital twin or a simulation of that patient's reservoir response. No raw monitor export was obtained. No invented points fill the 15-minute gaps; no continuous deficit AUC is calculated.

Source: Hunter KT II, Lopez AR, Yun KL. *Emergent Cardiopulmonary Bypass for a 180 Kilogram Patient: Support with a Single Oxygenator.* J Extra Corpor Technol. 2013;45:178–182. [Table 1 and case description]({provenance['source_url']}). Numerical facts were manually transcribed and checked; original article copyright remains with AMSECT. See [provenance](../data/published-case/provenance.json) and [input CSV](../data/published-case/observations.csv).

## Measurements and assumptions

The case reports BSA **2.73 m²**. Table 1 supplies timed pump flow, Hb, PaO2, temperature and calculated oxygen delivery. **Arterial saturation is absent.** Mixed venous saturation must not be substituted for arterial saturation. We show chosen SaO2 sensitivity endpoints **0.98–1.00**, not measured values, confidence intervals or guaranteed physiologic bounds. Temperature is retained as context; the content equation is not temperature adjusted.

The project equation is `DO2i = 10 × flow × (1.34 × Hb × SaO2 + 0.0031 × PaO2) / BSA`. Existing synthetic experiments retain their original 150 mmHg PaO2 default. The new optional PaO2 input and replay use the reported values.

| Time (min) | Flow (L/min) | Hb (g/dL) | PaO2 (mmHg) | Reported DO2 / BSA | Project DO2i, SaO2 sensitivity |
| --- | --- | --- | --- | --- | --- |
{table}

Oxygen delivery units: mL O2/min/m². The five observations are samples of one patient, not five independent patients.

![Published patient oxygen replay](published-patient.svg)

## Result and interpretation

At the same assumed saturation, replacing the old fixed PaO2 of 150 with the reported PaO2 raises calculated DO2i by **{a:.2f}–{b:.2f} mL O2/min/m²** across these samples. This quantifies a simplification in our oxygen module on actual recorded inputs; it does not establish a new physiological finding.

The source's Figure 2 uses coefficients **1.36 and 0.0032**, whereas this project's unchanged equation uses **1.34 and 0.0031**. With source coefficients and an explicit saturation=1 assumption, the largest absolute difference from reported total DO2 is **{summary['source_equation_max_abs_difference_ml_min']:.3f} mL/min**. We did not tune coefficients or saturation to the reported output. Rounded inputs and unreported saturation limit interpretation. Agreement between two calculated quantities checks arithmetic consistency, not predictive accuracy or clinical validation.

## What prevents the requested dynamic patient simulation

Synchronized pump commands, reservoir volume, venous return, time-resolved volume transfers and arterial pressure are missing. The five sparse samples cannot identify the patient's drainage, storage, actuator or sensor-bias dynamics. Running the existing synthetic reservoir using this patient's BSA would add assumed physiology; we do not label that a validated patient twin. The existing manuscript's reservoir conclusions remain synthetic.

A suitable next dataset must contain recorded inputs and independently observed responses at adequate resolution. Fit only on a development interval/cases, compare one-step and multi-step held-out predictions with persistence and simple physical baselines, and evaluate calibration across other patients before interpreting controller counterfactuals. Actual recorded care cannot establish outcomes under an unobserved alternative controller.

## Data-source audit

- **Selected:** the public Hunter case supplies five timed oxygen-input observations, usable now within the scope above.
- **[Mendeley CPB blood gases](https://data.mendeley.com/datasets/zkyr3hnmkr/4):** public metadata describes blood gases, not the required reservoir-control channels; no raw file was ingested. Direct metadata retrieval from this runtime returned HTTP 403.
- **[INSPIRE 1.4.2](https://physionet.org/content/inspire/1.4.2/):** credentialed access requires approved user status, CITI training and a signed DUA. No credentialed records were downloaded; synchronized pump/level channels remain unverified. Access alone is not evidence of suitability.
- **[GARIX](https://journals.sagepub.com/doi/10.1177/02676591251375788):** published minute-level pediatric CPB modeling supports feasibility; raw patient access was not established in this search.
- **[CM-CAD v1.2](https://zenodo.org/records/22144463):** release README describes ECG/SCG/PCG and session-level references. It does not establish synchronized CPB reservoir and command traces; CABG recordings alone do not meet our requirement.

This scoped search did not locate an openly retrievable, verified reservoir/command patient series. It does not prove none exists. No authors were contacted and no access agreements were accepted on the user's behalf.

## Reproduce

```bash
python examples/published_patient_replay.py
python examples/published_patient_replay.py --check
```

Outputs: [JSON with explicit evidence status](../results/published-case/replay.json), [derived CSV](../results/published-case/replay.csv), this report and the figure. The check recomputes all artifacts from source inputs and checks exact equality. Unit tests separately cover explicit units, missing saturation, input rejection, and oxygen-equation arithmetic.
'''
    # Scatter-only SVG: no invented continuous patient trajectory.
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="980" height="450" viewBox="0 0 980 450" role="img" aria-labelledby="title desc">',
        '<title id="title">Five observations from a published bypass patient</title>',
        '<desc id="desc">Reported indexed oxygen delivery and project calculation with assumed arterial saturation endpoints. No interpolation or reservoir validation.</desc>',
        '<rect width="980" height="450" fill="#0c161a"/>',
        '<g font-family="sans-serif" fill="#dce7e8"><text x="75" y="35" font-size="21">Actual recorded inputs. Explicit missing information.</text>',
        '<text x="75" y="61" font-size="13">One published case · BSA 2.73 m² · points only; no interpolation</text>']
    x=lambda t:85+(t/60-8)/60*795
    y=lambda v:340-(v-80)/240*240
    for tick in [100,150,200,250,300]:
        yy=y(tick)
        parts.append(f'<path d="M75 {yy} H910" stroke="#2c3b40"/><text x="34" y="{yy+4}" font-size="12">{tick}</text>')
    for r in rows:
        xx=x(r['time_s']);yl=y(r['project_do2i_low']);yh=y(r['project_do2i_high']);yp=y(r['reported_do2i'])
        parts.append(f'<path d="M{xx} {yl} V{yh} M{xx-5} {yl} H{xx+5} M{xx-5} {yh} H{xx+5}" fill="none" stroke="#efba6b" stroke-width="3"/>')
        parts.append(f'<circle cx="{xx+9}" cy="{yp}" r="5" fill="#69d9bb"/><text x="{xx-7}" y="365" font-size="12">{r["time_s"]/60:.0f}</text>')
    parts += ['<text x="75" y="88" font-size="12">DO2i (mL O2/min/m²)</text><text x="750" y="389" font-size="12">Time on bypass (min)</text>',
              '<circle cx="85" cy="412" r="5" fill="#69d9bb"/><text x="99" y="416" font-size="12">Reported DO2 / BSA</text>',
              '<path d="M360 405 V419" stroke="#efba6b" stroke-width="3"/><text x="373" y="416" font-size="12">Project equation: assumed SaO2 0.98–1.00 (unmeasured)</text>', '</g></svg>']
    svg='\n'.join(parts)+'\n'
    return {'results/published-case/replay.json':json_text,
            'results/published-case/replay.csv':csv_io.getvalue(),
            'docs/PATIENT_REPLAY.md':report, 'docs/published-patient.svg':svg,
            'web/published-patient.svg':svg}


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
