from version_display import v1_display
"""Build a result-derived rc.4 report and two labelled diagnostic replays."""
import argparse
import hashlib
from io import StringIO
import json
from xml.etree import ElementTree
import finite_return_study as study

ROOT = study.ROOT


def section(summary):
    primary = summary['groups']['primary']; abrupt = summary['groups']['abrupt_stop']
    selected = summary['selected_candidate']; reference = primary['zero_return']['means']['deficit_auc']
    labels = {'credit_15': '15-second credit', 'credit_30': '30-second credit', 'credit_60': '60-second credit',
              'zero_return': 'rc.3 zero-return reference', 'rc2': 'Previous rc.2', 'eligible_pi': 'Eligible PI'}
    rows = []
    for name in study.methods():
        stats = primary[name]
        rows.append(f'<tr><th scope="row">{labels[name]}</th><td>{stats["means"]["deficit_auc"]:.2f}</td><td>{stats["floor_crossing_cases"]}/512</td><td>{abrupt[name]["floor_crossing_cases"]}/128</td><td>{stats["worst_minimum_L"]*1000:.2f}</td></tr>')
    if selected:
        deficit = primary[selected]['means']['deficit_auc']
        selection = f'The fixed development rule selects {labels[selected].lower()}: zero floor crossings and zero empty requests in both the primary and abrupt-stop grids, then lowest primary deficit among qualifying candidates. Mean primary deficit falls {100*(reference-deficit)/reference:.1f}% versus rc.3, from {reference:.2f} to {deficit:.2f}.'
    else:
        selection = 'None of the three candidates meets the fixed zero-crossing/zero-empty selection rule across both primary and abrupt-stop grids. No candidate is selected. Lower oxygen deficit alone is insufficient to qualify a design.'
    witness = selected or 'credit_15'
    failures = sum(summary['groups'][g][n]['floor_crossing_cases'] for g in ('missing', 'biased', 'shared') for n in study.CANDIDATES)
    empties = sum(summary['groups'][g][n]['empty_cases'] for g in ('missing', 'biased', 'shared') for n in study.CANDIDATES)
    secondary = f'The three finite-credit candidates have {failures} floor-crossing cases and {empties} empty-request cases across their 1,152 missing/biased/shared-calibration runs. All failures and per-method/regime results remain in the linked logs. Missing calibration retains maximum permitted braking; finite credit never enables recovery without independent support.'
    gate = 'All existing per-regime development gates pass, but this remains reused development data and the PI comparator must be revisited before a design is frozen.' if summary['development_joint_success'] else 'The complete development milestone still fails. Stable v2.0 is not ready.'
    url = 'https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/'
    return '''<!-- finite-return-development:start -->
<section class="failure-section" id="finite-return-development" aria-labelledby="finite-return-heading">
<p class="eyebrow">V2.0-RC.4 / DEVELOPMENT ONLY</p>
<h2 id="finite-return-heading">Testing a limited return-flow assumption.</h2>
<p>rc.3 protected the reservoir but braked too much. This iteration credits half of a conservative current return-flow estimate for 15, 30 or 60 seconds, then assumes zero return forever. The exact braking reserve still retains every configured pump-lag model. These are explicit engineering assumptions about future return, not measurements or guarantees.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Finite return-flow comparison"><table data-study="finite-return"><caption>32 reused development patients · mean oxygen-deficit AUC per 600-second run (mL O₂/m²) · experimental reservoir floor 250 mL</caption><thead><tr><th scope="col">Controller</th><th scope="col">Primary deficit AUC</th><th scope="col">Primary floor crossings</th><th scope="col">Abrupt-stop floor crossings</th><th scope="col">Primary worst minimum (mL)</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<p>'''+selection+'''</p>
<p>The fixed 6,144-run experiment includes 3,072 primary, 2,304 calibration-failure and 768 abrupt-stop simulations. In the extra challenge, return stops for 45 seconds without advance warning. The controller sees current measurements; it never receives the event schedule. The three frozen references exactly reproduce all 2,688 repeated rc.3 comparison cases.</p>
<div class="caution"><strong>'''+gate+'''</strong><p>'''+secondary+'''</p><p>Unknown shared absolute calibration bias and pump dynamics outside the configured grid can still invalidate protection. Passing a finite set of abrupt-stop tests does not validate the return-flow assumption in general.</p></div>
<figure><img src="finite-return-comparison.svg" alt="Reservoir volume and oxygen delivery for a finite-return candidate, the conservative rc.3 reference and PI in primary and abrupt-stop diagnostic cases." style="width:100%;height:auto"><figcaption>Seed 37014, combined faults and slow pump. Left: the previously identified worst rc.2 primary case. Right: an abrupt 45-second return stop. Finite-credit trace: '''+labels[witness]+''' ('''+('selected on development' if selected else 'predeclared diagnostic reference; no candidate qualified')+'''). These reused development cases are not independent confirmation.</figcaption></figure>
<p>Confirmation remains 0/2, with both reserved 32-patient cohorts untouched. Final stable v1 stays at v1.14.0. The interactive controls below replay the labelled historical experiments.</p>
<div class="links"><a href="'''+url+'''results/finite-return-development/summary.json">rc.4 results and all gates ↗</a><a href="'''+url+'''results/finite-return-development/protocol.json">Fixed protocol ↗</a><a href="'''+url+'''src/perfusion_candidates/finite_return.py">Finite-return reserve code ↗</a></div>
</section>
<!-- finite-return-development:end -->'''


