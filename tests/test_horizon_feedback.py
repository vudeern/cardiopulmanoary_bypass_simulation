import unittest
from unittest.mock import patch
from perfusion_lab.sensing import Observation,Belief
from perfusion_research.feedback import FeedbackController,first_action_plan
from perfusion_research.bottleneck import TracedController


def fixture(controller,level=.8,supported=True):
    controller.previous=controller.pi.previous=1.;controller.nominal_flow=1.
    controller.set_reference_state(dict(bank_supported=supported,pump_models=[(2.,1.)],
        venous_bias_upper=.1,estimate=1.,lower=level))
    obs=Observation(0.,1.,level,14.,9.4,.98,37.,9.4)
    belief=Belief(9.4,9.,10.,3.,False,False,0.)
    return obs,belief


class FeedbackTests(unittest.TestCase):
    def test_planner_executes_bounded_first_action(self):
        r=first_action_plan([1.4,1.,14.],1.,1.,60.,100.,.85,1.1)
        self.assertTrue(r['accepted'],r);self.assertLessEqual(r['command'],1.1+1e-8)

    def test_shared_cap_matches_frozen_rc5_cap(self):
        for level in (.3,.8,1.2):
            for supported in (False,True):
                old=TracedController('pi',1.85);new=FeedbackController('pi',1.85)
                a,b=fixture(old,level,supported);c,d=fixture(new,level,supported)
                old.decide(a,b);new.decide(c,d)
                self.assertEqual(old.last_debug['decision_cap'],new.last_debug['decision_cap'])
                self.assertEqual(old.last_debug['predictive_feasible'],new.last_debug['predictive_feasible'])

    def test_rejected_solver_falls_back_to_same_point_pi(self):
        pi=FeedbackController('pi',1.85,feedback_mode='pi');mpc=FeedbackController('pi',1.85,feedback_mode='mpc')
        a,b=fixture(pi);c,d=fixture(mpc)
        expected=pi.decide(a,b)
        with patch('perfusion_research.feedback.first_action_plan',return_value=dict(accepted=False,status='timeout',elapsed_s=1.1,command=None)):
            actual=mpc.decide(c,d)
        self.assertEqual(expected.command,actual.command)
        self.assertEqual(mpc.last_debug['mpc_status'],'timeout')
        self.assertFalse(mpc.last_debug['mpc_accepted'])

    def test_accepted_proposal_is_applied_and_shielded(self):
        mpc=FeedbackController('pi',1.85,feedback_mode='mpc');obs,belief=fixture(mpc)
        with patch('perfusion_research.feedback.first_action_plan',return_value=dict(accepted=True,status='solved',elapsed_s=.01,command=7.)):
            result=mpc.decide(obs,belief)
        self.assertEqual(result.command,mpc.last_debug['decision_cap'])
        self.assertTrue(mpc.last_debug['shield_clip'])
        self.assertTrue(mpc.last_debug['applied_within_shared_cap'])
        self.assertEqual(mpc.previous,result.command)
        self.assertEqual(mpc.pi.previous,result.command)

    def test_unsupported_calibration_does_not_call_optimizer(self):
        mpc=FeedbackController('pi',1.85,feedback_mode='mpc');obs,belief=fixture(mpc,supported=False)
        with patch('perfusion_research.feedback.first_action_plan') as solve:mpc.decide(obs,belief)
        solve.assert_not_called();self.assertEqual(mpc.last_debug['mpc_status'],'unsupported_or_infeasible_reserve')

    def test_nonfinite_prediction_returns_no_action(self):
        r=first_action_plan([1.,1.,float('nan')],1.,1.,60.,100.,.85,1.1)
        self.assertFalse(r['accepted']);self.assertIsNone(r['command'])
