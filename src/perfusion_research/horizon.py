"""Offline nominal horizon planner. Not a protected runtime or device controller.

The prediction uses supplied return/O2 forecasts and fixed nominal parameters.
The appended zero-return backup has normal slew and ends at zero command, then
an analytic discrete tail. This establishes nominal terminal floor recoverability,
not robust protection against forecast, state, model, or timing errors.
"""
from dataclasses import dataclass
import math
from time import perf_counter
import numpy as np
from scipy import sparse
from scipy.optimize import linprog


def tail_factor(dt, tau):
    if not all(math.isfinite(v) and v > 0 for v in (dt, tau)):
        raise ValueError('Positive finite time parameters required')
    # 1-exp(-dt/tau) without catastrophic cancellation.
    decay_loss = -math.expm1(-dt/tau)
    if decay_loss == 0.:
        raise ValueError('Unrepresentable time ratio')
    value = dt/120.*(2.-decay_loss)/decay_loss
    if not math.isfinite(value):
        raise ValueError('Unrepresentable stopping tail')
    return value


@dataclass
class Problem:
    A: sparse.csc_matrix
    lower: np.ndarray
    upper: np.ndarray
    cost: np.ndarray
    horizon: int
    steps: int
    dt: float
    tau: float
    resistance: float
    compliance: float
    initial: np.ndarray
    previous: float
    returns: np.ndarray
    conversion: np.ndarray
    target: np.ndarray
    floor: float
    ceiling: float
    pressure_limit: float
    max_command: float
    slew: float

    @property
    def command_start(self): return 3*(self.steps+1)

    @property
    def deficit_start(self): return self.command_start+self.steps


def formulate(initial, previous, returns, conversion, target, *, dt=1., tau=2.,
              resistance=14., compliance=.0018, floor=.29, ceiling=5.8,
              pressure_limit=95., max_command=7., slew=.15):
    initial=np.asarray(initial,dtype=float)
    returns=np.asarray(returns,dtype=float)
    conversion=np.asarray(conversion,dtype=float)
    target=np.asarray(target,dtype=float)
    values=(dt,tau,resistance,compliance,ceiling,pressure_limit,max_command,slew)
    if (initial.shape!=(3,) or not np.isfinite(initial).all() or (initial<0).any()
            or returns.ndim!=1 or not len(returns) or len(returns)>120
            or conversion.shape!=returns.shape or target.shape!=returns.shape
            or not all(np.isfinite(v).all() for v in (returns,conversion,target))
            or (returns<0).any() or (conversion<=0).any() or (target<=0).any()
            or not all(math.isfinite(v) and v>0 for v in values)
            or not math.isfinite(floor) or not 0<=floor<ceiling
            or not math.isfinite(previous) or not 0<=previous<=max_command):
        raise ValueError('Invalid nominal horizon inputs')
    n=len(returns);backup=math.ceil(max_command/(slew*dt))+1
    if backup>1000:raise ValueError('Backup discretization too large')
    steps=n+backup;commands=3*(steps+1);deficits=commands+steps
    size=deficits+n
    rows=[];lower=[];upper=[]
    def add(coefficients,lo,hi):
        rows.append(coefficients);lower.append(lo);upper.append(hi)
    alpha=math.exp(-dt/tau);a=(1+alpha)/2.;b=(1-alpha)/2.
    beta=math.exp(-dt/(resistance*compliance*60.))
    return_all=np.r_[returns,np.zeros(backup)]
    for j in range(3):add({j:1.},initial[j],initial[j])
    for k in range(steps):
        v,q,p=3*k,3*k+1,3*k+2;vn,qn,pn=v+3,q+3,p+3;u=commands+k
        add({vn:1.,v:-1.,q:dt*a/60.,u:dt*b/60.},dt*return_all[k]/60.,dt*return_all[k]/60.)
        add({qn:1.,q:-alpha,u:-(1-alpha)},0.,0.)
        add({pn:1.,p:-beta,q:-(1-beta)*resistance*a,u:-(1-beta)*resistance*b},0.,0.)
        add({u:1.},0.,max_command)
        if k==0:add({u:1.},previous-slew*dt,previous+slew*dt)
        else:add({u:1.,u-1:-1.},-slew*dt,0. if k>=n else slew*dt)
        if k<n:
            add({deficits+k:1.,q:conversion[k]*a,u:conversion[k]*b},target[k],np.inf)
            add({deficits+k:1.},0.,np.inf)
    for k in range(steps+1):
        add({3*k:1.},floor,ceiling)
        add({3*k+1:1.},0.,max(max_command,initial[1]))
        add({3*k+2:1.},0.,pressure_limit)
    add({commands+steps-1:1.},0.,0.)
    add({3*steps:1.,3*steps+1:-tail_factor(dt,tau)},floor,np.inf)
    rr=[];cc=[];data=[]
    for r,coefficients in enumerate(rows):
        for col,value in coefficients.items():rr.append(r);cc.append(col);data.append(value)
    matrix=sparse.csc_matrix((data,(rr,cc)),shape=(len(rows),size))
    cost=np.zeros(size);cost[deficits:]=dt/60.
    return Problem(matrix,np.array(lower),np.array(upper),cost,n,steps,dt,tau,
        resistance,compliance,initial,previous,return_all,conversion,target,
        floor,ceiling,pressure_limit,max_command,slew)


