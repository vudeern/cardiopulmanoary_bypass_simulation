"""Reference quarantine with an explicitly simulated independent calibration.

No channel is perfect. Pairwise agreement cannot detect shared corruption.
Allowances are engineering assumptions, not calibrated confidence intervals.
"""
import math
from .reference import LevelReferences
from .simc import MatchedSupervisor
from .braking import braking_volume
from .control import Decision
from .model import oxygen_content,delivery


class FaultyReferences(LevelReferences):
    """Fault injection belongs to the sensor, never to the guard/controller."""
    def __init__(self,seed,*,profile='constant',fault_bias=0.,start=210.,end=360.,ramp_duration=180.,**options):
        if profile not in ('constant','step','ramp','spike'):raise ValueError('Unknown reference fault profile')
        if not all(math.isfinite(v) for v in (fault_bias,start,end,ramp_duration)) or start<0 or end<=start or ramp_duration<=0:raise ValueError('Invalid reference fault settings')
        super().__init__(seed,**options);self.profile,self.fault_bias=profile,fault_bias
        self.start,self.end,self.ramp_duration=start,end,ramp_duration;self.initial_bias=self.bias;self.labels={}

    def observe(self,t,true_level,inline_bias=0.):
        if self.profile=='constant':scale=1.
        elif self.profile=='step':scale=float(t>=self.start)
        elif self.profile=='spike':scale=float(self.start<=t<self.end)
        else:scale=min(1.,max(0.,(t-self.start)/self.ramp_duration))
        self.bias=self.initial_bias+self.fault_bias*scale
        if t+1e-9>=self.next_sample:self.labels[round(t,9)]=self.bias+self.common_mode_fraction*inline_bias
        return super().observe(t,true_level,inline_bias)


class ReferenceGuard:
    def __init__(self,initial_flow,dt=1.,*,base_uncertainty=.04,drift_allowance=.001,
                 audit_tolerance=.06,model_flow_allowance=.2,audit_wait=8.,max_cal_age=240.,clean_audits=1,screen=True):
        vals=(initial_flow,dt,base_uncertainty,drift_allowance,audit_tolerance,model_flow_allowance,audit_wait,max_cal_age)
        if not all(math.isfinite(v) for v in vals) or min(initial_flow,dt,audit_tolerance,max_cal_age)<=0 or min(base_uncertainty,drift_allowance,model_flow_allowance,audit_wait)<0 or clean_audits not in (1,2):raise ValueError('Invalid reference guard settings')
        self.dt,self.base,self.drift=dt,base_uncertainty,drift_allowance
        self.tolerance,self.model_allowance,self.wait,self.max_age=audit_tolerance,model_flow_allowance,audit_wait,max_cal_age
        self.screen=bool(screen);self.clean_required=clean_audits;self.clean_count=0;self.quarantined=True
        self.flow=initial_flow;self.integral=0.;self.history={};self.pending=[];self.calibrations={}
        self.cal=None;self.cal_count=0;self.q_bias=0.;self.correction=None;self.last_time=None

    def update(self,obs,routine,calibrations):
        if self.last_time is not None and not math.isclose(obs.time-self.last_time,self.dt,abs_tol=1e-8):raise ValueError('Guard time must advance by dt')
        self.last_time=obs.time;self.history[round(obs.time,9)]=(obs.reservoir,self.integral)
        for sample in list(routine)+list(calibrations):
            if sample.delivered>obs.time+1e-9 or sample.acquired>obs.time+1e-9:raise ValueError('Future reference supplied')
            if round(sample.acquired,9) not in self.history:raise ValueError('Unmatched acquisition')
        events=[]
        for sample in calibrations:
            key=round(sample.acquired,9);raw,mass=self.history[key];self.calibrations[key]=sample
            if self.cal is not None and sample.acquired<=self.cal[0]:continue
            if self.cal is not None:
                t,v,i,_=self.cal;self.q_bias=max(-2.,min(2.,60.*((mass-i)-(sample.value-v))/(sample.acquired-t)))
            self.cal=(sample.acquired,sample.value,mass,raw-sample.value);self.cal_count+=1
            # The independent channel corrects the fallback even if an equal-time
            # routine sample was previously accepted. No controller sees truth.
            self.correction=(sample.acquired,raw-sample.value)
        self.pending.extend(routine);remaining=[]
        for sample in self.pending:
            key=round(sample.acquired,9);raw,mass=self.history[key];peer=self.calibrations.get(key)
            if peer is None and obs.time<sample.delivered+self.wait-1e-9:
                remaining.append(sample);continue
            accepted=False;reason='no_independent_anchor'
            if peer is not None:
                error=abs(sample.value-peer.value)
                if error>self.tolerance:
                    self.quarantined=True;self.clean_count=0;reason='paired_audit_disagreement'
                else:
                    self.clean_count+=1;self.quarantined=self.clean_count<self.clean_required
                    accepted=not self.quarantined;reason='paired_audit_pass' if accepted else 'awaiting_clean_audits'
            elif self.cal is not None and not self.quarantined:
                t,v,i,offset=self.cal;age=max(0.,sample.acquired-t)
                inline_ok=abs(sample.value-(raw-offset))<=self.tolerance+self.drift*age
                mass_ok=True
                if self.cal_count>=2:
                    predicted=v+mass-i-self.q_bias*(sample.acquired-t)/60.
                    mass_ok=abs(sample.value-predicted)<=self.tolerance+self.model_allowance*age/60.
                accepted=inline_ok and mass_ok and obs.time-t<=self.max_age
                reason='prediction_pass' if accepted else 'prediction_disagreement'
                if not accepted:self.quarantined=True;self.clean_count=0
            elif self.cal is not None:reason='source_quarantined'
            if not self.screen:
                accepted=True;reason='screening_disabled';self.quarantined=False
            if accepted and (self.correction is None or sample.acquired>=self.correction[0]):self.correction=(sample.acquired,raw-sample.value)
            if not accepted and self.cal is not None:self.correction=(self.cal[0],self.cal[3])
            events.append(dict(acquired=sample.acquired,delivered=sample.delivered,decision_time=obs.time,accepted=accepted,reason=reason))
        self.pending=remaining
        if self.correction is None:estimate=obs.reservoir;age=None;uncertainty=self.base+.3
        else:
            t,offset=self.correction;age=obs.time-t
            estimate=obs.reservoir-offset;uncertainty=self.base+self.drift*age
        cal_age=None if self.cal is None else obs.time-self.cal[0]
        supported=self.cal_count>=2 and cal_age<=self.max_age and not self.quarantined
        lower=max(0.,estimate-uncertainty)
        return dict(estimate=estimate,lower=lower,uncertainty=uncertainty,age=age,
            bias=obs.reservoir-estimate,unknown=self.cal is None,calibration_age=cal_age,
            calibration_count=self.cal_count,quarantined=self.quarantined,supported=supported,
            venous_bias=self.q_bias,events=events)

    def advance(self,command,measured_venous):
        next_flow=command+(self.flow-command)*math.exp(-self.dt/2.)
        self.integral+=(measured_venous-(self.flow+next_flow)/2.)*self.dt/60.;self.flow=next_flow


