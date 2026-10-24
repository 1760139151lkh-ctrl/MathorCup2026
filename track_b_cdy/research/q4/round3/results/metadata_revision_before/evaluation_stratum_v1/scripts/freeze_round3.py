#!/usr/bin/env python3
"""Freeze final packet and scientific cache bytes offline, after computations stop."""
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
CACHE = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4')
BASE = ROOT/'track_b/audit/stage4/round3/baseline_manifest.json'
BASE_SHA = 'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'
SKIP_DIRS = {'venv', '.venv', '__pycache__', 'numba_cache', 'site-packages', '.git'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def entry(path, role):
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': path.stat().st_size, 'sha256': sha(path), 'role': role}


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def context():
    return {'input_version': {'baseline_commit': '904d7257b899b9f71d1ac9e0eab7479e459eab52',
                              'baseline_manifest_sha256': BASE_SHA, 'frozen_file_count': 725},
            'event_id': 'B20260826_Chhochen', 'physical_phase': 'bulk_release_propagation_and_target_arrival',
            'time_utc': None, 'time_uncertainty': None,
            'space_object': {'primary_geometry_version': 'q4-r3-spatial-copdem-v1',
                             'position_uncertainty_m': None, 'event_truth_accepted': False},
            'variable_semantics': {'units': 'm, m/s, seconds after bulk release, m3, kg; model-specific definitions retained',
                                   'forecast_role': 'not a forecast of mechanical initiation'},
            'forecast_reference_time': None, 'issue_time': None, 'valid_time': None, 'available_time': None,
            'data_role': 'scenario', 'evidence_status': 'candidate',
            'evaluation_stratum': 'conditional_scenario; local products/external_transfer/numerical_benchmark individually labelled',
            'initiation_to_release_delay_seconds': None, 'human_scientific_adoption': 'pending_team_review'}


def main():
    assert sha(BASE) == BASE_SHA
    summary = json.loads((R/'results/comparison_summary.json').read_text())
    assert summary['status'] == 'frozen_for_joint_review', 'Refuse to freeze a rolling integration'
    assert not summary['current_pending_runs'] and not summary['actual_attempts_unsettled'], 'Native attempts must settle first'
    validation = json.loads((R/'results/validation.json').read_text())
    assert validation['status'] == 'final' and validation['all_artifact_and_interface_checks_passed'], 'Final validation must pass first'
    assert json.loads((R/'workspace_verification.json').read_text())['passed'], 'Exit workspace verification must pass first'
    for row in validation['validated_root_bindings']:
        p = ROOT/row['path']
        assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], f'Post-validation change: {p}'
    def stamps(base):
        return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in base.rglob('*')
                if p.is_file() and not p.is_symlink() and not any(part in SKIP_DIRS for part in p.parts)
                and p.suffix not in ['.pyc', '.nbi', '.nbc'] and
                not (p.parent == R/'results' and p.name in ['cache_manifest.json', 'source_register.json', 'input_manifest.json', 'output_manifest.json'])}
    cache_before = stamps(CACHE)
    packet_before = stamps(R)
    # Recheck the actual bound bytes, not only their index hashes. This does not
    # rewrite validation.json or any packet member.
    subprocess.run([sys.executable, str(R/'scripts/validate_round3.py'), '--read-only-final'],
                   check=True, cwd=ROOT)
    now = datetime.now(timezone.utc).isoformat()
    cache_files = []
    for path in sorted(CACHE.rglob('*')):
        if not path.is_file() or path.is_symlink() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in ['.pyc', '.nbi', '.nbc']:
            continue
        relative = path.relative_to(CACHE)
        role = 'scientific_cache_input_or_source' if relative.parts[0] == 'spatial' or 'inputs' in relative.parts else 'model_artifact_or_execution_diagnostic'
        cache_files.append(entry(path, role))
    assert cache_before == stamps(CACHE), 'Scientific cache changed during freeze; stop writers before retrying'
    save(R/'results/cache_manifest.json', {
        'schema_version': 'q4-r3-cache-manifest-v1', 'generated_at_utc': now, **context(),
        'files': cache_files, 'file_count': len(cache_files),
        'total_bytes': sum(f['bytes'] for f in cache_files),
        'scope': 'Q4-owned scientific inputs, outputs, logs and rejected diagnostics; not evidence that every prepared case executed',
        'excluded': sorted(SKIP_DIRS)+['compiled Python/Numba cache', 'runtime owned by main advisor; exact source/image recorded separately'],
        'self_included': False})

    sources = [entry(path, 'source_record_or_read_time_receipt') for path in sorted((R/'sources').glob('*')) if path.is_file()]
    subindices = [R/'results'/name for name in ['spatial_source_index.json', 'spatial_supplement_bundle_v2.json',
                  'reduced_delivery_index.json', 'official_fields.json'] if (R/'results'/name).exists()]
    save(R/'results/source_register.json', {
        'schema_version': 'q4-r3-source-register-v1', 'generated_at_utc': now, **context(),
        'records': sources, 'subpacket_source_indices': [entry(p, 'source_or_artifact_subindex') for p in subindices],
        'source_metadata_policy': 'Canonical URL/product/version/retrieval UTC/actual read scope/bytes/hash and availability are in individually bound records; null is not acceptance.',
        'scientific_source_limitations': ['No accepted independent local event validation',
                                        'Optical47day vegetation-change screen is not event truth',
                                        'OSM edit date is not observation/historical availability',
                                        'Raw failed/rejected diagnostics retained with explicit status'],
        'self_included': False})

    direct = {BASE: 'frozen_baseline_manifest'}
    for rel in ['track_b/config/stage4_contract.json', 'track_b/config/stage4_round3_contract.json',
                'track_b/docs/18_stage4_round3_workflow.md', 'track_b/data/external/event_remote/jms_2026_uncorrected_proof.pdf',
                'track_b/data/processed/spatial/dem_utm45_30m.tif', 'track_b/research/q4/round2/results/geometry_candidates.geojson',
                'track_b/research/q4/round2/results/search_aoi.geojson']:
        direct[ROOT/rel] = 'frozen_inherited_direct_input_or_protocol'
    for folder, role in [('inputs', 'advisor_delivered_immutable_input'), ('config', 'registered_experiment_or_environment_definition')]:
        for path in (R/folder).rglob('*'):
            if path.is_file() and not any(part in SKIP_DIRS for part in path.parts):
                direct[path] = role
    for rel in ['results/computational_geometries.geojson', 'results/terrain_bundle.json',
                'results/spatial_inputs_60m.npz', 'results/spatial_inputs_120m.npz',
                'results/spatial_paths.csv', 'results/spatial_targets_v2.csv',
                'results/spatial_targets_v2_initial.csv', 'results/q2_release_mapping.json',
                'results/extended_domain_bundle.json']:
        if (R/rel).exists():
            direct[R/rel] = 'versioned_derived_model_input'
    for f in cache_files:
        path = Path(f['path'])
        if 'spatial' in path.relative_to(CACHE).parts[:1] or 'inputs' in path.relative_to(CACHE).parts or 'integrated_inputs' in path.relative_to(CACHE).parts[:1]:
            direct[path] = 'new_cached_model_input_or_source'
    save(R/'results/input_manifest.json', {
        'schema_version': 'q4-r3-input-manifest-v1', 'generated_at_utc': now, **context(),
        'files': [entry(path, role) for path, role in sorted(direct.items())],
        'file_count': len(direct), 'self_included': False,
        'scope': 'Direct inherited inputs, approved cross-question copies, protocols and derived/new cached inputs; full inherited725 inputs checked by workspace verifier',
        'read_time_schema_alias': 'sources/spatial_target_schema_revision.json preserves old962021... CSV bytes separately; no false claim original path stayed unchanged.'})

    out = R/'results/output_manifest.json'
    files = [path for path in sorted(R.rglob('*')) if path.is_file() and path != out
             and not any(part in SKIP_DIRS for part in path.parts) and path.suffix not in ['.pyc', '.nbi', '.nbc']]
    save(out, {'schema_version': 'q4-r3-output-manifest-v1', 'generated_at_utc': now, **context(),
               'files': [entry(path, 'round3_packet_artifact_input_or_protocol') for path in files],
               'file_count': len(files), 'self_included': False,
               'cache_index': 'results/cache_manifest.json',
               'scope': 'All round3 packet files except this self-index and interpreter caches; scientific cached bytes indexed separately; manifests do not index themselves.'})
    assert cache_before == stamps(CACHE), 'Scientific cache changed during manifest assembly'
    assert packet_before == stamps(R), 'Packet writer changed non-manifest files during freeze'
    print(json.dumps({'packet_files': len(files), 'cached_files': len(cache_files),
                      'cache_bytes': sum(f['bytes'] for f in cache_files), 'input_files': len(direct),
                      'output_manifest_sha256': sha(out)}))


if __name__ == '__main__':
    main()
