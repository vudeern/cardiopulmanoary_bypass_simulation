# Finite return-flow credit

The v1.15-dev.3 controller reserves enough blood to slow the pump even if return flow
stops immediately. This protects the reservoir in its development grid, but it
also keeps pump flow very low. The v1.15-dev.4 experiment changes one assumption: allow
some return for a short, explicitly declared interval, then assume none.

## What the controller knows

It uses delivered sensor readings, applied pump commands and the existing
calibration/model observer. It receives neither actual reservoir volume nor
future drainage changes, event schedules or the true pump response time.

The candidate computes a conservative current return estimate by subtracting
the observer's venous-bias upper bound and the fixed flow allowance from measured
return, then clipping at zero. It credits half of that estimate for a fixed
15-, 30- or 60-second horizon. These fractions and times are engineering
assumptions; the simulation does not establish them as universally valid bounds.

## How the reserve works

For a candidate command, hold that command for one control interval, then reduce
it at the maximum permitted rate of 0.15 L/min each second until zero. Propagate
every configured pump-lag hypothesis, including hypotheses rejected by the
calibration fit. Include the pump's remaining response after the command reaches
zero.

Let `R_zero` be maximum cumulative loss with no future return, and `R_constant`
be maximum cumulative loss with the credited return continuing forever. For
credited return `q` in L/min and a horizon `H` in seconds, the finite-credit
reserve is:

\[
R_H=\max\left(0, R_{\mathrm{constant}},
R_{\mathrm{zero}}-\frac{qH}{60}\right).
\]

The implementation rounds `H` down to a whole number of control intervals.
Before that cutoff, loss follows the constant-return trajectory. After the
cutoff, no return is credited, so cumulative loss can only increase until all
residual pump flow is gone. Its final value is total pumped volume minus the
finite return credit. A constant-return peak after the cutoff cannot exceed
that final value. This gives the exact maximum prefix loss for this particular
assumed return envelope and the declared discrete first-order pump model.

The command cap keeps this reserve inside the supported lower reservoir estimate
minus 290 mL. If even maximum permitted braking cannot fit, the controller brakes
and reports infeasibility. It does not override the existing slew limit.

## What remains conditional

- The assumed future return must hold. A sudden stop can violate it.
- Actual pump response must be covered by the configured hypotheses.
- The lower reservoir estimate must be valid. Shared absolute calibration bias
  remains unidentifiable from these measurements.
- A feasible stop must still be available. The controller cannot retroactively
  recover blood already committed to a slow pump's response.

Without independent calibration/model support, the candidate retains v1.15-dev.3's
maximum-braking fallback. Positive return credit cannot enable recovery in that
state. This can sacrifice almost all oxygen delivery when calibration is absent.

## How the experiment judges the change

All three horizons are fixed before outcome runs, on the same 32 development
patients. The experiment adds 6,144 runs: 3,072 primary, 2,304 calibration-failure
and 768 abrupt-stop runs. The extra challenge abruptly sets drainage to zero for
45 seconds, without giving its schedule to the controller.

A candidate qualifies for development selection only if it has zero floor
crossings and zero empty requests in both primary and abrupt-stop grids. Among
qualifying candidates, select the lowest primary oxygen deficit. If none qualify,
report no selected candidate. Secondary calibration failures never select the
winner. Every candidate and failure stays in the logs.

This experiment reuses development data. Both confirmation cohorts remain
untouched, the existing PI comparator remains frozen, and the v1 MPC milestone requires
the full project gates and later independent confirmation. Passing the added
abrupt-stop grid does not turn the finite-return assumption into a safety proof.

The implementation is in `src/perfusion_candidates/finite_return.py`; the fixed
experiment and results are in `results/finite-return-development/`.
