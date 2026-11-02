"""Generate an explicit answer to the declared reference-method question."""
import json
import csv
import numpy as np
from pathlib import Path
from perfusion_lab.benchmark import paired_interval

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/reference-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text())
ids=[v['id'] for v in s['methods']]
names={v['id']:v['label'] for v in s['methods']}
good=s['group_means']['good'];v=s['verdict']
answer=('Yes, on the declared primary synthetic test.' if v['demonstrated'] else
        'No advantage was demonstrated on the declared primary synthetic test.')
margin=next(m for m in s['methods'] if m['id']=='simple_reference')['options'].get('reserve_margin',0.)
with (OUT/'metrics.csv').open() as handle:
    primary_rows=[r for r in csv.DictReader(handle) if r['phase']=='evaluation' and r['reference_case']=='good']
secondary=[]
for metric in ('low_reservoir_s','empty_request_s','deficit_auc'):
    def blocks(vid):
        return [float(np.mean([float(r[metric]) for r in primary_rows if r['variant']==vid
                and int(r['seed'])==seed])) for seed in p['evaluation_seeds']]
    estimate=paired_interval([a-b for a,b in zip(blocks('simple_reference'),blocks('reserve'))])
    secondary.append(dict(metric=metric,variant='simple_reference',baseline='reserve',**estimate))
(OUT/'secondary-contrast.json').write_text(json.dumps(dict(
    status='Descriptive contrast added after seeing final results; not the predeclared primary test',
    reference_group='good',comparisons=secondary),indent=2)+'\n')
lines=['# Independent level reference: the research answer — v1.4.0','',
'## Question and answer','',
'**Question:** Does an age-based measurement-credibility allowance outperform a tuned simple '
'reference correction, given the same noisy, delayed measurements?','',f'**Answer: {answer}**','',
'This addresses the method comparison inside the simulator. It does not answer whether the '
'software is effective on actual equipment, scientifically novel, publishable at a particular '
'venue, patentable or commercially valuable. Those questions remain open.','',
'## The broader engineering question','',
'Under the good simulated reference channel, the simple-reference package has lower mean '
f"reservoir exposure (**{good['simple_reference']['low_reservoir_s']:.2f} versus {good['reserve']['low_reservoir_s']:.2f} s**), "
f"empty requests (**{good['simple_reference']['empty_request_s']:.2f} versus {good['reserve']['empty_request_s']:.2f} s**) and "
f"oxygen deficit (**{good['simple_reference']['deficit_auc']:.2f} versus {good['reserve']['deficit_auc']:.2f} mL O₂/m²**) "
'than always keeping the original +0.40 L reserve. Thus there is evidence of a useful tradeoff '
'improvement for this reference-plus-correction package inside the simulator. Added information '
'has a cost and must actually be obtainable; neither hardware cost nor real reference performance '
'is established here.','',
'This simple-reference versus fixed-reserve contrast was added descriptively after seeing '
'the final results. It does not replace the failed/passed primary test above, and is not presented '
'as an independently predeclared confirmation. The intervals below use the same paired patient blocks.','',
'| Outcome | Simple reference − fixed reserve | 95% paired interval |',
'|---|---:|---|']
for c in secondary:
    lines.append(f"| {c['metric']} | {c['mean']:.2f} | [{c['low']:.2f}, {c['high']:.2f}] |")
lines += ['',
'The result supports a narrow distinction: the reference-plus-simple-correction package improves '
'these three sample means relative to the fixed reserve with a good reference; extra age-based '
'complexity must still earn its own benefit. It does not isolate an information effect from every '
'policy change, and it does not generalize that gain to faulty reference channels.','',
'## Primary test: good reference channel','',
'The primary reference is sampled every 60 seconds, delivered after 4 seconds, with independent '
'Gaussian noise SD 0.01 L. Results below average seven final sensing conditions and three '
'plant settings equally within each of 12 paired virtual patients (seeds 10000–10011). '
'The cells are not treated as independent patients, and their weights are not clinical frequencies.','',
'| Method | Low reservoir (s) | Empty requests (s) | Deficit AUC (mL O₂/m²) |',
'|---|---:|---:|---:|']
for vid in ids:
    m=good[vid];lines.append(f"| {names[vid]} | {m['low_reservoir_s']:.2f} | {m['empty_request_s']:.2f} | {m['deficit_auc']:.2f} |")
