"""PI with a gated predictive override and rate-limited return to PI.

The agreement gate is an engineering consistency check, not a calibrated
confidence probability or a medical safety certificate. Shared sensor errors
can fool it. No injected fault truth or future samples enter this module.
"""
import math
from .simc import MatchedSupervisor
from .braking import braking_volume
from .control import Decision
from .model import oxygen_content,delivery


class SelectiveController:
    def __init__(self,bsa,dt=1.,target=280.,*,tau_c=1.5,target_level=.45,
                 base_allowance=.1,agreement=.08,max_age=90.,strength=.25,
                 mode='hybrid',nominal_tau=2.,venous_allowance=.3,fade_time=10.):
        vals=(bsa,dt,target,tau_c,target_level,base_allowance,agreement,max_age,strength,nominal_tau,venous_allowance,fade_time)
        if not all(math.isfinite(v) for v in vals) or min(bsa,dt,target,tau_c,target_level,agreement,max_age,nominal_tau,fade_time)<=0 or min(base_allowance,venous_allowance)<0 or not 0<=strength<=1 or mode not in ('hybrid','brake_only','boost_only','disabled'):
            raise ValueError('Invalid selective PI settings')
        self.bsa,self.dt,self.target=bsa,dt,target
        self.base,self.agreement,self.max_age,self.strength=base_allowance,agreement,max_age,strength
        self.mode,self.nominal_tau,self.q_allowance,self.fade_time=mode,nominal_tau,venous_allowance,fade_time
        self.pi=MatchedSupervisor('simc',bsa,dt,target,tau_c=tau_c,target_level=target_level)
        self.previous=self.flow=self.flow_upper=2.4*bsa
        self.integral=0.;self.history={};self.pending=[];self.anchor=None;self.venous_bias=0.
        self.reference_count=0;self.weight=0.;self.last_time=None;self.last_debug={}

    def observe_references(self,samples):self.pending.extend(samples)

    def decide(self,obs,belief):
        if self.last_time is not None and not math.isclose(obs.time-self.last_time,self.dt,abs_tol=1e-8):
            raise ValueError('Selective PI observations must advance by dt')
        self.last_time=obs.time;self.history[round(obs.time,9)]=self.integral
        for sample in self.pending:
            if sample.delivered>obs.time+1e-9 or sample.acquired>obs.time+1e-9:raise ValueError('Future reference supplied')
            key=round(sample.acquired,9)
            if key not in self.history:raise ValueError('Unmatched reference acquisition')
            if self.anchor is not None and sample.acquired<=self.anchor[0]:continue
            mass=self.history[key]
            if self.anchor is not None:
                t,v,i=self.anchor
                fitted=60.*((mass-i)-(sample.value-v))/(sample.acquired-t)
                self.venous_bias=min(2.,max(-2.,fitted))
            self.anchor=(sample.acquired,sample.value,mass);self.reference_count+=1
        self.pending=[]
        if self.anchor is None:estimate=obs.reservoir;age=None
        else:
            t,v,i=self.anchor;age=obs.time-t
            estimate=v+self.integral-i-self.venous_bias*age/60.
        residual=abs(estimate-obs.reservoir)
        eligible=(self.reference_count>=2 and age is not None and age<=self.max_age
                  and residual<=self.agreement and self.mode!='disabled')
        desired_weight=self.strength if eligible else 0.
        step=self.dt/self.fade_time
        self.weight=min(self.weight+step,max(self.weight-step,desired_weight))
        # Both PI state and the prediction are advanced with the actual applied
        # command. Tracking below prevents an integral jump on return to PI.
        self.pi.previous=self.previous
        base=self.pi.decide(obs,belief)
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        high=max(low,min(high,self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))))
        if obs.pressure>90.:high=low
        level=max(0.,min(estimate,obs.reservoir)-self.base)
        inflow=max(0.,belief.venous_flow-self.venous_bias-self.q_allowance)
        budget=max(0.,level-.25)
        loss=lambda u:braking_volume(self.flow_upper,u,inflow,10.,.15,self.dt)
        feasible=level>=.25 and loss(low)<=budget
        if not feasible:predicted=low
        elif loss(high)<=budget:predicted=high
        else:
            left,right=low,high
            for _ in range(24):
                mid=(left+right)/2
                if loss(mid)<=budget:left=mid
                else:right=mid
            predicted=left
        if self.mode=='brake_only':predicted=min(base.command,predicted)
        elif self.mode=='boost_only':predicted=max(base.command,predicted)
        command=min(high,max(low,base.command+self.weight*(predicted-base.command)))
        self.pi.core.track(command);self.pi.previous=command
        self.last_debug=dict(control_level_lower=level,balance_level_estimate=estimate,
            balance_reference_age=age,venous_bias_estimate=self.venous_bias,reference_count=self.reference_count,
            estimate_disagreement=residual,override_eligible=eligible,override_weight=self.weight,
            pi_command=base.command,predictive_command=predicted,override_delta=command-base.command,
            braking_volume=loss(command),braking_budget=budget,predictive_feasible=feasible,
            level_information_unknown=self.anchor is None)
        next_flow=command+(self.flow-command)*math.exp(-self.dt/self.nominal_tau)
        self.integral+=(belief.venous_flow-(self.flow+next_flow)/2.)*self.dt/60.;self.flow=next_flow
        a=math.exp(-self.dt);b=math.exp(-self.dt/10.)
        self.flow_upper=max(command+(self.flow_upper-command)*a,command+(self.flow_upper-command)*b)
        self.previous=command
        # A partial override is not a hard guarantee that the braking constraint
        # holds. Flag its violation rather than calling a blended action safe.
        violated=level<.25 or loss(command)>budget+1e-9
        return Decision(command,self.weight>0 and violated,delivery(command,belief.hb_lower,obs.sao2,self.bsa))
