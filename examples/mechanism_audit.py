"""Independent scalar counterexamples and a published-range plausibility audit.

These calculations do not call the full simulator's observer/controller.
Range concordance is explicitly not physical or clinical validation.
"""
import csv
import json
import math
from pathlib import Path
import numpy as np
from perfusion_lab.model import Patient

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/mechanism-audit'


def equilibrium(floor,margin,level_bias,flow_bias,horizon):
    return floor+margin-level_bias-horizon*flow_bias/60.


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for horizon in (5.,10.,20.,40.):
        for bias in (-.6,0.,.3,.6,.9):
            for margin in (0.,.1,.2,.4):
                for offset in (0.,.15):
                    expected=equilibrium(.25,margin,offset,bias,horizon)
                    volume=.85;dt=.5;drainage=4.
                    for _ in range(4000):
                        command=drainage+bias+60.*(volume+offset-margin-.25)/horizon
                        volume+=(drainage-command)*dt/60.
                    error=abs(volume-expected)
                    assert error<1e-9
                    records.append(dict(horizon_s=horizon,flow_bias_L_min=bias,margin_L=margin,
                        residual_level_bias_L=offset,predicted_equilibrium_L=expected,
                        numerical_equilibrium_L=volume,error_L=error,
                        equilibrium_below_floor=expected<.25,
                        negative_equilibrium_outside_physical_domain=expected<0.))
    with (OUT/'equilibria.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(records)
    # Construct two indistinguishable measured flow/volume-derivative signals.
    ident=[]
    for delta in (-.5,.5,1.):
        qv,qa,bias=4.,4.5,.3
        a=dict(qv=qv,qa=qa,bias=bias)
        b=dict(qv=qv+delta,qa=qa+delta,bias=bias-delta)
        assert a['qa']+a['bias']==b['qa']+b['bias']
        assert a['qv']-a['qa']==b['qv']-b['qa']
        ident.append(dict(delta=delta,system_a=a,system_b=b,
            measured_flow=a['qa']+a['bias'],volume_rate_L_s=(a['qv']-a['qa'])/60.))
    # Source: Searles et al. 2021, Tables 1/2. These are survey-derived
    # operating-limit summaries, not raw reservoir bench trajectories.
    samples=[]
    for seed in range(20000,20200):
        patient=Patient.sampled(seed);flow=2.4*patient.bsa;pressure=flow*patient.resistance
        samples.append(dict(seed=seed,flow_L_min=flow,flow_index=flow/patient.bsa,
            pressure_mmHg=pressure,in_reported_mean_limit_band=54.<=pressure<=82.))
    with (OUT/'nominal-range-audit.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(samples[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(samples)
    summary=dict(scalar_cases=len(records),maximum_error_L=max(r['error_L'] for r in records),
        identifiability_counterexamples=ident,
        published_range_source=dict(title='Orpheus CPB simulator validation study',
            authors='Searles, Darling and Riley',year=2021,doi='10.1182/ject-53-263',
            url='https://pmc.ncbi.nlm.nih.gov/articles/PMC8717731/',
            map_reported_low_limit_mean=54.,map_reported_high_limit_mean=82.,
            flow_index_reported_mean=2.34,flow_index_reported_sd=.35,
            interpretation='Survey-derived mean operating limits; not a distributional confidence interval or external time-series validation'),
        nominal_sample=dict(n=len(samples),fixed_index=2.4,
            pressure_min=min(r['pressure_mmHg'] for r in samples),
            pressure_max=max(r['pressure_mmHg'] for r in samples),
            fraction_in_mean_limit_band=float(np.mean([r['in_reported_mean_limit_band'] for r in samples]))),
        external_validation_completed=False,
        limits=['Reduced active-constraint idealization excludes actuator lag, clipping, pressure/oxygen constraints, noise and delayed differentiation.',
                'Negative mathematical equilibria are infeasible physical requests, not simulated negative blood volumes.',
                'Published-range concordance does not validate reservoir dynamics or clinical outcomes.',
                'Algebraic non-identifiability assumes unmeasured/unconstrained drainage and no trusted calibrated actuator model.'])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Verified',len(records),'scalar equilibria and',len(ident),'indistinguishable-system examples; range audit is not external validation.')

if __name__=='__main__':main()
