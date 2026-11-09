"""Reproduce the free published SIMC normalized example and independent checks."""
import json
import math
from pathlib import Path
import numpy as np
from perfusion_lab.simc import integrating_settings,PICore

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/simc-verification'


def bisect(f,lo,hi):
    if f(lo)*f(hi)>0:raise ValueError('Root not bracketed')
    for _ in range(100):
        mid=(lo+hi)/2
        if f(lo)*f(mid)<=0:hi=mid
        else:lo=mid
    return (lo+hi)/2


def normalized_frequency():
    settings=integrating_settings(1.,1.,1.)
    def loop(w):
        s=1j*w
        return settings.kc*(1+1/(settings.tau_i*s))*np.exp(-s)/s
    wc=bisect(lambda w:abs(loop(w))-1.,.001,10.)
    phase=lambda w:-math.pi/2-math.atan(1/(settings.tau_i*w))-w
    w180=bisect(lambda w:phase(w)+math.pi,.001,4.)
    frequencies=np.geomspace(1e-5,1e3,200000)
    sensitivity=1/np.abs(1+loop(frequencies))
    return dict(gain_margin=float(1/abs(loop(w180))),
                phase_margin_deg=(math.pi+phase(wc))*180/math.pi,
                max_sensitivity=float(sensitivity.max()),
                phase_crossover=w180,gain_crossover=wc)


def time_check(dt):
    # Independent closed-loop solution for k'=1, theta=0, tau_c=1.
    # Y/R=(s+1/4)/(s+1/2)^2; y=1-exp(-t/2)*(1-t/2).
    controller=PICore(integrating_settings(1.,0.,1.),dt)
    y=0.;maximum=0.
    for step in range(round(20/dt)):
        u=controller.update(1.,y);y+=u*dt
        t=(step+1)*dt;exact=1-math.exp(-t/2)*(1-t/2)
        maximum=max(maximum,abs(y-exact))
    return maximum


def verification():
    source=json.loads((ROOT/'data/simc-reference/source.json').read_text())
    fixture=source['verification_case'];settings=integrating_settings(fixture['kprime'],fixture['theta'],fixture['tau_c'])
    assert settings.kc==fixture['published_Kc'] and settings.tau_i==fixture['published_tauI']
    frequency=normalized_frequency()
    checks={key:abs(value-fixture['published_'+key])<=fixture['tolerances'][key] for key,value in frequency.items()}
    assert all(checks.values())
    errors={str(dt):time_check(dt) for dt in (.02,.01,.005)}
    assert errors['0.005']<errors['0.01']<errors['0.02'] and errors['0.005']<.005
    return dict(status='published_PI_tuning_and_normalized_frequency_example_reproduced',
        source=source['author_corrections_and_examples'],settings=dict(kc=settings.kc,tau_i=settings.tau_i),
        frequency=frequency,published_checks=checks,time_domain_max_errors=errors,
        scope='Verifies general PI mathematics and the published normalized example. CPB supervisor choices are separately declared; no clinical device or patient validation.')


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');a=parser.parse_args()
    text=json.dumps(verification(),indent=2)+'\n';path=OUT/'verification.json'
    if a.check:
        saved=json.loads(path.read_text());rebuilt=json.loads(text)
        assert saved.keys()==rebuilt.keys()
        for key in ('frequency','time_domain_max_errors'):
            for name,value in saved[key].items():
                assert math.isclose(value,rebuilt[key][name],rel_tol=1e-10,abs_tol=1e-12)
        for key in set(saved)-{'frequency','time_domain_max_errors'}:assert saved[key]==rebuilt[key]
    else:OUT.mkdir(parents=True,exist_ok=True);path.write_text(text)
    print('PASS: published SIMC gains, five frequency values and independent time-domain refinement.')


if __name__=='__main__':main()
