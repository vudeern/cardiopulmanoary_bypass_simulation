# Recorded benchmark results

24 synthetic patients, seeds 100–123; 20 minutes/run; dt = 2 s; target = 280 mL/min/m². These are simulation outputs, not measured patient outcomes.

| Scenario | Policy | Deficit AUC (mL/m²) | Low reservoir (s) | False reassurance (s) | Mean flow (L/min) | Hb bound coverage |
|---|---|---:|---:|---:|---:|---:|
| nominal | fixed | 0.00 | 0.00 | 0.00 | 4.64 | 0.99 |
| nominal | reactive | 6.94 | 0.00 | 270.83 | 4.27 | 0.99 |
| nominal | sentinel | 0.08 | 0.00 | 2.33 | 4.45 | 0.99 |
| nominal | no_calibration | 0.00 | 0.00 | 0.00 | 4.45 | 1.00 |
| nominal | no_lookahead | 0.08 | 0.00 | 2.33 | 4.45 | 0.99 |
| hemodilution | fixed | 487.05 | 0.00 | 2.08 | 4.64 | 0.99 |
| hemodilution | reactive | 13.18 | 0.00 | 253.92 | 5.01 | 0.99 |
| hemodilution | sentinel | 7.06 | 0.00 | 3.75 | 5.22 | 0.99 |
| hemodilution | no_calibration | 6.92 | 0.00 | 0.17 | 5.21 | 1.00 |
| hemodilution | no_lookahead | 7.06 | 0.00 | 3.75 | 5.22 | 0.99 |
| hb_bias | fixed | 404.42 | 0.00 | 817.42 | 4.64 | 0.86 |
| hb_bias | reactive | 766.46 | 0.00 | 519.83 | 4.21 | 0.86 |
| hb_bias | sentinel | 54.46 | 0.00 | 205.83 | 5.05 | 0.86 |
| hb_bias | no_calibration | 625.66 | 0.00 | 849.83 | 4.38 | 0.29 |
| hb_bias | no_lookahead | 54.46 | 0.00 | 205.83 | 5.05 | 0.86 |
| venous_obstruction | fixed | 0.00 | 6.92 | 0.00 | 4.64 | 0.99 |
| venous_obstruction | reactive | 6.94 | 0.00 | 270.83 | 4.27 | 0.99 |
| venous_obstruction | sentinel | 2.90 | 0.00 | 5.50 | 4.44 | 0.99 |
| venous_obstruction | no_calibration | 2.87 | 0.00 | 3.33 | 4.44 | 1.00 |
| venous_obstruction | no_lookahead | 0.08 | 9.08 | 2.33 | 4.45 | 0.99 |
| oxygenator_loss | fixed | 290.77 | 0.00 | 19.92 | 4.64 | 0.99 |
| oxygenator_loss | reactive | 10.43 | 0.00 | 262.08 | 4.80 | 0.99 |
| oxygenator_loss | sentinel | 0.12 | 0.00 | 3.83 | 4.99 | 0.99 |
| oxygenator_loss | no_calibration | 0.00 | 0.00 | 0.00 | 4.98 | 1.00 |
| oxygenator_loss | no_lookahead | 0.12 | 0.00 | 3.83 | 4.99 | 0.99 |
| compound | fixed | 596.81 | 0.00 | 497.42 | 4.64 | 0.83 |
| compound | reactive | 617.94 | 24.00 | 460.17 | 4.54 | 0.83 |
| compound | sentinel | 98.25 | 0.00 | 331.50 | 5.20 | 0.83 |
| compound | no_calibration | 520.79 | 0.00 | 704.00 | 4.70 | 0.41 |
| compound | no_lookahead | 82.03 | 66.50 | 309.75 | 5.25 | 0.83 |
| unmodeled_level_bias | fixed | 404.42 | 37.92 | 3.92 | 4.64 | 0.99 |
| unmodeled_level_bias | reactive | 13.93 | 139.58 | 256.50 | 4.92 | 0.99 |
| unmodeled_level_bias | sentinel | 6.18 | 149.92 | 8.83 | 5.13 | 0.99 |
| unmodeled_level_bias | no_calibration | 6.04 | 153.25 | 5.33 | 5.12 | 1.00 |
| unmodeled_level_bias | no_lookahead | 5.28 | 151.83 | 7.25 | 5.13 | 0.99 |

## Sentinel versus reactive, paired differences

Negative deficit AUC differences favor Sentinel. Intervals are 95% percentile bootstrap intervals over virtual-patient pairs, with 2,000 resamples and seed 2026. No multiplicity correction is applied.

| Scenario | Mean difference | Bootstrap interval |
|---|---:|---:|
| nominal | -6.86 | [-7.33, -6.40] |
| hemodilution | -6.11 | [-13.47, 7.85] |
| hb_bias | -712.00 | [-727.62, -695.96] |
| venous_obstruction | -4.03 | [-5.86, -1.72] |
| oxygenator_loss | -10.31 | [-10.76, -9.86] |
| compound | -519.69 | [-540.41, -495.41] |
| unmodeled_level_bias | -7.76 | [-11.57, -0.99] |

## Interpret the failures

Compound disturbance: calibration reduces delivery deficits in this model; reservoir look-ahead trades a larger delivery deficit for less time below the reservoir floor. This is a tradeoff, not universal dominance.

Unmodeled level bias: Sentinel averages more low-reservoir time and more empty-reservoir requests than reactive despite its better oxygen-delivery metric. An apparently favorable oxygen score can conceal another failure. This invalidates a global safety claim.

Hb bounds are not calibrated intervals: empirical coverage falls during bias and compound faults. False reassurance remains substantial after correction because inline monitoring itself remains biased and the reference is intermittent.

Fixed flow has zero nominal deficit in this sampler but uses more average flow than reactive. The benchmark does not measure hemolysis, neurological injury, renal injury, clinical workload, or clinical benefit.


## v1.1 guard extension

The original cohort results above remain unchanged. The replay benchmark now adds a sixth policy, `sentinel_guarded`, for 1,008 main records and 140 paired comparisons. A separate 1,092-run study on fresh seeds evaluates the level-step guard. See [LEVEL_GUARD.md](LEVEL_GUARD.md) for every scenario mean, the oxygen-delivery tradeoff, stress-map failures and reproduction commands.

## v1.2 conservative comparator study

The six-policy replay benchmark above remains unchanged. A separate 31-candidate study selects conservative baselines on tuning data before evaluation. See [CONSERVATIVE_COMPARISON.md](CONSERVATIVE_COMPARISON.md) for final cohort and stress-map results, the targeted-scenario reversal, scenario weighting, pilot history and remaining limitations.

## v1.3 frozen-policy stress study

The original and conservative studies remain unchanged. [ROBUSTNESS.md](ROBUSTNESS.md) reports 45 new sensing/dynamics cells, including drift/initial-offset blind spots, flow errors and false attribution of real dynamics to level faults. The previous zero-depletion finding does not generalize to this wider grid.

## v1.4 explicit research answer

[REFERENCE_RESULT.md](REFERENCE_RESULT.md) separates the broader reference-package comparison from the predeclared age-based-method test. The latter fails its joint protection/oxygen criterion. An additional descriptive contrast finds lower sample means for simple reference correction versus the fixed reserve under the good simulated channel. Biased, missing and common-mode reference failures remain in the record.
