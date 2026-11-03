# Data dictionary

All controller trajectories are synthetic unless explicitly identified as the five-point public-case oxygen input replay.

## Simulation outputs

`simulate(...)` returns configuration, patient parameters, per-step rows and integrated metrics. Truth is recorded at the end of each interval; observations and decisions are from the start of that interval. Units are explicit in `model.py` and the table below.

| Field | Meaning / units |
| --- | --- |
| `time`, `observation_time` | Interval end and sensor acquisition time, seconds |
| `flow`, `qv`, `command` | Step-average arterial flow, venous return, commanded flow, L/min |
| `reservoir`, `patient_volume` | Conserved physical volumes, L |
| `pressure` | Arterial pressure, mmHg |
| `hb`, `hb_inline`, `hb_estimate`, `hb_lower`, `hb_upper` | Hemoglobin and observer bounds, g/dL |
| `sao2` | Arterial saturation, fraction |
| `do2`, `measured_do2` | Indexed oxygen delivery, mL O2/min/m² |
| `observed_flow`, `observed_reservoir` | Faulty acquired channels, L/min and L |
| `observed_venous_flow` | Optional independent acquired venous flow, L/min; null when disabled |
| `level_reference`, `level_reference_acquired` | Delivered volume reference (L), original acquisition time (s) |
| `level_reference_estimate`, `level_reference_lower` | Corrected level and engineering lower estimate, L |
| `level_reference_age`, `level_reference_unknown` | Acquisition age (s) and missing/stale flag |
| `injected_level_bias`, `injected_flow_bias` | Hidden scoring information; never controller inputs |
| `empty_request`, `infeasible`, `level_fault` | Physical transfer limitation, candidate infeasibility, detector flag |

Metrics include oxygen-deficit AUC (mL O2/m²), exposure durations (seconds), minimum reservoir (L), mean flow (L/min) and summed absolute command changes (L/min). AUC uses dt/60 to convert seconds to minutes. Experimental thresholds are engineering choices, not treatment settings. Observer bounds are not calibrated confidence limits.

## Controller comparison

`data/controller-reference/reproduction.json` identifies the source, verified components, adaptations and unresolved reproduction requirements.

`results/controller-comparison/` contains:

- `protocol.json`: candidate grid, seed split, measurement assumptions and shared constraints.
- `selection.json`: development-only means, selected settings and exposure-budget eligibility.
- `metrics.csv`: every development and final run; no failed run is removed.
- `summary.json`: grouped working metrics and explicit false flags for exact reproduction and superiority claims.
- `debug-traces.json`: two prespecified cases, one evaluation seed, all three methods, full trajectories.

`venous_tracking_mae_l_min` compares step-average true arterial flow with step-average true venous flow for scoring. `level_mae_l` compares volume with the reference architecture's 0.45 L target; Sentinel has a floor objective, so this is not a common optimization target. Development budgets and scenario weights do not represent clinical margins or event frequencies.

The optional venous sensor uses its own random stream. It samples current venous flow before the plant advances, including the current drainage state in lagged plants. Noise and bias are explicit. Both matched arms receive the same sensor model and random innovations. Different controller actions can produce different physical flow observations; pairing does not imply identical trajectories.

## Public case

`data/published-case/observations.csv` preserves five reported samples and missing arterial saturation. `provenance.json` supplies the citation, units, extraction method and assumptions. `results/published-case/` contains arithmetic replay outputs. Chosen saturation endpoints are sensitivities, not measured values, confidence intervals or guaranteed bounds. No interpolation, deficit AUC or fitted reservoir model is produced from those sparse samples.

Older experiment folders retain their recorded protocol, parameters and raw metrics. They are exploratory engineering logs. Browser traces are subsampled for display; integrated metrics use full simulation resolution.

## Verified general-reference comparison

`data/simc-reference/source.json` maps the published general PI rule and normalized verification case. It explicitly distinguishes source equations from the simulation supervisor. `results/simc-verification/verification.json` stores computed frequency values and time-domain refinement errors.

`results/simc-benchmark/` contains the recorded protocol, development-only selection, every run in CSV, all final cells and patient-block comparisons in JSON, twelve replay traces, timestep sensitivity and machine diagnostics. The exact script/model/source hashes are recorded before the run. `diagnostics.json` retains every sensor-only pairing and finite-grid selection limitations. No prose result document is generated.

Final parameters come from wider uncalibrated ranges than development parameters. The SIMC source has an integrating-process gain; the applied reservoir uses signed gain −1/60 and a fixed 1.5-second design delay. The design sampling assumption stays fixed during timestep sensitivity. Random sensor draws change with dt, so those runs are sensitivity checks rather than a pure deterministic convergence proof.

The browser's verified-reference dataset has a 600-second duration and one-second scoring interval; older datasets retain their own duration and interval. The viewer scales its timeline and timing caption to the selected dataset.

The separate `canonical-protocol.json`, `canonical-metrics.csv` and `canonical-summary.json` are post-result descriptive sensitivity logs. They apply the source's canonical tau_c = theta choice using the already development-selected reservoir target. They reuse final cases, make no independent confirmation claim, and do not replace the recorded primary comparison.

## Braking-controller logs

`results/braking-study/` retains protocol, development candidates, selected methods, all evaluation rows, all 96 final cells and patient-block comparisons, and six prespecified replay cells. The final table is separate from two retained development-only pilots. Their original source hashes resolve to the snapshots in `data/braking-history/`. These are engineering records, not prose result reports.

New controller-only row fields are `braking_volume` and `braking_budget` (L), `control_level_lower` (L), `inflow_lower` and `balance_inflow_lower` (L/min), `actuator_flow_upper` (L/min), `estimated_drift_rate` (L/s), `braking_feasible` and `level_information_unknown`. A null balance estimate means insufficient past samples. Reference age and the estimated reference bias are causal observation metadata; injected bias and future truth are never passed to the controller.

The primary comparison uses good references and three specified in-range actuator regimes. The 12-second lag plant and delayed/missing or biased references are explicit secondary stress groups. All groups remain visible; engineering tolerances are not clinical safety margins.


## Continuity engineering logs

`results/continuity-study/` contains a frozen protocol, development selection, full per-run metrics, cell/group means, paired patient-block intervals and representative traces. The final-development grid has 3,072 runs; fresh evaluation has 6,144 runs (16 virtual patients × 8 faults × 4 plants × 4 reference regimes × 3 controllers). A separate 3,072-run development-only grid remains under `results/continuity-pilot-1/`; it is not a final evaluation.

New debug fields are `balance_level_estimate` [L], `balance_reference_age` [s or null before anchoring], and `venous_bias_estimate` [L/min]. These are estimates, not injected truth. The common `control_level_lower` is an engineering lower estimate, not a calibrated confidence bound. `level_information_unknown` flags no delivered anchor. The stopping constraint's existing debug fields retain the same units as v1.9.

The co-primary good-reference and delayed/lost-reference groups exclude the 12 s actuator, outside the design interval. The combined primary summary pools those two groups equally. Biased and never-delivered references, and all out-of-range lag cells, remain in explicitly labelled secondary groups, some of which overlap. Paired bootstrap intervals resample virtual patients as blocks; they do not represent a clinical population.
