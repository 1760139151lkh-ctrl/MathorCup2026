#!/usr/bin/env python3
"""Read-only integrity/inventory audit against the repository's original index.

AI assistance: Codex (model identifier not exposed in this session), OpenAI,
2026-10-23. Generated audit implementation; team must review before adoption.
This checks repository consistency, not authenticity against provider downloads.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--all-originals', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output or root / 'track_b/audit/inventory'
    out.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(r'^(.*?) \| (\d+) \| ([0-9a-f]{64})$')
    indexed = []
    for line in (root / '00_资料索引.txt').read_text(encoding='utf-8-sig').splitlines():
        match = pattern.match(line)
        if match:
            rel, size, expected_hash = match.groups()
            if args.all_originals or rel.startswith(('04_B赛道/', '01_比赛规范/', '02_提交模板/')):
                indexed.append((rel, int(size), expected_hash))
    if not indexed:
        raise ValueError('No index entries parsed: audit must not silently pass.')
    rows = []
    for rel, expected_size, expected_hash in indexed:
        path = root / rel
        size = path.stat().st_size if path.exists() else None
        actual_hash = None
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(block)
            actual_hash = digest.hexdigest()
        rows.append(dict(path=rel, bytes=size, extension=path.suffix.lower(),
                         expected_bytes=expected_size, sha256=actual_hash,
                         expected_sha256=expected_hash,
                         status='match' if size == expected_size and actual_hash == expected_hash else 'mismatch'))
    with (out / 'original_manifest.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    b_rows = [r for r in rows if r['path'].startswith('04_B赛道/')]
    actual_b = {p.relative_to(root).as_posix() for p in (root / '04_B赛道').rglob('*') if p.is_file() and p.name != '.DS_Store'}
    indexed_b = {r['path'] for r in b_rows}
    summary = dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),
                   scope='all original indexed files' if args.all_originals else 'B track + rules + templates',
                   indexed_count=len(rows), b_count=len(b_rows),
                   status_counts=dict(Counter(r['status'] for r in rows)),
                   b_bytes=sum(r['bytes'] or 0 for r in b_rows),
                   b_groups=dict(Counter(r['path'].split('/')[1] for r in b_rows)),
                   b_extensions=dict(Counter(r['extension'] for r in b_rows)),
                   b_zero_byte_files=[r['path'] for r in b_rows if r['bytes'] == 0],
                   unindexed_b_files=sorted(actual_b - indexed_b),
                   missing_b_files=sorted(indexed_b - actual_b),
                   limitations=['Hashes are compared with the existing repository index, not a provider-signed manifest.',
                                'File-header and content semantics are covered by the separate temporal/spatial audits.'])
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(any(r['status'] != 'match' for r in rows) or bool(summary['unindexed_b_files']) or bool(summary['missing_b_files']))


if __name__ == '__main__':
    raise SystemExit(main())
