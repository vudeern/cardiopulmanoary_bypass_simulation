import math
import unittest
from dataclasses import replace
import numpy as np
from perfusion_candidates.finite_return import finite_return_reserve, FiniteReturnRuntime
from perfusion_lab.depletion import DepletionRuntime
from perfusion_lab.reachability import joint_braking_reserve
from perfusion_lab.runtime import MeasurementFrame
from perfusion_lab.sensing import Observation


class FiniteReturnTests(unittest.TestCase):
    def test_reserve_matches_independent_stepwise_finite_return(self):
        rng = np.random.default_rng(4721)
        for dt in (.5, 1., 2.):
            for _ in range(40):
                tau, initial, command, qin = rng.uniform(.5, 15), rng.uniform(0, 7), rng.uniform(0, 7), rng.uniform(0, 7)
                horizon = rng.uniform(0, 120)
                flow = initial; total = peak = 0.
                for k in range(2000):
                    u = max(0., command-.15*dt*k)
                    nxt = u+(flow-u)*math.exp(-dt/tau)
                    inflow = qin if k < math.floor(horizon/dt) else 0.
                    total += ((flow+nxt)/2.-inflow)*dt/60.
                    peak = max(peak, total); flow = nxt
                self.assertAlmostEqual(finite_return_reserve([(tau, initial)], command, qin, horizon, dt), peak, places=9)

    def test_zero_credit_recovers_rc3_and_more_credit_never_increases_reserve(self):
        models = [(1., 3.), (12., 5.)]
        for u in (0., 2., 7.):
            zero = joint_braking_reserve(models, u, 0.)
            self.assertAlmostEqual(finite_return_reserve(models, u, 4., 0.), zero)
            self.assertAlmostEqual(finite_return_reserve(models, u, 0., 60.), zero)
            values = [finite_return_reserve(models, u, 2., h) for h in (0., 15., 30., 60.)]
            self.assertEqual(values, sorted(values, reverse=True))

    def test_no_calibration_keeps_identical_braking_fallback(self):
        old = DepletionRuntime(bsa=1.85, initial_hb=9.)
        new = FiniteReturnRuntime(bsa=1.85, initial_hb=9.)
        for t in range(80):
            obs = Observation(t, 4.44, .85, 60., 9., .98, 37., None)
            frame = MeasurementFrame(obs, 4.44)
            a, b = old.observe(frame), new.observe(frame)
            self.assertEqual(a.decision, b.decision)
            self.assertTrue(b.diagnostics['protection_unsupported'])
            for runtime, result in ((old, a), (new, b)):
                runtime.acknowledge(observation_time=t, applied_command=result.decision.command)

    def test_zero_credit_reproduces_supported_rc3_simulation(self):
        from perfusion_candidates.simulation import simulate_finite_return
        from perfusion_lab.depletion_simulation import simulate_depletion
        args = dict(duration=180., dt=1., venous_measurement={},
                    calibration_options=dict(period=60., delay=6.))
        expected = simulate_depletion(**args)
        actual = simulate_finite_return(**args, controller_options={'return_fraction': 0.})
        self.assertEqual(expected['metrics'], actual['metrics'])
        for old, new in zip(expected['rows'], actual['rows']):
            for key in ('command', 'reservoir', 'flow', 'do2', 'braking_volume'):
                self.assertEqual(old[key], new[key])

    def test_invalid_assumptions_rejected(self):
        for options in ({'return_fraction': -.1}, {'return_fraction': float('nan')}, {'return_horizon_s': -1.}, {'return_horizon_s': 121.}):
            with self.assertRaises(ValueError):
                FiniteReturnRuntime(bsa=1.85, initial_hb=9., controller_options=options)
        for h in (-1., float('nan')):
            with self.assertRaises(ValueError):
                finite_return_reserve([(2., 3.)], 2., 1., h)


if __name__ == '__main__':
    unittest.main()
