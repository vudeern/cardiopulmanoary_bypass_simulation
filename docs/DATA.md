# Data dictionary and experiment protocol

All files contain generated data. There are no patient records or device exports.

## Main experiment

`results/metrics.csv` contains 840 rows: seven scenarios × seeds 100–123 × five
policies. Patients, scenario inputs and sensor-noise streams are paired between
policies. All scenarios and failures are retained. `results/summary.json` records
the protocol and 112 paired comparisons (7 scenarios × 4 nonreference policies ×
4 metrics). Each difference is candidate minus reactive, calculated within seed
before summarizing. Bootstrap uses 2,000 resampled patient pairs, seed 2026, and
2.5/97.5 percentiles. Reusing the bootstrap seed makes estimates deterministic;
intervals are not independent across comparisons. No correction for multiplicity
or inference to a clinical population is performed.

The artifact is an engineering benchmark defined for this project, not a
preregistered clinical study. Controller weights and scenario magnitudes are
chosen assumptions; no claim of exhaustive optimal tuning is made.

## Per-run metrics

| Field | Unit | Meaning |
|---|---|---|
| scenario | string | Named fault schedule |
| seed | integer | Patient sampler seed; sensor seed is seed + 10000 |
| policy | string | Strategy identifier |
| deficit_auc | mL O₂/m² | Sum max(0,target−true delivery) × dt/60 |
| below_target_s | s | Duration true delivery < target |
| false_reassurance_s | s | Duration monitor ≥ target and ensuing true delivery < target |
| false_reassurance_margin_s | s | Same, additionally requiring true delivery < target−5 |
| concealed_deficit_auc | mL O₂/m² | Delivery deficit area during false-reassurance intervals |
| unmet_demand_auc | mL O₂/m² | Integrated hypothetical demand shortfall with extraction ceiling 0.60 |
| low_reservoir_s | s | Duration interval-end reservoir < 0.25 L |
| empty_request_s | s | Duration requested pump transfer exceeded available volume |
| high_pressure_s | s | Duration interval-end pressure > 95 mmHg |
| infeasible_s | s | Duration no predictive candidate met its screens and slew bound |
| hb_bound_coverage | fraction | Fraction of true Hb values inside the engineering stress bounds |
| minimum_reservoir | L | Smallest interval-end reservoir volume |
| flow_variation | L/min | Sum absolute successive command differences, excluding initial transition |
| mean_flow | L/min | Mean actual interval-average flow |

Strict inequalities matter near thresholds. A few units of noisy monitor error
can produce a long near-target false-reassurance duration with little deficit
area; use the margin and magnitude metrics together. A 0.25 L floor and 95 mmHg
ceiling are experimental comparison limits, not device or clinical specifications.

## Full trajectories

`perfusion-lab run` emits `run.json` and `run.csv`. The benchmark emits a regenerable
`results/trajectories.json` containing full trajectories for its first seed only,
one per scenario/policy. The JSON's top level has scenario name/parameters, policy,
seed, dt, duration, target, lab period, patient parameters, metrics and rows.

| Row field | Unit | Timing / meaning |
|---|---|---|
| time | s | End of simulation interval |
| observation_time | s | Start of interval; time − dt |
| flow | L/min | Actual interval-average pump delivery |
| qv | L/min | Start-of-interval venous-return calculation |
| reservoir | L | True end-of-interval volume |
| patient_volume | L | True end-of-interval complementary storage |
| pressure | mmHg | True end-of-interval Windkessel pressure |
| empty_request | boolean | Requested transfer exceeded available fluid |
| hb | g/dL | True held-interval hemoglobin |
| hb_estimate / hb_lower / hb_upper | g/dL | Observer quantities from start-of-interval information |
| hb_inline | g/dL or null | Noisy/bias-affected sensor sample; null means dropout |
| sao2 | fraction | True held-interval arterial saturation |
| temperature | °C | Held-interval scripted temperature |
| command | L/min | Start-of-interval controller command |
| do2 | mL/min/m² | True indexed delivery from actual mean flow |
| measured_do2 | mL/min/m² | Preceding monitor estimate; held Hb fallback during dropout |
| demand | mL/min/m² | Hypothetical indexed metabolic demand |
| unmet_demand | mL/min/m² | max(0,demand−0.60 × true delivery) |
| fault | boolean | Estimated Hb bias >0.6 g/dL in magnitude or stale inline Hb |
| stale | boolean | Last inline Hb sample >10 s old |
| infeasible | boolean | Predictive screen has no feasible grid candidate |
| reference_age | s | Age of most recent independent reference |
| hb_covered | boolean | True Hb lies in observer's engineering interval |

