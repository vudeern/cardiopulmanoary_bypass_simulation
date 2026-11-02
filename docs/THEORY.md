# A mechanism-level analysis of flow bias and reservoir forecasting

This is a reduced-model argument and an implementation invariance result. Neither is a full-system safety proof, and neither is claimed to be a first result in control theory.

## 1. What level and measured flow cannot identify by themselves

Let V be reservoir volume in L; q_v and q_a be true inflow/outflow in L/min; and b be additive flow-measurement bias in L/min. Assume

$$\dot V=(q_v-q_a)/60,\qquad y_q=q_a+b.$$

If inflow is unmeasured and unconstrained and no trusted actuator calibration supplies q_a, then, for any admissible constant δ, the alternative system

$$q'_v=q_v+\delta,\quad q'_a=q_a+\delta,\quad b'=b-\delta$$

has the same measured flow and volume derivative. Its initial V can also be identical. Therefore those two channels alone cannot uniquely identify absolute flow bias. A perfect independent level measurement supplies V; it does not remove this ambiguity about the two absolute flows. Additional known inflow or a sufficiently trusted actuator model can break the construction. This is an algebraic identifiability statement under the stated information assumptions, not a claim about all devices or all estimators.

## 2. Bias transmission through a derivative-based inflow estimate

In the noiseless, time-aligned idealization, an observer that estimates inflow using measured outflow and reservoir slope obtains

$$\widehat q_v=y_q+60\dot V=q_v+b.$$

Suppose the measured/corrected level retains a constant offset c, the controller subtracts margin m, and the local forecast horizon is H seconds. Its forecast floor constraint is

$$V+c-m+(\widehat q_v-u)H/60\ge V_{\min}.$$

Assume the constraint is active, q_v and b are constant, actual outflow equals commanded u without delay, and command/pressure/oxygen limits are inactive. Solving the active constraint gives

$$u=q_v+b+60(V+c-m-V_{\min})/H.$$

Substitution into conservation yields

$$\dot V=-\frac{V-[V_{\min}+m-c-Hb/60]}{H}.$$

Thus the stable equilibrium is

$$\boxed{V^*=V_{\min}+m-c-Hb/60.}$$

Protection of the floor at that equilibrium requires m ≥ c + Hb/60. A correct level reference removes c but does not remove the flow-bias term. For example, with V_min = 0.25 L, H = 20 s, m = 0.20 L, c = 0 and b = 0.90 L/min, the ideal equilibrium is 0.15 L, below the experimental floor despite correct level measurement.

The forward-Euler recurrence has factor 1 − Δt/H and is stable when 0 < Δt/H < 2. Independent scalar calculations check 160 combinations against the closed-form equilibrium. Cases predicting negative volume are outside the physical domain; they describe an infeasible request, not negative blood volume in the actual simulator.

### Limits of the mechanism claim

The full simulator uses filtered and delayed step-average measurements, actuator lag, flow/volume clipping, other constraints and time-varying faults. Its exact trajectories need not follow this equilibrium. The expression identifies a structural failure route; it does not fit or validate the full plant, guarantee a quantitative error bound for that plant, or establish clinical relevance.

## 3. A bias-invariant comparison class

The added level PI and threshold baselines compute commands from corrected level, Hb, saturation, direct pressure, controller state and time. They do not read measured flow or inferred drainage. In this simulator, changing only additive flow-sensor bias leaves all those inputs and random draws unchanged at the initial time. Equal commands then imply equal physical next states; the same reasoning repeats by induction. Physical trajectories and true oxygen delivery are consequently invariant to that sensor-only perturbation. Monitor-derived scores can still change.

This invariance does not imply good control or safety. A controller can be invariant and perform poorly. Level/reference bias, pressure errors, unknown actuator behavior and drainage disturbances can still defeat it. Its value here is as a strong baseline that separates flow-channel dependence from added reference information.

## Reproduction

Run `python examples/mechanism_audit.py` and `python -m unittest discover -s tests -v`.

- [Scalar checks](../results/mechanism-audit/equilibria.csv)
- [Indistinguishable-system examples and range-audit summary](../results/mechanism-audit/summary.json)
- [Feedback baseline implementation](../src/perfusion_lab/feedback.py)