lines += ['',
'The primary success rule was recorded before evaluation: bounded minus simple must have an '
'upper 95% paired bootstrap interval no greater than **+1 second** for both low-reservoir exposure '
'and empty requests, and simple minus bounded must have a strictly positive lower interval for '
'oxygen deficit. The 1-second tolerance is an engineering comparison choice, not a clinical '
'noninferiority margin. Other reference regimes are descriptive stress tests.','',
f"- Joint reservoir/empty-request criterion: **{'passed' if v['risk_criterion_pass'] else 'failed'}**.",
f"- Lower oxygen-deficit criterion: **{'passed' if v['deficit_criterion_pass'] else 'failed'}**.",
f"- Joint primary result: **{v['answer']}**.",'',
'| Outcome | Simple − age-based mean difference | 95% paired interval |',
'|---|---:|---|']
for metric in ('low_reservoir_s','empty_request_s','deficit_auc'):
    c=next(c for c in s['comparisons'] if c['group']=='good' and c['variant']=='simple_reference' and c['metric']==metric)
    lines.append(f"| {metric} | {c['mean']:.2f} | [{c['low']:.2f}, {c['high']:.2f}] |")
lines += ['',
'A non-demonstration is not proof of equivalence or impossibility. The 12-patient synthetic '
'sampler and its paired intervals only quantify variation under this construction. No sample-size '
'calculation for a clinical or external validation study is implied.','',
'## Does the extra measurement address the old blind spots?','',
'The following good-reference cells isolate the two level problems that the old step guard '
'could not generally identify. Each entry is mean low-reservoir exposure in seconds. '
'The simple method also includes its development-selected reserve margin, so this is a comparison '
'of complete methods, not a claim that the information effect has been isolated from every policy change.','',
'| Cell | Original | Fixed reserve | Old step guard | Simple reference | Age-based bound |',
'|---|---:|---:|---:|---:|---:|']
for sensor in ('drift','initial'):
    for plant in p['final_plants']:
        cell=f'{sensor}__{plant}__good';m=s['cell_means'][cell]
        lines.append('| '+cell+' | '+' | '.join(f"{m[vid]['low_reservoir_s']:.2f}" for vid in ids)+' |')
lines += ['',
'## Methods and fair access to information','',
'All methods use the existing Sentinel control cost, pressure screen, actuator limits and Hb '
'observer. The original, fixed +0.40 L reserve and old step guard deliberately ignore the new '
'channel: they are information ablations. Both reference-aware methods receive identical sampling '
'schedules, reference noise and dropouts for each paired case; reference values can differ because '
'their policies produce different physical trajectories.','',
'A reference at acquisition time τ is compared with the stored inline level from τ, even when '
'delivered later. Its bias estimate is held until the next delivered reference. The simple method '
f"subtracts this bias and a fixed **{margin:.2f} L** margin selected on development data. "
'The age-based method subtracts the same estimated bias plus **0.04 L + 0.003 L/s × acquisition '
'age**. It supplies a zero lower level while no reference is available or the last sample is '
'older than 180 seconds. This is an engineering loss-of-information response, not a guarantee '
'against depletion. Both methods still estimate drainage from the original flow/inline-change '
'observer; neither gains hidden true flow or drainage.','',
'The age allowance is not a confidence interval. Gaussian reference noise is unbounded, a '
'sudden sensor step can exceed the allowed drift, and flow bias can corrupt the shared forecast. '
'A simulated independent reference is additional information, not evidence that a suitable '
'real sensor already has the assumed accuracy or availability.','',
'## Development and final evaluation separation','',
'- Development: nine v1.3 sensing profiles × two plant settings × eight new seeds (9000–9007) '
'× seven candidates = **1,008 runs**.',
'- Simple margins tested: 0, 0.05, 0.10, 0.20, 0.30 and 0.40 L. Choose minimum deficit among '
'candidates meeting the age-based method’s development mean depletion/empty-request budgets; '
'if none matches, choose lexicographically by those risks and deficit and mark unmatched.',
f"- Selected simple margin: **{margin:.2f} L**; development budget match: **{selection['matched_development_budget']}**. "
'The selection file is written before final evaluation and its SHA-256 is checked afterward.',
'- Final: seven sensing conditions × three plants × six reference regimes × 12 new paired seeds '
'× five frozen methods = **7,560 runs**, for **8,568 total**.',
'- Final sensing uses +0.50 L level faults, +0.90 L/min flow bias, 240-second drift and 12× '
'inline level/flow noise. Development uses +0.40 L, +0.75 L/min, 300-second drift and 10× noise.',
'- Final pump response is 6 seconds, rather than the development slow pump’s 8 seconds. '
'The lagged final plant uses 18-second drainage lag and nonlinearity 0.06. Final drainage restriction '
'is 0.40 rather than 0.45; onset/window distributions also differ.',
'- The protocol is internally recorded, not externally preregistered. Fault families are '
'informed by previous failures; only the declared parameter/settings/seed changes are held out.',
'- Six replay cells and seed 10000 are fixed before evaluation. All 126 cells remain in the CSV '
'and summary. Bootstrap intervals use 2,000 paired patient resamples and seed 2026.','',
'## Reference reliability stress tests','',
'| Regime | Engineering construction |',
'|---|---|',
'| good | Period 60 s; delay 4 s; independent SD 0.01 L |',
'| noisy | Same timing; SD 0.05 L |',
'| delayed | Period 90 s; delay 30 s; SD 0.01 L |',
'| dropout | Period 60 s; delay 4 s; 25% random losses and no acquisitions from 360 to 840 s |',
'| biased | Good timing/noise plus +0.15 L reference bias |',
'| common_mode | Good timing/noise plus the inline level bias copied into the reference; independence deliberately violated |','',
'![All reference regimes and both outcomes](reference-results.svg)','',
'The table below lists reservoir exposure / deficit AUC, not a combined score. It deliberately '
'shows reference failures alongside the favorable-channel primary test.','',
'| Reference | Original | Fixed reserve | Old guard | Simple reference | Age-based bound |',
'|---|---|---|---|---|---|']
for group in p['references']:
    means=s['group_means'][group]
    lines.append('| '+group+' | '+' | '.join(f"{means[vid]['low_reservoir_s']:.2f} / {means[vid]['deficit_auc']:.2f}" for vid in ids)+' |')
