"""Replay recorded oxygen inputs, without inventing unobserved circuit dynamics."""
import csv
import math
from pathlib import Path
from .model import delivery

REQUIRED = ('time_s', 'flow_l_min', 'hb_g_dl', 'pao2_mmhg',
            'sao2_fraction', 'temperature_c', 'reported_do2_ml_min')


def read_observations(path):
    """Explicit units, ordered distinct times, no interpolation or saturation fill."""
    with Path(path).open(newline='') as f:
        reader = csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            raise ValueError('Missing required explicit-unit columns')
        rows = []
        for raw in reader:
            row = {}
            for key in REQUIRED:
                value = raw[key]
                if value is None:
                    raise ValueError(f'Truncated row: {key}')
                if key == 'sao2_fraction' and not value.strip():
                    row[key] = None
                    continue
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f'Nonfinite {key}')
                row[key] = number
            if row['time_s'] < 0 or (rows and row['time_s'] <= rows[-1]['time_s']):
                raise ValueError('Times must be nonnegative and strictly increasing')
            if (row['flow_l_min'] < 0 or not 0 < row['hb_g_dl'] <= 25
                    or row['pao2_mmhg'] < 0 or row['reported_do2_ml_min'] < 0
                    or not 0 < row['temperature_c'] < 50):
                raise ValueError('Invalid observation range')
            sat = row['sao2_fraction']
            if sat is not None and not 0 <= sat <= 1:
                raise ValueError('Arterial saturation must be a fraction, not percent')
            rows.append(row)
    if not rows:
        raise ValueError('No observations')
    return rows


def replay_oxygen(rows, bsa, saturation_sensitivity=(.98, 1.)):
    """Evaluate the existing content equation at observation times only.

    Missing SaO2 stays missing; hypothetical endpoints are labelled separately.
    Published DO2 is a calculated comparator, not an independent gold standard.
    No fitting, patient state estimation, controller recommendation or AUC.
    """
    if not math.isfinite(bsa) or bsa <= 0:
        raise ValueError('BSA must be finite and positive')
    lo, hi = saturation_sensitivity
    if not (math.isfinite(lo) and math.isfinite(hi) and 0 <= lo <= hi <= 1):
        raise ValueError('Invalid saturation sensitivity endpoints')
    output = []
    for row in rows:
        q, hb, pa = (row[k] for k in ('flow_l_min', 'hb_g_dl', 'pao2_mmhg'))
        sat = row['sao2_fraction']
        endpoints = (lo, hi) if sat is None else (sat, sat)
        calc = [delivery(q, hb, s, bsa, pa) for s in endpoints]
        measured_pa_high = delivery(q, hb, endpoints[1], bsa, pa)
        fixed_pa_high = delivery(q, hb, endpoints[1], bsa, 150.)
        output.append(dict(row,
            saturation_status='unmeasured_sensitivity' if sat is None else 'recorded',
            saturation_endpoints=list(endpoints),
            project_do2i_low=calc[0], project_do2i_high=calc[1],
            reported_do2i=row['reported_do2_ml_min']/bsa,
            fixed_pao2_150_do2i=fixed_pa_high,
            measured_pao2_increment_do2i=measured_pa_high-fixed_pa_high))
    return output
