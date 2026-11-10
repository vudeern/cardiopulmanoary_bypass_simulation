# V2 zero-return stopping comparison

**2.0.0rc3 — development only.** Final v1 remains v1.15.0. This follow-up tests whether joint pump/volume accounting retains a delivery benefit when the stopping calculation credits no future return.

## Fixed four-way design

Cross aggregate versus joint model accounting with zero versus 15-second return credit. All arms use the same fast PI, point estimate, causal observer, raw sensing, calibration allowances, pump-model set, 0.29 L stopping-budget floor, 0.25 L outcome floor, pressure rule and 0.15 L/min/s slew. Joint accounting checks every retained model with its own volume bound; aggregate accounting combines extrema across models.

The zero-credit arms set `return_horizon_s=0`. The existing reserve then equals the complete ramp-to-zero plus infinite pump coast-down loss with zero inflow, regardless of current measured return. This removes future-inflow credit from the stopping check. It does not establish that calibration/model bounds are valid, that initial or unsupported states are viable, or that model updates preserve recursive feasibility.

The matrix contains **40 new zero-credit simulations and 40 retained reference runs**, not 80 new simulations. The credit references are the exact published v2 joint-pilot cases, linked by trace path and SHA-256 rather than copied or counted as independent replication. All arms use the same two reused development patients, nominal/slow pumps and five cases: normal return, single interruption, repeated interruptions, repeated with +0.8 L/min venous-sensor bias, and repeated with 0.15 L/min venous-sensor noise SD. Each run lasts 600 seconds at 1-second steps. Independent calibration and routine references remain healthy.

## Full-run results

| Accounting / stopping credit | Mean deficit AUC | Floor cases | Worst reservoir |
| --- | ---: | ---: | ---: |
| Aggregate / 15 seconds, retained | 1557.7040 | 0/20 | 438.26 mL |
| Joint / 15 seconds, retained | 1448.9302 | 8/20 | 68.10 mL |
| Aggregate / zero, new | 1759.8195 | 0/20 | 441.79 mL |
| Joint / zero, new | 1695.2686 | 0/20 | 435.68 mL |

Deficit AUC units: mL O₂/m². Each arm has 20 runs from only two patients. All four arms have zero empty-request and high-pressure cases in this matrix. Observed floor exposure is zero for both new arms. These are finite development observations, not a general safety guarantee.

**Joint accounting reduces mean deficit by 3.67% versus aggregate accounting when both use zero future return.** That separates a model-association benefit from optimistic return credit.

| Case | Aggregate zero deficit | Joint zero deficit | Reduction |
| --- | ---: | ---: | ---: |
| Normal return | 1659.5469 | 1554.7153 | 6.32% |
| Single interruption | 1719.0973 | 1661.8192 | 3.33% |
| Repeated interruptions | 1804.2777 | 1753.7622 | 2.80% |
| Repeated + biased return sensor | 1806.0961 | 1756.3994 | 2.75% |
| Repeated + noisy return sensor | 1810.0797 | 1749.6468 | 3.34% |

Each row contains four paired cases from two patients. There are no untouched confirmation cohorts in these results.

The stricter stopping assumption has a delivery cost. Joint zero-credit control has **8.83% more deficit than the retained aggregate 15-second-credit PI**, which also has no observed floor crossings on this small matrix. Thus the new arm does not establish overall superiority over that reference. Compared with the failed joint-credit arm, floor failures disappear in these matched cases, while deficit rises. Removing speculative return credit is a robustness choice with a measured cost.

## What this establishes

The model-association gain survives without future-return credit, and the new joint arm avoids the previously observed interruption floor failures on these cases. Its gain is below 10%, and neither this two-patient development sample nor zero observed failures qualifies stable v2. The zero-return reserve remains conditional on retained dynamics and valid calibration/volume bounds; noise is not deterministically bounded by a standard deviation. Shared calibration corruption and dynamics outside the model envelope remain unresolved.

Both confirmation cohorts remain untouched. The new arm is retained for broader development, without changing the default controller or claiming hardware/clinical validation.

## Evidence and reproduction

- [Frozen protocol, source hashes and retained-reference hashes](../results/v2-zero-pilot/protocol.json)
- [Summary](../results/v2-zero-pilot/summary.json), [all 80 arm/case records](../results/v2-zero-pilot/runs.json), [new artifact checksums](../results/v2-zero-pilot/checksums.json)
- Forty new 600-step CSV traces in `results/v2-zero-pilot/`; retained credit traces stay in `results/v2-joint-pilot/`
- [Study driver](../examples/zero_v2_study.py), using the unchanged [joint controller](../src/perfusion_research/joint_v2.py)

```bash
python -m pip install -e ".[audit,horizon]"
python examples/zero_v2_study.py
python examples/validate_zero_v2.py
python -m unittest discover -s tests -v
```

Validation checks every source and retained-reference hash, recomputes full/recovery deficits and floor/empty/pressure outcomes from all traces, checks applied cap/slew/model margins, verifies group totals, and replays a noisy repeated-stop pair. Independent tests integrate a discrete ramp and infinite coast-down tail for multiple pump lags, and check that a fixed-hypothesis zero-credit cap is independent of measured return. That does not make the observer itself independent of return sensing.

## Next goal

Broaden the zero-credit aggregate/joint comparison across the existing development calibration-fault regimes and pump-model mismatch, keeping the protocol fixed before execution and retaining every failure. Check model-set support and initial/unsupported-state behavior before a design freeze. This step should establish where the improved calculation remains useful and where it fails; it is not a reason to consume reserved confirmation cohorts yet.
