# Perfusion Sentinel

A work-in-progress cardiopulmonary bypass simulation by Udeern Varanasi.

[Interactive replay](https://vudeern.github.io/perfusion-sentinel/) · [Portfolio](https://vudeern.github.io/projects.html) · [Model](docs/MODEL.md) · [Data dictionary](docs/DATA.md) · [Checks](docs/VALIDATION.md)

The project explores how sensing errors, oxygen delivery and limited venous return affect pump control. It uses an uncalibrated adult-like synthetic circuit. It does not control equipment, recommend patient settings, predict organ injury or reproduce a commercial product. There is no LivaNova affiliation.

## Version history

Versions are listed newest first. The current entry follows `main`; earlier entries link to frozen code snapshots. Historical material may differ from the current project.

| Version | Update | Snapshot |
| --- | --- | --- |
| v2.0-rc.1 (current) | Measurement-only controller API, exact v1 parity and final-v1 packaging | [Current code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/main) |
| v1.14 | Final v1: calibration-constrained model bank and discrete reserve | [Frozen code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/ace6a9fed2f9084b5fda95e9e1113af7a3d93dca) |
| v1.13 | Slowdown audit and truth-informed physical benchmarks | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/7cbb683484999ab73a79bf0fc368d682e8878ae7) |
| v1.12 | Reference screening, quarantine and independent calibration | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/ed16fcf9056d41c2ffd1eca7fe1149515780ccaf) |
| v1.11 | PI foundation with a selective predictive override | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/fe9c3cbab35d089a0af90ffdc6f9fae7b003ca07) |
| v1.10 | Reference continuity between level measurements | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/1e84727d9e064d4fca93c8e33f34cf2c98b9e917) |
| v1.9 | Predictive braking reserve | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/571f14652b7e800b57dac1a854c2a6592bdcd22c) |
| v1.8 | Verified free SIMC PI reference and matched comparison | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/7cce084e35f6e031e67057be5bc9360cfe513ee1) |
| v1.7 | Source-traced controller workbench; premature paper files removed | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/61ae1677b29fe93422e75c7cec5e0a27335c5f33) |
| v1.6 | Published-patient oxygen replay with provenance and limitations | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/03983990687231edd2879241c03ccb3aec3af872) |
| v1.5 | Bias-mechanism analysis and flow-independent baselines | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/52fc56e705cba0c23233e260a042ad65a295f3f4) |
| v1.4 | Timestamped independent level-reference comparison | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/397f505a84270ed430254e99f778151f8718178c) |
| v1.3 | Sensor drift, flow errors and unfamiliar plant dynamics | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/20b974392bc05c5ae91b71b400f8c2985a7ecfa1) |
| v1.2 | Comparison with tuned conservative baselines | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/85a1c5862af79374a5e50c7273039c08c72b81af) |
| v1.1 | Causal reservoir level-step guard and paired evaluation | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/61b74983f1681e5e80be3a24a6df9707793098fe) |
| v1.0 | Initial simulation, paired benchmark and failure analysis | [View code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/31414235c2587595a2f3c0e7e7b60b5a0632eff2) |

## Road to v2.0

The next development line is **v2.0 release candidates** at the owner’s request. Stable v2.0.0 remains a **project evidence milestone**, not clinical certification or an automatic consequence of adding features. The machine-readable policy is [version2-gates.json](data/version2-gates.json); each iteration reports [current progress](results/model-bank-study/version2-progress.json).

- At least **10% lower mean oxygen-deficit AUC** than the strongest development-eligible PI comparator with the same inputs and limits; the paired 95% interval must support improvement. Determine the comparator on development data, not after final results.
- **Zero empty-reservoir requests** in primary evaluation and mean low-reservoir time **≤1 s per 10-minute run** in each primary regime. Upper paired extra exposure must be ≤1 s low/empty and ≤5 s high pressure.
- Pass separately for **normal sensing, routine-reference bias and routine-reference outages**, within the declared independent-calibration assumptions.
- Confirm the frozen design on **two distinct fresh cohorts of at least 32 virtual patients each**, retain all failures, and pass source/artifact checks on both supported Python versions.
- Publish missing/biased/shared-corruption calibration failures and the fallback behavior. An unidentifiable shared absolute bias is not solved by labelling a release v2.0.

The original evidence policy is retained unchanged for historical hash verification; [version2-roadmap.json](data/version2-roadmap.json) records the new release-candidate numbering and exact remaining phases.

The present 16-patient evaluation is exploratory and cannot qualify for v2.0, even if some metrics pass. The synthetic parameter distribution and reused circuit model are not a validated clinical population.

## v2.0-rc.1 — Controller interface and frozen v1 package (current)

