#!/usr/bin/env python3
"""Packet integrity and interface checks; never certify regional model accuracy.

Run provisional checks while queues run. Run final checks after integration and
workspace verification, then freeze_round3.py. --check-manifests is read-only.
"""
import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
EXPECTED_BASE_SHA = 'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'
SKIP_DIRS = {'venv', '.venv', '__pycache__', 'numba_cache', 'site-packages', '.git'}
CACHE = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4')
checks = []


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def resolve(path):
    p = Path(path)
    return p if p.is_absolute() else ROOT/p


def check(name, condition, details=None):
    checks.append({'name': name, 'passed': bool(condition), 'details': details})


def bound_file(record):
    p = resolve(record['path'])
    return p.is_file() and ('bytes' not in record or p.stat().st_size == record['bytes']) and sha(p) == record['sha256']


def bound_group(name, entries):
    bad = [entry['path'] for entry in entries if not bound_file(entry)]
    check(name, not bad, {'checked_files': len(entries), 'mismatches': bad})


def truth(value):
    return value is True or str(value).lower() == 'true'


def csv_rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def require_bundle(rel, expected):
    p = R/rel
    check('bundle_identity_'+rel, p.is_file() and sha(p) == expected, rel)
    if p.is_file():
        doc = read(p)
        bound_group('bundle_members_'+rel, doc['files'])
        check('no_self_entry_'+rel, all(resolve(f['path']) != p for f in doc['files']))


def immutable_packets():
    base = ROOT/'track_b/audit/stage4/round3/baseline_manifest.json'
    check('baseline_manifest_identity', sha(base) == EXPECTED_BASE_SHA)
    require_bundle('exports/geometry_bundle.json', '64cd8369ce79d599890d4ed726a87833b63f64472c4dbea54408e39e79a40561')
    require_bundle('exports/geometry_v1/bundle.json', '5a2315f807bac296e5ae9bf877e655499b7a2b40e39df8edd3b0cccbeade853a')
    require_bundle('exports/propagation_v1/bundle.json', 'aeafa98159440c675eaae00b2cbd7afec21b31b92a2511f8cb3ed988594ad9e7')
    require_bundle('exports/propagation_handoff_v1.json', 'ef63555c5decb383a66eeb01ef48a7cfe1c1a29ec52cd435a9ed55a801ba2c16')
    require_bundle('exports/propagation_v2/bundle.json', '2a54e77d811faa8d949f92a2e45788751122517b6e91839ca8742cda20ea88a4')
    require_bundle('exports/propagation_v3/bundle.json', '150c72537ee162d29cc2e20e3e31183df1915f64999234789e1875d368c09b9c')
    require_bundle('exports/propagation_handoff_v3.json', '9bb9fb3cd4242e728d22412dbea0191853307c7c647cf5bd3c607110053ccee1')
    require_bundle('exports/compact_delta_v1/bundle.json', '28c67deb49d694e992c005365cf19c73d1db31a89126f64dbe8b6973adba61cb')
    require_bundle('exports/propagation_v4/bundle.json', '9ae2ac6e93d6972b351f76fd1a441b5d6a670f7ffb842426bc1feeecc326fbf0')
    require_bundle('results/spatial_supplement_bundle_v2.json', '81273f2f7f19ff5e598674542504ed012d96c4db7766224b7299a8351fd027ff')
    require_bundle('results/reduced_delivery_index.json', 'cd82c52cc772ed7702a6f4452f4bfbbe5c9a092bbbeeed46d356d09709a4a7dc')
    for rel in ['results/reduced_delivery_index.json', 'results/spatial_source_index.json']:
        bound_group('cached_members_'+rel, read(R/rel)['cache_files'])
    for rel, expected in [
        ('inputs/q3/event_bundle_q3-r3-event-v1-local/bundle.json', 'b38711d8e34e7ab79a21a8856099aa5fb2bd003f31fdab4a5074b55337003724'),
        ('inputs/q2/release_bundle_q2-r3-release-v1/bundle.json', 'ed745576ff706a4d82a560269b0e07804add6fc9bde2b3948cced43932ddf5b5'),
        ('inputs/q2/release_bundle_v2_q2-r3-release-v2-spatial-copdem-v1/bundle.json', '108ce2d34289fe3c5cdb5dacf6927bf977439bd9f06b959ff931f7d06b57f683'),
        ('inputs/q2/composition_bundle_q2-r3-literature-composition-v1/bundle.json', 'c8fb79484b4455ab5b64d4099fedcd0a9945ff8da6e00e30b44b51648ef54b4c')]:
        require_bundle(rel, expected)

    alias = read(R/'sources/spatial_target_schema_revision.json')
    old = alias['historical_binding']
    current = alias['current_binding']
    old_path = resolve(old['preserved_exact_bytes_path'])
    new_path = resolve(current['path'])
    check('historical_target_schema_alias_exact_bytes', sha(old_path) == old['sha256'] == old['preserved_sha256'])
    check('current_target_schema_exact_bytes', bound_file(current))
    a, b = csv_rows(old_path), csv_rows(new_path)
    check('target_alias_original_columns_and_order_unchanged', len(a) == len(b) == 5 and all(
        all(row[k] == new[k] for k in row) for row, new in zip(a, b)),
        'Explicit schema-only alias; original path old hash does NOT pass and is not asserted unchanged.')


