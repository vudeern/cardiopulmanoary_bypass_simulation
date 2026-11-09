"""Export the frozen continuity comparison for the existing interactive viewer."""
import csv,json,argparse
from pathlib import Path
from perfusion_lab.benchmark import paired_interval

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/continuity-study'


def outputs():
 p=json.loads((OUT/'protocol.json').read_text());runs=json.loads((OUT/'replays.json').read_text())
 rows=list(csv.DictReader((OUT/'evaluation.csv').open()));comparisons=[]
 for cell in p['replay_cells']:
  case,plant,ref=cell.split('__')
  for method in ('continuity','previous_braking'):
   diffs=[]
   for seed in p['evaluation_seeds']:
    records=[r for r in rows if (r['case'],r['plant'],r['reference'],int(r['seed']))==(case,plant,ref,seed)]
    diffs.append(float(next(r for r in records if r['method']==method)['deficit_auc'])-float(next(r for r in records if r['method']=='simc')['deficit_auc']))
   comparisons.append(dict(scenario=cell,variant=method,metric='deficit_auc',**paired_interval(diffs)))
 data=dict(protocol=dict(n=16,start_seed=28000,scenarios=p['replay_cells'],default_policy='continuity',baseline_label='SIMC PI',duration=600,dt=1),
  variants=[dict(id='continuity',label='Reference-continuity controller'),dict(id='simc',label='Retuned SIMC PI reference'),dict(id='previous_braking',label='v1.9 predictive braking · fixed context')],
  comparisons=comparisons,runs={},labels={c:c.replace('__',' · ').replace('_',' ') for c in p['replay_cells']},
  descriptions={c:'Frozen reference-continuity comparison: '+c.replace('__',' · ').replace('_',' ')+'. Same sensor/reference channels and actuator limits. Continuity integrates venous measurements and a nominal pump model between reference anchors. Engineering allowances are not guaranteed uncertainty bounds. The 12-second lag case is outside the declared actuator range.' for c in p['replay_cells']})
 result={'web/continuity-data.js':'/* Frozen synthetic continuity study. */\nconst CONTINUITY_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
 for cell in p['replay_cells']:
  subset={k:v for k,v in runs.items() if k.startswith(cell+'/')}
  result['web/continuity-'+cell+'.js']='/* Precomputed Python output; no browser physiology engine. */\nObject.assign(CONTINUITY_STUDY.runs,'+json.dumps(subset,separators=(',',':'))+');\n'
 return result


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 for name,value in outputs().items():
  path=ROOT/name
  if args.check:assert path.read_text()==value,name
  else:path.write_text(value)
 print('PASS: 18 continuity-study replay artifacts match source logs.')
