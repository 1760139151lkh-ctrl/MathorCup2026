#!/usr/bin/env python3
"""Seal only the fullmask join increment; verify it without producer-tree paths."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

R = Path(__file__).resolve().parents[1]
ROOT = R.parents[3]
BASE = '0d5326d6e3428df4d714d8101c41c7c925eca0ef'
COMMON_BASE = '904d7257b899b9f71d1ac9e0eab7479e459eab52'
QDIR = R / 'inputs/q4/bundle_q4-r3-propagation-v3'
Q = QDIR / 'bundle.json'
QPIN = '8457a9db624c33c0d0988ad8f4d8c8513ff21ac858ccff830bae577f77f0b683'
PRODUCER_PIN = '150c72537ee162d29cc2e20e3e31183df1915f64999234789e1875d368c09b9c'
P = R / 'results/arrival/propagation_v3'
O = R / 'results/fullmask_v3'
BUNDLE = R / 'exports/fullmask_propagation_join_bundle_v3.json'


def read(p):
    return json.loads(p.read_text())


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def record(p):
    return dict(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p), bytes=p.stat().st_size, sha256=sha(p))


def target(row, approved):
    p = Path(row['path'])
    if p.is_absolute():
        assert row['path'] in approved, 'Unapproved absolute executable reference'
        assert (row['bytes'], row['sha256']) == approved[row['path']]
    else:
        assert '..' not in p.parts and p.is_relative_to(Path('track_b/research/q3/round3'))
        p = ROOT / p
    assert p.is_file() and p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], row['path']
    return p


def canonical(row, approved):
    item = dict(row)
    p = Path(item['path'])
    if p.is_absolute() and p.is_relative_to(R):
        item['path'] = str(p.relative_to(ROOT))
    elif not p.is_absolute() and not p.is_relative_to(Path('track_b')):
        item['path'] = str((R / p).relative_to(ROOT))
    target(item, approved)
    return item


def prior_snapshot():
    """Build once against the pinned payload commit; verification needs no Git object."""
    raw = subprocess.check_output(['git', 'ls-tree', '-rz', BASE, '--', str(R.relative_to(ROOT))], cwd=ROOT)
    files = []
    for part in raw.split(b'\0'):
        if not part:
            continue
        header, path = part.decode().split('\t', 1)
        mode, kind, oid = header.split()
        assert kind == 'blob'
        p = ROOT / path
        data = p.read_bytes()
        current_oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        assert current_oid == oid, path
        files.append(dict(record(p), git_blob_oid=oid))
    assert files
    return dict(source_commit=BASE, files=files, scope='Every prior tracked Q3 round3 file remains exact bytes; all new input and output paths are separate')


def check_unique(rows, approved):
    assert len(rows) == len({row['path'] for row in rows})
    for row in rows:
        target(row, approved)


def adapter_checks(approved):
    validation = read(P / 'validation.json')
    assert validation['passed'] and not validation.get('adapter_pass_is_predictive_qualification', False)
    for name in ['input_index', 'output_index']:
        p = P / (name + '.json')
        assert sha(p) == validation[name + '_sha256']
        for row in read(p)['files']:
            target(row, approved)
    review = read(P / 'review/final_review.json')
    assert review['passed']
    for row in review['inputs']:
        canonical(row, approved)
    qa = read(P / 'figure_review.json')
    assert qa['passed'] and qa['figures']
    for row in qa['figures']:
        assert row['actually_opened']
        p = ROOT / row['path']
        assert not Path(row['path']).is_absolute() and sha(p) == row['sha256']
    return validation, review


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--verify-only', action='store_true')
    args = cli.parse_args()
    assert sha(Q) == QPIN and sha(QDIR / 'upstream_bundle.json') == PRODUCER_PIN
    qb = read(Q)
    assert len(qb['files']) == 66
    approved = {f['path']: (f['bytes'], f['sha256']) for f in qb['files'] if Path(f['path']).is_absolute()}
    for row in qb['files']:
        target(row, approved)
    av, review = adapter_checks(approved)
    if not args.verify_only:
        O.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        prior = prior_snapshot()
        write(O / 'frozen_prior_files.json', prior)
        old_report = R / 'workspace_verification.json'
        saved = old_report.read_bytes()
        try:
            run = subprocess.run([sys.executable, str(ROOT/'track_b/scripts/stage4_workspace.py'), 'verify', '--round', 'round3', '--question', 'q3', '--expected-root', str(ROOT), '--expected-base', COMMON_BASE], cwd=ROOT, capture_output=True, text=True)
            (O/'workspace_check.log').write_text(run.stdout + run.stderr)
            check = read(old_report)
            write(O/'workspace_verification.json', check)
            assert run.returncode == 0 and check['passed']
        finally:
            old_report.write_bytes(saved)
        for row in prior['files']:
            target(row, approved)
        merged = {}
        registrations = []

        def add(row, origin, role):
            item = canonical(row, approved)
            path = item['path']
            if path not in merged:
                merged[path] = {k: item[k] for k in ['path', 'bytes', 'sha256']}
                merged[path].update(roles=[], registrations=[])
            entry = merged[path]
            assert (entry['bytes'], entry['sha256']) == (item['bytes'], item['sha256'])
            for label in role if isinstance(role, list) else [role]:
                if label not in entry['roles']:
                    entry['roles'].append(label)
            entry['registrations'].append(origin)
            registrations.append(path)

        for i, row in enumerate(qb['files']):
            add(row, dict(index_name='approved_Q4_consumer_bundle', row_index_0based=i), row['role'])
        for i, row in enumerate(read(P/'input_index.json')['files']):
            add(row, dict(index_name='executed_adapter_input_index', row_index_0based=i), row.get('roles', row.get('role', 'adapter input')))
        for i, row in enumerate(review['inputs']):
            add(row, dict(index_name='independent_review_inputs', row_index_0based=i), row.get('roles', row.get('role', 'independent audit input')))
        for path, role in [(Q,'approved consumer packet'),(QDIR/'upstream_bundle.json','frozen producer packet'),(R/'scripts/seal_fullmask_v3.py','increment sealer source')]:
            add(record(path), dict(index_name='increment_registration'), role)
        inputs = list(merged.values())
        write(O/'input_manifest.json', dict(generated_at_utc=now, files=inputs,unique_file_count=len(inputs),registration_count=len(registrations),
              duplicate_registration_count=len(registrations)-len(inputs),deduplication_key='canonical path; byte/hash conflicts rejected; all roles and row provenance retained',
              portability='Repository files relative to current root; absolute reads limited to exact approved Q4 cache file records',
              source_base_commit=BASE,Q4_consumer_bundle_sha256=QPIN,physics_rerun=False))
        bundle_files=[p for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.log']
        bundle_files += [O/'input_manifest.json',O/'frozen_prior_files.json',R/'FULLMASK_V3_HANDOFF.md']
        write(BUNDLE,dict(bundle_version='q3-r3-fullmask-propagation-join-v3',producer_question='q3',created_at_utc=now,
              files=[dict(record(p),role=str(p.relative_to(R))) for p in bundle_files],source_base_commit=BASE,Q4_consumer_bundle_sha256=QPIN,
              local_truth_events_added=0,empirical_coverage=None,qualified_arrival_rows=0,absolute_arrival_rows=0,arrival_probability_rows=0,
              limitations=['Three selected physical cases are not the2048-design weighted forecast ensemble','Fullmask geometry-v2 is distinct from earlier compact geometry-v1',
                          'Raw conditional saved-output travel diagnostics only; no accepted arrival envelope','Unknown initiation-to-release lag is not zero; no absolute arrival or probability',
                          'Threshold footprints and raster-support distances are not validated warning effectiveness'],physical_solver_rerun=False))
        paths = [p for folder in [P,O,QDIR] for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['output_manifest.json','packet_validation.json']]
        paths += [BUNDLE,R/'FULLMASK_V3_HANDOFF.md',R/'scripts/join_propagation_v3.py',Path(__file__).resolve()]
        write(O/'output_manifest.json',dict(generated_at_utc=now,files=[record(p) for p in sorted(set(paths))],
              excluded={'output_manifest.json':'self reference','packet_validation.json':'avoid circular hash dependency','__pycache__':'transient interpreter bytes'}))
        checks=dict(approved_66_files_hash_verified=True,adapter_quality_and_lineage_checks=av['passed'],independent_review=review['passed'],
                    prior_tracked_payload_bytes_preserved=True,standard_workspace_checks=check['passed'],unique_portable_input_records=True,actual_final_figure_review=True)
        write(O/'packet_validation.json',dict(generated_at_utc=now,passed=all(checks.values()),checks=checks,input_manifest_sha256=sha(O/'input_manifest.json'),
              output_manifest_sha256=sha(O/'output_manifest.json'),frozen_prior_manifest_sha256=sha(O/'frozen_prior_files.json'),bundle_sha256=sha(BUNDLE),
              source_base_commit=BASE,physics_rerun=False,local_truth_events=0,empirical_coverage=None))
    packet = read(O/'packet_validation.json')
    assert packet['passed'] and all(packet['checks'].values())
    for key, path in [('input_manifest_sha256',O/'input_manifest.json'),('output_manifest_sha256',O/'output_manifest.json'),
                      ('frozen_prior_manifest_sha256',O/'frozen_prior_files.json'),('bundle_sha256',BUNDLE)]:
        assert sha(path) == packet[key]
    for p in [O/'input_manifest.json',O/'output_manifest.json',O/'frozen_prior_files.json',BUNDLE]:
        check_unique(read(p)['files'], approved)
    print(json.dumps(dict(passed=True,mode='verify_only' if args.verify_only else 'seal_increment',source_base_commit=BASE,
                         input_manifest_sha256=sha(O/'input_manifest.json'),output_manifest_sha256=sha(O/'output_manifest.json'),bundle_sha256=sha(BUNDLE))))


if __name__ == '__main__':
    main()
