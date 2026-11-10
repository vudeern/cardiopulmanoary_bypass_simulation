"""V2 joint hypothesis cap: preserve pump/volume association, not new information.

Conditional on the existing calibration/model and finite-return assumptions.
No covariance confidence, future event schedule or hidden state enters the cap.
"""
from math import exp
from perfusion_candidates.startup import StartupGuard
from perfusion_candidates.calibrated_pump import CalibratedPumpRuntime
from perfusion_candidates.finite_return import finite_return_reserve
from perfusion_lab.control import Decision
from perfusion_lab.model import delivery
from .feedback import FeedbackController


class JointGuard(StartupGuard):
    def update(self,obs,routine,calibrations):
        state=super().update(obs,routine,calibrations)
        hypotheses=[]
        if state['bank_supported']:
            age=(obs.time-self.samples[-1][0])/60.
            for model,vertices in self.polygons:
                values=[self.mass[model]+offset-bias*age for offset,bias in vertices]
                hypotheses.append(dict(tau=float(self.taus[model]),flow=float(self.flows[model]),
                    lower=max(0.,min(values)-self.model_error*age),
                    bias_upper=max(bias for _,bias in vertices)+self.model_error))
        state['joint_hypotheses']=hypotheses
        return state


def hypothesis_margin(hypotheses,command,measured_return,allowance,fraction,horizon,dt):
    """Worst model-specific remaining volume above unchanged .29 L reserve floor."""
    if not hypotheses:return float('-inf')
    return min(h['lower']-.29-finite_return_reserve([(h['tau'],h['flow'])],command,
        fraction*max(0.,measured_return-h['bias_upper']-allowance),horizon,dt) for h in hypotheses)


def joint_cap(hypotheses,low,high,measured_return,allowance,fraction,horizon,dt):
    margin=lambda u:hypothesis_margin(hypotheses,u,measured_return,allowance,fraction,horizon,dt)
    if margin(low)<0:return low,False
    if margin(high)>=0:return high,True
    left,right=low,high
    for _ in range(18):
        mid=(left+right)/2.
        if margin(mid)>=0:left=mid
        else:right=mid
    return left,True


class JointController(FeedbackController):
    def __init__(self,*args,joint_enabled=False,**options):
        super().__init__(*args,feedback_mode='pi',**options);self.joint_enabled=joint_enabled

    def decide(self,obs,belief):
        flow=self.nominal_flow;previous=self.previous
        baseline=super().decide(obs,belief)
        state=self.reference_state;h=state.get('joint_hypotheses',())
        # The original first action has already tracked the PI integrator. The
        # uncapped nominal request is captured by the wrapper below before that
        # tracking; never call PI twice or invent an action above its request.
        low=max(0.,previous-.15*self.dt)
        cap,feasible=joint_cap(h,low,self.last_debug['decision_high'],belief.venous_flow,
            self.allowance,self.return_fraction,self.return_horizon_s,self.dt)
        valid=bool(state['bank_supported'] and len(h)==len(state.get('pump_models',())))
        if not valid:cap=self.last_debug['decision_cap'];feasible=self.last_debug['predictive_feasible']
        applied=baseline.command
        if self.joint_enabled and valid:
            applied=min(self.last_debug['decision_high'],max(low,min(self._nominal_request,cap)))
        chosen_cap=cap if self.joint_enabled else self.last_debug['decision_cap']
        self.pi.core.track(applied);self.pi.previous=self.previous=applied
        self.nominal_flow=applied+(flow-applied)*exp(-self.dt/2.)
        self.last_debug.update(joint_enabled=self.joint_enabled,joint_supported=valid,
            aggregate_cap=self.last_debug['decision_cap'],joint_cap=cap,decision_cap=chosen_cap,
            hypothesis_margin=hypothesis_margin(h,applied,belief.venous_flow,self.allowance,
                self.return_fraction,self.return_horizon_s,self.dt) if valid else None,
            predictive_feasible=feasible if self.joint_enabled else self.last_debug['predictive_feasible'],
            protection_active=applied<self._nominal_request-1e-9,
            joint_action_changed=abs(applied-baseline.command)>1e-6,
            applied_within_shared_cap=applied<=chosen_cap+1e-7)
        return Decision(applied,not feasible if self.joint_enabled else baseline.infeasible,
            delivery(applied,belief.hb_lower,obs.sao2,self.bsa))



class JointRuntime(CalibratedPumpRuntime):
    def __init__(self,*,bsa,initial_hb,dt=1.,target=280.,kind='pi',level_mode='screened',controller_options=None,guard_options=None):
        options=dict(controller_options or {});enabled=options.pop('joint_enabled',False)
        if kind!='pi':raise ValueError('Joint-cap comparison uses matched PI')
        super().__init__(bsa=bsa,initial_hb=initial_hb,dt=dt,target=target,kind=kind,
            level_mode=level_mode,controller_options=options,guard_options=guard_options)
        guard=dict(guard_options or {});minimum=guard.pop('startup_minimum_anchors',1)
        self.guard=JointGuard(2.4*bsa,dt,minimum_anchors=minimum,**guard)
        self.controller=JointController(kind,bsa,dt,target,joint_enabled=enabled,**options)
        original=self.controller.pi.decide
        def record_request(obs,belief):
            decision=original(obs,belief);self.controller._nominal_request=decision.command;return decision
        self.controller.pi.decide=record_request

