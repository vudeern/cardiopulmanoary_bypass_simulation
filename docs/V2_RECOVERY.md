# V2 recovery-aware control: first development pilot

V2 begins here, after the complete final [v1.15.0 snapshot](https://github.com/vudeern/cardiopulmanoary_bypass_simulation/releases/tag/v1.15.0). Package version: **2.0.0rc1**, development only. All earlier MPC research and its conditional performance bound belong to v1; historical execution IDs remain preserved in frozen records.

## Goal and implemented change

Detect return-flow interruption from current measurements and restore delivery after return recovers, while retaining the independent reservoir/stopping protection. The new causal phase detector needs two supported calibration anchors, a 20-sample measured-return history and two consecutive threshold crossings. It receives no interruption schedule. All three comparison arms run this detector; only the recovery arm uses its phase to override the requested command toward the currently permitted cap for 30 seconds. The independent cap, slew authority, state estimates and measurements are unchanged.

This first pilot tests whether a recovery-specific request adds anything beyond fast PI. It does not change the protection model or introduce new sensor information.

## Fixed development comparison

Two reused development patients (37000 and 37014), nominal and slow pumps, normal return and a 45-second interruption, three arms: **24 runs**, each 600 seconds at 1-second steps. Interruption runs lose drainage during [168, 213) seconds. The primary recovery analysis window is [213, 273); normal runs use the same sham window. Calibration and independent references are healthy. Event times enter the simulator and analysis only.

| Arm | Interruption recovery-window deficit | Interruption total deficit | Normal total deficit |
| --- | ---: | ---: | ---: |
| Standard PI | 160.9756 | 1496.0416 | 1416.1981 |
| Fast PI | 159.6940 | 1494.7735 | 1414.5171 |
| Recovery-aware fast PI | 159.6940 | 1494.7735 | 1414.5171 |

Deficit AUC units: mL O₂/m². Each mean has four runs from two patients; these are exploratory paired development results, not independent confirmation.

**Added recovery-policy benefit versus matched fast PI: 0.0%.** Commands match fast PI throughout all eight paired trajectories. The recovery override changes no command: fast PI already asks for the flow permitted by the shared cap during detected recovery. Fast PI lowers recovery-window deficit by about 0.80% relative to standard PI; that is a gain-setting comparison, not a benefit attributable to the new policy.

The detector identifies both interruption and recovery with 1-second latency in each of the four recovery-arm interruption cases. It reports no false interruptions in the eight recovery-arm cases, including the four normal controls. Detection is an implemented capability, not evidence of improved oxygen delivery or dependable fault diagnosis under broader sensor conditions.

All 24 runs have zero observed reservoir-floor crossings, empty requests and command-cap violations. Independent replay validation also checks the 0.15 L/min/s slew limit. These finite simulated observations do not establish general protection. Historical calibration-corruption and depletion failures remain in the v1 reports.

## Evidence and reproduction

- [Frozen protocol and source hashes](../results/v2-recovery-pilot/protocol.json)
- [Summary](../results/v2-recovery-pilot/summary.json), [all run metrics](../results/v2-recovery-pilot/runs.json), and [checksums](../results/v2-recovery-pilot/checksums.json)
- Twenty-four full 600-step CSV traces in `results/v2-recovery-pilot/`
- [Controller and causal detector](../src/perfusion_research/recovery_v2.py)

```bash
python -m pip install -e ".[audit,horizon]"
python examples/recovery_v2_study.py
python examples/validate_recovery_v2.py
python -m unittest discover -s tests -v
```

The validator recomputes full-run/recovery AUCs, cap and slew compliance, group summaries and source/trace hashes, then reruns a matched slow-pump interruption pair. Source hashes preserve the tested design. Both reserved confirmation cohorts remain untouched.

## Next design question

Request-only recovery logic has no benefit on this tested grid. Before expanding it, investigate the state-dependent protection bottleneck: can an independently justified, causal return-confidence model permit faster recovery without increasing exposure when return fails again? Retain the present cap as a reference, test short repeated interruptions and noisy/bias-corrupted return measurements, and compare any changed protection design against identically informed fast PI. A larger command or a relaxed boundary alone is not an improvement.

The original full-run ≥10% evidence policy remains unmet. Recovery-window success would be a separate result; neither this development version nor causal detection satisfies stable v2 qualification. No hardware or clinical validation is claimed.
