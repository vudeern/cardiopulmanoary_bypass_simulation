from dataclasses import replace
import unittest
from perfusion_lab.runtime import MeasurementFrame
from perfusion_lab.sensing import Observation
from perfusion_research.boot_v2 import BootRuntime,StartupRejected,ActuationContractViolation


def frame(flow=0.,volume=.85,time=0.):
    return MeasurementFrame(Observation(time=time,flow=flow,reservoir=volume,pressure=0.,hb_inline=10.,sao2=.98,temperature=37.,hb_lab=10.),4.)


def runtime(budget=None):
    options={'return_horizon_s':0.}
    if budget is not None:options['envelope_budget']=budget
    return BootRuntime(bsa=1.8,initial_hb=10.,controller_options=options)


class BootInterlockTests(unittest.TestCase):
    def test_cold_primed_start_has_certificate_before_any_ramp(self):
        r=runtime();out=r.observe(frame())
        self.assertTrue(out.diagnostics['startup_authorized'])
        self.assertTrue(out.diagnostics['envelope_feasible'])
        self.assertGreaterEqual(out.diagnostics['startup_margin'],0.)
        self.assertLessEqual(out.decision.command,.15)
        r.acknowledge(observation_time=0.,applied_command=out.decision.command)

    def test_hot_start_rejected_without_command_or_committed_state(self):
        r=runtime()
        with self.assertRaises(StartupRejected) as caught:r.observe(frame(flow=4.32))
        self.assertEqual(caught.exception.reason,'held_zero_stop_infeasible')
        self.assertFalse(r.startup_authorized);self.assertIsNone(r.pending);self.assertIsNone(r.last_time)
        self.assertEqual(r.controller.previous,0.)

    def test_unprimed_start_rejected(self):
        with self.assertRaises(StartupRejected):runtime().observe(frame(volume=.35))

    def test_no_contract_rejected_instead_of_counted_as_safe_run(self):
        with self.assertRaises(StartupRejected) as caught:runtime({'inline_error_L':None,'anchor_error_L':None}).observe(frame())
        self.assertEqual(caught.exception.reason,'no_bounded_level_source')

    def test_invalid_frame_does_not_authorize(self):
        r=runtime()
        with self.assertRaises(ValueError):r.observe(frame(time=1.))
        self.assertFalse(r.startup_authorized)

    def test_higher_applied_command_is_recorded_and_latches_violation(self):
        r=runtime();out=r.observe(frame())
        with self.assertRaises(ActuationContractViolation):r.acknowledge(observation_time=0.,applied_command=out.decision.command+.01)
        self.assertIsNone(r.pending);self.assertTrue(r.actuation_fault)
        with self.assertRaises(ActuationContractViolation):r.observe(frame(time=1.))
