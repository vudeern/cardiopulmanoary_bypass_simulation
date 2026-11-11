"""Simulation-only startup fixtures; historical plant equations remain frozen."""
from contextlib import contextmanager
import perfusion_candidates.calibrated_pump as runtime_module
import perfusion_candidates.calibrated_pump_simulation as simulation
import perfusion_lab.stress as stress
from .boot_v2 import BootRuntime


@contextmanager
def startup_fixture(state):
    if state not in ('cold','hot','unprimed'):raise ValueError('Unknown initial-state fixture')
    original_plant,original_stress,original_runtime=simulation.Plant,stress.StressPlant,runtime_module.CalibratedPumpRuntime
    def initialize(plant):
        if state!='hot':plant.flow=0.;plant.pressure=0.
        if state=='unprimed':plant.reservoir=.35
        if hasattr(plant,'drainage_state'):plant.drainage_state=plant.venous_return(1.)
    class InitialPlant(original_plant):
        def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);initialize(self)
    class InitialStressPlant(original_stress):
        def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);initialize(self)
    simulation.Plant=InitialPlant;stress.StressPlant=InitialStressPlant;runtime_module.CalibratedPumpRuntime=BootRuntime
    try:yield
    finally:simulation.Plant=original_plant;stress.StressPlant=original_stress;runtime_module.CalibratedPumpRuntime=original_runtime


def simulate_boot(*args,startup_state='cold',**kwargs):
    with startup_fixture(startup_state):return simulation.simulate_calibrated_pump(*args,**kwargs)