def spatial_and_release():
    for dx, shape in [(60, (154, 300)), (120, (77, 150))]:
        with np.load(R/f'results/spatial_inputs_{dx}m.npz') as d:
            mask = d['source_mask'].astype(bool)
            check(f'grid_{dx}_finite_shape', d['z'].shape == shape and np.isfinite(d['z']).all())
            check(f'grid_{dx}_source_support', int(mask.sum()) == {60: 257, 120: 67}[dx])
    geo = read(R/'results/computational_geometries.geojson')
    check('computational_geojson_crs84_not_projected_numbers', 'crs' not in geo and all(
        -180 <= xy[0] <= 180 and -90 <= xy[1] <= 90
        for f in geo['features'] for xy in coordinate_pairs(f['geometry']['coordinates'])))
    mapping = read(R/'results/q2_release_mapping.json')
    bound_group('q2_mapping_input_and_geometry_hashes', [mapping[k] for k in ['protocol', 'upstream_bundle', 'source_geometry', 'mapped_geometries']])
    for row in mapping['releases']:
        sid = row['scenario_id']
        check('q2_exact_plan_area_'+sid, abs(row['actual_polygon_area_m2']/row['source_plan_area_m2']-1) < 1e-9)
        check('q2_vertical_thickness_volume_'+sid, abs(row['source_plan_area_m2']*row['thickness_vertical_m']/row['upstream_release_volume_m3']-1) < 1e-10)
        check('q2_grid_integrated_volume_'+sid, abs(row['grid_volume_relative_error']) < 1e-7)
        fractions = row['phase_fractions']
        density = fractions['rock']*2700 + fractions['ice']*917 + fractions['free_water']*1000
        check('q2_volume_fraction_and_density_'+sid, row['phase_fraction_basis'] == 'volume' and
              abs(sum(fractions.values())-1) < 1e-12 and abs(density-row['bulk_density_kg_m3']) < 1e-8)
        check('q2_never_crossed_is_if_released_'+sid, row['upstream_onset_status'] != 'never_crossed' or row['if_released_propagation'])
        check('q2_time_origin_unknown_delay_'+sid, row['initiation_to_release_delay_seconds'] is None and row['not_an_initiation_prediction'])
        bound_group('q2_release_files_'+sid, [row['release_raster'], row['release_arrays']])
    extension = read(R/'results/extended_domain_bundle.json')
    bound_group('extended_domain_files', extension['files'])
    check('extension_preserves_core', extension['core_dem_exactly_preserved'] and extension['shape'] == [245, 318])


def coordinate_pairs(coords):
    if coords and isinstance(coords[0], (int, float)):
        yield coords
    else:
        for part in coords:
            yield from coordinate_pairs(part)


