"""Offline local sensitivity diagnostics, never a controller or safety bound.

Uses the existing StressPlant, frozen commands and actual reference scheduler.
Other patient parameters and the scripted disturbance profile are held known:
full local rank here is only an optimistic diagnostic, not an identification proof.
"""
from dataclasses import replace
import numpy as np
from .stress import StressPlant
from .reference import LevelReferences


PARAMETERS = ('initial_volume', 'inline_bias', 'venous_bias', 'pump_tau',
              'unstressed_volume', 'common_level_bias', 'flow_bias')
SCALES = np.array([.1, .1, .3, 2., .1, .1, .3])
MODES = ('healthy', 'reference_outage', 'calibration_missing', 'shared_unknown')


def trajectory(patient, scenario, commands, *, tau=2., delta=None, dt=1., venous_bias=0.):
    """Return expected measurement means at step starts; no added random noise.

    delta has physical units in PARAMETERS order. The common offset affects
    every level channel. Each returned reference retains its actual acquisition
    and delivery time. Noise SDs below are whitening scales, not hard bounds.
    """
    commands = np.asarray(commands, dtype=float)
    delta = np.zeros(7) if delta is None else np.asarray(delta, dtype=float)
    if (commands.ndim != 1 or not len(commands) or delta.shape != (7,)
            or not np.isfinite(commands).all() or not np.isfinite(delta).all()
            or (commands < 0).any() or (commands > 7).any()
            or not np.isfinite(dt) or not 0 < dt <= 5 or not np.isfinite(venous_bias)
            or not np.isfinite(tau) or tau+delta[3] <= 0):
        raise ValueError('Invalid sensitivity experiment')
    p = replace(patient, unstressed_volume=patient.unstressed_volume+delta[4])
    plant = StressPlant(p, actuator_tau=tau+delta[3])
    plant.reservoir += delta[0]
    if not 0 < plant.reservoir < p.volume:
        raise ValueError('Initial volume outside plant')
    routine = LevelReferences(0, period=60., delay=4., noise_sd=0.)
    calibration = LevelReferences(0, period=120., delay=6., noise_sd=0.)
    duration = len(commands)*dt
    records = []
    state = dict(flow=plant.flow, reservoir=plant.reservoir, pressure=plant.pressure)
    for k, command in enumerate(commands):
        t = k*dt
        inputs = scenario.inputs(t, duration)
        noise_scale = inputs.get('level_noise_scale', 1.)
        values = (
            ('inline', max(0., state['reservoir']+inputs['reservoir_bias']+delta[1]+delta[5]), .003*noise_scale),
            ('flow', max(0., state['flow']+inputs.get('flow_bias', 0.)+delta[6]),
             .015*inputs.get('flow_noise_scale', 1.)),
            ('venous', max(0., plant.venous_return(inputs['drainage'])+venous_bias+delta[2]), .015),
            ('pressure', state['pressure'], .25))
        for channel, value, sd in values:
            records.append((t, t, channel, value, sd))
        for channel, sensor in (('routine', routine), ('calibration', calibration)):
            for sample in sensor.observe(t, state['reservoir']+delta[5]):
                records.append((t, sample.acquired, channel, sample.value, .01))
        state = plant.step(float(command), inputs['drainage'], dt)
    return records


def sensitivity(patient, scenario, commands, *, tau=2., epsilon=1e-3, venous_bias=0.):
    """Central differences wrt dimensionless parameters scaled by SCALES."""
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError('epsilon must be positive')
    base = trajectory(patient, scenario, commands, tau=tau, venous_bias=venous_bias)
    columns = []
    for i, scale in enumerate(SCALES):
        perturbation = np.zeros(7)
        perturbation[i] = epsilon*scale
        plus = trajectory(patient, scenario, commands, tau=tau, delta=perturbation, venous_bias=venous_bias)
        minus = trajectory(patient, scenario, commands, tau=tau, delta=-perturbation, venous_bias=venous_bias)
        columns.append([(a[3]-b[3])/(2*epsilon*a[4]) for a, b in zip(plus, minus)])
    return base, np.column_stack(columns)


def diagnose(records, jacobian, mode, cutoff):
    """SVD of available whitened rows, with explicit nuisance parameters.

    Healthy anchors fix the common level offset; other modes estimate it.
    The outage masks routine acquisitions in [150,480), preserving packets
    acquired before the outage and delivered during it.
    """
    if mode not in MODES:
        raise ValueError('Unknown information mode')
    mask = np.array([r[0] <= cutoff and
        not (mode == 'calibration_missing' and r[2] == 'calibration') and
        not (mode == 'reference_outage' and r[2] == 'routine' and 150 <= r[1] < 480)
        for r in records])
    indices = [0, 1, 2, 3, 4, 6] if mode in ('healthy', 'reference_outage') else list(range(7))
    matrix = jacobian[mask][:, indices]
    if not len(matrix):
        raise ValueError('No available observations')
    _, s, vh = np.linalg.svd(matrix, full_matrices=False)
    tolerance = max(1e-7*s[0], 1e-8)
    rank = int((s > tolerance).sum())
    return dict(mode=mode, cutoff_s=cutoff, observations=int(mask.sum()),
        parameters=[PARAMETERS[i] for i in indices], singular_values=s.tolist(),
        numerical_rank=rank, parameter_count=len(indices),
        condition_number=float(s[0]/s[-1]) if rank == len(indices) else None,
        weakest_direction=dict(zip([PARAMETERS[i] for i in indices], vh[-1].tolist())),
        smallest_scaled_sensitivity=float(s[-1]),
        locally_full_rank=rank == len(indices))
