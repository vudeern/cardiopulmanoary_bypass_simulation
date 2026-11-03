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
```

Physics tests check mass conservation, actuator response, pressure decay, oxygen units and numerical refinement. Sensor/observer tests check causal timing, missing measurements, bias correction and explicit uncertainty assumptions. The frozen original replay cases detect changes to existing numerical behavior.

Source-component tests compare the occluder map with a separately written direct equation and verify its inverse. The third-order reference filter is checked against its analytic step response at multiple timesteps. These are mathematical implementation checks, not validation of a particular device or patient.

The controller-comparison validator checks the complete grid, candidate budgets, seed split, frozen selection, grouped metrics, truth-based metric recomputation and fresh reruns of debug traces. It also requires explicit unresolved exact-reproduction flags. An adapted controller must not pass as a reproduced author implementation.

The DOM contract executes exported traces and application code in a minimal mock DOM. It checks selection, timeline, finite chart geometry and controls; it does not certify browser layout. Artifact checks verify local links, SVG XML, metric units and pairing.

The patient replay check recomputes arithmetic artifacts from the cited numerical inputs. It does not test held-out patient prediction. No raw external reservoir series or original reference-controller experimental traces have been obtained. Exact source-controller replication, independent model validation and equipment relevance remain open.

Do not regenerate paper drafts or result write-ups during development. Those documents and their generators have been removed at the project owner's request.
