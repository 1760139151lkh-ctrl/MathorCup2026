#!/usr/bin/env python3
"""Offline evidence consolidation; never correct velocity values or fetch data."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'track_b/research/q2/round2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    binding = json.loads((OUT / 'workspace_binding.json').read_text())
    assert ROOT == Path(binding['execution_root']).resolve()
    frozen_path = ROOT / binding['manifest']
    assert sha(frozen_path) == binding['manifest_sha256']
    frozen = {r['path']: r for r in json.loads(frozen_path.read_text())['files']}
    version = {'baseline_commit': binding['common_baseline_commit'], 'baseline_manifest_sha256': binding['manifest_sha256']}
    metadata = {'event_id': 'B20260826_Chhochen', 'physical_phase': 'background_evidence_review',
                'time_utc': None, 'time_uncertainty': None, 'space_object': {'id': 'NC_parameter_domain_or_reviewed_search_AOI', 'true_failure_geometry_verified': False},
                'variable_semantics': 'historical product and access evidence only; no event parameter estimates',
                'available_time': None, 'forecast_reference_time': None, 'issue_time': None, 'valid_time': None,
                'data_role': 'exploration', 'input_version': version, 'evidence_status': 'local_fact'}
    local_inputs = {}

    def use(path, role='read_input'):
        path = path if isinstance(path, Path) else ROOT / path
        name = str(path.relative_to(ROOT))
        record = {'path': name, 'bytes': path.stat().st_size, 'sha256': sha(path), 'role': role}
        if name in frozen:
            assert record['sha256'] == frozen[name]['sha256'] and record['bytes'] == frozen[name]['bytes'], name
        local_inputs[name] = record
        return path

    def load(path):
        return json.loads(use(path).read_text())

    velocity_registry = load(OUT / 'sources/velocity_source_register.json')
    for row in velocity_registry['local_inputs_used']:
        path = use(row['path'], 'velocity_chain_local_evidence')
        assert sha(path) == row['sha256']
    sources = []
    for row in velocity_registry['sources']:
        assert sha(use(row['saved_path'], 'official_source_snapshot')) == row['sha256']
        sources.append(row)
    # The source producer opened these rendered PDF pages; preserve their exact
    # hash/version separately from the raw official PDF and from human adoption.
    for row in velocity_registry.get('rendered_pages_opened', []):
        path_name = row.get('path', row.get('saved_path'))
        if path_name:
            assert sha(use(path_name, 'derived_pdf_page_actually_opened_by_internal_reviewer')) == row['sha256']
    budget = load(OUT / 'network_budget.json')
    assert budget['consumed_response_body_bytes_combined'] == sum(r['body_bytes_consumed'] for r in budget['requests']) == 192
    assert len(budget['requests']) == 2 and budget['consumed_response_body_bytes_combined'] <= 134217728
    for request in budget['requests']:
        path = use(request['body_path'], 'authentication_failure_body_not_pixels')
        assert sha(path) == request['sha256'] and path.stat().st_size == request['body_bytes_consumed']
        sources.append({**metadata, 'source_id': f'sar_request_{request["request_id"]}', 'url': request['url'],
                        'version': request['scene_id'], 'retrieved_at_utc': request['ended_at_utc'],
                        'actual_reading_scope': 'Anonymous Range header probe received 401 JSON; error body only, not TIFF/pixels.',
                        'http_status': request['http_status'], 'saved_path': request['body_path'], 'bytes': path.stat().st_size,
                        'sha256': request['sha256'], 'outcome': 'excluded_with_reason'})
    for path in sorted((OUT / 'inputs').iterdir()):
        if path.is_file():
            use(path, 'advisor_distributed_search_geometry_evidence')
    approval = load(OUT / 'inputs/advisor_aoi_review.json')
    assert sha(OUT / 'inputs/search_aoi.geojson') == approval['geometry_sha256']
    assert sha(OUT / 'inputs/search_aoi_evidence.json') == approval['evidence_sha256']
    for row in approval['files']:
        path = use(Path(row['delivered_path']), 'advisor_distributed_search_geometry_evidence')
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    pair = load(OUT / 'results/pair_access.json')
    aoi = load(OUT / 'results/aoi_support_check.json')
    guards = load(OUT / 'results/network_guard_checks.json')
    first_round = load('track_b/research/q2/results/input_check.json')
    use('track_b/config/stage4_round2_contract.json')
    use('track_b/data/external/event_remote/scene_inventory.json')
    use('track_b/research/q2/results/parameter_evidence.csv')
    assert guards['passed'] and all(not row['usable_pixels_obtained'] for row in pair['records'])
    assert aoi['network_requests_this_step'] == 0 and aoi['producer_pending_fields_preserved']
    assert aoi['aoi_sha256'] == approval['geometry_sha256']
    assert not aoi['all_search_features_contained_in_both_catalogue_footprints']
    with (OUT / 'results/velocity_definition_chain.csv').open() as stream:
        velocity_rows = list(csv.DictReader(stream))
    assert len(velocity_rows) == 16
    records = [
        ('velocity_climatological_definition', 'adoptable_with_explicit_role', 'NC metadata and pinned official definition support historical-background interpretation; exact local original object not authenticated.', 'VELOCITY_REVIEW.md; results/velocity_definition_chain.csv V01-V09', 'Record 2014-2024 claim, 2018 intercept and meter/year; do not imply an event observation.'),
        ('local_velocity_generation_chain', 'unknown_with_evidence_and_next_action', 'Original object ID/native grid/maker script/order of magnitude, mosaic, interpolation, masking and rotation remain missing.', 'results/velocity_definition_chain.csv V06,V09,V10,V13,V14', 'Retrieve minimal exact provenance and a few matched native cells in a later task; retain raw values.'),
        ('velocity_magnitude_discrepancy', 'adoptable_with_explicit_role', json.dumps(first_round['velocity_arithmetic_consistency'], ensure_ascii=False, sort_keys=True), 'frozen round1 results/input_check.json, not recomputed', 'Arithmetic discrepancy stays flagged; no cause or correction asserted.'),
        ('stage3_as_residual_cause', 'excluded_with_reason', 'Stage3 read/sort/raw-decode checks preserve supplied velocities and do not regenerate them.', 'VELOCITY_REVIEW.md; velocity_definition_chain V11', 'Trace upstream local NC creation instead.'),
        ('velocity_vector_basis', 'unknown_with_evidence_and_next_action', 'EPSG32645 describes geometry but actual component rotation into target frame is not recorded.', 'velocity_definition_chain V14', 'Q4 cannot treat vx/vy as verified event initial-flow vectors.'),
        ('event_initial_velocity_or_acceleration', 'excluded_with_reason', 'Climatological fields and seasonal amplitude do not supply the 2026 event sequence or release initial velocity.', 'velocity_definition_chain V15', 'Q4 event initial conditions remain separate scenarios/unknowns.'),
        ('fixed_pair_vv_pixels', 'excluded_with_reason', 'Both approved anonymous VV requests returned 401 JSON; 96+96=192 response-body bytes, no TIFF or pixels.', 'results/pair_access.json; network_budget.json', 'End this access path; no retry, new date/orbit/polarization or whole-scene request.'),
        ('reviewed_search_aoi_footprint', 'adoptable_with_explicit_role', 'Both catalogue footprints intersect but do not contain the whole search AOI; three retrospective map-symbol anchors are inside both.', 'results/aoi_pixel_support.csv; inputs/advisor_aoi_review.json', 'Search-only topology; unknown original map accuracy/datum retained; no shrinking or failure-boundary adoption.'),
        ('structural_hydraulic_event_parameters', 'unknown_with_evidence_and_next_action', 'This bounded evidence round did not measure structural strength, sliding geometry, pore pressure or source temperature.', 'round1 parameter_evidence.csv; current access failure', 'Q2/Q4 still need independent source/structure/water-thermal constraints before event thresholds.')]
    statuses = {'velocity_climatological_definition': 'inference', 'local_velocity_generation_chain': 'unverified',
                'velocity_magnitude_discrepancy': 'local_fact', 'stage3_as_residual_cause': 'local_fact',
                'velocity_vector_basis': 'unverified', 'event_initial_velocity_or_acceleration': 'inference',
                'fixed_pair_vv_pixels': 'local_fact', 'reviewed_search_aoi_footprint': 'local_fact',
                'structural_hydraulic_event_parameters': 'unverified'}
    rows = [{**metadata, 'evidence_status': statuses[name], 'parameter_or_use': name, 'outcome': outcome, 'finding': finding,
             'source_locator': source, 'next_action': next_action} for name, outcome, finding, source, next_action in records]
    with (OUT / 'results/parameter_evidence_update.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    save(OUT / 'results/source_register.json', {**metadata, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
         'records': sources, 'official_velocity_document_count': 5,
         'official_velocity_source_body_bytes': velocity_registry['downloaded_source_body_bytes'],
         'sar_response_body_budget_accounted_separately': True, 'sar_response_body_bytes': 192,
         'aoi_approval': {'path': str((OUT / 'inputs/advisor_aoi_review.json').relative_to(ROOT)), 'sha256': sha(OUT / 'inputs/advisor_aoi_review.json'), 'purpose': 'search_only'},
         'rendered_pages_opened': velocity_registry.get('rendered_pages_opened', []),
         'no_historical_available_time_inferred_from_retrieval': True})
    save(OUT / 'input_manifest.json', {'input_version': version, 'files': list(local_inputs.values()),
         'scope': 'Actual local/official/approved evidence consumed; no self-entry or output manifest. Source/register may reference derived review inputs explicitly.'})
    result = {**metadata, 'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'ready_for_joint_review',
              'velocity_chain_records': len(velocity_rows), 'parameter_updates': len(rows),
              'sar_scenes_attempted': 2, 'sar_http_statuses': [r['http_status'] for r in budget['requests']],
              'sar_body_bytes_combined': 192, 'sar_body_limit': 134217728,
              'usable_pixels_obtained': False, 'co_registration_verified': False,
              'search_aoi_adopted_only_for_catalogue_screening': True,
              'whole_search_aoi_contained': False, 'all_three_map_symbol_anchors_inside': True,
              'offline_guard_checks_passed': len(guards['checks']),
              'first_round_residual_recomputed': False, 'raw_velocity_values_modified': False,
              'scientific_model_acceptance': 'not_evaluated; no threshold or event reconstruction',
              'resolved': ['official definition context', 'stage3 velocity preservation', 'fixed-pair anonymous access outcome', 'reviewed search-AOI catalogue support'],
              'unknown': ['exact native source object/local maker chain', 'residual cause', 'velocity vector rotation', 'event parameters', 'pixel content and quality'],
              'blocked_for_current_route': ['2026 VV pixel change analysis via tested anonymous endpoints', 'event-constrained critical-condition estimation'],
              'can_continue': ['background evidence stratification', 'source/terrain provenance', 'conditional uncertainty design']}
    save(OUT / 'results/result_index.json', result)
    excluded = {'output_manifest.json', 'HANDOFF.md'}
    outputs = []
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and str(path.relative_to(OUT)) not in excluded:
            outputs.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    save(OUT / 'output_manifest.json', {'input_version': version, 'file_count': len(outputs), 'files': outputs,
         'excluded': ['output_manifest.json: self-reference', 'HANDOFF.md: Git binds handoff text, avoids circular manifest reference', '__pycache__: runtime cache'],
         'scope': 'Exact current delivery bytes; rerun offline steps then regenerate before validating after timestamp changes.'})
    print(json.dumps({'status': result['status'], 'input_files': len(local_inputs), 'output_files': len(outputs),
                      'velocity_rows': len(velocity_rows), 'parameter_updates': len(rows), 'sar_body_bytes': 192}, ensure_ascii=False))


if __name__ == '__main__':
    main()
