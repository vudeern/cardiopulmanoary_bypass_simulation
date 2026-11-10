"""Experimental simulated feedback behind the unchanged rc.5 command shield.

No device I/O. The nominal plan is not a safety certificate. Both PI and MPC
retain the existing conditional calibration/model/return assumptions and normal
slew authority. Invalid or late optimization falls back to the same shielded PI.
"""
from dataclasses import replace
import math
from time import perf_counter
import numpy as np
from scipy import sparse
from scipy.optimize import linprog
from perfusion_lab.control import Decision
from perfusion_lab.model import oxygen_content,delivery
from perfusion_candidates.finite_return import finite_return_reserve
from perfusion_candidates.calibrated_pump import CalibratedPumpRuntime
from .bottleneck import TracedController
from .horizon import formulate,HorizonSolver,validate_plan


def first_action_plan(initial,previous,returns,conversion,target,low,cap,dt=1.,deadline=1.):
    """Primary deficit optimum, then largest first command at the same optimum.

    The tie break makes the applied action well-defined without choosing among
    equivalent future sequences. It retains the primary LP optimum to 1e-8 AUC.
    Every accepted action passes original-unit plan validation and a full timer.
    """
    start=perf_counter()
    try:
        p=formulate(initial,previous,np.full(15,returns),np.full(15,conversion),np.full(15,target),dt=dt)
        row=sparse.csc_matrix(([1.],([0],[p.command_start])),shape=(1,len(p.cost)))
        p=replace(p,A=sparse.vstack([p.A,row],format='csc'),lower=np.r_[p.lower,low],upper=np.r_[p.upper,cap])
        primary=HorizonSolver(deadline_s=deadline).solve(p)
        if not primary['accepted']:return dict(accepted=False,status=primary['status'],elapsed_s=perf_counter()-start,command=None)
        objective=primary['checks']['objective']
        A=sparse.vstack([p.A,sparse.csc_matrix(p.cost.reshape(1,-1))],format='csc')
        lower=np.r_[p.lower,-np.inf];upper=np.r_[p.upper,objective+1e-8]
        equality=np.isfinite(lower)&(lower==upper);high=np.isfinite(upper)&~equality;bottom=np.isfinite(lower)&~equality
        cost=np.zeros(len(p.cost));cost[p.command_start]=-1.
        remaining=max(1e-6,deadline-(perf_counter()-start))
        secondary=linprog(cost,A_ub=sparse.vstack([A[high],-A[bottom]]),b_ub=np.r_[upper[high],-lower[bottom]],
            A_eq=A[equality],b_eq=lower[equality],bounds=[(None,None)]*len(cost),method='highs',options={'time_limit':remaining})
        checks=validate_plan(p,secondary.x) if secondary.success else dict(valid=False)
        elapsed=perf_counter()-start
        accepted=bool(secondary.success and checks['valid'] and checks['objective']<=objective+1e-7 and elapsed<=deadline)
        return dict(accepted=accepted,status='solved' if accepted else 'secondary_or_validation_rejected',
            elapsed_s=elapsed,command=float(secondary.x[p.command_start]) if accepted else None)
    except Exception as error:
        return dict(accepted=False,status=f'exception:{type(error).__name__}',elapsed_s=perf_counter()-start,command=None)


class FeedbackController(TracedController):
    def __init__(self,*args,feedback_mode='pi',**kwargs):
        if feedback_mode not in ('pi','mpc'):raise ValueError('Unknown feedback mode')
        super().__init__(*args,**kwargs)
        self.mode=feedback_mode

    def decide(self,obs,belief):
        previous=self.previous;nominal_flow=self.nominal_flow;state=self.reference_state
        # Point estimate feeds both nominal controllers; the independent lower
        # estimate continues to determine the identical protection cap.
        self.pi.previous=previous
        point_obs=replace(obs,reservoir=state['estimate'])
        nominal_pi=self.pi.decide(point_obs,belief)
        low=max(0.,previous-.15*self.dt);high=min(7.,previous+.15*self.dt)
        high=max(low,min(high,self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))))
        if obs.pressure>90.:high=low
        models=state.get('pump_models',())
        supported=bool(state['bank_supported'] and models)
        budget=max(0.,obs.reservoir-.29) if supported else 0.
        qin=self.return_fraction*max(0.,belief.venous_flow-state['venous_bias_upper']-self.allowance)
        loss=lambda u:finite_return_reserve(models,u,qin,self.return_horizon_s,self.dt)
        feasible=supported and obs.reservoir>=.29 and loss(low)<=budget
        cap=low
        if feasible:
            cap=high
            if loss(high)>budget:
                left,right=low,high
                for _ in range(18):
                    mid=(left+right)/2.
                    if loss(mid)<=budget:left=mid
                    else:right=mid
                cap=left
        protected_pi=min(high,max(low,min(nominal_pi.command,cap)))
        applied=protected_pi;fallback='pi_mode';accepted=False;elapsed=0.;proposal=None
        if self.mode=='mpc':
            if not feasible:fallback='unsupported_or_infeasible_reserve'
            else:
                conversion=10.*oxygen_content(belief.hb_lower,obs.sao2)/self.bsa
                plan=first_action_plan([state['estimate'],nominal_flow,obs.pressure],
                    previous,max(0.,belief.venous_flow),conversion,self.target,low,min(high,cap),self.dt)
                elapsed=plan['elapsed_s'];fallback=plan['status'];accepted=plan['accepted'];proposal=plan['command']
                if accepted:
                    applied=min(high,max(low,min(cap,proposal)));fallback='none'
        self.pi.core.track(applied);self.pi.previous=self.previous=applied
        self.nominal_flow=applied+(nominal_flow-applied)*math.exp(-self.dt/2.)
        self.last_debug=dict(control_level_lower=obs.reservoir,point_volume_start=state['estimate'],
            decision_cap=cap,decision_high=high,braking_budget=budget,braking_volume=loss(applied),
            predictive_feasible=feasible,protection_unsupported=not supported,
            protection_inflow_floor=qin,feedback_mode=self.mode,mpc_accepted=accepted,
            mpc_status=fallback,mpc_elapsed_s=elapsed,mpc_proposal=proposal,
            protected_pi_action=protected_pi,action_changed=abs(applied-protected_pi)>1e-6,
            shield_clip=bool(accepted and abs(applied-proposal)>1e-7),
            applied_within_shared_cap=applied<=min(high,cap)+1e-7,
            protection_active=applied<(proposal if accepted else nominal_pi.command)-1e-9)
        return Decision(float(applied),not feasible,delivery(applied,belief.hb_lower,obs.sao2,self.bsa))


class FeedbackRuntime(CalibratedPumpRuntime):
    def __init__(self,*,bsa,initial_hb,dt=1.,target=280.,kind='pi',level_mode='screened',controller_options=None,guard_options=None):
        options=dict(controller_options or {});mode=options.pop('feedback_mode','pi')
        if kind!='pi':raise ValueError('Feedback comparison uses matched PI settings')
        super().__init__(bsa=bsa,initial_hb=initial_hb,dt=dt,target=target,kind=kind,level_mode=level_mode,
            controller_options=options,guard_options=guard_options)
        self.controller=FeedbackController(kind,bsa,dt,target,feedback_mode=mode,**options)
