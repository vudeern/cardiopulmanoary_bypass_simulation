"""V2 recovery-aware request policy behind the unchanged independent v1 cap.

The detector is causal and uses the same measured return stream in every arm.
No event timing enters the controller. Detection does not certify a true fault.
"""
from collections import deque
import math
import statistics
from perfusion_candidates.calibrated_pump import CalibratedPumpRuntime
from perfusion_candidates.finite_return import finite_return_reserve
from perfusion_lab.control import Decision
from perfusion_lab.model import delivery
from .feedback import FeedbackController


class ReturnPhase:
    def __init__(self):
        self.history=deque(maxlen=20);self.phase='warming';self.low_count=0;self.high_count=0
        self.baseline=None;self.until=None

    def update(self,time,flow,supported,anchors):
        if not supported or anchors<2:
            self.history.clear();self.phase='warming';self.low_count=self.high_count=0
            return self.phase
        if self.phase in ('warming','normal'):
            if len(self.history)<20:
                self.history.append(flow);self.phase='warming';return self.phase
            baseline=statistics.median(self.history)
            low=baseline>.5 and flow<.65*baseline
            self.low_count=self.low_count+1 if low else 0
            if self.low_count>=2:
                self.baseline=baseline;self.phase='interrupted';self.high_count=0
            else:
                if not low:self.history.append(flow)
                self.phase='normal'
        elif self.phase=='interrupted':
            self.high_count=self.high_count+1 if flow>.8*self.baseline else 0
            if self.high_count>=2:self.phase='recovering';self.until=time+30.
        elif self.phase=='recovering' and time>=self.until:
            self.history.clear();self.history.append(flow);self.phase='warming';self.low_count=self.high_count=0
        return self.phase


class RecoveryController(FeedbackController):
    def __init__(self,*args,recovery_enabled=False,**options):
        super().__init__(*args,feedback_mode='pi',**options)
        self.recovery_enabled=bool(recovery_enabled);self.return_phase=ReturnPhase()

    def decide(self,obs,belief):
        previous=self.previous;flow=self.nominal_flow
        baseline=super().decide(obs,belief)
        phase=self.return_phase.update(obs.time,belief.venous_flow,
            self.reference_state['bank_supported'],self.reference_state['calibration_count'])
        applied=baseline.command
        if self.recovery_enabled and phase=='recovering' and self.last_debug['predictive_feasible']:
            applied=max(applied,min(self.last_debug['decision_cap'],self.last_debug['decision_high']))
        self.pi.core.track(applied);self.pi.previous=self.previous=applied
        self.nominal_flow=applied+(flow-applied)*math.exp(-self.dt/2.)
        self.last_debug.update(recovery_phase=phase,recovery_enabled=self.recovery_enabled,
            recovery_action_changed=abs(applied-baseline.command)>1e-6,
            applied_within_shared_cap=applied<=self.last_debug['decision_cap']+1e-7,
            braking_volume=finite_return_reserve(self.reference_state.get('pump_models',()),applied,
                self.last_debug['protection_inflow_floor'],self.return_horizon_s,self.dt))
        return Decision(float(applied),baseline.infeasible,delivery(applied,belief.hb_lower,obs.sao2,self.bsa))


class RecoveryRuntime(CalibratedPumpRuntime):
    def __init__(self,*,bsa,initial_hb,dt=1.,target=280.,kind='pi',level_mode='screened',controller_options=None,guard_options=None):
        options=dict(controller_options or {});enabled=options.pop('recovery_enabled',False)
        if kind!='pi':raise ValueError('Recovery comparison uses matched PI settings')
        super().__init__(bsa=bsa,initial_hb=initial_hb,dt=dt,target=target,kind=kind,level_mode=level_mode,
            controller_options=options,guard_options=guard_options)
        self.controller=RecoveryController(kind,bsa,dt,target,recovery_enabled=enabled,**options)
