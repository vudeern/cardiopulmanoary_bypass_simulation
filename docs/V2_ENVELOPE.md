# V2 independent protection envelope

**2.0.0rc5 — development only.** This update implements a separate protection path rather than treating an optimization observer's fit status as safety evidence. Final v1 remains v1.15.0; stable v2 remains unqualified.

## Implemented architecture and declared scope

The optimization observer, its fitted model bank and existing PI gains remain unchanged. A separate envelope clips both aggregate and joint PI through the same additional command cap. It uses raw absolute level readings, delayed calibration samples, acknowledged commands and configured error/dynamics budgets. It receives no true volume, injected fault magnitude or event schedule.

The illustrative simulation contract is:

- Absolute inline-level and calibration errors each bounded by **0.30 L**, when their contract is available. This budget covers the known 0.22 L development corruption with an engineering allowance; it is not a validated sensor specification or Gaussian coverage guarantee.
- Pump lag in **[1, 20] seconds**, initial motor flow within **0.10 L/min** of the configured starting flow, exact command acknowledgement and nonnegative return.
- The same 0.29 L stopping-budget floor, 0.25 L outcome floor, 7 L/min command limit and **0.15 L/min/s** slew. No future inflow is credited.

The envelope subtracts its declared error from raw level readings. Delayed anchors are propagated from acquisition time by subtracting an independent upper bound on pumped volume, assuming zero incoming return. No model-fit pruning narrows that safety path. The final implementation also carries its previous valid lower bound through mass balance, so a noisier new reading cannot discard a stronger existing bound.

A command-only motor interval propagates over the full lag range. The final stopping calculation bounds a descending command ramp and its infinite coast-down even when lag changes step by step within the declared range: while command exceeds flow, the fastest lag maximizes next flow; once braking command falls below flow, the slowest lag maximizes all subsequent flow. The decreasing ramp permits one switch, followed by an analytic tail. Unit tests compare this calculation with independent discrete rollouts and test continued feasibility under adversarial bounded readings and changing lag.

If no bounded channel or propagated bound exists, the envelope reports unavailable information and commands maximum permitted braking. A negative stopping margin is explicitly uncertified. Neither that fallback nor sensor agreement guarantees safety from an initially unviable state or when the declared contracts are false. A certificate applies only when the protected setpoint is actually held; a higher applied command breaks it. The runtime records acknowledgements but implements no equipment stop, I/O scheduler or independent watchdog.

## Fixed cases and adaptive implementation follow-up

Both new arms receive identical budgets and clipping authority. Each implementation stage runs 72 simulations: the previous four-plant/four-calibration matrix (64 cases), four nominal-pump cases where inline, routine and calibration channels all share +0.22 L bias, and four cases with no declared channel contract and missing calibration. The same two development patients are reused.

The first stage avoided observed floor crossings, but had **614 uncertified steps after stopping had first become feasible**. Its source, full results and traces are retained. An explicitly adaptive follow-up adds carried lower bounds and the conservative varying-lag stopping calculation, with no budget or gain changes; that follow-up is frozen before its outcomes. It has **zero** such later uncertified steps. These stages are development iterations, not independent confirmation.

There are **144 new simulations across the two implementation stages and 64 unique retained rc4 references**. Each stage's 136-record view includes the same 64 references; those references are not counted twice as new evidence. Neither confirmation cohort is used.

## Final primary comparison

| Controller / protection path | Mean deficit AUC | Floor cases | Worst reservoir |
| --- | ---: | ---: | ---: |
| Retained aggregate PI, no independent envelope | 2092.7254 | 2/32 | 237.87 mL |
| Retained joint PI, no independent envelope | 2058.1896 | 6/32 | 229.96 mL |
| Aggregate PI + final envelope | 2305.5807 | 0/32 | 454.89 mL |
| Joint PI + final envelope | 2301.7409 | 0/32 | 454.89 mL |

Deficit AUC units: mL O₂/m² per full run. Each arm has 32 runs from two reused patients. The final envelope arms have zero empty requests, high-pressure cases, observed lower-bound coverage failures and applied cap/slew violations on this matrix. The eight additional cases also have no observed floor/empty/high-pressure outcomes. Shared bias within the declared budget is bounded, not identified or corrected as truth.

**Joint PI improves deficit only 0.17% versus equally protected aggregate PI.** The final envelope increases deficit by **10.17%** for aggregate PI and **11.83%** for joint PI relative to their retained unshielded references. Those references do not use the new protection contract, so this is a measured architecture trade-off, not evidence of MPC or overall performance superiority. Missing calibration still makes the old nominal controller brake conservatively even when an inline protection bound exists.

## Startup remains an explicit blocker

The inherited simulator starts with 0.85 L volume and the pump already flowing at 2.4×BSA. **All 72 final runs begin without a feasible stopping certificate** under the declared worst-case contract. Maximum permitted braking is recorded, not labelled safe. The four no-contract runs never obtain a certificate. The remaining 68 eventually become feasible and have no later certificate loss in these traces.

The scenario's initial return permits recovery in these runs; that is not a zero-return guarantee from time zero. A release-ready startup path must establish an initially feasible envelope before ramping flow, or explicitly reject the starting state. A later fallback cannot repair an already inevitable violation. The mathematical envelope also remains conditional on valid channel budgets and pump/error assumptions; unbounded shared corruption is not solved.

## Evidence and reproduction

- [Final frozen protocol](../results/v2-envelope-carry/protocol.json), [summary](../results/v2-envelope-carry/summary.json), [run records](../results/v2-envelope-carry/runs.json), [checksums](../results/v2-envelope-carry/checksums.json)
- [First implementation protocol](../results/v2-envelope/protocol.json), [results](../results/v2-envelope/summary.json), [run records](../results/v2-envelope/runs.json), [checksums](../results/v2-envelope/checksums.json)
- Full-precision CSV traces are stored losslessly in four per-plant ZIPs in each result directory.
- [Independent envelope/runtime](../src/perfusion_research/envelope_v2.py), [carried-bound follow-up](../src/perfusion_research/envelope_carry_v2.py), [tests](../tests/test_envelope_carry_v2.py)

```bash
python -m pip install -e ".[audit,horizon]"
python examples/envelope_v2_study.py
python examples/envelope_carry_study.py
python examples/validate_envelope_v2.py
python -m unittest discover -s tests -v
```

Validation checks both immutable implementation stages, all source/reference/archive/member hashes, recomputed truth metrics, actual-plant stopping loss, motor-state upper coverage, declared sample budgets, feasible margins, normal braking fallback, groups and fault replays. Analysis-only truth and plant lag never enter the controller. Passing these reproduction checks does not qualify the design for release.

## Next steps and release status

Implement an explicit startup/priming interlock that requires a feasible envelope before ramping the pump. Then work on delivery performance within justified budgets, retune the equally informed PI reference, and freeze only after the full development gates pass. The ≥10% target remains unmet, startup is not certified, and both fresh confirmation cohorts remain untouched. No stable v2, hardware validation or clinical suitability is claimed.
