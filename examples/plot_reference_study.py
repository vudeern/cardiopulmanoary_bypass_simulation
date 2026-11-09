"""Show both outcomes for every reference regime and all final sensor cells."""
import json
from pathlib import Path
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'results/figures').mkdir(parents=True,exist_ok=True);OUT=ROOT/'results/reference-study'
p=json.loads((OUT/'protocol.json').read_text());s=json.loads((OUT/'summary.json').read_text())
ids=[v['id'] for v in s['methods']]
names=['Original','Fixed reserve','Old step guard','Simple reference','Age-based bound']
colors=['#82949b','#bd7e34','#7562a2','#3a9aab','#35835a']
groups=list(p['references']);x=np.arange(len(groups))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.hashsalt':'perfusion-reference-v1.4'})
fig,axes=plt.subplots(1,2,figsize=(14,5.3),layout='constrained')
for ax,metric,title,unit in zip(axes,['low_reservoir_s','deficit_auc'],
    ['Reservoir exposure','Oxygen-delivery deficit'],['Mean seconds below 0.25 L','Mean deficit AUC (mL O₂/m²)']):
    for i,(vid,name,color) in enumerate(zip(ids,names,colors)):
        values=[s['group_means'][g][vid][metric] for g in groups]
        ax.bar(x+(i-2)*.15,values,width=.145,color=color,label=name)
    ax.set_xticks(x,[g.replace('_',' ') for g in groups],rotation=20)
    ax.set_title(title,loc='left',fontweight='bold');ax.set_ylabel(unit)
    ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='outside lower center',ncol=5,frameon=False,fontsize=8)
fig.suptitle('Does measurement credibility add value beyond simple correction?\n'
             'Good reference is the primary test; other regimes challenge its assumptions',fontsize=12)
fig.savefig(ROOT/'results/figures/reference-results.svg',metadata={'Date':None});plt.close(fig)
sensors=list(p['final_sensors']);plants=list(p['final_plants'])
matrices=[]
for group in groups:
    matrices.append(np.array([[s['cell_means'][a+'__'+b+'__'+group]['bounded_reference']['low_reservoir_s']-
        s['cell_means'][a+'__'+b+'__'+group]['simple_reference']['low_reservoir_s']
        for b in plants] for a in sensors]))
limit=max(1,max(float(np.abs(m).max()) for m in matrices))
fig,axes=plt.subplots(2,3,figsize=(12,8),layout='constrained')
for ax,group,values in zip(axes.flat,groups,matrices):
    image=ax.imshow(values,aspect='auto',cmap='RdBu_r',vmin=-limit,vmax=limit)
    ax.set_xticks(range(3),plants,rotation=20)
    ax.set_yticks(range(len(sensors)),[v.replace('_',' ') for v in sensors])
    ax.set_title(group.replace('_',' ')+' reference',fontweight='bold')
    fig.colorbar(image,ax=ax,label='Mean exposure difference (s)',shrink=.8)
fig.suptitle('Age-based bound − simple reference: all 126 final cells\n'
             'Blue favors age-based protection; red favors simple correction',fontsize=12)
fig.savefig(ROOT/'results/figures/reference-cells.svg',metadata={'Date':None});plt.close(fig)
for name in ('reference-results.svg','reference-cells.svg'):
    shutil.copyfile(ROOT/'docs'/name,ROOT/'web'/name)
print('Plotted every reference regime and all 126 final cells.')