def model_interface(provisional):
    runs = csv_rows(R/'results/model_runs.csv')
    arrivals = csv_rows(R/'results/target_arrivals.csv')
    check('unique_run_identifiers', len({row['run_id'] for row in runs}) == len(runs), len(runs))
    run_ids = {row['run_id'] for row in runs}
    check('arrival_run_foreign_keys', all(row['run_id'] in run_ids for row in arrivals), len(arrivals))
    check('reduced_not_used_for_arrival_envelope', all(not truth(row['include_in_arrival_envelope'])
          for row in runs if row['producer'] == 'reduced'))
    check('unqualified_or_boundary_affected_not_used_for_arrival_envelope', all(
        not truth(row['include_in_arrival_envelope']) for row in arrivals if
        truth(row['domain_affected_before_arrival']) or 'quarantin' in row['arrival_status'] or
        row['model_id'].startswith('independent_')))
    check('mechanical_initiation_delay_stays_unknown', all(
        row['initiation_to_release_delay_seconds'] in ['', 'null', 'None'] for row in arrivals))
    check('no_imputed_probability_weights', all(row['probability_weight'] in ['', 'null', 'None'] for row in arrivals))
    check('no_claimed_event_timing_validation', all(not truth(row['event_timing_validated']) for row in arrivals))
    check('missing_or_not_arrived_stays_null', all(row['travel_time_seconds'] in ['', 'null', 'None']
          for row in arrivals if row['arrival_status'] in ['missing', 'not_arrived_by_horizon']))
    check('q2_no_start_rows_remain_conditional', all(truth(row['if_released_propagation']) for row in arrivals
          if row.get('upstream_onset_status') == 'never_crossed'))
    check('quarantined_runs_excluded', all(not truth(row['include_in_scientific_parameter_comparison']) and
          not truth(row['include_in_arrival_envelope']) for row in runs if 'quarantin' in row['execution_status']))

    fields = read(R/'results/official_fields.json')['fields']
    bound_group('native_process_field_hashes', fields)
    invalid_times, invalid_shapes = [], []
    for record in fields:
        with np.load(resolve(record['path'])) as d:
            t = d['time_s']
            if not (t.ndim == 1 and np.isfinite(t).all() and len(t) and np.all(np.diff(t) > 0)):
                invalid_times.append(record['run_id'])
            h = d['depth_frames']
            if not (h.ndim == 3 and h.shape[0] == len(t) and np.isfinite(h).all() and
                    np.nanmin(h) >= -1e-7 and len(d['transform']) >= 6):
                invalid_shapes.append(record['run_id'])
    check('native_times_from_native_arrays_monotonic', not invalid_times, invalid_times)
    check('native_fields_finite_nonnegative_and_georeferenced', not invalid_shapes, invalid_shapes)
    summary = read(R/'results/comparison_summary.json')
    check('integration_read_consistent', not summary['source_inputs_changed_during_read'])
    check('zero_independent_event_validation', summary['independent_local_validation_events'] == 0)
    app = summary['registered_applicability_completion']
    check('registered_and_applicable_scope_explicit', app['registered_conditional_count'] == 38 and
          app['applicable_required_count'] == 30 and app['quarantined_not_run_count'] == 7)
    control_index = read(R/'results/official_native_control_index.json')
    control_files = [f for row in control_index['runs'] for f in row['native_input_controls']]
    bound_group('actual_saved_native_controls_not_reconstructed_runner', control_files)
    adapters = [{'path': row['saved_executed_adapter_path'], 'sha256': row['saved_executed_adapter_sha256']}
                for row in control_index['runs'] if row.get('saved_executed_adapter_path')]
    bound_group('saved_execution_start_adapter_snapshots', adapters)
    fixes = [f for f in fields if f.get('solver_build') == 'explicit_resourcefix_build']
    check('resourcefix_binary_identity_explicit', len(fixes) == 5 and all(
          f['actual_binary_sha256'] == '45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c' and
          f['executed_solver_source_modified'] and f['readonly_addon_mount'] for f in fixes))
    if not provisional:
        check('integration_final', summary['status'] == 'frozen_for_joint_review')
        check('all_current_registered_runs_settled', not summary['current_pending_runs'], summary['current_pending_runs'])
        check('all_actual_attempts_settled', not summary['actual_attempts_unsettled'], summary['actual_attempts_unsettled'])
        bound_group('final_integration_inputs_still_match_read_time_bytes',
                    read(R/'results/comparison_input_index.json')['files'])
        bundle_path = R/'exports/propagation_bundle.json'
        check('propagation_export_exists', bundle_path.exists())
        if bundle_path.exists():
            bundle = read(bundle_path)
            version = re.fullmatch(r'q4-r3-propagation-v(\d+)', bundle.get('bundle_version', ''))
            check('final_propagation_version_v4_or_higher', version is not None and int(version.group(1)) >= 4)
            check('final_propagation_status', bundle.get('status') == 'frozen_for_joint_review' and
                  bundle.get('partial') is False and bundle.get('all_routes_completed') is True)
            check('floating_export_matches_frozen_v4', sha(bundle_path) == sha(R/'exports/propagation_v4/bundle.json'))
            bound_group('propagation_export_members', bundle['files'])
            check('propagation_export_not_self_indexed', all(resolve(f['path']) != bundle_path for f in bundle['files']))
            check('propagation_input_version_structured', isinstance(bundle['input_version'], dict) and
                  bundle['input_version'].get('baseline_manifest_sha256') == EXPECTED_BASE_SHA and
                  bundle['input_version'].get('baseline_commit') == '904d7257b899b9f71d1ac9e0eab7479e459eab52')
            # A valid old early packet must not pass with a new final root summary.
            for name in ['model_runs', 'comparison_metrics', 'target_arrivals']:
                exported = resolve(bundle['table_paths'][name])
                check('final_export_matches_root_'+name, sha(exported) == sha(R/f'results/{name}.csv'))
        decision = read(R/'config/scientific_acceptance_decision_05.json')
        accepted = set(decision['accepted_arrival_envelope_run_ids'])
        check('scientific_acceptance_list_is_explicit', not accepted)
        check('no_unaccepted_arrival_envelope_runs', all(not truth(row['include_in_arrival_envelope']) or
              row['run_id'] in accepted for row in runs))
        check('no_unaccepted_arrival_envelope_targets', all(not truth(row['include_in_arrival_envelope']) or
              row['run_id'] in accepted for row in arrivals))
    return summary


