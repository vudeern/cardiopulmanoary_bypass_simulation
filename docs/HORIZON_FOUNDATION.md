# Horizon foundation and delivery-limit audit

This milestone adds an offline nominal optimizer and instruments the unchanged
rc.5 controller. It does not apply optimizer commands, replace the observer,
change actuator authority or qualify stable v2.0. Stable v1 remains v1.14.0;
the controller package remains 2.0.0rc5. Both confirmation cohorts are untouched.

## What limits delivery in these development runs?

The audit executes 384 measured-controller runs: 32 reused development patients,
two physiology profiles, two pump responses, and three controller settings.
Routine references and calibration are healthy. The combined physiology still
contains the established inline/flow faults and drainage disturbance. This is a
limited sensing regime, not the complete release qualification grid.

| Controller | Runs | Mean oxygen-deficit AUC | Floor cases | Empty cases | Deficit during reserve-limited intervals |
| --- | ---: | ---: | ---: | ---: | ---: |
| rc.5 selected hybrid | 128 | 1456.624 | 0 | 0 | 90.50% |
| Illustrative PI, tau_c=5 s / level=0.35 L | 128 | 1461.379 | 0 | 0 | 87.07% |
| Illustrative PI, tau_c=0.2 s / level=0.25 L | 128 | 1456.578 | 0 | 0 | 91.71% |

The fast PI differs from rc.5 by only about 0.003% in mean deficit. These two PI
settings are illustrative and do not establish the strongest eligible comparator.
No new 10% target is qualified from this grid.

The instrumentation repeats the existing stopping-cap calculation and assigns
one limiting label per interval in this priority: unsupported calibration,
pressure slowdown, binding stopping reserve, oxygen cap, upward slew, downward
slew, then controller choice. Four uninstrumented replays reproduce every applied
command exactly and every metric within 1e-9. The wrapper changes no decision.

For rc.5, 90.50% of deficit occurs during intervals labelled stopping-reserve
limited, 8.20% during upward-slew intervals, and 1.24% during controller-choice
intervals. This is a temporal association under a declared label priority, not
causal attribution. It does not mean removing the reserve would safely recover
90.50% of delivery. Better planning could alter earlier states, but these results
show why changing PI gains alone has little room to help under this protection.

## The nominal optimization

`perfusion_research.horizon.formulate` builds a linear program with separate
volume, physical pump flow, pressure, command and nonnegative oxygen-deficit
variables. Pump lag and the simulator's trapezoidal interval-average flow retain
the seconds-to-minutes conversion. Pressure follows the existing nominal
Windkessel update. The objective is the linear oxygen-deficit integral; no squared
deficit, arbitrary flow penalty or regularizer changes that primary objective.

The optimizer includes normal 0.15 L/min/s command slew, the first change from
the previous command, command bounds, volume floor and ceiling, and pressure
bounds. After the 15-second delivery horizon, it appends enough nonincreasing,
normal-slew braking commands to reach zero while assuming zero return. The final
volume must cover the exact discrete zero-command tail. Terminal volume ceiling
and terminal floor reserve are separate inequalities. No emergency command
authority is introduced.

This is nominal recoverability along a supplied forecast and backup, not a robust
invariant set. Return forecasts are held constant during the delivery horizon;
real return depends on volume and can change abruptly. Unknown initial state,
lag, resistance, compliance, sensor bias, latency and disturbances still require
independent protection before runtime integration. The terminal construction
alone does not establish recovery after an unforeseen earlier disturbance.

`HorizonSolver()` uses SciPy/HiGHS as the independent LP reference. The optional
`ScaledOSQPSolver` in `horizon_osqp.py` uses positive diagonal variable and row
scaling and positive objective normalization, preserving the feasible set and
optimal primary objective. OSQP retains its workspace and warm starts for the
same sparsity pattern. All returned answers are transformed back and independently
checked against the original physical equations and constraints at 1e-6 tolerance.

The original unscaled OSQP path in `horizon.py` is retained as a frozen diagnostic
reference: it reached 100,000 iterations on a test fixture. Use the scaled adapter
for OSQP experiments. Read-only CI diagnostics established that scaling resolves
that fixture without relaxing the original physical checks. CI compares the
scaled adapter against HiGHS on two inflow fixtures and checks workspace reuse;
this is not a claim of reliable convergence over the entire patient grid.

Infeasible, late, exceptional or invalid answers return `command=None`. That is
deliberate refusal to issue an action, not a validated safe fallback. This offline
component contains no watchdog, equipment interface or protected control runtime.

## Snapshot results and timing

There are 1,024 offline plans: four observation times on each of 128 rc.5 runs,
each with two causal return forecasts. They use the current guard's volume point
estimate, a generic two-second pump model propagated from known applied commands,
measured pressure, and current measured Hb/saturation information. True patient
lag, resistance, compliance, future Hb and future events are never supplied.
The nominal pressure model uses fixed R=14 and C=0.0018.

| Return forecast held for 15 s | Plans | Accepted | Rejected | Median solve + validation | p99 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current measured return | 512 | 444 | 68 | 5.52 ms | 8.46 ms |
| Current protective return credit | 512 | 444 | 68 | 5.34 ms | 8.46 ms |

The 68 rejections in each arm are invalid physical initial inputs, including
negative noisy pressure readings near zero. They are retained rather than
silently clamped. All 888 accepted plans pass independent rollout and constraints;
the largest rollout discrepancy is below 9.51e-8 in the checked state units.

The timing summaries include zero-valued entries for invalid-input records where no solve was attempted. Every accepted reference solve exceeds the illustrative 2 ms target. These timings
include solver setup/solve and independent plan validation, exclude formulation,
observation and scheduling, and describe the recorded Python 3.12/SciPy 1.17
development environment. They are not hardware worst-case execution times or
OSQP timing results. A 1-second diagnostic rejection deadline is used; Python
deadline checking cannot establish hard real-time behavior.

No optimizer plan is applied to the plant. Therefore these snapshots establish
neither an MPC oxygen-deficit gain nor protection performance under feedback.

## Next experiments

1. Separate physical stopping-volume cost from calibration/model uncertainty
   using the same action authority and measurements. Do not weaken the floor.
2. Validate an independently anchored point estimator and pressure treatment on
   fresh noise, bias, outlier and outage profiles within development seeds.
   Keep the existing independent protection envelope; covariance alone cannot
   justify reducing reserve.
3. Compare causal return predictors while giving PI and MPC identical estimates.
   Add robust prefix recoverability and runtime-owned backup handling before
   applying horizon commands.
4. Retune PI over the complete development matrix, then test the unchanged 10%
   and protection gates. Freeze only after development passes; confirmation is
   still two untouched cohorts of 32 patients each.

## Reproduce

```bash
python -m pip install -e ".[audit,horizon]"
python examples/horizon_study.py
python examples/validate_horizon.py
python -m unittest discover -s tests -v
```

OSQP is optional and was unavailable in the local runtime; the recorded 1,024
plans use HiGHS. The OSQP tests execute in GitHub CI on Python 3.10 and 3.12.
The frozen audit source, source hashes, command hashes, every case and accepted
plan vector, rejection reasons, aggregates and checksums are public in
`results/horizon-foundation/`. The separate scaled adapter does not rewrite the
original execution source or results. No clinical or hardware validation is claimed.