lines += ['', '![All final cells, age-based versus simple exposure](reference-cells.svg)','',
'## Interpretation and remaining limits','',
'Use the primary answer above to judge the proposed age-based method; do not select a favorable '
'reference subgroup after seeing results. The extra measurement and the complexity of the method '
'are separate questions. Any gains that disappear under common-mode bias or flow error must '
'remain part of the claimed operating scope. The simulated hardware assumptions and the retained '
'flow/drainage model still need independent physical measurements and stronger alternative methods. '
'This study does not turn the project into a clinically usable or sellable controller.','',
'### Descriptive flow-error diagnostic','',
'The following table averages the three primary-test plants by sensing condition. It is a '
'diagnostic added after evaluation, not an additional primary hypothesis. It exposes why correcting '
'level alone does not repair the shared flow/drainage observer.','',
'| Sensor condition | Simple low (s) | Age-based low (s) | Simple empty requests (s) | Age-based empty requests (s) |',
'|---|---:|---:|---:|---:|']
for sensor in p['final_sensors']:
    cells=[s['cell_means'][sensor+'__'+plant+'__good'] for plant in p['final_plants']]
    values=[float(np.mean([cell[vid][metric] for cell in cells]))
            for metric in ('low_reservoir_s','empty_request_s')
            for vid in ('simple_reference','bounded_reference')]
    lines.append('| '+sensor+' | '+' | '.join(f'{x:.2f}' for x in values)+' |')
lines += ['',
'## Complete final cell exposures','',
'Values are mean seconds below the 0.25 L experimental floor; the CSV/JSON also retain every '
'oxygen, pressure, pump and reference-availability outcome.','',
'| Cell | Original | Reserve | Old guard | Simple reference | Age-based bound |',
'|---|---:|---:|---:|---:|---:|']
for cell,means in s['cell_means'].items():
    lines.append('| '+cell+' | '+' | '.join(f"{means[vid]['low_reservoir_s']:.2f}" for vid in ids)+' |')
