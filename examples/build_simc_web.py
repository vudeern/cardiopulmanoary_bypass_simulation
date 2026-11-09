"""Export working comparison replays; no paper/report documents."""
import csv
import json
from pathlib import Path
from perfusion_lab.benchmark import paired_interval

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/simc-benchmark'


def outputs():
    p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
    runs=json.loads((OUT/'replays.json').read_text());rows=list(csv.DictReader((OUT/'metrics.csv').open()))
    comparisons=[]
    for cell in p['replay_cells']:
        case,plant,ref=cell.split('__');diff=[]
        for seed in p['evaluation_seeds']:
            selected=[r for r in rows if r['phase']=='evaluation' and r['case']==case and r['plant']==plant and r['reference']==ref and int(r['seed'])==seed]
            diff.append(float(next(r for r in selected if r['method']=='forecast')['deficit_auc'])-
                        float(next(r for r in selected if r['method']=='simc')['deficit_auc']))
        comparisons.append(dict(scenario=cell,variant='forecast',metric='deficit_auc',**paired_interval(diff)))
    variants=[dict(id='simc',label='Verified SIMC PI · reservoir override'),
              dict(id='forecast',label='Forecast · shared supervisor')]
    data=dict(protocol=dict(n=16,start_seed=16000,scenarios=p['replay_cells'],default_policy='forecast',
        baseline_label='SIMC PI',duration=600,dt=1),variants=variants,comparisons=comparisons,runs={},
        labels={cell:cell.replace('__',' · ').replace('_',' ') for cell in p['replay_cells']},
        descriptions={cell:('Frozen final simulation: '+cell.replace('__',' · ').replace('_',' ')+'. '
            'Both controllers share the same sensing, references, oxygen cap, pressure slowdown and actuator limits. '
            'SIMC is a verified general PI method; this is a simulated CPB application, not a clinical-device comparison.') for cell in p['replay_cells']})
    result={'web/verified-data.js':'/* Generated verified general-reference comparison. */\nconst VERIFIED_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
    for cell in p['replay_cells']:
        subset={name:value for name,value in runs.items() if name.startswith(cell+'/')}
        result['web/verified-'+cell+'.js']='/* Frozen synthetic replay, 1 s scoring and 3 s display. */\nObject.assign(VERIFIED_STUDY.runs,'+json.dumps(subset,separators=(',',':'))+');\n'
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for name,content in outputs().items():
        path=ROOT/name
        if args.check:assert path.read_text()==content,name
        else:path.write_text(content)
    print('PASS: 12 final replays exported and tied to the frozen comparison.' if not args.check else 'PASS: verified-reference replay artifacts match source logs.')


if __name__=='__main__':main()
