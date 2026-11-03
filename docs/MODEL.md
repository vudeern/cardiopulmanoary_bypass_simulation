# Model, observer and controller

All parameters describe a hypothetical adult-like research circuit. None is a
manufacturer specification or a recommended patient setting. The model is
uncalibrated. The equations are implemented in `src/perfusion_lab/`.

## Units and time convention

Simulation time and `dt` are in seconds. Flows are L/min, volumes L, pressure mmHg,
Hb g/dL, saturation a fraction, BSA m² and indexed oxygen delivery mL O₂/min/m².
Multiplying flow by `dt/60` gives a volume transfer. A row's `observation_time` is
the start of the interval; `time` is its end. Delivery uses the interval-average
actual flow. Reservoir and pressure are interval-end values. Scenario inputs are
held over the interval. This difference matters when comparing monitor and truth.

## Conserved patient–reservoir storage

Let total volume be Vₜ, reservoir volume Vᵣ, patient volume Vₚ = Vₜ − Vᵣ, effective
unstressed volume V₀, venous compliance Cᵥ and venous resistance Rᵥ.

```math
P_v = \max(0, (V_p-V_0)/C_v)
```

```math
Q_v = \min(7.5, f_{drain} P_v / R_v)
```

Drainage `f_drain` is a prescribed obstruction multiplier. This is an effective
storage model, not a physiological atrial pressure/cannula collapse model. The
same interval uses start-of-step storage for the venous-return calculation.

The pump state approaches command u with a 2-second time constant:

```math
Q_{k+1}=u+(Q_k-u)e^{-\Delta t/2}
```

Requested mean transfer flow is `(Q_k + Q_{k+1})/2`, a trapezoidal approximation
to this exponential's interval mean. Return volume is limited to available patient
volume. Pump transfer is limited to reservoir volume plus return volume. Patient
and reservoir gain/lose equal quantities, so their total remains Vₜ. When the
requested volume exceeds availability, the exported `empty_request` flag records
the failure; the model does not invent negative blood volume. The actuator state
continues to represent its requested-flow response even when transfer is limited.

This lumped timing permits same-step return to support outflow and does not model
intra-step air entry. There is no bleed, infusion or transfusion channel. The
scripted Hb reduction is separate from this volume conservation and **does not
conserve RBC mass**. It must not be interpreted as a physical dilution intervention.

## Arterial Windkessel

For step-average actual flow Q, arterial resistance Rₐ and compliance Cₐ:

```math
P_{k+1}=Q R_a+(P_k-Q R_a)e^{-\Delta t/(60R_aC_a)}
```

This is the exact held-input solution to `Cₐ dP/dt_min = Q − P/Rₐ`. CVP is omitted.
It provides an approximate pressure penalty, not a validated hemodynamic waveform.

## Oxygen content, delivery and demand

With PaO₂ fixed at 150 mmHg:

```math
C_{aO2}=1.34 Hb S_{aO2}+0.0031 P_{aO2}
```

```math
DO_{2i}=10 Q C_{aO2}/BSA
```

The factor 10 converts L to dL. Hemoglobin and arterial saturation are scripted
scenario inputs. The oxygenator-loss scenario changes saturation only; dissolved
oxygen remains tied to the fixed PaO₂. This is not a consistent oxygen-dissociation
or membrane-gas-transfer model, and no detailed gas-exchange claim is justified.

Temperature rises from 32 to 37 °C over normalized experiment phase 0.35–0.85.
A separate demand proxy is `D(T) = D₃₇ Q₁₀^((T−37)/10)`. Unmet demand is
`max(0, D(T) − 0.60 DO₂i)`. The 60% extraction ceiling is a hypothetical constant;
there is no venous oxygen state, tissue oxygen transport, or physiological debt
repayment. Neither this proxy nor deficit AUC is an AKI prediction.

## Patient sampler

Each run uses NumPy `default_rng(seed)`. The following draws are independent
uniform distributions; they do not model population correlations or prevalence.