This release candidate starts the v2 development line. **Controller behavior is unchanged from v1.14; the performance milestone has not passed.** Exact parity on 24 paired 10-minute runs covers hybrid, matched PI and single-model configurations, including missing, biased and shared calibration. Every trajectory field and metric matches. This reuses old cases and is an interface regression check, not a new confirmation cohort. The check and source hashes are in [runtime parity](results/runtime-parity/summary.json).

`ControllerRuntime` accepts a `MeasurementFrame` containing the current `Observation`, measured venous flow and already-delivered timestamped level samples. It returns a bounded requested setpoint, a validity interval and explicit unsupported/conflict/quarantine/infeasibility statuses. It receives no plant object, truth, fault labels, future inputs or seed. The caller must acknowledge the setpoint actually applied before sending another frame; both the observer mass balance and PI tracking use that acknowledgement. Invalid values, future/unmatched samples and missing/duplicate frames are rejected before input state changes. Rejected input produces no new command; a future adapter must implement an independent watchdog and stop path.

```python
from perfusion_lab.runtime import ControllerRuntime, MeasurementFrame
from perfusion_lab.sensing import Observation

runtime = ControllerRuntime(bsa=1.85, initial_hb=9.0, dt=1.0)
# Illustrative measured values in the documented units, not patient settings.
obs = Observation(0.0, 4.44, 0.85, 60.0, 9.0, 0.98, 37.0, 9.0)
output = runtime.observe(MeasurementFrame(obs, venous_flow=4.44))
# Simulation acknowledges the requested setpoint. A device adapter must instead
# acknowledge the actual accepted setpoint and own independent fault handling.
runtime.acknowledge(observation_time=0.0, applied_command=output.decision.command)
```

The simulation adapter is `perfusion_lab.runtime_simulation.simulate_runtime`. Frozen v1 controller and simulation modules remain intact. The interface is fixed-step Python with histories that grow with run length; timing, bounded memory, device drivers and physical stopping remain future work. It is a foundation for a bench prototype, not equipment-ready software.

```bash
python examples/validate_runtime.py --check
python examples/check_versions.py
```

**Final v1 is v1.14.0**, pinned to `ace6a9fed2f9084b5fda95e9e1113af7a3d93dca`. The [release page](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/releases/tag/v1.14.0) provides a full frozen source ZIP, Python wheel/sdist, example configuration, reproduction instructions, manifest and checksums. The wheel installs Python modules and the original CLI; full study reproduction uses the source ZIP. Packaging verifies the frozen 398-file snapshot and never rewrites its results. The publication workflow runs only after successful source CI and never moves an existing tag or overwrites a published release. Paper drafts remain excluded.

Next: develop the estimator/reserve on 32 development patients, tune an equally informed PI comparator, freeze settings and analysis, then run two untouched 32-patient confirmation cohorts. Oxygen, reservoir and pressure gates remain unchanged. Confirmation has not started; there are **0/2 qualifying cohorts**. The final step is stable v2.0.0 only if those gates pass, followed by simulated I/O and a separately tested bench-only prototype.

## v1.14 — Calibration-constrained model bank

The new causal observer propagates a generic bank of 1, 2, 4, 8 and 12 s pump models using applied commands and measured venous inflow. The last four delivered independent calibrations fit a mass-balance intercept and venous-offset slope. Calibration error allowances, fit residuals, extrapolation weights and model-error growth define an engineering volume interval across retained models. No true reservoir volume, true pump lag or future disturbance enters the controller.

With supported calibration and a quarantined routine channel, the model/calibration path can operate independently of that rejected routine source. If the inline and bank intervals conflict, it widens to their union and disables recovery. Before calibration support exists or after model support is lost, it returns to the established guarded PI path. Shared calibration corruption and changing/unmodelled dynamics can still invalidate the estimate; this is not a calibrated confidence interval or safety proof.

The reserve calculation uses the exact discrete first-order residual tail and discrete command-ramp area across retained pump states. A recovery floor limits extra flow, and the conditional reserve cap cannot be weakened by the recovery blend. Its protection still depends on model/error/inflow assumptions. Matched PI receives the same observer; retuned calibration-only PI, the frozen v1.12 hybrid and a single-model ablation are retained as comparisons.

```bash
python examples/model_bank_study.py --stage develop
python examples/model_bank_study.py --stage evaluate
python examples/validate_model_bank_study.py
python examples/build_model_bank_web.py
python examples/check_versions.py
```

The fresh evaluation improves the **routine-reference-bias group under healthy calibration** relative to the previous hybrid: oxygen-deficit AUC falls from 853.77 to 567.17 mL O₂/m² (33.6%), with paired difference −286.60 (95% interval −320.02 to −251.31). Mean volume error falls from 44.35 to 24.98 mL. Low-reservoir time changes from 0.68 to 0.80 s (upper paired extra exposure 0.26 s), with zero empty requests. In clean-reference cases the oxygen change versus the previous hybrid is inconclusive; outage AUC improves from 588.72 to 564.08. These scoped results do not establish overall superiority.

