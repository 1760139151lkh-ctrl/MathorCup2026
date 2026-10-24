#!/usr/bin/env python3
"""Inventory existing Python runtimes without installing or changing them.

AI assistance: Codex, OpenAI, 2026-10-23; exact model ID unavailable.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ['numpy', 'pandas', 'openpyxl', 'xarray', 'scipy', 'tifffile', 'h5py',
            'h5netcdf', 'netCDF4', 'rasterio', 'GDAL', 'shapely', 'pyproj', 'fiona',
            'geopandas', 'pypdf', 'python-docx']
PROBE = '''import json,sys,importlib.metadata as m
packages=json.loads(sys.argv[1]); result={}
for package in packages:
    try: result[package]=m.version(package)
    except m.PackageNotFoundError: result[package]=None
print(json.dumps({'executable':sys.executable,'python_version':sys.version,'packages':result}))
'''


def main():
    candidates = [shutil.which('python3'), '/usr/local/anaconda3/bin/python',
                  str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')]
    runtimes = []
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen or not Path(candidate).exists():
            continue
        seen.add(candidate)
        proc = subprocess.run([candidate, '-c', PROBE, json.dumps(PACKAGES)], text=True, capture_output=True, timeout=30)
        record = {'requested_executable': candidate, 'exit_code': proc.returncode}
        if proc.returncode == 0:
            record.update(json.loads(proc.stdout))
        else:
            record['error'] = proc.stderr[-2000:]
        runtimes.append(record)
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'runtimes': runtimes,
              'scope': 'Installed distribution metadata only; successful import and end-to-end GIS operations are separate checks.',
              'tools': {tool: shutil.which(tool) for tool in ['gdalinfo', 'ncdump', 'textutil', 'pdftoppm', 'git']},
              'installations_performed': False}
    out = ROOT / 'track_b/audit/environment.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
