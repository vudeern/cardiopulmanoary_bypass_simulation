"""Independent, explicitly conditional zero-return protection for simulation.

Budgets are configured assumptions, not inferred error coverage. No observer fit,
true volume, injected fault magnitude or future event enters this envelope.
"""
from dataclasses import dataclass,replace
import math
from perfusion_lab.control import Decision
from perfusion_lab.model import delivery
from .joint_v2 import JointRuntime


@dataclass(frozen=True)
class EnvelopeBudget:
    inline_error_L: float | None = .30
    anchor_error_L: float | None = .30
    tau_min_s: float = 1.
    tau_max_s: float = 20.
    initial_flow_error_lpm: float = .10
    max_anchor_age_s: float = 240.

    def __post_init__(self):
        values=(self.tau_min_s,self.tau_max_s,self.initial_flow_error_lpm,self.max_anchor_age_s)
        if not all(math.isfinite(x) for x in values) or not 0<self.tau_min_s<=self.tau_max_s or self.initial_flow_error_lpm<0 or self.max_anchor_age_s<=0:
            raise ValueError('Invalid pump/start/age bounds')
        if any(v is not None and (not math.isfinite(v) or v<0) for v in (self.inline_error_L,self.anchor_error_L)):
            raise ValueError('Channel errors must be nonnegative or explicitly unavailable')


def stopping_volume(command,flow_upper,tau_upper,dt=1.,slew=.15):
    """Exact worst total ramp-to-zero loss for fixed first-order tau <= upper.

    Sum of trapezoidal flow over the infinite stop equals the command sum plus
    the initial-flow tail. The tail coefficient increases with positive tau.
    This is not a bound for arbitrary time-varying lag or unmodelled actuators.
    """
    if not all(math.isfinite(v) for v in (command,flow_upper,tau_upper,dt,slew)) or min(command,flow_upper)<0 or min(tau_upper,dt,slew)<=0:
        raise ValueError('Invalid stop bound')
    decrement=slew*dt;n=math.ceil(command/decrement)
    command_sum=n*command-decrement*n*(n-1)/2.
    tail=dt*flow_upper/(120.*math.tanh(dt/(2.*tau_upper)))
    return command_sum*dt/60.+tail


class ProtectionEnvelope:
    def __init__(self,initial_flow,dt=1.,budget=None):
        self.budget=budget or EnvelopeBudget();self.dt=dt
        if not math.isfinite(initial_flow) or initial_flow<0 or not math.isfinite(dt) or dt<=0:raise ValueError('Invalid initial flow/timing')
        self.flow_lower=max(0.,initial_flow-self.budget.initial_flow_error_lpm)
        self.flow_upper=initial_flow+self.budget.initial_flow_error_lpm
        self.out_upper=0.;self.history={};self.anchors=[];self.lower=None;self.time=None

    def update(self,obs,calibrations):
        self.time=obs.time;self.history[round(obs.time,9)]=self.out_upper
        candidates=[]
        if self.budget.inline_error_L is not None:candidates.append(max(0.,obs.reservoir-self.budget.inline_error_L))
        self.anchors.extend(calibrations)
        self.anchors=[s for s in self.anchors if obs.time-s.acquired<=self.budget.max_anchor_age_s]
        if self.budget.anchor_error_L is not None:
            for s in self.anchors:
                acquired=round(s.acquired,9)
                if acquired not in self.history:raise ValueError('Anchor has no acquisition history')
                # Assume zero return over acquisition-to-now: only subtract a
                # command-derived upper outflow. Delayed measurements stay causal.
                candidates.append(max(0.,s.value-self.budget.anchor_error_L-(self.out_upper-self.history[acquired])))
        self.lower=max(candidates) if candidates else None
        return self.lower

    def advance(self,command):
        if not math.isfinite(command) or not 0<=command<=7:raise ValueError('Invalid applied command')
        a=(math.exp(-self.dt/self.budget.tau_min_s),math.exp(-self.dt/self.budget.tau_max_s))
        endpoints=[command+(q-command)*decay for q in (self.flow_lower,self.flow_upper) for decay in a]
        after_lower,after_upper=min(endpoints),max(endpoints)
        self.out_upper+=(self.flow_upper+after_upper)*self.dt/120.
        self.flow_lower,self.flow_upper=after_lower,after_upper

    def margin(self,command):
        if self.lower is None:return None
        return self.lower-.29-stopping_volume(command,self.flow_upper,self.budget.tau_max_s,self.dt)

    def cap(self,low,high):
        if self.lower is None or self.margin(low)<0:return low,False
        if self.margin(high)>=0:return high,True
        left,right=low,high
        for _ in range(18):
            mid=(left+right)/2.
            if self.margin(mid)>=0:left=mid
            else:right=mid
        return left,True


class EnvelopeRuntime(JointRuntime):
    def __init__(self,*,bsa,initial_hb,dt=1.,target=280.,kind='pi',level_mode='screened',controller_options=None,guard_options=None):
        options=dict(controller_options or {});budget=EnvelopeBudget(**options.pop('envelope_budget',{}))
        super().__init__(bsa=bsa,initial_hb=initial_hb,dt=dt,target=target,kind=kind,level_mode=level_mode,
            controller_options=options,guard_options=guard_options)
        self.envelope=ProtectionEnvelope(2.4*bsa,dt,budget);controller=self.controller;original=controller.decide
        def protected(obs,belief):
            previous=controller.previous;nominal_flow=controller.nominal_flow
            result=original(obs,belief);low=max(0.,previous-.15*dt)
            cap,feasible=self.envelope.cap(low,controller.last_debug['decision_high'])
            applied=max(low,min(result.command,cap))
            controller.pi.core.track(applied);controller.pi.previous=controller.previous=applied
            controller.nominal_flow=applied+(nominal_flow-applied)*math.exp(-dt/2.)
            controller.last_debug.update(legacy_command=result.command,legacy_cap=controller.last_debug['decision_cap'],
                envelope_cap=cap,decision_cap=min(cap,controller.last_debug['decision_cap']),
                envelope_lower=self.envelope.lower,envelope_flow_upper=self.envelope.flow_upper,
                envelope_contract_available=self.envelope.lower is not None,envelope_feasible=feasible,
                envelope_margin=self.envelope.margin(applied),envelope_clipped=applied<result.command-1e-7,
                applied_within_shared_cap=applied<=min(cap,controller.last_debug['decision_cap'])+1e-7)
            return Decision(applied,result.infeasible or not feasible,delivery(applied,belief.hb_lower,obs.sao2,bsa))
        controller.decide=protected

    def observe(self,frame):
        self._validate(frame)  # Reject invalid frames before touching envelope state.
        self.envelope.update(frame.observation,frame.calibrations)
        output=super().observe(frame)
        flags=() if self.envelope.lower is not None else ('independent_envelope_unavailable',)
        if not output.diagnostics['envelope_feasible']:flags+=('independent_stop_not_certified',)
        return replace(output,status=output.status+flags)

    def acknowledge(self,*,observation_time,applied_command):
        super().acknowledge(observation_time=observation_time,applied_command=applied_command)
        self.envelope.advance(applied_command)
