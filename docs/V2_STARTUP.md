# V2 startup/priming admission interlock

**2.0.0rc6 — development only.** The runtime now requires a feasible independent held-zero stopping bound before issuing a first command. This addresses the previous uncertified-start behavior within a declared admissible-start contract. It does not physically prime a circuit, stop a rejected moving pump, implement a watchdog, or establish hardware/clinical suitability.

## What changed

The adapter must establish a held-zero setpoint before creating this runtime. At observation time zero, the runtime bounds initial motor flow from the measured startup flow plus/minus a declared **0.10 L/min** sensor-error budget. It builds the same carried independent envelope used previously, with **0.30 L** absolute level/anchor error budgets and a **1–20 second** pump-lag range. These remain illustrative engineering assumptions, not validated sensor specifications or Gaussian guarantees.

Admission requires a bounded level source and a nonnegative stopping margin for holding zero. Only then are controller command/tracking states initialized consistently at zero and optimizer motor points initialized from the startup measurement. Normal **0.15 L/min/s** ramping and the independent/legacy caps remain in force. Invalid frames or rejected starts issue no command. A higher-than-protected applied acknowledgement is recorded and latches an actuation-contract violation; an external adapter must own any independent equipment-stop action.

The simulation has a new, explicit cold fixture: motor flow and pressure start at zero, with reservoir volume 0.85 L. Both PI arms receive the same physical initial state, sensing, startup-flow error budget and interlock. Historical equations and warm-start studies remain unchanged. Because the initial condition changed, warm-start deficit values are **not** a fair performance-improvement denominator.

The interlock does not add fluid or operate priming hardware. A separate unprimed fixture has only 0.35 L. The hot fixture retains the inherited already-moving pump. Those inputs are rejected when the measured bounds cannot support a held-zero stop. Rejection is an admission decision, not a demonstration that an already moving system stopped safely.

## Fixed study: 80 attempts, 68 completions, 12 rejections

The study reuses two development patients. Its main matrix has four plant variants × four calibration regimes × two patients × two matched PI arms: 64 attempts. Four nominal-pump diagnostic conditions add 16 attempts. All admitted runs last 600 seconds with the previous repeated-return interruptions; the controller receives no event schedule. No outcome-based tuning or fresh confirmation cohort is used.

| Condition group | Attempts | Completed runs | Rejected before command |
| --- | ---: | ---: | ---: |
| Main calibration/model matrix | 64 | 64 | 0 |
| Inline + routine + calibration share +0.22 L bias | 4 | 4 | 0 |
| No declared level-error contract | 4 | 0 | 4 |
| Already-moving hot start | 4 | 0 | 4 |
| Insufficiently primed volume | 4 | 0 | 4 |

Rejected attempts retain their reason and measured-bound details. They have **no fabricated zero deficit, floor exposure or empty-request metrics**, and no 600-step trace. Their outcomes cannot be counted as safe completed runs. Each diagnostic group uses the same two patients and both arms; it is not an independent four-patient cohort.

## Completed-run results

| Main matrix arm | Mean deficit AUC | Floor cases | Initially uncertified | Worst reservoir |
| --- | ---: | ---: | ---: | ---: |
| Aggregate PI + interlock/envelope | 2319.5951 | 0/32 | 0/32 | 691.82 mL |
| Joint PI + interlock/envelope | 2314.6113 | 0/32 | 0/32 | 691.01 mL |

Deficit AUC units: mL O₂/m² per full run. **All 68 admitted runs have a stopping certificate from the first frame, no later uncertified steps, and no observed floor crossing, empty request, high-pressure case or volume-lower-bound coverage failure.** The four admitted shared-bias diagnostics have a worst volume of 613.63 mL. These finite simulation outcomes remain conditional on the declared contracts; unbounded or undetectable out-of-contract shared error is not solved.

Joint deficit improves only **0.21%** versus equally protected aggregate PI on the main matrix. That misses the 10% milestone. Warm-start historical values are retained by hash for provenance, not presented as a controlled delivery comparison.

A remaining delivery bottleneck is explicit: with independent calibration missing, the legacy nominal/model-bank gate holds flow commands at zero despite an available inline protection bound and valid stopping certificate. Full-run deficit is **2800.0** in every such run. Admission and floor protection alone do not establish useful oxygen delivery.

## Evidence and reproduction

- [Frozen protocol and warm-reference hashes](../results/v2-boot/protocol.json)
- [Summary](../results/v2-boot/summary.json), [all 80 attempt records](../results/v2-boot/attempts.json), [artifact checksums](../results/v2-boot/checksums.json)
- Full-precision traces for the 68 completed runs are losslessly stored in four per-plant ZIPs in `results/v2-boot/`.
- [Admission runtime](../src/perfusion_research/boot_v2.py), [explicit simulation initialization adapter](../src/perfusion_research/boot_simulation.py), [interlock tests](../tests/test_boot_v2.py)

```bash
python -m pip install -e ".[audit,horizon]"
python examples/boot_v2_study.py
python examples/validate_boot_v2.py
python -m unittest discover -s tests -v
```

Validation checks source/reference/archive/member hashes, all attempt outcomes and rejection denominators, initial/ramp command limits, actual-plant stopping loss, motor-state interval coverage, level/error budgets, physical metrics, aggregates and admitted/rejected replays. Analysis-only true state and plant lag do not enter the controller. Unit tests cover primed admission, hot/unprimed/no-bound rejection, invalid-frame handling and higher-applied-command latching.

## What remains before a stable v2 release

Startup admission is implemented and passes this fixed admissible-start development matrix. It still needs broader regime validation under its declared contract. Next, remove the redundant legacy fit gate from nominal request generation **only where the independent protection envelope is authoritative and feasible**, provide exactly the same authority to PI, and measure the delivery change. Never remove the independent floor/stopping cap to gain performance.

Retune the equally informed PI reference before any design freeze. The ≥10% gain and full primary-regime evidence remain unmet; both fresh confirmation cohorts remain untouched. No default controller promotion, hardware priming, emergency-stop guarantee or stable v2 release is claimed.
