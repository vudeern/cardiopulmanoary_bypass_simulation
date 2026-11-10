from version_display import v1_display
"""Generate the rc.5 four-arm report and labelled diagnostic replays."""
import argparse
import hashlib
from io import StringIO
import json
from xml.etree import ElementTree
import calibrated_pump_study as study

ROOT=study.ROOT
LABELS={'rc4':'rc.4 reference','single_anchor':'One anchor, full grid',
    'retained_two_anchor':'Two anchors, retained models','retained_single_anchor':'One anchor, retained models',
    'archived_pi':'Archived eligible PI'}


def replay(name,stage):
    fault='positive_start' if stage=='primary' else 'clean'
    if name in study.NAMES:
        return study.run(37014,stage,'combined','slow',fault,'good',name,study.methods()[name])
    if name=='archived_pi':
        prev=study.first.previous
        return prev.run(37014,stage,'combined','slow',fault,'good','eligible_pi',prev.methods()['eligible_pi'])
    return study.first.run(37014,stage,'combined','slow',fault,'good',name,study.first.methods()[name])


def section(s):
    primary=s['groups']['primary']; abrupt=s['groups']['abrupt_stop']; selected=s['selected_candidate']
    base=primary['rc4']['means']['deficit_auc']; early=primary['single_anchor']['means']['deficit_auc']
    table=[]
    for n in ('rc4','single_anchor')+study.NAMES:
        d=primary[n]
        table.append(f'<tr><th scope="row">{LABELS[n]}</th><td>{d["means"]["startup_unsupported_s"]:.0f}</td><td>{d["means"]["deficit_auc"]:.2f}</td><td>{d["floor_crossing_cases"]}/512</td><td>{abrupt[n]["floor_crossing_cases"]}/128</td></tr>')
    if selected:
        d=primary[selected];delta=100*(base-d['means']['deficit_auc'])/base
        decision=f'The fixed follow-up selection rule chooses {LABELS[selected].lower()}. Primary deficit falls {delta:.1f}% versus rc.4, from {base:.2f} to {d["means"]["deficit_auc"]:.2f}, with zero floor crossings and empty requests in the primary and abrupt-stop grids. Its worst primary reservoir minimum is {d["worst_minimum_L"]*1000:.2f} mL.'
    else:
        decision='No replacement is selected. The rc.4 reference remains best among qualifying arms, or no replacement passes the fixed protection rule. Lower oxygen deficit alone does not qualify a design.'
    costs=[]
    for g in ('missing','biased','shared'):
        for n in ('rc4','single_anchor')+study.NAMES:
            d=s['groups'][g][n]
            costs.append(f'<tr><th scope="row">{g} / {LABELS[n]}</th><td>{d["means"]["deficit_auc"]:.2f}</td><td>{d["floor_crossing_cases"]}/128</td><td>{d["empty_cases"]}/128</td></tr>')
    witness=selected or 'retained_two_anchor'
    gate='All existing development gates pass, but a comparator review and independent confirmation are still required.' if s['development_joint_success'] else 'The complete development milestone still fails. Stable v2.0 remains blocked on oxygen delivery and later independent confirmation.'
    url='https://github.com/vudeern/cardiopulmanoary_bypass_simulation/blob/main/'
    return '''<!-- startup-models:start -->
<section class="failure-section" id="startup-models" aria-labelledby="startup-models-heading">
<p class="eyebrow">V2.0-RC.5 / ADAPTIVE DEVELOPMENT ONLY</p>
<h2 id="startup-models-heading">Earlier support is not enough.<br>Test the braking bottleneck.</h2>
<p>The first independent calibration arrives at 6 seconds; the second arrives at 126 seconds. One anchor can initialize a wide volume/bias set without narrowing the existing uncertainty allowances. Earlier support alone lowers mean deficit by only '''+f'{100*(base-early)/base:.3f}%'+'''. The controller still lacks a feasible higher-flow command.</p>
<p>The adaptive follow-up reserves against pump hypotheses still consistent with calibration, instead of the entire configured grid. This tests the braking bottleneck with one- and two-anchor support. It makes protection conditional on retaining a sufficiently accurate pump response; a bad calibration/model assumption can discard the real response and defeat reserve.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="Startup and braking mechanism comparison"><table data-study="startup-models"><caption>Same 32 development patients · deficit AUC in mL O₂/m² per 600-second run · experimental floor 250 mL</caption><thead><tr><th scope="col">Arm</th><th scope="col">Startup unsupported (s)</th><th scope="col">Primary deficit AUC</th><th scope="col">Primary floor crossings</th><th scope="col">Abrupt-stop floor crossings</th></tr></thead><tbody>'''+''.join(table)+'''</tbody></table></div>
<p>'''+decision+'''</p>
<div class="caution"><strong>'''+gate+'''</strong><p>Archived eligible PI has mean primary deficit 444.08. These are reused development data: the 2,048-run startup comparison informed a 2,048-run follow-up, completing four paired mechanism arms. The same 512 archived PI primary cases supply the unchanged gate comparison and are not counted as new runs. No independent confirmation, universal protection or hardware/clinical validation is claimed.</p></div>
<details><summary>All calibration-failure outcomes</summary><div class="table-scroll" tabindex="0" role="region" aria-label="rc.5 calibration failure results"><table><caption>128 cases per arm and calibration regime</caption><thead><tr><th scope="col">Regime / arm</th><th scope="col">Deficit AUC</th><th scope="col">Floor crossings</th><th scope="col">Empty requests</th></tr></thead><tbody>'''+''.join(costs)+'''</tbody></table></div></details>
<p>All settings, failures and both protocols remain public. Missing calibration preserves the braking fallback and its delivery cost. Shared absolute bias remains unidentifiable, and passing this abrupt-stop grid does not prove the model-retention assumptions generally valid.</p>
<figure><img src="startup-models-comparison.svg" alt="Reservoir volume and oxygen delivery for an rc.5 diagnostic arm, rc.4 and PI in primary and abrupt-stop cases." style="width:100%;height:auto"><figcaption>Seed 37014, combined faults, slow pump. Left: the previously identified primary diagnostic case. Right: a 45-second abrupt return stop. rc.5 trace: '''+LABELS[witness]+''' ('''+('selected on reused development data' if selected else 'diagnostic arm; no replacement selected')+'''). These cases are not independent confirmation.</figcaption></figure>
<p>New rc.5 simulations: 2,048 primary, 1,536 calibration-failure and 512 abrupt-stop runs, for 4,096 total. Confirmation remains 0/2 and both reserved cohorts stay untouched. Final stable v1 remains v1.14.0; the interactive controls below retain the labelled historical experiments.</p>
<div class="links"><a href="'''+url+'''results/calibrated-pump-development/summary.json">Four-arm results and gates ↗</a><a href="'''+url+'''results/startup-development/summary.json">Startup-only results ↗</a><a href="'''+url+'''docs/STARTUP_AND_MODELS.md">Mechanisms and assumptions ↗</a><a href="'''+url+'''results/calibrated-pump-development/protocol.json">Adaptive follow-up protocol ↗</a></div>
</section>
<!-- startup-models:end -->'''


