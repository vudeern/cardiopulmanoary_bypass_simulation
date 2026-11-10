"""Build the complete git-tracked final v1 snapshot and pinned release assets."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    out=Path(sys.argv[1]).resolve()
    if ROOT==out or ROOT in out.parents:raise ValueError('Assets must be outside source')
    if out.exists() and any(out.iterdir()):raise ValueError('Use an empty asset directory')
    assert 'version = "1.15.0"' in (ROOT/'pyproject.toml').read_text()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    subprocess.run(['git','diff','--exit-code','HEAD'],cwd=ROOT,check=True,capture_output=True)
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')[:-1]
    checks={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    out.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-c','import setuptools.build_meta as b; b.build_sdist('+repr(str(out))+'); b.build_wheel('+repr(str(out))+')'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    archive=out/'perfusion-sentinel-v1.15.0-source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in paths:z.write(ROOT/p,'perfusion-sentinel-v1.15.0/'+p)
        z.writestr('perfusion-sentinel-v1.15.0/SOURCE_SHA256SUMS',''.join(v+'  '+p+'\n' for p,v in sorted(checks.items())))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    shutil.copyfile(ROOT/'releases/v1-example.json',out/'example-config.json')
    (out/'REPRODUCE-v1.txt').write_text('Final v1.15.0 source commit: '+sha+'\nUse the full source ZIP for study reproduction.\npython -m pip install -e ".[audit,horizon]"\npython -m unittest discover -s tests -v\npython examples/fixed_ceiling_bound.py\npython examples/validate_feedback.py\nHistorical execution IDs remain unchanged; see data/version-lineage.json and docs/V1_CONCLUSION.md.\nNo equipment is controlled.\n')
    manifest=dict(version='1.15.0',tag='v1.15.0',source_commit=sha,source_file_count=len(paths),
        source_sha256=checks,python=sys.version,simulation_only=True,universal_mpc_impossibility_proven=False,
        scope='Complete v1 research through the applied MPC pilot and conditional fixed-ceiling conclusion; original execution metadata retained.')
    (out/'release-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir())))
    print(f'Built {len(list(out.iterdir()))} assets from {sha}; {len(paths)} tracked files.')


if __name__=='__main__':main()
