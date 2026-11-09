"""Plot every guard stress-map cell; retain failures and a common color scale."""
import json
from pathlib import Path
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT/'results/level-guard/summary.json').read_text())
cells = summary['map']
biases = sorted({c['level_bias_L'] for c in cells})
drains = sorted({c['drainage'] for c in cells})
matrices = []
for policy in ('sentinel', 'sentinel_guarded'):
    matrices.append(np.array([[next(c for c in cells if c['level_bias_L']==b and
        c['drainage']==d)['means'][policy]['low_reservoir_s'] for d in drains] for b in biases]))
a, b = matrices
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':9,
                     'svg.hashsalt':'perfusion-level-guard-v1.1'})
fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.8), layout='constrained')
for ax, matrix, title in zip(axes, [a, b, b-a],
        ['Original Sentinel', 'Guarded Sentinel', 'Guarded − original']):
    difference = '−' in title
    limit = max(1., float(np.abs(b-a).max()))
    image = ax.imshow(matrix, origin='lower', aspect='auto',
        cmap='RdBu_r' if difference else 'YlOrRd',
        vmin=-limit if difference else 0,
        vmax=limit if difference else max(1., float(a.max()), float(b.max())))
    ax.set_xticks(range(len(drains)), [f'{d:.2f}' for d in drains], rotation=45)
    ax.set_yticks(range(len(biases)), [f'{v:.1f}' for v in biases])
    ax.set_xlabel('Drainage multiplier')
    ax.set_ylabel('Positive level-sensor bias (L)')
    ax.set_title(title, fontweight='bold')
    fig.colorbar(image, ax=ax, label='Seconds below 0.25 L', shrink=.8)
fig.suptitle('A step-fault guard reduces depletion, but small offsets can escape\n'
             '49 fault cells × 4 paired virtual patients · fresh seeds 1500–1503', fontsize=12)
fig.savefig(ROOT/'results/figures/level-guard.svg', metadata={'Date':None})
plt.close(fig)
shutil.copyfile(ROOT/'results/figures/level-guard.svg', ROOT/'web/level-guard.svg')
print('Wrote guard stress map to results/figures and replay.')
