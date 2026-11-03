"""Orchestration separates plant truth, measurements, belief and decisions."""
from dataclasses import asdict, replace
import math
import numpy as np
from .model import Patient, Plant, Scenario, SCENARIOS, delivery
from .sensing import Sensors, Twin
from .control import Controller


def simulate(scenario='compound', policy='sentinel', seed=7, duration=1200., dt=2.,
             target=280., patient=None, lab_period=180., controller_options=None,
             plant_options=None,level_mode='ignore',level_reference_options=None,
             level_observer_options=None,controller_kind='forecast',venous_measurement=None):
    """Return aligned step-end truth and step-start information/action logs.

    All metrics integrate actual step-average pump delivery. No ground-truth
    value is supplied to the observer except the explicitly modeled lab channel.
    A row's measured/estimated quantities are from time-dt; its truth is at time.
    """
    if isinstance(scenario, str):
        if scenario not in SCENARIOS:
            raise ValueError(f'Unknown scenario {scenario}')
        scenario = SCENARIOS[scenario]
    if not isinstance(scenario, Scenario):
        raise ValueError('scenario must be a known name or a Scenario')
    if not all(math.isfinite(x) and x>0 for x in (duration, dt, target, lab_period)):
        raise ValueError('duration, dt, target and lab_period must be finite and positive')
    if dt>5. or not math.isclose(duration/dt, round(duration/dt), abs_tol=1e-9):
        raise ValueError('Use dt <= 5 seconds and a duration divisible by dt')
    p = patient if patient is not None else Patient.sampled(seed)
    plant_options = dict(plant_options or {})
    if plant_options:
        from .stress import StressPlant
        plant = StressPlant(p, **plant_options)
    else:
        plant = Plant(p)
    if scenario.dilution >= p.hb:
        raise ValueError('Scenario dilution must leave positive hemoglobin')
    sensors = Sensors(seed+10000, lab_period=lab_period)
    twin = Twin(p.hb, calibrate=policy!='no_calibration', guard_level=policy=='sentinel_guarded')
    controller_options = dict(controller_options or {})
    venous_options=dict(venous_measurement or {})
    if set(venous_options)-{'noise_sd','bias'}:
        raise ValueError('Unknown venous measurement settings')
    if venous_measurement is not None:
        if not all(math.isfinite(v) for v in venous_options.values()) or venous_options.get('noise_sd',.015)<0:
            raise ValueError('Invalid venous measurement settings')
    if controller_kind=='published_adapted' and venous_measurement is None:
        raise ValueError('Published adaptation requires an explicit venous measurement channel')
    if controller_kind=='selective':
        if policy!='sentinel' or venous_measurement is None:
            raise ValueError('Selective PI requires common observer and explicit venous sensor')
        from .selective import SelectiveController
        controller=SelectiveController(p.bsa,dt,target,**controller_options)
    elif controller_kind=='continuity':
        if policy!='sentinel' or venous_measurement is None:
            raise ValueError('Continuity controller requires common observer and venous sensor')
        from .continuity import ContinuityController
        controller=ContinuityController(p.bsa,dt,target,**controller_options)
    elif controller_kind=='braking':
        if policy!='sentinel' or venous_measurement is None:
            raise ValueError('Braking controller requires the common observer and explicit venous sensor')
        from .braking import BrakingController
        controller=BrakingController(p.bsa,dt,target,**controller_options)
    elif controller_kind=='published_adapted':
        if policy!='sentinel':raise ValueError('Published adaptation uses the common observer')
        from .published_control import PublishedLevelAdapter
        controller=PublishedLevelAdapter(p.bsa,dt,**controller_options)
    elif controller_kind in ('simc','matched_forecast'):
        if policy!='sentinel':raise ValueError('Matched controllers use the common observer')
        from .simc import MatchedSupervisor
        controller=MatchedSupervisor('simc' if controller_kind=='simc' else 'forecast',
            p.bsa,dt,target,**controller_options)
    elif controller_kind=='forecast':
        controller = Controller(policy, p.bsa, dt, target, **controller_options)
    else:
        if policy!='sentinel':raise ValueError('Feedback baselines use sentinel Hb observation')
        from .feedback import LevelFeedback
        controller=LevelFeedback(controller_kind,p.bsa,dt,target,**controller_options)
    if level_mode not in ('ignore','hold','bounded'):
        raise ValueError('Unknown level reference mode')
    if level_mode!='ignore' and policy!='sentinel':
        raise ValueError('Reference-aware methods use original sentinel as the common controller')
    reference_sensor=reference_filter=None
    if level_reference_options is not None or level_mode!='ignore':
        from .reference import LevelReferences,ReferenceLevel
        reference_sensor=LevelReferences(seed+50000,**dict(level_reference_options or {}))
        if level_mode!='ignore':
            reference_filter=ReferenceLevel(level_mode,**dict(level_observer_options or {}))
    state = dict(flow=plant.flow, reservoir=plant.reservoir, pressure=plant.pressure)
    venous_rng=np.random.default_rng(seed+70000)
    rows = []
    for k in range(round(duration/dt)):
        t = k*dt
        inputs = scenario.inputs(t, duration)
        hb = p.hb-inputs['hb_loss']
        obs = sensors.observe(t, state, hb, inputs)
        samples=reference_sensor.observe(t,state['reservoir'],inputs['reservoir_bias']) if reference_sensor else []
        reference_level=reference_filter.update(obs,samples) if reference_filter else None
        belief = twin.update(obs)
        measured_venous=None
        if venous_measurement is not None:
            # Current sensor acquisition, before advancing plant/controller time.
            # For lagged drainage the state is current flow, not future-step average.
            current_venous=(plant.drainage_state if getattr(plant,'drainage_tau',0.)
                            else plant.venous_return(inputs['drainage']))
            measured_venous=max(0.,current_venous+venous_options.get('bias',0.)+
                venous_options.get('noise_sd',.015)*venous_rng.normal())
            belief=replace(belief,venous_flow=measured_venous)
        control_obs=replace(obs,reservoir=reference_level['lower']) if reference_level else obs
        if reference_level is not None:
            control_obs=replace(control_obs,level_reference_age=reference_level['age'] if reference_level else None,
                level_reference_bias=reference_level['bias'] if reference_level else 0.)
        if controller_kind in ('selective','continuity'):controller.observe_references(samples)
        decision = controller.decide(control_obs, belief)
        state = plant.step(decision.command, inputs['drainage'], dt)
        do2 = delivery(state['flow'], hb, inputs['sao2'], p.bsa)
        demand = p.demand37 * p.q10**((inputs['temperature']-37.)/10.)
        # Physiologic debt proxy differs from an area below a fixed GDP target.
        # The 0.6 extraction ceiling is a synthetic assumption, not an AKI model.
        unmet = max(0., demand-.60*do2)
        measured_hb = obs.hb_inline if obs.hb_inline is not None else belief.hb
        rows.append(dict(time=t+dt, observation_time=t, **state, hb=hb,
                         observed_flow=obs.flow, observed_reservoir=obs.reservoir,
                         observed_venous_flow=measured_venous,
                         injected_level_bias=inputs['reservoir_bias'],
                         injected_flow_bias=inputs.get('flow_bias',0.),
                         level_reference=samples[-1].value if samples else None,
                         level_reference_acquired=samples[-1].acquired if samples else None,
                         level_reference_estimate=reference_level['estimate'] if reference_level else None,
                         level_reference_lower=reference_level['lower'] if reference_level else None,
                         level_reference_age=reference_level['age'] if reference_level else None,
                         level_reference_unknown=reference_level['unknown'] if reference_level else None,
                         hb_estimate=belief.hb, hb_lower=belief.hb_lower,
                         hb_upper=belief.hb_upper,
                         hb_inline=obs.hb_inline, sao2=inputs['sao2'],
                         temperature=inputs['temperature'], command=decision.command,
                         do2=do2, measured_do2=delivery(obs.flow, measured_hb, obs.sao2, p.bsa),
                         demand=demand, unmet_demand=unmet,
                         fault=belief.fault, stale=belief.stale,
                         level_fault=belief.level_fault, level_bias_estimate=belief.level_bias,
                         reservoir_lower=belief.reservoir_lower,
                         infeasible=decision.infeasible,
                         reference_age=belief.reference_age,
                         hb_covered=belief.hb_lower<=hb<=belief.hb_upper))
        if controller_kind in ('braking','continuity','selective'):rows[-1].update(controller.last_debug)
    values = lambda key: np.array([r[key] for r in rows], dtype=float)
    true_low = values('do2')<target
    # False reassurance compares a start-of-step monitor to its ensuing interval;
    # this includes genuine monitoring lag and is labeled as such in the docs.
    reassurance = true_low & (values('measured_do2')>=target)
    metrics = dict(deficit_auc=float(np.maximum(0., target-values('do2')).sum()*dt/60.),
                   below_target_s=float(true_low.sum()*dt),
                   false_reassurance_s=float(reassurance.sum()*dt),
                   false_reassurance_margin_s=float((reassurance & (values('do2')<target-5.)).sum()*dt),
                   concealed_deficit_auc=float((np.maximum(0.,target-values('do2'))*reassurance).sum()*dt/60.),
                   unmet_demand_auc=float(values('unmet_demand').sum()*dt/60.),
                   low_reservoir_s=float((values('reservoir')<.25).sum()*dt),
                   empty_request_s=float(values('empty_request').sum()*dt),
                   high_pressure_s=float((values('pressure')>95).sum()*dt),
                   infeasible_s=float(values('infeasible').sum()*dt),
                   hb_bound_coverage=float(values('hb_covered').mean()),
                   minimum_reservoir=float(values('reservoir').min()),
                   flow_variation=float(np.abs(np.diff(values('command'))).sum()),
                   mean_flow=float(values('flow').mean()))
    metrics['level_fault_s'] = float(values('level_fault').sum()*dt)
    return dict(scenario=scenario.name, scenario_parameters=asdict(scenario),
                policy=policy, controller_options=controller_options,
                controller_kind=controller_kind,venous_measurement=venous_measurement,
                seed=seed, dt=dt, lab_period=lab_period,
                plant_model=type(plant).__name__, plant_options=plant_options,
                level_mode=level_mode,level_reference_options=level_reference_options,
                level_observer_options=level_observer_options,
                duration=duration, target=target, patient=asdict(p), metrics=metrics,
                rows=rows)

