"""Export the frozen braking comparison for the existing interactive viewer."""
import csv,json,argparse
from pathlib import Path
from perfusion_lab.benchmark import paired_interval

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/braking-study'


def outputs():
 p=json.loads((OUT/'protocol.json').read_text());runs=json.loads((OUT/'replays.json').read_text())
 rows=list(csv.DictReader((OUT/'evaluation.csv').open()));comparisons=[]
 for cell in p['replay_cells']:
  case,plant,ref=cell.split('__')
  for method in ('braking','old_forecast'):
   diffs=[]
   for seed in p['evaluation_seeds']:
    records=[r for r in rows if (r['case'],r['plant'],r['reference'],int(r['seed']))==(case,plant,ref,seed)]
    diffs.append(float(next(r for r in records if r['method']==method)['deficit_auc'])-float(next(r for r in records if r['method']=='simc')['deficit_auc']))
   comparisons.append(dict(scenario=cell,variant=method,metric='deficit_auc',**paired_interval(diffs)))
 data=dict(protocol=dict(n=16,start_seed=25000,scenarios=p['replay_cells'],default_policy='braking',baseline_label='SIMC PI',duration=600,dt=1),
  variants=[dict(id='braking',label='Predictive braking controller'),dict(id='simc',label='Retuned SIMC PI reference'),dict(id='old_forecast',label='Earlier forecast · fixed context')],
  comparisons=comparisons,runs={},labels={c:c.replace('__',' · ').replace('_',' ') for c in p['replay_cells']},
  descriptions={c:'Frozen braking-reserve comparison: '+c.replace('__',' · ').replace('_',' ')+'. Same sensor/reference channels and actuator limits. Braking uses command-history bounds, past level trends and reference metadata; engineering allowances are not guaranteed uncertainty bounds. The 12-second lag case is outside the declared actuator range.' for c in p['replay_cells']})
 result={'web/braking-data.js':'/* Frozen synthetic braking study. */\nconst BRAKING_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
 for cell in p['replay_cells']:
  subset={k:v for k,v in runs.items() if k.startswith(cell+'/')}
  result['web/braking-'+cell+'.js']='/* Precomputed Python output; no browser physiology engine. */\nObject.assign(BRAKING_STUDY.runs,'+json.dumps(subset,separators=(',',':'))+');\n'
 return result


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 for name,value in outputs().items():
  path=ROOT/name
  if args.check:assert path.read_text()==value,name
  else:path.write_text(value)
 print('PASS: 18 braking-study replay artifacts match source logs.')
