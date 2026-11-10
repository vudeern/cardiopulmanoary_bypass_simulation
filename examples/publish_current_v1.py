"""Verify final-v1 assets, publish the release, then retire its predecessor."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile


def gh(*args):return subprocess.check_output(['gh',*args],text=True)


def main():
    repo=os.environ['GH_REPO'];assert repo=='vudeern/cardiopulmanoary_bypass_simulation'
    tag='v1.15.0';finalize=sys.argv[1]=='--finalize-existing'
    assets=None if finalize else Path(sys.argv[1]).resolve()
    matches=[r for r in json.loads(gh('api',f'repos/{repo}/releases?per_page=100')) if r['tag_name']==tag]
    assert len(matches)<=1,'Ambiguous release listings'
    release=matches[0] if matches else None
    if release is None:
        assert not finalize,'Expected draft is missing'
        manifest=json.loads((assets/'release-manifest.json').read_text());sha=manifest['source_commit']
        assert manifest['version']=='1.15.0'
        try:reference=json.loads(gh('api',f'repos/{repo}/git/ref/tags/{tag}'))
        except subprocess.CalledProcessError:
            reference=json.loads(gh('api','--method','POST',f'repos/{repo}/git/refs','-f',f'ref=refs/tags/{tag}','-f',f'sha={sha}'))
        assert reference['object']['sha']==sha,'Refuse to move a tag'
        gh('release','create',tag,'--repo',repo,'--target',sha,'--draft','--title','v1.15.0 — Complete final v1 research snapshot',
            '--notes-file','releases/v1.15-notes.md',*[str(p) for p in sorted(assets.iterdir())])
        matches=[r for r in json.loads(gh('api',f'repos/{repo}/releases?per_page=100')) if r['tag_name']==tag]
        assert len(matches)==1;release=matches[0]
    expected={'example-config.json','perfusion-sentinel-v1.15.0-source.zip','perfusion_sentinel-1.15.0-py3-none-any.whl',
        'perfusion_sentinel-1.15.0.tar.gz','release-manifest.json','REPRODUCE-v1.txt','SHA256SUMS'}
    assert {a['name'] for a in release['assets']}==expected
    reference=json.loads(gh('api',f'repos/{repo}/git/ref/tags/{tag}'));obj=reference['object']
    if obj['type']=='tag':obj=json.loads(gh('api',f"repos/{repo}/git/tags/{obj['sha']}"))['object']
    sha=obj['sha'];assert re.fullmatch('[0-9a-f]{40}',sha)
    source_runs=json.loads(gh('api',f'repos/{repo}/actions/runs?head_sha={sha}&per_page=100'))['workflow_runs']
    assert any(r['name']=='Verify simulation' and r['head_sha']==sha and r['conclusion']=='success' for r in source_runs),'Frozen source CI is not verified'
    with tempfile.TemporaryDirectory() as d:
        folder=Path(d)
        for asset in release['assets']:
            with (folder/asset['name']).open('wb') as stream:
                subprocess.run(['gh','api',f"repos/{repo}/releases/assets/{asset['id']}",'-H','Accept: application/octet-stream'],stdout=stream,check=True)
        manifest=json.loads((folder/'release-manifest.json').read_text())
        assert manifest['source_commit']==sha and manifest['version']=='1.15.0'
        for line in (folder/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1);assert name in expected
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest
        with zipfile.ZipFile(folder/'perfusion-sentinel-v1.15.0-source.zip') as z:
            assert z.testzip() is None
            assert len(z.namelist())==manifest['source_file_count']+1
            for name,digest in manifest['source_sha256'].items():
                assert hashlib.sha256(z.read('perfusion-sentinel-v1.15.0/'+name)).hexdigest()==digest
    gh('api','--method','PATCH',f"repos/{repo}/releases/{release['id']}",'-F','draft=false','-f','make_latest=true')
    verified=json.loads(gh('api',f"repos/{repo}/releases/{release['id']}"));assert not verified['draft'] and len(verified['assets'])==7
    old=[r for r in json.loads(gh('api',f'repos/{repo}/releases?per_page=100')) if r['tag_name']=='v1.14.0']
    if old:
        assert len(old)==1 and old[0]['id']==433112360
        gh('api','--method','DELETE',f"repos/{repo}/releases/{old[0]['id']}")
    gh('api','--method','PATCH',f'repos/{repo}/git/refs/heads/release/v1','-f',f'sha={sha}','-F','force=false')
    print('Verified complete v1.15.0 assets published; old release listing deleted; historical tag preserved.')


if __name__=='__main__':main()
