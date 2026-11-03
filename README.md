# Perfusion Sentinel

A work-in-progress cardiopulmonary bypass simulation by Udeern Varanasi.

[Interactive replay](https://vudeern.github.io/perfusion-sentinel/) · [Portfolio](https://vudeern.github.io/projects.html) · [Model](docs/MODEL.md) · [Data dictionary](docs/DATA.md) · [Checks](docs/VALIDATION.md)

The project explores how sensing errors, oxygen delivery and limited venous return affect pump control. It uses an uncalibrated adult-like synthetic circuit. It does not control equipment, recommend patient settings, predict organ injury or reproduce a commercial product. There is no LivaNova affiliation.

## Current work: reproduce an existing controller

The reference is [Takahashi et al., 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10393111/), DOI 10.1109/JTEHM.2023.3290951. Their system combines measured venous flow, arterial-flow control and reservoir feedback with occluder actuation. The [source map and unresolved configuration](data/controller-reference/reproduction.json) records which components are verified.

Implemented source components are the nonlinear occluder flow map and third-order reference filter. Tests independently check the direct equation, inverse, analytic step response and timestep consistency. Calibration parameters must be supplied explicitly.

The comparison runner additionally provides a **flow-domain adaptation** of the reference architecture. It uses development-selected gains, the current synthetic pump actuator, explicit derivative damping/filtering and anti-windup. It does **not** implement the complete published feedforward/PID occluder loop. Exact reproduction remains blocked by unverified supplement configuration and unavailable original experimental traces. Its output cannot establish an advantage over the authors' controller.

A new noisy venous-flow measurement is provided to both the adapted baseline and matched Sentinel. A separate legacy Sentinel arm retains inferred venous flow to expose the information difference. All share the synthetic plant, flow/slew limits and reference measurements. The reference prioritizes venous-flow/level tracking; Sentinel prioritizes oxygen delivery and a reservoir floor. Those objective differences remain visible in the logged metrics.

```bash
python -m pip install -e .
python examples/controller_comparison.py
python examples/validate_controller_comparison.py
```

The runner records development candidates before final evaluation. Both families receive eight candidates and the same development conditions. Selection is frozen before evaluating new seeds, a lagged-drainage plant and a venous-sensor-bias condition. Outputs are working CSV/JSON logs under `results/controller-comparison/`. There is no publication verdict or final project conclusion.

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
