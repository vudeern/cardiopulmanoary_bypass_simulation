# V2 independent authority: delivery restored behind the stopping cap

**2.0.0rc7 — development only.** Nominal PI can now request flow without a legacy model-bank fit when the independent envelope certifies the proposed stopping cap. Startup admission, error budgets, pressure slowdown, oxygen-demand cap, 0–7 L/min range and 0.15 L/min/s slew limits remain in force. No default controller promotion or stable release is made.

## Controlled architecture comparison

The fixed study repeats rc6's 80 attempts: four plants × four calibration regimes × two reused patients × two PI arms (64), plus four nominal-pump diagnostics (16). Both arms use the same cold fixture, sensing, PI settings and independent protection authority. The fitted aggregate/joint caps remain diagnostics; neither can veto a nominal request that the independent envelope permits. This does not remove the independent stopping/floor cap.

One exploratory nominal/missing-calibration run checked the mechanism before the matrix was frozen. No gains or budgets were changed afterward. All patients are reused development cases. Historical rc6 results are retained and hash-checked; no fresh confirmation patient is used.

| Main matrix arm | rc6 mean deficit AUC | rc7 mean deficit AUC | Reduction vs same rc6 arm | rc7 floor cases | rc7 worst reservoir |
| --- | ---: | ---: | ---: | ---: | ---: |
| Aggregate nominal PI | 2319.5951 | 1993.6822 | 14.05% | 0/32 | 659.72 mL |
| Joint nominal PI | 2314.6113 | 1993.6822 | 13.87% | 0/32 | 659.72 mL |

AUC units: mL O₂/m² per full 600-second run. Missing-calibration mean deficit falls from **2800.0 to 1992.8580 (28.83%)**, because the independent bound now permits useful flow. Healthy-calibration reductions are 7.85% and 7.62%; biased/shared-calibration reductions are 7.57% and 7.26% against the respective rc6 arms. All-channel shared-bias diagnostic reductions are 10.17% and 9.85%. These are changes from the previous architecture, not superiority over equally informed PI.

**The two new PI arms have identical commands in every admitted pair and identical main-matrix deficit: 0% matched-PI gain.** The historical joint hypothesis calculation no longer changes the applied action once both arms share the same authoritative envelope. Exceeding 10% relative to a restricted rc6 reference does not meet the release requirement against the strongest equally informed PI.

## Protection and rejected starts

All **68 admitted runs** retain a stopping certificate from the first observation, with no later uncertified step, observed reservoir-floor crossing, empty request, high-pressure case, lower-bound coverage failure or cap violation. The worst reservoir over all admitted runs is **611.14 mL** (659.72 mL in the main matrix). The same **12 starts are rejected before any command**: four without a level-error contract, four hot starts and four insufficient-volume starts. Rejections have no fabricated safe-run or deficit metrics.

The engineering assumptions remain 0.30 L absolute inline/anchor errors, a 1–20 s actuator-lag interval and 0.10 L/min startup-flow error. They are not validated sensor specifications; unbounded Gaussian errors and out-of-contract common corruption are not solved. Rejection does not physically stop a moving pump. This is a synthetic simulation runtime, not equipment priming, a watchdog or a clinical controller.

## Reproduce and audit

```bash
python -m pip install -e ".[audit,horizon]"
python examples/authority_v2_study.py
python examples/validate_authority_v2.py
python -m unittest discover -s tests -v
node tests/web_contract.cjs
```

- [Frozen protocol](../results/v2-authority/protocol.json), [all attempts](../results/v2-authority/attempts.json), [summary](../results/v2-authority/summary.json), [checksums](../results/v2-authority/checksums.json)
- Full-precision traces: four lossless per-plant ZIPs in `results/v2-authority/`.
- [Runtime](../src/perfusion_research/authority_v2.py), [focused tests](../tests/test_authority_v2.py), [validator](../examples/validate_authority_v2.py)

Validation independently recomputes physical deficit/floor/pressure metrics, checks motor and volume bounds against simulated truth, verifies actual-plant ramp-to-zero stopping loss, startup/slew limits, source/reference/archive/member hashes and all aggregate denominators, and replays admitted and rejected examples. Applied commands are compared across every matched pair. True state and actual plant lag are analysis-only and do not enter runtime decisions.

## Next step

Retune the PI reference on development patients with this same independent authority, then evaluate the full primary-regime matrix. Identify a causal recovery-control change that can improve over that reference while preserving protection. Freeze only after the release gates pass, then run two untouched cohorts of at least 32 patients each. Stable v2, hardware readiness and clinical benefit remain unqualified.
