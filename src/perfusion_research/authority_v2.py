"""Opt-in nominal PI authority behind the independent stopping envelope.

Legacy observer fit is diagnostic, not an additional permission to request flow.
Both comparison arms use exactly the same nominal request and protection.
"""
import math
from perfusion_lab.control import Decision
from perfusion_lab.model import delivery
from .boot_v2 import BootRuntime


class AuthorityRuntime(BootRuntime):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        controller = self.controller
        original = controller.decide

        def decide(obs, belief):
            previous, nominal_flow = controller.previous, controller.nominal_flow
            legacy = original(obs, belief)
            low = max(0., previous - .15 * self.dt)
            high = controller.last_debug['decision_high']
            cap, feasible = self.envelope.cap(low, high)
            # The recorded request precedes all legacy and independent caps.
            # Pressure, demand, range and slew constraints remain in high/low.
            request = controller._nominal_request
            applied = min(high, max(low, min(request, cap))) if feasible else low
            controller.pi.core.track(applied)
            controller.pi.previous = controller.previous = applied
            controller.nominal_flow = applied + (nominal_flow-applied)*math.exp(-self.dt/2.)
            controller.last_debug.update(
                authority_legacy_command=legacy.command, nominal_request=request,
                independent_authority=feasible, decision_cap=cap,
                envelope_cap=cap, envelope_feasible=feasible,
                envelope_margin=self.envelope.margin(applied),
                envelope_clipped=applied < request-1e-7,
                authority_action_changed=abs(applied-legacy.command)>1e-7,
                protection_active=applied < request-1e-9,
                applied_within_shared_cap=applied <= min(high, cap)+1e-7)
            return Decision(applied, not feasible,
                            delivery(applied, belief.hb_lower, obs.sao2, controller.bsa))

        controller.decide = decide
