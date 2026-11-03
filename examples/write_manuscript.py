"""Assemble a review draft from verified results; never certify publication."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
s=json.loads((ROOT/'results/submission-study/summary.json').read_text())
p=json.loads((ROOT/'results/submission-study/protocol.json').read_text())
audit=json.loads((ROOT/'results/mechanism-audit/summary.json').read_text())
good=s['group_means']['good'];pi=good['pi'];forecast=good['forecast']
verdict=s['verdict'];passed=verdict['demonstrated']
primary={c['metric']:c for c in s['comparisons'] if c['group']=='good' and c['variant']=='pi'}
def estimate(metric):
    c=primary[metric];return f"{c['mean']:.2f} [{c['low']:.2f}, {c['high']:.2f}]"
title='Flow-measurement bias in reservoir forecasts: an analytic mechanism and reproducible reference-assisted control benchmark'
text=f'''# {title}

**Working manuscript for independent review. Not submitted or peer reviewed.** Prepared for Udeern Varanasi. Author details, funding/competing-interest declarations and final author approval remain to be completed. Scientific priority and suitability for a particular venue have not been established.

## Abstract

**Objective.** Determine how additive flow-measurement bias can defeat a reservoir forecast despite level-reference correction, and assess whether stronger flow-independent feedback baselines improve the protection–oxygen-delivery tradeoff in an open simulation benchmark.

**Methods.** We derive a reduced active-constraint equilibrium and an indistinguishable-system construction, verify the equilibrium independently in 160 scalar cases, and add level PI and threshold baselines that ignore measured flow. All controllers receive the same timestamped level-reference information. Twenty-two candidate configurations are compared on 2,464 development runs, with one per family frozen before 4,032 final runs with new seeds, fault magnitudes, timing and dynamics. The primary comparison uses 16 paired virtual patients with good references; patient-block bootstrap intervals preserve within-patient correlation. Published aggregate operating ranges support a limited plausibility audit, not external time-series validation.

**Results.** In the reduced model, equilibrium volume is V* = V_min + m − c − Hb/60, where m is reserve margin, c residual level offset, H forecast horizon and b flow bias. Correcting c does not remove b. Independent scalar errors are below {audit['maximum_error_L']:.2g} L. The PI and threshold baselines have exact physical-output invariance to sensor-only flow-bias changes in this implementation. In the final good-reference group, PI deficit AUC was {pi['deficit_auc']:.2f} versus {forecast['deficit_auc']:.2f} mL O₂/m² for forecast, but low-reservoir exposure was {pi['low_reservoir_s']:.2f} versus {forecast['low_reservoir_s']:.2f} s. The primary joint criterion was {'met' if passed else 'not met'}.

**Conclusion.** A level reference alone does not repair a flow-biased drainage forecast. Stronger simple baselines change the comparison, but no universal controller benefit or clinical safety follows. The contribution offered for review is a transparent mechanism-and-benchmark analysis; the PI/threshold algorithms and algebra are not claimed as new control theory. Physical validation and independent assessment of the application-level literature gap remain necessary for broader claims.

## 1. Introduction

Reservoir depletion and adequate oxygen delivery impose competing demands on pump control. Automatic reservoir/flow regulation has already been demonstrated experimentally [1], and predictive level warnings are established [2]. Independent reservoir measurement also predates this project [3]. Consequently, neither automatic control, an additional level reference, nor PI control is an original contribution by itself. Related industrial tank work also addresses sensor fault tolerance [5].

This study focuses on a narrower failure route: an inflow estimate formed by adding measured outflow to a reservoir derivative inherits additive flow bias. Improving the level measurement can therefore leave a dangerous forecast error intact. We connect that mechanism to a reproducible numerical benchmark and stronger simple comparators. The candidate application-level contribution is the auditable combination of explicit information assumptions, counterexamples and equal-information tests; its novelty remains provisional pending a broader review.

The study asks two questions. First, what can level and flow channels identify without an independent inflow or trusted actuator anchor? Second, does a level PI baseline lower oxygen deficit relative to a tuned forecast while maintaining comparable reservoir and pressure exposure? Failed comparisons and adverse cases are retained.

## 2. Reduced-model analysis

Let V be volume in L, q_v and q_a inflow/outflow in L/min, and y_q = q_a + b the measured flow. Conservation is V̇ = (q_v − q_a)/60. With unmeasured unconstrained inflow and no trusted calibrated actuator model, replacing (q_v, q_a, b) with (q_v + δ, q_a + δ, b − δ) preserves both y_q and V̇. Accurate volume measurement alone does not distinguish the systems. This information statement does not apply when a trusted additional channel removes the ambiguity.

For a noiseless time-aligned derivative estimate, q̂_v = y_q + 60V̇ = q_v + b. If the level retains offset c and the controller subtracts margin m, its H-second forecast is V + c − m + (q̂_v − u)H/60. With that floor constraint active, ideal instantaneous actuation and other limits inactive, solving for command u and substituting into conservation gives

$$\\dot V=-\\frac{{V-[V_{{\\min}}+m-c-Hb/60]}}{{H}},\\qquad
V^*=V_{{\\min}}+m-c-Hb/60.$$

Thus equilibrium floor protection requires m ≥ c + Hb/60 under these assumptions. At H = 20 s, m = 0.20 L, c = 0 and b = 0.90 L/min, V* = 0.15 L, below the experimental 0.25 L floor. A forward-Euler update is stable for 0 < Δt/H < 2. The full proof, assumptions and numerical checks are in [THEORY.md](THEORY.md).

The full plant contains actuator lag, filtering, clipping, other constraints, noise and time-varying faults. Its exact trajectories are not asserted to follow the reduced equilibrium. Negative mathematical equilibria identify requests outside the physical domain; the simulator never permits negative reservoir volume.

## 3. Simulation and comparison methods

### 3.1 Plant and information

The existing plant conserves transfer between a venous reservoir and one compliant patient-storage compartment, with an arterial Windkessel and a first-order pump command response. Oxygen content links Hb, saturation and flow to indexed delivery. Parameter values and disturbance magnitudes are engineering choices, not fitted clinical distributions. The 280 mL/min/m² delivery target and 0.25 L floor are experimental comparators, not patient-specific recommendations. The model does not predict organ injury.

Every method receives the same measurement channels, Hb-reference process, independent level-reference schedule and paired random noise/dropout. Delivered level references are matched to stored inline readings at acquisition time. The common reference correction holds the resulting level-bias estimate; it supplies no true flow or drainage. The final reference regimes are good, delayed, dropout and biased. The good channel has a 60-second period, 4-second delay and independent noise SD 0.01 L; its hardware feasibility is not established by this simulation.

### 3.2 Controllers

The forecast controller retains the original finite-candidate oxygen/flow cost and a 20-second drainage forecast. It estimates effective arterial resistance using measured pressure divided by measured flow. Candidate reserve margins range from 0 to 0.50 L.

The PI baseline caps oxygen-demand flow by level PI feedback, with tracking anti-windup. The threshold baseline slows toward zero below a level threshold and otherwise follows oxygen-demand flow. Both ignore measured flow and inferred drainage. They use direct pressure slowdown at 90 mmHg; forecast instead screens predicted pressure against 95 mmHg. This is a documented design difference, not an exact reconstruction of a published hardware controller. All share the 0–7 L/min command range, 0.15 L/min/s slew limit and measurement channels; all are scored for actual pressure above 95 mmHg.

Because flow bias changes only a sensor channel that PI/threshold do not consume, their physical trajectories remain identical under a sensor-only bias perturbation, by induction on equal controller/plant states and paired random draws. This does not prove good performance or protection against level/reference faults. Monitor-derived scores can still change. The property is tested in unit-level trajectories and 384 final paired counterfactuals.

### 3.3 Development, freezing and evaluation

Development includes seven sensing cases, two plants, eight seeds (11000–11007) and 22 configurations: six forecast margins, twelve PI gain/target combinations and four thresholds. Within each family, the lowest deficit candidate meeting mean low-reservoir and empty-request budgets of 1 second is selected. If none qualifies, the least-exposure candidate is retained and labelled unmatched. These budgets are engineering selection rules. Selection is saved and hashed before evaluation. Candidate grids are finite; the selected forecast margin and PI target lie at grid boundaries, so no global optimality is asserted.

Final evaluation uses seeds 12000–12015, seven sensing conditions, three plant settings, four reference regimes and three frozen methods: 4,032 runs. Total new runs are 6,496. Final level offsets are 0.60 L, positive flow bias 1.10 L/min, noise scaling 14×, restriction fraction 0.35, and altered event timing. Pump/lag/nonlinearity settings also differ from development. These are held-out parameter conditions within known fault families, not an independent physiological dataset.

The primary good-reference comparison requires PI-minus-forecast upper 95% paired intervals ≤1 s for reservoir/empty-request exposure and ≤5 s for high-pressure exposure, with a deficit-AUC upper interval below zero. Tolerances are not clinical noninferiority margins. Other comparisons are descriptive. The plan was internally recorded before evaluation, not independently preregistered.

### 3.4 Statistics and verification

Scenarios have equal artificial weights. Metrics are first averaged across cells within each patient seed; 2,000 paired percentile bootstrap resamples of 16 patient blocks use random seed 2026. Correlated cells are not treated as independent patients. Raw runs, protocols, selections and scripts are retained, including earlier exploratory studies that are not pooled into this evaluation. The analysis verifies all 60 grouped paired intervals and independently reruns all 12 prespecified final replay trajectories.

## 4. Results

### 4.1 Primary good-reference outcomes

| Method | Low reservoir (s) | Empty requests (s) | Deficit AUC (mL O₂/m²) | Pressure exposure (s) |
|---|---:|---:|---:|---:|
'''
for method in s['methods']:
    m=good[method['id']]
    text+=f"| {method['label']} | {m['low_reservoir_s']:.2f} | {m['empty_request_s']:.2f} | {m['deficit_auc']:.2f} | {m['high_pressure_s']:.2f} |\n"
text+=f'''
PI-minus-forecast differences, with 95% paired intervals, were {estimate('low_reservoir_s')} s for reservoir exposure, {estimate('empty_request_s')} s for empty requests, {estimate('deficit_auc')} mL O₂/m² for deficit, and {estimate('high_pressure_s')} s for pressure exposure. The primary joint result is **{verdict['answer']}**. Lower deficit does not compensate for a failed protection criterion under the declared test.

![Reduced-model mechanism and final primary tradeoff](submission-mechanism.svg)

### 4.2 Reference reliability

| Reference | Forecast low / deficit | PI low / deficit | Threshold low / deficit |
|---|---|---|---|
'''
for group in p['references']:
    m=s['group_means'][group]
    text+='| '+group+' | '+' | '.join(f"{m[vid]['low_reservoir_s']:.2f} / {m[vid]['deficit_auc']:.2f}" for vid in ('forecast','pi','threshold'))+' |\n'
text+=f'''
Units are seconds / mL O₂/m². All 84 final cells remain in the machine-readable summary. Delayed, missing or biased references change the tradeoff; no method is labelled universally superior.

![All reference regimes and three outcomes](submission-outcomes.svg)

### 4.3 Verification and published-range audit

All 160 independent scalar calculations match the closed-form equilibrium within 1e-9 L. The flow-independent baselines retain identical true outcomes in all 384 final sensor-only counterfactual pairs. These are mathematical/software checks, not external experimental validation.

An audit of 200 nominal fixed-flow model draws found a pressure range of {audit['nominal_sample']['pressure_min']:.2f}–{audit['nominal_sample']['pressure_max']:.2f} mmHg; {audit['nominal_sample']['fraction_in_mean_limit_band']:.0%} fell between survey-derived mean operating limits reported in [4]. This is not an accuracy or safety rate. No raw reservoir bench time series was used to calibrate or validate the plant. The range comparison neither establishes dynamic fidelity nor justifies crisis-management claims.

## 5. Discussion

The reduced mechanism explains why improving level information can leave flow-dependent forecasting errors intact. It also motivates a necessary comparison: a controller that does not consume the unreliable flow channel. PI and threshold control are established methods; their role here is to challenge the benchmark rather than provide a new algorithm. The stronger comparison changes the oxygen/protection balance but does not satisfy the declared joint PI criterion in this study.

The invariance result is intentionally limited. Ignoring a channel eliminates direct dependence on its bias, but supplies no guarantee against bad level references, different actuator dynamics or inadequate inflow. Likewise, a small scalar numerical error is verification of an ideal calculation, not validation of the underlying physiology. Negative or null method comparisons can still be informative when conditions, failures and scope are explicit.

The main remaining uncertainties are the uncalibrated plant, artificial fault magnitudes and scenario weights, finite candidate grids, simple pressure handling, modest number of paired virtual patients and incomplete external evidence. The scoped literature audit does not prove scientific priority. A broader review may find equivalent mechanism analyses or benchmarks. Physical validation and expert review are required before representing the work as practically relevant to equipment or patients.

## 6. Conclusion

In the stated reduced model, residual level error and flow bias transmit additively into forecast-floor error through c + Hb/60. Independent level correction alone does not remove the flow term. Flow-independent simple baselines provide a stronger comparison class, yet the tested PI method does not demonstrate the declared joint protection/oxygen advantage. The work supplies a reproducible, mechanism-grounded failure benchmark for review, without claiming a validated medical controller, first-in-field method or guaranteed publication.

## Data, code and reproducibility

- [Recorded protocol](../results/submission-study/protocol.json), [frozen selection](../results/submission-study/selection.json), [all new runs](../results/submission-study/metrics.csv), [all cells and paired intervals](../results/submission-study/summary.json).
- [Scalar/range audit](../results/mechanism-audit/summary.json), [full derivation](THEORY.md), [literature/evidence audit](LITERATURE_AUDIT.md).
- Run `python examples/mechanism_audit.py`, `python examples/submission_study.py`, `python examples/plot_submission_study.py`, `python examples/validate_submission_study.py` and the repository tests. Use `python examples/write_manuscript.py` to regenerate this draft after outputs exist.

## Ethics, assistance and author declarations

The controller benchmark uses synthetic data; no new human/animal experiments or medical-equipment control were performed. A separate [published-patient oxygen replay](PATIENT_REPLAY.md) uses five numerical observations from a public case report (Hunter et al., 2013; PMID 24303600). It does not fit patient dynamics, measure reservoir response or validate the controller conclusions. No ethics-waiver determination is claimed. ChatGPT/Codex assisted software, study-script and manuscript drafting; an independently recorded exact model version is unavailable. The human author must verify the equations, implementation, analysis, citations and declarations before submission. Funding, competing interests and final author/affiliation details remain for author confirmation. No external domain review or author submission approval has been recorded.

## References

1. Takahashi H, et al. Simultaneous Control of Venous Reservoir Level and Arterial Flow Rate in Cardiopulmonary Bypass With a Centrifugal Pump. IEEE J Transl Eng Health Med. 2023;11:435–440. [doi:10.1109/JTEHM.2023.3290951](https://doi.org/10.1109/JTEHM.2023.3290951).
2. Shinohara T, et al. Predictive monitoring of venous reservoir level fluctuations and rapid depletion during CPB via real-time image analysis. Perfusion. 2026. [doi:10.1177/02676591261489051](https://doi.org/10.1177/02676591261489051).
3. Montano SR, Morris RW, Pybus DA. The use of a load cell for continuous cardiotomy reservoir level measurement during cardiopulmonary bypass. Perfusion. 1996;11:319–325. [doi:10.1177/026765919601100404](https://doi.org/10.1177/026765919601100404).
4. Searles BE, Darling EM, Riley JB. Objective Content Validation of the Hemodynamic and Technical Parameters of the Orpheus Cardiopulmonary Bypass Simulator. J Extra Corpor Technol. 2021;53:263–269. [doi:10.1182/ject-53-263](https://doi.org/10.1182/ject-53-263).
5. Irfan M, et al. Design of a fault-tolerant control system for a centrifugal pump-based level control system for sensor faults. Scientific Reports. 2026;16:14189. [doi:10.1038/s41598-026-42361-x](https://doi.org/10.1038/s41598-026-42361-x).
'''
(ROOT/'docs/PAPER_DRAFT.md').write_text(text)
readiness=dict(status='review_draft_not_certified_publishable',version='1.5.0',
    completed=['Focused prior-art/evidence audit','Reduced-model derivation and 160 independent scalar checks',
        'Stronger reference-aware PI/threshold baselines and 384 exact flow-bias-invariant pairs',
        'Frozen development selection and 4032 final runs with 16 paired virtual patients',
        'Primary joint criterion reported without changing it after failure','Working manuscript and reproducible analysis'],
    unresolved=['Independent expert review of equations, model, code and application relevance',
        'Scientific-priority/novelty assessment beyond the focused search',
        'Raw reservoir bench/time-series or other fit-for-purpose independent model validation',
        'Venue-specific scope, reporting and author declarations'],
    external_validation_completed=False,submission_made=False,publication_acceptance_established=False)
(ROOT/'results/submission-study/readiness.json').write_text(json.dumps(readiness,indent=2)+'\n')
(ROOT/'docs/SUBMISSION_READINESS.md').write_text('''# Submission readiness: evidence and remaining gaps

The update produces a **working manuscript for independent review**, not a certification that a journal will accept the work.

Completed: a focused literature audit; a reduced-model derivation with independently checked counterexamples; stronger flow-independent PI/threshold baselines; frozen development selection; new final conditions; paired patient analysis; all adverse results; and a reproducible manuscript.

The PI primary test fails despite a lower oxygen deficit. This is retained as a result, not hidden by changing the criterion. The mathematical contribution is scoped to the reduced model and is not claimed as new general control theory.

Unresolved: independent domain review, a defensible application-level novelty assessment, fit-for-purpose external model validation, final author declarations and venue-specific suitability. Published aggregate ranges are not raw reservoir dynamics and were not presented as such.

The absence of physical validation does not make every idealized simulation paper unpublishable. It limits the claims and raises the burden for a clear theoretical or methodological contribution. That burden cannot be certified by another software test suite or by this assistant alone.

Files: [working manuscript](PAPER_DRAFT.md), [theory](THEORY.md), [literature audit](LITERATURE_AUDIT.md), [machine-readable readiness](../results/submission-study/readiness.json).
''')
patient_note='''\n## Published-patient oxygen replay update\n\nThe v1.6 [patient replay](PATIENT_REPLAY.md) uses five public case-report observations. It checks oxygen arithmetic with actual inputs and explicit unmeasured-saturation assumptions. It supplies no raw reservoir series, fitted patient dynamics, held-out prediction or controller validation; those gaps above remain open. Reproduce and verify with `python examples/published_patient_replay.py --check`.\n'''
path=ROOT/'docs/SUBMISSION_READINESS.md'
path.write_text(path.read_text()+patient_note)
header='<section class="failure-section" id="manuscript" aria-labelledby="manuscript-heading">'
html=header+f'''<p class="eyebrow">08 / MECHANISM AND MANUSCRIPT</p><h2 id="manuscript-heading">Explain the failure. Test stronger baselines.</h2>
<p>The review draft now connects an analytic bias mechanism with 6,496 new runs and reference-aware PI/threshold comparisons. In a reduced active-constraint model, equilibrium is V* = V_min + margin − level offset − horizon × flow bias / 60. Correct level alone does not remove a biased-flow forecast error.</p>
<img src="submission-mechanism.svg" alt="Reduced-model equilibrium versus flow bias and the final protection/oxygen tradeoff for tuned forecast, PI and threshold controllers.">
<div class="table-scroll" tabindex="0" role="region" aria-label="Stronger-baseline primary results"><table><caption>Primary good-reference comparison · 16 paired virtual patients · mean outcomes</caption><thead><tr><th scope="col">Method</th><th scope="col">Low reservoir (s)</th><th scope="col">Empty requests (s)</th><th scope="col">Deficit AUC</th><th scope="col">High pressure (s)</th></tr></thead><tbody>'''
for method in s['methods']:
    m=good[method['id']]
    html+=f'<tr><th scope="row">{method["label"]}</th><td>{m["low_reservoir_s"]:.2f}</td><td>{m["empty_request_s"]:.2f}</td><td>{m["deficit_auc"]:.2f}</td><td>{m["high_pressure_s"]:.2f}</td></tr>'
html+=f'''</tbody></table></div><p><strong>Primary result: {verdict['answer'].replace('_',' ')}.</strong> PI lowers oxygen deficit and pressure exposure but adds reservoir exposure. The declared joint criterion is retained. Exact flow-bias invariance in the added baselines is a construction/property check, not a safety guarantee.</p>
<img src="submission-outcomes.svg" alt="Every stronger-baseline reference regime, with reservoir, oxygen and pressure exposure kept separate.">
<p><strong>Evidence status:</strong> 160 independent scalar checks, 384 sensor-only invariant pairs and a published-range plausibility audit are complete. Raw external reservoir dynamics, independent expert review and scientific-priority assessment remain unresolved. The manuscript is an unsubmitted review draft; publication readiness is not certified.</p>
<div class="links"><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/docs/PAPER_DRAFT.md">Read the working manuscript ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/docs/THEORY.md">Derivation and assumptions ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/docs/LITERATURE_AUDIT.md">Prior art and external-evidence audit ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/docs/SUBMISSION_READINESS.md">Readiness and remaining gaps ↗</a></div><small>Choose “Stronger baselines” above for four prespecified cases. Deficit AUC units: mL O₂/m². All conditions are synthetic engineering challenges.</small></section>'''
path=ROOT/'web/index.html';page=path.read_text()
if header in page:
    start=page.index(header);end=page.index('</section>',start)+len('</section>')
    page=page[:start]+html+page[end:]
else:page=page.replace('<section class="methods">',html+'<section class="methods">',1)
path.write_text(page.replace('08 / THE METHOD','09 / THE METHOD'))
print('Generated manuscript, explicit readiness boundary and portfolio section.')
