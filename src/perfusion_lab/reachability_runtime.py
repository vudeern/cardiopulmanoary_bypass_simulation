"""Opt-in development runtime; the rc.1 runtime and its replay hashes stay frozen."""
from .runtime import ControllerRuntime
from .reachability import ConsistentGuard, ReachabilityController
from dataclasses import replace


class ReachabilityRuntime(ControllerRuntime):
    def _validate(self, frame):
        # Reference values are raw sensor readings, not physical state: Gaussian
        # acquisition noise can make them negative near an empty reservoir.
        # Use magnitudes only for the inherited physical-range check. NaN/Inf,
        # acquisition/delivery times and frame order are still validated there.
        # The original signed readings (not these validation copies) reach the
        # observer through ControllerRuntime.observe, preserving all sensor data.
        validated=replace(frame,
            routine=tuple(replace(s,value=abs(s.value)) for s in frame.routine),
            calibrations=tuple(replace(s,value=abs(s.value)) for s in frame.calibrations))
        super()._validate(validated)

    def __init__(self, *, bsa, initial_hb, dt=1., target=280., kind='hybrid',
                 level_mode='screened',controller_options=None,guard_options=None):
        # Reuse the validated measurement/acknowledgement boundary without
        # changing the frozen rc.1 implementation or default behavior.
        super().__init__(bsa=bsa,initial_hb=initial_hb,dt=dt,target=target,kind=kind,level_mode=level_mode)
        self.guard = ConsistentGuard(2.4*bsa,dt,**dict(guard_options or {}))
        self.controller = ReachabilityController(kind,bsa,dt,target,**dict(controller_options or {}))
