"""Flow-measurement-independent baselines; no novelty or safety claim.

These use level/reference, Hb and saturation for oxygen demand, plus a direct
pressure slowdown. They intentionally do not consume measured flow or inferred
drainage, allowing an exact flow-bias-invariance comparison within this model.
"""
import math
import numpy as np
from .control import Decision
from .model import oxygen_content,delivery


class LevelFeedback:
    def __init__(self,kind,bsa,dt=2.,target=280.,*,target_level=.6,kp=4.,ki=.08,
                 threshold=.8,pressure_slowdown=90.):
        if kind not in ('pi','threshold'):raise ValueError('Unknown level feedback kind')
        if not all(math.isfinite(v) and v>0 for v in
                   (target_level,kp,ki,threshold,pressure_slowdown)):
            raise ValueError('Feedback settings must be finite and positive')
        self.kind,self.bsa,self.dt,self.target=kind,bsa,dt,target
        self.target_level,self.kp,self.ki=target_level,kp,ki
        self.threshold,self.pressure_slowdown=threshold,pressure_slowdown
        self.previous=2.4*bsa;self.integral=self.previous

    def decide(self,obs,belief):
        low=max(0.,self.previous-.15*self.dt);high=min(7.,self.previous+.15*self.dt)
        oxygen_flow=self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))
        if self.kind=='pi':
            error=obs.reservoir-self.target_level
            self.integral+=self.ki*error*self.dt
            proposed=self.integral+self.kp*error
            desired=min(oxygen_flow,proposed)
        else:
            desired=oxygen_flow if obs.reservoir>=self.threshold else 0.
        if obs.pressure>self.pressure_slowdown:desired=min(desired,low)
        command=float(np.clip(desired,low,high))
        if self.kind=='pi' and abs(command-proposed)>1e-9:
            # Back-calculation tracking prevents integration beyond demand,
            # actuator or pressure limits. This also handles command slew.
            self.integral=command-self.kp*error
        self.previous=command
        return Decision(command,False,delivery(command,belief.hb_lower,obs.sao2,self.bsa))
