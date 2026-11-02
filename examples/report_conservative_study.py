"""Generate the comparison report and web section from retained results."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/conservative-comparison'
p=json.loads((OUT/'protocol.json').read_text())
s=json.loads((OUT/'summary.json').read_text())
selection=json.loads((OUT/'selection.json').read_text())
names={v['id']:('Original Sentinel' if v['id']=='original' else 'Guarded Sentinel'
    if v['id']=='guarded' else f"Reserve +{v['options']['reserve_margin']:.2f} L"
    if v['family']=='reserve' else f"Flow cap {v['options']['flow_cap_index']:.1f} L/min/m²")
    for v in s['selected']}
reserve=next(v['id'] for v in s['selected'] if v['family']=='reserve')
cap=next(v['id'] for v in s['selected'] if v['family']=='flow_cap')
g=s['pooled_means']['guarded'];r=s['pooled_means'][reserve]
fault=s['cohort_means']['unmodeled_level_bias']
interval=next(c for c in s['comparisons'] if c['scenario']=='pooled' and
              c['variant']==reserve and c['metric']=='deficit_auc')
lines=['# Conservative comparator study — v1.2.0','',
'## Question','',
'Does the step-fault guard offer anything beyond keeping a larger reserve or limiting flow all the time? '
'These comparators are simple modifications of original Sentinel, not reproductions of commercial devices '
'or published state-of-the-art controllers. The guard, cost function, Hb observer, pressure screen, '
'20-second forecast and actuator limits are unchanged. No new guard parameters were tuned.','',
'## Design history: retain the exploratory pilot','',
'The first search used six reserve margins (0.10–0.60 L) and six cap indices (1.4–2.4 L/min/m²). '
'Its cap selection hit the highest available setting. We expanded the search rather than report that '
'boundary-limited comparison as decisive. The complete 2,240-run pilot remains in '
'[conservative-pilot](../results/conservative-pilot/protocol.json), including all candidate metrics, selection and summaries. '
'It is exploratory evidence and is not pooled into the final evaluation.','',
'The expanded search uses **12 reserve margins** (0.05–0.60 L in 0.05 L steps) and **17 cap indices** '
'(1.4–4.6 L/min/m² in 0.2 steps), plus original and guarded Sentinel: **31 candidate settings**. '
'The upper cap is effectively inactive for all sampled patient sizes. The three final seed groups '
'were unused in the pilot. The protocol is recorded internally, not independently preregistered.','',
'## Selection before evaluation','',
'- Tuning: seven scenarios × eight seeds (5000–5007) × 31 candidates = **1,736 runs**.',
'- Within each comparator family, select the lowest tuning mean oxygen deficit among candidates meeting '
'both the guard’s mean low-reservoir and empty-request budgets. Ties follow the declared candidate order. '
'If none meets both budgets, retain the least-exposure candidate and mark it unmatched.',
'- The resulting settings were written before evaluation: **+0.40 L reserve** and **2.4 L/min/m² flow cap**. '
'Both met zero-exposure tuning budgets. Neither is a clinical recommendation.',
'- Final evaluation: seven scenarios × 24 fresh seeds (6000–6023) × four locked settings = **672 runs**.',
'- Final stress map: 49 fault cells × four fresh seeds (7000–7003) × four settings = **784 runs**.',
'- Final study total: **3,192 runs**, separate from the 2,240-run pilot. All run-level outcomes remain.',
'- Every run lasts 1,200 seconds at 2-second steps. Scenarios have equal artificial weight; this '
'does not estimate clinical event frequencies. Bootstrap intervals resample the 24 patient seeds '
'after averaging seven scenarios within each patient, rather than pretending there are 168 independent patients.','',
'![All tuning candidates and final locked settings](conservative-frontier.svg)','',
'## Final pooled evaluation','',
'Each row is an equal-weight mean over seven scenarios and 24 paired virtual patients. '
'Deficit AUC is in mL O₂/m². Lower exposure and deficit are preferable, but these are different outcomes.','',
'| Strategy | Low reservoir (s) | Empty requests (s) | Deficit AUC |',
'|---|---:|---:|---:|']
for vid,m in s['pooled_means'].items():
    lines.append(f"| {names[vid]} | {m['low_reservoir_s']:.2f} | {m['empty_request_s']:.2f} | {m['deficit_auc']:.2f} |")
lines += ['',
f"Guarded Sentinel has **{g['deficit_auc']:.2f}** mean deficit versus **{r['deficit_auc']:.2f}** "
'for the selected fixed reserve, with zero measured depletion/empty requests for both on this evaluation. '
f"The paired difference (reserve − guarded) is **{interval['mean']:.2f}**, with a 95% "
f"percentile bootstrap interval **[{interval['low']:.2f}, {interval['high']:.2f}] mL O₂/m²**. "
'A degenerate zero-exposure interval is only an observation of this finite sample, not proof of zero risk.','',
'**The cap does not preserve its tuning risk match on evaluation:** its mean low-reservoir exposure '
f"is {s['pooled_means'][cap]['low_reservoir_s']:.2f} s versus zero for guarded. "
'Do not describe this as an exactly risk-matched evaluation comparison.','',
'## Scenario-level outcomes: the important reversal','',
'The next table reports mean deficit AUC in mL O₂/m²; all other metrics are retained in the CSV and JSON.','',
'| Scenario | Original | Guarded | Reserve +0.40 L | Cap 2.4 |',
'|---|---:|---:|---:|---:|']
for scenario,policies in s['cohort_means'].items():
    lines.append('| '+scenario+' | '+' | '.join(f"{policies[v['id']]['deficit_auc']:.2f}" for v in s['selected'])+' |')
lines += ['',
f"**The simpler reserve wins on the +0.40 L sensor-fault scenario:** its deficit is "
f"**{fault[reserve]['deficit_auc']:.2f}**, compared with **{fault['guarded']['deficit_auc']:.2f}** "
'for guarded, with zero depletion for both. The guard’s pooled advantage comes from avoiding '
'unnecessary conservatism in other scenarios, especially venous obstruction and compound faults. '
'The conclusion depends on how scenarios are weighted; it is not universal superiority.','',
f"In that same scenario, guarded averages {fault['guarded']['high_pressure_s']:.2f} s above "
f"the pressure ceiling versus {fault[reserve]['high_pressure_s']:.2f} s for the reserve. "
'The guard therefore does not dominate every secondary measure either.','',
'## Full stress map','',
'![All locked strategies over all 49 fault cells](conservative-map.svg)','',
'The settings remain locked on the stress map; no cell-specific retuning is performed. '
'All four strategies retain failures. Cell counts below concern low-reservoir time only; '
'equal cells include both successes and unresolved failures.','',
'| Strategy | Cells better / equal / worse than guarded | Worst cell mean exposure (s) |',
'|---|---|---:|']
for vid in s['pooled_means']:
    diffs=[c['means'][vid]['low_reservoir_s']-c['means']['guarded']['low_reservoir_s'] for c in s['map']]
    counts=[sum(d< -1e-9 for d in diffs),sum(abs(d)<1e-9 for d in diffs),sum(d>1e-9 for d in diffs)]
    worst=max(c['means'][vid]['low_reservoir_s'] for c in s['map'])
    lines.append(f"| {names[vid]} | {' / '.join(str(c) for c in counts)} | {worst:.2f} |")
lines += ['',
'## Bounded conclusion and next falsification','',
'Under this equal-weight synthetic challenge set, the guard reduces the oxygen cost of protection '
'relative to the selected always-on reserve. A fixed reserve is better in the targeted bias scenario itself. '
'The cap’s protection does not generalize completely to fresh seeds. These are comparative numerical '
'findings, not established scientific novelty, clinical usefulness or evidence of a market.','',
'The same structural plant and scripted fault timing are used in tuning and evaluation. New seeds '
'are not new physiology or external measurements. The finite grids do not exhaust simple policies, '
'especially conditional threshold/rate alarms, joint reserve/cap tuning, or optimized adaptive margins. '
'The next study should challenge those comparators, scenario weights, gradual drift, initial offsets, '
'flow-sensor faults and plant mismatch. External bench/data validation remains necessary before '
'claims about real equipment.','',
'## Reproduce','',
'```bash','python -m pip install -e ".[plots]"',
'python -m unittest discover -s tests -v',
'python examples/conservative_study.py --pilot  # optional: reproduce archived exploratory pilot',
'python examples/conservative_study.py',
'python examples/plot_conservative_study.py',
'python examples/report_conservative_study.py',
'python examples/validate_conservative_study.py',
'node tests/web_contract.cjs','```','',
'The replay’s “Conservative comparison” dataset uses evaluation seed 6000 and locked settings. '
'Its cohort differences use guarded Sentinel as the reference; the original dataset continues to use reactive.','',
'[Protocol](../results/conservative-comparison/protocol.json) · '
'[Frozen tuning selection](../results/conservative-comparison/selection.json) · '
'[All final-study metrics](../results/conservative-comparison/metrics.csv) · '
'[Complete means and intervals](../results/conservative-comparison/summary.json) · '
'[Execution environment](../results/conservative-comparison/environment.json)','']
(ROOT/'docs/CONSERVATIVE_COMPARISON.md').write_text('\n'.join(lines))
header='<section class="failure-section" id="conservative-comparison" aria-labelledby="comparison-heading">'
html=header+'''<p class="eyebrow">05 / CHALLENGE THE GUARD</p>
<h2 id="comparison-heading">Does a simpler reserve do just as well?</h2>
<p>Two simple changes to original Sentinel test whether detection adds value: always keep extra reserve, or cap pump flow. An exploratory pilot hit a search boundary, so the search was expanded to 31 settings and all final seeds were replaced. Settings were selected on tuning data and locked before evaluation.</p>
<img src="conservative-frontier.svg" alt="All 31 tuning candidates and four locked evaluation settings plotted by reservoir exposure and oxygen deficit.">
<div class="table-scroll" tabindex="0" role="region" aria-label="Final conservative comparison results"><table><caption>Final evaluation · 24 paired virtual patients · seven equally weighted synthetic scenarios</caption><thead><tr><th scope="col">Strategy</th><th scope="col">Low reservoir (s)</th><th scope="col">Empty requests (s)</th><th scope="col">Deficit AUC (mL O₂/m²)</th></tr></thead><tbody>'''
for vid,m in s['pooled_means'].items():
    html+=f'<tr><th scope="row">{names[vid]}</th><td>{m["low_reservoir_s"]:.2f}</td><td>{m["empty_request_s"]:.2f}</td><td>{m["deficit_auc"]:.2f}</td></tr>'
html+='</tbody></table></div>'
html+=f'''<p><strong>The pooled result:</strong> guarded deficit is {g['deficit_auc']:.2f} versus {r['deficit_auc']:.2f} for the fixed reserve, with zero measured depletion for both. Reserve minus guarded is {interval['mean']:.2f} mL O₂/m² (95% paired bootstrap interval {interval['low']:.2f} to {interval['high']:.2f}). Scenarios are equally weighted challenges, not clinical event frequencies.</p>
<p><strong>The reversal:</strong> in the +0.40 L sensor-bias scenario, the fixed reserve has less deficit: {fault[reserve]['deficit_auc']:.2f} versus {fault['guarded']['deficit_auc']:.2f}, with zero depletion for both. The guard earns its pooled advantage in other scenarios. The flow cap also loses its tuning risk match on evaluation.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Scenario-level oxygen deficits"><table><caption>Deficit AUC by scenario · mL O₂/m² · the average does not describe every case</caption><thead><tr><th scope="col">Scenario</th><th scope="col">Original</th><th scope="col">Guarded</th><th scope="col">Reserve +0.40 L</th><th scope="col">Cap 2.4</th></tr></thead><tbody>'''
for scenario,policies in s['cohort_means'].items():
    html+=f'<tr><th scope="row">{scenario.replace("_"," ")}</th>'+''.join(f'<td>{policies[v["id"]]["deficit_auc"]:.2f}</td>' for v in s['selected'])+'</tr>'
html+='''</tbody></table></div><img src="conservative-map.svg" alt="All four locked strategies retain low-reservoir failures on the complete 49-cell stress map.">
<p><strong>What this establishes:</strong> a bounded comparison against two conservative modifications, under the existing synthetic model. It does not establish novelty or performance on real equipment. Gradual drift, flow-sensor errors, unfamiliar plant dynamics and stronger conditional comparators remain to be tested.</p>
<small>Final study: 1,736 tuning + 672 evaluation + 784 stress-map runs = 3,192. The 2,240-run pilot is archived separately. Replay: choose “Conservative comparison” above · seed 6000; aggregate seeds 6000–6023. Full stress map: seeds 7000–7003.</small>
<div class="links"><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/docs/CONSERVATIVE_COMPARISON.md">Full comparison and limitations ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/results/conservative-comparison/selection.json">Inspect the frozen selection ↗</a><a href="https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/results/conservative-comparison/metrics.csv">All final-study outcomes ↗</a></div></section>'''
path=ROOT/'web/index.html';text=path.read_text()
if header in text:
    start=text.index(header);end=text.index('</section>',start)+len('</section>')
    text=text[:start]+html+text[end:]
else:
    text=text.replace('<section class="methods">',html+'<section class="methods">',1)
text=text.replace('05 / THE METHOD','06 / THE METHOD')
path.write_text(text)
print('Generated comparison report and website section from raw-result summaries.')
