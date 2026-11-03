# Perfusion Sentinel

A work-in-progress cardiopulmonary bypass simulation by Udeern Varanasi.

[Interactive replay](https://vudeern.github.io/perfusion-sentinel/) · [Portfolio](https://vudeern.github.io/projects.html) · [Model](docs/MODEL.md) · [Data dictionary](docs/DATA.md) · [Checks](docs/VALIDATION.md)

The project explores how sensing errors, oxygen delivery and limited venous return affect pump control. It uses an uncalibrated adult-like synthetic circuit. It does not control equipment, recommend patient settings, predict organ injury or reproduce a commercial product. There is no LivaNova affiliation.

## Current design: continuity between level references

The `continuity` controller integrates measured venous inflow minus a nominal first-order pump-flow estimate. Delivered level references anchor this balance **at their acquisition time**, so a delayed sample corrects the past before propagation to the present. Consecutive reference volumes fit a venous-sensor offset (clipped to ±2 L/min); the controller does not receive the actual offset, future drainage or true pump lag. A braking reserve uses the command-history actuator interval and the estimated inflow. A linearly growing model-error allowance replaces the old abrupt 180-second loss-of-reference shutdown.

This is a model-dependent engineering estimate. An incorrect pump model or changing venous-sensor bias can accumulate volume error during an outage. A biased reference anchors the estimate incorrectly. Before any reference arrives, the method uses the inline level and explicitly flags that it is unanchored; this fallback is not guaranteed to be protective.

```bash
python examples/continuity_study.py --stage develop
python examples/continuity_study.py --stage evaluate
python examples/validate_continuity_study.py
python examples/build_continuity_web.py
```

The fresh evaluation **does not demonstrate the joint goal**. With good references, mean oxygen-deficit AUC is 154.35 versus 137.08 mL O₂/m² for PI, while low-reservoir time is 0.74 versus 30.85 s. The protection criterion passes, but oxygen does not. During outages, AUC is 307.89 versus 122.49 and low-reservoir time 30.93 versus 39.46 s; both the oxygen and protection criteria fail (the paired upper interval for extra empty requests is 1.64 s, beyond the 1 s limit). Relative to v1.9 braking on the same fresh cases, outage AUC improves from 2061.44 to 307.89, but low-reservoir time rises from 2.89 to 30.93 s. The fixed-prior-PI sensitivity also retains higher oxygen deficit for continuity. This version reduces the old shutdown penalty without solving the oxygen/protection tradeoff. A post-evaluation audit (`examples/diagnose_continuity.py`) identifies large volume-estimation errors in selected outage cells: one delivered reference cannot identify a constant venous-flow offset, and integrating it can overestimate the reservoir. Its truth-aligned logs are diagnostic only; no tuning follows the final evaluation.

The final revision gives each family 16 candidates on the same development grid, including reference outages. One earlier development-only grid is retained in `results/continuity-pilot-1/` with source snapshots in `data/continuity-history/`. No final evaluation was run for that attempt. Architecture design is informed by the previous studies; challenge families are reused. Fresh patient and noise seeds test the frozen design, not an independently validated physiological model.

The co-primary test requires reservoir/pressure protection and less oxygen deficit versus the retuned SIMC PI reference **separately in both good-reference and delayed/lost-reference groups**, with in-range plants. Biased references, no references at all and an out-of-range pump lag remain secondary stress tests. The v1.9 braking controller stays as a fixed context arm. A separately specified 2,048-run sensitivity retains the previous fast PI settings (`tau_c=1.5`, level target 0.45 L); it never replaces the frozen primary test. All failures remain in the machine-readable logs under `results/continuity-study/`.

## Previous design: predictive braking reserve

The new `braking` controller reserves volume for the pump's response lag and rate-limited slowdown. It tracks an interval of actuator flow from command history, cross-checks measured venous flow against past inline-level changes, and adjusts its level allowance using observed reference-bias trends. These engineering allowances are not calibrated uncertainty bounds or guarantees about future drainage.

The new controller and the general SIMC PI reference share sensors, reference metadata, oxygen-demand caps, pressure slowdown and actuator limits. Sixteen candidates per family are selected only on the current development grid. The earlier forecast stays as a fixed context arm. Settings and source hashes are frozen before evaluating fresh patient seeds and stronger conditions. Missing/bad references and an actuator lag outside the design range remain in the logs.

```bash
python examples/braking_study.py --stage develop
python examples/braking_study.py --stage evaluate
python examples/validate_braking_study.py
python examples/build_braking_web.py
```

The 4,608-run fresh evaluation passes the predefined protection criterion but fails the oxygen criterion. In the primary good-reference, in-range group, mean low-reservoir time is 1.11 s for braking versus 7.26 s for PI; both have zero empty requests. Mean oxygen-deficit AUC is 224.48 versus 206.39 mL O₂/m² (8.8% higher). Paired patient-block intervals retain the oxygen penalty. Missing reference measurements trigger large slowdowns: mean AUC 1,830.11 versus 176.75 for PI in that secondary group. The planned joint advantage remains undemonstrated.

Raw outputs are in `results/braking-study/`. Two superseded development-only designs and their exact source snapshots are retained in `results/braking-pilot-1/`, `results/braking-pilot-2/` and `data/braking-history/`. The final revision has equal-sized tuning grids; earlier architecture exploration is not claimed to have an equal total search budget. No final evaluation data were used for those development revisions.

The controller flags infeasible stopping requests and absent/stale level information; it never receives the injected fault magnitude or true future inflow. A constant lag within 1–10 seconds, adequate level/error allowances and an inflow lower estimate that remains valid are conditional assumptions. A past slope alone cannot guarantee future venous return. Clinical protection and scientific novelty are not established by these simulations.

## Previous comparison: verified free SIMC PI reference

The reproducible reference is [Skogestad's SIMC PI method](https://www.mic-journal.no/PDF/2004/MIC-2004-2-2.pdf), with [free author notes and corrections](https://skoge.folk.ntnu.no/publications/2003/tuningPID/README.html). This is an established **general process-control method**, applied here as a reservoir override. It is not a clinical CPB controller or commercial medical device.

The implementation reproduces the published normalized PI settings and five reported frequency-response values. A separate analytic time-domain solution checks the discrete PI implementation and its refinement. The [source mapping](data/simc-reference/source.json) distinguishes the published equations from the shared oxygen/pressure/actuator supervisor added for this application.

Both controllers receive the same sensor/reference pipeline and actuator limits. Each family receives eight development candidates. Selection is frozen before evaluation on wider synthetic patient parameters, new faults, changed pump/drainage dynamics, and delayed or missing references. Patient-block comparisons retain all challenge cells and adverse outcomes. The planned joint advantage is not demonstrated; the model exposes an oxygen/depletion tradeoff. Neither clinical benefit nor scientific priority is established.

```bash
python -m pip install -e .
python examples/verify_simc.py
python examples/simc_benchmark.py
python examples/analyze_simc.py
python examples/check_simc_tight.py
python examples/validate_simc_benchmark.py
python examples/validate_simc_tight.py
python examples/build_simc_web.py
```

Working outputs remain CSV/JSON under `results/simc-verification/` and `results/simc-benchmark/`. The interactive replay offers six prespecified final cases, both methods and the first evaluation seed. It scores at one-second resolution and displays every third sample. The final cohort has 16 paired virtual patients; artificial challenge cells are not clinical event frequencies. Finite candidate grids and boundary-selected settings limit conclusions about optimal tuning. An additional canonical `tau_c = theta` check is explicitly labeled post-result and descriptive. It reuses final cases, retains the original test, and does not select a new setting on those outcomes.

The earlier [Takahashi bypass-controller workbench](data/controller-reference/reproduction.json) remains explicitly incomplete. It is not the verified primary comparator. Its exploratory runner and logs are retained for continuity; they must not be presented as the authors' reproduced controller.

## Run the existing experiments

```bash
perfusion-lab run --scenario compound --policy sentinel --out /tmp/perfusion-run
perfusion-lab benchmark --out /tmp/perfusion-benchmark
python examples/published_patient_replay.py
python -m unittest discover -s tests
node tests/web_contract.cjs
```

Use `perfusion-lab --help` for the existing command interface. Earlier experiments and raw logs remain reproducible. Existing PI/threshold policies are project baselines, not faithful implementations of a commercial or published controller. `web/` replays precomputed Python output; it does not run a second physiology engine.

The public-case input file contains five observations transcribed from [Hunter et al., 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC4557537/). [Provenance](data/published-case/provenance.json) preserves missing arterial saturation and source attribution. This is an oxygen-equation replay only; no patient reservoir dynamics are fitted or validated.

## Repository

- `src/perfusion_lab/`: plant, sensors, observer and controller code.
- `tests/`: physics, information, controller and replay contracts.
- `data/`: source provenance and reference implementation mapping.
- `results/`: reproducible raw experiment logs and machine summaries.
- `examples/`: runners, optional engineering plots and artifact checks.
- `docs/`: model, data dictionary and validation instructions.
- `web/`: interactive replay and work-in-progress project page.

Paper drafts, abstracts, result write-ups and publication-readiness documents are removed while development continues. Their generators are removed as well. Optional plotting tools write to `results/figures/`, not `docs/`. Historical experiments are development evidence, not clinical validation or final publication claims.

Code is MIT licensed. Source articles and externally published numerical facts retain their own attribution and rights; the software license does not relicense them.
