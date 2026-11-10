import json
import math
from pathlib import Path
import random
import unittest


class V1ClosureTests(unittest.TestCase):
    def test_positive_pump_recurrence_gives_fixed_cap_upper_bound(self):
        rng=random.Random(101)
        for tau in (2.,6.):
            alpha=math.exp(-1./tau);q=4.;upper=4.
            for _ in range(600):
                cap=rng.uniform(0.,7.);u=rng.uniform(0.,cap)
                q=alpha*q+(1-alpha)*u;upper=alpha*upper+(1-alpha)*cap
                self.assertLessEqual(q,upper+1e-12)

    def test_published_bound_has_explicit_scope(self):
        root=Path(__file__).resolve().parents[1]
        bound=json.loads((root/'results/v1-closure/fixed-ceiling-bound.json').read_text())
        self.assertTrue(bound['fixed_ceiling_10_percent_ruled_out'])
        self.assertFalse(bound['universal_mpc_impossibility_proven'])
        self.assertLess(bound['maximum_reduction_fraction'],.001)
        self.assertEqual(len(bound['cases']),16)
        self.assertEqual(bound['confirmation_seeds_executed'],[])
