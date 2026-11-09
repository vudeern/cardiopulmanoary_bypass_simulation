import math
import unittest
from dataclasses import replace
from perfusion_lab.simc import integrating_settings,PICore,MatchedSupervisor
from perfusion_lab.sensing import Observation,Belief
from perfusion_lab.simulation import simulate


class SIMCTests(unittest.TestCase):
    def test_published_normalized_settings_and_signed_units(self):
        p=integrating_settings(1.,1.,1.)
        self.assertEqual((p.kc,p.tau_i,p.ki),(.5,8.,.0625))
        v=integrating_settings(-1/60,1.5,20.)
        self.assertAlmostEqual(v.kc,-60/21.5)
        self.assertEqual(v.tau_i,86.)
        self.assertLess(v.kc,0.)

    def test_negative_process_gain_has_correct_action(self):
        core=PICore(integrating_settings(-1/60,1.5,20.),1.,4.5)
        self.assertGreater(core.update(.65,.85),4.5)
        core=PICore(integrating_settings(-1/60,1.5,20.),1.,4.5)
        self.assertLess(core.update(.65,.45),4.5)

    def test_invalid_source_inputs_rejected(self):
        for args in ((0.,1.,1.),(1.,-1.,1.),(1.,1.,0.),(math.nan,1.,1.)):
            with self.assertRaises(ValueError):integrating_settings(*args)
        core=PICore(integrating_settings(1,1,1),1)
        with self.assertRaises(ValueError):core.update(1,math.inf)
        with self.assertRaises(ValueError):core.track(math.nan)

    def test_antiwindup_tracks_applied_output(self):
        core=PICore(integrating_settings(1.,0.,1.),1.,3.)
        self.assertEqual(core.update(1.,0.),4.25)
        core.track(2.)
        self.assertEqual(core.bias+core.settings.kc*core.error+core.integral,2.)
        previous=core.integral
        raw=core.update(1.,0.);core.track(raw)
        self.assertAlmostEqual(core.integral,previous+.25)

    def test_shared_pressure_and_actuator_constraints(self):
        obs=Observation(0.,4.5,.85,100.,9.4,.98,37.,9.4)
        belief=Belief(9.4,9.1,9.7,4.5,False,False,0.)
        decisions=[]
        for kind in ('simc','forecast'):
            controller=MatchedSupervisor(kind,1.85,1.)
            d=controller.decide(obs,belief);decisions.append(d.command)
            self.assertAlmostEqual(d.command,2.4*1.85-.15)
        self.assertEqual(decisions[0],decisions[1])

    def test_design_gains_frozen_during_timestep_sensitivity(self):
        a=MatchedSupervisor('simc',1.85,1.)
        b=MatchedSupervisor('simc',1.85,.5)
        self.assertEqual(a.core.settings,b.core.settings)

    def test_PI_physical_trajectory_ignores_flow_sensor_bias(self):
        # Identical truth and random draws; only an unused venous sensor changes.
        kw=dict(scenario='compound',seed=16000,duration=60.,dt=1.,controller_kind='simc')
        a=simulate(**kw,venous_measurement={'noise_sd':.015,'bias':0.})
        b=simulate(**kw,venous_measurement={'noise_sd':.015,'bias':.6})
        self.assertNotEqual(a['rows'][0]['observed_venous_flow'],b['rows'][0]['observed_venous_flow'])
        for x,y in zip(a['rows'],b['rows']):
            for key in ('reservoir','flow','pressure','command','do2'):
                self.assertEqual(x[key],y[key])

    def test_normalized_published_margins_and_time_domain(self):
        from examples.verify_simc import verification
        result=verification()
        self.assertTrue(all(result['published_checks'].values()))
        self.assertLess(result['time_domain_max_errors']['0.005'],.005)


if __name__=='__main__':unittest.main()
