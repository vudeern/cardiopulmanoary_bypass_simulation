import math
import unittest
import numpy as np
from perfusion_lab.reachability import ConsistentGuard,joint_braking_reserve
from perfusion_lab.model_bank import discrete_reserve
from perfusion_lab.reference import LevelSample
from perfusion_lab.sensing import Observation


class ReachabilityTests(unittest.TestCase):
    def test_signed_raw_reference_is_preserved_but_invalid_time_and_nan_rejected(self):
        from perfusion_lab.reachability_runtime import ReachabilityRuntime
        from perfusion_lab.runtime import MeasurementFrame
        from dataclasses import replace
        obs=Observation(0.,4.44,0.,60.,9.,.98,37.,None)
        frame=MeasurementFrame(obs,4.44,calibrations=(LevelSample(0.,0.,-.01),))
        runtime=ReachabilityRuntime(bsa=1.85,initial_hb=9.)
        for bad in (LevelSample(0.,0.,float('nan')),LevelSample(0.,1.,-.01)):
            with self.assertRaises(ValueError):runtime.observe(replace(frame,calibrations=(bad,)))
        result=runtime.observe(frame)
        self.assertEqual(runtime.guard.cal[1],-.01)
        self.assertEqual(result.reference['calibration_count'],1)

    def test_joint_reserve_matches_independent_stepwise_emergency(self):
        rng = np.random.default_rng(912)
        for dt in (.5,1.,2.):
            for _ in range(60):
                tau,flow,command,qin = rng.uniform(.5,15),rng.uniform(0,7),rng.uniform(0,7),rng.uniform(0,7)
                initial = rng.uniform(0,7)
                x=initial;loss=peak=0.
                for k in range(2500):
                    u=max(0.,command-.15*dt*k)
                    y=u+(x-u)*math.exp(-dt/tau)
                    loss+=((x+y)/2.-qin)*dt/60.;peak=max(peak,loss);x=y
                self.assertAlmostEqual(joint_braking_reserve([(tau,initial)],command,qin,dt),peak,places=9)

    def test_zero_inflow_tail_is_exact_and_model_max_is_conservative(self):
        models=[(2.,4.),(12.,5.)]
        actual=joint_braking_reserve(models,0.,0.)
        expected=max(discrete_reserve(flow,tau,0.,.15,1.) for tau,flow in models)
        self.assertAlmostEqual(actual,expected,places=10)
        self.assertEqual(joint_braking_reserve([(2.,1.)],0.,2.),0.)
        for u in np.linspace(0,7,40):
            self.assertGreaterEqual(joint_braking_reserve(models,float(u),3.),joint_braking_reserve(models,max(0.,float(u)-.01),3.)-1e-10)

    def test_joint_loss_does_not_exceed_separate_old_allowances(self):
        for tau in (1.,4.,12.):
            for flow in (0.,3.,7.):
                for command in (0.,2.,7.):
                    for qin in (0.,2.,5.):
                        old=discrete_reserve(max(0.,flow-qin),tau,max(0.,command-qin),.15,1.)
                        self.assertLessEqual(joint_braking_reserve([(tau,flow)],command,qin),old+1e-10)

    def test_consistent_set_contains_known_constant_bias_and_volume(self):
        guard=ConsistentGuard(4.44,calibration_error=.04,model_error_flow=.03)
        volume=.85;flow=4.44;queue=[]
        for t in range(361):
            if t%60==0:queue.append(LevelSample(t,t+6,volume+(.015 if t%120 else -.015)))
            samples=[s for s in queue if s.delivered==t]
            obs=Observation(t,flow,volume+.6*t/360.,60.,9.,.98,37.,None)
            state=guard.update(obs,[],samples)
            if t>=66:
                self.assertTrue(state['bank_supported'])
                self.assertLessEqual(state['lower'],volume+1e-9)
                self.assertGreaterEqual(state['estimate']+state['uncertainty'],volume-1e-9)
                self.assertGreaterEqual(state['venous_bias_upper'],.6)
            command=4.2+.3*math.sin(t/30.)
            guard.advance(command,4.8)
            nxt=command+(flow-command)*math.exp(-1/4.)
            volume+=(4.2-(flow+nxt)/2.)/60.;flow=nxt

    def test_impossible_anchors_lose_model_support(self):
        guard=ConsistentGuard(4.44)
        for t in range(61):
            obs=Observation(t,4.44,.85,60.,9.,.98,37.,None)
            samples=[LevelSample(t,t,.85 if t==0 else 20.)] if t in (0,60) else []
            state=guard.update(obs,[],samples);guard.advance(4.44,4.44)
        self.assertFalse(state['bank_supported'])
        self.assertEqual(state['active_models'],0)

    def test_legacy_modes_preserve_frozen_runtime_trajectory(self):
        from perfusion_lab.runtime_simulation import simulate_runtime
        from perfusion_lab.reachability_simulation import simulate_reachability
        args=dict(duration=180.,dt=1.,venous_measurement={},calibration_options=dict(period=60.,delay=6.))
        expected=simulate_runtime(**args)
        actual=simulate_reachability(**args,controller_options=dict(reserve_mode='legacy'),reference_guard_options=dict(interval_mode='legacy'))
        actual['controller_options']={}
        self.assertEqual(expected,actual)


if __name__=='__main__':unittest.main()
