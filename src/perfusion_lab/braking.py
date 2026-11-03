"""Predictive braking reserve under explicit engineering uncertainty allowances.

This is a simulation design, not a medical safety proof. Assumes bounded
actuator lag, bounded residual level error and a lower inflow estimate that
remains valid during braking. Abrupt unseen drainage loss can violate that last
assumption; violated assumptions and infeasible braking are retained as failures.
"""
import math
from .control import Decision
from .model import oxygen_content,delivery


def braking_volume(flow_upper,command,inflow_lower,tau_upper,slew,dt):
    """Conservative excess outflow [L] for one hold then rate-limited braking.

    Initial positive flow excess times lag + hold and ramp command areas.
    Positive parts intentionally overestimate loss when starting below inflow.
    Constant unknown first-order lag is assumed <=tau_upper.
    """
    values=(flow_upper,command,inflow_lower,tau_upper,slew,dt)
    if not all(math.isfinite(v) for v in values) or min(flow_upper,command,inflow_lower)<0 or min(tau_upper,slew,dt)<=0:
        raise ValueError('Invalid braking inputs')
    excess=max(0.,command-inflow_lower)
    peak=max(0.,flow_upper-inflow_lower)
    return (tau_upper*peak+dt*excess+excess*excess/(2*slew))/60.


class BrakingController:
    def __init__(self,bsa,dt=1.,target=280.,*,venous_allowance=.8,drift_allowance=.004,
                 base_allowance=.03,tau_lower=1.,tau_upper=10.,floor=.25,
                 pressure_slowdown=90.,max_age=180.,rate_multiplier=2.):
        vals=(bsa,dt,target,venous_allowance,drift_allowance,base_allowance,tau_lower,tau_upper,floor,pressure_slowdown,max_age,rate_multiplier)
        if not all(math.isfinite(v) for v in vals) or min(bsa,dt,target,tau_lower,tau_upper,floor,pressure_slowdown,max_age,rate_multiplier)<=0 or min(venous_allowance,drift_allowance,base_allowance)<0 or tau_upper<tau_lower:
            raise ValueError('Invalid braking controller settings')
        self.bsa,self.dt,self.target=bsa,dt,target
        self.venous_allowance,self.drift_allowance,self.base_allowance=venous_allowance,drift_allowance,base_allowance
        self.tau_lower,self.tau_upper,self.floor=tau_lower,tau_upper,floor
        self.pressure_slowdown,self.max_age=pressure_slowdown,max_age
        self.previous=2.4*bsa;self.flow_lower=self.flow_upper=self.previous
        self.last_debug={};self.level_history=[]
        self.rate_multiplier=rate_multiplier;self.last_bias=None;self.last_acquired=None;self.estimated_drift=0.

    def decide(self,obs,belief):
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        oxygen_flow=self.target*self.bsa/(10*oxygen_content(belief.hb_lower,obs.sao2))
        high=max(low,min(high,oxygen_flow))
        if obs.pressure>self.pressure_slowdown:high=low
        age=obs.level_reference_age
        unknown=age is None or age>self.max_age
        acquired=None if age is None else obs.time-age
        if acquired is not None and (self.last_acquired is None or acquired>self.last_acquired+1e-9):
            if self.last_acquired is not None:
                self.estimated_drift=max(0.,(obs.level_reference_bias-self.last_bias)/(acquired-self.last_acquired))
            self.last_bias=obs.level_reference_bias;self.last_acquired=acquired
        drift_rate=max(self.drift_allowance,self.rate_multiplier*self.estimated_drift)
        allowance=self.base_allowance+drift_rate*(self.max_age if age is None else age)
        level_lower=0. if unknown else max(0.,obs.reservoir-allowance)
        qin=max(0.,belief.venous_flow-self.venous_allowance)
        # Undo only the observed reference correction to track raw inline level.
        # This avoids mistaking a reference update for a real volume change.
        raw_level=obs.reservoir+obs.level_reference_bias
        if self.level_history and obs.time<=self.level_history[-1][0]:
            raise ValueError('Observation times must increase')
        self.level_history.append((obs.time,raw_level))
        self.level_history=[x for x in self.level_history if x[0]>=obs.time-5.-1e-9]
        balance_qin=None
        if len(self.level_history)>1:
            first_t,first_v=self.level_history[0]
            slope=(raw_level-first_v)/(obs.time-first_t)
            # Current command-history lower flow plus past volume slope. The
            # past slope is not a guaranteed bound on future venous return.
            balance_qin=max(0.,self.flow_lower+60.*(slope-drift_rate))
            qin=min(qin,balance_qin)
        budget=max(0.,level_lower-self.floor)
        loss=lambda u:braking_volume(self.flow_upper,u,qin,self.tau_upper,.15,self.dt)
        feasible=not unknown and level_lower>=self.floor and loss(low)<=budget
        if not feasible:command=low
        elif loss(high)<=budget:command=high
        else:
            left,right=low,high
            for _ in range(24):
                mid=(left+right)/2
                if loss(mid)<=budget:left=mid
                else:right=mid
            command=left
        self.last_debug=dict(braking_volume=loss(command),braking_budget=budget,
            control_level_lower=level_lower,inflow_lower=qin,actuator_flow_upper=self.flow_upper,
            braking_feasible=feasible,level_information_unknown=unknown,
            balance_inflow_lower=balance_qin,estimated_drift_rate=drift_rate)
        a=math.exp(-self.dt/self.tau_lower);b=math.exp(-self.dt/self.tau_upper)
        self.flow_lower=min(command+(self.flow_lower-command)*a,command+(self.flow_lower-command)*b)
        self.flow_upper=max(command+(self.flow_upper-command)*a,command+(self.flow_upper-command)*b)
        self.previous=command
        return Decision(command,not feasible,delivery(command,belief.hb_lower,obs.sao2,self.bsa))
