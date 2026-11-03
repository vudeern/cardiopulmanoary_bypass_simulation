# Submission readiness: evidence and remaining gaps

The update produces a **working manuscript for independent review**, not a certification that a journal will accept the work.

Completed: a focused literature audit; a reduced-model derivation with independently checked counterexamples; stronger flow-independent PI/threshold baselines; frozen development selection; new final conditions; paired patient analysis; all adverse results; and a reproducible manuscript.

The PI primary test fails despite a lower oxygen deficit. This is retained as a result, not hidden by changing the criterion. The mathematical contribution is scoped to the reduced model and is not claimed as new general control theory.

Unresolved: independent domain review, a defensible application-level novelty assessment, fit-for-purpose external model validation, final author declarations and venue-specific suitability. Published aggregate ranges are not raw reservoir dynamics and were not presented as such.

The absence of physical validation does not make every idealized simulation paper unpublishable. It limits the claims and raises the burden for a clear theoretical or methodological contribution. That burden cannot be certified by another software test suite or by this assistant alone.

Files: [working manuscript](PAPER_DRAFT.md), [theory](THEORY.md), [literature audit](LITERATURE_AUDIT.md), [machine-readable readiness](../results/submission-study/readiness.json).

## Published-patient oxygen replay update

The v1.6 [patient replay](PATIENT_REPLAY.md) uses five public case-report observations. It checks oxygen arithmetic with actual inputs and explicit unmeasured-saturation assumptions. It supplies no raw reservoir series, fitted patient dynamics, held-out prediction or controller validation; those gaps above remain open. Reproduce and verify with `python examples/published_patient_replay.py --check`.
