"""Generate a failure-first report and portfolio section from stress outputs."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/robustness'
p=json.loads((OUT/'protocol.json').read_text())
s=json.loads((OUT/'summary.json').read_text())
names=dict(original='Original Sentinel',guarded='Guarded Sentinel',
           **{'reserve_0.40':'Reserve +0.40 L','cap_2.4':'Flow cap 2.4 L/min/m²'})
drift=s['cell_means']['drift__reference']['guarded']
initial=s['cell_means']['initial__reference']['guarded']
cap=s['cell_means']['clean__cap_violation']['guarded']
guard=s['pooled_means']['guarded'];reserve=s['pooled_means']['reserve_0.40']
lines=['# Frozen-policy robustness study — v1.3.0','',
'## Main finding: the earlier zero-depletion result does not generalize','',
'The v1.2 guard and conservative settings are frozen. We test nine sensing conditions against five '
'plant regimes, using 24 unused paired seeds (8000–8023): **45 cells and 4,320 runs**. No tuning, '
'selection or threshold changes occur in this study. All cells remain in the results.','',
f"On the reference plant, gradual drift gives **{drift['low_reservoir_s']:.2f} s** mean reservoir "
f"exposure and an initial offset gives **{initial['low_reservoir_s']:.2f} s**; neither produces a "
'level alarm in these runs. In the clean-sensor, altered-drainage-cap cell, every guarded run '
'raises a level flag despite no injected sensor fault. An alarm therefore does not establish '
'correct fault identification.','',
'This is a synthetic falsification of general protection beyond the earlier challenge set. '
'It is not external validation, a calibrated model of a patient, or evidence of a device malfunction.','',
'## Frozen policies and provenance','',
'- Original Sentinel and Guarded Sentinel remain unchanged.',
'- The +0.40 L reserve and 2.4 L/min/m² cap are exactly the settings selected in v1.2. '
'They are not retuned to the new grid.',
'- The protocol records the SHA-256 of the source settings, and the study checks those bytes '
'again after all runs. The source selection and all prior studies remain available.',
'- Six replay cells and seed 8000 are declared before simulation: clean/reference, drift/reference, '
'initial/reference, high flow bias/reference, step/slow pump, and clean/drainage-cap violation. '
'The remaining cells remain inspectable in the tables, maps and CSV.',
'- Every simulation lasts 1,200 seconds at 2-second steps. Paired policies share patient parameters, '
'fault timing and random observation noise. Bootstrap resampling uses the 24 paired patient seeds; '
'pooled cells are averaged within patient before resampling.','',
'## Sensor challenges','',
'All cases include scripted 1.8 g/dL dilution and a drainage restriction to 45%. '
'“Clean” means no injected sensor fault, not absence of a physiological disturbance. '
'The restriction starts uniformly between 25% and 50% of the run and lasts 15%–25% of its duration; '
'the same timing is used for paired policies. Biases persist after onset and are not removed.','',
'| Sensing condition | Declared engineering perturbation |',
'|---|---|',
'| clean | Original sensor noise; no added bias |',
'| step | +0.40 L level step at event onset |',
'| drift | Level rises gradually to +0.40 L over 300 s |',
'| initial | +0.40 L level offset present from the first observation |',
'| small_step | +0.10 L level step |',
'| flow_high | +0.75 L/min flow measurement bias; no level bias |',
'| flow_low | −0.75 L/min flow measurement bias; no level bias |',
'| drift_flow | Gradual +0.40 L level drift plus +0.75 L/min flow bias |',
'| noisy | Tenfold level/flow noise SD: 0.03 L and 0.15 L/min; no added bias |','',
'## Plant regimes','',
'| Regime | Change unknown to the controller |',
'|---|---|',
'| reference | Existing v1.2 plant and patient sampler |',
'| slow_pump | Pump time constant 8 s rather than 2 s |',
'| lagged_nonlinear | Drainage response time constant 12 s; resistance scales as 1 + 0.04 × filling pressure |',
'| cap_violation | Maximum drainage 9 L/min rather than the detector’s assumed 7.5 L/min |',
'| varied_storage | Venous compliance sampled in [0.09, 0.15] L/mmHg and resistance in [0.7, 1.1] mmHg·min/L |','',
'The alternative plant preserves volume accounting and uses the same explicit units, while changing '
'the pump response or drainage law. Neutral alternative settings reproduce the original numerical '
'plant exactly. These variants are deliberately chosen engineering stress assumptions; they are '
'not independent experimental models or evidence of higher physiological fidelity.','',
'## Pooled outcomes: protection still has an oxygen cost','',
'Equal weight is given to each of the 45 artificial cells. These weights do not represent '
'clinical frequencies. Deficit AUC is mL O₂/m²; reservoir exposure is seconds.','',
'| Strategy | Low reservoir (s) | Empty requests (s) | Deficit AUC |',
'|---|---:|---:|---:|']
for vid,m in s['pooled_means'].items():
    lines.append(f"| {names[vid]} | {m['low_reservoir_s']:.2f} | {m['empty_request_s']:.2f} | {m['deficit_auc']:.2f} |")
lines += ['',
f"The fixed reserve has lower mean reservoir exposure (**{reserve['low_reservoir_s']:.2f} s** "
f"versus **{guard['low_reservoir_s']:.2f} s**) but greater oxygen deficit "
f"(**{reserve['deficit_auc']:.2f}** versus **{guard['deficit_auc']:.2f}**). "
'This evaluation is not risk-matched, and neither outcome should be presented alone as a win.','']
for metric,unit in [('low_reservoir_s','s'),('deficit_auc','mL O₂/m²')]:
    c=next(c for c in s['comparisons'] if c['scenario']=='pooled' and
           c['variant']=='reserve_0.40' and c['metric']==metric)
    lines.append(f"Reserve − guarded, {metric}: {c['mean']:.2f} {unit}; "
                 f"95% paired percentile bootstrap interval [{c['low']:.2f}, {c['high']:.2f}] "
                 f"{unit}. These intervals describe the synthetic sampler only.")
lines += ['', '![Every stress cell for every policy](robustness-exposure.svg)','',
'![Guard versus reserve: both outcomes](robustness-tradeoffs.svg)','',
'## Sensing-condition means across all five plant regimes','',
'| Sensing condition | Guarded low (s) | Reserve low (s) | Guarded deficit | Reserve deficit | Guarded runs with a level flag |',
'|---|---:|---:|---:|---:|---:|']
for sensor,policies in s['sensor_means'].items():
    a,b=policies['guarded'],policies['reserve_0.40']
    lines.append(f"| {sensor} | {a['low_reservoir_s']:.2f} | {b['low_reservoir_s']:.2f} | "
                 f"{a['deficit_auc']:.2f} | {b['deficit_auc']:.2f} | {a['level_alarm_ever']:.1%} |")
lines += ['',
'## Alarm ambiguity and blind spots','',
'![Any level flag by cell](robustness-alarms.svg)','',
'The flag records a discontinuity hypothesis and remains latched. Its frequency is not a '
'sensitivity/specificity estimate: flow faults or unexpected physics can trigger a level flag, '
'and a flag in a case with level bias does not establish an accurate bias estimate. '
'In clean, flow_high, flow_low and noisy cases no level fault is injected. Flags in those rows '
'are false attribution to the level channel under the test construction.','',
'A startup offset has no trusted baseline anchor in the present observer. Slow drift can remain '
'inside the increment envelope. A flow measurement bias corrupts both inferred drainage and the '
'fault envelope. Changing real drainage beyond the declared cap breaks the model assumption. '
'None of these can be fixed merely by treating the existing flag as a confirmed diagnosis.','',
'## Complete cell outcomes','',
'Each cell below has 24 paired virtual patients. Values are mean reservoir exposure in seconds; '
'all oxygen, pressure, pump demand and alarm metrics remain in the machine-readable summary and CSV.','',
'| Cell | Original | Guarded | Reserve | Flow cap |',
'|---|---:|---:|---:|---:|']
for cell,policies in s['cell_means'].items():
    lines.append('| '+cell+' | '+' | '.join(f"{policies[v['id']]['low_reservoir_s']:.2f}"
                                           for v in p['variants'])+' |')
lines += ['',
'## Next design requirement','',
'The next candidate must address measurement credibility: for example, a separate noisy reference '
'channel or explicitly bounded uncertainty that can declare the level unidentifiable. Any extra '
'information must be given fairly to comparators and tested with reference error, delay and dropout. '
'Adding a reference is not itself a novelty claim. Reusing this stress grid to design a new observer '
'would turn it into development data; a later evaluation must use new held-out conditions and seeds. '
'Stronger conditional baselines, physiology calibration, physical bench measurements and user demand '
'remain unresolved. No publication readiness or commercial readiness is established here.','',
'## Reproduce and inspect','',
'```bash','python -m pip install -e ".[plots]"',
'python -m unittest discover -s tests -v',
'python examples/robustness_study.py',
'python examples/plot_robustness_study.py',
'python examples/report_robustness_study.py',
'python examples/validate_robustness_study.py',
'node tests/web_contract.cjs','```','',
'[Recorded protocol](../results/robustness/protocol.json) · '
'[Per-seed parameters](../results/robustness/parameters.json) · '
'[All 4,320 outcomes](../results/robustness/metrics.csv) · '
'[All means and 1,104 intervals](../results/robustness/summary.json) · '
'[Environment](../results/robustness/environment.json)','',
'The stress replay plots interval-end true reservoir volume and preceding interval-start measured '
'level (plus the guarded lower estimate where defined). These timestamps differ by two seconds, '
'as with the existing monitor convention.','']
(ROOT/'docs/ROBUSTNESS.md').write_text('\n'.join(lines))
header='<section class="failure-section" id="robustness" aria-labelledby="robustness-heading">'
html=header+f'''<p class="eyebrow">06 / BREAK THE ASSUMPTIONS</p>
<h2 id="robustness-heading">The protection does not generalize.</h2>
<p>All four strategies and their settings were frozen before 4,320 new runs: nine sensing challenges × five plant regimes × 24 paired virtual patients. The wider test exposes gradual-drift and startup-offset blind spots, flow-measurement errors, and false level-fault attribution under unfamiliar dynamics.</p>
<div class="guard-results"><article><strong>{drift['low_reservoir_s']:.2f} s</strong><span>Mean exposure under gradual drift<br>Reference plant · no level alarms</span></article><article><strong>{initial['low_reservoir_s']:.2f} s</strong><span>Mean exposure with an initial offset<br>Reference plant · no level alarms</span></article><article><strong>{cap['level_alarm_ever']:.0%}</strong><span>Runs flagged in a clean-sensor cell<br>Altered drainage cap · no level fault injected</span></article></div>
<p>These cases show why a level flag is a hypothesis, and why the earlier zero-depletion result applies only to its original challenge set. The alternative dynamics are engineering assumptions, not calibrated physiology.</p>
<img src="robustness-exposure.svg" alt="All 45 stress cells for the four frozen strategies. Gradual drift, initial bias and combined errors retain depletion failures.">
<div class="table-scroll" tabindex="0" role="region" aria-label="Pooled unfamiliar-dynamics outcomes"><table><caption>Equal-weight means across 45 artificial cells · not clinical event frequencies</caption><thead><tr><th scope="col">Strategy</th><th scope="col">Low reservoir (s)</th><th scope="col">Empty requests (s)</th><th scope="col">Deficit AUC (mL O₂/m²)</th></tr></thead><tbody>'''
for vid,m in s['pooled_means'].items():
    html+=f'<tr><th scope="row">{names[vid]}</th><td>{m["low_reservoir_s"]:.2f}</td><td>{m["empty_request_s"]:.2f}</td><td>{m["deficit_auc"]:.2f}</td></tr>'
html+=f'''</tbody></table></div><p><strong>The tradeoff remains:</strong> the fixed reserve reduces mean exposure to {reserve['low_reservoir_s']:.2f} s versus {guard['low_reservoir_s']:.2f} s for guarded, while increasing oxygen deficit from {guard['deficit_auc']:.2f} to {reserve['deficit_auc']:.2f}. Neither is a general solution. These outcomes are not risk-matched.</p>
<img src="robustness-tradeoffs.svg" alt="Guard minus reserve differences show where each method has lower depletion or oxygen deficit.">
<img src="robustness-alarms.svg" alt="Any level flag by sensing and dynamics condition. Starred rows have no injected level fault, so flags can falsely attribute a problem to that channel.">
<p><strong>The next requirement:</strong> establish when the level measurement is trustworthy, using explicitly tested uncertainty or an independent reference. A new method would need fresh evaluation conditions; these failures must not be tuned away and then reused as independent evidence.</p>
<small>All 45 cells remain in the report. Six replay cells and seed 8000 were fixed before evaluation; choose “Unfamiliar sensing &amp; dynamics” above to inspect true, sensed and estimated levels. Aggregate seeds 8000–8023. No clinical calibration or established novelty.</small>
<div class="links"><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/docs/ROBUSTNESS.md">Full robustness report ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/results/robustness/metrics.csv">All 4,320 outcomes ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/results/robustness/protocol.json">Frozen protocol and settings hash ↗</a></div></section>'''
path=ROOT/'web/index.html';text=path.read_text()
if header in text:
    start=text.index(header);end=text.index('</section>',start)+len('</section>')
    text=text[:start]+html+text[end:]
else:text=text.replace('<section class="methods">',html+'<section class="methods">',1)
text=text.replace('06 / THE METHOD','07 / THE METHOD')
path.write_text(text)
print('Generated failure-first report, complete cell table and portfolio section.')
