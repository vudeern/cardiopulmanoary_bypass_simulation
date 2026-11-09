"""Export frozen reference-integrity replays and observed bias rejection counts."""
import argparse,csv,json
from pathlib import Path
from perfusion_lab.benchmark import paired_interval
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/integrity-study'

def outputs():
 p=json.loads((OUT/'protocol.json').read_text());runs=json.loads((OUT/'replays.json').read_text());rows=list(csv.DictReader((OUT/'evaluation.csv').open()));comparisons=[]
 for cell in p['replay_cells']:
  phys,plant,fault,cal=cell.split('__')
  for method in ('hybrid','calibration_pi','unscreened'):
   diffs=[]
   for seed in p['evaluation_seeds']:
    block=[r for r in rows if (r['phys'],r['plant'],r['fault'],r['calibration'],int(r['seed']))==(phys,plant,fault,cal,seed)]
    diffs.append(float(next(r for r in block if r['method']==method)['deficit_auc'])-float(next(r for r in block if r['method']=='matched_pi')['deficit_auc']))
   comparisons.append(dict(scenario=cell,variant=method,metric='deficit_auc',**paired_interval(diffs)))
 data=dict(protocol=dict(n=16,start_seed=34000,scenarios=p['replay_cells'],default_policy='hybrid',baseline_label='matched screened PI',duration=600,dt=1),
  variants=[dict(id='hybrid',label='Screened PI + predictive override'),dict(id='matched_pi',label='PI · same screened reference observer'),dict(id='calibration_pi',label='Tuned PI · independent calibration only'),dict(id='unscreened',label='Ablation · screening disabled')],comparisons=comparisons,runs={},
  labels={c:c.replace('__',' · ').replace('_',' ') for c in p['replay_cells']},
  descriptions={c:'Frozen reference-integrity experiment: '+c.replace('__',' · ').replace('_',' ')+'. Independent calibration is a simulated measurement channel with declared noise and failure modes, not supplied truth. Routine references are screened before correction. Both matched controllers receive the same observer design. Missing, biased and jointly corrupted calibrations remain explicit failures.' for c in p['replay_cells']})
 result={'web/integrity-data.js':'/* Frozen synthetic reference-integrity study. */\nconst INTEGRITY_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
 for cell in p['replay_cells']:result['web/integrity-'+cell+'.js']='/* Precomputed Python output. */\nObject.assign(INTEGRITY_STUDY.runs,'+json.dumps({k:v for k,v in runs.items() if k.startswith(cell+'/')},separators=(',',':'))+');\n'
 classification={}
 for cal in p['calibrations']:
  classification[cal]={}
  for method in ('hybrid','matched_pi','unscreened'):
   block=[r for r in rows if r['calibration']==cal and r['method']==method]
   totals={k:sum(int(float(r[k])) for r in block) for k in ('reference_bad_total','reference_bad_rejected','reference_good_total','reference_good_rejected')}
   classification[cal][method]={**totals,'bad_bias_sample_rejection_fraction':totals['reference_bad_rejected']/totals['reference_bad_total'] if totals['reference_bad_total'] else None,'healthy_bias_sample_rejection_fraction':totals['reference_good_rejected']/totals['reference_good_total'] if totals['reference_good_total'] else None}
 result['results/integrity-study/classification.json']=json.dumps(dict(status='observed_synthetic_bias_labels_not_clinical_sensitivity',label_rule='abs(injected routine bias)>0.04 L; noise alone is not labelled bias. Rejection can reflect quarantine rather than identification of a specific bias. Always inspect healthy-sample rejection alongside biased-sample rejection.',calibration_only_pi='Does not evaluate routine samples and is omitted from classification rates.',calibrations=classification),indent=2)+'\n'
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 for name,value in outputs().items():
  p=ROOT/name
  if args.check:assert p.read_text()==value,name
  else:p.write_text(value)
 print('PASS: 24 reference-integrity replays and observed reference classifications match source logs.')
