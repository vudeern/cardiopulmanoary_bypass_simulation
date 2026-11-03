# Perfusion Sentinel

A work-in-progress cardiopulmonary bypass simulation by Udeern Varanasi.

[Interactive replay](https://vudeern.github.io/perfusion-sentinel/) · [Portfolio](https://vudeern.github.io/projects.html) · [Model](docs/MODEL.md) · [Data dictionary](docs/DATA.md) · [Checks](docs/VALIDATION.md)

The project explores how sensing errors, oxygen delivery and limited venous return affect pump control. It uses an uncalibrated adult-like synthetic circuit. It does not control equipment, recommend patient settings, predict organ injury or reproduce a commercial product. There is no LivaNova affiliation.

## Current comparison: verified free SIMC PI reference

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
