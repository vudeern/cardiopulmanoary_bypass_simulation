import unittest
from perfusion_research.joint_v2 import hypothesis_margin,joint_cap
from perfusion_candidates.finite_return import finite_return_reserve

class JointHypothesisTests(unittest.TestCase):
    def setUp(self):
        self.h=[dict(tau=2.,flow=2.,lower=.6,bias_upper=.1),dict(tau=6.,flow=4.,lower=1.3,bias_upper=.8)]

    def test_joint_constraint_covers_every_retained_model(self):
        cap,ok=joint_cap(self.h,0.,7.,3.,.1,.5,15.,1.)
        self.assertTrue(ok)
        self.assertGreaterEqual(hypothesis_margin(self.h,cap,3.,.1,.5,15.,1.),-1e-12)
        self.assertLess(hypothesis_margin(self.h,cap+1e-4,3.,.1,.5,15.,1.),0.)

    def test_joint_never_rejects_aggregate_feasible_action(self):
        models=[(x['tau'],x['flow']) for x in self.h];found=False
        for i in range(701):
            u=i/100.
            aggregate=.6-.29-finite_return_reserve(models,u,.5*(3.-.8-.1),15.,1.)
            joint=hypothesis_margin(self.h,u,3.,.1,.5,15.,1.)
            if aggregate>=0:self.assertGreaterEqual(joint,aggregate-1e-12)
            if aggregate<0 and joint>=0:found=True
        self.assertTrue(found)

    def test_single_hypothesis_is_exact_original_constraint(self):
        h=self.h[1:]
        for u in (0.,1.,3.,7.):
            expected=1.3-.29-finite_return_reserve([(6.,4.)],u,.5*(3.-.8-.1),15.,1.)
            self.assertAlmostEqual(hypothesis_margin(h,u,3.,.1,.5,15.,1.),expected)

    def test_empty_support_brakes_without_claiming_feasibility(self):
        self.assertEqual(joint_cap([],1.,1.3,3.,.1,.5,15.,1.),(1.,False))
