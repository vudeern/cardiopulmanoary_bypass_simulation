# Focused literature and evidence audit

Checked November 2, 2026. This is a focused search, not a systematic review, patent search, or proof of scientific priority. Search coverage and access were incomplete. The purpose is to prevent claims contradicted by accessible prior work.

## Search trail

Queries included: “Simultaneous Control of Venous Reservoir Level” supplementary/data; “cardiopulmonary bypass reservoir level benchmark dataset open source control simulation experimental validation”; “venous reservoir sensor bias control model”; “reservoir flow sensor bias model predictive control mass balance”; and “cardiopulmonary bypass benchmark fault control”. Both available search engines were used. Primary journal/PubMed records were preferred. Some PMC direct views returned access challenges; searchable text and primary records supplied the facts listed below.

| Primary source | What it establishes | Consequence for this project |
|---|---|---|
| Takahashi et al., 2023, DOI 10.1109/JTEHM.2023.3290951 | Reservoir/flow control with physical perfusate experiments already exists. | We cannot claim to invent simultaneous control. Our generic PI comparator is not a reproduction of its occluder hardware/controller. |
| Shinohara et al., 2026, DOI 10.1177/02676591261489051 | Camera-derived level trends were used for predictive warnings. | Predicting reservoir depletion is not itself new. Our threshold baseline is generic, not a replica of that alarm system. |
| Montano et al., 1996, DOI 10.1177/026765919601100404 | Continuous cardiotomy-reservoir measurement with a load cell was studied. | An additional level measurement is established prior art; our simulated reference is not demonstrated hardware. |
| Searles et al., 2021, DOI 10.1182/ject-53-263 | A CPB simulator was checked against reported operating ranges. | Those ranges can inform a plausibility check, not validate our reservoir time response. |
| Irfan et al., 2026, DOI 10.1038/s41598-026-42361-x | Fault-tolerant level control exists in industrial pump/tank systems. | Neither general fault tolerance nor PI control is a new contribution here. |

Primary links: [Takahashi](https://pubmed.ncbi.nlm.nih.gov/37534100/), [Shinohara](https://pubmed.ncbi.nlm.nih.gov/42778174/), [Montano](https://pubmed.ncbi.nlm.nih.gov/8884860/), [Searles](https://pmc.ncbi.nlm.nih.gov/articles/PMC8717731/), [Irfan](https://www.nature.com/articles/s41598-026-42361-x).

## What external data were actually used?

Only published aggregate operating-limit summaries were used in the numerical range check. We did not obtain a raw experimental reservoir trajectory with matching geometry, pump commands, inflow, level, timing and calibration sufficient to fit and then independently validate this plant. Supplementary-material and repository leads do not establish that such a dataset is available; a paper's metadata entry is not raw data.

The range check compares nominal model outputs with survey-derived mean pressure limits of 54 and 82 mmHg and a reported flow-index mean of 2.34 ± 0.35 L/min/m². These are reported operating summaries, not confidence bounds for a patient population. Model parameters were not fitted to force agreement. See [the numerical audit](../results/mechanism-audit/summary.json).

No hemolysis, renal injury, patient outcome, device-equivalence or real-world safety validation was completed. The FDA pump/nozzle hemolysis dataset encountered during searching addresses a different model/output and was not treated as validation of reservoir control.

## Candidate contribution and unresolved priority

The defensible candidate is an open, auditable failure benchmark linking a reduced-model bias mechanism to controller comparisons under equal information. The algebra and flow-independent PI/threshold design are not claimed to be novel control theory. Whether the application-level benchmark and analysis add enough knowledge for a specific journal requires independent subject-matter review and a broader related-work assessment.

## Readiness boundary

The manuscript is a review draft. Numerical verification, open code and a stronger comparison improve its assessability; they cannot establish journal acceptance or replace independent model validation. External reservoir data/bench validation, expert review of assumptions and equations, confirmation of the claimed literature gap, and author approval of all declarations remain unresolved.
