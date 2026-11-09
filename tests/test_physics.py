"""Independent invariants and analytic checks, not snapshots of implementation."""
import math
import unittest
from perfusion_lab.model import Patient, Plant, oxygen_content, delivery
from perfusion_lab.simulation import simulate


class PhysicsTests(unittest.TestCase):
    def test_oxygen_units_against_hand_calculation(self):
        # Hb=10, SaO2=1, PaO2=0 => 13.4 mL/dL. 5 L/min at 2 m²
        # is 50*13.4/2 = 335 mL/min/m²; dissolved O2 at 150 adds 11.625.
        self.assertAlmostEqual(oxygen_content(10, 1, 0), 13.4)
        self.assertAlmostEqual(delivery(5, 10, 1, 2), 346.625)

    def test_volume_conservation_under_aggressive_requests(self):
        p, plant = Patient(), Plant(Patient())
        for i in range(400):
            r = plant.step(7 if i%50<25 else 0, .1 if i%70<35 else 1, 2)
            self.assertGreaterEqual(r['reservoir'], 0)
            self.assertLessEqual(r['reservoir'], p.volume)
            self.assertAlmostEqual(r['reservoir']+r['patient_volume'], p.volume, places=12)

    def test_zero_input_pressure_decay(self):
        plant = Plant(Patient())
        plant.flow=0
        initial=plant.pressure
        r=plant.step(0,1,2)
        expected=initial*math.exp(-2/(plant.p.resistance*plant.p.compliance*60))
        self.assertAlmostEqual(r['pressure'], expected)

    def test_fixed_actuator_steady_state(self):
        plant=Plant(Patient())
        for _ in range(200):
            r=plant.step(4.5,1,2)
        self.assertAlmostEqual(r['flow'], 4.5)
        self.assertAlmostEqual(r['pressure'], 63., places=6)
        self.assertAlmostEqual(r['qv'], r['flow'], places=5)

    def test_invalid_inputs(self):
        for kw in ({'dt':0},{'dt':6},{'duration':7,'dt':2},{'target':float('nan')}):
            with self.assertRaises(ValueError):
                simulate(**kw)
        with self.assertRaises(ValueError):
            Patient(compliance=-1)

    def test_reproducible_and_finite(self):
        a=simulate(duration=120)
        self.assertEqual(a,simulate(duration=120))
        for value in a['metrics'].values():
            self.assertTrue(math.isfinite(value))

    def test_refinement_converges_fixed_policy(self):
        # Test nominal smooth forcing with sensor-independent fixed control.
        metrics=[simulate('nominal','fixed',42,120,dt)['metrics'] for dt in (2,1,.5)]
        self.assertAlmostEqual(metrics[0]['mean_flow'],metrics[2]['mean_flow'],places=10)
        self.assertLess(abs(metrics[1]['minimum_reservoir']-metrics[2]['minimum_reservoir']),
                        abs(metrics[0]['minimum_reservoir']-metrics[2]['minimum_reservoir']))
