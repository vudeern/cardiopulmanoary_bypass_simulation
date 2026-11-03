"""Publish the user-requested frozen release from a trusted GitHub Actions job.

The GitHub connector cannot create releases or upload binary assets. This script
uses the job's repository-scoped token; it never prints or stores that token.
Existing published releases and tags are checked and never overwritten.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def gh(*args):
    result = subprocess.run(['gh', *args], text=True, capture_output=True)
    if result.returncode: raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    repo = os.environ['GH_REPO']
    manifest = json.loads((ROOT/'releases/v1.14.0.json').read_text())
    releases = gh('api', f'repos/{repo}/releases?per_page=100')
    existing = next((r for r in releases if r['tag_name'] == manifest['tag']), None)
    if existing is not None:
        ref = gh('api', f'repos/{repo}/git/ref/tags/{manifest["tag"]}')
        assert ref['object']['type'] == 'commit' and ref['object']['sha'] == manifest['commit'], 'Existing release points to another commit'
        assert not existing['draft'], 'Existing draft needs explicit review'
        expected = {'SHA256SUMS','release-manifest.json','REPRODUCE-v1.txt','example-config.json',
                    'perfusion-sentinel-v1.14.0-source.zip'}
        names = {a['name'] for a in existing['assets']}
        assert expected <= names and any(n.endswith('.whl') for n in names) and any(n.endswith('.tar.gz') for n in names), 'Published release is incomplete; refusing to overwrite'
    if args.check:
        print('exists='+str(existing is not None).lower())
        return
    if existing is not None:
        print('Frozen release already exists; no changes.')
        return
    if args.assets is None: raise ValueError('Asset directory required')
    assets = args.assets.resolve()
    sums = (assets/'SHA256SUMS').read_text().splitlines()
    import hashlib
    for line in sums:
        digest, name = line.split('  ',1)
        assert hashlib.sha256((assets/name).read_bytes()).hexdigest() == digest, name
    # gh creates the tag at the pinned commit only if it does not exist.
    # A conflicting pre-existing tag is rejected before publication.
    refs = gh('api', f'repos/{repo}/git/matching-refs/tags/{manifest["tag"]}')
    for ref in refs:
        if ref['ref'] == 'refs/tags/'+manifest['tag']:
            assert ref['object']['type'] == 'commit' and ref['object']['sha'] == manifest['commit'], 'Conflicting tag'
    notes = ROOT/'releases/v1-release-notes.txt'
    result = subprocess.run(['gh','release','create',manifest['tag'],
        '--repo',repo,'--target',manifest['commit'],'--title','v1.14.0 — Final v1 research snapshot',
        '--notes-file',str(notes),*[str(p) for p in sorted(assets.iterdir())]], capture_output=True,text=True)
    if result.returncode: raise RuntimeError(result.stderr.strip())
    print(result.stdout.strip())


if __name__ == '__main__': main()