| Parameter | Range / fixed value | Unit |
|---|---:|---|
| BSA | U(1.55, 2.15) | m² |
| Initial Hb | U(8.6, 10.2) | g/dL |
| Arterial resistance | U(11, 18) | mmHg min/L |
| Arterial compliance | U(0.0014, 0.0022) | L/mmHg |
| Demand at 37 °C | U(110, 140) | mL/min/m² |
| Q₁₀ | U(2.0, 2.7) | dimensionless |
| Venous compliance | 0.12 | L/mmHg |
| Venous resistance | 0.9 | mmHg min/L |
| Total volume | 5.8 | L |
| Unstressed volume | 4.35 | L |
| Initial reservoir volume | 0.85 | L |
| Initial pump flow | 2.4 × BSA | L/min |
| Initial arterial pressure | initial flow × resistance | mmHg |

The initial storage may be away from the return-flow equilibrium; the startup
transient is included rather than removed. A custom `Patient()` uses fixed values
documented in `model.py`, not the sampler.

## Fault schedule

Let φ = t/duration. Dilution, Hb bias and saturation loss ramp from zero to their
specified magnitude over φ = 0.25–0.40 and then remain. Drainage restriction and
level bias are active for φ = 0.48–0.67. Compound Hb dropout is active for
φ = 0.40–0.57. Fault timing is known to the experiment runner but not controllers.

For a 1200-second run this means a ramp over seconds 300–480, drainage/level fault
over 576–804, and dropout over 480–684. All runs retain the warming schedule.

## Measurement model and information boundary

Sensors draw six independent standard Gaussian samples each step using seed
`patient_seed + 10000`. All strategies draw the same number of samples even during
dropout, preserving common random numbers across the pair.

| Channel | Noise SD | Additional disturbance |
|---|---:|---|
| Pump flow | 0.015 L/min | none |
| Reservoir | 0.003 L | scenario additive bias |
| Arterial pressure | 0.25 mmHg | none |
| Inline Hb | 0.07 g/dL | scenario bias or missing value |
| Arterial saturation | 0.001 | scripted saturation loss |
| Independent lab Hb | 0.10 g/dL | sampled at t = 0, 180, 360, … |

Temperature is assumed available without noise. Flow/reservoir are floored at
zero; saturation is clipped to [0.5, 1]. References are instantaneous independent
samples, not delayed laboratory results. The model assumes no common-mode bias
between lab and inline Hb. A periodic independent reference is essential: with
only an additive Hb sensor, true Hb and bias cannot generally be separated.

The observer knows initial Hb and estimates bias as `inline − lab` when both are
present. It then uses `inline − last_bias`; during dropout it holds its previous
Hb estimate, accepting a lab sample when available. The no-calibration ablation
still accepts an available lab Hb during dropout but never corrects the inline
bias. It therefore removes reference-based inline correction, not all possible
reference information.

The Hb stress width is:

```math
w=0.25+0.002 a_{ref}+\mathbf{1}_{stale}0.004a_{inline}
```

Ages are seconds. Stale means last inline sample is older than 10 seconds.
The estimate is clipped to [2, 20] g/dL; bounds are estimate ± width with those
same limits. These allowances are design choices, not proven limits on Gaussian
noise, dilution speed or bias drift. The injected faults can violate them.
`fault` is set when the last estimated absolute bias exceeds 0.6 g/dL or inline
is stale. It cannot flag an unobserved bias before a reference reveals it.

Venous flow is estimated from measured reservoir change and measured pump flow:
`Qᵥ_raw = Q_meas + 60 ΔVᵣ_meas/Δt`. It is clipped to [0,8] and smoothed by a
0.5/0.5 update. The first estimate is the measured pump flow. A level-bias step
corrupts this estimate, as well as the apparent volume.

No controller receives the changing true Hb, actual obstruction multiplier,
future inputs, true pressure resistance, or true reservoir volume directly.
BSA is a known patient parameter. The observer receives only `Observation`.

## Policies

