"""Publish verified v1.15 assets, then remove only the explicitly superseded release.

Runs in GitHub Actions with the standard repository token. No token is logged.
Never moves an existing release tag or deletes historical tags/source commits.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def gh(*args):return subprocess.check_output(['gh',*args],text=True)


def main():
    assets=Path(sys.argv[1]).resolve();repo=os.environ['GH_REPO']
    if repo!='vudeern/cardiopulmanoary_bypass_simulation':raise ValueError('Unexpected repository')
    manifest=json.loads((assets/'release-manifest.json').read_text());sha=manifest['source_commit']
    if manifest['version']!='1.15.0':raise ValueError('Unexpected version')
    tag='v1.15.0';expected={p.name for p in assets.iterdir()}
    assert len(expected)==7 and 'SHA256SUMS' in expected
    try:reference=json.loads(gh('api',f'repos/{repo}/git/ref/tags/{tag}'))
    except subprocess.CalledProcessError:
        reference=json.loads(gh('api','--method','POST',f'repos/{repo}/git/refs','-f',f'ref=refs/tags/{tag}','-f',f'sha={sha}'))
    obj=reference['object']
    if obj['type']=='tag':obj=json.loads(gh('api',f"repos/{repo}/git/tags/{obj['sha']}"))['object']
    assert obj['sha']==sha,'Refuse to move an existing tag'
    release=None
    try:release=json.loads(gh('api',f'repos/{repo}/releases/tags/{tag}'))
    except subprocess.CalledProcessError:pass
    if release is None:
        gh('release','create',tag,'--repo',repo,'--target',sha,'--draft','--title','v1.15.0 — Complete final v1 research snapshot',
            '--notes-file','releases/v1.15-notes.md',*[str(p) for p in sorted(assets.iterdir())])
        release=json.loads(gh('api',f'repos/{repo}/releases/tags/{tag}'))
    assert {a['name'] for a in release['assets']}==expected,'Incomplete replacement assets'
    with tempfile.TemporaryDirectory() as d:
        gh('release','download',tag,'--repo',repo,'--dir',d)
        folder=Path(d);downloaded=json.loads((folder/'release-manifest.json').read_text())
        assert downloaded['source_commit']==sha,'Refuse to overwrite a release from another commit'
        for line in (folder/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1);assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest
    gh('release','edit',tag,'--repo',repo,'--draft=false','--latest')
    verified=json.loads(gh('api',f'repos/{repo}/releases/tags/{tag}'))
    assert not verified['draft'] and len(verified['assets'])==7
    # The user explicitly asked to delete this release listing, not its tag.
    try:old=json.loads(gh('api',f'repos/{repo}/releases/tags/v1.14.0'))
    except subprocess.CalledProcessError:old=None
    if old is not None:
        assert old['id']==433112360 and old['tag_name']=='v1.14.0','Unexpected old release; stop deletion'
        gh('api','--method','DELETE',f"repos/{repo}/releases/{old['id']}")
    gh('api','--method','PATCH',f'repos/{repo}/git/refs/heads/release/v1','-f',f'sha={sha}','-F','force=false')
    print('Verified v1.15.0 published; superseded v1.14.0 release removed; historical tag preserved.')


if __name__=='__main__':main()