def validate_plan(problem, vector, tolerance=1e-6):
    """Independent physical rollout as well as raw matrix residual checks."""
    p=problem;x=np.asarray(vector,dtype=float)
    if x.shape!=p.cost.shape or not np.isfinite(x).all():
        return dict(valid=False,reason='nonfinite_or_shape')
    residual=p.A@x
    violation=max(0.,float(np.max(p.lower-residual)),float(np.max(residual-p.upper)))
    states=x[:p.command_start].reshape(-1,3)
    controls=x[p.command_start:p.deficit_start]
    v,q,pressure=p.initial.copy();rollout_error=0.;physical_violation=0.
    for k,u in enumerate(controls):
        qnext=u+(q-u)*math.exp(-p.dt/p.tau);flow=(q+qnext)/2.
        v+=(p.returns[k]-flow)*p.dt/60.
        pressure=p.resistance*flow+(pressure-p.resistance*flow)*math.exp(-p.dt/(p.resistance*p.compliance*60.))
        q=qnext
        rollout_error=max(rollout_error,float(np.max(np.abs(states[k+1]-[v,q,pressure]))))
        physical_violation=max(physical_violation,p.floor-v,v-p.ceiling,pressure-p.pressure_limit)
    physical_violation=max(physical_violation,p.floor+tail_factor(p.dt,p.tau)*q-v)
    actual_deficit=sum(max(0.,p.target[k]-p.conversion[k]*(states[k,1]+states[k+1,1])/2.) for k in range(p.horizon))*p.dt/60.
    objective=float(p.cost@x)
    slack_understatement=max(0.,actual_deficit-objective)
    valid=max(violation,rollout_error,physical_violation,slack_understatement)<=tolerance
    return dict(valid=bool(valid),matrix_violation=violation,rollout_error=rollout_error,
        physical_violation=max(0.,physical_violation),actual_deficit=actual_deficit,
        objective=objective,slack_understatement=slack_understatement)


class HorizonSolver:
    """Retained OSQP workspace, or an independent HiGHS LP reference.

    Rejected plans return command=None; there is no invented safe fallback here.
    A future runtime must own independent protection and validated backup actions.
    The deadline rejects late answers; Python cannot guarantee hard real time.
    """
    def __init__(self,backend='highs',deadline_s=1.):
        if backend not in ('highs','osqp') or not math.isfinite(deadline_s) or deadline_s<=0:
            raise ValueError('Invalid solver configuration')
        self.backend=backend;self.deadline=deadline_s;self.workspace=None;self.pattern=None

    def solve(self,problem):
        start=perf_counter();p=problem;status='exception';vector=None
        try:
            if self.backend=='highs':
                equality=np.isfinite(p.lower)&(p.lower==p.upper)
                high=np.isfinite(p.upper)&~equality;low=np.isfinite(p.lower)&~equality
                result=linprog(p.cost,A_ub=sparse.vstack([p.A[high],-p.A[low]]),
                    b_ub=np.r_[p.upper[high],-p.lower[low]],A_eq=p.A[equality],b_eq=p.lower[equality],
                    bounds=[(None,None)]*len(p.cost),method='highs',options={'time_limit':self.deadline})
                status='solved' if result.success else f'highs_{result.status}'
                vector=result.x if result.success else None
            else:
                import osqp
                pattern=(p.A.shape,p.A.indptr.tobytes(),p.A.indices.tobytes())
                if self.workspace is None or pattern!=self.pattern:
                    self.workspace=osqp.OSQP()
                    self.workspace.setup(P=sparse.csc_matrix((len(p.cost),len(p.cost))),q=p.cost,
                        A=p.A,l=p.lower,u=p.upper,verbose=False,eps_abs=1e-8,eps_rel=1e-8,
                        max_iter=100000,time_limit=self.deadline,polishing=True,warm_starting=True)
                    self.pattern=pattern
                else:self.workspace.update(q=p.cost,Ax=p.A.data,l=p.lower,u=p.upper)
                result=self.workspace.solve(raise_error=False)
                status=result.info.status
                vector=result.x if result.info.status_val==1 else None
        except Exception as error:
            status=f'exception:{type(error).__name__}'
        checks=validate_plan(p,vector) if vector is not None else dict(valid=False,reason=status)
        elapsed=perf_counter()-start
        accepted=bool(checks['valid'] and elapsed<=self.deadline)
        if not accepted and self.backend=='osqp':self.workspace=None;self.pattern=None
        return dict(accepted=accepted,command=float(vector[p.command_start]) if accepted else None,
            status=status,elapsed_s=elapsed,deadline_s=self.deadline,checks=checks,
            vector=vector.tolist() if accepted else None)