Every policy commands 0–7 L/min with a slew bound of 0.15 L/min/s. Fixed flow is
2.4 × BSA. Reactive uses `u_next = u_previous + 0.004(target − measured_DO₂i)`,
then applies the common command/slew limits. The gain is per update, so changing
dt changes the closed-loop policy; a dt sweep is not solely a numerical-convergence
experiment for reactive control. Fixed control is used for the convergence check.

Predictive policies evaluate u = 0, 0.1, …, 7.0 L/min. Delivery uses the lower Hb
stress bound and current saturation. Effective arterial resistance is estimated
as measured pressure / max(measured flow, 0.5). Predicted pressure is u × that
resistance; the candidate is screened at 95 mmHg.

The local reservoir forecast is `Vᵣ_pred = Vᵣ_meas + (Qᵥ_est − u) × 20/60`.
Candidates must satisfy `Vᵣ_pred ≥ 0.25 L`, except in `no_lookahead`. This is a
constant-flow endpoint forecast: it does not integrate future changes in venous
return, actuator lag or pressure, nor prove an invariant safe set.

Among feasible candidates the policy minimizes:

```math
J(u)=100[\max(0,D^*-DO_{2i}^{lower}(u))/D^*]^2+0.025u^2+0.1(u-u_{previous})^2
```

When no candidate meets the screens and slew interval, it commands the ramp-limited
minimum feasible-by-actuation flow and marks the step infeasible. The fallback can
still fail the reservoir or pressure threshold. Soft oxygen penalties permit a
small below-target solution even with a feasible oxygen target. This is finite-
candidate receding-horizon screening, not a stochastic robust MPC proof.

## Numerical and inference limits

Use dt ≤ 5 s and a duration divisible by dt. Storage transfers use an explicit
start-of-step drainage estimate, pressure is exact only for held mean inflow,
and the actuator mean is approximated. Numerical tests verify invariants and
refinement under fixed control; they do not establish fidelity to patients.
All five strategies use the same plant, and the predictive model shares some
algebra with that plant, which favors model-matched policies. External model-form
validation, matched control effort, full threshold sensitivity and realistic
reference delays remain future work.


## v1.1 optional level-step guard

Only `sentinel_guarded` changes level processing. The observer checks whether measured ΔV lies within [−Q Δt/60 − 0.03, (7.5 − Q) Δt/60 + 0.03] L. An out-of-envelope increment is assigned to a sensor step, estimated as ΔV − (previous inferred drainage − current measured flow) Δt/60. The accumulated offset is subtracted before drainage estimation. After detection the forecast also subtracts a latched 0.08 L reserve allowance. This detector assumes independent unbiased flow and a 7.5 L/min drainage cap; it cannot generally separate physiological/model errors from sensor faults. Initial bias and slow drift are unidentifiable. See LEVEL_GUARD.md for the full method, tradeoffs and remaining failures.

## v1.2 conservative comparator options

Original `sentinel` optionally accepts a nonnegative `reserve_margin` (L), subtracted from measured reservoir level before the forecast, or a positive `flow_cap_index` (L/min/m²), converted to a patient-size-specific command cap. A newly active cap is approached at the common slew limit. Neither option changes the observer or supplies hidden truth. Defaults preserve existing numerical outputs. These are simple modifications to Sentinel, not reproductions of published controllers. See CONSERVATIVE_COMPARISON.md.

## v1.3 optional stress plant

`StressScenario` creates persistent steps, gradual drift, initial offsets, flow bias and larger noise without giving hidden parameters to the observer. `StressPlant` changes actuator response, optionally adds first-order drainage lag and pressure-dependent venous resistance, or deliberately violates the drainage cap. A separate regime varies venous compliance and resistance. Neutral alternative settings reproduce the original plant exactly; the default path and all 42 original replay metric sets are regression checked. These are illustrative assumption changes, not a calibrated improvement in physiological fidelity. See ROBUSTNESS.md.

## v1.4 optional independent level reference

