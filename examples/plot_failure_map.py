"""Plot the failure surface from every recorded fault-map run."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((ROOT/'results/failure-map.csv').open()))
biases=sorted({float(r['level_bias_L']) for r in rows})
drains=sorted({float(r['drainage']) for r in rows})
summary=[]
a=np.zeros((len(biases),len(drains)));b=a.copy()
for i,bias in enumerate(biases):
    for j,drain in enumerate(drains):
        cell=[r for r in rows if float(r['level_bias_L'])==bias and float(r['drainage'])==drain]
        for policy,matrix in [('reactive',a),('sentinel',b)]:
            matrix[i,j]=np.mean([float(r['low_reservoir_s']) for r in cell if r['policy']==policy])
        summary.append(dict(level_bias_L=bias,drainage=drain,reactive_low_s=float(a[i,j]),
                            sentinel_low_s=float(b[i,j]),difference_s=float(b[i,j]-a[i,j])))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.hashsalt':'perfusion-sentinel'})
fig,axes=plt.subplots(1,3,figsize=(12.5,4.7),layout='constrained')
for ax,matrix,title in zip(axes,[a,b,b-a],['Reactive: time below floor','Sentinel: time below floor','Sentinel − reactive']):
    difference='−' in title
    lim=max(1,float(np.abs(b-a).max()))
    image=ax.imshow(matrix,origin='lower',aspect='auto',cmap='RdBu_r' if difference else 'YlOrRd',
                    vmin=-lim if difference else 0,vmax=lim if difference else max(a.max(),b.max(),1))
    ax.set_xticks(range(len(drains)),[f'{x:.2f}' for x in drains],rotation=45)
    ax.set_yticks(range(len(biases)),[f'{x:.1f}' for x in biases]);ax.set_xlabel('Drainage multiplier')
    ax.set_ylabel('Positive reservoir sensor bias (L)');ax.set_title(title,fontweight='bold')
    fig.colorbar(image,ax=ax,label='Seconds',shrink=.8)
fig.suptitle('An oxygen-delivery improvement can conceal a reservoir failure\n49 fault cells × 4 paired virtual patients; experimental floor 0.25 L',fontsize=12)
fig.savefig(ROOT/'docs/failure-map.svg',metadata={'Date':None});plt.close(fig)
(ROOT/'results/failure-map-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('Wrote failure-map figure and 49-cell summary.')
