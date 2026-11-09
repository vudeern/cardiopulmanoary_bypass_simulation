"""Offline taps and counterfactual decisions; production controllers unchanged."""
import copy
from dataclasses import replace
from unittest.mock import patch
from .integrity import IntegrityController
from .sensing import Sensors
from .model import delivery
from .stress import StressPlant
from .audit import emergency_feasible,pressure_envelope


def audit_run(run_function,patient,scenario,plant_options,mode='observed',record_decisions=False):
    """Run the original orchestration with explicit diagnostic-only input taps.

    The two closed-loop ablations remove the engineering interval or supply
    exact current reservoir volume. Both may violate protection constraints.
    Local probes fork the identical pre-decision controller and physical state;
    their immediate gains cannot be summed as one achievable trajectory.
    """
    if mode not in ('observed','margin_removed','true_volume'):raise ValueError('Unknown audit mode')
    holder={};events=[];physical=StressPlant(patient,**plant_options)
    future=[scenario.inputs(t,600.) for t in range(600)]
    limits=pressure_envelope(patient,1.,600,physical.actuator_tau)
    counters=dict(decision_steps=0,slowdown_steps=0,below_target_steps=0,
        uncertainty_raises_command_steps=0,true_volume_raises_command_steps=0,
        support_gate_raises_command_steps=0,local_safe_higher_oxygen_steps=0,
        slowdown_local_safe_higher_oxygen_steps=0,guard_lower_above_truth_steps=0,
        observed_pressure_slowdown_steps=0)
    errors=[];widths=[]

    class TappedSensors(Sensors):
        def observe(self,t,state,hb,inputs):
            holder.update(truth=dict(state),hb=hb,inputs=inputs)
            return super().observe(t,state,hb,inputs)

    class TappedController(IntegrityController):
        def decide(self,obs,belief):
            truth=holder['truth']['reservoir'];previous=self.previous
            before=copy.deepcopy(self) if record_decisions else None
            supplied=obs
            if mode=='margin_removed':supplied=replace(obs,reservoir=self.reference_state['estimate'])
            elif mode=='true_volume':supplied=replace(obs,reservoir=truth)
            action=super().decide(supplied,belief)
            if record_decisions:
                k=round(obs.time);assert abs(physical.reservoir-truth)<1e-8
                point=IntegrityController.decide(copy.deepcopy(before),replace(obs,reservoir=before.reference_state['estimate']),belief).command
                exact=IntegrityController.decide(copy.deepcopy(before),replace(obs,reservoir=truth),belief).command
                relaxed=copy.deepcopy(before);relaxed.reference_state={**relaxed.reference_state,'supported':True}
                gate=IntegrityController.decide(relaxed,obs,belief).command
                actual=copy.copy(physical);actual_state=actual.step(action.command,future[k]['drainage'],1.)
                actual_do2=delivery(actual_state['flow'],holder['hb'],holder['inputs']['sao2'],patient.bsa)
                probes=[('remove_interval',point),('exact_volume',exact),('enable_support',gate),('higher_command',min(7.,previous+.15))]
                accepted=[]
                for label,u in probes:
                    if u<=action.command+1e-9:continue
                    if actual_do2>=280.:continue
                    if not emergency_feasible(physical,previous,u,k,future,limits):continue
                    other=copy.copy(physical);step=other.step(u,future[k]['drainage'],1.)
                    other_do2=delivery(step['flow'],holder['hb'],holder['inputs']['sao2'],patient.bsa)
                    gain=(max(0.,280.-actual_do2)-max(0.,280.-other_do2))/60.
                    if gain>1e-10:accepted.append(dict(probe=label,command=u,immediate_deficit_reduction=gain))
                down=action.command<previous-1e-9
                counters['decision_steps']+=1;counters['slowdown_steps']+=int(down)
                counters['below_target_steps']+=int(actual_do2<280.)
                counters['uncertainty_raises_command_steps']+=int(point>action.command+1e-9)
                counters['true_volume_raises_command_steps']+=int(exact>action.command+1e-9)
                counters['support_gate_raises_command_steps']+=int(gate>action.command+1e-9)
                counters['local_safe_higher_oxygen_steps']+=bool(accepted)
                counters['slowdown_local_safe_higher_oxygen_steps']+=bool(accepted and down)
                counters['guard_lower_above_truth_steps']+=int(obs.reservoir>truth+1e-9)
                counters['observed_pressure_slowdown_steps']+=int(obs.pressure>90.)
                errors.append(obs.reservoir-truth);widths.append(before.reference_state['uncertainty'])
                if down or accepted:events.append(dict(time=obs.time,command=action.command,previous=previous,
                    true_volume=truth,guard_lower=obs.reservoir,point_estimate=before.reference_state['estimate'],
                    uncertainty=before.reference_state['uncertainty'],pressure=obs.pressure,
                    supported=before.reference_state['supported'],pi_command=self.last_debug['pi_command'],
                    point_command=point,exact_volume_command=exact,support_enabled_command=gate,
                    local_verified_probes=accepted))
                physical.step(action.command,future[k]['drainage'],1.)
            return action

    with patch('perfusion_lab.simulation.Sensors',TappedSensors),patch('perfusion_lab.integrity.IntegrityController',TappedController):
        result=run_function()
    envelope_excess=sum(r['pressure']>limits[k]+1e-8 for k,r in enumerate(result['rows']))
    result['audit_feasible']=not (result['metrics']['low_reservoir_s'] or result['metrics']['empty_request_s'] or envelope_excess)
    result['pressure_envelope_excess_s']=envelope_excess
    if record_decisions:
        counters.update(mean_guard_lower_error=sum(errors)/len(errors),mean_interval_width=sum(widths)/len(widths))
    result['audit_counters']=counters;result['audit_events']=events
    return result
