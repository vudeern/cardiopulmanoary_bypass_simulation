"""SIMC PI tuning and a common application supervisor.

Source: Skogestad (2003), corrected open MIC reprint (2004), Eqs.23–24,
Table 1 integrating process. This is a general process-control reference,
not a commercial or published clinical CPB controller.
"""
from dataclasses import dataclass
import math
from .control import Controller,Decision
from .model import oxygen_content,delivery


@dataclass(frozen=True)
class PISettings:
    kc: float
    tau_i: float

    @property
    def ki(self):return self.kc/self.tau_i


def integrating_settings(kprime,theta,tau_c):
    """g(s)=kprime*exp(-theta*s)/s, including signed process gain.

    kc=1/[kprime*(tau_c+theta)], tau_i=4*(tau_c+theta).
    All time quantities use seconds; kprime must use matching units.
    """
    if not all(math.isfinite(v) for v in (kprime,theta,tau_c)) or kprime==0 or theta<0 or tau_c<=0:
        raise ValueError('Nonzero finite gain, nonnegative delay and positive tau_c required')
    return PISettings(1./(kprime*(tau_c+theta)),4.*(tau_c+theta))


class PICore:
    """Parallel PI, error=setpoint-measurement; forward rectangular integration.

    No hidden saturation. Application-level tracking is a separate explicit call.
    """
    def __init__(self,settings,dt,bias=0.):
        if not all(math.isfinite(v) for v in (settings.kc,settings.tau_i,dt,bias)) or settings.tau_i<=0 or dt<=0:
            raise ValueError('Invalid PI settings')
        self.settings,self.dt,self.bias=settings,dt,bias
        self.integral=0.;self.error=0.

    def update(self,setpoint,measurement):
        if not all(math.isfinite(v) for v in (setpoint,measurement)):
            raise ValueError('Nonfinite PI input')
        self.error=setpoint-measurement
        self.integral+=self.settings.ki*self.error*self.dt
        return self.bias+self.settings.kc*self.error+self.integral

    def track(self,applied):
        if not math.isfinite(applied):raise ValueError('Nonfinite applied command')
        self.integral=applied-self.bias-self.settings.kc*self.error


class MatchedSupervisor:
    """Compare source PI and existing forecast with the same application shell.

    Both share Hb-based oxygen demand cap, direct pressure slowdown, flow limits,
    slew limits and initial command. PI acts as a reservoir override. These CPB
    application choices are not part of the published SIMC tuning rule.
    Forecast retains its original internal cost/pressure/floor screening.
    """
    def __init__(self,kind,bsa,dt=1.,target=280.,*,tau_c=20.,target_level=.65,
                 reserve_margin=.2,nominal_actuator_tau=2.,pressure_slowdown=90.,design_sample_period=1.):
        if kind not in ('simc','forecast'):raise ValueError('Unknown matched controller')
        if not all(math.isfinite(v) and v>0 for v in
                   (bsa,dt,target,tau_c,target_level,nominal_actuator_tau,pressure_slowdown,design_sample_period)):
            raise ValueError('Invalid supervisor settings')
        self.kind,self.bsa,self.dt,self.target=kind,bsa,dt,target
        self.target_level,self.pressure_slowdown=target_level,pressure_slowdown
        self.previous=2.4*bsa
        # Design model: dV/dt=(qv-u)/60. Half-rule neglects actuator lag;
        # half a sample is included as an explicit ZOH design approximation.
        self.theta=nominal_actuator_tau/2.+design_sample_period/2.
        self.core=PICore(integrating_settings(-1./60.,self.theta,tau_c),dt,self.previous)
        self.forecast=Controller('sentinel',bsa,dt,target,reserve_margin=reserve_margin)

    def decide(self,obs,belief):
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        if self.kind=='simc':
            desired=self.core.update(self.target_level,obs.reservoir)
            infeasible=False
        else:
            self.forecast.previous=self.previous
            d=self.forecast.decide(obs,belief)
            desired=d.command;infeasible=d.infeasible
        oxygen_flow=self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))
        desired=min(desired,oxygen_flow)
        if obs.pressure>self.pressure_slowdown:desired=min(desired,low)
        applied=min(high,max(low,desired))
        if self.kind=='simc':self.core.track(applied)
        self.previous=float(applied)
        return Decision(float(applied),infeasible,delivery(applied,belief.hb_lower,obs.sao2,self.bsa))