`LevelReferences` samples hidden physical volume through a separate seeded noisy channel, queues delivery, and models dropout, outages, bias or shared systematic error. `ReferenceLevel` sees only delivered samples and stored raw inline observations. It estimates bias using matching acquisition timestamps; no future level or reference is supplied. The hold mode corrects the current inline reading; its fixed reserve margin is applied by the common controller. The bounded mode subtracts an engineering allowance of 0.04 + 0.003 × acquisition age L, using zero lower level when unknown or older than 180 s. This is not a calibrated confidence bound or a guarantee against depletion. Both methods retain the original drainage observer, which can still be wrong under flow bias or raw level jumps. Default ignored-reference behavior preserves the existing benchmark metrics.

## v1.5 flow-independent simple baselines

The PI/threshold controller classes use corrected level, Hb, saturation and direct pressure, while deliberately ignoring measured flow and inferred drainage. PI has tracking anti-windup; threshold control requests slowdown below its setpoint. Both use the common command range/slew and a direct pressure slowdown above 90 mmHg, distinct from forecast pressure prediction. Invariance to sensor-only flow bias is not a safety proof. The reduced equilibrium analysis has separate idealizing assumptions and is not asserted to exactly describe the full simulator.

## Source-informed comparator workbench

`published_control.py` provides a source-traced nonlinear occluder map and exact discrete third-order reference filter. The experimental `published_adapted` policy is a flow-domain adaptation of measured-venous-flow plus level I-PD feedback. It replaces the source occluder/feedforward/PID inner loop with the existing common pump-flow actuator. Its derivative sign/filtering, anti-windup and development-selected gains are explicit engineering choices, not verified source settings. The reference architecture has a level target; Sentinel has an oxygen/floor objective. The configuration mapping is in `data/controller-reference/reproduction.json`.

`venous_measurement` defaults to disabled. When enabled, its current noisy acquisition replaces only the controller-facing venous-flow belief after the original observer update; original measurements and observer calculations are retained. It cannot receive future drainage or fault truth. The same channel is enabled for both matched comparison arms.

## Verified general PI baseline and shared supervisor

`simc.py` implements the published integrating-process SIMC equations: Kc = 1/[kprime × (tau_c + theta)], tau_I = 4 × (tau_c + theta). The signed outflow-to-level gain is kprime = −1/60; seconds and L/min are converted explicitly. The nominal design neglects half of the two-second actuator time constant and includes half of the fixed one-second design sampling interval, yielding theta = 1.5 s. This is a design approximation, not an identified patient or equipment parameter.

The PI core has error = setpoint − measurement and explicit rectangular integral update. Tracking anti-windup is called after the application applies common oxygen-demand, direct pressure and flow/slew constraints. The forecast arm retains the original predictive controller inside that same application shell. Its internal candidate objective, pressure forecast and reservoir screen are algorithm differences, not extra physical actuator authority.

The published reference is general process control. Only its PI tuning and normalized mathematical example are reproduced. The CPB supervisor and circuit are declared simulation adaptations. No clinical controller, device behavior or source patient experiment is reproduced by this comparison. Source mapping is in `data/simc-reference/source.json`.

## Predictive braking controller

`braking.py` uses the pump-volume balance to bound excess outflow while holding a candidate command for one sample and then braking toward an inflow estimate at the common slew limit. For nonnegative command excess c = max(u − q_in_lower,0), initial positive flow excess d = max(q_upper − q_in_lower,0), response lag bound T and slew r, the reserved volume is `(T*d + dt*c + c*c/(2*r))/60` L. This upper estimate assumes a constant first-order lag <=T and a persistent valid inflow lower estimate. Its numerical test integrates independent braking trajectories.

Current actuator-flow bounds propagate from known initial command and command history using lag endpoints. A five-second past raw-level slope provides a second inflow estimate using the lower actuator bound. Raw level is reconstructed by undoing only the causal reference correction, so a calibration update is not treated as an actual volume change. The lower of the two inflow estimates is used. A slope over past samples is not a guaranteed lower bound on future inflow.