The full criterion fails. Relative to matched model-bank PI, oxygen deficit improves by roughly 19–20%, but upper paired extra low-reservoir exposure is 1.84 s (clean), 1.39 s (bias) and 1.57 s (outage), beyond the +1 s limit. The retuned calibration-only PI has lower oxygen deficit but depletes much more in final testing (77.27 s mean low-reservoir time and 1.03 s empty requests in primary groups); it remains reported and is not discarded after seeing those failures. The hybrid has no empty requests in any primary run, but clean-reference low-reservoir time is 1.01 s, just over the 1 s milestone.

**v2.0 status: not ready.** This is one 16-patient exploratory cohort, not either of the required 32-patient confirmation cohorts. Several comparator/protection checks remain unmet. With missing calibration the new hybrid reproduces the matched PI fallback. With biased or shared-corrupted calibration the model interval can fail and depletion/empty requests remain; a narrow range is not a guarantee of correctness. The detailed milestone checks are in `results/model-bank-study/version2-progress.json`.

The new harness preserves the established timing and physiology pipeline and is tested for exact parity when using the old factories. Previous controller/orchestration files remain unchanged so frozen historical experiments remain reproducible. The study uses 4,096 development runs and 15,360 evaluation runs with fresh patient/noise seeds and pump responses different from development. Scenario families and the synthetic model remain reused. All failures and secondary calibration-corruption regimes remain in the logs; no paper drafts are generated.

## v1.13 — Audit the slowdowns before changing the controller

This is a **post-result diagnostic**, not a new sensor-based controller or fresh performance validation. Every deployed controller source hash is unchanged. The audit reuses the v1.12 patients and scenarios, compares the hybrid and both PI references, forks identical decision states, and runs two diagnostic closed-loop ablations: removing the uncertainty interval and supplying exact current reservoir volume. Unsafe ablation outcomes remain failures.

```bash
python -m pip install -e ".[audit]"
python examples/slowdown_audit.py --stage all
python examples/export_slowdown_witnesses.py
python examples/validate_slowdown_audit.py
python examples/build_slowdown_web.py
```

The declared scope is 640 diagnostic runs over eight cells and 16 previously evaluated patients, including 128 observed hybrid decision audits. A separate 96-cell physical benchmark covers every patient/physiology/plant combination in the prior 10,752-run cohort. Reference faults do not alter those physical inputs. All 96 selected witness command schedules are retained for replay through the unchanged full plant.

**There is demonstrated room within the model, but margins cannot simply be deleted.** Across the eight audit cells, observed hybrid mean oxygen-deficit AUC is 861.16 mL O₂/m². A truth-informed feasible witness reaches 512.15 with no reservoir-floor or empty-request violations; this is about 41% lower, but it uses true state, true parameters and future disturbances. Removing the interval gives AUC 567.56 while increasing low-reservoir time from 11.38 to 94.17 s and introducing empty requests. Exact volume gives 672.60 and 1.74 s, but remains noncompliant in 20 of 128 runs. It is a diagnostic, not a proposed deployable policy.

A sparse LP relaxation gives a numerically checked deficit lower bound of 287.19 under the audit weighting; the 224.96 gap to the feasible witness is unresolved. The LP assumes optimistic maximum drainage at the reservoir floor and relaxed storage, so its commands are never presented as a real controller. The finite-grid witness is feasible, not globally optimal. Both use the same declared slew, pump, reservoir and pressure constraints, with an explicit minimum-reachable initial-pressure allowance.

Of 38,742 observed slowdown decisions, 27,793 (71.7%) have at least one higher-flow first action with improved immediate true oxygen delivery and a verified emergency continuation. These local opportunities use future truth, overlap, and cannot be summed as one achievable improvement or used to delete every slowdown. Failed probes do not prove that a slowdown was physically necessary. The observer's mean interval width is 0.275 L; its lower estimate also exceeds true volume in some fault cases. Better volume estimation and reserve design need testing together.

The first audit output used a continuous residual-flow approximation. It is explicitly superseded in `data/slowdown-audit/tail-correction/`; the final audit was rerun with the exact discrete trapezoidal geometric tail and a regression test for the counterexample. No controller tuning or case selection followed this correction. No paper drafts or prose result documents are generated.

## v1.12 — Screening biased references

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

## v1.11 — PI with a selective predictive override

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

## v1.10 — Continuity between level references

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

## v1.9 — Predictive braking reserve

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

## v1.8 — Verified free SIMC PI reference

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
