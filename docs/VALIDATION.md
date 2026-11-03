# Verification record and practical limits

Release 1.5.0; v1.0 baseline checks retained below. The checks below verify software behavior and numerical properties,
not accuracy for a patient or a medical device. The release environment is recorded
in `results/environment.json`.

## Completed local checks

- **59 Python unit tests pass.** Independent hand calculations check oxygen units;
  volume conservation is checked under aggressive alternating pump/drainage
  requests; zero-input pressure decay and steady-state flow/pressure are checked
  against analytic values. A fixed-policy refinement test checks convergence of
  the explicit reservoir transient. Invalid inputs and custom reference schedules
  are exercised. Identifiability, dropout, policy slew limits, paired noise,
  bootstrap behavior and the 42 scenario-policy combinations are also checked.
- **Editable package installation succeeds.** The Python module CLI and installed
  console entrypoint export a compound trajectory and finite metrics.
- **1,008 main runs, 392 original failure-map runs and 1,092 guard-study runs complete.** All recorded runs are
  retained in the metric CSVs. Artifact checks independently recalculate all 140
  main paired mean differences; the extension validator checks 112 additional paired intervals and all 49 new map cells and check bounds, local links and SVG parseability.
- **JavaScript syntax and DOM-contract checks pass.** The actual replay and UI
  code execute against a dependency-free mock DOM over all 136 views across five explicitly labelled datasets, beginning/
  middle/end positions, playback, reset and calculator inputs. Generated chart
  coordinates are finite and expected controls/IDs exist.
- **Release ZIP is checked** for extractability, required source/docs/web files,
  exclusion of caches and large regenerable output, and a successful smoke run
  from an extracted copy. File hashes are provided in `SHA256SUMS`.

Commands:

```bash
python -m unittest discover -s tests -v
python -m perfusion_lab.cli run --scenario compound --out /tmp/perfusion-check
node --check web/app.js
node tests/web_contract.cjs
python examples/validate_submission_study.py
python examples/validate_reference_study.py
python examples/validate_robustness_study.py
python examples/validate_conservative_study.py
python examples/validate_level_guard.py
python examples/validate_artifacts.py
```

The GitHub workflow repeats Python tests, a CLI smoke run, web-contract checks and
artifact validation on Python 3.10 and 3.12. A workflow definition is not proof of
a hosted CI pass; inspect the repository's Actions run for the published commit.

## Browser limitation

No full Chromium visual/interaction run was available in the authoring environment:
the browser executable was absent and the browser download endpoint returned HTTP
403. The mock-DOM test does not verify rendering, actual form-control clamping,
accessibility semantics, layout, keyboard interaction or browser compatibility.
The HTML is responsive and uses native controls, but a human or browser-capable CI
should review desktop/mobile layouts and keyboard navigation before treating that
aspect as visually validated.

## Scientific limitations requiring further validation

No external patient/bench calibration, clinical endpoint validation, device
comparison, sensitivity to every controller weight, systematic literature search,
formal safety proof, stochastic interval calibration or clinical deployment
qualification has been completed. The model shares structure with the predictive
policy; real plant mismatch could change the findings. Positive and negative
results remain conditional on the documented synthetic distributions and faults.


## v1.2 conservative comparison checks

The new validator independently recomputes tuning-only selection from all candidates, all 192 final paired intervals using patient blocks, 49 complete map cells, all reported means and 28 new replay metric sets. It checks disjoint seeds and all 3,192 final records. The 2,240-run pilot is archived separately and excluded from final estimates. The 70-view DOM check verifies cohort switches, policy resets, timeline reset and playback cancellation. These remain numerical/DOM checks, not full browser rendering.

## v1.3 unfamiliar-dynamics checks

Nine new tests cover exact neutral-plant equivalence, all 42 frozen original replay metric sets, independent actuator calculations, volume conservation, persistent drift, initial offsets, explicit flow-fault injection and configuration validation. The robustness validator checks 4,320 unique records, settings hashes, disjoint seeds, all 45 cell means and 1,104 paired intervals. It independently reruns all 24 new replay trajectories, including sensed/estimated level traces. The 94-view DOM test checks changing scenario lists as datasets switch. These are synthetic numerical tests, not clinical or full browser validation.

## v1.4 reference-study verification

Ten new tests check acquisition/delivery causality, timestamp matching, analytic age allowances, explicit unknown/stale response, paired random draws under dropout, common-mode contamination, ignored-reference invariance, invalid inputs and the primary decision rule. The reference-study validator checks all 8,568 unique records, development-only margin selection, the frozen selection hash, 126 final cell means, all 168 grouped paired intervals, the failed/passed primary verdict, and the separately labelled post-result descriptive contrast. It independently reruns all 30 new replays and confirms paired reference delivery counts. The DOM contract now covers all 124 views; full browser rendering remains unverified.

## v1.5 mechanism and stronger-baseline checks

Seven new tests check closed-loop and controller-level flow-bias invariance, common command/slew limits, pressure slowdown, invalid configuration and hand-calculated reduced-model equilibria. The analysis verifies 160 independent scalar cases, 6,496 unique stronger-baseline runs, development-only selection, 84 final cell means, all 60 grouped paired intervals, 384 exact sensor-only counterfactual pairs and 12 independently rerun replays. The published-range check is explicitly not external validation. Manuscript/readiness files retain the failed primary result and unresolved evidence gaps. The web contract now covers 136 views.

## Published-patient oxygen replay update

The v1.6 [patient replay](PATIENT_REPLAY.md) uses five public case-report observations. It checks oxygen arithmetic with actual inputs and explicit unmeasured-saturation assumptions. It supplies no raw reservoir series, fitted patient dynamics, held-out prediction or controller validation; those gaps above remain open. Reproduce and verify with `python examples/published_patient_replay.py --check`.
