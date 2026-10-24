#!/usr/bin/env python3
"""Audit full-source Q2 geometry-v2/Q4 propagation-v3 without rerunning physics.

Passing adapter QA does not qualify the numerical model or create arrival truth.
Only the two registered model replacements below are accepted. No fuzzy joins.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

R = Path(__file__).resolve().parents[1]
ROOT = R.parents[3]
CACHE = Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q4/official')
PIN = '8457a9db624c33c0d0988ad8f4d8c8513ff21ac858ccff830bae577f77f0b683'
PRODUCER_PIN = '150c72537ee162d29cc2e20e3e31183df1915f64999234789e1875d368c09b9c'
DEFAULT_BUNDLE = R / 'inputs/q4/bundle_q4-r3-propagation-v3/bundle.json'
DEFAULT_OUT = R / 'results/arrival/propagation_v3'
MODEL_REPLACEMENTS = {
    'q2r3_S_v1': ('S', 'q2r3_S_analytic_v1'),
    'q2r3_ST_v1': ('S_T', 'q2r3_S_T_analytic_v1'),
}
PARAMETER_VERSION = 'q2r3-design-v1'
MAPPING_VERSION = 'q2-r3-release-v2-spatial-copdem-v1'
GEOMETRY_VERSION = 'q4-r3-spatial-copdem-v1'
PHYSICAL_FIELDS = [
    'theta_deg', 'thickness_normal_m', 'rock_volume_fraction', 'bridge_fraction',
    'bridge_cohesion_kpa', 'rock_mu', 'initial_temp_c', 'diffusivity_m2_s',
    'interface_depth_m', 'station_source_offset_c', 'storativity', 'drainage_hours',
    'connected_depth_m', 'rain_multiplier', 'melt_mm_deg_day', 'damage_rate_h_inv',
    'damage_exponent', 'initial_damage', 'drainage_damage_coupling', 'density_kg_m3',
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(path, data, columns=None):
    if columns is None:
        columns = list(dict.fromkeys(k for row in data for k in row))
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)


def present(value):
    return value is not None and str(value).strip() != ''


def flag(value):
    return value is True or str(value).lower() == 'true'


def number(value):
    return float(value) if present(value) else None


def close(a, b, rtol=1e-10, atol=1e-10):
    return math.isclose(float(a), float(b), rel_tol=rtol, abs_tol=atol)


def unique(data, **keys):
    found = [x for x in data if all(x.get(k) == v for k, v in keys.items())]
    if len(found) != 1:
        raise ValueError(f'Expected one exact row for {keys}, got {len(found)}')
    return found[0]


def resolve(path):
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def relative(path):
    p = Path(path)
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def file_record(path, role):
    p = Path(path)
    return dict(path=relative(p), bytes=p.stat().st_size, sha256=sha(p), role=role)


def support_distance(x, y, rectangles):
    """Euclidean point distance to a union of actual release raster cell boxes."""
    answer = np.full(np.asarray(x).shape, np.inf, dtype=float)
    for xmin, xmax, ymin, ymax in rectangles:
        dx = np.maximum(np.maximum(xmin - x, x - xmax), 0)
        dy = np.maximum(np.maximum(ymin - y, y - ymax), 0)
        answer = np.minimum(answer, np.hypot(dx, dy))
    return answer


def saved_first_hit(time, depth, mask, horizon):
    eligible = np.isfinite(time) & (time <= horizon)
    at = np.flatnonzero(eligible)
    if not mask.any():
        return dict(status='no_registered_cell_centres_in_buffer', hit=False,
                    lower=None, upper=None, last_saved=None, cells=0)
    hits = np.any(depth[:, mask] >= 0.1, axis=1)
    found = at[hits[at]]
    first = int(found[0]) if len(found) else None
    return dict(status=('already_inundated_at_initial_saved_state' if first == 0 else
                        'arrived_at_saved_output' if first is not None else
                        'not_arrived_at_saved_outputs_through_horizon'),
                hit=first is not None,
                lower=float(time[first - 1]) if first is not None and first > 0 else None,
                upper=float(time[first]) if first is not None else None,
                last_saved=float(time[at[-1]]) if len(at) else None,
                cells=int(mask.sum()))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--bundle', default=str(DEFAULT_BUNDLE))
    cli.add_argument('--expected-sha256', default=PIN)
    cli.add_argument('--outdir', default=str(DEFAULT_OUT))
    args = cli.parse_args()
    bp, out = Path(args.bundle).resolve(), Path(args.outdir).resolve()
    if bp != DEFAULT_BUNDLE or out != DEFAULT_OUT or args.expected_sha256 != PIN or sha(bp) != PIN:
        raise ValueError('Unregistered packet or output scope')
    if not (out / 'PROTOCOL.md').exists():
        raise ValueError('Retain the registered protocol before computation')
    checks, input_by_path, roles = [], {}, {}

    def check(name, passed, detail=None):
        record = dict(name=name, passed=bool(passed))
        if detail is not None:
            record['detail'] = detail
        checks.append(record)
        if not passed:
            raise ValueError(f'Adapter check failed: {name}; {detail}')

    def add_input(path, role):
        p = Path(path).resolve()
        entry = file_record(p, role)
        key = str(p)
        if key in input_by_path:
            current = input_by_path[key]
            check('repeated_input_binding:' + relative(p),
                  entry['sha256'] == current['sha256'] and entry['bytes'] == current['bytes'])
            if role not in current['roles']:
                current['roles'].append(role)
        else:
            entry['roles'] = [role]
            del entry['role']
            input_by_path[key] = entry
        return p

    add_input(bp, 'pinned imported Q4 packet')
    producer_path = bp.parent / 'upstream_bundle.json'
    check('producer_packet_pin', sha(producer_path) == PRODUCER_PIN)
    add_input(producer_path, 'pinned producer packet snapshot; no producer path access')
    bundle = read_json(bp)
    check('advisor_review_binds_producer', bundle['advisor_review']['upstream_bundle_sha256'] == PRODUCER_PIN)
    check('66_unique_delivered_role_objects', len(bundle['files']) == len({f['path'] for f in bundle['files']}) == 66)
    for f in bundle['files']:
        p = resolve(f['path']).resolve()
        allowed = p.is_relative_to(bp.parent) or (p.is_relative_to(CACHE) and
                  f.get('storage') == 'immutable_external_cache')
        check('approved_delivered_path:' + relative(p), allowed)
        check('delivered_hash:' + relative(p), p.stat().st_size == f['bytes'] and sha(p) == f['sha256'])
        roles.setdefault(f['role'], []).append(p)
        add_input(p, f['role'])

    def one_role(name):
        found = roles.get(name, [])
        check('one_role:' + name, len(found) == 1)
        return found[0]

    run_path, target_path, metric_path = map(one_role, ['model_runs', 'target_arrivals', 'comparison_metrics'])
    export = run_path.parent
    runs, targets, metrics = rows(run_path), rows(target_path), rows(metric_path)
    check('three_selected_runs', len(runs) == 3 and
          set(x['run_id'] for x in runs) == set(bundle['selected_run_ids']))
    check('21_unique_run_target_rows', len(targets) == len({(x['run_id'], x['target_id']) for x in targets}) == 21 and
          len({x['target_id'] for x in targets}) == 7)
    check('two_base_scenarios_no_statistical_weights', len({x['base_scenario_id'] for x in runs}) == 2 and
          bundle['probability_weights'] is None and bundle['independent_local_validation_events'] == 0)
    decision = read_json(export / 'quality/scientific_acceptance_decision_05.json')
    check('empty_accepted_envelope_list', decision['accepted_arrival_envelope_run_ids'] ==
          bundle['accepted_arrival_envelope_run_ids'] == [])
    check('decision05_false_qualification', all(decision[k] is False and bundle[k] is False
          for k in ['scientifically_qualified_for_prediction', 'mass_conservation_qualified', 'regional_accuracy_qualified']))
    protocol = read_json(export / 'provenance/fullmask_registration/q2_fullmask_integration_protocol.json')
    check('fullmask_preregistered_selection', protocol['before_selected_fullmask_propagation'] is True and
          set(protocol['selected_scenario_ids']) == {x['scenario_id'] for x in runs} and
          protocol['release_mapping_version'] == MAPPING_VERSION and protocol['geometry_version'] == GEOMETRY_VERSION)

    fullroot = R / 'inputs/q2/release_bundle_v2_q2-r3-release-v2-spatial-copdem-v1'
    originalroot = R / 'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1'
    analyticroot = R / 'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1'
    full_manifest_path = add_input(fullroot / 'bundle.json', 'frozen Q3-imported Q2 geometry-v2 manifest')
    full_manifest = read_json(full_manifest_path)
    fullpath = fullroot / 'files/results/release_states_geometry_v2.csv'
    copied_fullpath = export / 'provenance/upstream_q2_fullmask/release_states_geometry_v2.csv'
    copied_manifest_path = export / 'provenance/upstream_q2_fullmask/bundle.json'
    copied_manifest = read_json(copied_manifest_path)
    check('fullmask_received_bundle_matches_registration', sha(copied_manifest_path) == protocol['upstream_bundle_sha256'])
    check('copied_and_Q3_frozen_release_tables_identical', sha(fullpath) == sha(copied_fullpath) ==
          unique(full_manifest['files'], role='release_states_geometry_v2')['sha256'] ==
          unique(copied_manifest['files'], role='release_states_geometry_v2')['sha256'])
    add_input(fullpath, 'frozen Q3 fullmask release table byte-identical to Q4 copied source')
    pp = originalroot / 'files/results/parameter_ensemble.csv'
    ap = analyticroot / 'files/results/analytic_thermal/parameter_ensemble.csv'
    cp = analyticroot / 'files/results/analytic_thermal/mechanism_contract.json'
    fp = R / 'results/engine_a/analytic_erfc/first_passages.csv'
    for manifestroot, required in [(originalroot, [pp]), (analyticroot, [ap, cp])]:
        manifest = read_json(add_input(manifestroot / 'bundle.json', 'frozen imported mechanism manifest'))
        for p in required:
            entries = [f for f in manifest['files'] if resolve(f['path']).resolve() == p.resolve()]
            check('existing_import_hash:' + relative(p), len(entries) == 1 and
                  p.stat().st_size == entries[0]['bytes'] and sha(p) == entries[0]['sha256'])
            add_input(p, 'frozen original/analytic parameters and explicit join contract')
    add_input(fp, 'frozen actual analytic-erfc first-passage results')
    contract = read_json(cp)
    check('analytic_contract_preserves_release_and_base_join', contract['parameter_version'] == PARAMETER_VERSION and
          contract['base_scenario_join'] == 'base_scenario_id joins v1/v2 and release-geometry-v2; release states unchanged, use this model version onset/censoring when combined')
    fullrows, oldpars, newpars, onsets = rows(fullpath), rows(pp), rows(ap), rows(fp)
    compact_audit_path = add_input(R / 'results/arrival/propagation_v2/release_mapping_audit.csv', 'frozen compact-source v2 descriptive comparison only')
    compact_arrival_path = add_input(R / 'results/arrival/propagation_v2/conditional_arrivals.csv', 'frozen compact-source target diagnostics; different source experiment')
    compact_audits, compact_targets = rows(compact_audit_path), rows(compact_arrival_path)
    lineage_audit, parameter_audit, volume_audit, joined, target_audit, footprints, comparison, arrays = ([] for _ in range(8))

    import rasterio
    from pyproj import Transformer
    projection = Transformer.from_crs('EPSG:4326', 'EPSG:32645', always_xy=True)
    points = {x['target_id']: (float(x['x_m']), float(x['y_m']), x['geometry_version'])
              for x in rows(export / 'geometry/spatial_targets_v2.csv')}
    geom = read_json(export / 'geometry/computational_geometries.geojson')
    check('GeoJSON_coordinate_semantics', geom['crs_note'] == 'GeoJSON CRS84 longitude/latitude; distances in EPSG32645')
    for f in geom['features']:
        if f['geometry']['type'] == 'Point':
            tx, ty = projection.transform(*f['geometry']['coordinates'])
            points[f['properties']['space_id']] = (tx, ty, f['properties']['geometry_version'])

    for run in runs:
        rid, scenario, base = run['run_id'], run['scenario_id'], run['base_scenario_id']
        line = unique(bundle['lineage_by_run'], run_id=rid)
        case_path = export / f'provenance/{rid}/case.json'
        case = read_json(case_path)
        release = unique(fullrows, scenario_id=scenario, base_scenario_id=base)
        registered = unique(protocol['records'], scenario_id=scenario, base_scenario_id=base)
        embedded = case['upstream_fullmask_record']
        old = unique(oldpars, scenario_id=base)
        check('registered_model_replacement:' + rid, old['model_id'] in MODEL_REPLACEMENTS)
        mechanism, analytic_model = MODEL_REPLACEMENTS[old['model_id']]
        check('analytic_model_contract:' + rid, contract['model_ids'][mechanism] == analytic_model)
        new = unique(newpars, base_scenario_id=base, model_id=analytic_model)
        onset = unique(onsets, base_scenario_id=base, model_id=analytic_model, mechanism_id=mechanism,
                       parameter_version=PARAMETER_VERSION, geometry_version=old['geometry_version'])
        check('full_release_keys_exact:' + rid, all(
            release[k] == registered[k] == embedded[k] for k in ['scenario_id', 'base_scenario_id',
                'model_id', 'mechanism_id', 'parameter_version', 'geometry_version', 'release_mapping_version',
                'parameter_set_id', 'grid_resolution_m']))
        check('bundle_run_lineage_exact:' + rid, all(run[k] == line[k] for k in [
            'scenario_id', 'base_scenario_id', 'upstream_model_id', 'upstream_parameter_version',
            'mechanism_id', 'parameter_version', 'geometry_version', 'release_mapping_version']))
        check('case_frozen_release_lineage:' + rid,
              case['run_id'] == rid and case['scenario_id'] == scenario and case['base_scenario_id'] == base and
              release['model_id'] == old['model_id'] == case['upstream_model_id'] == line['upstream_model_id'] and
              release['mechanism_id'] == mechanism == line['mechanism_id'] and
              release['parameter_version'] == old['parameter_version'] == new['parameter_version'] ==
              case['upstream_parameter_version'] == line['upstream_parameter_version'] == PARAMETER_VERSION and
              case['geometry_version'] == line['geometry_version'] == release['geometry_version'] == GEOMETRY_VERSION and
              case['release_mapping_version'] == line['release_mapping_version'] == release['release_mapping_version'] == MAPPING_VERSION)
        check('mechanism_geometry_separate_from_source:' + rid,
              old['geometry_version'] == new['geometry_version'] == onset['geometry_version'] == 'conditional_plane_slab_v1')
        check('design_identity_preserved:' + rid, all(old[k] == new[k] for k in [
            'parameter_set_id', 'mechanism_id', 'law_policy', 'parameter_version', 'geometry_version', 'design_role', 'prior_weight']))
        for k in PHYSICAL_FIELDS:
            same = close(old[k], new[k], rtol=1e-13, atol=1e-13)
            parameter_audit.append(dict(run_id=rid, base_scenario_id=base, parameter=k,
                original_value=old[k], analytic_value=new[k], unchanged=same))
            check('physical_parameter_preserved:' + rid + ':' + k, same)
        for k in ['plan_area_m2', 'mechanism_thickness_normal_m', 'mechanism_plane_theta_deg',
                  'release_thickness_vertical_m', 'release_thickness_normal_equivalent_m', 'release_volume_m3',
                  'integrated_volume_m3', 'density', 'release_mass_kg']:
            check('case_and_registration_release_value:' + rid + ':' + k,
                  close(release[k], registered[k]) and close(release[k], embedded[k]))
        area = float(release['plan_area_m2'])
        vertical = float(release['release_thickness_vertical_m'])
        normal = float(release['mechanism_thickness_normal_m'])
        angle = float(release['mechanism_plane_theta_deg'])
        density, volume = float(release['density']), float(release['release_volume_m3'])
        resolution = float(release['grid_resolution_m'])
        reference_area = float(case['reference_source_grid_area_m2'])
        unnormalised_vertical = normal / math.cos(math.radians(angle))
        norm_factor = reference_area / area
        check('reference_area_and_grid_normalization:' + rid, close(reference_area, 925200) and
              close(normal, old['thickness_normal_m']) and close(angle, old['theta_deg']) and
              close(volume, reference_area * unnormalised_vertical) and close(vertical, unnormalised_vertical * norm_factor) and
              close(vertical, case['release_thickness_m']) and close(area, case['source_plan_area_m2']) and
              close(norm_factor, case['grid_thickness_normalization_factor']) and close(volume, area * vertical))
        fractions = json.loads(release['phase_fractions'])
        initial_velocity = json.loads(release['initial_velocity'])
        check('material_composition_and_bulk_phase:' + rid,
              release['phase_fraction_basis'] == case['passive_material_fraction_basis'] == 'volume' and
              fractions == case['passive_material_volume_fractions'] and close(sum(fractions.values()), 1) and
              close(density, fractions['ice'] * 917 + fractions['rock'] * 2700) and
              close(density, case['bulk_density_kg_m3']) and close(density, old['density_kg_m3']) and
              case['phase_volume_fractions'] == [1])
        check('zero_initial_velocity:' + rid, all(initial_velocity[k] == 0 for k in ['x', 'y', 'z']) and
              case['initial_velocity_east_north_m_s'] == [0, 0])
        check('original_no_cross_is_if_released:' + rid, release['onset_status'] == case['upstream_onset_status'] ==
              line['upstream_onset_status'] and (release['onset_status'] != 'never_crossed' or
                  (case['if_released_propagation'] and flag(run['if_released_propagation']) and
                   onset['status'] == 'no_cross_observed_complete' and
                   not present(onset['crossing_lower_utc']) and not present(onset['crossing_upper_utc']))))
        check('unknown_release_lag:' + rid, case['initiation_to_release_delay_seconds'] is None and
              line['initiation_to_release_delay_seconds'] is None and not present(run['initiation_to_release_delay_seconds']))
        check('qualification_remains_false:' + rid, all(not flag(run[k]) for k in [
            'scientifically_qualified_for_prediction', 'mass_conservation_qualified', 'regional_accuracy_qualified',
            'include_in_arrival_envelope', 'accepted_arrival_envelope_run_membership']))
        check('paper_target_coordinates_match_case:' + rid,
              all(t['id'] in points and np.allclose(points[t['id']][:2], t['xy'], rtol=0, atol=1e-6) for t in case['targets']))

        actual_release_path = Path(case['release']).resolve()
        check('actual_release_path_is_explicit_role:' + rid, actual_release_path in roles['immutable native release thickness'])
        check('actual_release_hash_is_registered:' + rid, sha(actual_release_path) ==
              case['release_sha256'] == registered['release_raster_sha256'] == embedded['release_raster_sha256'])
        expected_tiff_role = f"release_thickness_{old['parameter_set_id']}_{int(resolution)}m"
        expected_entry = unique(full_manifest['files'], role=expected_tiff_role)
        frozen_tiff = resolve(expected_entry['path']).resolve()
        check('frozen_Q2_tiff_pin:' + rid, frozen_tiff.is_relative_to(fullroot) and
              sha(frozen_tiff) == expected_entry['sha256'] == sha(actual_release_path) and
              frozen_tiff.stat().st_size == expected_entry['bytes'])
        add_input(frozen_tiff, 'frozen Q3-imported fullmask release TIFF')
        with rasterio.open(actual_release_path) as ds:
            supplied, transform, crs = ds.read(1).astype(float), ds.transform, str(ds.crs)
        with rasterio.open(frozen_tiff) as ds:
            check('frozen_Q2_release_array_and_grid_identical:' + rid,
                  np.array_equal(supplied, ds.read(1)) and transform == ds.transform and str(ds.crs) == crs)
        check('release_grid_metric_axis_aligned:' + rid, crs == 'EPSG:32645' and
              transform.a == resolution and transform.e == -resolution and transform.b == transform.d == 0)
        positive, cell_area = supplied > 0, resolution ** 2
        actual_volume = float(supplied[positive].sum() * cell_area)
        check('actual_fullmask_volume_not_legacy:' + rid,
              close(actual_volume, volume, rtol=1e-12) and close(actual_volume, case['release_grid_volume_m3'], rtol=1e-12) and
              close(actual_volume, registered['actual_grid_volume_m3'], rtol=1e-12) and
              close(actual_volume, embedded['actual_grid_volume_m3'], rtol=1e-12) and
              not close(actual_volume, case['expected_reference_grid_volume_m3']))
        check('actual_source_support:' + rid, int(positive.sum()) == int(case['source_mask_cells']) and
              int(positive.sum()) == (257 if resolution == 60 else 67) and
              close(int(positive.sum()) * cell_area, area) and close(area, case['source_grid_area_m2']))
        field_entry = unique(bundle['files'], role='actual_official_process_fields', run_id=rid)
        check('field_case_execution_log_binding:' + rid, sha(case_path) == field_entry['case_sha256'] and
              sha(export / f'provenance/{rid}/execution.json') == field_entry['execution_sha256'] and
              sha(export / f'provenance/{rid}/run.log') == field_entry['log_sha256'])
        parser = export / 'provenance/postprocessing' / Path(field_entry['parser_source_snapshot_path']).name
        check('copied_parser_hash_binding:' + rid, parser in roles['actual parser source snapshot bound to selected process fields'] and
              sha(parser) == field_entry['parser_sha256_at_start'])
        with np.load(field_entry['path'], allow_pickle=False) as z:
            time, depth, tr, stored_volume = [z[k].copy() for k in ['time_s', 'depth_frames', 'transform', 'volume_m3']]
        check('actual_saved_depth_time_grid:' + rid, len(time) == depth.shape[0] == len(stored_volume) and
              depth.shape[1:] == supplied.shape and np.all(np.isfinite(depth)) and depth.min() >= 0 and
              np.all(np.diff(time) > 0) and np.array_equal(tr, np.array(tuple(transform))) and
              close(time[0], 0) and close(time[-1], field_entry['time_end_seconds']) and close(time[-1], run['actual_end_time_seconds']))
        native_rows = []
        with (export / f'provenance/{rid}/native_internal_summary.txt').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                if row['nout'].isdigit():
                    native_rows.append(row)
        check('native_summary_time_binding:' + rid, native_rows[0]['nout'] == '0' and
              close(native_rows[0]['tsum'], 0) and close(native_rows[-1]['tsum'], time[-1]))
        native_initial = float(native_rows[0]['volume'])
        native_final = float(native_rows[-1]['volume'])
        raw_validation = json.loads(run['raw_validation_json'])
        native_residual = native_final / native_initial - 1
        metric = unique(metrics, run_id=rid)
        initial_grid_volume = float(depth[0].astype(float).sum() * cell_area)
        max_initial_depth_difference = float(np.max(np.abs(depth[0] - supplied)))
        check('native_initial_and_saved_TIFF_rounding_audit:' + rid,
              max_initial_depth_difference <= 0.00051 and
              close(initial_grid_volume, stored_volume[0], rtol=1e-12) and
              close(native_initial, raw_validation['native_internal_summary_initial_phase_volumes_m3'][0]) and
              abs(initial_grid_volume - volume) <= 0.00051 * int(positive.sum()) * cell_area and
              close(max_initial_depth_difference, raw_validation['initial_depth_vs_supplied_max_difference_m'], rtol=1e-8))
        check('native_budget_kept_separate_and_reproduced:' + rid,
              close(native_final, raw_validation['native_internal_summary_final_phase_volumes_m3'][0]) and
              close(native_residual, metric['native_internal_summary_mass_budget_relative_residual'], rtol=1e-8) and
              all(x == 0 for x in raw_validation['native_signed_entrainment_phase_volumes_m3']) and
              all(x == 0 for x in raw_validation['native_edge_store_outflow_phase_volumes_m3']))
        saved_residual = float(stored_volume[-1] / stored_volume[0] - 1)
        check('saved_raster_budget_reproduced:' + rid,
              close(saved_residual, metric['ascii_raster_source_adjusted_budget_relative_residual'], rtol=1e-8))
        volume_audit.append(dict(run_id=rid, scenario_id=scenario, base_scenario_id=base, grid_resolution_m=resolution,
            source_geometry_version=GEOMETRY_VERSION, release_mapping_version=MAPPING_VERSION,
            mechanism_normal_thickness_m=normal, mechanism_plane_theta_deg=angle,
            source_exact_polygon_area_m2=case['source_exact_area_m2'], reference_60m_area_m2=reference_area,
            actual_grid_area_m2=area, source_support_cells=int(positive.sum()),
            grid_thickness_normalization_factor=norm_factor, release_vertical_thickness_m=vertical,
            reference_unnormalised_vertical_thickness_m=unnormalised_vertical,
            Q2_frozen_release_volume_m3=volume, actual_release_TIFF_volume_m3=actual_volume,
            executed_case_release_grid_volume_m3=case['release_grid_volume_m3'],
            saved_initial_depth_integral_m3=initial_grid_volume, NPZ_initial_volume_m3=float(stored_volume[0]),
            native_internal_initial_volume_m3=native_initial, native_internal_final_volume_m3=native_final,
            saved_initial_relative_difference=initial_grid_volume / volume - 1,
            saved_initial_max_depth_difference_m=max_initial_depth_difference,
            native_ASCII_depth_rounding_audit_bound_m=0.00051,
            legacy_expected_reference_grid_volume_m3=case['expected_reference_grid_volume_m3'],
            legacy_reference_used_as_actual_or_budget_denominator=False,
            density_kg_m3=density, passive_material_fractions=json.dumps(fractions, sort_keys=True),
            solver_phase='one equivalent_bulk phase; composition passive',
            raster_budget_relative_residual=saved_residual, native_internal_budget_relative_residual=native_residual,
            budget_representations_separate=True, mass_conservation_qualified=False,
            scientifically_qualified_for_prediction=False, actual_release_raster_sha256=sha(actual_release_path),
            source_geometry_sha256=case['source_geometry_sha256'], source_fields_sha256=field_entry['sha256']))
        lineage_audit.append(dict(run_id=rid, source_release_scenario_id=scenario, base_scenario_id=base,
            mechanism_id=mechanism, original_model_id=old['model_id'], analytic_model_id=analytic_model,
            analytic_scenario_id=onset['scenario_id'], parameter_version=PARAMETER_VERSION,
            mechanism_geometry_version=old['geometry_version'], release_geometry_version=GEOMETRY_VERSION,
            release_mapping_version=MAPPING_VERSION, grid_resolution_m=resolution,
            physical_parameters_compared=len(PHYSICAL_FIELDS), physical_parameters_unchanged=True,
            old_onset_status=release['onset_status'], analytic_onset_status=onset['status'],
            conditional_analytic_crossing_lower_utc=onset['crossing_lower_utc'] or None,
            conditional_analytic_crossing_upper_utc=onset['crossing_upper_utc'] or None,
            conditional_analytic_interpolated_point_utc=onset['crossing_point_utc'] or None,
            if_released_propagation=case['if_released_propagation'], initiation_to_release_delay_seconds=None,
            adapter_lineage_status='accepted_exact_fullmask_lineage_and_registered_analytic_replacement',
            evaluation_stratum='conditional_scenario', scientific_acceptance_decision_version=decision['version']))

        yy, xx = np.indices(supplied.shape)
        xx = transform.c + (xx + 0.5) * transform.a
        yy = transform.f + (yy + 0.5) * transform.e
        half = resolution / 2
        rectangles = [(float(xx[j, i] - half), float(xx[j, i] + half),
                       float(yy[j, i] - half), float(yy[j, i] + half)) for j, i in zip(*np.nonzero(positive))]
        distance = support_distance(xx, yy, rectangles)
        horizon = float(run['requested_horizon_seconds'])
        permitted = time <= horizon
        requested_max, all_max = depth[permitted].max(axis=0), depth.max(axis=0)
        check('saved_impact_area_reproduced:' + rid,
              close(np.count_nonzero(all_max >= 0.1) * cell_area, metric['impact_area_m2']))
        for scope, hmax, last in [('saved_outputs_through_requested_horizon', requested_max, float(time[permitted][-1])),
                                 ('all_actual_saved_outputs', all_max, float(time[-1]))]:
            for threshold in [0.1, 1, 5]:
                wet = hmax >= threshold
                footprints.append(dict(run_id=rid, scenario_id=scenario, scope=scope,
                    requested_horizon_seconds=horizon, last_included_saved_seconds=last, grid_resolution_m=resolution,
                    threshold_depth_m=threshold, affected_cell_count=int(wet.sum()), affected_plan_area_m2=float(wet.sum() * cell_area),
                    maximum_affected_cell_centre_distance_from_release_support_m=float(distance[wet].max()) if wet.any() else None,
                    distance_definition='Euclidean cell-centre to union of positive actual per-run release raster cell footprints',
                    metric_crs='EPSG:32645', source_geometry_version=GEOMETRY_VERSION,
                    source_geometry_is_observed_release=False, footprint_is_validated_hazard_zone=False,
                    validated_warning_distance_m=None, scientifically_qualified_for_prediction=False,
                    mass_conservation_qualified=False, arrival_probability=None, source_fields_sha256=field_entry['sha256']))
        arrays.append((scenario, requested_max, positive, xx, yy))
        for target in [x for x in targets if x['run_id'] == rid]:
            tid = target['target_id']
            check('target_exact_fullmask_lineage:' + rid + ':' + tid, all(target[k] == run[k] for k in [
                'scenario_id', 'base_scenario_id', 'upstream_model_id', 'upstream_parameter_version',
                'geometry_version', 'release_mapping_version', 'parameter_version']))
            check('target_qualification_false:' + rid + ':' + tid, all(not flag(target[k]) for k in [
                'include_in_arrival_envelope', 'scientifically_qualified_for_prediction', 'mass_conservation_qualified',
                'regional_accuracy_qualified', 'accepted_arrival_envelope_run_membership']) and
                not present(target['probability_weight']) and not present(target['initiation_to_release_delay_seconds']))
            check('target_geometry_binding:' + rid + ':' + tid,
                  tid in points and points[tid][2] == target['target_geometry_version'])
            tx, ty, _ = points[tid]
            mask = np.hypot(xx - tx, yy - ty) <= 100
            actual, formal = saved_first_hit(time, depth, mask, float(time[-1])), saved_first_hit(time, depth, mask, horizon)
            agrees = actual['hit'] == flag(target['observed_hit']) and all(
                (actual[key] is None and not present(target[column])) or
                (actual[key] is not None and present(target[column]) and close(actual[key], target[column]))
                for key, column in [('lower', 'arrival_bracket_lower_seconds'), ('upper', 'arrival_bracket_upper_seconds')])
            check('independent_field_target_reproduction:' + rid + ':' + tid,
                  agrees and target['source_fields_sha256'] == field_entry['sha256'] and flag(target['target_field_hash_matches']))
            target_audit.append(dict(run_id=rid, target_id=tid, grid_resolution_m=resolution,
                target_buffer_cell_count=int(mask.sum()), actual_last_saved_seconds=actual['last_saved'],
                recomputed_actual_status=actual['status'], actual_first_hit_lower_seconds=actual['lower'],
                actual_first_hit_upper_seconds=actual['upper'], requested_horizon_status=formal['status'],
                requested_last_saved_seconds=formal['last_saved'], requested_first_hit_lower_seconds=formal['lower'],
                requested_first_hit_upper_seconds=formal['upper'], original_actual_hit_and_bracket_agree=agrees,
                source_field_binding_agrees=True, target_point_to_release_raster_support_distance_m=float(
                    support_distance(np.array(tx), np.array(ty), rectangles))))
            joined.append(dict(run_id=rid, scenario_id=scenario, base_scenario_id=base, event_id=bundle['common_context']['event_id'],
                source_analytic_scenario_id=onset['scenario_id'], original_upstream_model_id=old['model_id'],
                analytic_onset_model_id=analytic_model, propagation_model_id=run['model_id'], mechanism_id=mechanism,
                parameter_version=PARAMETER_VERSION, mechanism_geometry_version=old['geometry_version'],
                release_geometry_version=GEOMETRY_VERSION, release_mapping_version=MAPPING_VERSION, grid_resolution_m=resolution,
                target_id=tid, entity_id=target['entity_id'] or None, target_kind=target['target_kind'] or None,
                target_geometry_version=target['target_geometry_version'], source_first_passage_status=onset['status'],
                original_upstream_onset_status=release['onset_status'], conditional_onset_lower_utc=onset['crossing_lower_utc'] or None,
                conditional_onset_upper_utc=onset['crossing_upper_utc'] or None, forecast_input_mode=onset['forecast_input_mode'],
                if_released_propagation=case['if_released_propagation'], initiation_to_release_delay_seconds=None,
                time_origin='bulk_release', physical_phase='conditional_bulk_release_to_target_arrival',
                raw_conditional_arrival_status=target['arrival_status'], diagnostic_bulk_release_arrival_lower_seconds=actual['lower'],
                diagnostic_bulk_release_arrival_upper_seconds=actual['upper'], diagnostic_arrival_within_requested_horizon=formal['hit'],
                requested_horizon_seconds=horizon, last_saved_within_requested_horizon_seconds=formal['last_saved'],
                actual_last_saved_seconds=actual['last_saved'], arrival_definition=target['arrival_definition'],
                diagnostic_observation_available=flag(target['diagnostic_observation_available']),
                conditional_diagnostic_range_eligible=flag(target['conditional_diagnostic_range_eligible']),
                diagnostic_eligibility_is_qualification=False, absolute_arrival_lower_utc=None,
                absolute_arrival_upper_utc=None, absolute_arrival_time_utc=None, qualified_arrival_lower_seconds=None,
                qualified_arrival_upper_seconds=None, arrival_probability=None, probability_weight=None,
                include_in_arrival_envelope=False, accepted_arrival_envelope_run_membership=False,
                numerical_qualification=run['numerical_qualification'], mass_conservation_qualified=False,
                regional_accuracy_qualified=False, scientifically_qualified_for_prediction=False,
                scientific_acceptance_decision_version=decision['version'],
                arrival_envelope_semantics_version=bundle['arrival_envelope_semantics_version'],
                event_timing_validated=False, arrival_is_initiation_truth=False, evaluation_stratum='conditional_scenario',
                independent_local_validation_events=0, adapter_lineage_status='accepted_exact_fullmask_lineage',
                arrival_status='unqualified_conditional_diagnostic;unknown_initiation_to_bulk_release_lag',
                source_fields_sha256=field_entry['sha256']))
        compact = unique(compact_audits, base_scenario_id=base)
        oldhit = unique(compact_targets, base_scenario_id=base, target_id='paper_junction')
        currenthit = unique(target_audit, run_id=rid, target_id='paper_junction')
        comparison.append(dict(run_id=rid, base_scenario_id=base, fullmask_grid_resolution_m=resolution,
            fullmask_source_area_m2=area, fullmask_actual_volume_m3=actual_volume,
            compact_run_id=compact['run_id'], compact_grid_resolution_m=60,
            compact_source_plan_area_m2=compact['original_plan_area_m2'], compact_volume_m3=compact['original_volume_m3'],
            source_volume_ratio=actual_volume / float(compact['original_volume_m3']),
            compact_junction_diagnostic_lower_seconds=oldhit['diagnostic_bulk_release_arrival_lower_seconds'],
            compact_junction_diagnostic_upper_seconds=oldhit['diagnostic_bulk_release_arrival_upper_seconds'],
            fullmask_junction_diagnostic_lower_seconds=currenthit['actual_first_hit_lower_seconds'],
            fullmask_junction_diagnostic_upper_seconds=currenthit['actual_first_hit_upper_seconds'],
            same_mechanical_parameters=True, changed_computational_source=True, changed_grid_resolution=resolution != 60,
            causal_geometry_effect_or_model_gain_validated=False, both_results_scientifically_unqualified=True,
            comparison_scope='descriptive different-source experiment; not validation, probability or qualified model gain'))

    check('all21_lineage_pairs_retained', len(joined) == 21)
    check('3raw_junction_hits18_saved_nonhits', sum(x['actual_first_hit_upper_seconds'] is not None for x in target_audit) == 3 and
          all(x['target_id'] == 'paper_junction' for x in target_audit if x['actual_first_hit_upper_seconds'] is not None))
    check('all_absolute_qualified_probability_fields_null', all(all(x[k] is None for k in [
        'absolute_arrival_lower_utc', 'absolute_arrival_upper_utc', 'absolute_arrival_time_utc',
        'qualified_arrival_lower_seconds', 'qualified_arrival_upper_seconds', 'arrival_probability', 'probability_weight']) for x in joined))
    check('all_no_accepted_envelope_membership', all(not x['include_in_arrival_envelope'] and
          not x['accepted_arrival_envelope_run_membership'] for x in joined))
    check('p36_actual_July8_analytic_crossing', all(x['analytic_onset_status'] == 'point_crossing_linear_between_samples' and
          x['conditional_analytic_crossing_lower_utc'] == '2026-07-08T15:00:00+00:00' and
          x['conditional_analytic_crossing_upper_utc'] == '2026-07-08T16:00:00+00:00'
          for x in lineage_audit if x['base_scenario_id'] == 'q2r3-p0036-S_T-linear'))
    write_csv(out / 'lineage_audit.csv', lineage_audit)
    write_csv(out / 'physical_parameter_audit.csv', parameter_audit)
    write_csv(out / 'release_mapping_audit.csv', volume_audit)
    write_csv(out / 'conditional_arrivals.csv', joined)
    write_csv(out / 'saved_field_target_checks.csv', target_audit)
    write_csv(out / 'depth_footprint_diagnostics.csv', footprints)
    write_csv(out / 'compact_v2_comparison.csv', comparison)
    write_csv(out / 'rejected_pairings.csv', [], ['run_id', 'target_id', 'reason'])
    write_json(out / 'adapter_schema.json', dict(version='q3-q4-fullmask-adapter-v3',
        exact_keys=['full_release_scenario_id', 'base_scenario_id', 'model_id', 'mechanism_id',
                    'parameter_version', 'release_mapping_version', 'source_geometry_version', 'grid_resolution_m'],
        mechanism_model_replacement=MODEL_REPLACEMENTS, physical_fields=PHYSICAL_FIELDS,
        source_volume_authority='Q2 frozen geometry-v2 row + actual supplied release TIFF integral + case actual grid volume + audited native/saved initial state',
        legacy_reference_field_is_actual_volume=False, source_geometry_is_mechanism_geometry=False,
        material_fractions_are_solver_phase_fractions=False, selected_runs_are_probability_ensemble=False,
        accepted_arrival_envelope_run_ids=[], absolute_release_lag_unknown=True,
        semantic_adapter_pass_is_predictive_qualification=False))

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)
    for ax, (scenario, hmax, positive, xx, yy) in zip(axes, arrays):
        image = ax.pcolormesh(xx / 1000, yy / 1000, np.ma.masked_where(hmax < 0.1, hmax),
                              cmap='viridis', shading='nearest', vmin=0, vmax=120)
        ax.contour(xx / 1000, yy / 1000, positive.astype(float), levels=[0.5], colors=['red'], linewidths=1)
        for tid, (tx, ty, _) in points.items():
            ax.scatter(tx / 1000, ty / 1000, marker='x', color='black', s=12)
            if tid in ['paper_junction', 'paper_port_symbol']:
                ax.annotate(tid.replace('paper_', ''), (tx / 1000, ty / 1000), xytext=(3, 3), textcoords='offset points', fontsize=7)
        ax.set_aspect('equal')
        ax.set_title(scenario.replace('__geomv2_', '\n') + '\nUNQUALIFIED; saved outputs <=1800s', fontsize=9)
        ax.set_xlabel('Easting (km; EPSG:32645)')
        ax.set_ylabel('Northing (km; EPSG:32645)')
    fig.colorbar(image, ax=axes, label='Saved-output max depth (m; shown >=0.1m)', shrink=0.85)
    fig.suptitle('Full-source conditional diagnostics; red = actual release raster support; black x = target representatives\nNo absolute arrival, arrival probability or validated warning distance', fontsize=11)
    fig.savefig(out / 'conditional_footprints.png', dpi=180)
    plt.close(fig)
    summary = dict(status='fullmask_v3_adapter_executed_unqualified_diagnostics_only', bundle_version=bundle['bundle_version'],
        bundle_sha256=PIN, producer_bundle_sha256=PRODUCER_PIN, delivered_files_verified=66,
        selected_physical_runs=3, unique_base_parameter_scenarios=2, representative_targets=7,
        osm_representative_points=5, osm_candidate_entities=3, paper_candidate_points=2,
        run_target_rows=21, accepted_lineage_pairs=21, rejected_lineage_pairs=0,
        raw_saved_junction_hits=3, raw_saved_target_nonhits=18, independent_local_validation_events=0,
        qualified_arrival_rows=0, qualified_arrival_envelope_rows=0, absolute_arrival_rows=0,
        probability_rows=0, probability_weights=None, selected_runs_are_2048_probability_ensemble=False,
        physical_parameters_compared_per_run=len(PHYSICAL_FIELDS), release_mapping_version=MAPPING_VERSION,
        geometry_version=GEOMETRY_VERSION, legacy_reference_volume_used_as_actual=False,
        native_saved_initial_volume_audited=True, mass_conservation_qualified=False,
        regional_accuracy_qualified=False, scientifically_qualified_for_prediction=False,
        accepted_arrival_envelope_run_ids=[], scientific_acceptance_decision_version=decision['version'],
        no_physical_solver_rerun=True, no_existing_frozen_file_modified=True)
    write_json(out / 'summary.json', summary)
    write_json(out / 'status.json', summary)
    (out / 'RESULTS.md').write_text('''# Full-source propagation v3 adapter results

All 66 delivered role objects were verified by exact path, bytes and SHA256. The imported packet and producer snapshot are separately pinned. Exact frozen Q2 geometry-v2 and analytic-erfc joins retain all **21 rows: 3 runs x 7 representative points**, representing only **2 selected base parameter scenarios**. Five OSM points describe three candidate entities; the two paper points are candidate objects. No independent validation event or statistical weight is created.

The source is the full paper-candidate computational mask, distinct from the compact v2 experiment. At 60m the source has **257 cells / 925,200m²**; at 120m **67 cells / 964,800m²**. The declared exact polygon area (927,822.8616m²) is a different area definition. p0000-60 releases **51,755,728.59264966m³**; p0036 at either resolution releases **31,184,139.1284297m³**. At 120m the vertical thickness is **32.3218689142m**, normalized from 33.7052952101m by 925200/964800. The mechanical normal thickness and all 20 shared physical parameters remain unchanged. Actual TIFF arrays, hashes, grid transforms and integrals match the frozen Q3-imported Q2-v2 rasters. The inherited **13,878,000m³ expected-reference field is stale metadata**, separately audited and never used as actual release volume or a budget denominator.

The explicit analytic model replacement retains p0000's **no_cross_observed_complete / if-released** status with no onset timestamp. p0036 retains the actual conditional July 8 15:00–16:00 UTC analytic crossing bracket (interpolation 15:34:17.258933921 UTC). These ideal-weather retrospective mechanical first-crossing times are not observed bulk release or operational forecasts.

Actual saved native depth and native times reproduce the three paper-junction threshold brackets:

| Selected run | Bulk-release-relative diagnostic interval (s) |
| --- | --- |
| p0000 S, 60m | (161.1, 180.2] |
| p0036 ST, 120m | (240.6, 260.1] |
| p0036 ST, 60m | (221.0, 240.7] |

Detection is h>=0.1m at registered cell centres within a 100m representative-point buffer, with previous-below/first-above saved-output brackets. The other 18 records have no threshold hit at saved outputs; this does not establish continuous-time safety. Requested 1800s and actual slightly later final output times are retained separately.

All three runs remain **scientifically, regionally and mass-conservation unqualified** under decision05's empty accepted-envelope list. Execution diagnostic eligibility does not confer acceptance. Saved-raster source-adjusted residuals are **+0.947210%, -0.397350%, +1.663189%**; native internal residuals are separately **+0.947784%, -0.388377%, +1.665052%**. No percentage observed here is designated a physical pass threshold. The depth-rounding bound in the initial-input audit is an I/O consistency check, not conservation or prediction certification. All absolute arrivals, qualified intervals, probabilities and weights remain null, because acceptance is absent and the initiation-to-bulk-release delay remains unknown.

The footprint table and three-panel figure read only actual stored fields. Depth thresholds 0.1/1/5m are descriptive; area is affected cell area. Distance is affected cell-centre Euclidean distance to the actual per-grid positive-release raster cell footprints. It is not a centroid/path length, exact observed polygon runout, validated hazard zone or warning distance. The compact-v2 comparison retains the different source assumption and grid difference; it is not a validated model gain or a weighted 2048-member forecast.

Reproduce from the Q3 worktree:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 track_b/.venv/bin/python track_b/research/q3/round3/scripts/join_propagation_v3.py
```

`review/` is independently owned and is excluded from this script's output index. Root seals that review and these results together. No old script, result, bundle, or portable manifest is edited by this adapter.
''')
    add_input(out / 'PROTOCOL.md', 'registered precomputation protocol')
    add_input(Path(__file__), 'actually executed fullmask adapter source')
    for entry in input_by_path.values():
        p = resolve(entry['path'])
        check('input_unchanged_during_adapter:' + entry['path'],
              p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256'])
    figure_review = out / 'figure_review.json'
    if figure_review.exists():
        visual = read_json(figure_review)
        check('actual_figure_review_binding', visual.get('passed') is True and
              len(visual.get('figures', [])) == 1 and visual['figures'][0]['actually_opened'] is True and
              resolve(visual['figures'][0]['path']) == out / 'conditional_footprints.png' and
              visual['figures'][0]['sha256'] == sha(out / 'conditional_footprints.png'))
    input_records = sorted(input_by_path.values(), key=lambda x: x['path'])
    check('input_index_has_no_repeated_canonical_paths', len(input_records) == len({x['path'] for x in input_records}))
    write_json(out / 'input_index.json', dict(files=input_records, file_list_excludes_self=True,
        exact_role_objects_verified=66, roles_merged_for_repeated_canonical_paths=True,
        path_resolution='repository entries Q3 ROOT-relative; external entries exact approved cache path',
        source_and_upstream_metadata_paths_are_not_read_permissions=True,
        no_active_other_question_worktree_reads=True))
    output_records = [file_record(p, 'new fullmask adapter output') for p in sorted(out.iterdir())
        if p.is_file() and p.name not in ['output_index.json', 'validation.json']]
    write_json(out / 'output_index.json', dict(files=output_records, file_list_excludes_self=True,
        validation_excluded_to_avoid_cycle=True, independent_review_directory_excluded=True,
        path_resolution='Q3 ROOT-relative repository paths; no recursive output traversal'))
    validation = dict(passed=all(x['passed'] for x in checks), generated_at_utc=datetime.now(timezone.utc).isoformat(),
        check_count=len(checks), checks=checks, adapter_pass_is_predictive_qualification=False,
        input_index_sha256=sha(out / 'input_index.json'), output_index_sha256=sha(out / 'output_index.json'),
        figure_visual_qa='passed_external_visual_inspection' if figure_review.exists() else 'pending_external_visual_inspection')
    write_json(out / 'validation.json', validation)
    print(json.dumps(summary, ensure_ascii=False))
    print(f'Adapter QA: {len(checks)}/{len(checks)} passed; inputs={len(input_records)}, outputs={len(output_records)}')


if __name__ == '__main__':
    main()

