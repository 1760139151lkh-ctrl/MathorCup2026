#!/usr/bin/env python3
"""Bind Q4 artifacts to the common contract and current file hashes.

Run after experiments, visual review and HANDOFF updates. This does not rerun
experiments or certify scientific conclusions. OpenAI Codex assistance, 2026-10-24.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
Q = ROOT / 'track_b/research/q4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    run = json.loads((Q / 'results/run_summary.json').read_text())
    binding = json.loads((Q / 'workspace_binding.json').read_text())
    assert ROOT == Path(binding['execution_root']).resolve()
    assert run['input_version']['script_sha256'] == digest(Q / 'scripts/run_feasibility.py')
    assert run['input_version']['config_sha256'] == digest(Q / 'config/feasibility.json')
    for item in json.loads((Q / 'results/visual_review.json').read_text())['images']:
        assert digest(Q / item['path']) == item['sha256'], 'Changed figure needs a fresh actual visual review'
    for item in json.loads((Q / 'sources/geometry_reading.json').read_text())['reading']:
        assert digest(ROOT / item['source_path']) == item['source_sha256']
    base = {'input_version': run['input_version'], 'event_id': 'B20260826_Chhochen',
            'physical_phase': 'propagation_feasibility_only', 'time_utc': None, 'time_uncertainty': None,
            'space_object': {'crs': 'EPSG:32645', 'source_area': None, 'channel': None, 'target_site': None,
                             'note': 'Technical parameter grid only; actual event geometry not verified'},
            'variable_semantics': {'terrain_unit': 'm', 'vertical_datum': None,
                                   'rule': 'No merged/corrected terrain or event release state'},
            'forecast_reference_time': None, 'issue_time': None, 'valid_time': None, 'available_time': None,
            'data_role': 'exploration', 'evidence_status': 'local_fact'}
    files = [Q / name for name in ('RESULTS.md', 'METHOD_OPTIONS.md', 'PROPOSALS.md', 'HANDOFF.md')]
    for folder in ('scripts', 'config', 'results', 'figures', 'sources'):
        files.extend(p for p in (Q / folder).iterdir() if p.is_file() and p.name != 'result_index.json')
    artifacts = []
    for path in sorted(set(files)):
        context = dict(base)
        relative = path.relative_to(Q).as_posix()
        if 'synthetic' in path.name:
            context.update({'event_id': None, 'physical_phase': 'synthetic_scalar_advection',
                            'space_object': {'crs': None, 'coordinate_system': 'arbitrary synthetic Cartesian x; no event location'},
                            'variable_semantics': {'scalar_units': '1', 'x_units': 'm', 'time_units': 's',
                                                   'parameters': 'arbitrary synthetic test values'},
                            'data_role': 'scenario'})
        if relative in ('METHOD_OPTIONS.md', 'PROPOSALS.md', 'results/geometry_evidence.csv', 'results/parameter_evidence.csv'):
            context['evidence_status'] = 'candidate'
        if relative.startswith('sources/'):
            context['evidence_status'] = 'external_source'
        if path.name == 'cross_question_updates.json':
            context['evidence_status'] = 'unverified'
        artifacts.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': digest(path),
                          'context': context,
                          'semantic_note': 'Evidence tables preserve per-row provenance and unknowns; index binding does not approve their claims.'})
    result = {'schema_version': 1, 'contract_version': 'stage4-r1-v1',
              'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'question': 'q4', 'research_question': 'Terrain and propagation-model feasibility, not event reconstruction',
              'artifact_count': len(artifacts), 'artifacts': artifacts,
              'operational_evidence': ['workspace_binding.json', 'workspace_verification.json', 'environment_setup.log'],
              'operational_hash_policy': 'Operational files are outside this scientific-artifact hash set; latest verification is read directly.',
              'null_reasons': {'time_utc': 'No actual event arrival forecast or initiation estimate was produced.',
                               'space_object': 'Release polygon, target point and traced corridor are unverified.',
                               'available_time': 'No historical operational availability asserted.'},
              'source_to_port_continuity_verified': False, 'event_reconstruction_performed': False,
              'independent_event_validation_performed': False, 'human_core_model_adoption': 'pending',
              'self_hash_policy': 'This index excludes itself to avoid recursive hashes.'}
    path = Q / 'results/result_index.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'artifacts': len(artifacts), 'index': str(path), 'sha256': digest(path)}))


if __name__ == '__main__':
    main()