def plot(s,check=False,preview_path=None):
    witness=s['selected_candidate'] or 'retained_two_anchor'; results={}
    for stage in ('primary','abrupt_stop'):
        for name in (witness,'rc4','archived_pi'):results[stage+'/'+name]=replay(name,stage)
    traces={k:[[round(r['time'],8),round(r['reservoir'],8),round(r['do2'],8)] for r in v['rows']] for k,v in results.items()}
    checksum=hashlib.sha256(json.dumps(traces,sort_keys=True).encode()).hexdigest()
    if check:
        tree=ElementTree.fromstring((ROOT/'web/startup-models-comparison.svg').read_text())
        assert any(n.text==checksum for n in tree.iter()),'Stale startup/model trace data'
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'svg.hashsalt':'startup-models-rc5','font.size':9})
    fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True,layout='constrained')
    for col,stage in enumerate(('primary','abrupt_stop')):
        for name,color in ((witness,'#26736a'),('rc4','#b5852d'),('archived_pi','#6b64a4')):
            rows=results[stage+'/'+name]['rows'];t=[r['time'] for r in rows]
            axes[0,col].plot(t,[r['reservoir']*1000 for r in rows],label=LABELS[name],color=color,linewidth=1.5)
            axes[1,col].plot(t,[r['do2'] for r in rows],color=color,linewidth=1.5)
        axes[0,col].set_title('Primary diagnostic' if stage=='primary' else '45-second abrupt return stop')
        axes[0,col].axhline(250,color='#333333',linestyle='--',label='250 mL floor')
        axes[1,col].axhline(280,color='#333333',linestyle='--',label='280 oxygen target')
        axes[0,col].set_ylabel('Reservoir volume (mL)');axes[1,col].set_ylabel('Oxygen delivery (mL O₂/min/m²)')
        axes[1,col].set_xlabel('Simulation time (s)')
        for ax in axes[:,col]:ax.grid(alpha=.2);ax.legend(fontsize=7,loc='best')
    fig.suptitle('Startup and calibrated pump hypotheses · seed 37014 · development only')
    if preview_path:fig.savefig(preview_path,format='png',dpi=140)
    stream=StringIO();fig.savefig(stream,format='svg',metadata={'Date':None,'Description':checksum});plt.close(fig)
    return stream.getvalue()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');parser.add_argument('--preview-path');args=parser.parse_args()
    s=json.loads((study.OUT/'summary.json').read_text());fragment=section(s)
    path=ROOT/'web/index.html';html=path.read_text();start,end='<!-- startup-models:start -->','<!-- startup-models:end -->'
    if start in html:
        before,rest=html.split(start,1);_,after=rest.split(end,1);updated=before+fragment+after
    else:
        marker='<!-- finite-return-development:start -->';assert html.count(marker)==1
        updated=html.replace(marker,fragment+'\n'+marker)
    updated=updated.replace('Perfusion Sentinel / v2.0-rc.4','Perfusion Sentinel / v2.0-rc.5')
    svg=plot(s,check=args.check,preview_path=args.preview_path)
    if args.check:assert v1_display(updated)==v1_display(html),'Stale startup/model report';print('PASS: rc.5 report and six diagnostic traces match recorded outcomes.')
    else:path.write_text(v1_display(updated));(ROOT/'web/startup-models-comparison.svg').write_text(svg)
