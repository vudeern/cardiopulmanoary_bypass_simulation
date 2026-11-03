"""Display all tuning candidates and final outcomes without hiding failures."""
import json
from pathlib import Path
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'results/figures').mkdir(parents=True,exist_ok=True)
OUT=ROOT/'results/conservative-comparison'
p=json.loads((OUT/'protocol.json').read_text())
selection=json.loads((OUT/'selection.json').read_text())
s=json.loads((OUT/'summary.json').read_text())
colors=dict(original='#82949b', guarded='#35835a', reserve='#bd7e34', flow_cap='#7562a2')
markers=dict(original='s', guarded='*', reserve='o', flow_cap='^')
def label(v):
    if v['family']=='reserve':return f"Reserve +{v['options']['reserve_margin']:.2f} L"
    if v['family']=='flow_cap':return f"Cap {v['options']['flow_cap_index']:.1f} L/min/m²"
    return 'Guarded' if v['family']=='guarded' else 'Original'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
                     'svg.hashsalt':'perfusion-conservative-v1.2'})
fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
for family in ('original','guarded','reserve','flow_cap'):
    group=[v for v in p['candidates'] if v['family']==family]
    a=[selection['candidate_means'][v['id']] for v in group]
    axes[0].scatter([r['low_reservoir_s'] for r in a],[r['deficit_auc'] for r in a],
        color=colors[family],marker=markers[family],s=90 if family=='guarded' else 35,
        label=family.replace('_',' '),alpha=.8)
axes[0].set_title('Tuning: all 31 candidate settings',loc='left',fontweight='bold')
axes[0].legend(fontsize=8)
for v in s['selected']:
    m=s['pooled_means'][v['id']]
    axes[1].scatter(m['low_reservoir_s'],m['deficit_auc'],color=colors[v['family']],
                    marker=markers[v['family']],s=90 if v['id']=='guarded' else 45)
    axes[1].annotate(label(v),(m['low_reservoir_s'],m['deficit_auc']),
                     xytext=(8,5),textcoords='offset points',fontsize=8)
axes[1].set_title('Final evaluation: settings locked on tuning',loc='left',fontweight='bold')
for ax in axes:
    ax.set_xlabel('Mean time below reservoir floor (s)')
    ax.set_ylabel('Mean oxygen-delivery deficit AUC (mL O₂/m²)')
    ax.grid(alpha=.15);ax.set_axisbelow(True)
    ax.set_xlim(-1,max(20,ax.get_xlim()[1])*1.35)
    ax.set_ylim(bottom=0)
fig.suptitle('Does detecting a fault beat always being conservative?\n'
             'Equal weight for seven synthetic scenarios; lower on both axes is preferable',fontsize=12)
fig.savefig(ROOT/'results/figures/conservative-frontier.svg',metadata={'Date':None});plt.close(fig)
cells=s['map'];biases=p['level_bias_L'];drains=p['drainage']
limit=max(1,max(c['means'][v['id']]['low_reservoir_s'] for c in cells for v in s['selected']))
fig,axes=plt.subplots(2,2,figsize=(10,8),layout='constrained')
for ax,v in zip(axes.flat,s['selected']):
    values=np.array([[next(c for c in cells if c['level_bias_L']==b and
        c['drainage']==d)['means'][v['id']]['low_reservoir_s'] for d in drains] for b in biases])
    image=ax.imshow(values,origin='lower',aspect='auto',cmap='YlOrRd',vmin=0,vmax=limit)
    ax.set_xticks(range(7),[f'{d:.2f}' for d in drains],rotation=45)
    ax.set_yticks(range(7),[f'{b:.1f}' for b in biases])
    ax.set_xlabel('Drainage multiplier');ax.set_ylabel('Level-sensor bias (L)')
    ax.set_title(label(v),fontweight='bold')
    fig.colorbar(image,ax=ax,label='Seconds below 0.25 L',shrink=.85)
fig.suptitle('No strategy eliminates the complete fault grid\n'
             '49 cells × four paired virtual patients · fresh seeds 7000–7003',fontsize=12)
fig.savefig(ROOT/'results/figures/conservative-map.svg',metadata={'Date':None});plt.close(fig)
for name in ('conservative-frontier.svg','conservative-map.svg'):
    shutil.copyfile(ROOT/'docs'/name,ROOT/'web'/name)
print('Wrote complete tuning/evaluation frontier and four-strategy stress map.')
