import importlib.util
import unittest
from unittest.mock import patch
import numpy as np
from perfusion_research.horizon import formulate,tail_factor,HorizonSolver,validate_plan
from perfusion_lab.model import Patient
from perfusion_lab.stress import StressPlant


def problem(**options):
    return formulate([1.4,1.,14.],1.,np.ones(8),np.full(8,60.),np.full(8,100.),**options)


class HorizonTests(unittest.TestCase):
    def test_tail_matches_long_discrete_simulation(self):
        for tau in (2.,6.,12.):
            q=4.;total=0.
            for _ in range(2000):
                new=q*np.exp(-1/tau);total+=(q+new)/120.;q=new
            self.assertAlmostEqual(total,4.*tail_factor(1.,tau),places=11)

    def test_stable_tail_and_invalid_inputs(self):
        self.assertAlmostEqual(tail_factor(1e-12,2.),2./60.,places=12)
        for dt,tau in ((0,2),(1,-1),(1,float('nan')),(1e-300,1e300)):
            with self.assertRaises(ValueError):tail_factor(dt,tau)

    def test_rollout_matches_actual_plant_first_step(self):
        patient=Patient();plant=StressPlant(patient)
        plant.reservoir=1.4;plant.flow=1.;plant.pressure=14.
        r=plant.venous_return(1.)
        p=formulate([1.4,1.,14.],1.,np.full(8,r),np.full(8,60.),np.full(8,100.))
        result=HorizonSolver().solve(p);self.assertTrue(result['accepted'],result)
        actual=plant.step(result['command'],1.,1.)
        states=np.array(result['vector'][:p.command_start]).reshape(-1,3)
        np.testing.assert_allclose(states[1],[actual['reservoir'],plant.flow,actual['pressure']],atol=1e-8)

    def test_backup_has_normal_slew_zero_command_and_reserve(self):
        p=problem();result=HorizonSolver().solve(p);self.assertTrue(result['accepted'])
        x=np.array(result['vector']);u=x[p.command_start:p.deficit_start];states=x[:p.command_start].reshape(-1,3)
        self.assertLessEqual(np.max(np.abs(np.diff(np.r_[p.previous,u]))),p.slew*p.dt+1e-8)
        self.assertAlmostEqual(u[-1],0.,places=8)
        self.assertGreaterEqual(states[-1,0]-tail_factor(p.dt,p.tau)*states[-1,1],p.floor-1e-8)

    def test_infeasible_state_returns_no_action(self):
        p=formulate([.1,5.,70.],5.,np.zeros(8),np.full(8,60.),np.full(8,280.))
        r=HorizonSolver().solve(p);self.assertFalse(r['accepted']);self.assertIsNone(r['command'])

    def test_corrupt_solution_and_terminal_ceiling_rejected(self):
        p=problem();r=HorizonSolver().solve(p);x=np.array(r['vector'])
        x[3*p.steps]=p.ceiling+.1
        self.assertFalse(validate_plan(p,x)['valid'])
        x[0]=float('nan');self.assertFalse(validate_plan(p,x)['valid'])

    def test_exception_and_deadline_reject_action(self):
        with patch('perfusion_research.horizon.linprog',side_effect=RuntimeError('test')):
            self.assertIsNone(HorizonSolver().solve(problem())['command'])
        self.assertFalse(HorizonSolver(deadline_s=1e-9).solve(problem())['accepted'])

    @unittest.skipUnless(importlib.util.find_spec('osqp'),'OSQP optional extra unavailable locally')
    def test_osqp_matches_independent_lp_and_updates_workspace(self):
        solver=HorizonSolver('osqp',deadline_s=5.)
        for returns in (1.,1.1):
            p=formulate([1.4,1.,14.],1.,np.full(8,returns),np.full(8,60.),np.full(8,100.))
            reference=HorizonSolver().solve(p);result=solver.solve(p)
            self.assertTrue(result['accepted'],result)
            self.assertAlmostEqual(result['checks']['objective'],reference['checks']['objective'],places=5)
            workspace=solver.workspace
            result=solver.solve(p);self.assertTrue(result['accepted']);self.assertIs(solver.workspace,workspace)
