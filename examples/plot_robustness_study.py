"""Plot all 45 stress cells, including failures and ambiguous alarm flags."""
import json
from pathlib import Path
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'results/figures').mkdir(parents=True,exist_ok=True)
OUT=ROOT/'results/robustness'
p=json.loads((OUT/'protocol.json').read_text())
s=json.loads((OUT/'summary.json').read_text())
sensors=list(p['sensor_cases']);plants=list(p['plant_cases'])
plant_labels=['Reference','Slow pump','Lag + nonlinear','Cap violated','Varied storage']
sensor_labels=[x.replace('_',' ') for x in sensors]
def matrix(vid,metric):
    return np.array([[s['cell_means'][a+'__'+b][vid][metric] for b in plants] for a in sensors])
def axes_labels(ax):
    ax.set_xticks(range(5),plant_labels,rotation=25,ha='right',fontsize=8)
    ax.set_yticks(range(9),sensor_labels,fontsize=8)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,
                     'svg.hashsalt':'perfusion-robustness-v1.3'})
fig,axes=plt.subplots(2,2,figsize=(11,9),layout='constrained')
names=['Original Sentinel','Guarded Sentinel','Reserve +0.40 L','Cap 2.4 L/min/m²']
maximum=max(float(matrix(v['id'],'low_reservoir_s').max()) for v in p['variants'])
for ax,v,name in zip(axes.flat,p['variants'],names):
    image=ax.imshow(matrix(v['id'],'low_reservoir_s'),aspect='auto',vmin=0,
                    vmax=max(1,maximum),cmap='YlOrRd')
    axes_labels(ax);ax.set_title(name,fontweight='bold')
    fig.colorbar(image,ax=ax,label='Mean seconds below 0.25 L',shrink=.85)
fig.suptitle('Frozen strategies under unfamiliar sensing and dynamics\n'
             'All 45 synthetic cells × 24 paired virtual patients; no retuning',fontsize=12)
fig.savefig(ROOT/'results/figures/robustness-exposure.svg',metadata={'Date':None});plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5.5),layout='constrained')
for ax,metric,title,unit in zip(axes,['low_reservoir_s','deficit_auc'],
        ['Reservoir exposure: guarded − reserve','Oxygen deficit: guarded − reserve'],
        ['Seconds','mL O₂/m²']):
    values=matrix('guarded',metric)-matrix('reserve_0.40',metric)
    limit=max(1,float(np.abs(values).max()))
    image=ax.imshow(values,aspect='auto',cmap='RdBu_r',vmin=-limit,vmax=limit)
    axes_labels(ax);ax.set_title(title,fontweight='bold')
    fig.colorbar(image,ax=ax,label=unit,shrink=.85)
fig.suptitle('Protection and oxygen delivery remain separate outcomes\n'
             'Blue favors guarded; red favors the locked fixed reserve',fontsize=12)
fig.savefig(ROOT/'results/figures/robustness-tradeoffs.svg',metadata={'Date':None});plt.close(fig)
fig,ax=plt.subplots(figsize=(8,5.5),layout='constrained')
values=matrix('guarded','level_alarm_ever')
image=ax.imshow(values,aspect='auto',vmin=0,vmax=1,cmap='YlOrRd')
axes_labels(ax)
ax.set_yticklabels([label+(' *' if sensor in ('clean','flow_high','flow_low','noisy') else '')
                    for sensor,label in zip(sensors,sensor_labels)])
for i in range(9):
    for j in range(5):
        ax.text(j,i,f'{values[i,j]:.0%}',ha='center',va='center',fontsize=8,
                color='white' if values[i,j]>.65 else 'black')
fig.colorbar(image,ax=ax,label='Fraction of runs with any level flag',shrink=.85)
ax.set_title('A level flag does not establish correct fault identification\n'
             '* No level fault injected; all other channels/physics may still differ',fontsize=11)
fig.savefig(ROOT/'results/figures/robustness-alarms.svg',metadata={'Date':None});plt.close(fig)
for name in ('robustness-exposure.svg','robustness-tradeoffs.svg','robustness-alarms.svg'):
    shutil.copyfile(ROOT/'docs'/name,ROOT/'web'/name)
print('Plotted all 45 cells, paired tradeoffs and alarm ambiguity.')
