# Identifiability before estimator and horizon-MPC development

This development milestone adds an offline information audit to the released
rc.5 simulator. It changes no controller, plant equation, protection limit,
actuator authority, release gate or package version. Stable v1 remains v1.14.0;
stable v2.0 is not qualified. Both reserved confirmation cohorts are untouched.

## What was executed

- 128 baseline controller runs: the same 32 development patients (37000–37031),
  clean/combined physiology and nominal/slow pumps, 600 seconds at 1-second steps.
- 3,968 offline plant replays using those recorded commands, including two
  central-difference step sizes and an explicit indistinguishable-state example.
- 2,048 local sensitivity analyses: four information assumptions and four
  availability cutoffs per baseline case. These are analyses of reused data,
  not 2,048 independent patients or new controller comparisons.

The baseline is `retained_single_anchor` from public commit
`c92c7f2fe84bc00b7d81f283ee916a76f72bf347`, with good calibration and clean routine
references. Commands are held identical across all perturbations and information
masks. No probing command is added. The sensor-noise realization affects the
baseline controller commands; sensitivity replays use expected measurement means,
without fresh measurement noise. They are not noisy parameter-recovery trials.

The seven tested quantities are initial reservoir volume, inline level offset,
venous-flow offset, pump time constant, unstressed patient storage, common offset
on all level channels, and pump-flow sensor offset. Parameter scales are 0.1 L,
0.1 L, 0.3 L/min, 2 s, 0.1 L, 0.1 L and 0.3 L/min. Central differences use
dimensionless steps 0.001 and 0.0005. Each measurement row is divided by its
configured sensor SD. This scaling supports numerical comparison; it does not
turn Gaussian noise into a bounded safety envelope.

The actual `StressPlant` and `LevelReferences` implement replay and reference
timing. Volume is in liters, flow in liters/minute, time in seconds. Pump output
removes volume; venous return replenishes it. Pump lag remains in the plant.
Reference rows enter only after delivery and retain their acquisition time.

## Results

At the final 599-second availability cutoff:

| Information assumption | Locally full-rank cases | Rank / unknowns |
| --- | ---: | ---: |
| Healthy routine and calibration, absolute offsets fixed known zero | 128/128 | 6/6 |
| Routine acquisition outage 150–480 s; healthy calibration retained | 128/128 | 6/6 |
| Calibration missing; remaining level channels have unknown common offset | 0/128 | 6/7 |
| Routine and calibration share unknown absolute offset | 0/128 | 6/7 |

The same rank pattern occurs at the declared 5, 30 and 126-second cutoffs.
At 5 seconds, a routine reference acquired at zero has already arrived at 4 s;
the first calibration arrives at 6 s. The healthy-source analysis assumes that
routine source is unbiased; it does not imply the current guard should accept an
unaudited source, nor justify higher startup flow before calibration.

Halving the finite-difference step produces zero numerical-rank disagreements.
The maximum relative change in the entire Jacobian is **1.04%**; the model has
clamps and saturation, so the derivatives are approximate. Numerical rank uses
`max(1e-7 * largest_singular_value, 1e-8)` and is not a universal statistical
identifiability threshold. Per-case spectra and weakest directions remain public.
No confidence interval or successful parameter recovery is inferred from rank.

Offline reservoir replay matches the controller harness to **1.11e-16 L**.
An additional finite-shift check changes starting reservoir volume by +20 mL,
unstressed patient storage by −20 mL, and common level offset by −20 mL. All
predicted measurement means remain identical to **1.42e-14** numerical precision
over the tested trajectories. In these cases transfer clipping does not break
the symmetry: patient filling depends on `total_volume - reservoir - unstressed`,
which this transformation preserves, while the sensor offset cancels the level
shift. More command variation cannot resolve this particular ambiguity while
those assumptions and the symmetry hold. A known absolute reference or justified
independent storage/volume information is required.

## Scope and next decision

This is a conditional local audit, not a global observability proof or an RLS
persistent-excitation certificate. Other patient parameters, the disturbance
schedule, and the bias-profile shape are held known. Adding unknown resistance,
compliance, drift or changing lag can create further ambiguities. The late outage
also retains information from earlier anchors. We have not shown that an estimator
can recover each parameter accurately from independent noisy or corrupted runs.

The next estimator should begin with independently anchored volume/bias and the
existing bounded pump hypotheses. Do not freely adapt every absolute offset and
storage state together. Freeze or retain conservative sets when information is
insufficient. Validate recovery, drift, outliers, outages and coverage on fresh
noise realizations within development seeds before giving the same estimator to
PI and horizon MPC. Filter covariance alone cannot relax protection.

Horizon MPC still needs physical pump dynamics, oxygen-deficit AUC as its primary
objective, pressure/actuator constraints, a state-dependent stopping reserve,
validated terminal recovery and checked solver-failure handling. Then retune PI
with identical information and authority. The unchanged ≥10% improvement and
protection requirements must pass before design freeze and the two independent
32-patient confirmation cohorts. This audit provides no performance gain.

## Reproduce

```bash
python -m pip install -e ".[audit]"
python examples/identifiability_study.py
python examples/validate_identifiability.py
python -m unittest discover -s tests -v
```

The runner only accepts the locked development seeds. `--seed 37000` runs one
patient; `--summarize` requires every case. The frozen protocol refuses changed
settings or source hashes. Raw command CSVs, case JSONs, summary, source hashes
and output checksums are in `results/identifiability-development/`. The validator
checks the complete grid and independently replays four stored command traces.
CI also checks reproduction on Python 3.10 and 3.12; local validation used 3.12.

No equipment is controlled and no clinical or hardware safety claim is made.
