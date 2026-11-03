"""Source-traced control components and an explicitly adapted comparator.

Reference: Takahashi et al., JTEHM 2023, doi:10.1109/JTEHM.2023.3290951.
The 2022 author preprint supplies the transfer functions used here. The complete
2023 supplement/configuration and original trajectories have not been verified.
This module must not be described as an exact experimental reproduction.
"""
import math
from dataclasses import dataclass
from .control import Decision


@dataclass(frozen=True)
class OccluderMap:
    """Published Eq. (1), simplified with beta=A*(R+delta_R0).

    Physical calibration must supply beta, k and q0; none are paper defaults.
    Opening uses the same coordinate system as the supplied calibration.
    """
    q0: float
    beta: float
    k: float

    def __post_init__(self):
        if not all(math.isfinite(v) and v>0 for v in (self.q0,self.beta,self.k)):
            raise ValueError('Positive finite calibration parameters required')

    def flow(self,opening):
        if not math.isfinite(opening) or opening<0:
            raise ValueError('Opening must be finite and nonnegative')
        # Stable equivalent of q0*beta*expm1(k*x)/(1+beta*expm1(k*x)).
        if self.k*opening>700:return self.q0
        z=self.beta*math.expm1(self.k*opening)
        return self.q0*z/(1+z)

    def inverse(self,flow):
        if not math.isfinite(flow) or not 0<=flow<self.q0:
            raise ValueError('Flow must be in [0,q0); finite inverse required')
        return math.log1p(flow/(self.beta*(self.q0-flow)))/self.k


class ThirdOrderReference:
    """Gm(s)=1/(1+sigma*s)^3; exact zero-order-hold state update.

    This exact cascade update avoids introducing three separate Euler lags.
    """
    def __init__(self,sigma,dt,initial):
        if not all(math.isfinite(x) and x>0 for x in (sigma,dt)) or not math.isfinite(initial):
            raise ValueError('Invalid reference settings')
        self.sigma,self.dt=sigma,dt
        self.state=[initial]*3

    def update(self,command):
        if not math.isfinite(command):raise ValueError('Nonfinite reference')
        a=self.dt/self.sigma;e=math.exp(-a)
        z=[v-command for v in self.state]
        self.state=[command+e*z[0],command+e*(z[1]+a*z[0]),
                    command+e*(z[2]+a*z[1]+a*a*z[0]/2)]
        return self.state[2]


class PublishedLevelAdapter:
    """Flow-domain adaptation of measured-venous-flow plus I-PD architecture.

    Explicit changes: flow commands replace the occluder/feedforward/PID inner
    loop; gains are development-selected, not author gains; conventional positive
    derivative damping, filtering, tracking anti-windup and common actuator limits
    are engineering choices. The preprint's extracted PD sign needs verification.
    No oxygen supervisor is added to the reference architecture.
    """
    def __init__(self,bsa,dt=2.,*,kp=4.,ki=.08,kd=.5,target_level=.45,
                 sigma=3.6,derivative_tau=1.):
        if not all(math.isfinite(v) and v>0 for v in
                   (bsa,dt,kp,ki,target_level,sigma,derivative_tau)) or not math.isfinite(kd) or kd<0:
            raise ValueError('Invalid adapted controller settings')
        self.dt,self.kp,self.ki,self.kd=dt,kp,ki,kd
        self.target_level,self.derivative_tau=target_level,derivative_tau
        self.previous=2.4*bsa;self.previous_level=None;self.derivative=0.;self.integral=0.
        self.reference=ThirdOrderReference(sigma,dt,self.previous)

    def decide(self,obs,belief):
        # belief.venous_flow must be the explicit measured channel in this arm.
        error=obs.reservoir-self.target_level
        raw_derivative=0. if self.previous_level is None else (obs.reservoir-self.previous_level)/self.dt
        a=math.exp(-self.dt/self.derivative_tau)
        self.derivative=a*self.derivative+(1-a)*raw_derivative
        self.previous_level=obs.reservoir
        self.integral+=self.ki*error*self.dt
        raw=belief.venous_flow+self.kp*error+self.integral+self.kd*self.derivative
        bounded=min(7.,max(0.,raw))
        # Track only amplitude saturation. Do not erase the reference model's lag.
        if bounded!=raw:self.integral+=bounded-raw
        desired=self.reference.update(bounded)
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        command=min(high,max(low,desired))
        self.previous=command
        return Decision(command)