def manifests():
    for name in ['source_register', 'input_manifest', 'cache_manifest', 'output_manifest']:
        p = R/f'results/{name}.json'
        doc = read(p)
        entries = doc.get('files', doc.get('records', []))
        entries = entries + doc.get('subpacket_source_indices', [])
        check(name+'_no_self', not any(resolve(f['path']) == p for f in entries))
        check(name+'_unique_paths', len({f['path'] for f in entries}) == len(entries))
        bound_group(name+'_bytes', entries)
        if 'file_count' in doc:
            check(name+'_count', len(entries) == doc['file_count'])
    for name, base, exclude_symlinks in [('output_manifest', R, False), ('cache_manifest', CACHE, True)]:
        index_path = R/f'results/{name}.json'
        indexed = {resolve(f['path']) for f in read(index_path)['files']}
        actual = {p for p in base.rglob('*') if p.is_file() and p != index_path and
                  not (exclude_symlinks and p.is_symlink()) and
                  not any(part in SKIP_DIRS for part in p.parts) and p.suffix not in ['.pyc', '.nbi', '.nbc']}
        check(name+'_complete_path_set', indexed == actual,
              {'unindexed': sorted(str(p) for p in actual-indexed),
               'listed_but_absent': sorted(str(p) for p in indexed-actual)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--provisional', action='store_true')
    mode.add_argument('--check-manifests', action='store_true', help='Read-only verification after freeze; no packet writes')
    mode.add_argument('--read-only-final', action='store_true', help='All final checks without rewriting validation.json')
    args = parser.parse_args()
    if args.check_manifests:
        manifests()
    else:
        immutable_packets()
        spatial_and_release()
        summary = model_interface(args.provisional)
        for p in sorted((R/'scripts').glob('*.py')):
            try:
                ast.parse(p.read_text())
                parsed = True
            except SyntaxError:
                parsed = False
            check('python_AST_'+p.name, parsed)
        startup = read(R/'sources/startup_workspace_verification.json')
        check('startup_five_groups_passed', startup['passed'])
        if not args.provisional:
            check('exit_five_groups_passed', read(R/'workspace_verification.json')['passed'])
            for rel in ['MODEL_COMPARISON.md', 'HANDOFF.md', 'REPRODUCE.md', 'PAPER_OUTLINE.md', 'QUESTION_REQUIREMENT_MAP.md']:
                check('final_document_'+rel, (R/rel).is_file() and '未执行模板' not in (R/rel).read_text())
            review = read(R/'results/comparison_visual_review.json')
            bound_group('root_figures_actually_reviewed_and_unchanged', review['figures'])
            check('root_figures_manual_open_recorded', all(row.get('actual_opened') is True for row in review['figures']))
            check('root_figure_review_complete', {resolve(row['path']) for row in review['figures']} ==
                  set((R/'figures').glob('comparison_*.png')))
    report = {'schema_version': 'q4-r3-packet-validation-v1', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'provisional' if args.provisional else 'read_only_manifests' if args.check_manifests else 'final_read_only' if args.read_only_final else 'final',
              'all_artifact_and_interface_checks_passed': all(c['passed'] for c in checks),
              'checks': checks, 'check_count': len(checks),
              'scientific_scope': 'Integrity, finite outputs and honest interfaces; does not certify physical model correctness or regional accuracy.',
              'independent_local_event_validation_count': 0,
              'known_numerical_failures_retained_separately': 'results/numerical_validation.json',
              'regional_accuracy_qualified': False, 'human_scientific_adoption': 'pending_team_review'}
    if not args.check_manifests:
        report['validated_root_bindings'] = [
            {'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
            for p in [R/'results/comparison_summary.json', R/'results/model_runs.csv',
                      R/'results/comparison_metrics.csv', R/'results/target_arrivals.csv',
                      R/'results/official_fields.json', R/'results/comparison_input_index.json',
                      R/'config/scientific_acceptance_decision_05.json',
                      R/'exports/propagation_bundle.json', R/'results/comparison_visual_review.json',
                      R/'scripts/validate_round3.py', R/'scripts/freeze_round3.py']]
    if not args.check_manifests and not args.read_only_final:
        target = R/'results'/('validation_provisional.json' if args.provisional else 'validation.json')
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'passed': report['all_artifact_and_interface_checks_passed'], 'checks': len(checks),
                      'failed': [c for c in checks if not c['passed']]}, ensure_ascii=False))
    raise SystemExit(0 if report['all_artifact_and_interface_checks_passed'] else 1)


if __name__ == '__main__':
    main()
