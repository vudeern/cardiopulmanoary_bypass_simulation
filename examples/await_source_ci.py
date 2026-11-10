"""Wait for the complete same-commit Verify simulation workflow before release."""
import json
import os
import subprocess
import time

repo=os.environ['GH_REPO'];sha=os.environ['GITHUB_SHA']
assert repo=='vudeern/cardiopulmanoary_bypass_simulation'
for _ in range(90):
    data=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs?head_sha={sha}&per_page=50'],text=True))
    runs=[r for r in data['workflow_runs'] if r['name']=='Verify simulation' and r['head_sha']==sha]
    if any(r['status']=='completed' and r['conclusion']=='success' for r in runs):
        print('Full same-commit CI passed');break
    if any(r['status']=='completed' and r['conclusion'] not in ('success','cancelled') for r in runs):
        raise SystemExit('Source CI failed; release is blocked')
    time.sleep(10)
else:raise SystemExit('Timed out waiting for source CI; release is blocked')
