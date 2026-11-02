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

Only `sentinel_guarded` changes level processing. The observer checks whether measured ΔV lies within [−Q Δt/60 − 0.03, (7.5 − Q) Δt/60 + 0.03] L. An out-of-envelope increment is assigned to a sensor step, estimated as ΔV − (previous inferred drainage − current measured flow) Δt/60. The accumulated offset is subtracted before drainage estimation. After detection the forecast also subtracts a latched 0.08 L reserve allowance. This detector assumes independent unbiased flow and a 7.5 L/min drainage cap; it cannot generally separate physiological/model errors from sensor faults. Initial bias and slow drift are unidentifiable. See [LEVEL_GUARD.md](LEVEL_GUARD.md) for the full method, tradeoffs and remaining failures.

## v1.2 conservative comparator options

Original `sentinel` optionally accepts a nonnegative `reserve_margin` (L), subtracted from measured reservoir level before the forecast, or a positive `flow_cap_index` (L/min/m²), converted to a patient-size-specific command cap. A newly active cap is approached at the common slew limit. Neither option changes the observer or supplies hidden truth. Defaults preserve existing numerical outputs. These are simple modifications to Sentinel, not reproductions of published controllers. See [CONSERVATIVE_COMPARISON.md](CONSERVATIVE_COMPARISON.md).

## v1.3 optional stress plant

`StressScenario` creates persistent steps, gradual drift, initial offsets, flow bias and larger noise without giving hidden parameters to the observer. `StressPlant` changes actuator response, optionally adds first-order drainage lag and pressure-dependent venous resistance, or deliberately violates the drainage cap. A separate regime varies venous compliance and resistance. Neutral alternative settings reproduce the original plant exactly; the default path and all 42 original replay metric sets are regression checked. These are illustrative assumption changes, not a calibrated improvement in physiological fidelity. See [ROBUSTNESS.md](ROBUSTNESS.md).
