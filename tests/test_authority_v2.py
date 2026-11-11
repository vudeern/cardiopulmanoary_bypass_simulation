from dataclasses import replace
import unittest
from perfusion_research.authority_v2 import AuthorityRuntime
from perfusion_research.boot_v2 import StartupRejected, ActuationContractViolation
from test_boot_v2 import frame


class IndependentAuthorityTests(unittest.TestCase):
    def runtime(self, joint=False, budget=None):
        options = dict(return_horizon_s=0., joint_enabled=joint)
        if budget is not None: options['envelope_budget'] = budget
        return AuthorityRuntime(bsa=1.8, initial_hb=10., controller_options=options)

    def test_missing_calibration_allows_delivery_with_equal_pi_authority(self):
        arms = [self.runtime(joint) for joint in (False, True)]
        commands = [[], []]
        for time in range(30):
            for i, runtime in enumerate(arms):
                out = runtime.observe(frame(volume=1.4, time=float(time)))
                self.assertFalse(out.reference['bank_supported'])
                self.assertTrue(out.diagnostics['independent_authority'])
                self.assertGreaterEqual(out.diagnostics['envelope_margin'], 0.)
                self.assertLessEqual(out.decision.command, out.diagnostics['envelope_cap'])
                commands[i].append(out.decision.command)
                runtime.acknowledge(observation_time=float(time), applied_command=out.decision.command)
        self.assertGreater(max(commands[0]), .15)
        self.assertEqual(commands[0], commands[1])

    def test_pressure_slowdown_still_brakes(self):
        runtime = self.runtime()
        for time in range(10):
            out = runtime.observe(frame(volume=1.4, time=float(time)))
            runtime.acknowledge(observation_time=float(time), applied_command=out.decision.command)
        previous = out.decision.command
        measurement = frame(volume=1.4, time=10.)
        out = runtime.observe(replace(measurement, observation=replace(measurement.observation, pressure=100.)))
        self.assertAlmostEqual(out.decision.command, max(0., previous-.15))

    def test_no_contract_and_hot_start_still_rejected(self):
        with self.assertRaises(StartupRejected):
            self.runtime(budget=dict(inline_error_L=None, anchor_error_L=None)).observe(frame())
        with self.assertRaises(StartupRejected): self.runtime().observe(frame(flow=4.32))

    def test_higher_applied_command_still_latches_fault(self):
        runtime = self.runtime()
        out = runtime.observe(frame())
        with self.assertRaises(ActuationContractViolation):
            runtime.acknowledge(observation_time=0., applied_command=out.decision.command+.01)
        with self.assertRaises(ActuationContractViolation): runtime.observe(frame(time=1.))
