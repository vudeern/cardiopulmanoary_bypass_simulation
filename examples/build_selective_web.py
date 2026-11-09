"""Export frozen selective PI replays; no browser physiology engine."""
import argparse,csv,json
from pathlib import Path
from perfusion_lab.benchmark import paired_interval
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/selective-study'

def outputs():
 p=json.loads((OUT/'protocol.json').read_text());runs=json.loads((OUT/'replays.json').read_text());rows=list(csv.DictReader((OUT/'evaluation.csv').open()));comparisons=[]
 for cell in p['replay_cells']:
  case,plant,reference=cell.split('__')
  for method in ('hybrid','fast_pi','brake_only','boost_only'):
   diffs=[]
   for seed in p['evaluation_seeds']:
    block=[r for r in rows if (r['case'],r['plant'],r['reference'],int(r['seed']))==(case,plant,reference,seed)]
    diffs.append(float(next(r for r in block if r['method']==method)['deficit_auc'])-float(next(r for r in block if r['method']=='simc')['deficit_auc']))
   comparisons.append(dict(scenario=cell,variant=method,metric='deficit_auc',**paired_interval(diffs)))
 data=dict(protocol=dict(n=16,start_seed=31000,scenarios=p['replay_cells'],default_policy='hybrid',baseline_label='development-selected SIMC PI',duration=600,dt=1),
  variants=[dict(id='hybrid',label='PI + gated predictive override'),dict(id='simc',label='Development-selected SIMC PI'),dict(id='fast_pi',label='Previous fast SIMC PI · fixed check'),dict(id='brake_only',label='Ablation · braking override only'),dict(id='boost_only',label='Ablation · recovery override only')],comparisons=comparisons,runs={},
  labels={c:c.replace('__',' · ').replace('_',' ') for c in p['replay_cells']},
  descriptions={c:'Frozen selective PI comparison: '+c.replace('__',' · ').replace('_',' ')+'. PI is the foundation. A model-based override requires two reference acquisitions, fresh-enough information and agreement between estimates, with gradual return to PI. This gate is an engineering check, not a confidence probability or hard safety guarantee. The 12-second actuator is outside the declared prediction range.' for c in p['replay_cells']})
 result={'web/selective-data.js':'/* Frozen synthetic selective PI study. */\nconst SELECTIVE_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
 for cell in p['replay_cells']:
  result['web/selective-'+cell+'.js']='/* Precomputed Python output. */\nObject.assign(SELECTIVE_STUDY.runs,'+json.dumps({k:v for k,v in runs.items() if k.startswith(cell+'/')},separators=(',',':'))+');\n'
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 for name,value in outputs().items():
  p=ROOT/name
  if args.check:assert p.read_text()==value,name
  else:p.write_text(value)
 print('PASS: 30 selective PI replay artifacts match frozen source logs.')
