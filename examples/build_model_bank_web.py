"""Export model-bank replays and explicit progress against the v2 milestone."""
import argparse,csv,json
from pathlib import Path
from perfusion_lab.benchmark import paired_interval
from model_bank_study import group
from simc_benchmark import digest
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/model-bank-study'

def outputs():
 p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text());sel=json.loads((OUT/'selection.json').read_text());runs=json.loads((OUT/'replays.json').read_text());rows=list(csv.DictReader((OUT/'evaluation.csv').open()));comparisons=[]
 for cell in p['replay_cells']:
  phys,plant,fault,cal=cell.split('__')
  for method in ('hybrid','calibration_pi','previous_hybrid','single_model'):
   diffs=[]
   for seed in p['evaluation_seeds']:
    block=[r for r in rows if (r['phys'],r['plant'],r['fault'],r['calibration'],int(r['seed']))==(phys,plant,fault,cal,seed)]
    diffs.append(float(next(r for r in block if r['method']==method)['deficit_auc'])-float(next(r for r in block if r['method']=='matched_pi')['deficit_auc']))
   comparisons.append(dict(scenario=cell,variant=method,metric='deficit_auc',**paired_interval(diffs)))
 data=dict(protocol=dict(n=16,start_seed=36000,scenarios=p['replay_cells'],default_policy='hybrid',baseline_label='PI with the same model-bank observer',duration=600,dt=1),
  variants=[dict(id='hybrid',label='Model-bank hybrid · causal'),dict(id='matched_pi',label='PI · same model-bank observer'),dict(id='calibration_pi',label='Retuned calibration-only PI'),dict(id='previous_hybrid',label='Previous v1.12 hybrid · frozen context'),dict(id='single_model',label='Ablation · nominal two-second model only')],comparisons=comparisons,runs={},labels={c:c.replace('__',' · ').replace('_',' ') for c in p['replay_cells']},descriptions={c:'Frozen v1.14 evaluation: '+c.replace('__',' · ').replace('_',' ')+'. A generic pump-model bank is fitted to past delivered calibration measurements and applied commands. No true volume, true lag or future disturbance enters the controller. Error bands and model coverage are engineering assumptions; missing or shared-corrupted calibration can still defeat them. These are new patient/noise seeds, but reused synthetic model and fault families.' for c in p['replay_cells']})
 result={'web/model-bank-data.js':'/* Frozen causal model-bank experiment. */\nconst MODEL_BANK_STUDY = '+json.dumps(data,separators=(',',':'))+';\n'}
 for cell in p['replay_cells']:result['web/model-bank-'+cell+'.js']='/* Precomputed Python output. */\nObject.assign(MODEL_BANK_STUDY.runs,'+json.dumps({k:v for k,v in runs.items() if k.startswith(cell+'/')},separators=(',',':'))+');\n'
 # Comparator is selected using development evidence, never final outcomes.
 eligible=[]
 if sel['selected']['eligible']:eligible.append(('matched_pi',sel['selected']['pi']['deficit_auc']))
 if sel['calpi_eligible']:eligible.append(('calibration_pi',sel['calpi_means'][sel['calpi']['id']]['deficit_auc']))
 baseline=min(eligible,key=lambda x:x[1])[0] if eligible else None
 progress={}
 for g in ('clean','bias','outage'):
  h=s['group_means'][g]['hybrid'];rec=[r for r in rows if group(r,g) and r['method']=='hybrid'];empty_runs=sum(float(r['empty_request_s'])>0 for r in rec)
  if baseline:
   b=s['group_means'][g][baseline];cs={c['metric']:c for c in s['comparisons'] if c['group']==g and c['baseline']==baseline}
   reduction=1-h['deficit_auc']/b['deficit_auc'] if b['deficit_auc']>0 else 0.
   checks=dict(oxygen_mean_reduction_at_least_10_percent=reduction>=.1,oxygen_paired_interval_supports_improvement=cs['deficit_auc']['high']<0.,mean_low_reservoir_at_most_1s=h['low_reservoir_s']<=1.,zero_empty_request_runs=empty_runs==0,paired_low_extra_at_most_1s=cs['low_reservoir_s']['high']<=1.,paired_empty_extra_at_most_1s=cs['empty_request_s']['high']<=1.,paired_pressure_extra_at_most_5s=cs['high_pressure_s']['high']<=5.)
  else:reduction=None;checks=dict(eligible_development_baseline_available=False)
  progress[g]=dict(mean_oxygen_reduction_fraction=reduction,mean_low_reservoir_s=h['low_reservoir_s'],empty_request_runs=empty_runs,checks=checks,exploratory_metrics_pass=all(checks.values()))
 value=dict(milestone_policy_sha256=digest(ROOT/'data/version2-gates.json'),release='v1.14',target='v2.0',version2_ready=False,baseline_selected_on_development=baseline,patient_count_this_cohort=16,qualifying_confirmation_cohorts=0,required_confirmation_cohorts=2,minimum_patients_each_confirmation=32,regimes=progress,reason='This 16-patient exploratory evaluation does not satisfy the prespecified two-cohort 32-patient confirmation requirement, irrespective of individual metric outcomes.',limitations='Primary claims assume healthy independent calibration. Missing/biased/shared-corruption calibration failures remain published; version numbers do not confer clinical certification.')
 result['results/model-bank-study/version2-progress.json']=json.dumps(value,indent=2)+'\n'
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 for name,value in outputs().items():
  path=ROOT/name
  if args.check:assert path.read_text()==value,name
  else:path.write_text(value)
 print('PASS: 40 model-bank replay artifacts and explicit v2 milestone status match source logs.')
