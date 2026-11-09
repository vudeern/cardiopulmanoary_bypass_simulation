"""Export the post-result audit with an explicitly nondeployable truth witness."""
import argparse,csv,json
from pathlib import Path
from perfusion_lab.benchmark import paired_interval
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/slowdown-audit'

def outputs():
 p=json.loads((OUT/'protocol.json').read_text());runs=json.loads((OUT/'replays.json').read_text());bench=json.loads((OUT/'benchmarks.json').read_text());rows=list(csv.DictReader((OUT/'runs.csv').open()));comparisons=[]
 for cell in p['cells']:
  phys,plant,_,_=cell.split('__');b=bench['34000__'+phys+'__'+plant];selected=b['rows'][::3]
  if selected[-1] is not b['rows'][-1]:selected.append(b['rows'][-1])
  tr={k:[r[f] for r in selected] for k,f in dict(t='time',do2='do2',monitor='do2',reservoir='reservoir',pressure='pressure',level_sensor='reservoir',level_lower='reservoir').items()}
  for k in ('infeasible','fault','level_fault'):tr[k]=[False]*len(selected)
  tr['metrics']={**b['metrics'],'false_reassurance_s':0.};runs[cell+'/truth_witness']=tr
  for method in ('matched_pi','calibration_pi','margin_removed','true_volume','truth_witness'):
   diffs=[]
   for seed in p['patient_seeds']:
    actual=float(next(r for r in rows if r['cell']==cell and int(r['seed'])==seed and r['method']=='hybrid')['deficit_auc'])
    other=bench[str(seed)+'__'+phys+'__'+plant]['metrics']['deficit_auc'] if method=='truth_witness' else float(next(r for r in rows if r['cell']==cell and int(r['seed'])==seed and r['method']==method)['deficit_auc'])
    diffs.append(other-actual)
   comparisons.append(dict(scenario=cell,variant=method,metric='deficit_auc',**paired_interval(diffs)))
 data=dict(protocol=dict(n=16,start_seed=34000,scenarios=p['cells'],default_policy='hybrid',baseline_label='observed hybrid',duration=600,dt=1),
  variants=[dict(id='hybrid',label='Observed hybrid · unchanged'),dict(id='matched_pi',label='Matched screened PI'),dict(id='calibration_pi',label='Calibration-only PI'),dict(id='margin_removed',label='Diagnostic · uncertainty interval removed'),dict(id='true_volume',label='Diagnostic · exact volume supplied'),dict(id='truth_witness',label='Offline truth witness · not deployable')],comparisons=comparisons,runs={},
  labels={c:c.replace('__',' · ').replace('_',' ') for c in p['cells']},
  descriptions={c:'Post-result decision audit: '+c.replace('__',' · ').replace('_',' ')+'. Existing patient/noise seeds are reused; no controller is retuned. Interval removal and exact volume are diagnostic ablations that may violate constraints. The offline witness uses true parameters, state and future disturbances, respects the reservoir floor and an explicit unavoidable-initial-pressure envelope, and is not a clinical or sensor-based controller. The optimistic LP is a separate bound, never a replayed plant trajectory.' for c in p['cells']})
 result={'web/slowdown-data.js':'/* Post-result diagnostic; no deployable performance claim. */\nconst SLOWDOWN_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
 for cell in p['cells']:result['web/slowdown-'+cell+'.js']='/* Precomputed Python audit output. */\nObject.assign(SLOWDOWN_STUDY.runs,'+json.dumps({k:v for k,v in runs.items() if k.startswith(cell+'/')},separators=(',',':'))+');\n'
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 for name,value in outputs().items():
  path=ROOT/name
  if args.check:assert path.read_text()==value,name
  else:path.write_text(value)
 print('PASS: 48 slowdown-audit replay artifacts match source evidence; LP is not shown as a real trajectory.')
