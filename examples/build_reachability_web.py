from version_display import v1_display
"""Export rc.2 development replays; explicitly label reused selection data."""
import argparse
import csv
import json
from pathlib import Path
from perfusion_lab.benchmark import paired_interval
from reachability_base_study import OUT,ROOT
from reachability_study import REPLAY_CELLS,OUT as FIRST_OUT


def outputs():
    summary=json.loads((OUT/'summary.json').read_text())
    selection=json.loads((OUT/'selection.json').read_text())
    replay=json.loads((OUT/'replays.json').read_text())
    risk=json.loads((OUT/'risk-summary.json').read_text())
    risk_replays=json.loads((OUT/'risk-replays.json').read_text())
    names=list(dict.fromkeys((selection['candidate'],selection['comparator'],'frozen_v1')))
    cells=['__'.join(c) for c in REPLAY_CELLS]
    records=[]
    for directory in (FIRST_OUT,OUT):
        for stage in ('primary','secondary'):
            for path in sorted((directory/stage).glob('*.csv')):
                with path.open() as f:records.extend(csv.DictReader(f))
    comparisons=[]
    baseline=selection['comparator']
    for cell in REPLAY_CELLS:
        rows=[r for r in records if tuple(r[k] for k in ('phys','plant','fault','calibration'))==cell]
        for name in names:
            if name==baseline:continue
            differences=[]
            for seed in range(37000,37032):
                by_name={r['method']:float(r['deficit_auc']) for r in rows if int(r['seed'])==seed}
                differences.append(by_name[name]-by_name[baseline])
            comparisons.append(dict(scenario='__'.join(cell),variant=name,metric='deficit_auc',**paired_interval(differences)))
    risk_cell=tuple(risk['worst_cell']);risk_key=risk['worst_replay_key']
    cases=[r for r in records if tuple(r[k] for k in ('phys','plant','fault','calibration'))==risk_cell]
    for name in names:
        if name==baseline:continue
        differences=[]
        for seed in range(37000,37032):
            by_name={r['method']:float(r['deficit_auc']) for r in cases if int(r['seed'])==seed}
            differences.append(by_name[name]-by_name[baseline])
        comparisons.append(dict(scenario=risk_key,variant=name,metric='deficit_auc',**paired_interval(differences)))
    replay.update(risk_replays);cells.append(risk_key)
    labels={'legacy_common':'Common-settings legacy hybrid','interval_only':'Calibration-set change only',
        'reserve_only':'Joint-braking change only','combined':'Calibration set + joint braking',
        'frozen_v1':'Frozen final v1 hybrid',
        'matched_legacy':'Joint braking · matched PI base',
        'aggressive_legacy':'Joint braking · aggressive PI base',
        'matched_consistent':'Calibration set + joint braking · matched PI base',
        'aggressive_consistent':'Calibration set + joint braking · aggressive PI base'}
    data=dict(protocol=dict(n=32,start_seed=37000,scenarios=cells,default_policy=selection['candidate'],
        baseline_label='Development-selected PI',duration=600,dt=1,
        scenario_seeds={c:(risk['worst_seed'] if c==risk_key else 37000) for c in cells}),
        variants=[dict(id=n,label=labels.get(n,'Development-selected PI · '+n.replace('_',' '))) for n in names],
        comparisons=comparisons,runs={},labels={c:c.replace('__',' · ').replace('_',' ') for c in cells},
        descriptions={c:'rc.2 DEVELOPMENT case: '+c.replace('__',' · ').replace('_',' ')+'. Settings and PI comparator were selected using these same 32 development patients. These replays are exploratory and are not untouched confirmation evidence. Calibration error and retained pump/inflow assumptions can fail; shared bias remains unidentifiable.' for c in cells})
    data['labels'][risk_key]='Lowest reservoir case · seed '+str(risk['worst_seed'])
    data['descriptions'][risk_key]='POST-RESULT WORST-CASE VIEW: the selected development controller reached '+str(round(1000*risk['statistics'][selection['candidate']]['minimum_reservoir_L'],2))+' mL in this synthetic case, despite passing mean exposure gates. This patient was selected after inspecting results. The PI and frozen v1 traces use the same patient and fault. Cohort intervals still summarize all 32 development patients for these physical settings; no individual safety or confirmation claim is established.'
    values={'web/reachability-data.js':'/* Development only: selection and analysis reuse these patients. */\nconst REACHABILITY_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
    for cell in cells:
        values['web/reachability-'+cell+'.js']='/* Precomputed development replay. */\nObject.assign(REACHABILITY_STUDY.runs,'+json.dumps({k:v for k,v in replay.items() if k.startswith(cell+'/')},separators=(',',':'))+');\n'
    progress=dict(version='2.0.0rc2',stage='development_only',patients=32,
        primary_runs=summary['total_primary_runs'],secondary_runs=summary['total_secondary_runs'],
        candidate=summary['candidate'],comparator=summary['comparator'],
        candidate_eligible=summary['candidate_eligible'],comparator_eligible=summary['comparator_eligible'],
        development_gates=summary['development_gates'],development_joint_success=summary['development_joint_success'],
        version2_ready=False,qualifying_confirmation_cohorts=0,confirmation_seeds_executed=[],
        reason='Development selection and analysis reuse the same 32 patients. Two distinct untouched confirmation cohorts are still required, even if development gates pass.')
    values['results/reachability-base-development/version2-progress.json']=json.dumps(progress,indent=2)+'\n'
    # Visible numbers must stay aligned with the complete retained logs.
    import re,html
    page=(ROOT/'web/index.html').read_text()
    table=re.search(r'<table data-study="reachability">(.*?)</table>',page,re.S)
    assert table,'Missing current development table'
    body=re.search(r'<tbody>(.*?)</tbody>',table.group(1),re.S).group(1)
    displayed=[[html.unescape(re.sub('<[^>]+>','',v)).strip() for v in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',row,re.S)] for row in re.findall(r'<tr>(.*?)</tr>',body,re.S)]
    expected=[]
    for group,label in (('clean','Clean reference'),('bias','Reference bias'),('outage','Reference outage')):
        a=summary['method_means'][selection['candidate']]['groups'][group]
        b=summary['method_means'][selection['comparator']]['groups'][group]
        expected.append([label,f"{a['deficit_auc']:.2f}",f"{b['deficit_auc']:.2f}",f"{100*(1-a['deficit_auc']/b['deficit_auc']):.1f}%",f"{a['low_reservoir_s']:.2f}",f"{b['low_reservoir_s']:.2f}"])
    assert displayed==expected,'Visible development table is stale'
    readme=(ROOT/'README.md').read_text()
    selected_risk=risk['statistics'][selection['candidate']]
    assert str(selected_risk['low_reservoir_cases'])+'/'+str(selected_risk['primary_cases']) in readme
    assert f"{1000*selected_risk['minimum_reservoir_L']:.2f} mL" in readme
    return {k:(v1_display(v) if k.startswith('web/') else v) for k,v in values.items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for name,value in outputs().items():
        path=ROOT/name
        if args.check:assert path.read_text()==value,name
        else:path.write_text(value)
    print('PASS: 21 explicitly labelled development/worst-case replay views and v2 progress match raw logs.')
