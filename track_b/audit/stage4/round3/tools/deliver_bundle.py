#!/usr/bin/env python3
"""Hash-check an explicitly reviewed R3 export and deliver immutable copies.

AI assistance: OpenAI Codex, 2026-10-24. This tool records an advisor's
scope decision; it does not accept scientific labels or model conclusions.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[5]
AUDIT = ROOT / 'track_b/audit/stage4/round3'
CACHE = ROOT.parent / 'research_cache/round3'


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save_once(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Immutable delivery already exists with different bytes: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer', choices=('q1', 'q2', 'q3', 'q4'), required=True)
    parser.add_argument('--bundle', required=True, help='Repo-relative export path')
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--consumers', nargs='+', choices=('q1', 'q2', 'q3', 'q4'), required=True)
    parser.add_argument('--review-note', required=True)
    args = parser.parse_args()
    registry = json.loads((AUDIT / 'workspaces.json').read_text())
    workspaces = {w['question']: Path(w['execution_root']) for w in registry['workspaces']}
    source_root = workspaces[args.producer]
    packet = Path(f'track_b/research/{args.producer}/round3')
    bundle_path = (source_root / args.bundle).resolve()
    assert bundle_path.is_relative_to(source_root / packet / 'exports')
    assert sha(bundle_path) == args.expected_sha256, 'Export changed since review'
    original = json.loads(bundle_path.read_text())
    contract = json.loads((ROOT / 'track_b/config/stage4_round3_contract.json').read_text())
    assert all(k in original for k in contract['bundles']['required'])
    assert original['producer_question'] == args.producer
    assert original['input_version']['baseline_commit'] == registry['common_baseline_commit']
    label = re.sub(r'[^A-Za-z0-9_.-]+', '_', bundle_path.stem + '_' + original['bundle_version'])
    verified = []
    seen = set()
    for item in original['files']:
        assert all(k in item for k in contract['bundles']['file_fields'])
        declared = Path(item['path'])
        source = (source_root / declared).resolve()
        assert source != bundle_path and source not in seen
        seen.add(source)
        if declared.is_absolute():
            assert source.is_relative_to(CACHE.resolve()), str(source)
            relative = None
        else:
            assert source.is_relative_to((source_root / packet).resolve()), str(source)
            relative = source.relative_to(source_root / packet)
        assert source.is_file() and source.stat().st_size == item['bytes'], str(source)
        assert sha(source) == item['sha256'], str(source)
        verified.append((item, source, relative))
    records = []
    for consumer in args.consumers:
        assert consumer != args.producer
        consumer_root = workspaces[consumer]
        destination = Path(f'track_b/research/{consumer}/round3/inputs/{args.producer}/{label}')
        delivered = dict(original)
        delivered['files'] = []
        for item, source, relative in verified:
            row = dict(item)
            if relative is not None:
                target = destination / 'files' / relative
                save_once(consumer_root / target, source.read_bytes())
                row['upstream_path'] = row['path']
                row['path'] = target.as_posix()
            delivered['files'].append(row)
        delivered['advisor_review'] = {
            'upstream_bundle_sha256': args.expected_sha256,
            'note': args.review_note,
            'adoption_scope': 'Only the explicit review note; all upstream limitations retained',
        }
        save_once(consumer_root / destination / 'upstream_bundle.json', bundle_path.read_bytes())
        data = (json.dumps(delivered, ensure_ascii=False, indent=2) + '\n').encode()
        save_once(consumer_root / destination / 'bundle.json', data)
        records.append({'producer': args.producer, 'consumer': consumer,
                        'bundle_version': original['bundle_version'],
                        'upstream_path': args.bundle,
                        'upstream_bundle_sha256': args.expected_sha256,
                        'delivered_bundle_path': (destination / 'bundle.json').as_posix(),
                        'delivered_bundle_sha256': hashlib.sha256(data).hexdigest(),
                        'files': delivered['files'], 'review_note': args.review_note})
    ledger_path = AUDIT / 'handoffs.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'round': 'round3', 'deliveries': []}
    for row in records:
        existing = [r for r in ledger['deliveries'] if
                    (r['producer'], r['consumer'], r['bundle_version'], r['upstream_path']) ==
                    (row['producer'], row['consumer'], row['bundle_version'], row['upstream_path'])]
        if existing:
            assert existing[0] == row, 'Ledger delivery changed'
        else:
            ledger['deliveries'].append(row)
    ledger['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'verified_files': len(verified), 'deliveries': records}, ensure_ascii=False))


if __name__ == '__main__':
    main()
