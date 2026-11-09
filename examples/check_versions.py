"""Check version history; prereleases cannot claim completed v2 evidence."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
project = (ROOT/'pyproject.toml').read_text()
match = re.search(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)(?:rc(\d+))?"', project, re.M)
assert match, 'Unsupported version format'
major, minor, patch = map(int, match.groups()[:3])
rc = match.group(4)
label = f'v{major}.{minor}'+(f'-rc.{rc}' if rc else '')
readme = (ROOT/'README.md').read_text()
assert len(re.findall(r'^\| v\d+\.\d+(?:-rc\.\d+)? \(current\) \|',readme,re.M)) == 1
assert f'| {label} (current) |' in readme
assert re.search(r'^#{2,3} '+re.escape(label)+r' .*\(current\)',readme,re.M)
labels = set(re.findall(r'^\| (v\d+\.\d+(?:-rc\.\d+)?)(?: \(current\))? \|',readme,re.M))
# Preserve every v1 iteration even after the v2 development line starts.
for i in range(15 if major >= 2 else minor+1): assert f'v1.{i}' in labels
policy = json.loads((ROOT/'data/version2-gates.json').read_text())
assert policy['target_version'] == '2.0.0'
assert policy['confirmation']['distinct_fresh_cohorts_min'] >= 2
assert policy['confirmation']['virtual_patients_min_per_cohort'] >= 32
if major >= 2:
    roadmap = json.loads((ROOT/'data/version2-roadmap.json').read_text())
    assert roadmap['final_v1_commit'] == 'ace6a9fed2f9084b5fda95e9e1113af7a3d93dca'
    assert roadmap['current_version'] == match.group(0).split('"')[1]
    assert roadmap['next_stable_version'] == '2.0.0'
    if rc:
        assert not roadmap['version2_ready'], 'Prerelease must not claim the stable milestone'
    else:
        evidence_path = ROOT/'results/version2-confirmation/summary.json'
        assert evidence_path.exists(), 'Stable v2 needs recorded confirmation evidence'
        evidence = json.loads(evidence_path.read_text())
        assert evidence['version2_ready'] and evidence['qualifying_confirmation_cohorts'] >= 2
        assert evidence['all_primary_regimes_pass'] and evidence['two_python_versions_pass']
print(f'PASS: {label} history retained; stable v2 requires confirmation evidence.')
