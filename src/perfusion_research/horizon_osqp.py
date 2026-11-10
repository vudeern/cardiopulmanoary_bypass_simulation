"""Equivalently scaled OSQP adapter for the frozen nominal LP formulation.

Unlike relaxing constraints or adding a regularizer, positive diagonal variable,
row and objective scaling preserves the original feasible set and LP optimum.
Answers are transformed back and checked in original physical units.
"""
import math
from time import perf_counter
import numpy as np
from scipy import sparse
from .horizon import validate_plan


def scaled_problem(p):
    scales=np.r_[np.tile([1.,p.max_command,p.pressure_limit],p.steps+1),
        np.full(p.steps,p.max_command),np.full(p.horizon,max(280.,float(max(p.target))))]
    matrix=p.A@sparse.diags(scales)
    norms=np.asarray(abs(matrix).max(axis=1).toarray()).ravel()
    row_scale=1./np.maximum(norms,1e-12)
    matrix=(sparse.diags(row_scale)@matrix).tocsc()
    cost=p.cost*scales;cost_scale=max(abs(cost));cost=cost/cost_scale
    return scales,matrix,p.lower*row_scale,p.upper*row_scale,cost


class ScaledOSQPSolver:
    def __init__(self,deadline_s=1.):
        if not math.isfinite(deadline_s) or deadline_s<=0:raise ValueError('Invalid deadline')
        self.deadline=deadline_s;self.workspace=None;self.pattern=None

    def solve(self,p):
        start=perf_counter();vector=None;status='exception'
        try:
            import osqp
            scales,A,lower,upper,cost=scaled_problem(p)
            pattern=(A.shape,A.indptr.tobytes(),A.indices.tobytes())
            if self.workspace is None or pattern!=self.pattern:
                self.workspace=osqp.OSQP()
                self.workspace.setup(P=sparse.csc_matrix((len(cost),len(cost))),q=cost,
                    A=A,l=lower,u=upper,verbose=False,eps_abs=1e-8,eps_rel=1e-8,
                    max_iter=100000,time_limit=self.deadline,polishing=True,warm_starting=True)
                self.pattern=pattern
            else:self.workspace.update(q=cost,Ax=A.data,l=lower,u=upper)
            result=self.workspace.solve(raise_error=False);status=result.info.status
            if result.info.status_val==1:vector=result.x*scales
        except Exception as error:status=f'exception:{type(error).__name__}'
        checks=validate_plan(p,vector) if vector is not None else dict(valid=False,reason=status)
        elapsed=perf_counter()-start;accepted=bool(checks['valid'] and elapsed<=self.deadline)
        if not accepted:self.workspace=None;self.pattern=None
        return dict(accepted=accepted,command=float(vector[p.command_start]) if accepted else None,
            status=status,elapsed_s=elapsed,deadline_s=self.deadline,checks=checks,
            vector=vector.tolist() if accepted else None)
