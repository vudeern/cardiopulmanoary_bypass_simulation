# V2 calibration and model-boundary study

**2.0.0rc4 — development only; design freeze blocked.** Controllers and observer allowances are unchanged from the zero-return comparison. Final v1 remains v1.15.0.

## Fixed design and provenance

Full four-plant × four-calibration × two-controller matrix on two reused development patients: **64 evaluations, comprising 56 new simulations and eight retained rc3 references**. All cases have the same three return interruptions, 600-second duration, 1-second step, fast-PI gains and zero future-return credit. No outcome-based tuning or selection was performed. Both reserved confirmation cohorts remain untouched.

Plants: nominal pump, tau=6 s slow pump, tau=20 s outside-grid pump, and tau=5 s pump with 20 s drainage lag and nonlinear venous return. The retained pump grid is 1, 2, 4, 8 and 12 seconds. Tau=20 is outside its range; tau=5 and tau=6 also lack exact grid members. These synthetic perturbations are not independently validated physiological models.

Calibration regimes: healthy, completely missing, +0.22 L calibration bias, and +0.22 L shared routine/calibration bias. Shared corruption is constant on both channels; agreement does not establish absolute accuracy. The venous channel retains 0.015 L/min noise SD and no injected bias. Calibration/routine channels retain 0.01 L noise SD. Controller calibration/error allowances are not widened to absorb the injected faults.

The eight healthy nominal/slow repeated-stop references are exact hashed rc3 records. New full-precision CSV traces are stored losslessly in four ZIP archives, one per plant. Every new trace has an individual SHA-256 plus an archive checksum; no repeated run is counted as another patient or independent confirmation.

## Results by calibration regime

| Calibration | Aggregate deficit | Joint deficit | Aggregate floor cases | Joint floor cases |
| --- | ---: | ---: | ---: | ---: |
| Healthy | 1975.7012 | 1927.8788 | 0/8 | 0/8 |
| Missing | 2687.0083 | 2687.0083 | 0/8 | 0/8 |
| Biased | 1853.9668 | 1808.4811 | 1/8 | 3/8 |
| Shared | 1854.2255 | 1809.3902 | 1/8 | 3/8 |

Deficit AUC units: mL O₂/m² per full run. Each row has eight runs per controller from two patients and four plants, not eight independent patients. The complete 16-cell breakdown is in the summary.

Across the whole matrix, joint control crosses the 250 mL floor in **6/32 cases**, versus **2/32** for aggregate PI. Worst volumes are **229.96 mL** and **237.87 mL**, respectively. Neither controller makes an empty request or exceeds the 95 pressure threshold in this matrix. Applied commands satisfy their selected cap and slew checks; those checks do not establish that the volume bound is correct.

Healthy-calibration mean deficit improves **2.42%** with joint accounting, with no observed floor crossing in that regime. This includes changed pump/drainage dynamics and is not the same population of cases as the preceding 3.67% result. Missing calibration produces identical commands/delivery in both arms, no observed floor crossings, and high deficit: 2687.0083. It leaves all 600 seconds unsupported in each run; conservative delivery is not an accuracy success.

Biased calibration and shared corruption each produce three joint-arm floor cases, versus one aggregate-arm case. The nominal pump produces both joint failures for each biased regime; the slow pump produces the remaining joint failure. No floor crossing was observed in the tau=20 or lagged-plant cases. That small negative finding does not validate either model mismatch.

## What failed underneath the stopping check

Zero future-return credit removes one optimistic assumption. It does not fix an incorrect absolute-volume estimate or certify a model bank.

A post-result replay diagnostic uses the new traces' bank bounds at observation time, compared against the true reservoir at the **start** of that step (previous row's step-end reservoir; initial value 0.85 L). Across the 56 new traces, it counts **8,444 supported seconds with true volume outside the bank interval**: 3,849 in biased-calibration cases, 3,780 in shared-corruption cases, and 815 in healthy-calibration cases with changed dynamics. These are interval-step counts across reused patients, not independent failures or calibrated probability estimates. The eight retained traces do not contain these extra bank fields and are excluded from this diagnostic.

Thus `bank_supported` means the observer's consistency checks passed; it is not an independent integrity certificate. A cap can obey every modeled stopping inequality while a biased or misspecified volume bound permits a physical floor crossing. Both zero-return designs fail protection on this fault matrix and are **not qualified for a design freeze or stable v2**. No clinical/hardware validation or overall superiority is established.

## Evidence and reproduction

- [Frozen protocol and hashes](../results/v2-robustness/protocol.json)
- [Full results](../results/v2-robustness/summary.json), [all 64 metrics records](../results/v2-robustness/runs.json), [artifact checksums](../results/v2-robustness/checksums.json)
- [Nominal traces](../results/v2-robustness/traces-nominal.zip), [slow traces](../results/v2-robustness/traces-slow.zip), [outside-grid traces](../results/v2-robustness/traces-outside.zip), [lagged traces](../results/v2-robustness/traces-lagged.zip)
- [Study driver](../examples/robust_v2_study.py), using the unchanged [joint runtime](../src/perfusion_research/joint_v2.py)

```bash
python -m pip install -e ".[audit,horizon]"
python examples/robust_v2_study.py
python examples/validate_robust_v2.py
python -m zipfile -e results/v2-robustness/traces-nominal.zip /tmp/perfusion-nominal-traces
```

Validation checks all source/reference hashes, ZIP integrity and members, individual CSV hashes, full-run deficits, floor/empty/pressure outcomes, supported/infeasible states, caps/slew/model margins and aggregate counts, then replays two fault cases. It prints the post-result interval-coverage diagnostic. Passing validation means the research artifacts reproduce; observed floor failures remain failures.

## Next controller goal

Separate the optimization observer's consistency status from the protection envelope. The envelope needs an explicitly stated anchor-bias and model-error budget, and a defined conservative fallback when that integrity support is absent. Test any such change against PI with the same information and budgets, retaining this failed matrix and measuring the delivery cost. Shared absolute bias cannot be identified merely from two agreeing corrupted channels; no finite safety claim is possible for an unbounded unknown offset. A declared simulation fault envelope must not be presented as a validated hardware sensor specification.