lines += ['', '## Reproduce','', '```bash','python -m pip install -e ".[plots]"',
'python -m unittest discover -s tests -v','python examples/reference_study.py',
'python examples/plot_reference_study.py','python examples/report_reference_study.py',
'python examples/validate_reference_study.py','node tests/web_contract.cjs','```','',
'[Protocol and primary criteria](../results/reference-study/protocol.json) · '
'[Development selection](../results/reference-study/selection.json) · '
'[Frozen methods](../results/reference-study/methods.json) · '
'[All 8,568 outcomes](../results/reference-study/metrics.csv) · '
'[Machine-readable answer and intervals](../results/reference-study/summary.json) · '
'[Per-seed parameters](../results/reference-study/parameters.json)','',
'Replay sensor/lower-estimate traces are from interval start; physical reservoir truth is at '
'interval end. Simple reference lower estimates are shown before the controller’s fixed margin.','']
(ROOT/'docs/REFERENCE_RESULT.md').write_text('\n'.join(lines))
header='<section class="failure-section" id="reference-result" aria-labelledby="reference-heading">'
html=header+f'''<p class="eyebrow">07 / ANSWER THE QUESTION</p><h2 id="reference-heading">Does credibility checking beat simple correction?</h2>
<p><strong>{answer}</strong> The primary comparison uses the same noisy, delayed level references for both methods, with the simple reserve margin selected on separate development cases. The test requires lower oxygen deficit without materially worse depletion exposure.</p>
<p><strong>The broader result:</strong> with a good simulated reference, simple correction plus a {margin:.2f} L margin reduces mean reservoir exposure from {good['reserve']['low_reservoir_s']:.2f} to {good['simple_reference']['low_reservoir_s']:.2f} s, empty requests from {good['reserve']['empty_request_s']:.2f} to {good['simple_reference']['empty_request_s']:.2f} s, and oxygen deficit from {good['reserve']['deficit_auc']:.2f} to {good['simple_reference']['deficit_auc']:.2f} mL O₂/m², compared with the fixed reserve. This is an additional descriptive contrast, not the predeclared primary test. It supports the simpler reference package under these assumptions.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Primary reference comparison"><table><caption>Primary good-reference test · 12 paired virtual patients · 21 equally weighted sensing/plant cells</caption><thead><tr><th scope="col">Method</th><th scope="col">Low reservoir (s)</th><th scope="col">Empty requests (s)</th><th scope="col">Deficit AUC (mL O₂/m²)</th></tr></thead><tbody>'''
for vid in ids:
    m=good[vid];html+=f'<tr><th scope="row">{names[vid]}</th><td>{m["low_reservoir_s"]:.2f}</td><td>{m["empty_request_s"]:.2f}</td><td>{m["deficit_auc"]:.2f}</td></tr>'
html+=f'''</tbody></table></div><p><strong>Predeclared criteria:</strong> the age-based method’s upper paired interval must stay within +1 second of simple correction for both depletion metrics, and its oxygen deficit must be lower with a paired interval excluding zero. Protection criterion: {'passed' if v['risk_criterion_pass'] else 'failed'}. Oxygen criterion: {'passed' if v['deficit_criterion_pass'] else 'failed'}. This is an engineering tolerance, not a clinical margin.</p>
<img src="reference-results.svg" alt="Both reservoir exposure and oxygen deficit for all five methods across six reference reliability regimes.">
<p><strong>Separate the information from the algorithm:</strong> a new reference can make an existing offset observable; that alone does not show that an age-based policy is better than a simple correction. The report separately compares the old drift/startup blind spots and keeps biased, delayed, missing and common-mode references in view.</p>
<img src="reference-cells.svg" alt="Age-based versus simple reference reservoir exposure across every one of the 126 final cells.">
<p>The simple method uses a {margin:.2f} L fixed margin. The age-based method uses a 0.04 L base allowance plus 0.003 L/s of sample age, with an explicit loss-of-information response. These are engineering assumptions, not calibrated probability bounds. Neither receives true flow or drainage.</p>
<small>1,008 development + 7,560 held-out evaluation runs = 8,568. The final evaluation changes sensor magnitudes, timing, pump response and drainage settings. References are simulated hardware; novelty, real-equipment benefit and commercial demand remain unestablished. Choose “Independent level reference” above for six prespecified replay cells.</small>
<div class="links"><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/docs/REFERENCE_RESULT.md">Research answer and paired intervals ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/results/reference-study/summary.json">Machine-readable verdict ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/results/reference-study/protocol.json">Protocol and exact pass/fail criteria ↗</a></div></section>'''
path=ROOT/'web/index.html';text=path.read_text()
if header in text:
    start=text.index(header);end=text.index('</section>',start)+len('</section>')
    text=text[:start]+html+text[end:]
else:text=text.replace('<section class="methods">',html+'<section class="methods">',1)
path.write_text(text.replace('07 / THE METHOD','08 / THE METHOD'))
print('Generated the explicit primary answer and all final reference outcomes.')

