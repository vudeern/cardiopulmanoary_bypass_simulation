"""A noisy delayed level-reference channel and two causal ways to use it.

The bounded method uses engineering allowances, not probabilistic guarantees.
Both methods match references to stored inline readings at acquisition time.
"""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class LevelSample:
    acquired: float
    delivered: float
    value: float


class LevelReferences:
    def __init__(self,seed,*,period=60.,delay=4.,noise_sd=.01,bias=0.,
                 dropout_prob=0.,outage_start=None,outage_end=None,common_mode_fraction=0.):
        if not all(math.isfinite(v) for v in (period,delay,noise_sd,bias,dropout_prob,common_mode_fraction)):
            raise ValueError('Reference settings must be finite')
        if period<=0 or delay<0 or noise_sd<0 or not 0<=dropout_prob<=1:
            raise ValueError('Invalid reference schedule or noise')
        if (outage_start is None)!=(outage_end is None):
            raise ValueError('Provide both outage endpoints')
        if outage_start is not None and not (math.isfinite(outage_start) and
            math.isfinite(outage_end) and 0<=outage_start<outage_end):
            raise ValueError('Invalid outage interval')
        self.period,self.delay,self.noise_sd,self.bias=period,delay,noise_sd,bias
        self.dropout_prob=dropout_prob
        self.outage_start,self.outage_end=outage_start,outage_end
        self.common_mode_fraction=common_mode_fraction
        self.rng=np.random.default_rng(seed)
        self.next_sample=0.;self.queue=[]

    def observe(self,t,true_level,inline_bias=0.):
        if t+1e-9>=self.next_sample:
            normal=self.rng.normal();uniform=self.rng.random()
            outage=self.outage_start is not None and self.outage_start<=t<self.outage_end
            if not outage and uniform>=self.dropout_prob:
                self.queue.append(LevelSample(t,t+self.delay,float(true_level+
                    self.noise_sd*normal+self.bias+self.common_mode_fraction*inline_bias)))
            self.next_sample+=self.period
        ready=[sample for sample in self.queue if sample.delivered<=t+1e-9]
        self.queue=[sample for sample in self.queue if sample.delivered>t+1e-9]
        return ready


class ReferenceLevel:
    def __init__(self,mode,*,base_allowance=.04,drift_allowance=.003,max_age=180.):
        if mode not in ('hold','bounded'):raise ValueError('Unknown reference mode')
        if not all(math.isfinite(v) and v>=0 for v in (base_allowance,drift_allowance,max_age)):
            raise ValueError('Invalid engineering allowances')
        self.mode=mode;self.base_allowance=base_allowance
        self.drift_allowance=drift_allowance;self.max_age=max_age
        self.inline={};self.bias=0.;self.acquired=None

    def update(self,obs,samples):
        self.inline[obs.time]=obs.reservoir
        for sample in samples:
            if sample.delivered>obs.time+1e-9 or sample.acquired>obs.time:
                raise ValueError('Future reference supplied to observer')
            if sample.acquired not in self.inline:
                raise ValueError('No matching inline acquisition')
            if self.acquired is None or sample.acquired>=self.acquired:
                self.bias=self.inline[sample.acquired]-sample.value
                self.acquired=sample.acquired
        age=None if self.acquired is None else obs.time-self.acquired
        estimate=obs.reservoir-self.bias
        unknown=age is None or age>self.max_age
        if self.mode=='hold':
            lower=max(0.,estimate)
        elif unknown:
            lower=0.  # Explicitly conservative loss-of-information response.
        else:
            lower=max(0.,estimate-self.base_allowance-self.drift_allowance*age)
        return dict(estimate=estimate,lower=lower,bias=self.bias,age=age,unknown=unknown)
