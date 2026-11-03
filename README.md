# Perfusion Sentinel

A work-in-progress cardiopulmonary bypass simulation by Udeern Varanasi.

[Interactive replay](https://vudeern.github.io/perfusion-sentinel/) · [Portfolio](https://vudeern.github.io/projects.html) · [Model](docs/MODEL.md) · [Data dictionary](docs/DATA.md) · [Checks](docs/VALIDATION.md)

The project explores how sensing errors, oxygen delivery and limited venous return affect pump control. It uses an uncalibrated adult-like synthetic circuit. It does not control equipment, recommend patient settings, predict organ injury or reproduce a commercial product. There is no LivaNova affiliation.

## Current experiment: screening biased references

The new `screened` reference mode evaluates routine samples **before** either PI or the predictive override uses them. It waits briefly for a same-acquisition independent calibration, tests unpaired samples against calibrated inline history and (after two calibrations) mass balance, quarantines inconsistent routine references, and restores the most recent independent calibration correction. A widening engineering uncertainty range defines the level supplied to both matched controllers. Quarantine and absent/stale calibration prevent upward predictive overrides, including during fade-out.

Independent calibration is an additional **simulated measurement channel**, with noise, delay and explicit failure regimes. It is not truth supplied to the controller, a hardware validation, or a solution from the original sensors alone. A startup bias shared by both channels can still be unidentifiable. The reference sensor can have startup positive/negative bias, a step, a ramp, shared inline drift or a transient spike. Calibration can be healthy, absent, biased or corrupted with the same fault.

```bash
python examples/integrity_study.py --stage develop
python examples/integrity_study.py --stage evaluate
python examples/validate_integrity_study.py
python examples/build_integrity_web.py
```

The fresh evaluation shows a **conditional protection gain with a large oxygen cost**. Under healthy independent calibration and nonclean reference-fault profiles, screened hybrid low-reservoir time is 0.58 versus 30.44 s with screening disabled (paired difference −29.85 s, 95% interval −32.32 to −26.48); empty requests fall from 2.51 s to zero. Oxygen-deficit AUC rises from 506.39 to 850.55 mL O₂/m². Calibration-only PI reaches 544.76 with 1.19 s low-reservoir time. The full engineering criterion fails: the extra reservoir exposure versus matched screened PI has an upper interval of 1.28 s, beyond the +1 s margin, and the oxygen cost versus calibration-only PI exceeds the +5 AUC margin.

With healthy calibration, the hybrid rejects 3382/3600 bias-labelled routine samples (93.9%) and 0/3120 healthy-bias samples. These are observed synthetic classifications, not clinical sensitivity/specificity. With missing calibration it rejects all routine samples, healthy and biased. Shared corruption reduces biased-sample rejection to 47/3600 (1.3%) and leaves 27.12 s mean low-reservoir exposure. Biased calibration causes rejection of every healthy-bias routine sample. This work does not solve common-mode bias or establish overall superiority.

Eight guard configurations are compared using both hybrid and matched PI; the chosen guard is common to those controllers. A calibration-only PI receives the same independent measurements and has 16 gain/setpoint candidates. The screening-disabled ablation uses the same hybrid, guard allowances and measurement channels, but accepts routine samples. Its purpose is to isolate screening, not to represent an established clinical device. Missing calibration is retained in development as a stress test; selection is based on good calibration. One earlier development-only run is preserved with exact source snapshots after separating the calibration RNG from the patient-parameter RNG.

The frozen engineering criterion requires less biased-reference reservoir exposure than the screening-disabled arm, plus bounded extra reservoir/pressure exposure and oxygen deficit versus both screened PI and calibration-only PI, under healthy calibration. Biased and missing calibration and shared corruption remain secondary. Rejected bias-labelled samples must always be reported alongside rejected healthy samples; rejecting everything is not evidence of useful detection. The chosen development setting narrowly misses the 1 s mean low-reservoir eligibility target (1.04 s) and is explicitly marked ineligible.

All reference decision logs and comparison outputs are machine-readable under `results/integrity-study/`. No clinical replacement, scientific novelty or guaranteed error bound is established. Paper drafts remain excluded.

## Previous design: PI with a selective predictive override

The `selective` controller keeps SIMC PI as its foundation. A predictive override requires two delivered reference acquisitions, sufficiently recent information and agreement between the reference-anchored mass balance and corrected inline level. Its weight changes gradually. The PI integral and pump estimate track the **actual applied command**, so fading the override returns to PI without an integral discontinuity. A recovery override cannot add flow at measured pressure ≥85 mmHg; the common pressure slowdown remains 90 mmHg.

The override can either reduce flow for reservoir risk or recover flow toward oxygen demand when a reserve appears available. Separate braking-only and recovery-only arms use the selected parameters with no extra tuning. This is a candidate upgrade within the synthetic circuit, not a demonstrated replacement for a clinical controller. Agreement between imperfect estimates is not a confidence probability: shared bias can fool the gate, and a partially blended override need not satisfy a hard braking bound. Violations remain flagged.

```bash
python examples/selective_study.py --stage develop
python examples/selective_study.py --stage evaluate
python examples/validate_selective_study.py
python examples/build_selective_web.py
python examples/selective_capacity.py
```

The fresh evaluation shows a **scoped gain, not overall superiority**. Under good references and in-range plants, oxygen-deficit AUC falls from 224.13 to 174.37 mL O₂/m² (22.2%); paired difference −49.75, 95% interval −59.49 to −41.50. The protection criterion passes: low-reservoir time is 0.36 versus 0.20 s, both have zero empty requests, and the upper paired differences remain within the predefined +1 s low/empty and +5 s pressure margins. During outages, hybrid and matched PI have AUC 190.30 and 190.20; oxygen improvement fails. Against the fast PI under good references, the oxygen interval crosses zero, so the full joint criterion fails.

The component arms show the recovery path supplies the oxygen gain; braking limits its extra reservoir exposure. Under good references, recovery-only AUC/low-reservoir time is 173.11/1.66 s, hybrid 174.37/0.36 s, and braking-only 225.60/0.00 s. With biased references, the hybrid's mean low-reservoir time is 51.03 versus 9.70 s for matched PI: shared reference error can fool the agreement gate. With no references, all physical metrics match the selected PI exactly. None of these simulations establishes clinical replacement or a universally protective controller.

The matched PI foundation (`tau_c=5`, level target 0.65 L) was selected during development before tuning the override. The final grid gives each family 16 candidates; two preceding complete development grids are preserved in `results/selective-pilot-1/` and `results/selective-pilot-2/` with exact source snapshots. Total architecture exploration is not claimed to have equal budgets. Development uses the same wide synthetic parameter ranges as final evaluation, with disjoint patient/noise seeds. Previously studied scenario families and model assumptions remain reused.

The frozen joint criterion compares the hybrid separately with **both** the development-selected PI and the previous fixed fast PI, in both good-reference and outage groups. Every comparison must pass the reservoir/pressure non-inferiority limits and show less oxygen deficit. Biased/never references and out-of-range lag are retained as secondary groups. Machine-readable logs include the component comparisons and all failed outcomes; there are no paper drafts or prose results documents.

An offline steady-state capacity screen reports when a fixed oxygen target exceeds sustainable model capacity at the declared volume/pressure limits. Stored reservoir volume and pressure transients can bridge short intervals, so this screen is neither a finite-horizon impossibility proof nor a dynamic optimal controller. It never relaxes the controller success criterion.

## Previous design: continuity between level references

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
