"""Offline truth-informed witnesses and optimistic LP bounds.

These diagnostics receive plant parameters/state and future disturbances. They
are not sensor-based controllers or clinical recommendations. The witness is a
feasible heuristic, not a globally optimal policy. The LP relaxes drainage and
storage and therefore cannot be replayed as a physical controller.
"""
import copy,math
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from .model import delivery,oxygen_content
from .stress import StressPlant

FLOOR=.25


def pressure_envelope(patient,dt,n,actuator_tau):
    """Smallest reachable pressure transient from mandated initial pump state."""
    u=x=2.4*patient.bsa;p=x*patient.resistance
    aa=math.exp(-dt/actuator_tau);ap=math.exp(-dt/(patient.resistance*patient.compliance*60.))
    limits=[]
    for _ in range(n):
        u=max(0.,u-.15*dt);next_x=u+(x-u)*aa
        p=ap*p+(1-ap)*patient.resistance*(x+next_x)/2.;x=next_x
        limits.append(max(95.,p))
    return np.array(limits)


def emergency_feasible(plant,previous,command,start,inputs,limits,dt=1.,horizon=60.,floor=FLOOR+1e-5):
    """Candidate then fastest slowdown, exact future inputs, certified quiet tail.

    Only establishes that this particular continuation is feasible. Failure is
    not a proof that no other safe continuation exists.
    """
    if not 0.<=command<=7. or plant.reservoir<floor-1e-9 or abs(command-previous)>.15*dt+1e-9:return False
    p=copy.copy(plant);u=command;stop=min(len(inputs),start+max(1,round(horizon/dt)))
    for k in range(start,stop):
        if k>start:u=max(0.,u-.15*dt)
        state=p.step(u,inputs[k]['drainage'],dt)
        if state['reservoir']<floor-1e-9 or state['empty_request'] or state['pressure']>limits[k]+1e-8:return False
    if stop==len(inputs):return True
    # After command reaches zero, no inflow is needed to bound the remaining
    # loss. The discrete trapezoidal pump tail is a geometric series;
    # continuous tau*x/60 would underestimate this simulator's transfer.
    # Pressure then cannot rise
    # above max(current pressure, R*x). All future venous return is nonnegative.
    decay=math.exp(-dt/p.actuator_tau)
    residual_loss=p.flow*dt/120.*(1.+decay)/(1.-decay)
    return (u<=1e-12 and p.reservoir-residual_loss>=floor
            and max(p.pressure,p.flow*p.p.resistance)<=95.+1e-8)


def witness(patient,scenario,plant_options,duration=600.,dt=1.,horizon=60.,candidates=9,oxygen_cap=True):
    plant=StressPlant(patient,**plant_options);n=round(duration/dt)
    inputs=[scenario.inputs(k*dt,duration) for k in range(n)]
    limits=pressure_envelope(patient,dt,n,plant.actuator_tau);previous=plant.flow;rows=[];misses=0
    for k in range(n):
        low=max(0.,previous-.15*dt);high=min(7.,previous+.15*dt)
        if oxygen_cap:
            need=280.*patient.bsa/(10.*oxygen_content(patient.hb-inputs[k]['hb_loss'],inputs[k]['sao2']))
            high=max(low,min(high,need))
        options=np.linspace(high,low,candidates)
        chosen=None
        for u in options:
            if emergency_feasible(plant,previous,float(u),k,inputs,limits,dt,horizon):chosen=float(u);break
        if chosen is None:chosen=low;misses+=1
        state=plant.step(chosen,inputs[k]['drainage'],dt);previous=chosen
        do2=delivery(state['flow'],patient.hb-inputs[k]['hb_loss'],inputs[k]['sao2'],patient.bsa)
        rows.append(dict(time=(k+1)*dt,observation_time=k*dt,command=chosen,do2=do2,**state,pressure_allowance=float(limits[k])))
    feasible=(all(r['reservoir']>=FLOOR-1e-9 and not r['empty_request'] and r['pressure']<=r['pressure_allowance']+1e-8 for r in rows))
    metrics=dict(deficit_auc=sum(max(0.,280.-r['do2']) for r in rows)*dt/60.,
        low_reservoir_s=sum(r['reservoir']<FLOOR for r in rows)*dt,
        empty_request_s=sum(r['empty_request'] for r in rows)*dt,
        high_pressure_s=sum(r['pressure']>95. for r in rows)*dt,
        pressure_envelope_excess_s=sum(r['pressure']>r['pressure_allowance']+1e-8 for r in rows)*dt,
        minimum_reservoir=min(r['reservoir'] for r in rows),mean_flow=float(np.mean([r['flow'] for r in rows])),
        flow_variation=sum(abs(b['command']-a['command']) for a,b in zip(rows,rows[1:])),
        below_target_s=sum(r['do2']<280. for r in rows)*dt)
    return dict(rows=rows,metrics=metrics,feasible=feasible,no_verified_continuation_steps=misses)


