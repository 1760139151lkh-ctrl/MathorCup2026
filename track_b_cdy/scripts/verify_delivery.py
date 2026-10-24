#!/usr/bin/env python3
"""Verify phase-1/2 document links and saved evidence consistency, offline.

AI assistance: Codex, OpenAI, 2026-10-23; exact model/version unavailable.
No scientific-model performance or remote URL availability is tested here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'track_b'


def link_targets(text):
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    for match in re.finditer(r'!?\[[^\]\n]*\]\(', text):
        start = pos = match.end()
        depth = 1
        while pos < len(text) and depth:
            char = text[pos]
            if char == '\\':
                pos += 2
                continue
            depth += (char == '(') - (char == ')')
            pos += 1
        if depth == 0:
            target = text[start:pos - 1].strip()
            if target.startswith('<'):
                target = target[1:target.index('>')]
            yield target


def main():
    errors = []
    output = WORK / 'audit/delivery_checks.json'
    local_links = 0
    documents = [ROOT / 'README.md', *sorted(path for path in WORK.rglob('*.md')
                                            if not any(part in {'.venv', '__pycache__'} for part in path.parts))]
    for path in documents:
        for target in link_targets(path.read_text(encoding='utf-8')):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            local_links += 1
            rel = unquote(target.split('#', 1)[0])
            destination = (path.parent / rel).resolve()
            # This record is produced at the end of the current check, including a first run.
            if destination != output and not destination.exists():
                errors.append(f'Broken local link in {path.relative_to(ROOT)}: {target}')
    parsed_json = 0
    json_data = {}
    for path in sorted((WORK / 'audit').rglob('*.json')):
        if path == output:
            continue
        try:
            json_data[path.relative_to(WORK / 'audit').as_posix()] = json.loads(path.read_text(encoding='utf-8'))
            parsed_json += 1
        except (OSError, ValueError) as exc:
            errors.append(f'Invalid JSON {path.relative_to(ROOT)}: {exc}')

    def expect(condition, message):
        if not condition:
            errors.append(message)

    inventory = json_data['inventory/summary.json']
    expect(inventory['b_count'] == 266 and inventory['indexed_count'] == 270, 'Original inventory counts differ from the audited batch.')
    expect(inventory['status_counts'] == {'match': 270}, 'Original hashes have mismatches.')
    expect(not inventory['unindexed_b_files'] and not inventory['missing_b_files'], 'B-track file set changed.')
    temporal = json_data['temporal/summary.json']
    expect(temporal['manifest_file_count'] == 47 and temporal['raw_hashes_unchanged_after_audit'], 'Temporal raw inventory check failed.')
    expect(temporal['daily']['rows'] == 7519 and temporal['daily']['file_count'] == 21, 'Daily coverage summary changed.')
    script_hash = hashlib.sha256((WORK / 'scripts/audit_temporal.py').read_bytes()).hexdigest()
    expect(temporal['script_sha256'] == script_hash, 'Temporal output was not generated with the final script.')
    temporal_hashes_checked = 0
    for item in json_data['temporal/output_manifest.json']:
        path = WORK / 'audit/temporal' / item['file']
        if not path.is_file():
            errors.append(f'Missing temporal output: {item["file"]}')
            continue
        expect(path.stat().st_size == item['bytes'], f'Size changed: {item["file"]}')
        expect(hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], f'Hash changed: {item["file"]}')
        temporal_hashes_checked += 1
    spatial = json_data['spatial/summary.json']
    expect(spatial['file_count'] == 218 and spatial['raster_count'] == 173, 'Spatial inventory summary changed.')
    expect(spatial['raster_all_cell_read_successes'] == 173 and not spatial['raster_all_cell_read_failures'], 'Raster full-cell scan failed.')
    sources = json_data['research_sources.json']
    expect(len(sources['research']) == 15 and len(sources['datasets']) == 13, 'Source registry count differs from this handoff.')
    for group in ['research', 'datasets']:
        ids = [item['id'] for item in sources[group]]
        expect(len(ids) == len(set(ids)), f'Duplicate source IDs in {group}.')
    for item in sources['research']:
        for field in ['id', 'title', 'url', 'supports', 'limits', 'read_scope']:
            expect(bool(item.get(field)), f'Missing research field: {item.get("id")} / {field}')
    forecast = json_data['forecast_probe/summary.json']
    expect(forecast['success'] and forecast['index_http_status'] == 200 and forecast['header_http_status'] == 206,
           'Historical forecast probe did not succeed.')
    expect(not forecast['data_decoded'] and forecast['actual_operational_available_time'] is None,
           'Forecast probe scope changed; update the handoff explicitly.')
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': not errors,
              'markdown_documents': len(documents), 'local_links_checked': local_links,
              'json_files_parsed_excluding_this_record': parsed_json,
              'temporal_output_hashes_checked': temporal_hashes_checked,
              'research_records': len(sources['research']), 'dataset_candidates': len(sources['datasets']),
              'errors': errors,
              'scope': ['Local file-target links only; heading anchors and remote HTTP URLs are not validated.',
                        'Saved audit-artifact consistency only; model correctness and scientific conclusions are not tested.',
                        'Counts are intentionally fixed to the phase-1/2 handoff and must be revised when the scope changes.']}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
