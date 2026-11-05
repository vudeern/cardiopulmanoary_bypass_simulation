"""Opt-in development runtime; the rc.1 runtime and its replay hashes stay frozen."""
from .runtime import ControllerRuntime
from .reachability import ConsistentGuard, ReachabilityController


class ReachabilityRuntime(ControllerRuntime):
    def __init__(self, *, bsa, initial_hb, dt=1., target=280., kind='hybrid',
                 level_mode='screened',controller_options=None,guard_options=None):
        # Reuse the validated measurement/acknowledgement boundary without
        # changing the frozen rc.1 implementation or default behavior.
        super().__init__(bsa=bsa,initial_hb=initial_hb,dt=dt,target=target,kind=kind,level_mode=level_mode)
        self.guard = ConsistentGuard(2.4*bsa,dt,**dict(guard_options or {}))
        self.controller = ReachabilityController(kind,bsa,dt,target,**dict(controller_options or {}))
