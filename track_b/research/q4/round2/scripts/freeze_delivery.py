#!/usr/bin/env python3
"""Freeze existing R2 evidence indices offline; never rebuild adopted geometry."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R = ROOT / 'track_b/research/q4/round2'
BASE = '76ee1532cb2acf36fb82c5f4749a4288507dfcc8'
MANIFEST = ROOT / 'track_b/audit/stage4/round2/baseline_manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path, **extra):
    return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
            'sha256': sha(path), **extra}


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    now = datetime.now(timezone.utc).isoformat()
    assert sha(MANIFEST) == 'c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d'
    context = {
        'input_version': {'baseline_commit': BASE, 'manifest_path': str(MANIFEST.relative_to(ROOT)),
                          'manifest_sha256': sha(MANIFEST), 'frozen_file_count': 565},
        'event_id': 'B20260826_Chhochen', 'physical_phase': 'retrospective_candidate_geometry_and_terrain_review',
        'time_utc': None, 'time_uncertainty': None,
        'space_object': {'geometry_version': 'q4-r2-fig1-candidates-v1',
                         'geometry_sha256': sha(R/'results/geometry_candidates.geojson'),
                         'candidate_crs': 'OGC:CRS84 assumed; EPSG:32645 for metric diagnostics',
                         'original_map_datum_verified': False, 'positional_uncertainty_m': None,
                         'event_geometry_accepted': False},
        'variable_semantics': {'coverage': 'valid-grid geometric support, not geographic truth or dynamics',
                               'units': 'metric diagnostics in metres and square metres; original raster vertical datum unknown',
                               'corridor_half_widths_m': [100, 250, 500],
                               'corridor_widths_are_error_bounds': False},
        'forecast_reference_time': None, 'issue_time': None, 'valid_time': None, 'available_time': None,
        'data_role': 'exploration', 'evidence_status': 'candidate',
        'null_policy': 'Unknown or unavailable; generation/retrieval dates are not event or historical availability times.'}
    notes_path = R/'sources/dem_provenance_notes.json'
    geo_path = R/'sources/independent_geography_review.json'
    notes = json.loads(notes_path.read_text())
    geography = json.loads(geo_path.read_text())
    # A startup verification entry in the original notes describes its read-time bytes;
    # the main operational report is overwritten by the mandatory exit verifier.
    dem_sources = {key: value for key, value in notes['sources'].items() if key != 'workspace_check'}
    source_register = {
        'schema_version': 'q4-r2-source-register-v1', 'generated_at_utc': now, **context,
        'register_scope': 'Source read/retrieval metadata only; external HTML payloads were not retained locally.',
        'source_record_files': [record(notes_path), record(geo_path)],
        'dem_local_and_paper_sources': dem_sources,
        'dem_bounded_external_trace': notes['bounded_external_trace'],
        'independent_geographic_sources': geography['sources'],
        'independent_directed_searches': geography['directed_searches'],
        'independent_http_attempts': geography['http_attempts'],
        'source_map_render': {
            'source': record(ROOT/'track_b/data/external/event_remote/jms_2026_uncorrected_proof.pdf'),
            'version': 'JMS uncorrected proof, DOI 10.1007/s11629-026-1482-y',
            'actual_visual_read_scope': 'PDF page6 Fig.1/caption and 300dpi panel-c and longitude-tick crops; no full visual paper review claimed',
            'render_dpi': 300, 'crop_origin_page_pixels_xy': [400, 880], 'crop_size_pixels_wh': [1730, 1120],
            'render_files': [record(R/'sources'/name) for name in
                             ['jms_page6_300dpi.png', 'jms_fig1c_crop_300dpi.png', 'jms_longitude_ticks_300dpi.png']],
            'read_time_record': 'results/search_aoi_evidence.json generated_at_utc records the early read/digitisation stage'},
        'startup_snapshot': record(R/'sources/startup_workspace_verification.json'),
        'advisor_relay': record(R/'sources/advisor_aoi_receipt.json'),
        'internal_review': record(R/'sources/independent_internal_review.json'),
        'omitted_mutable_record': 'dem_provenance_notes sources.workspace_check remains a historical read-time reference; use startup snapshot and final workspace_verification separately',
        'http_null_policy': 'No raw body/status supplied by search tools, or TLS before HTTP response, stays null; local byte counts never impersonate downloaded response sizes.'}
    save(R/'results/source_register.json', source_register)

    paths = {}
    for value in dem_sources.values():
        if value.get('path'):
            path = ROOT/value['path']
            paths[path] = 'frozen_source_or_protocol' if not path.is_relative_to(R) else 'local_execution_binding'
    external = [MANIFEST, ROOT/'track_b/config/stage4_contract.json', ROOT/'track_b/config/stage4_round2_contract.json',
                ROOT/'track_b/docs/16_stage4_round2_workflow.md', ROOT/'track_b/docs/15_stage4_round1_review.md',
                ROOT/'track_b/data/external/event_remote/pdf_preview/jms-06.png',
                ROOT/'track_b/data/processed/spatial/nc_glacier_mask.tif',
                ROOT/'track_b/research/q4/HANDOFF.md', ROOT/'track_b/research/q4/PROPOSALS.md']
    for path in external:
        paths[path] = 'frozen_source_or_protocol'
    for rel in ['TASK.md', 'config/map_digitisation.json', 'config/geometry_trace.json',
                'sources/jms_page6_300dpi.png', 'sources/jms_fig1c_crop_300dpi.png',
                'sources/jms_longitude_ticks_300dpi.png', 'results/georeference_review.json',
                'results/search_aoi.geojson', 'results/search_aoi_evidence.json']:
        paths[R/rel] = 'derived_round2_analysis_input' if rel != 'TASK.md' else 'frozen_task_protocol'
    input_manifest = {
        'schema_version': 'q4-r2-input-manifest-v1', 'generated_at_utc': now, **context,
        'scope': 'Direct inputs/protocols and explicitly labelled local derived analysis inputs; not the full 565-file baseline index',
        'files': [record(path, role=role) for path, role in sorted(paths.items())],
        'excluded': ['This manifest and other delivery indices', 'Mutable exit workspace_verification.json'],
        'self_included': False}
    save(R/'results/input_manifest.json', input_manifest)

    output_path = R/'results/output_manifest.json'
    files = [path for path in sorted(R.rglob('*'))
             if path.is_file() and path != output_path and '__pycache__' not in path.parts and path.suffix != '.pyc']
    output_manifest = {
        'schema_version': 'q4-r2-output-manifest-v1', 'generated_at_utc': now, **context,
        'scope': 'All delivered round2 files except this index and interpreter cache; includes source/input indices and exit report',
        'files': [record(path, role='protocol_or_binding' if path.name in ['TASK.md', 'workspace_binding.json', 'workspace_verification.json']
                        else 'round2_exploratory_artifact_or_source_record') for path in files],
        'file_count': len(files), 'self_included': False,
        'no_circular_hashes': 'Source register and input manifest do not reference output manifest; none indexes itself.'}
    save(output_path, output_manifest)
    print(json.dumps({'input_files': len(paths), 'output_files': len(files),
                      'output_manifest_sha256': sha(output_path), 'early_AOI_unchanged': sha(R/'results/search_aoi.geojson')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
