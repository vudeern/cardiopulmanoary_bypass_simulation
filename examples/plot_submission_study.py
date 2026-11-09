"""Publication-draft figures showing the mechanism and all baseline outcomes."""
import json
import csv
from pathlib import Path
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'results/figures').mkdir(parents=True,exist_ok=True);OUT=ROOT/'results/submission-study'
s=json.loads((OUT/'summary.json').read_text());p=json.loads((OUT/'protocol.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.hashsalt':'perfusion-mechanism-v1.5'})
fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
bias=np.linspace(-.6,1.2,100)
for margin in (0.,.2,.4):axes[0].plot(bias,.25+margin-20.*bias/60.,label=f'Margin {margin:.1f} L')
axes[0].axhline(.25,color='black',ls='--',label='Experimental floor')
axes[0].axhline(0.,color='gray',lw=.8);axes[0].set_xlabel('Flow measurement bias (L/min)')
axes[0].set_ylabel('Reduced-model equilibrium (L)');axes[0].legend(fontsize=8)
axes[0].set_title('Correct level does not remove flow-bias transmission',loc='left',fontweight='bold',fontsize=10)
axes[0].text(.02,.03,'Negative equilibria are physically infeasible requests.',transform=axes[0].transAxes,fontsize=8)
good=s['group_means']['good'];colors=['#82949b','#35835a','#bd7e34']
for v,color in zip(s['methods'],colors):
    m=good[v['id']]
    axes[1].scatter(m['low_reservoir_s'],m['deficit_auc'],color=color,s=55)
    axes[1].annotate(v['family'],(m['low_reservoir_s'],m['deficit_auc']),xytext=(7,5),textcoords='offset points')
axes[1].set_xlabel('Mean seconds below reservoir floor');axes[1].set_ylabel('Mean deficit AUC (mL O₂/m²)')
axes[1].set_xlim(-.3,max(m['low_reservoir_s'] for m in good.values())*1.7)
axes[1].set_ylim(0,max(m['deficit_auc'] for m in good.values())*1.18);axes[1].set_title('Final good-reference comparison: no universal winner',loc='left',fontweight='bold',fontsize=10)
for ax in axes:ax.grid(alpha=.15);ax.set_axisbelow(True)
fig.savefig(ROOT/'results/figures/submission-mechanism.svg',metadata={'Date':None});plt.close(fig)
groups=list(p['references']);x=np.arange(len(groups))
fig,axes=plt.subplots(1,3,figsize=(14,4.6),layout='constrained')
for ax,metric,title in zip(axes,['low_reservoir_s','deficit_auc','high_pressure_s'],
    ['Reservoir exposure (s)','Oxygen deficit (mL O₂/m²)','Pressure exposure >95 mmHg (s)']):
    for i,(v,color) in enumerate(zip(s['methods'],colors)):
        ax.bar(x+(i-1)*.24,[s['group_means'][g][v['id']][metric] for g in groups],
               width=.23,color=color,label=v['family'])
    ax.set_xticks(x,groups,rotation=20);ax.set_title(title,fontsize=10,fontweight='bold')
    ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False)
fig.suptitle('All frozen stronger-baseline outcomes: protection, delivery and pressure remain distinct',fontsize=12)
fig.savefig(ROOT/'results/figures/submission-outcomes.svg',metadata={'Date':None});plt.close(fig)
for name in ('submission-mechanism.svg','submission-outcomes.svg'):
    shutil.copyfile(ROOT/'docs'/name,ROOT/'web'/name)
print('Plotted reduced-model mechanism and every reference-regime outcome.')
