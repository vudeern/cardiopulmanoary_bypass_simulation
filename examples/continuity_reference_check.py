"""Secondary fixed-prior-PI sensitivity; does not replace frozen primary test.

The fixed settings and scope are written before reading the new evaluation.
No tuning is performed. Machine-readable engineering logs only.
"""
import csv,json,argparse
from pathlib import Path
from continuity_study import run,mean,write_csv,REFS,FINAL_CASES,FINAL_PLANTS
from simc_benchmark import digest,dumps,METRICS
from perfusion_lab.benchmark import paired_interval
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/continuity-reference-check'
METHOD=dict(id='prior_simc',kind='simc',options=dict(tau_c=1.5,target_level=.45))

def specification():
 return dict(status='secondary_fixed_reference_sensitivity',method=METHOD,
  reason='Retain the previous v1.9 fast PI settings alongside the newly development-selected primary PI. This is a separately labelled sensitivity, never a replacement for the frozen primary criterion.',
  seeds=list(range(28000,28016)),cases=FINAL_CASES,plants=FINAL_PLANTS,references=REFS,
  source_sha256=digest(Path(__file__)),main_protocol_sha256=digest(ROOT/'results/continuity-study/protocol.json'),
  tuning_performed=False,clinical_validation=False)

def execute(check=False):
 p=json.loads((OUT/'protocol.json').read_text());assert p==specification()
 target=ROOT/'results/continuity-study/evaluation.csv'
 rows=list(csv.DictReader((OUT/'evaluation.csv').open())) if check else []
 if not check:
  for seed in p['seeds']:
   for case in FINAL_CASES:
    for plant in FINAL_PLANTS:
     for reference in REFS:
      result=run('evaluation',case,plant,reference,seed,METHOD)
      rows.append(dict(phase='evaluation',case=case,plant=plant,reference=reference,seed=seed,method='prior_simc',**{k:result['metrics'][k] for k in METRICS}))
   print('Fixed prior PI seed complete:',seed,flush=True)
  write_csv(OUT/'evaluation.csv',rows)
 assert len(rows)==2048
 assert len({tuple(r[k] for k in ('case','plant','reference','seed')) for r in rows})==2048
 current=list(csv.DictReader(target.open()));groups={};comparisons=[]
 for group in ('good','delayed_loss','biased','never','outside_lag_bound'):
  def select(r):return r['plant']=='outside_lag_bound' if group=='outside_lag_bound' else r['reference']==group and (r['plant']!='outside_lag_bound' if group in ('good','delayed_loss') else True)
  ref=[r for r in rows if select(r)];new=[r for r in current if select(r) and r['method']=='continuity']
  groups[group]=dict(continuity=mean(new),prior_simc=mean(ref))
  for metric in METRICS:
   differences=[]
   for seed in p['seeds']:
    differences.append(mean([r for r in new if int(r['seed'])==seed])[metric]-mean([r for r in ref if int(r['seed'])==seed])[metric])
   comparisons.append(dict(group=group,metric=metric,**paired_interval(differences)))
 summary=dict(status=p['status'],runs=2048,group_means=groups,comparisons=comparisons,protocol_sha256=digest(OUT/'protocol.json'),primary_replaced=False)
 if check:
  stored=json.loads((OUT/'summary.json').read_text())
  def same(a,b):
   if isinstance(a,dict):
    assert a.keys()==b.keys()
    for k in a:same(a[k],b[k])
   elif isinstance(a,list):
    assert len(a)==len(b)
    for x,y in zip(a,b):same(x,y)
   elif isinstance(a,(str,bool)) or a is None:assert a==b
   else:assert abs(float(a)-float(b))<1e-8
  same(stored,summary)
  for r in (rows[0],rows[1024],rows[-1]):
   result=run('evaluation',r['case'],r['plant'],r['reference'],int(r['seed']),METHOD)
   same({m:float(r[m]) for m in METRICS},{m:result['metrics'][m] for m in METRICS})
  print('PASS: 2048 fixed-prior-PI sensitivity runs, prespecified source/primary hashes, patient-block comparisons and rerun sentinels; primary unchanged.')
 else:(OUT/'summary.json').write_text(dumps(summary));print(dumps(groups),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
 if args.freeze:
  OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'protocol.json').exists();(OUT/'protocol.json').write_text(dumps(specification()));print('Fixed prior-PI sensitivity specified; no evaluation read.')
 else:execute(args.check)
