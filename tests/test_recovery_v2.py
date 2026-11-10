import unittest
from perfusion_research.recovery_v2 import ReturnPhase


class RecoveryPhaseTests(unittest.TestCase):
    def test_no_adaptation_without_two_supported_anchors(self):
        detector=ReturnPhase()
        for t in range(40):self.assertEqual(detector.update(t,4.,True,1),'warming')
        self.assertEqual(len(detector.history),0)

    def test_detects_drop_then_recovery_from_measurements(self):
        detector=ReturnPhase()
        for t in range(21):detector.update(t,4.,True,2)
        self.assertEqual(detector.phase,'normal')
        detector.update(21,1.,True,2)
        self.assertEqual(detector.update(22,1.,True,2),'interrupted')
        detector.update(23,4.,True,2)
        self.assertEqual(detector.update(24,4.,True,2),'recovering')
        self.assertEqual(detector.update(53,4.,True,2),'recovering')
        self.assertEqual(detector.update(54,4.,True,2),'warming')

    def test_isolated_low_sample_does_not_trigger(self):
        detector=ReturnPhase()
        for t in range(21):detector.update(t,4.,True,2)
        detector.update(21,1.,True,2);detector.update(22,4.,True,2)
        self.assertEqual(detector.phase,'normal')
