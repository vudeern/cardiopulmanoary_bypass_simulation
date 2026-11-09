import unittest
from dataclasses import replace
from perfusion_lab.runtime import ControllerRuntime, MeasurementFrame
from perfusion_lab.sensing import Observation
from perfusion_lab.reference import LevelSample


class RuntimeTests(unittest.TestCase):
    def frame(self, time=0., **changes):
        obs = Observation(time, 4.44, .85, 60., 9., .98, 37., 9.)
        return replace(MeasurementFrame(obs, 4.44), **changes)

    def runtime(self):
        return ControllerRuntime(bsa=1.85, initial_hb=9.)

    def test_invalid_packets_are_rejected_without_consuming_a_frame(self):
        for invalid in (
            self.frame(1.), self.frame(venous_flow=float('nan')),
            self.frame(calibrations=(LevelSample(0., 1., .85),)),
            self.frame(calibrations=(LevelSample(.5, .5, .85),)),
            self.frame(calibrations=(LevelSample(0., 0., .85),)*2),
            self.frame(observation=replace(self.frame().observation, hb_inline=float('inf'))),
        ):
            with self.subTest(invalid=invalid):
                runtime = self.runtime()
                with self.assertRaises(ValueError): runtime.observe(invalid)
                self.assertEqual(runtime.observe(self.frame()), self.runtime().observe(self.frame()))

    def test_acknowledgement_is_required_and_tracks_actual_setpoint(self):
        runtime = self.runtime()
        output = runtime.observe(self.frame())
        with self.assertRaises(ValueError): runtime.observe(self.frame(1.))
        with self.assertRaises(ValueError): runtime.acknowledge(observation_time=1., applied_command=4.)
        with self.assertRaises(ValueError): runtime.acknowledge(observation_time=0., applied_command=float('nan'))
        runtime.acknowledge(observation_time=0., applied_command=3.)
        self.assertEqual(runtime.controller.previous, 3.)
        self.assertEqual(runtime.controller.pi.previous, 3.)
        # Pump model uses the acknowledged command, not the request.
        import math
        self.assertAlmostEqual(runtime.guard.flow, 3.+1.44*math.exp(-.5))
        next_output = runtime.observe(self.frame(1.))
        self.assertLessEqual(abs(next_output.decision.command-3.), .15+1e-9)
        self.assertEqual(output.valid_until, 1.)

    def test_status_and_log_mutation_do_not_change_internal_state(self):
        runtime = self.runtime()
        output = runtime.observe(self.frame())
        self.assertIn('model_recovery_unsupported', output.status)
        output.reference['supported'] = True
        output.reference['pump_models'].append((1., 100.))
        self.assertFalse(runtime.controller.reference_state['supported'])
        self.assertEqual(runtime.controller.reference_state['pump_models'], [])

    def test_skipped_or_duplicate_time_is_rejected_and_recoverable(self):
        runtime = self.runtime()
        runtime.observe(self.frame())
        runtime.acknowledge(observation_time=0., applied_command=4.44)
        for t in (0., 2.):
            with self.assertRaises(ValueError): runtime.observe(self.frame(t))
        self.assertEqual(runtime.observe(self.frame(1.)).observation_time, 1.)

    def test_simulation_adapter_exactly_matches_frozen_v114(self):
        from perfusion_lab.model_simulation import simulate_model
        from perfusion_lab.runtime_simulation import simulate_runtime
        from perfusion_lab.stress import StressScenario
        for kind in ('integrity_hybrid', 'integrity_pi'):
            for dt in (1., 2.):
                for mode in ('screened', 'calibration_only'):
                    with self.subTest(kind=kind, dt=dt, mode=mode):
                        args = dict(duration=180., dt=dt, seed=41000,
                            controller_kind=kind, level_mode=mode,
                            venous_measurement=dict(bias=.75),
                            plant_options=dict(actuator_tau=9.),
                            calibration_options=dict(period=60., delay=6.),
                            reference_fault_options=dict(fault_bias=.22),
                            controller_options=dict(recovery_floor=.45))
                        scenario = StressScenario('combined', drainage=.3, reservoir_bias=.6)
                        self.assertEqual(simulate_model(scenario, **args), simulate_runtime(scenario, **args))


if __name__ == '__main__': unittest.main()
