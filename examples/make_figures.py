"""Publication-style static figures made from the actual benchmark, not artwork."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((ROOT/'results/metrics.csv').open()))
summary=json.loads((ROOT/'results/summary.json').read_text())
policies=['fixed','reactive','sentinel','no_calibration','no_lookahead']
colors=['#82949b','#65a7b0','#3f996c','#d59c51','#9e79b8']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.hashsalt':'perfusion-sentinel'})
fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
for ax,metric,title,ylabel in zip(axes,['deficit_auc','low_reservoir_s'],
                                ['Compound disturbance: oxygen delivery','Compound disturbance: reservoir'],
                                ['Delivery deficit AUC (mL O₂/m²)','Time below 0.25 L (s)']):
    values=[[float(r[metric]) for r in rows if r['scenario']=='compound' and r['policy']==p] for p in policies]
    for i,(v,c) in enumerate(zip(values,colors)):
        ax.bar(i,np.mean(v),color=c,width=.65)
        # Individual patient points expose variation hidden by an average.
        ax.scatter(np.linspace(i-.2,i+.2,len(v)),v,s=9,color='black',alpha=.35)
    ax.set_xticks(range(5),['Fixed','Reactive','Sentinel','No Hb\ncalibration','No reservoir\nforecast'])
    ax.set_ylabel(ylabel);ax.set_title(title,loc='left',fontweight='bold');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.suptitle('Perfusion Sentinel | 24 synthetic patients, seeds 100–123',fontweight='bold')
fig.savefig(ROOT/'docs/benchmark.svg',metadata={'Date':None});plt.close(fig)
fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
cc=[c for c in summary['comparisons'] if c['policy']=='sentinel' and c['metric']=='deficit_auc']
x=np.arange(len(cc)); y=np.array([c['mean'] for c in cc])
ax.errorbar(x,y,yerr=[y-np.array([c['low'] for c in cc]),np.array([c['high'] for c in cc])-y],fmt='o',color='#3f996c',capsize=4)
ax.axhline(0,color='gray',ls='--');ax.set_xticks(x,[c['scenario'].replace('_','\n') for c in cc],fontsize=8)
ax.set_ylabel('Sentinel − reactive deficit AUC (mL O₂/m²)')
ax.set_title('Paired effects across all seven scenarios',loc='left',fontweight='bold')
fig.savefig(ROOT/'docs/paired-effects.svg',metadata={'Date':None});plt.close(fig)
# Machine-derived Markdown ensures the README/results report cannot invent wins.
metrics=['deficit_auc','low_reservoir_s','false_reassurance_s','mean_flow','hb_bound_coverage']
lines=['# Recorded benchmark results','',
       '24 synthetic patients, seeds 100–123; 20 minutes/run; dt = 2 s; target = 280 mL/min/m². These are simulation outputs, not measured patient outcomes.','',
       '| Scenario | Policy | Deficit AUC (mL/m²) | Low reservoir (s) | False reassurance (s) | Mean flow (L/min) | Hb bound coverage |',
       '|---|---|---:|---:|---:|---:|---:|']
for scenario in dict.fromkeys(r['scenario'] for r in rows):
    for policy in policies:
        selected=[r for r in rows if r['scenario']==scenario and r['policy']==policy]
        means=[np.mean([float(r[k]) for r in selected]) for k in metrics]
        lines.append('| '+scenario+' | '+policy+' | '+' | '.join(f'{v:.2f}' for v in means)+' |')
lines+=['','## Sentinel versus reactive, paired differences','',
        'Negative deficit AUC differences favor Sentinel. Intervals are 95% percentile bootstrap intervals over virtual-patient pairs, with 2,000 resamples and seed 2026. No multiplicity correction is applied.','',
        '| Scenario | Mean difference | Bootstrap interval |','|---|---:|---:|']
for c in cc:
    lines.append(f"| {c['scenario']} | {c['mean']:.2f} | [{c['low']:.2f}, {c['high']:.2f}] |")
lines+=['','## Interpret the failures', '',
'Compound disturbance: calibration reduces delivery deficits in this model; reservoir look-ahead trades a larger delivery deficit for less time below the reservoir floor. This is a tradeoff, not universal dominance.', '',
'Unmodeled level bias: Sentinel averages more low-reservoir time and more empty-reservoir requests than reactive despite its better oxygen-delivery metric. An apparently favorable oxygen score can conceal another failure. This invalidates a global safety claim.', '',
'Hb bounds are not calibrated intervals: empirical coverage falls during bias and compound faults. False reassurance remains substantial after correction because inline monitoring itself remains biased and the reference is intermittent.', '',
'Fixed flow has zero nominal deficit in this sampler but uses more average flow than reactive. The benchmark does not measure hemolysis, neurological injury, renal injury, clinical workload, or clinical benefit.']
(ROOT/'docs/RESULTS.md').write_text('\n'.join(lines)+'\n')
print('Wrote figures and complete result tables.')
