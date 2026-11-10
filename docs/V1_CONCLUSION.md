# V1 conclusion: the tested MPC missed 10%; a fixed-ceiling limit is provable

All research through this conclusion is classified as v1. The previous public
v2.0-rc.1 through rc.5 labels are reclassified as v1.15 development milestones.
Their original execution identifiers remain inside frozen protocols and source
hash records so historical studies reproduce without rewriting their evidence.
The complete final snapshot is v1.15.0; v2 begins with recovery-aware control.

## What is established

The applied 48-run pilot reduces mean deficit by 0.1435% versus matched PI and
is about 0.0418% worse than the existing hybrid. It does not meet the 10% target.
That result rejects a superiority claim for this tested nominal MPC candidate;
it does not prove that every possible MPC design fails.

For a narrower class, there is a mathematical bound. Hold each of the 16 PI
replays' command-ceiling streams fixed. For the first-order pump,

    Q[k+1] = alpha*Q[k] + (1-alpha)*u[k],   0 < alpha < 1,

the sequence u[k]=cap[k] upper-bounds requested flow for every controller with
u[k]<=cap[k]. This follows by induction because both coefficients are positive.
Oxygen content is exogenous and positive in this simulator, so larger requested
flow cannot increase deficit. Ignoring depletion clipping, pressure and slew
restrictions makes this cap-command sequence an optimistic relaxation of the
physical problem. Its deficit lower-bounds the deficit of every admissible
controller under that SAME fixed stream, regardless of algorithm.

Across those cases, PI mean deficit is about 1455.984; the optimistic lower bound
is about 1455.747. The maximum possible improvement within that fixed-ceiling
class is only **0.0163%**, so **10% is ruled out for that class and those cases**.
The calculation includes conservative numerical allowances and is reproduced by
`python examples/fixed_ceiling_bound.py`.

## What is not established

The ceilings in the actual protection algorithm depend on reservoir state,
estimated parameters and prior commands. A different controller can change
future ceilings. The applied MPC result already exceeds the fixed-PI-stream
0.0163% limit because it follows a different cap stream. This is fully consistent
with the bound and demonstrates why it cannot establish universal impossibility.

**There is no proof here that MPC in general cannot achieve 10%.** Publishing
that claim would overstate the evidence. V1 closes with a failed tested target,
an explicit conditional bound, and retained positive and negative findings.

## V2 goal: recovery-aware delivery

V2 will detect drainage interruption and recovery using current measured venous
flow, reduce delivery under the existing protection cap, and recover delivery
promptly when return recovers. The first candidate will change the requested
command, never the independent floor or stopping reserve. Matched PI and the new
controller receive identical measurements, estimates and actuator authority.

The first development experiment measures deficit specifically during a declared
post-interruption recovery window, total-run deficit, recovery time, false alarms,
floor exposure and empty requests. Interruption timing is known only to the
experiment analysis; the controller does not receive future events. Abrupt-stop
and sensor-fault outcomes remain visible. A recovery-specific benefit alone does
not satisfy the original full-run 10% release milestone. That milestone remains
unmet unless separately demonstrated on the required confirmation cohorts.

No clinical, hardware or general protection certification is claimed by either
version number.
