"""Build a deterministic, auditable source ZIP without caches or raw replay logs."""
import hashlib
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'perfusion-sentinel-v1.9.0.zip'
EXCLUDED={'.git','.venv','__pycache__','build','dist'}


def release_files():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(part in EXCLUDED or part.endswith('.egg-info') for part in p.relative_to(ROOT).parts):
            continue
        if p.name in {'CHECKPOINT.md','SHA256SUMS'} or p.relative_to(ROOT).as_posix()=='results/trajectories.json':
            continue
        if p.suffix in {'.pyc','.pyo','.zip'}:
            continue
        yield p


def main():
    paths=list(release_files())
    (ROOT/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in paths))
    paths.append(ROOT/'SHA256SUMS')
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in paths:
            info=zipfile.ZipInfo('perfusion-sentinel-v1.9.0/'+p.relative_to(ROOT).as_posix(),date_time=(2026,10,30,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,p.read_bytes())
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
    print(f'{OUTPUT}: {len(paths)} files, {OUTPUT.stat().st_size:,} bytes')

if __name__=='__main__':
    main()