The reference-bias trend sets an engineering drift allowance above an explicit minimum. The controller subtracts base error plus drift allowance times acquisition age from corrected level. With missing/stale information or insufficient braking reserve it requests the fastest permitted slowdown and records infeasibility. It still cannot exceed common command and slew limits, so depletion remains possible. These uncertainty choices are not probability statements.

The v1.8 simulator source used for the previous general-PI protocol is retained in `data/simc-reference/frozen-v1.8/`. Its recorded hash is checked there if the current simulator has changed. Prior replay metrics are independently rerun with the current implementation to check that the interface extension did not alter old behavior.


## Reference-continuity design

The raw mass-balance integral at each decision time is `I[k+1] = I[k] + dt/60 * (measured_qv[k] - (qhat[k]+qhat[k+1])/2)`. The first-order nominal command response propagates `qhat`. Delivered samples `(ta, Va)` anchor `Va + I[t] - I[ta] - bq*(t-ta)/60`; consecutive reference acquisitions estimate `bq = 60 * (I[ta]-I[tprev] - (Va-Vprev)) / (ta-tprev)`, clipped to ±2 L/min. Reference acquisition history is required; future or unmatched samples are rejected. Before anchoring, the corrected inline level is a flagged fallback.

The level used in the stopping constraint subtracts `base_allowance + age_allowance * reference_age` from this estimate. There is no hard age cutoff. A rate-limited reserve still uses the 1–10 s actuator interval and the same common oxygen and pressure constraints. The nominal model used by the estimator is a separately tuned approximation, not a supplied true plant parameter. Past venous bias fits need not remain valid. This replacement trades the old age-triggered slowdown for possible integrated model/sensor error; it is not a safety guarantee. The never-reference and biased-reference tests challenge identifiability directly.

The v1.9 orchestration source is retained at `data/braking-history/frozen-v1.9/simulation.py` to verify its frozen hash while running old replay regressions through current orchestration. The previous controller implementations and numerical outputs are preserved.


## Selective PI upgrade experiment

The foundation is the existing SIMC PI reservoir override and common oxygen-demand/pressure/actuator shell. The predictive estimate uses acquisition-anchored mass balance, a nominal 2 s pump response and consecutive-reference venous-offset fits. The gate requires at least two distinct acquisitions, age below the selected maximum, and absolute disagreement with corrected inline level below a selected allowance. It checks consistency, not identifiability or statistical confidence.

The predictive recommendation is the greatest rate-limited command consistent with the conditional braking calculation. The applied action is `u_PI + weight * (u_predictive - u_PI)`, constrained by the same pump limits. Weight changes by at most `dt / 10 s` per decision. In braking-only mode the recommendation cannot exceed PI; in recovery-only mode it cannot fall below PI. Recovery adds no flow at measured pressure ≥85 mmHg. This extra recovery screen does not alter the PI comparator's common 90 mmHg slowdown.

PI anti-windup and the nominal pump integral both track the final applied command. A zero weight reproduces the PI command at the controller's current state; disabling the override for an entire run reproduces the corresponding PI experiment exactly. Returning to PI after intervention does not imply the physical trajectory becomes identical to a run that never intervened.

The prediction is not a hard constraint on a partly blended action. Its violation is explicitly flagged when the override is active. Fading an override can retain a small contribution after eligibility is lost. Shared measurement bias, stale references and model mismatch can still cause depletion or unnecessary slowing. The previous orchestration source is retained at `data/continuity-history/frozen-v1.10/simulation.py` to validate old frozen hashes while numerical regressions run on current code.


## Reference-integrity experiment

`FaultyReferences` injects faults on the sensing side only. Routine noise uses seed+50000; independent calibration uses seed+110000, distinct from the seed+90000 virtual-patient sampler. Bias labels are joined to decisions only after controller actions for offline classification. The new optional simulation arguments are `reference_fault_options`, `calibration_options` and `reference_guard_options`; default behavior and prior numerical experiments remain unchanged.

