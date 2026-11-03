"""Build frozen v1 assets without changing its source or publishing anything."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    manifest = json.loads((ROOT/'releases/v1.14.0.json').read_text())
    if source == out or source in out.parents:
        raise ValueError('Output must be outside the frozen source')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use an empty output directory')
    # Source checksums were published with v1.14. Verify before building.
    expected_checksums = hashlib.sha256((source/'SHA256SUMS').read_bytes()).hexdigest()
    if expected_checksums != manifest['source_checksums_sha256']:
        raise ValueError('This is not the frozen v1.14 checksum manifest')
    files = []
    for line in (source/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = source/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen source mismatch: {name}')
        files.append(name)
    files.append('SHA256SUMS')
    if (source/'.git').exists():
        head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=source, text=True).strip()
        if head != manifest['commit']: raise ValueError('Wrong frozen commit')
        subprocess.run(['git','diff','--exit-code','HEAD'], cwd=source, check=True, capture_output=True)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        build_source = Path(temp)/'source'
        for name in files:
            target = build_source/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source/name, target)
        subprocess.run([sys.executable, '-c',
            'import setuptools.build_meta as b; b.build_sdist('+repr(str(out))+'); b.build_wheel('+repr(str(out))+')'],
            cwd=build_source, check=True, stdout=subprocess.DEVNULL)
    with zipfile.ZipFile(out/'perfusion-sentinel-v1.14.0-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            entry = zipfile.ZipInfo('perfusion-sentinel-v1.14.0/'+name, date_time=(1980,1,1,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, (source/name).read_bytes())
    shutil.copyfile(ROOT/'releases/v1-reproduction.txt',out/'REPRODUCE-v1.txt')
    shutil.copyfile(ROOT/'releases/v1-example.json',out/'example-config.json')
    info = dict(manifest, python=sys.version, source_file_count=len(files),
                package_scope='Wheel/sdist: Python software. Full source ZIP: all frozen code, data, results, tests and viewer assets.')
    (out/'release-manifest.json').write_text(json.dumps(info,indent=2)+'\n')
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()))
    (out/'SHA256SUMS').write_text(sums)
    print(f'Built {len(list(out.iterdir()))} v1 assets from {manifest["commit"]}; source unchanged.')


if __name__ == '__main__': main()
