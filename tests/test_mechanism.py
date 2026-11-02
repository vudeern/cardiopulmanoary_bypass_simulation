"""Hand-calculated mechanism cases, separate from full simulator behavior."""
import unittest
from examples.mechanism_audit import equilibrium

class MechanismTests(unittest.TestCase):
    def test_correct_level_does_not_cancel_flow_bias(self):
        self.assertAlmostEqual(equilibrium(.25,.2,0.,.9,20.),.15)

    def test_required_margin_offsets_both_error_terms(self):
        self.assertAlmostEqual(equilibrium(.25,.45,.15,.9,20.),.25)

if __name__=='__main__':unittest.main()
