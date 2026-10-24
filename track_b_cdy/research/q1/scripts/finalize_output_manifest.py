#!/usr/bin/env python3
"""Inventory the stable Q1 packet; volatile runtime files and self are explicit.

Run only after reports and visual inspection records are complete.
AI assistance: OpenAI Codex, 2026-10-24.
"""
import argparse
import hashlib
import json
from pathlib import Path

Q = Path(__file__).resolve().parents[1]
OUT = Q / 'results/output_manifest.json'
EXCLUDED = {'results/output_manifest.json', 'workspace_verification.json',
            'workspace_binding.json', 'environment_setup.log', 'round1_run.log',
            'remote_comparison_run.log'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if args.verify_only:
        manifest = json.loads(OUT.read_text())
        for entry in manifest['files']:
            path = Q / entry['path']
            assert path.is_file() and path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], entry['path']
        actual = {str(p.relative_to(Q)) for p in Q.rglob('*') if p.is_file()
                  and str(p.relative_to(Q)) not in EXCLUDED and '__pycache__' not in p.parts}
        assert actual == {e['path'] for e in manifest['files']}, 'Stable packet has missing or unlisted files'
        print(json.dumps({'passed': True, 'files_verified': len(manifest['files'])}))
        return
    paths = sorted(p for p in Q.rglob('*') if p.is_file()
                   and str(p.relative_to(Q)) not in EXCLUDED and '__pycache__' not in p.parts)
    value = {'packet_version': 'q1-r1-v1', 'context_ref': 'context.json',
             'scope': 'All stable Q1 task/docs/code/config/results/figures and bounded source evidence; not only first-script outputs.',
             'excluded_exact_paths': sorted(EXCLUDED), 'excluded_directory_names': ['__pycache__'],
             'exclusion_reason': 'Self-reference or advisor/runtime verification and logs that may change independently; checked separately at handoff.',
             'files': [{'path': str(p.relative_to(Q)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths]}
    OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(paths), 'manifest_sha256': sha(OUT)}))


if __name__ == '__main__':
    main()