def plot(summary, check=False, preview_path=None):
    witness = summary['selected_candidate'] or 'credit_15'
    results = {}
    for stage in ('primary', 'abrupt_stop'):
        for name in (witness, 'zero_return', 'eligible_pi'):
            results[stage+'/'+name] = study.run(37014, stage, 'combined', 'slow', 'positive_start' if stage == 'primary' else 'clean', 'good', name, study.methods()[name])
    traces = {key: [[round(r['time'], 8), round(r['reservoir'], 8), round(r['do2'], 8)] for r in value['rows']] for key, value in results.items()}
    checksum = hashlib.sha256(json.dumps(traces, sort_keys=True).encode()).hexdigest()
    if check:
        tree = ElementTree.fromstring((ROOT/'web/finite-return-comparison.svg').read_text())
        assert any(node.text == checksum for node in tree.iter()), 'Stale diagnostic trace data'
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'svg.hashsalt': 'finite-return-rc4', 'font.size': 9})
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, layout='constrained')
    for column, stage in enumerate(('primary', 'abrupt_stop')):
        for name, label, color in ((witness, witness.replace('credit_', '')+'-second credit', '#26736a'), ('zero_return', 'rc.3 zero return', '#b5852d'), ('eligible_pi', 'Eligible PI', '#6b64a4')):
            rows = results[stage+'/'+name]['rows']; t = [r['time'] for r in rows]
            axes[0, column].plot(t, [r['reservoir']*1000 for r in rows], label=label, color=color, linewidth=1.5)
            axes[1, column].plot(t, [r['do2'] for r in rows], color=color, linewidth=1.5)
        axes[0, column].set_title('Primary diagnostic' if stage == 'primary' else '45-second abrupt return stop')
        axes[0, column].axhline(250, color='#333333', linestyle='--', label='250 mL floor')
        axes[1, column].axhline(280, color='#333333', linestyle='--', label='280 oxygen target')
        axes[0, column].set_ylabel('Reservoir volume (mL)')
        axes[1, column].set_ylabel('Oxygen delivery (mL O₂/min/m²)')
        axes[1, column].set_xlabel('Simulation time (s)')
        for ax in axes[:, column]: ax.grid(alpha=.2); ax.legend(fontsize=7, loc='best')
    fig.suptitle('Finite-return protection · seed 37014 · reused development cases')
    if preview_path: fig.savefig(preview_path, format='png', dpi=140)
    stream = StringIO(); fig.savefig(stream, format='svg', metadata={'Date': None, 'Description': checksum}); plt.close(fig)
    return stream.getvalue()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true'); parser.add_argument('--preview-path'); args = parser.parse_args()
    summary = json.loads((study.OUT/'summary.json').read_text()); fragment = section(summary)
    path = ROOT/'web/index.html'; html = path.read_text()
    start, end = '<!-- finite-return-development:start -->', '<!-- finite-return-development:end -->'
    if start in html:
        before, rest = html.split(start, 1); _, after = rest.split(end, 1); updated = before+fragment+after
    else:
        marker = '<!-- depletion-development:start -->'; assert html.count(marker) == 1
        updated = html.replace(marker, fragment+'\n'+marker)
    updated = updated.replace('Perfusion Sentinel / v2.0-rc.3', 'Perfusion Sentinel / v2.0-rc.4')
    svg = plot(summary, check=args.check, preview_path=args.preview_path)
    if args.check:
        assert v1_display(updated) == v1_display(html), 'Stale finite-return report'
        print('PASS: finite-return web report and six diagnostic trace series match results.')
    else:
        path.write_text(v1_display(updated)); (ROOT/'web/finite-return-comparison.svg').write_text(svg)