def relaxation(patient,scenario,plant_options,duration=600.,dt=1.):
    """Sparse linear relaxation with optimistic maximum drainage at floor."""
    n=round(duration/dt);p=patient;plant=StressPlant(p,**plant_options)
    inputs=[scenario.inputs(k*dt,duration) for k in range(n)]
    limits=pressure_envelope(p,dt,n,plant.actuator_tau)
    aa=math.exp(-dt/plant.actuator_tau);ap=math.exp(-dt/(p.resistance*p.compliance*60.))
    qstate=plant.drainage_state;qin=[]
    for inp in inputs:
        filling=max(0.,(p.volume-FLOOR-p.unstressed_volume)/p.venous_compliance)
        upper=min(plant.max_drainage,inp['drainage']*filling/(p.venous_resistance*(1.+plant.venous_nonlinearity*filling)))
        if plant.drainage_tau:
            a=math.exp(-dt/plant.drainage_tau)
            average=upper+(qstate-upper)*plant.drainage_tau/dt*(1.-a)
            qstate=upper+(qstate-upper)*a
        else:average=upper
        qin.append(average)
    # x = [commands, end actuator flows, end pressure, relaxed volume, deficit].
    size=5*n;er=[];ec=[];ev=[];be=[];ur=[];uc=[];uv=[];bu=[]
    def eq(terms,b):
        row=len(be);be.append(b)
        for j,v in terms.items():er.append(row);ec.append(j);ev.append(v)
    def ub(terms,b):
        row=len(bu);bu.append(b)
        for j,v in terms.items():ur.append(row);uc.append(j);uv.append(v)
    initial_x=plant.flow;initial_p=plant.pressure;initial_v=plant.reservoir
    for k in range(n):
        u=k;x=n+k;pr=2*n+k;v=3*n+k;d=4*n+k
        if k:
            eq({x:1.,n+k-1:-aa,u:-(1-aa)},0.)
            eq({pr:1.,2*n+k-1:-ap,n+k-1:-(1-ap)*p.resistance/2.,x:-(1-ap)*p.resistance/2.},0.)
            eq({v:1.,3*n+k-1:-1.,n+k-1:dt/120.,x:dt/120.},qin[k]*dt/60.)
            ub({u:1.,k-1:-1.},.15*dt);ub({u:-1.,k-1:1.},.15*dt)
        else:
            eq({x:1.,u:-(1-aa)},aa*initial_x)
            eq({pr:1.,x:-(1-ap)*p.resistance/2.},ap*initial_p+(1-ap)*p.resistance*initial_x/2.)
            eq({v:1.,x:dt/120.},initial_v+qin[k]*dt/60.-initial_x*dt/120.)
            ub({u:1.},initial_x+.15*dt);ub({u:-1.},-initial_x+.15*dt)
        c=10.*oxygen_content(p.hb-inputs[k]['hb_loss'],inputs[k]['sao2'])/p.bsa
        terms={d:-1.,x:-c/2.}
        if k:terms[n+k-1]=-c/2.;rhs=-280.
        else:rhs=-280.+c*initial_x/2.
        ub(terms,rhs)
    aeq=coo_matrix((ev,(er,ec)),shape=(len(be),size)).tocsr();aub=coo_matrix((uv,(ur,uc)),shape=(len(bu),size)).tocsr()
    lower=np.r_[np.zeros(3*n),np.full(n,FLOOR),np.zeros(n)]
    # An upper bound on the relaxed buffer prevents unbounded residual-error
    # terms in the dual check; it cannot exclude a relaxed mass trajectory.
    vmax=initial_v+sum(qin)*dt/60.
    upper=np.r_[np.full(2*n,7.),limits,np.full(n,vmax),np.full(n,280.)]
    cost=np.r_[np.zeros(4*n),np.full(n,dt/60.)]
    return dict(c=cost,A_eq=aeq,b_eq=np.array(be),A_ub=aub,b_ub=np.array(bu),lb=lower,ub=upper,n=n,drainage_upper=np.array(qin),pressure_envelope=limits)


def dual_lower_bound(problem,result):
    """Sign-clipped dual plus a finite-box correction for stationarity error.

    Numerical check with an outward safety subtraction, not interval arithmetic.
    """
    if np.any(problem['c']<0):raise ValueError('Deficit-bound helper requires nonnegative objective coefficients')
    y=np.asarray(result.eqlin.marginals);z=np.minimum(0.,result.ineqlin.marginals)
    lo=np.maximum(0.,result.lower.marginals);hi=np.minimum(0.,result.upper.marginals)
    residual=problem['c']-problem['A_eq'].T@y-problem['A_ub'].T@z-lo-hi
    raw=float(problem['b_eq']@y+problem['b_ub']@z+problem['lb']@lo+problem['ub']@hi)
    correction=float(np.minimum(residual*problem['lb'],residual*problem['ub']).sum())
    lower=max(0.,raw+correction-1e-7)
    primal=max(float(np.max(np.abs(problem['A_eq']@result.x-problem['b_eq']),initial=0.)),
               float(np.max(problem['A_ub']@result.x-problem['b_ub'],initial=0.)),
               float(np.max(problem['lb']-result.x)),float(np.max(result.x-problem['ub'])))
    return dict(lower_bound=lower,objective=float(result.fun),dual_box_correction=correction,
                stationarity_max=float(np.max(np.abs(residual))),primal_residual_max=primal,
                primal_minus_checked_bound=float(result.fun-lower))


def physical_bound(patient,scenario,plant_options,duration=600.,dt=1.):
    problem=relaxation(patient,scenario,plant_options,duration,dt)
    result=linprog(problem['c'],A_ub=problem['A_ub'],b_ub=problem['b_ub'],A_eq=problem['A_eq'],b_eq=problem['b_eq'],bounds=list(zip(problem['lb'],problem['ub'])),method='highs-ds',options=dict(primal_feasibility_tolerance=1e-9,dual_feasibility_tolerance=1e-9))
    if not result.success:return dict(success=False,status=int(result.status),message=result.message)
    check=dual_lower_bound(problem,result)
    assert check['primal_residual_max']<1e-6 and check['lower_bound']<=check['objective']+1e-6
    return dict(success=True,status=0,**check)
