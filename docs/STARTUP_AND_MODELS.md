# Startup support and pump-model braking

The v1.15-dev.5 experiment separates two reasons a controller may slow the pump:

1. It has not yet received enough independent calibration information.
2. Even with support, its lower volume estimate cannot cover its assumed stopping loss.

Those are different conditions. An earlier support flag does not create extra
blood or remove uncertainty about venous-sensor bias.

## One independent anchor

The first calibration sample is acquired at time zero and delivered at 6 s.
The next arrives at 126 s. The previous observer waits for two anchors before
enabling model support.

The new observer can initialize its feasible volume/bias set from one delivered
anchor. It retains the same calibration-error allowance, all configured pump
hypotheses and the full ±2 L/min venous-bias prior. It propagates that wide set
until later anchors constrain the bias. With missing, stale or conflicting
support, the existing braking fallback remains.

The engineering assumptions have not become more accurate merely because support
is enabled earlier. The independent test checks that a known trajectory within
the declared assumptions remains inside the single-anchor interval, and that
later anchors reproduce the previous sets for an identical measurement/command
history. This is not a confidence-coverage or clinical-safety proof.

## Calibration-consistent stopping hypotheses

The previous protection rule reserves against every configured pump response,
including hypotheses the calibration/model observer has rejected. The follow-up
uses the surviving hypotheses for the existing finite-return reserve.

This can reduce braking conservatism, but it adds a dependency: the calibration
and model-error assumptions must retain a response that adequately covers the
actual pump. If those assumptions discard the real response, reserve can fail.
Shared absolute calibration bias remains unidentifiable. No true pump lag or
future event schedule enters the controller.

The lower volume estimate remains the minimum across the feasible model sets.
The reserve remains the maximum stopping loss across the chosen hypotheses.
There is no new sensor, changed actuator limit or extra future-return credit.
The existing half-return credit lasts 15 seconds, then assumes zero forever.

## Four paired mechanism arms

| Arm | Independent anchors required | Braking hypotheses |
| --- | ---: | --- |
| v1.15-dev.4 reference | 2 | Entire configured grid |
| Early support only | 1 | Entire configured grid |
| Calibrated pump only | 2 | Calibration-consistent set |
| Both changes | 1 | Calibration-consistent set |

The first two arms form a fixed 2,048-run startup comparison. The other two form
an explicitly adaptive 2,048-run follow-up after inspecting development outcomes
and two illustrative model-retention replays. Both stages reuse the same 32
development patients. They are not independent experiments or confirmation cohorts.

Across both stages there are 2,048 primary, 1,536 calibration-failure and 512
abrupt-stop runs. The same 45-second abrupt drainage stop is retained. Selection
requires zero reservoir-floor crossings and zero empty requests in both primary
and abrupt-stop grids, then lowest primary deficit among eligible arms. The v1.15-dev.4
reference can win; calibration-failure results never choose the winner.

The 512 archived eligible-PI primary records provide the unchanged project-gate
comparison and are not counted as new simulations. An equally informed comparator
still needs review before a design is frozen. Both confirmation cohorts remain
untouched, and hardware adaptation remains future work.

Sources: `src/perfusion_candidates/startup.py`,
`src/perfusion_candidates/calibrated_pump.py`, and the two protocols under
`results/startup-development/` and `results/calibrated-pump-development/`.
