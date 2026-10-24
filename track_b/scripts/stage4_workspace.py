#!/usr/bin/env python3
"""Freeze inputs and verify isolated stage-4 workspaces without rewriting them.

AI assistance: OpenAI Codex, 2026-10-24; human adoption review remains required.
Only snapshot writes the common manifest. Verify writes only the assigned q folder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'track_b/audit/stage4/baseline_manifest.json'
ROUNDS = ('round1', 'round2')
QUESTIONS = ('q1', 'q2', 'q3', 'q4')


def manifest_path(round_name='round1'):
    if round_name not in ROUNDS:
        raise ValueError(f'Unsupported research round: {round_name}')
    if round_name == 'round1':
        return MANIFEST
    return ROOT / 'track_b/audit/stage4/round2/baseline_manifest.json'


def question_directory(question, round_name='round1'):
    manifest_path(round_name)
    if question not in QUESTIONS:
        raise ValueError(f'Unsupported question: {question}')
    path = ROOT / 'track_b/research' / question
    return path / 'round2' if round_name == 'round2' else path


def safe_path(path):
    """Reject symlink redirects, including a report filename redirected elsewhere."""
    if not path.is_relative_to(ROOT) or path.resolve() != path:
        raise ValueError(f'Path escapes its assigned location or uses a symlink: {path}')
    return path


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def committed_entries(commit):
    entries = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-rz', commit]).decode().split('\0')
    result = {}
    for entry in entries:
        if entry:
            metadata, name = entry.split('\t', 1)
            mode, kind, object_id = metadata.split()
            result[name] = (kind, object_id)
    return result


def fingerprint(path, object_format):
    safe_path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Frozen input must be a regular committed file: {path}')
    size = path.stat().st_size
    content_hash = hashlib.sha256()
    git_hash = hashlib.new(object_format)
    git_hash.update(f'blob {size}\0'.encode())
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            content_hash.update(block)
            git_hash.update(block)
    return {'bytes': size, 'sha256': content_hash.hexdigest(), 'git_blob': git_hash.hexdigest()}


def snapshot(preparation_commit, round_name='round1'):
    destination = safe_path(manifest_path(round_name))
    commit = git('rev-parse', preparation_commit)
    object_format = git('rev-parse', '--show-object-format')
    prefixes = ('04_B赛道/', '01_比赛规范/', '02_提交模板/',
                'track_b/data/', 'track_b/audit/')
    files = []
    for name, (kind, object_id) in sorted(committed_entries(commit).items()):
        # A later preparation commit may already contain the previous manifest.
        # Orchestration records remain mutable and must never freeze themselves.
        if name.startswith('track_b/audit/stage4/'):
            continue
        research_input = round_name == 'round2' and name.startswith('track_b/research/')
        if research_input and (any(name.startswith(f'track_b/research/{q}/round2/') for q in QUESTIONS)
                               or any(part in ('__pycache__', '.cache', '.pytest_cache') for part in Path(name).parts)):
            continue
        if research_input or name.startswith(prefixes) or name.startswith(('track_b/scripts/', 'track_b/config/')) or name in ('track_b/requirements.in', 'track_b/requirements-lock.txt'):
            path = ROOT / name
            if kind != 'blob':
                raise ValueError(f'Frozen input must be a regular committed file: {name}')
            item = fingerprint(path, object_format)
            if item['git_blob'] != object_id:
                raise ValueError(f'Working file differs from preparation commit: {name}')
            files.append({'path': name, **item})
    value = {'schema_version': 1, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
             'preparation_commit': commit, 'contract_version': f'stage4-r{ROUNDS.index(round_name) + 1}-v1',
             'scope': ('Original B/rules/templates plus preparation-commit shared data/audits/scripts/config/lock; no question outputs or self-reference.'
                       if round_name == 'round1' else
                       'Original B/rules/templates and shared preparation inputs, plus committed round-1 research inputs; excludes stage4 orchestration, round-2 question outputs and caches.'),
             'file_count': len(files), 'files': files}
    save(safe_path(destination), value)
    print(json.dumps({'manifest': str(destination), 'files': len(files), 'preparation_commit': commit}))


def input_integrity(round_name='round1'):
    manifest = safe_path(manifest_path(round_name))
    value = json.loads(manifest.read_text(encoding='utf-8'))
    if value['contract_version'] != f'stage4-r{ROUNDS.index(round_name) + 1}-v1':
        raise ValueError('Manifest contract version does not match research round')
    entries = committed_entries(value['preparation_commit'])
    object_format = git('rev-parse', '--show-object-format')
    errors = []
    for entry in value['files']:
        path = ROOT / entry['path']
        try:
            actual = fingerprint(path, object_format)
            matches = (all(actual[field] == entry[field] for field in ('bytes', 'sha256', 'git_blob'))
                       and entries.get(entry['path']) == ('blob', entry['git_blob']))
        except (OSError, ValueError):
            matches = False
        if not matches:
            errors.append(entry['path'])
    if errors:
        raise ValueError(f'Frozen input mismatch: {errors[:12]}')
    return {'file_count': len(value['files']), 'manifest_sha256': sha256(manifest),
            'preparation_commit': value['preparation_commit']}


def environment():
    if Path(sys.prefix).resolve() != (ROOT / 'track_b/.venv').resolve():
        raise ValueError('Use this worktree\'s track_b/.venv/bin/python')
    if sys.version_info[:2] != (3, 12):
        raise ValueError('Validated lock requires Python 3.12')
    frozen = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze', '--all'], text=True)
    lock = ROOT / 'track_b/requirements-lock.txt'
    if sorted(frozen.splitlines()) != sorted(lock.read_text().splitlines()):
        raise ValueError('Installed distributions differ from the exact lock')
    checked = subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True, timeout=60)
    if checked.returncode:
        raise ValueError(checked.stdout + checked.stderr)
    return {'python': sys.version.split()[0], 'prefix': sys.prefix, 'package_count': len(frozen.splitlines()),
            'lock_sha256': sha256(lock), 'pip_check': checked.stdout.strip()}


def formats():
    import eccodes
    import geopandas as gpd
    import pandas as pd
    import rasterio
    import xarray as xr
    source = ROOT / '04_B赛道'
    csv = source / '01_逐小时地气观测（2021-2026）/MET_Gyirong_2026.csv'
    assert len(pd.read_csv(csv, nrows=3)) == 3
    book = source / '02_逐日平均气温（2005-2025）/2米气温数据_2025.xlsx'
    assert len(pd.read_excel(book, engine='openpyxl')) == 214
    history = gpd.read_file(next((source / '06_历史灾点').glob('*.shp')))
    assert len(history) == 84 and history.crs.to_epsg() == 4490
    with rasterio.open(source / '07_DEM（2026-08-26）/DEM.tif') as dataset:
        assert dataset.shape == (1148, 1816)
        assert dataset.read(1, window=rasterio.windows.Window(0, 0, 16, 16), masked=True).count() == 256
    nc = next((source / '04_冰川地形、冰厚及表面速度').glob('*.nc'))
    with xr.open_dataset(nc, engine='h5netcdf', decode_cf=True, decode_coords='all') as dataset:
        assert dataset.sizes['y'] == 138 and dataset.sizes['x'] == 145
    with (ROOT / 'track_b/data/external/forecast_sample/temperature_2m.grib2').open('rb') as stream:
        message = eccodes.codes_grib_new_from_file(stream)
        assert message is not None
        try:
            assert eccodes.codes_get(message, 'dataDate') == 20260825
            assert eccodes.codes_get(message, 'units') == 'K'
        finally:
            eccodes.codes_release(message)
    return {'formats_read': ['CSV', 'XLSX', 'SHP', 'GeoTIFF', 'NetCDF4', 'GRIB2']}


def responsibility(question, base, round_name='round1'):
    directory = safe_path(question_directory(question, round_name))
    allowed = directory.relative_to(ROOT).as_posix() + '/'
    committed = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--no-renames', '--name-only', '-z', base, 'HEAD']).decode().split('\0')
    unstaged = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--no-renames', '--name-only', '-z', 'HEAD']).decode().split('\0')
    untracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--others', '--exclude-standard', '-z']).decode().split('\0')
    changes = sorted({name for name in committed + unstaged + untracked if name})
    disallowed = [name for name in changes if not name.startswith(allowed)]
    if disallowed:
        raise ValueError(f'Changes outside assigned folder: {disallowed[:12]}')
    for name in changes:
        safe_path(ROOT / name)
    return {'allowed_directory': allowed, 'changed_paths': changes}


def verify(args):
    round_name = getattr(args, 'round', 'round1')
    try:
        out = safe_path(question_directory(args.question, round_name) / 'workspace_verification.json')
        if ROOT != Path(args.expected_root).resolve():
            raise ValueError(f'Workspace root mismatch: {ROOT}')
    except (ValueError, OSError, RuntimeError) as exc:
        # An identity/path failure must not create files in the wrong workspace.
        print(json.dumps({'passed': False, 'report': None, 'checks': [
            {'name': 'safe_report_destination', 'passed': False,
             'error': f'{type(exc).__name__}: {exc}'}]}, ensure_ascii=False))
        return 1
    checks = []
    def check(name, operation):
        try:
            checks.append({'name': name, 'passed': True, 'evidence': operation()})
        except Exception as exc:
            checks.append({'name': name, 'passed': False, 'error': f'{type(exc).__name__}: {exc}'})
    def identity():
        if ROOT != Path(args.expected_root).resolve():
            raise ValueError(f'Workspace root mismatch: {ROOT}')
        base = git('rev-parse', args.expected_base)
        subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', base, 'HEAD'], check=True)
        if args.pristine and git('rev-parse', 'HEAD') != base:
            raise ValueError('Initial workspace HEAD is not the common baseline')
        return {'root': str(ROOT), 'head': git('rev-parse', 'HEAD'), 'baseline_commit': base,
                'branch': git('rev-parse', '--abbrev-ref', 'HEAD')}
    check('workspace_and_git_baseline', identity)
    check('frozen_input_hashes', lambda: input_integrity(round_name))
    check('isolated_environment_and_lock', environment)
    check('six_real_formats', formats)
    check('question_file_ownership', lambda: responsibility(args.question, args.expected_base, round_name))
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'question': args.question,
              'passed': all(c['passed'] for c in checks), 'checks': checks,
              'scope': 'Workspace, frozen inputs, environment and technical I/O only; no scientific model acceptance.'}
    if round_name == 'round2':
        result['round'] = round_name
    save(safe_path(out), result)
    print(json.dumps({'passed': result['passed'], 'report': str(out), 'checks': [dict(name=c['name'], passed=c['passed'], **({'error': c['error']} if 'error' in c else {})) for c in checks]}, ensure_ascii=False))
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    snap = commands.add_parser('snapshot')
    snap.add_argument('--preparation-commit', required=True)
    snap.add_argument('--round', choices=ROUNDS, default='round1')
    run = commands.add_parser('verify')
    run.add_argument('--question', choices=QUESTIONS, required=True)
    run.add_argument('--round', choices=ROUNDS, default='round1')
    run.add_argument('--expected-root', required=True)
    run.add_argument('--expected-base', required=True)
    run.add_argument('--pristine', action='store_true', help='Require HEAD to equal the common starting commit')
    args = parser.parse_args()
    if args.command == 'snapshot':
        snapshot(args.preparation_commit, args.round)
        return 0
    return verify(args)


if __name__ == '__main__':
    raise SystemExit(main())
