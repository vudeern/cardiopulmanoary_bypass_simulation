# Engineering checks

Run from the repository root after installing the package:

```bash
python -m unittest discover -s tests
node tests/web_contract.cjs
python examples/validate_artifacts.py
python examples/validate_level_guard.py
python examples/validate_conservative_study.py
python examples/validate_robustness_study.py
python examples/validate_reference_study.py
python examples/validate_submission_study.py
python examples/published_patient_replay.py --check
python examples/validate_controller_comparison.py
python examples/verify_simc.py --check
python examples/validate_simc_benchmark.py
python examples/validate_simc_tight.py
python examples/build_simc_web.py --check
python examples/validate_braking_study.py
python examples/build_braking_web.py --check
python examples/validate_continuity_study.py
python examples/build_continuity_web.py --check
python examples/continuity_reference_check.py --check
python examples/diagnose_continuity.py --check
```

Physics tests check mass conservation, actuator response, pressure decay, oxygen units and numerical refinement. Sensor/observer tests check causal timing, missing measurements, bias correction and explicit uncertainty assumptions. The frozen original replay cases detect changes to existing numerical behavior.

Source-component tests compare the occluder map with a separately written direct equation and verify its inverse. The third-order reference filter is checked against its analytic step response at multiple timesteps. These are mathematical implementation checks, not validation of a particular device or patient.

The controller-comparison validator checks the complete grid, candidate budgets, seed split, frozen selection, grouped metrics, truth-based metric recomputation and fresh reruns of debug traces. It also requires explicit unresolved exact-reproduction flags. An adapted controller must not pass as a reproduced author implementation.

The DOM contract executes exported traces and application code in a minimal mock DOM. It checks selection, timeline, finite chart geometry and controls; it does not certify browser layout. Artifact checks verify local links, SVG XML, metric units and pairing.

The patient replay check recomputes arithmetic artifacts from the cited numerical inputs. It does not test held-out patient prediction. No raw external reservoir series or original reference-controller experimental traces have been obtained. Exact source-controller replication, independent model validation and equipment relevance remain open.

Do not regenerate paper drafts or result write-ups during development. Those documents and their generators have been removed at the project owner's request.

The verified general-reference check reproduces the published PI gains and five normalized frequency-domain values within declared rounding tolerances. An independent analytic time-domain solution tests the PI implementation at multiple timesteps. Signed-gain, anti-windup, common-constraint and unused-sensor invariance tests cover application details.

The new benchmark validator independently checks all candidate budgets, seed partitions, selection, final cells and patient-block intervals, and recomputes the joint criterion. It reruns every stored replay and timestep-sensitivity case and checks source/configuration hashes. It does not certify physiological validity, optimal tuning or scientific novelty.

Braking tests check the reserve's units and independent numerical upper estimate, command-history actuator intervals, reference-bias trend handling, missing information, common actuator limits and independence from unused arterial-flow measurements. The study validator independently checks both retained development pilots, archived source hashes, final selection and source freeze, every final cell, paired intervals, the criterion and all stored replays. None of these checks supplies a clinical safety proof.


Continuity tests check delayed acquisition-time anchoring, venous-offset identification against an independently advanced matched plant, long-outage integration, inline-drift independence after anchoring, flagged absence of any anchor, causal reference validation, common constraints and unused arterial-flow invariance. Matched-model arithmetic is not a bound on mismatch; the frozen study tests mismatched plants and unidentifiable references explicitly. Its audit independently rebuilds selection, every cell, paired intervals, both co-primary criteria and every displayed replay. Half-step runs are numerical-refinement smoke checks, not convergence validation or a retuning gate.

The post-evaluation mechanism audit aligns estimates with step-start physical truth in four selected cells. It is labelled diagnostic, does not alter selection or success criteria, and retains signed/absolute estimate error and venous-offset error per virtual patient.