class IntegrityController:
    """The hybrid and its matched PI use the exact same guarded level input."""
    def __init__(self,kind,bsa,dt=1.,target=280.,*,tau_c=5.,target_level=.65):
        if kind not in ('hybrid','pi'):raise ValueError('Invalid integrity controller')
        self.kind,self.bsa,self.dt,self.target=kind,bsa,dt,target
        self.pi=MatchedSupervisor('simc',bsa,dt,target,tau_c=tau_c,target_level=target_level)
        self.previous=self.flow_upper=2.4*bsa;self.weight=0.;self.reference_state=None;self.last_debug={}

    def set_reference_state(self,state):self.reference_state=state

    def decide(self,obs,belief):
        state=self.reference_state
        if state is None:raise ValueError('Guard state required')
        self.pi.previous=self.previous;base=self.pi.decide(obs,belief)
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        high=max(low,min(high,self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))))
        if obs.pressure>90.:high=low
        lower=max(0.,obs.reservoir-.04);budget=max(0.,lower-.25)
        qin=max(0.,belief.venous_flow-state['venous_bias']-.3)
        loss=lambda u:braking_volume(self.flow_upper,u,qin,10.,.15,self.dt)
        feasible=lower>=.25 and loss(low)<=budget
        if not feasible:predicted=low
        elif loss(high)<=budget:predicted=high
        else:
            left,right=low,high
            for _ in range(24):
                mid=(left+right)/2
                if loss(mid)<=budget:left=mid
                else:right=mid
            predicted=left
        eligible=self.kind=='hybrid' and state['supported']
        desired=float(eligible);self.weight=min(self.weight+self.dt/10.,max(self.weight-self.dt/10.,desired))
        # A rejected reference can never cause an upward override, including
        # during fade-out. PI still uses the same guarded lower estimate.
        if not eligible or obs.pressure>=85.:predicted=min(base.command,predicted)
        command=min(high,max(low,base.command+self.weight*(predicted-base.command)))
        self.pi.core.track(command);self.pi.previous=command
        self.last_debug=dict(control_level_lower=lower,override_weight=self.weight,
            override_eligible=eligible,override_delta=command-base.command,pi_command=base.command,
            braking_volume=loss(command),braking_budget=budget,predictive_feasible=feasible)
        a=math.exp(-self.dt);b=math.exp(-self.dt/10.)
        self.flow_upper=max(command+(self.flow_upper-command)*a,command+(self.flow_upper-command)*b);self.previous=command
        return Decision(command,self.weight>0 and (lower<.25 or loss(command)>budget+1e-9),delivery(command,belief.hb_lower,obs.sao2,self.bsa))
