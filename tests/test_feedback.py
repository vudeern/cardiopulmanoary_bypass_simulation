"""Flow-bias invariance and actuator constraints of stronger simple baselines."""
from dataclasses import replace
import unittest
from perfusion_lab.feedback import LevelFeedback
from perfusion_lab.sensing import Observation,Twin
from perfusion_lab.stress import StressScenario
from perfusion_lab.simulation import simulate


class FeedbackTests(unittest.TestCase):
    def test_controller_command_is_invariant_to_measured_flow(self):
        obs=Observation(0.,4.5,.7,70.,9.,.98,35.,None)
        belief=Twin(9.).update(obs)
        for kind in ('pi','threshold'):
            a,b=LevelFeedback(kind,1.85),LevelFeedback(kind,1.85)
            for i in range(30):
                left=replace(obs,time=i*2.,reservoir=.8-i*.01)
                right=replace(left,flow=left.flow+2.)
                self.assertEqual(a.decide(left,belief),b.decide(right,belief))

    def test_closed_loop_truth_is_invariant_to_flow_bias(self):
        for kind in ('pi','threshold'):
            options=dict(controller_kind=kind,level_mode='hold',level_reference_options={})
            a=simulate(StressScenario('zero',drainage=.4),seed=17,duration=120.,**options)
            b=simulate(StressScenario('biased',drainage=.4,flow_bias=.9),seed=17,duration=120.,**options)
            for left,right in zip(a['rows'],b['rows']):
                for key in ('command','flow','reservoir','pressure','do2'):
                    self.assertEqual(left[key],right[key],(kind,key))

    def test_common_slew_and_flow_limits(self):
        for kind in ('pi','threshold'):
            r=simulate('compound',seed=17,duration=120.,controller_kind=kind)
            commands=[2.4*r['patient']['bsa']]+[row['command'] for row in r['rows']]
            self.assertTrue(all(0<=q<=7 for q in commands))
            self.assertTrue(all(abs(b-a)<=.3+1e-9 for a,b in zip(commands,commands[1:])))

    def test_pressure_slowdown_uses_direct_pressure(self):
        obs=Observation(0.,4.5,1.2,96.,9.,.98,35.,None)
        belief=Twin(9.).update(obs)
        for kind in ('pi','threshold'):
            result=LevelFeedback(kind,1.85).decide(obs,belief)
            self.assertAlmostEqual(result.command,2.4*1.85-.3)

    def test_invalid_kind_and_parameters(self):
        for kind,options in [('unknown',{}),('pi',{'kp':0.}),('threshold',{'threshold':float('nan')})]:
            with self.assertRaises(ValueError):LevelFeedback(kind,1.85,**options)

if __name__=='__main__':unittest.main()
