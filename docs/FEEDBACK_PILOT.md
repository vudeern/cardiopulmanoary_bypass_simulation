# First applied horizon-feedback comparison

The horizon optimizer now controls the simulated pump. This pilot answers whether
the existing nominal planner improves delivery once its commands are actually
applied behind the shared protection layer. It is no longer an offline snapshot
study. The default rc.5 controller and historical experiment sources stay frozen.

## Result

| Arm | Runs | Mean oxygen-deficit AUC | Floor cases | Empty cases | Lowest reservoir |
| --- | ---: | ---: | ---: | ---: | ---: |
| Matched PI using guard point volume | 16 | 1455.984 | 0 | 0 | 552.420 mL |
| Horizon MPC using the same point volume | 16 | 1453.894 | 0 | 0 | 552.420 mL |
| Existing rc.5 hybrid reference | 16 | 1453.288 | 0 | 0 | 552.441 mL |

**MPC reduces deficit by 0.1435% versus matched PI, not the required 10%.** It is
about 0.0418% worse than the existing rc.5 hybrid reference. This implementation
does not demonstrate useful controller superiority. There are zero observed
floor crossings, empty requests, high-pressure seconds or shared-cap violations
in these 48 runs; that is a scoped observation, not a general protection proof.

MPC actions are actually applied on **7,459 of 9,600 candidate control steps**.
On 42 steps the chosen action differs by more than 1e-6 L/min from the protected
PI action computed at that same MPC trajectory state. That counterfactual action
count is distinct from comparing two independently evolving trajectories.
All four patient-level average deficit differences favor MPC over the matched PI,
but the effect is tiny and the cohort is reused development data.

## What changed

`perfusion_research.feedback.FeedbackRuntime` provides an opt-in simulation
runtime. Both nominal PI and MPC receive the same calibration-guard point volume,
Hb estimate, sensors and previous applied commands. Both use the same independent
lower-volume estimate for the current rc.5 protection calculation. The experiment
does not give MPC true reservoir volume, true pump lag, true patient resistance
or compliance, or future event timing.

At each eligible one-second tick MPC solves the existing 15-second nominal
oxygen-deficit LP with its normal-slew braking continuation. A second LP chooses
the largest first command while preserving the best primary objective within
1e-8 AUC. This makes the applied first action deterministic among equivalent
future plans without adding a squared-deficit or effort penalty.

The first command is bounded inside the LP and clamped again by the same current
calibration/model reserve cap, pressure slowdown, oxygen cap, 0–7 L/min limits
and 0.15 L/min/s normal slew used by PI. Cap parity against the frozen controller
is tested separately. No emergency command authority or safety-floor relaxation
is introduced. The existing protection still depends on its declared calibration,
retained-model and finite-return assumptions.

PI uses tau_c=0.2 s and a 0.25 L nominal reservoir setpoint. It is one declared
comparison setting, not an exhaustive retuning or newly certified strongest PI.
The rc.5 reference retains its original lower-volume input and hybrid policy;
it is an additional before/after reference, not the matched estimator isolation.

## Fallback and failure outcomes

The runtime computes the protected point-estimate PI action every tick. Invalid,
late, infeasible or otherwise rejected optimization uses that action. The same
tracking anti-windup records whichever command was actually applied. Tests cover
unsupported calibration, rejection/timeout fallback, shared-cap parity and final
clamping. Fallback preserves the existing policy and its limitations; it cannot
guarantee recovery from an already unrecoverable state or invalid model envelope.

| Candidate outcome | Steps |
| --- | ---: |
| Accepted MPC action applied | 7,459 |
| Unsupported calibration or infeasible current reserve: protected PI | 2,120 |
| Invalid nominal prediction input: protected PI | 19 |
| Secondary solve or plan validation rejected: protected PI | 2 |

Invalid prediction inputs include negative noisy pressure readings. Those are
rejected rather than silently presented as accurate physical state estimates.
All statuses and 600-step applied trajectories are public. The mean recorded
optimizer duration across all candidate ticks is about 9.72 ms, including zero
entries on ticks without an optimizer call. Timing is descriptive of this local
Python/SciPy environment. The one-second diagnostic rejection timer and Python
execution do not establish hard real-time behavior or the illustrative 2 ms goal.

## Experiment scope and next decision

This is a fixed 48-run development pilot: four reused patients (37000, 37007,
37014, 37031), clean/combined physiology, nominal/slow pumps, and three arms.
Each run lasts 600 seconds at dt=1 second. Routine references and independent
calibration are healthy. Combined physiology retains the established inline/flow
faults and drainage disturbance. These are not confirmation patients or the full
primary sensing/failure grid. Settings were frozen before the pilot; all outcomes
are retained and no successful arm is selected after inspecting failures.

**Do not expand this exact nominal MPC into a large tuning sweep.** Actual
feedback confirms that it offers little improvement under the existing shared
protection. Meaningful further gains need a concrete improvement in state/return
information usable by both controllers, or a separately justified physical
actuator/protection change. The four-patient result cannot establish that all MPC
architectures fail; it rejects a large-benefit claim for this tested candidate.

Stable v2.0 remains unqualified. The 10% target, protection criteria and two
untouched confirmation cohorts are unchanged. No hardware or clinical validation
is claimed. Development code and positive and negative findings are published.

## Run the applied controller

```bash
python -m pip install -e ".[audit,horizon]"
python examples/feedback_study.py
python examples/validate_feedback.py
```

The planner uses the locally available HiGHS backend. OSQP is not substituted
mid-experiment. The original plant, measurement acquisition timing, observer and
acknowledgement boundary are reused through an explicit runtime adapter. All
source hashes, settings, per-run metrics, paired patient differences, full applied
traces and checksums are in `results/feedback-pilot/`. The validator independently
checks trace metrics, cap/slew limits, aggregates and a full PI/MPC replay pair.
