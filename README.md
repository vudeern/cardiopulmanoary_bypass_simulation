# Perfusion Sentinel

A cardiopulmonary bypass simulation and controller research project by Udeern Varanasi.

[Interactive replay](https://vudeern.github.io/perfusion-sentinel/) · [Portfolio](https://vudeern.github.io/projects.html) · [Model](docs/MODEL.md)

## Goal and motivation

Improve oxygen delivery while protecting reservoir volume when sensing is biased, delayed or missing and return flow is limited. This synthetic, uncalibrated circuit supports reproducible controller comparisons and a future separately tested bench prototype. It does not control equipment or establish clinical suitability.

## Current released version

### v1.15 — Complete final v1 research snapshot (current)

All work through the applied horizon-MPC pilot and fixed-ceiling conclusion belongs to **v1**, including milestones previously displayed as v2 release candidates. **v1.15.0** replaces the earlier final-v1 release at v1.14.0. [Release and packages](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/releases/tag/v1.15.0) · [V1 conclusion](docs/V1_CONCLUSION.md) · [Complete history](docs/V1_HISTORY.md).

The complete source ZIP includes controller code, historical comparisons and failures, raw results, applied traces and reproduction scripts. Wheel/sdist install the software; use the source ZIP for study reproduction. Packages do not drive equipment. The historical v1.14 tag and commit remain preserved; its superseded release listing is removed only after the replacement assets are verified.

## V1 conclusion

The applied 48-run pilot improves mean oxygen-deficit AUC by **0.1435%** versus matched PI and is about **0.0418% worse** than the existing hybrid. The tested MPC misses 10%.

Earlier development variants crossed the reservoir floor in **24/512** cases, with a minimum of **3.54 mL**. Shared-corrupted calibration failures remain unresolved. The recent small pilot does not erase those retained historical failures.

A conditional mathematical bound rules out 10% **when the recorded PI command-ceiling streams are held fixed**: an optimistic relaxation can improve mean deficit by at most about **0.0163%**. This does **not** prove all MPC designs incapable of 10%; a different controller can change future ceilings. [Argument and limitations](docs/V1_CONCLUSION.md) · [Reproducible bound](results/v1-closure/fixed-ceiling-bound.json).

No universal MPC impossibility, overall superiority, hardware validation or clinical benefit is established. All measured results and failures remain retained. Version numbers describe the research line, not scientific success.

## Current progress and next goal

The next development line is **v2: recovery-aware control**. Detect return-flow interruption from measurements, retain independent stopping/floor protection, and restore delivery promptly when measured return recovers. Compare recovery-window deficit, total deficit, recovery time, false alarms, floor exposure and empty requests against equally informed PI.

A recovery-specific benefit does not automatically satisfy the original full-run 10% release milestone. The [release evidence policy](data/version2-gates.json) and untouched confirmation cohorts remain separate requirements. Development work and negative results are published to GitHub and the portfolio.

## How to use the repository

```bash
python -m pip install -e ".[audit,horizon]"
python examples/fixed_ceiling_bound.py
python examples/feedback_study.py
python examples/validate_feedback.py
python -m unittest discover -s tests -v
perfusion-lab run --scenario compound --out results/local-run
```

Frozen protocols and historical result fields keep their original execution identifiers. The [lineage mapping](data/version-lineage.json) assigns those studies to v1 without changing measured results or source hashes. Earlier commands and reports are in [V1_HISTORY.md](docs/V1_HISTORY.md).

## Version history

| Version | Update | Snapshot |
| --- | --- | --- |
| v1.15 (current) | Complete MPC research, applied pilot and conditional fixed-ceiling conclusion | [Final v1 release](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/releases/tag/v1.15.0) |
| v1.15-dev.4 reference | 126 | 1545.77 | 0/512 | 0/128 |
| v1.15-dev.3 zero return | 1749.13 | 0/512 | 0/128 | 753.62 |
| v1.15-dev.5 (historical) | Single-anchor startup, calibrated pump hypotheses and a 4,096-run controlled/adaptive development comparison | [Current code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/main) |
| v1.15-dev.4 | Finite return-flow credit, explicit abrupt-stop challenges and a 6,144-run fixed development comparison | [Frozen code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/9d79573635bcc1760292516b70d518d7dd55881a) |
| v1.15-dev.3 | Zero-return braking reserve, explicit calibration fallback and a 2,688-run protection/delivery comparison | [Frozen code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/63c71527ca3760ccdb22235d9945b89cbdfed445) |
| v1.15-dev.2 | Calibration sets, joint braking, adaptive PI-base development and explicit worst-case failures | [Frozen code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/df071764934fbb8bdc2496363a42bf545fc28bc7) |
| v1.15-dev.1 | Measurement-only controller API, exact v1 parity and final-v1 packaging | [Frozen code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/99d7237a37115cd30ea0c99836fa6515d62c7bb1) |
| v1.14 | Historical: calibration-constrained model bank and discrete reserve | [Frozen code](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/tree/ace6a9fed2f9084b5fda95e9e1113af7a3d93dca) |
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
