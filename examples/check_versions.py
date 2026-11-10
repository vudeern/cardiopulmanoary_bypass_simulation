"""Validate the user-rebased v1 closure and distinct v2 recovery line."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
project=(ROOT/'pyproject.toml').read_text()
version=re.search(r'^version\s*=\s*"([^"]+)"',project,re.M).group(1)
lineage=json.loads((ROOT/'data/version-lineage.json').read_text())
assert version==lineage['current_version']
assert lineage['final_v1_version']=='1.15.0' and lineage['final_v1_tag']=='v1.15.0'
readme=(ROOT/'README.md').read_text()
for i in range(16):assert f'| v1.{i}' in readme
assert 'universal MPC impossibility is not established' in lineage['claim_rule']
policy=json.loads((ROOT/'data/version2-gates.json').read_text())
assert policy['target_version']=='2.0.0'
assert policy['confirmation']['distinct_fresh_cohorts_min']>=2
assert policy['confirmation']['virtual_patients_min_per_cohort']>=32
if version.startswith('1.'):
    assert version=='1.15.0' and lineage['current_line']=='v1'
else:
    assert version.startswith('2.') and lineage['current_line']=='v2'
    assert 'recovery' in readme.lower()
    if 'rc' not in version:
        path=ROOT/'results/version2-confirmation/summary.json'
        assert path.exists(),'Stable v2 requires full confirmation evidence'
        evidence=json.loads(path.read_text())
        assert evidence['version2_ready'] and evidence['qualifying_confirmation_cohorts']>=2
        assert evidence['all_primary_regimes_pass'] and evidence['two_python_versions_pass']
print(f'PASS: {version}; final v1 lineage and honest claim scope retained; stable v2 remains evidence-gated.')