`ReferenceGuard` buffers each routine sample for up to 8 seconds after arrival to allow a same-acquisition calibration audit. A pair is compared before the routine value changes the inline correction. Without a pair, acceptance requires consistency with the latest calibration and raw inline history, and, after two calibrations, a mass-balance prediction. The pump model is nominal 2 s; consecutive independent calibrations fit a bounded venous-sensor offset. Rejection quarantines the routine source and restores independent calibration correction. A clean paired audit is required to clear quarantine. A distinct calibration acquisition count prevents duplicates from creating support.

The current corrected inline estimate subtracts `base_uncertainty + drift_allowance * correction_age` to produce an engineering lower estimate. Before any calibration it uses an explicit 0.3 L extra allowance and remains unsupported; this is not an identifiable or guaranteed bound. Both matched controllers use this same observer design. The hybrid requires two calibrations, recent calibration and an unquarantined source before adding flow; otherwise even a fading override cannot exceed its PI recommendation. A partly blended action is not a hard stopping guarantee.

The calibration-only PI uses this observer with no routine samples and a fixed declared uncertainty design, then development-selected PI gains. Screening disabled accepts routine samples despite test failures, with the same channels and guard allowances. This ablation isolates reference acceptance. Corrupting both channels can yield false agreement; noise being independent does not imply faults are independent.

The v1.11 orchestration source remains at `data/selective-history/frozen-v1.11/simulation.py`; old protocol hashes are verified against that source while old numerical replays run through current orchestration.


## Offline slowdown audit

The audit is separate from controller execution. Its taps preserve the original sensor RNG draws and controller outputs in observed mode; the original frozen controller and simulation source hashes are checked. Exact volume and interval removal are explicit diagnostic-only changes before the decision. Local forks copy the identical PI/controller state before the decision and evaluate higher actions through the exact current plant with future disturbances.

The feasible witness chooses from nine commands per interval, checking a 60 s exact-plant emergency slowdown. Once the command reaches zero, residual pump transfer is bounded by `flow * dt/120 * (1+a)/(1-a)`, `a=exp(-dt/tau)`, the infinite geometric sum of this model's trapezoidal flow integration. A continuous `tau*flow/60` expression would underestimate discrete transfer. The remaining pressure is bounded by `max(current_pressure, R*flow)`. Witnesses use a 0.00001 L numerical floor margin. Two fixed heuristics, with and without a true oxygen-demand cap, are retained; the lower-deficit feasible witness is selected. It is not a global optimizer.

The LP variables are command, actuator flow, pressure, relaxed reservoir and oxygen deficit at every interval. Slew and actuator/pressure dynamics are exact linear equations. Venous return is replaced by its state-dependent upper envelope at the reservoir floor, propagated through any declared drainage lag. The relaxed tank has no physiological storage ceiling, only a mathematical finite upper bound from accumulated upper inflow. This optimistic relaxation contains feasible physical paths and therefore bounds their objective from below. Its trajectory is not generally feasible in the full plant.

All constraints require floor 0.25 L, no empty requests, command 0–7 L/min and slew 0.15 L/min/s. Pressure above 95 mmHg is allowed only within the smallest reachable initial transient obtained by maximal immediate deceleration from the mandated initial pump state. Raw high-pressure time is still reported. This allowance is explicit and shared by witness, relaxation and audit-compliance checks; it is not a clinical safety criterion.

The numerical LP check clips inequality/bound dual signs and accounts for stationarity residual using finite variable bounds: add `sum(min(residual*lower_bound, residual*upper_bound))` to the dual objective, then subtract 1e-7. Nonnegativity of deficit supplies a zero lower bound. Primal residuals and the objective gap are retained. This is floating-point numerical verification, not formal interval arithmetic or physiological validation.

For feasible controls, the optimistic LP lower bound ≤ unknown perfect-information physical optimum ≤ full-plant witness. The middle gap is unresolved; the future-informed witness does not upper-bound the best attainable causal sensor-based policy. A locally verified continuation only proves existence for that fork. Its failure does not prove impossibility; successes from different forks need not be jointly realizable.