The row does not export every noisy channel; `Observation` defines the full
controller interface. Measured DO₂ uses the preceding flow observation and inline
Hb, or the observer Hb when inline is missing. It remains an uncorrected monitor
value when a biased inline measurement is available. Sentinel's internal decision
uses its separate corrected lower Hb bound. The distinction is intentional.

## Compact replay

`web/data.js` and `web/data-*.js` are generated by `examples/build_web.py`. It contains all 35 first-seed
runs, their full-resolution metrics, and the paired aggregate comparisons. Chart
arrays `t`, `do2`, `monitor`, `reservoir`, `pressure`, `fault`, `infeasible` are
rounded for display. Sampling keeps every third row and the final row: approximately
6 seconds between points. It does not retain every brief event; metrics remain
computed at 2-second resolution. The live plot is a representative run, not the
cohort mean. Its selected seed must not be mistaken for a random patient prediction.

## Failure map

`results/failure-map.csv` has 392 rows: reservoir bias {0,0.1,…,0.6} L × seven
equally spaced drainage multipliers from 0.3 to 1.0 × seeds 500–503 × two policies.
The custom scenario includes dilution=1.8 g/dL, the standard fault schedules,
and no inline Hb bias/dropout. `failure-map-protocol.json` records exact floating-
point grid values and seeds. Additional columns `level_bias_L` and `drainage`
identify the grid cell. Per-run metrics have the definitions above.

`failure-map-summary.json` contains each grid cell's mean low-reservoir duration
for reactive and Sentinel and their difference. These four-seed means are an
exploratory map, with no claim of a precise transition boundary or clinical safety.


## v1.1 level-step guard fields

Simulation rows add `level_fault` (latched discontinuity flag), `level_bias_estimate` (inferred signed level offset, L) and `reservoir_lower` (corrected level minus the post-alarm 0.08 L allowance, clipped at zero; null for original policies). `level_fault_s` is the integrated latched-flag duration, not detection latency or confirmed-fault duration. `fault` remains the separate Hb flag. Extension CSVs add `experiment`, `level_bias_L` and `drainage`; see [LEVEL_GUARD.md](LEVEL_GUARD.md) for cohort definitions.

## v1.2 conservative comparison

`results/conservative-comparison/` contains a tuning-only candidate CSV, the complete 3,192-run CSV, protocol, frozen selection, environment, and final aggregate JSON. `experiment` identifies tuning/evaluation/map; `variant` identifies the complete policy configuration and `family` groups reserve/cap/original/guarded. The protocol maps variants to policy and options. `controller_options` in single-run exports records reserve margins in L and flow caps in L/min/m². Pooled intervals resample patient seeds after within-seed scenario averaging. `results/conservative-pilot/` is the separate 2,240-run exploratory archive. See [CONSERVATIVE_COMPARISON.md](CONSERVATIVE_COMPARISON.md).

## v1.3 stress data

Simulation rows now log `observed_flow`, `observed_reservoir`, `injected_level_bias` and `injected_flow_bias`. Injection values are truth logs for scoring, never inputs to the controller. `plant_options` and `plant_model` are exported separately from controller options. Stress CSV fields identify sensor/plant cells and alarm timing; blank `first_alarm_s` means no flag. `level_alarm_ever` is any latched level flag, not correct fault isolation. In no-level-fault cases, flags are false attribution by construction. See [ROBUSTNESS.md](ROBUSTNESS.md).
