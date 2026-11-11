# Perfusion Sentinel

A cardiopulmonary bypass simulation and controller research project by Udeern Varanasi.

[Interactive replay](https://vudeern.github.io/perfusion-sentinel/) · [Portfolio](https://vudeern.github.io/projects.html) · [Model](docs/MODEL.md)

## Goal and motivation

Improve oxygen delivery while protecting reservoir volume when sensing is biased, delayed or missing and return flow is limited. This synthetic, uncalibrated circuit supports reproducible controller comparisons and a future separately tested bench prototype. It does not control equipment or establish clinical suitability.

## Current released version

### v1.15 — Complete final v1 research snapshot

All work through the applied horizon-MPC pilot and fixed-ceiling conclusion belongs to **v1**, including milestones previously displayed as v2 release candidates. **v1.15.0** replaces the earlier final-v1 release at v1.14.0. [Release and packages](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/releases/tag/v1.15.0) · [V1 conclusion](docs/V1_CONCLUSION.md) · [Complete history](docs/V1_HISTORY.md).

The complete source ZIP includes controller code, historical comparisons and failures, raw results, applied traces and reproduction scripts. Wheel/sdist install the software; use the source ZIP for study reproduction. Packages do not drive equipment. The historical v1.14 tag and commit remain preserved; its superseded release listing is removed only after the replacement assets are verified.

## V1 conclusion

The applied 48-run pilot improves mean oxygen-deficit AUC by **0.1435%** versus matched PI and is about **0.0418% worse** than the existing hybrid. The tested MPC misses 10%.

Earlier development variants crossed the reservoir floor in **24/512** cases, with a minimum of **3.54 mL**. Shared-corrupted calibration failures remain unresolved. The recent small pilot does not erase those retained historical failures.

A conditional mathematical bound rules out 10% **when the recorded PI command-ceiling streams are held fixed**: an optimistic relaxation can improve mean deficit by at most about **0.0163%**. This does **not** prove all MPC designs incapable of 10%; a different controller can change future ceilings. [Argument and limitations](docs/V1_CONCLUSION.md) · [Reproducible bound](results/v1-closure/fixed-ceiling-bound.json).

No universal MPC impossibility, overall superiority, hardware validation or clinical benefit is established. All measured results and failures remain retained. Version numbers describe the research line, not scientific success.

## Current progress: v2.0.0rc7 independent delivery authority

The new development line is **v2: recovery-aware control**, version **2.0.0rc7**. Detect return-flow interruption from measurements, retain independent stopping/floor protection, and restore delivery promptly when measured return recovers. Compare recovery-window deficit, total deficit, recovery time, false alarms, floor exposure and empty requests against equally informed PI.

**Independent delivery authority implemented:** nominal PI requests can now proceed without a legacy fit only when the independent stopping envelope is feasible. In the repeated 80-attempt development matrix, **68 runs complete with certificates from the first frame and no observed floor/empty/high-pressure outcomes; 12 starts remain rejected**. Mean deficit falls **14.05% versus rc6 aggregate PI** (13.87% versus rc6 joint PI), but the two equally informed updated PI arms produce **identical commands: 0% matched-PI gain**. This architecture gain does not satisfy the 10% release milestone. [Results, retained references and limitations](docs/V2_AUTHORITY.md).

**Previous startup admission:** the runtime now requires a feasible independent held-zero stopping bound before any first command. Both arms use an explicitly cold, primed simulation fixture and consistent zero-command initialization. Of **80 attempts, 68 complete with certificates from time zero and no observed floor/empty/high-pressure outcomes; 12 are explicitly rejected**, not counted as safe runs. Main-matrix joint deficit improves only **0.21%** versus equally protected PI. [Contract, fixture change, rejections, results and remaining bottleneck](docs/V2_STARTUP.md).

**Previous envelope implementation:** both PI arms now share a separate raw-level/anchor error envelope, command-derived pump interval and zero-return stopping cap. The final 64-case matrix has **0/32 floor failures per arm**, versus 2/32 and 6/32 for retained references; eight extra bias/unsupported cases also have zero observed failures. Joint delivery gain versus equally protected PI is only **0.17%**, and the additional protection costs delivery. All 72 final runs start uncertified; no contract means conservative braking without a certificate. [Architecture, both implementation stages, costs and startup blocker](docs/V2_ENVELOPE.md).

**Previous boundary study:** 56 new simulations plus eight hashed references cover four plants and four calibration regimes. Joint zero-return control crosses the 250 mL floor in **6/32 cases**, versus **2/32** for aggregate PI. Worst volumes are **229.96 mL** and **237.87 mL**. Healthy-calibration mean deficit falls 2.42%, but bias/shared-corruption failures block both designs from freezing. Observer support sometimes coexists with incorrect volume bounds. [Full results and failure diagnosis](docs/V2_ROBUSTNESS.md).

**Previous v2 comparison:** 40 new zero-credit runs plus 40 hashed references complete the aggregate/joint × zero/15-second-credit design. Joint accounting lowers deficit by **3.67% versus aggregate accounting under the same zero-return assumption**, with **0/20 floor cases** and a worst volume of **435.68 mL**. The retained joint-credit arm had 8/20 floor cases. Joint zero-credit control still has **8.83% more deficit than the older aggregate credit reference**. It is a limited development gain, not overall superiority or stable-v2 qualification. [Full four-way results](docs/V2_ZERO_RETURN.md).

**Previous v2 experiment:** a 40-run matched-PI study preserves each retained pump model's own volume and stopping calculation instead of combining extrema from different models. Normal-return deficit falls **12.58%**, but the candidate crosses the 250 mL floor in **8/20 runs**, versus **0/20** for aggregate PI. Worst volume is **68.10 mL**. It is **not selected**. [Results, conditional argument and failure replay](docs/V2_JOINT.md).

**Next controller goal:** retune PI with the new independent authority and evaluate the full primary regimes. Then test a causal recovery change against that strongest equally informed reference. The ≥10% matched-PI target, broader evidence and fresh confirmation remain unmet.

**First v2 pilot completed:** 24 runs on two reused development patients. Interruption and recovery detection latency is 1 second in all four recovery-arm interruption cases, with no false alarms in its eight cases. Recovery-aware fast PI and matched fast PI produce identical commands: **0% added deficit reduction**. All 24 runs have zero observed floor crossings, empty requests and cap violations. [Results, limitations and next design question](docs/V2_RECOVERY.md).

A recovery-specific benefit does not automatically satisfy the original full-run 10% release milestone. The [release evidence policy](data/version2-gates.json) and untouched confirmation cohorts remain separate requirements. Development work and negative results are published to GitHub and the portfolio.

## How to use the repository

```bash
python -m pip install -e ".[audit,horizon]"
python examples/fixed_ceiling_bound.py
python examples/authority_v2_study.py
python examples/validate_authority_v2.py
python -m unittest discover -s tests -v
perfusion-lab run --scenario compound --out results/local-run
```

Frozen protocols and historical result fields keep their original execution identifiers. The [lineage mapping](data/version-lineage.json) assigns those studies to v1 without changing measured results or source hashes. Earlier commands and reports are in [V1_HISTORY.md](docs/V1_HISTORY.md).

## Version history

| Version | Update | Snapshot |
| --- | --- | --- |
| v2.0.0rc7 (development; performance unqualified) | Remove legacy fit veto behind independent cap; 14.05% gain vs rc6, 0% vs equally informed PI | [Study](docs/V2_AUTHORITY.md) |
| v2.0.0rc6 (development; performance unqualified) | Startup admission, explicit rejections and certified-from-first-frame cold starts | [Study](docs/V2_STARTUP.md) |
| v2.0.0rc5 (development; startup/performance blocked) | Independent protection envelope, carried bounds and varying-lag stopping check | [Study](docs/V2_ENVELOPE.md) |
| v2.0.0rc4 (development; freeze blocked) | Calibration/model boundary study exposes floor failures and incorrect supported bounds | [Study](docs/V2_ROBUSTNESS.md) |
| v2.0.0rc3 (development) | Zero-return joint cap: 3.67% gain vs matched zero-return aggregate PI; no observed floor failures | [Study](docs/V2_ZERO_RETURN.md) |
| v2.0.0rc2 (development; candidate rejected) | Joint model cap: normal-return gain, interruption floor failures | [Study](docs/V2_JOINT.md) |
| v2.0.0rc1 (historical development) | Recovery-aware interruption and resumption pilot | [Study](docs/V2_RECOVERY.md) |
| v1.15 (final v1 release) | Complete MPC research, applied pilot and conditional fixed-ceiling conclusion | [Final v1 release](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/releases/tag/v1.15.0) |
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
