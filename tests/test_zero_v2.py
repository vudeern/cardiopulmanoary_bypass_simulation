import math
import unittest
from perfusion_candidates.finite_return import finite_return_reserve
from perfusion_research.joint_v2 import joint_cap,hypothesis_margin


class ZeroReturnTests(unittest.TestCase):
    def test_zero_credit_reserve_covers_direct_discrete_stop(self):
        # Independent step integration, then analytic tail after command hits 0.
        for tau in (1.,2.,6.,12.):
            for command in (0.,.37,3.1,7.):
                flow=4.;u=command;volume=0.;alpha=math.exp(-1./tau)
                while True:
                    after=u+(flow-u)*alpha;volume+=(flow+after)/120.;flow=after
                    if u==0:break
                    u=max(0.,u-.15)
                volume+=flow*(1+alpha)/(1-alpha)/120.
                self.assertAlmostEqual(finite_return_reserve([(tau,4.)],command,3.,0.,1.),volume,places=10)

    def test_zero_credit_cap_is_independent_of_measured_return(self):
        h=[dict(tau=2.,flow=2.,lower=.6,bias_upper=.1),dict(tau=6.,flow=4.,lower=1.3,bias_upper=.8)]
        for measured in (0.,1.,3.,7.):
            self.assertEqual(joint_cap(h,0.,7.,measured,.1,.5,0.,1.),joint_cap(h,0.,7.,0.,.1,.5,0.,1.))
            self.assertEqual(hypothesis_margin(h,2.,measured,.1,.5,0.,1.),hypothesis_margin(h,2.,0.,.1,.5,0.,1.))
