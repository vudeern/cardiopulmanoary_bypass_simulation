# Research rationale and prior art

Research checked October 30, 2026. This is a focused engineering literature review, not a systematic review or patent search. No literature or patient dataset was downloaded into the simulator, and no published figure or proprietary algorithm was copied.

## Why LivaNova is relevant

LivaNova's public research page names predictive extracorporeal monitoring, perfusion data/workflow benchmarking and advanced modeling as areas of interest [1]. Its Essenz platform combines a heart-lung machine, patient monitoring and sensing, and already advertises automated sensor checks and warnings [2]. The Patient Monitor describes individualized quality indicators, retrospective views and data export [3]. Together these suggest that transparent monitoring experiments are a relevant engineering direction. They do not establish company interest in this particular implementation, device compatibility, or a clinical gap in an existing product.

The project focuses on cardiopulmonary bypass rather than a generic ECMO simulator. LivaNova announced the wind-down of its Advanced Circulatory Support unit in January 2024, including discontinuation of certain system operations/service by year end, while retaining standalone cannula products [4]. That makes the current cardiopulmonary monitoring direction a better-supported company connection than assuming all historical support platforms remain active.

## Clinical motivation versus what is implemented

Ranucci and colleagues' randomized trial evaluated a goal-directed strategy targeting indexed oxygen delivery of at least 280 mL/min/m² [5]. It found a reduction in AKIN stage 1 injury, while more severe AKI and secondary outcomes did not show significant differences. That supplies context for a threshold-based delivery metric; it does not license translating our simulated exposure reductions into a reduction in kidney injury. Our experiment has no creatinine, renal autoregulation, inflammatory injury, transfusion decisions, or clinical endpoint model. The value 280 is a research comparator, not a universally suitable patient target.

## Existing engineering work

Takahashi and colleagues demonstrated simultaneous control of reservoir level and arterial flow using a control architecture tested with glycerin and bovine-blood perfusates [6]. Automated coordination of these quantities is therefore prior art. Our short-horizon grid policy is a simple test instrument, not an attempt to claim that automated perfusion or reservoir control is new.

Sharabiani and colleagues developed GARIX, a physiology-informed dynamic model of oxygen extraction using high-resolution pediatric bypass observations [7]. That work includes clinical data fitting and dynamical behavior beyond this project's scripted demand proxy. Our adult-like, uncalibrated model is deliberately smaller and does not claim comparable physiological fidelity or validation.

A recent reservoir monitoring study also describes predictive warning based on observed level change [8]. Forecasting depletion is therefore not a first-ever idea. The project combines a simple forecast with a hemoglobin bias/reference experiment so that interactions can be examined in one reproducible benchmark.

## Where this project can contribute

| Prior approach or concept | Established point | This project's bounded contribution |
|---|---|---|
| Goal-directed perfusion trial | Oxygen delivery is a clinically investigated management quantity | Transparent exposure metrics, without an injury prediction |
| Simultaneous reservoir/flow control | Both quantities can be controlled together | A common fault grid comparing simple policies and ablations |
| Physiology-informed oxygenation model | Oxygenation dynamics can be modeled with clinical observations | Inspectable minimal plant with explicit assumptions and no data-fit claim |
| Predictive reservoir monitoring | Level trends can warn of depletion | A stress map of forecast failure when the level sensor itself is biased |
| Independent reference calibration | Bias can become identifiable with additional information | A visible distinction between inline truth, reference-based belief and monitor reassurance |

The proposed research question is: **Under paired synthetic conditions, how do intermittent reference calibration and a reservoir forecast change the tradeoff between concealed delivery deficits and reservoir depletion, and how does that tradeoff fail when the observer's assumptions are violated?**

The reusable artifact is the experiment protocol, implementation, synthetic dataset and failure analysis. Establishing scientific novelty would require a broader search, expert review and an explicitly comparative study. No first-in-field, patentability, device-performance or clinical-benefit claim is made.

## Interpretation guardrails tied to the evidence

The fault magnitudes, Gaussian noise, reference period, patient distributions and controller limits are chosen assumptions. They are not estimates from LivaNova equipment. In particular, a synthetic +2 g/dL Hb fault or +0.4 L level fault must not be presented as a measured product failure. We do not call LivaNova APIs, import clinical exports, or connect to equipment.

Controllers in the benchmark receive identical synthetic patient parameters only where documented (BSA and initial Hb); they do not receive the hidden scenario, future drainage, true changing Hb, or plant resistance. A lower Hb stress bound is not a probabilistic guarantee. Bootstrap intervals characterize variation in an artificial sampler, not treatment effects in people. The maps expose counterexamples to a broad safety claim rather than establishing a clinically valid safety envelope.

## Sources

1. LivaNova. **Investigator-Initiated Research.** [Official research priorities](https://www.livanova.com/en-us/contact-us/investigator-initiated-research).
2. LivaNova. **Essenz Perfusion System.** [Official platform description](https://www.livanova.com/cardiopulmonary/en-us/essenz).
3. LivaNova. **Essenz Patient Monitor.** [Official monitor description](https://www.livanova.com/cardiopulmonary/en-us/essenz/patient-monitor).
4. LivaNova. **LivaNova to Wind Down Advanced Circulatory Support Business Unit.** January 8, 2024. [Official announcement](https://investor.livanova.com/news-releases/news-release-details/livanova-wind-down-advanced-circulatory-support-business-unit).
5. Ranucci M, et al. **Goal-directed perfusion to reduce acute kidney injury: A randomized trial.** J Thorac Cardiovasc Surg. 2018;156:1918–1927.e2. [DOI: 10.1016/j.jtcvs.2018.04.045](https://doi.org/10.1016/j.jtcvs.2018.04.045). [PubMed](https://pubmed.ncbi.nlm.nih.gov/29778331/).
6. Takahashi H, et al. **Simultaneous Control of Venous Reservoir Level and Arterial Flow Rate in Cardiopulmonary Bypass With a Centrifugal Pump.** IEEE J Transl Eng Health Med. 2023;11:435–440. [DOI: 10.1109/JTEHM.2023.3290951](https://doi.org/10.1109/JTEHM.2023.3290951). [PubMed](https://pubmed.ncbi.nlm.nih.gov/37534100/).
7. Sharabiani MTA, et al. **Towards goal-directed perfusion – Part I: Developing physiology-inspired mathematical framework using high-resolution paediatric CPB data.** Perfusion. [DOI: 10.1177/02676591251375788](https://doi.org/10.1177/02676591251375788). [Full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC13490700/). First published online September 10, 2025; later issue assignment is shown by the repository record.
8. **Predictive monitoring of venous reservoir level fluctuations and rapid depletion during CPB via real-time image analysis.** [PubMed record and abstract](https://pubmed.ncbi.nlm.nih.gov/42778174/). Used as evidence of prior predictive warning work; the implementation here is independently written.

## November 2, 2026 follow-up: test whether detection adds value

The v1.2 [conservative comparator study](CONSERVATIVE_COMPARISON.md) challenges the guard against an always-on reserve and a fixed flow cap, with tuning/evaluation separation and complete negative findings. Its pooled improvement does not establish scientific novelty: the reserve wins on the targeted sensor fault itself, scenario weights are artificial, and the plant structure remains shared. The next evidence gap is comparison against stronger conditional baselines under drift, flow-sensor faults and plant mismatch, followed by external measurement validation.
