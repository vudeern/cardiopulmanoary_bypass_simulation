"""Keep README version labels and the user-defined v2 milestone consistent."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
project=(ROOT/'pyproject.toml').read_text();version=re.search(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"',project,re.M).groups();major,minor,patch=map(int,version)
readme=(ROOT/'README.md').read_text();label=f'v{major}.{minor}'
assert len(re.findall(r'^\| v\d+\.\d+ \(current\) \|',readme,re.M))==1
assert f'| {label} (current) |' in readme
assert re.search(r'^## '+re.escape(label)+r' .*\(current\)',readme,re.M)
labels=set(re.findall(r'^\| (v\d+\.\d+)(?: \(current\))? \|',readme,re.M))
for i in range(minor+1):assert f'v{major}.{i}' in labels
policy=json.loads((ROOT/'data/version2-gates.json').read_text())
assert policy['target_version']=='2.0.0' and policy['confirmation']['distinct_fresh_cohorts_min']>=2 and policy['confirmation']['virtual_patients_min_per_cohort']>=32
if major>=2:
 progress=json.loads((ROOT/'results/model-bank-study/version2-progress.json').read_text())
 assert progress['version2_ready'] and progress['qualifying_confirmation_cohorts']>=2,'v2 needs recorded confirmation evidence'
print(f'PASS: README history/current section match {label}; v2 remains an explicit evidence milestone.')
