# V2 joint hypothesis protection: delivery gain with interruption failures

Version **2.0.0rc2**, development only. This is a new experimental cap, not a stable release or an adopted replacement. Final v1 remains [v1.15.0](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/releases/tag/v1.15.0).

## Why this changes the controller

The first v2 recovery policy changed no commands: fast PI already reached the independent protection cap. This iteration changes the cap calculation itself. The earlier calculation combined the lowest volume bound across retained pump models, the highest venous-bias bound across models, and the worst stopping loss across models. Those extrema can belong to different models.

The new cap keeps each model's own volume lower bound, pump state and bias upper bound together. It checks the stopping inequality for **every retained model**. Within each model, volume and bias extrema are still combined conservatively; no vertex-only shortcut or covariance-derived safety margin is introduced. Both arms receive the same model-specific observer output, point estimate, PI gains and raw measurements. Only the protection calculation differs.

For model i, let Lᵢ be its volume lower bound, Bᵢ its bias upper bound and Rᵢ(u, q) its finite-return stopping reserve. The existing aggregate test is

    maxᵢ Rᵢ(u, q_global) <= minᵢ Lᵢ - 0.29,

where q_global uses the largest Bᵢ. The joint test requires

    Rᵢ(u, qᵢ) <= Lᵢ - 0.29   for every retained i.

Because qᵢ >= q_global and reserve is nonincreasing in credited return, the aggregate test implies every joint inequality at the same state. The converse need not hold. This removes a cross-model combination of worst cases, while retaining all model-specific checks. It does **not** establish stopping feasibility when the assumed future return disappears.

The floor, pump-model retention, calibration/error allowances, pressure rule, 0.15 L/min/s slew, 7 L/min command limit, and 50% return credit for 15 seconds are unchanged. No future event times enter the controller. Unsupported calibration retains the earlier braking fallback.

## Fixed 40-run development matrix

Two reused development patients, nominal and slow pumps, five return/sensor cases, two matched fast-PI arms; 600 seconds at 1-second steps. Each table row contains four paired cases from two patients. Interruption windows are [168, 213), [228, 243), and [258, 288) seconds; the single-stop case uses only the first. The noisy channel has 0.15 L/min noise SD; the biased channel has +0.8 L/min bias. Independent calibration and routine references remain healthy.

| Case | Aggregate PI deficit | Joint PI deficit | Reduction | Aggregate floor cases | Joint floor cases |
| --- | ---: | ---: | ---: | ---: | ---: |
| Normal return | 1414.5171 | 1236.5382 | 12.58% | 0/4 | 0/4 |
| Single interruption | 1494.7735 | 1399.2620 | 6.39% | 0/4 | 2/4 |
| Repeated interruptions | 1623.6488 | 1540.1440 | 5.14% | 0/4 | 2/4 |
| Repeated + biased return sensor | 1625.9167 | 1543.2243 | 5.09% | 0/4 | 2/4 |
| Repeated + noisy return sensor | 1629.6640 | 1525.4827 | 6.39% | 0/4 | 2/4 |

Deficit AUC units: mL O₂/m², integrated over the full run. These are exploratory development means, not independent confirmation or evidence of general superiority.

**The candidate fails protection and is not selected.** It crosses the 250 mL floor in 8/20 runs, versus 0/20 for aggregate PI. Worst volume is 68.10 mL, versus 438.26 mL for aggregate PI across this matrix. Neither arm makes an empty request. A 12.58% normal-return gain does not meet the project target: interruption failures and the limited development sample prevent qualification. Reserved confirmation cohorts remain untouched.

## Why the retained stopping assumption matters

In seed 37000 with the nominal pump and single interruption, the joint arm is feasible immediately before return loss, with about 1.022 L in the reservoir. At observation time 168 s, measured return drops and the reserve margin becomes approximately -0.388 L. The controller immediately uses its full permitted deceleration, but cannot undo the pump flow and slew obligations already committed. Reservoir volume reaches 68.10 mL. The old aggregate PI avoids a floor crossing in the same case.

This trace shows that checking a finite-return stopping path is not a zero-return invariant guarantee. Removing conservatism makes that limitation consequential. The model-specific algebra above is conditional on the existing calibration/model bounds and future-return assumptions; it does not prove those assumptions true. No hardware or clinical validation is established.

## Evidence and reproduction

- [Frozen protocol and source hashes](../results/v2-joint-pilot/protocol.json)
- [Summary](../results/v2-joint-pilot/summary.json), [all 40 run metrics](../results/v2-joint-pilot/runs.json), and [checksums](../results/v2-joint-pilot/checksums.json)
- Forty full 600-step CSV traces in `results/v2-joint-pilot/`
- [Joint observer and cap](../src/perfusion_research/joint_v2.py)
- [Initial output-handling failure](../results/v2-joint-pilot-attempt1/README.md)

The first execution completed all traces, then failed to serialize a NumPy integer in the metrics file. Its protocol, driver, log and trace hashes are retained. A scalar-conversion fix repeats the same numerical experiment; validation requires all 40 trace hashes to match the original attempt. A second attempt saved the metrics successfully but failed while printing the same NumPy scalars; its protocol, driver and log are also archived. The final driver prints the saved JSON. These repeats are not counted as extra patients or evidence.

```bash
python -m pip install -e ".[audit,horizon]"
python examples/joint_v2_study.py
python examples/validate_joint_v2.py
python -m unittest discover -s tests -v
```

Validation recomputes deficits, recovery-window metrics, floor/empty outcomes, command limits and group summaries; checks every source/trace hash and feasible model margin; confirms exact parity of the aggregate arm with the earlier fast PI; and replays a noisy repeated-stop pair. Tests include a separated-hypothesis example, single-model equivalence and absence of support.

## Next goal

Test joint hypothesis accounting with **zero future return** in the stopping calculation. Use a fixed 2×2 comparison: aggregate versus joint accounting, each with zero-return versus the retained 15-second credit. Keep the finite-credit failures as references and require interruption protection before considering a candidate for further development. This will separate the benefit of model association from the optimistic return assumption. No untested follow-up is included in this result.
