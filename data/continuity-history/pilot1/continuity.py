"""Reference-anchored mass balance bridges interruptions in level references.

Uncalibrated simulation controller. The nominal pump model, venous bias fit and
age allowance are engineering estimates, not guaranteed uncertainty bounds.
"""
import math
from .braking import braking_volume
from .control import Decision
from .model import oxygen_content,delivery


class ContinuityController:
    def __init__(self,bsa,dt=1.,target=280.,*,base_allowance=.06,venous_allowance=.2,
                 nominal_tau=4.,age_allowance=.0001,tau_lower=1.,tau_upper=10.,floor=.25):
        vals=(bsa,dt,target,base_allowance,venous_allowance,nominal_tau,age_allowance,tau_lower,tau_upper,floor)
        if not all(math.isfinite(v) for v in vals) or min(bsa,dt,target,nominal_tau,tau_lower,tau_upper,floor)<=0 or min(base_allowance,venous_allowance,age_allowance)<0 or tau_lower>tau_upper:
            raise ValueError('Invalid continuity settings')
        self.bsa,self.dt,self.target=bsa,dt,target
        self.base,self.venous_allowance,self.nominal_tau=base_allowance,venous_allowance,nominal_tau
        self.age_allowance,self.tau_lower,self.tau_upper,self.floor=age_allowance,tau_lower,tau_upper,floor
        self.previous=self.flow=self.flow_lower=self.flow_upper=2.4*bsa
        self.integral=0.;self.history={};self.pending=[];self.anchor=None;self.venous_bias=0.
        self.last_time=None;self.last_debug={}

    def observe_references(self,samples):
        self.pending.extend(samples)

    def decide(self,obs,belief):
        if self.last_time is not None and not math.isclose(obs.time-self.last_time,self.dt,abs_tol=1e-8):
            raise ValueError('Continuity observations must advance by dt')
        self.last_time=obs.time
        self.history[round(obs.time,9)]=self.integral
        for sample in self.pending:
            if sample.delivered>obs.time+1e-9 or sample.acquired>obs.time+1e-9:
                raise ValueError('Future reference supplied')
            key=round(sample.acquired,9)
            if key not in self.history:raise ValueError('Reference has no acquisition history')
            if self.anchor is not None and sample.acquired<=self.anchor[0]:continue
            mass=self.history[key]
            if self.anchor is not None:
                t,v,i=self.anchor
                # integral contains the raw venous sensor, before bias correction.
                fitted=60.*((mass-i)-(sample.value-v))/(sample.acquired-t)
                self.venous_bias=min(2.,max(-2.,fitted))
            self.anchor=(sample.acquired,sample.value,mass)
        self.pending=[]
        if self.anchor is None:
            estimate=obs.reservoir;age=0.
        else:
            t,v,i=self.anchor;age=obs.time-t
            estimate=v+(self.integral-i)-self.venous_bias*age/60.
        allowance=self.base+self.age_allowance*age
        lower=max(0.,estimate-allowance)
        inflow=max(0.,belief.venous_flow-self.venous_bias-self.venous_allowance)
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        high=max(low,min(high,self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))))
        if obs.pressure>90.:high=low
        budget=max(0.,lower-self.floor)
        loss=lambda u:braking_volume(self.flow_upper,u,inflow,self.tau_upper,.15,self.dt)
        feasible=lower>=self.floor and loss(low)<=budget
        if not feasible:command=low
        elif loss(high)<=budget:command=high
        else:
            left,right=low,high
            for _ in range(24):
                mid=(left+right)/2
                if loss(mid)<=budget:left=mid
                else:right=mid
            command=left
        self.last_debug=dict(control_level_lower=lower,balance_level_estimate=estimate,
            balance_reference_age=age if self.anchor else None,venous_bias_estimate=self.venous_bias,
            braking_volume=loss(command),braking_budget=budget,braking_feasible=feasible,
            level_information_unknown=self.anchor is None,inflow_lower=inflow,actuator_flow_upper=self.flow_upper)
        next_flow=command+(self.flow-command)*math.exp(-self.dt/self.nominal_tau)
        self.integral+=(belief.venous_flow-(self.flow+next_flow)/2.)*self.dt/60.
        self.flow=next_flow
        a=math.exp(-self.dt/self.tau_lower);b=math.exp(-self.dt/self.tau_upper)
        self.flow_lower=min(command+(self.flow_lower-command)*a,command+(self.flow_lower-command)*b)
        self.flow_upper=max(command+(self.flow_upper-command)*a,command+(self.flow_upper-command)*b)
        self.previous=command
        return Decision(command,not feasible,delivery(command,belief.hb_lower,obs.sao2,self.bsa))
