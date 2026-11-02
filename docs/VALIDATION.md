# Verification record and practical limits

Release 1.1.0; v1.0 baseline checks retained below. The checks below verify software behavior and numerical properties,
not accuracy for a patient or a medical device. The release environment is recorded
in `results/environment.json`.

## Completed local checks

- **26 Python unit tests pass.** Independent hand calculations check oxygen units;
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
  code execute against a dependency-free mock DOM over all 42 views, beginning/
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

