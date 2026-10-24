#!/usr/bin/env python3
"""Bind all stable Q1 R2 outputs and verify direct input/output hashes offline.

AI assistance: OpenAI Codex, 2026-10-24. This does not rerun R1 processing.
"""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path

R2 = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
OUT = R2 / 'output_manifest.json'
EXACT_EXCLUSIONS = {'output_manifest.json', 'workspace_binding.json', 'workspace_verification.json'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def included(path):
    return (path.is_file() and str(path.relative_to(R2)) not in EXACT_EXCLUSIONS
            and '__pycache__' not in path.parts and not fnmatch.fnmatch(path.name, '*.log'))


def verify_inputs():
    manifest = json.loads((R2 / 'input_manifest.json').read_text())
    for entry in manifest['files']:
        path = ROOT / entry['path']
        assert path.resolve() == path and path.is_relative_to(ROOT), entry['path']
        assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], entry['path']
        assert path != R2 / 'input_manifest.json' and path != OUT
    return len(manifest['files'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    input_count = verify_inputs()
    if not args.verify_only:
        cfg = json.loads((R2 / 'config/analysis.json').read_text())
        entries = [{'path': str(p.relative_to(R2)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                   for p in sorted(R2.rglob('*')) if included(p)]
        manifest = {'packet_version': 'q1-r2-v1', 'common_baseline_commit': cfg['common_baseline_commit'],
            'context_ref': 'results/context.json',
            'scope': 'All stable files below this round2 directory, including input_manifest, task/docs/code/config/results/figures and saved source evidence. Output manifest excludes itself.',
            'excluded_exact_paths': sorted(EXACT_EXCLUSIONS), 'excluded_patterns': ['*.log', '**/__pycache__/**'],
            'exclusion_reason': 'Self-reference or mutable runtime binding/check/log; Git and explicit workspace verification bind those separately.',
            'files': entries}
        OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    manifest = json.loads(OUT.read_text())
    actual = {str(p.relative_to(R2)) for p in R2.rglob('*') if included(p)}
    assert actual == {e['path'] for e in manifest['files']}, 'Missing or unlisted stable output'
    for entry in manifest['files']:
        path = R2 / entry['path']
        assert path.resolve() == path and path.is_relative_to(R2), entry['path']
        assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], entry['path']
        assert path != OUT
    print(json.dumps({'passed': True, 'input_files_verified': input_count,
                      'stable_output_files_verified': len(manifest['files']), 'manifest_sha256': sha(OUT)}))


if __name__ == '__main__':
    main()
