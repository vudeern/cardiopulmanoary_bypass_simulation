"""Behavioral checks for the offline information audit."""
import unittest
import numpy as np
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressScenario
from perfusion_lab.identifiability import trajectory, sensitivity, diagnose


class IdentifiabilityTests(unittest.TestCase):
    def test_storage_and_shared_offset_have_identical_outputs(self):
        p=Patient();s=StressScenario('test');u=np.full(150,4.)
        base=trajectory(p,s,u)
        shifted=trajectory(p,s,u,delta=[.02,0,0,0,-.02,-.02,0])
        np.testing.assert_allclose([r[3] for r in base], [r[3] for r in shifted], atol=1e-12)

    def test_delayed_anchor_only_counts_after_delivery(self):
        p=Patient();s=StressScenario('test')
        records,jac=sensitivity(p,s,np.linspace(3.,5.,150))
        before=diagnose(records,jac,'healthy',5.)
        after=diagnose(records,jac,'healthy',6.)
        self.assertEqual(after['observations']-before['observations'],5)
        cal=[r for r in records if r[2]=='calibration']
        self.assertEqual(cal[0][:2],(6.,0.))

    def test_shared_unknown_retains_null_direction(self):
        p=Patient();s=StressScenario('test')
        records,jac=sensitivity(p,s,np.linspace(3.,5.,150))
        shared=diagnose(records,jac,'shared_unknown',149.)
        healthy=diagnose(records,jac,'healthy',149.)
        self.assertLess(shared['numerical_rank'],shared['parameter_count'])
        self.assertTrue(healthy['locally_full_rank'])

    def test_pump_outflow_reduces_reservoir(self):
        p=Patient();s=StressScenario('test',drainage=0.,event_start=0.,event_end=1.)
        records=trajectory(p,s,[5.,5.])
        levels=[r[3] for r in records if r[2]=='inline']
        self.assertLess(levels[1],levels[0])

    def test_rejects_invalid_inputs(self):
        for commands in ([],[-1.],[8.],[float('nan')]):
            with self.assertRaises(ValueError):trajectory(Patient(),StressScenario('test'),commands)
