import math
import unittest
from dataclasses import replace
from perfusion_lab.model import Patient
from perfusion_lab.published_control import OccluderMap,ThirdOrderReference,PublishedLevelAdapter
from perfusion_lab.simulation import simulate


class SourceComponentTests(unittest.TestCase):
    def test_static_map_matches_direct_published_expression(self):
        # Independent direct Eq.1; arbitrary calibration fixtures, not author values.
        r,d,a,k,q0=14.,2.,.02,2.,7.5
        model=OccluderMap(q0,a*(r+d),k)
        for x in (0.,.1,.3,.9,1.5):
            z=math.expm1(k*x)
            expected=(1+d/r)*q0*r*a*z/(1+r*a*z+d*a*z)
            self.assertAlmostEqual(model.flow(x),expected,places=12)
            self.assertAlmostEqual(model.inverse(expected),x,places=12)

    def test_analytic_third_order_step_response_and_refinement(self):
        sigma=3.6
        for dt in (.1,.5,1.):
            model=ThirdOrderReference(sigma,dt,0.)
            for i in range(round(18/dt)):
                value=model.update(1.)
                t=(i+1)*dt
                exact=1.-math.exp(-t/sigma)*(1+t/sigma+.5*(t/sigma)**2)
                self.assertAlmostEqual(value,exact,places=12)

    def test_invalid_parameters_and_inverse_domain_rejected(self):
        for args in ((0,1,1),(1,-1,1),(1,1,math.nan)):
            with self.assertRaises(ValueError):OccluderMap(*args)
        model=OccluderMap(3.,.1,2.)
        for q in (-1.,3.,math.nan):
            with self.assertRaises(ValueError):model.inverse(q)
        with self.assertRaises(ValueError):ThirdOrderReference(0.,1.,0.)
        with self.assertRaises(ValueError):PublishedLevelAdapter(1.8,kd=-1.)

    def test_explicit_measured_venous_channel_required(self):
        with self.assertRaises(ValueError):simulate(controller_kind='published_adapted',duration=10.)
        with self.assertRaises(ValueError):simulate(venous_measurement={'noise_sd':-1.},duration=10.)
        with self.assertRaises(ValueError):simulate(venous_measurement={'future':1.},duration=10.)

    def test_sensor_is_current_acquisition_and_limits_are_shared(self):
        p=Patient()
        result=simulate('nominal',seed=13000,duration=60.,dt=1.,patient=p,
            controller_kind='published_adapted',venous_measurement={'noise_sd':0.})
        first=result['rows'][0]
        expected=(p.volume-.85-p.unstressed_volume)/(p.venous_compliance*p.venous_resistance)
        self.assertAlmostEqual(first['observed_venous_flow'],expected)
        self.assertEqual(first['observation_time'],0.)
        previous=2.4*p.bsa
        for r in result['rows']:
            self.assertTrue(0<=r['command']<=7.)
            self.assertLessEqual(abs(r['command']-previous),.15+1e-10)
            previous=r['command']

    def test_legacy_channel_is_optional_and_exactly_reproducible(self):
        a=simulate('compound',duration=60.,seed=14000)
        b=simulate('compound',duration=60.,seed=14000,venous_measurement=None)
        self.assertEqual(a,b)
        self.assertTrue(all(r['observed_venous_flow'] is None for r in a['rows']))


if __name__=='__main__':unittest.main()
