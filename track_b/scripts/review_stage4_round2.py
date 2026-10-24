#!/usr/bin/env python3
"""Read-only round-2 integration checks; writes only the main review report.

AI assistance: OpenAI Codex, 2026-10-24. No scientific model acceptance.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'track_b/audit/stage4/round2'
REPORT = AUDIT / 'integration_checks.json'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def read(path):
    return json.loads(path.read_text())


def manifest_check(root, packet, path, output=False):
    value = read(path)
    rows = value['files']
    seen = set()
    for entry in rows:
        name = entry['path']
        options = [p for p in (root / name, packet / name) if p.is_file()]
        options = list(dict.fromkeys(p.resolve() for p in options))
        assert len(options) == 1, f'Ambiguous/missing manifest input: {name}'
        target = options[0]
        assert target.is_relative_to(root.resolve()), name
        assert target != path.resolve() and target not in seen, name
        if output:
            assert target.is_relative_to(packet.resolve()), name
        assert target.stat().st_size == entry['bytes'], name
        assert digest(target) == entry['sha256'], name
        seen.add(target)
    return {'path': str(path.relative_to(root)), 'file_count': len(rows),
            'sha256': digest(path), 'all_entries_match': True}


def main():
    registry = read(AUDIT / 'workspaces.json')
    checks = []
    def check(name, action):
        try:
            checks.append({'name': name, 'passed': True, 'evidence': action()})
        except Exception as exc:
            checks.append({'name': name, 'passed': False,
                           'error': f'{type(exc).__name__}: {exc}'})

    def frozen():
        path = ROOT / 'track_b/scripts/stage4_workspace.py'
        spec = importlib.util.spec_from_file_location('stage4_workspace', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.input_integrity('round2')
        assert result['manifest_sha256'] == registry['manifest_sha256']
        return result
    check('frozen_preparation_inputs', frozen)

    def preservation():
        value = read(AUDIT / 'round1_preservation.json')
        roots = [ROOT] + [Path(w['execution_root']) for w in registry['workspaces']]
        for root in roots:
            for entry in value['files']:
                target = root / entry['path']
                assert target.stat().st_size == entry['bytes'], str(target)
                assert digest(target) == entry['sha256'], str(target)
        return {'protected_files_per_checkout': len(value['files']),
                'checkouts': len(roots), 'all_unchanged': True}
    check('round1_packets_and_original_manifest_preserved', preservation)

    for item in registry['workspaces']:
        def workspace(w=item):
            root = Path(w['execution_root'])
            packet = Path(f"track_b/research/{w['question']}/round2")
            assert git(root, 'status', '--porcelain') == '', str(root)
            assert git(root, 'rev-parse', 'HEAD') == w['source_commit']
            assert git(root, 'branch', '--show-current') == w['git_branch']
            assert git(root, 'rev-parse', w['previous_branch']) == w['previous_source_commit']
            subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor',
                            registry['common_baseline_commit'], w['source_commit']], check=True)
            subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor',
                            w['integration_commit'], 'HEAD'], check=True)
            changed = git(root, 'diff', '--no-renames', '--name-only',
                          registry['common_baseline_commit'], 'HEAD').splitlines()
            assert changed and all(p.startswith(packet.as_posix() + '/') for p in changed)
            for name in changed:
                assert (ROOT / name).is_file(), name
                assert digest(root / name) == digest(ROOT / name), name
                assert git(root, 'rev-parse', w['source_commit'] + ':' + name) == git(
                    ROOT, 'rev-parse', w['integration_commit'] + ':' + name), name
            reports = read(root / packet / 'workspace_verification.json')
            assert reports['passed'] and len(reports['checks']) == 5
            manifests = {}
            for name in ('input_manifest.json', 'output_manifest.json'):
                paths = [p for p in (packet / name, packet / 'results' / name)
                         if (root / p).is_file()]
                assert len(paths) == 1, (w['question'], name)
                relative = paths[0]
                source = manifest_check(root, root / packet, root / relative,
                                        output=name == 'output_manifest.json')
                integrated = manifest_check(ROOT, ROOT / packet, ROOT / relative,
                                            output=name == 'output_manifest.json')
                assert source == integrated
                manifests[name] = integrated
            output = manifests['output_manifest.json']
            assert output['file_count'] == w['output_files_verified']
            assert output['sha256'] == w['final_output_manifest_sha256']
            return {'root': str(root), 'source_commit': w['source_commit'],
                    'integration_commit': w['integration_commit'],
                    'changed_paths_verified_in_main': len(changed), 'clean': True,
                    'five_exit_checks_passed': True, 'manifests': manifests}
        check(item['question'] + '_source_scope_and_integrated_artifacts', workspace)

    def interfaces():
        aoi = 'track_b/research/q4/round2/results/search_aoi.geojson'
        delivered = 'track_b/research/q2/round2/inputs/search_aoi.geojson'
        review = read(AUDIT / 'aoi_handoff_review.json')
        assert digest(ROOT / aoi) == digest(ROOT / delivered) == review['geometry_sha256']
        assert digest(AUDIT / 'aoi_handoff_review.json') == digest(
            ROOT / 'track_b/research/q2/round2/inputs/advisor_aoi_review.json')
        q3 = ROOT / 'track_b/research/q3/round2/results'
        event = read(q3 / 'us7000tc90_review.json')
        forecast = read(q3 / 'gfs_f009_availability_chain.json')
        assert not event['approved_training_label']
        assert not event['approved_independent_validation_label']
        assert not event['relationship']['strict_causal_same_chain_verified']
        assert not event['relationship']['statistical_independence_verified']
        assert forecast['available_time'] is None and not forecast['available_time_verified']
        assert forecast['real_coverage'] is None
        network = read(ROOT / 'track_b/research/q2/round2/network_budget.json')
        assert network['max_response_body_bytes_combined'] == 134217728
        assert network['consumed_response_body_bytes_combined'] == 192
        assert len(network['requests']) == 2
        assert sum(r['body_bytes_consumed'] for r in network['requests']) == 192
        assert not network['whole_scene_allowed']
        assert not network['redirects_or_retries_enabled']
        for request in network['requests']:
            assert request['http_status'] == 401 and not request['usable_pixels_obtained']
            assert digest(ROOT / request['body_path']) == request['sha256']
        return {'aoi_identical_to_approved_delivery': True,
                'mechanical_truth_and_causal_independence_not_auto_accepted': True,
                'forecast_first_availability_and_real_coverage_null': True,
                'sar_budget_evidence_sha256': digest(
                    ROOT / 'track_b/research/q2/round2/network_budget.json'),
                'sar_response_body_bytes': 192, 'sar_limit_bytes': 134217728,
                'sar_authentication_failures': 2, 'sar_pixels_obtained': False}
    check('cross_question_geometry_and_time_interfaces', interfaces)

    def links():
        docs = [ROOT / f'track_b/{name}' for name in
                ('STATUS.md', 'README.md', 'docs/16_stage4_round2_workflow.md',
                 'docs/17_stage4_round2_review.md')]
        docs += [ROOT / f'track_b/research/q{n}/round2/{name}'
                 for n in range(1, 5) for name in ('HANDOFF.md', 'ROUTE_UPDATE.md')]
        count = 0
        for doc in docs:
            assert doc.is_file(), str(doc)
            for target in re.findall(r'\]\(([^\s)]+)\)', doc.read_text()):
                target = target.strip('<>').split('#', 1)[0]
                if not target or re.match(r'^[a-zA-Z][\w+.-]*:', target):
                    continue
                path = (doc.parent / target).resolve()
                assert path.exists() or path == REPORT, (str(doc), target)
                count += 1
        return {'documents': len(docs), 'local_links': count, 'all_targets_exist': True}
    check('review_and_handoff_links', links)

    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'round': 'round2', 'passed': all(c['passed'] for c in checks),
              'checks': checks, 'review_script_sha256': digest(Path(__file__)),
              'scope': 'Input immutability, source ownership, copied artifacts and interfaces; not scientific model acceptance.',
              'human_scientific_adoption': 'pending'}
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'checks': len(checks),
                      'failures': [c for c in checks if not c['passed']],
                      'report': str(REPORT)}, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
