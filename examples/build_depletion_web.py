from version_display import v1_display
"""Generate the rc.3 report and a fixed, post-result worst-case rc.2 replay."""
import argparse
from io import StringIO
from pathlib import Path
import hashlib
from xml.etree import ElementTree
import depletion_study as study
import json

ROOT = study.ROOT


def section(summary):
    groups = summary['groups']; rows = []
    for label, name in (('Conservative protection', 'protected'), ('Previous rc.2', 'rc2'), ('Eligible PI', 'eligible_pi')):
        data = groups['primary'][name]
        rows.append(f'<tr><th scope="row">{label}</th><td>{data["means"]["deficit_auc"]:.2f}</td><td>{data["floor_crossing_cases"]}/512</td><td>{data["worst_minimum_L"]*1000:.2f}</td></tr>')
    url = 'https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/'
    return '''<!-- depletion-development:start -->
<section class="failure-section" id="depletion-development" aria-labelledby="depletion-heading">
<p class="eyebrow">V2.0-RC.3 / DEVELOPMENT ONLY</p>
<h2 id="depletion-heading">Depletion prevented in this grid.<br>Oxygen delivery still needs work.</h2>
<p>The new protection mode budgets for return flow stopping completely while the pump slows. It retains every configured pump-lag model for braking and commands maximum permitted deceleration when independent calibration support is missing or conflicting. The previous controller and independently selected PI comparator are rerun with the same inputs and actuator limits.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Conservative depletion comparison"><table data-study="depletion"><caption>32 reused development patients · 512 healthy-calibration primary cases per method · means per 600-second run</caption><thead><tr><th scope="col">Controller</th><th scope="col">Oxygen-deficit AUC (mL O₂/m²)</th><th scope="col">Cases below 250 mL</th><th scope="col">Worst minimum (mL)</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<p>All three methods have zero primary empty-reservoir requests. Across 2,688 new runs (1,536 primary and 1,152 calibration-failure runs), the protected mode has no floor crossings or empty requests. In missing/biased/shared-calibration tests its worst minimum is 622.15 mL. These are observed results within this synthetic grid, not guaranteed protection against arbitrary corruption or omitted pump dynamics.</p>
<div class="caution"><strong>The protection costs too much oxygen delivery.</strong><p>Primary deficit AUC rises to 1,749.13 from 396.25 for rc.2 and 444.08 for eligible PI. Missing-calibration deficit rises further to 2,706.39. Stable v2.0 remains blocked. The next step is a less restrictive protection design with explicit return-flow assumptions, while retaining this conservative mode as a reference.</p></div>
<figure><img src="depletion-worst-case.svg" alt="Replay of the previous worst-case patient: conservative protection preserves reservoir volume while delivering less oxygen than rc.2 and PI." style="width:100%;height:auto"><figcaption>Post-result diagnostic replay: seed 37014, combined faults, slow pump, positive-start routine bias, healthy independent calibration. This is the previously identified worst rc.2 case, not a new confirmation patient.</figcaption></figure>
<p>The same 32 patients are reused for development; confirmation remains 0/2. Final stable v1 stays at v1.14.0. The interactive controls below continue to replay the labelled historical experiments, including rc.2.</p>
<div class="links"><a href="'''+url+'''results/depletion-development/summary.json">rc.3 results ↗</a><a href="'''+url+'''results/depletion-development/protocol.json">Fixed development protocol ↗</a><a href="'''+url+'''src/perfusion_lab/depletion.py">Protection code ↗</a></div>
</section>
<!-- depletion-development:end -->'''


def plot(check=False):
    results = {name: study.run(37014, 'combined', 'slow', 'positive_start', 'good', name, method) for name, method in study.methods().items()}
    # Numerical libraries/CPU kernels can differ in insignificant last bits.
    # Validate scientific traces at 1e-8 precision, below displayed precision;
    # raw simulation records retain full precision and their own checks.
    traces = {name: [[round(r['time'], 8), round(r['reservoir'], 8), round(r['do2'], 8)] for r in result['rows']] for name, result in results.items()}
    checksum = hashlib.sha256(json.dumps(traces, sort_keys=True).encode()).hexdigest()
    if check:
        root = ElementTree.fromstring((ROOT/'web/depletion-worst-case.svg').read_text())
        assert any(node.text == checksum for node in root.iter()), 'Stale diagnostic trace data'
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'svg.hashsalt': 'depletion-rc3', 'font.size': 10})
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True, layout='constrained')
    for name, label, color in (('protected', 'Conservative protection', '#26736a'), ('rc2', 'Previous rc.2', '#b54538'), ('eligible_pi', 'Eligible PI', '#6b64a4')):
        result = results[name]
        rows = result['rows']
        axes[0].plot([r['time'] for r in rows], [r['reservoir']*1000 for r in rows], label=label, color=color, linewidth=1.7)
        axes[1].plot([r['time'] for r in rows], [r['do2'] for r in rows], color=color, linewidth=1.7)
    axes[0].axhline(250, color='#333333', linestyle='--', label='Experimental floor (250 mL)')
    axes[1].axhline(280, color='#333333', linestyle='--', label='Oxygen target (280)')
    axes[0].set_ylabel('Reservoir volume (mL)'); axes[1].set_ylabel('Oxygen delivery (mL O₂/min/m²)')
    axes[1].set_xlabel('Simulation time (s)')
    for ax in axes:
        ax.grid(alpha=.2); ax.legend(loc='best', fontsize=8)
    fig.suptitle('Previously identified worst rc.2 case · seed 37014 · development only')
    stream = StringIO(); fig.savefig(stream, format='svg', metadata={'Date': None, 'Description': checksum}); plt.close(fig)
    return stream.getvalue()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    summary = json.loads((study.OUT/'summary.json').read_text()); fragment = section(summary)
    path = ROOT/'web/index.html'; html = path.read_text()
    start, end = '<!-- depletion-development:start -->', '<!-- depletion-development:end -->'
    if start in html:
        before, rest = html.split(start, 1); _, after = rest.split(end, 1)
        updated = before+fragment+after
    else:
        marker = '<section class="failure-section" id="v2-development"'
        assert html.count(marker) == 1
        updated = html.replace(marker, fragment+'\n'+marker)
    updated = updated.replace('V2.0-RC.2 / DEVELOPMENT ONLY', 'V2.0-RC.2 / PREVIOUS DEVELOPMENT')
    updated = updated.replace('Perfusion Sentinel / v2.0-rc.2', 'Perfusion Sentinel / v2.0-rc.3')
    svg = plot(check=args.check); svg_path = ROOT/'web/depletion-worst-case.svg'
    if args.check:
        assert v1_display(updated) == v1_display(html), 'Stale depletion report'
        print('PASS: depletion web report and diagnostic replay figure match recorded results.')
    else:
        path.write_text(v1_display(updated)); svg_path.write_text(svg)
