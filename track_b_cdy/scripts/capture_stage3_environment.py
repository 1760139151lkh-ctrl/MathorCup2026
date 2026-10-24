#!/usr/bin/env python3
"""Capture the validated stage-3 runtime and native-library versions.

AI assistance: Codex, OpenAI, 2026-10-23; exact model/version unavailable.
No system or Anaconda environment is modified.
"""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import cfgrib
import eccodes
import geopandas
import h5netcdf
import pyarrow
import pyogrio
import pyproj
import rasterio
import shapely
import xarray


def main():
    root = Path(__file__).resolve().parents[2]
    lock = root / 'track_b/requirements-lock.txt'
    expected = root / 'track_b/.venv'
    if Path(sys.prefix).resolve() != expected.resolve():
        raise RuntimeError('Run this with track_b/.venv/bin/python.')
    pip_check = subprocess.run([sys.executable, '-m', 'pip', 'check'], text=True, capture_output=True, timeout=60)
    if pip_check.returncode:
        raise RuntimeError(pip_check.stdout + pip_check.stderr)
    frozen = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze', '--all'], text=True)
    if frozen != lock.read_text(encoding='utf-8'):
        raise RuntimeError('Installed distributions differ from the checked lock file.')
    packages = {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
              'executable': sys.executable, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
              'isolated_venv': sys.prefix != sys.base_prefix,
              'platform': platform.platform(), 'machine': platform.machine(),
              'packages': dict(sorted(packages.items(), key=lambda item: item[0].lower())),
              'native_libraries': {'rasterio_gdal': rasterio.__gdal_version__,
                                   'pyogrio_gdal': pyogrio.__gdal_version_string__,
                                   'proj': pyproj.proj_version_str,
                                   'geos': shapely.geos_version_string,
                                   'eccodes': eccodes.codes_get_api_version()},
              'xarray_engines': sorted(xarray.backends.list_engines()),
              'pip_check_exit_code': pip_check.returncode, 'pip_check_output': pip_check.stdout.strip(),
              'lock_matches_installed': True,
              'lock_sha256': hashlib.sha256(lock.read_bytes()).hexdigest(),
              'limitations': ['This lock has been validated on macOS x86_64 / Python 3.12 only.',
                             'A version lock does not fix unverified input-data semantics or scientific-model choices.',
                             'Native GIS wheels are verified with project samples; not all optional GDAL drivers are tested.']}
    out = root / 'track_b/audit/stage3/environment.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'isolated_venv': True, 'packages': len(packages), 'native_libraries': result['native_libraries'],
                      'pip_check': result['pip_check_output'], 'lock_matches_installed': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
