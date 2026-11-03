"""Post-evaluation truth audit; truth is used here only, never by controllers."""
import argparse,json
from pathlib import Path
import numpy as np
from continuity_study import run
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/continuity-study'
CELLS=('combined__lagged__good','combined__lagged__delayed_loss','venous_bias__nominal__good','venous_bias__nominal__delayed_loss')

def output():
 p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text());rows=[]
 for cell in CELLS:
  case,plant,reference=cell.split('__')
  for seed in p['evaluation_seeds']:
   result=run('evaluation',case,plant,reference,seed,s['methods']['continuity']);samples=[];truth=.85
   for r in result['rows']:
    if r['balance_reference_age'] is not None:
     samples.append(dict(age=r['balance_reference_age'],error=r['balance_level_estimate']-truth,
       offset_error=r['venous_bias_estimate']-.75))
    truth=r['reservoir']
   for scope in ('anchored','age_over_180s'):
    selected=[r for r in samples if scope=='anchored' or r['age']>180]
    if selected:rows.append(dict(cell=cell,seed=seed,scope=scope,n=len(selected),
      mean_level_error_L=float(np.mean([r['error'] for r in selected])),
      mean_absolute_level_error_L=float(np.mean([abs(r['error']) for r in selected])),
      max_level_overestimate_L=max(r['error'] for r in selected),
      mean_venous_offset_error_L_min=float(np.mean([r['offset_error'] for r in selected]))))
 return dict(status='post_evaluation_mechanism_audit_not_a_selection_or_success_gate',
  truth_used_only_in_analysis=True,observation_alignment='Estimate at decision time versus preceding physical state, not step-end truth.',
  limitation='Selected cells describe the mechanism; they are not a complete-grid summary. No further tuning is performed.',rows=rows)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();value=output();path=OUT/'diagnostics.json'
 if args.check:
  old=json.loads(path.read_text());assert len(old['rows'])==len(value['rows'])
  for a,b in zip(old['rows'],value['rows']):
   for k,v in a.items():
    if isinstance(v,(int,float)):assert abs(v-b[k])<1e-8
    else:assert v==b[k]
  print('PASS: aligned post-evaluation continuity mechanism audit; no tuning performed.')
 else:
  path.write_text(json.dumps(value,indent=2)+'\n')
  for cell in CELLS:
   for scope in ('anchored','age_over_180s'):
    rows=[r for r in value['rows'] if r['cell']==cell and r['scope']==scope]
    if rows:print(cell,scope,'mean signed/absolute level error L:',np.mean([r['mean_level_error_L'] for r in rows]),np.mean([r['mean_absolute_level_error_L'] for r in rows]))
