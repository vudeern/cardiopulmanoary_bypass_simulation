"""Read-only decision instrumentation around the unchanged rc.5 algorithm."""
import math
from perfusion_candidates.calibrated_pump import CalibratedPumpController
from perfusion_candidates.finite_return import finite_return_reserve
from perfusion_lab.model import oxygen_content


class TracedController(CalibratedPumpController):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.nominal_flow=2.4*self.bsa

    def decide(self,obs,belief):
        previous=self.previous;state=self.reference_state
        result=super().decide(obs,belief)
        low=max(0.,previous-.15*self.dt);slew_high=min(7.,previous+.15*self.dt)
        oxygen_flow=self.target*self.bsa/(10.*oxygen_content(belief.hb_lower,obs.sao2))
        high=max(low,min(slew_high,oxygen_flow))
        if obs.pressure>90.:high=low
        supported=bool(state['bank_supported'] and state.get('pump_models'))
        budget=max(0.,obs.reservoir-.29) if supported else 0.
        qin=self.last_debug['protection_inflow_floor']
        loss=lambda u:finite_return_reserve(state.get('pump_models',()),u,qin,self.return_horizon_s,self.dt)
        feasible=supported and obs.reservoir>=.29 and loss(low)<=budget
        cap=low
        if feasible:
            cap=high
            if loss(high)>budget:
                left,right=low,high
                for _ in range(18):
                    mid=(left+right)/2.
                    if loss(mid)<=budget:left=mid
                    else:right=mid
                cap=left
        near=lambda a,b:abs(a-b)<=1e-5
        if not supported:reason='unsupported_calibration'
        elif obs.pressure>90.:reason='pressure_slowdown'
        elif cap<high-1e-5 and near(result.command,cap):reason='stopping_reserve'
        elif oxygen_flow<=slew_high and oxygen_flow>=low and near(result.command,high):reason='oxygen_cap'
        elif near(result.command,slew_high):reason='up_slew'
        elif near(result.command,low):reason='down_slew'
        else:reason='controller_choice'
        self.last_debug.update(limit_reason=reason,decision_cap=cap,decision_high=high,
            command_headroom=max(0.,min(high,cap)-result.command),nominal_flow_start=self.nominal_flow,
            point_volume_start=state['estimate'],measured_pressure_start=obs.pressure,
            measured_return_start=belief.venous_flow,previous_command=previous)
        self.nominal_flow=result.command+(self.nominal_flow-result.command)*math.exp(-self.dt/2.)
        return result
