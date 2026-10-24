#!/usr/bin/env python3
"""Audit compact SH/STH delta with frozen Q2 and actual Q4 fields; no physics rerun.

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
CACHE = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
PIN = '044a9a08ce09e8b2b5470a6a4351942fb08054e52e9728e2bb4d51a2295841ac'
PRODUCER_PIN = '28c67deb49d694e992c005365cf19c73d1db31a89126f64dbe8b6973adba61cb'
DEFAULT_BUNDLE = R / 'inputs/q4/bundle_q4-r3-compact-delta-v1/bundle.json'
DEFAULT_OUT = R / 'results/arrival/compact_delta_v1'
MODEL_REPLACEMENTS = {
    'q2r3_SH_v1': ('S_H', 'q2r3_S_H_analytic_v1'),
    'q2r3_STH_v1': ('S_T_H', 'q2r3_S_T_H_analytic_v1'),
}

PARAMETER_VERSION = 'q2r3-design-v1'
MAPPING_VERSION = 'q4-r3-q2-mapped-release-v1'
GEOMETRY_VERSION = 'q4-r3-q2-mapped-release-v1'
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
        raise ValueError('Unregistered delta packet or output scope')
    if not (out / 'PROTOCOL.md').exists():
        raise ValueError('Retain registered protocol before computation')
    checks, index, roles = [], {}, {}

    def check(name, passed, detail=None):
        entry = dict(name=name, passed=bool(passed))
        if detail is not None:
            entry['detail'] = detail
        checks.append(entry)
        if not passed:
            raise ValueError(f'Adapter check failed: {name}; {detail}')

    def add_input(path, role):
        p = Path(path).resolve()
        entry, key = file_record(p, role), str(p)
        if key in index:
            current = index[key]
            check('repeat_input_binding:' + relative(p), entry['bytes'] == current['bytes'] and entry['sha256'] == current['sha256'])
            if role not in current['roles']:
                current['roles'].append(role)
        else:
            entry['roles'] = [entry.pop('role')]
            index[key] = entry
        return p

    add_input(bp, 'pinned imported compact delta packet')
    producer_path = bp.parent / 'upstream_bundle.json'
    check('producer_pin', sha(producer_path) == PRODUCER_PIN)
    add_input(producer_path, 'pinned producer packet snapshot; producer paths not permissions')
    bundle = read_json(bp)
    check('advisor_binds_producer', bundle['advisor_review']['upstream_bundle_sha256'] == PRODUCER_PIN)
    check('48_distinct_role_objects', len(bundle['files']) == len({f['path'] for f in bundle['files']}) == 48)
    for f in bundle['files']:
        p = resolve(f['path']).resolve()
        check('approved_path:' + relative(p), p.is_relative_to(bp.parent) or (
              p.is_relative_to(CACHE) and f.get('storage') == 'immutable_external_cache'))
        check('delivered_hash:' + relative(p), p.stat().st_size == f['bytes'] and sha(p) == f['sha256'])
        roles.setdefault(f['role'], []).append(p)
        add_input(p, f['role'])

    def one_role(name):
        found = roles.get(name, [])
        check('one_role:' + name, len(found) == 1)
        return found[0]

    rp, tp, mp = map(one_role, ['model_runs', 'target_arrivals', 'comparison_metrics'])
    export = rp.parent
    runs, targets, metrics = rows(rp), rows(tp), rows(mp)
    check('only_two_selected_compact_bases', len(runs) == 2 and
          {x['base_scenario_id'] for x in runs} == {'q2r3-p0072-S_H-linear', 'q2r3-p0255-S_T_H-linear'} and
          {x['run_id'] for x in runs} == set(bundle['selected_run_ids']))
    check('14_distinct_run_target_rows', len(targets) == len({(x['run_id'], x['target_id']) for x in targets}) == 14 and
          len({x['target_id'] for x in targets}) == 7)
    decision = read_json(export / 'quality/scientific_acceptance_decision_05.json')
    check('no_accepted_envelope_or_weights', decision['accepted_arrival_envelope_run_ids'] ==
          bundle['accepted_arrival_envelope_run_ids'] == [] and bundle['probability_weights'] is None and
          bundle['independent_local_validation_events'] == 0 and all(decision[k] is False and bundle[k] is False
          for k in ['scientifically_qualified_for_prediction', 'mass_conservation_qualified', 'regional_accuracy_qualified']))
    release_path = export / 'provenance/upstream_q2/release_states.csv'
    original_bundle = read_json(export / 'provenance/upstream_q2/upstream_bundle.json')
    copied_bundle = read_json(export / 'provenance/upstream_q2/bundle.json')
    check('Q2_original_catalogue_hash_chain', sha(release_path) ==
          unique(original_bundle['files'], role='results/release_states.csv')['sha256'] ==
          unique(copied_bundle['files'], role='results/release_states.csv')['sha256'])
    frozen_release = add_input(R / 'inputs/q4/bundle_q4-r3-propagation-v2/files/exports/propagation_v2/provenance/upstream_q2/release_states.csv',
                              'previously frozen original Q2 compact release catalogue')
    check('delta_catalogue_equals_frozen_Q3_parent', sha(frozen_release) == sha(release_path))
    release_rows = rows(release_path)
    originalroot = R / 'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1'
    analyticroot = R / 'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1'
    pp, op = originalroot / 'files/results/parameter_ensemble.csv', originalroot / 'files/results/scenario_outcomes.csv'
    ap = analyticroot / 'files/results/analytic_thermal/parameter_ensemble.csv'
    aop = analyticroot / 'files/results/analytic_thermal/scenario_outcomes.csv'
    cp = analyticroot / 'files/results/analytic_thermal/mechanism_contract.json'
    fp = R / 'results/engine_a/analytic_erfc/first_passages.csv'
    for manifestroot, required in [(originalroot, [pp, op]), (analyticroot, [ap, aop, cp])]:
        manifest = read_json(add_input(manifestroot / 'bundle.json', 'frozen imported mechanism manifest'))
        for p in required:
            matches = [x for x in manifest['files'] if resolve(x['path']).resolve() == p.resolve()]
            check('frozen_import_hash:' + relative(p), len(matches) == 1 and sha(p) == matches[0]['sha256'] and
                  p.stat().st_size == matches[0]['bytes'])
            add_input(p, 'frozen original/analytic parameters, onset scopes and explicit join contract')
    check('original_parameter_hash_matches_compact_Q2_bundle', sha(pp) ==
          unique(original_bundle['files'], role='results/parameter_ensemble.csv')['sha256'])
    add_input(fp, 'frozen actual analytic-erfc full-history first passages')
    contract = read_json(cp)
    check('analytic_contract_release_join', contract['parameter_version'] == PARAMETER_VERSION and
          contract['base_scenario_join'] == 'base_scenario_id joins v1/v2 and release-geometry-v2; release states unchanged, use this model version onset/censoring when combined')
    oldpars, newpars, oldoutcomes, analytic_outcomes, onsets = rows(pp), rows(ap), rows(op), rows(aop), rows(fp)
    lineage, parameters, release_audit, onset_audit, joined, target_audit, footprints, panels = ([] for _ in range(8))
    import rasterio
    from pyproj import Transformer
    projection = Transformer.from_crs('EPSG:4326', 'EPSG:32645', always_xy=True)
    points = {x['target_id']: (float(x['x_m']), float(x['y_m']), x['geometry_version'])
              for x in rows(export / 'geometry/spatial_targets_v2.csv')}
    geom = read_json(export / 'geometry/computational_geometries.geojson')
    check('GeoJSON_lonlat_semantics', geom['crs_note'] == 'GeoJSON CRS84 longitude/latitude; distances in EPSG32645')
    for feature in geom['features']:
        if feature['geometry']['type'] == 'Point':
            tx, ty = projection.transform(*feature['geometry']['coordinates'])
            prop = feature['properties']
            points[prop['space_id']] = (tx, ty, prop['geometry_version'])

    for run in runs:
        rid, base = run['run_id'], run['base_scenario_id']
        case_path = export / f'provenance/{rid}/case.json'
        case = read_json(case_path)
        source, old, outcome = unique(release_rows, scenario_id=base), unique(oldpars, scenario_id=base), unique(oldoutcomes, scenario_id=base)
        line = unique(bundle['lineage_by_run'], run_id=rid)
        check('registered_original_model:' + rid, source['model_id'] in MODEL_REPLACEMENTS)
        mechanism, new_model = MODEL_REPLACEMENTS[source['model_id']]
        new = unique(newpars, base_scenario_id=base, model_id=new_model)
        onset = unique(onsets, base_scenario_id=base, model_id=new_model, mechanism_id=mechanism,
                       parameter_version=PARAMETER_VERSION, geometry_version=old['geometry_version'])
        analytic_outcome = unique(analytic_outcomes, base_scenario_id=base, scenario_id=onset['scenario_id'],
                                  model_id=new_model, parameter_version=PARAMETER_VERSION)
        check('contract_model_replacement:' + rid, contract['model_ids'][mechanism] == new_model)
        check('analytic_outcomes_and_first_passages_same_global_scope:' + rid,
              analytic_outcome['onset_status'] == outcome['onset_status'] and
              analytic_outcome['evaluation_onset_status'] == outcome['evaluation_onset_status'] and
              analytic_outcome['crossing_time_utc'] == onset['crossing_point_utc'])
        check('linear_branch_design_identity:' + rid, old['law_policy'] == new['law_policy'] == onset['law_policy'] == 'linear_extension' and
              all(old[k] == new[k] for k in ['parameter_set_id', 'mechanism_id', 'parameter_version', 'geometry_version', 'design_role', 'prior_weight']))
        for k in PHYSICAL_FIELDS:
            same = float(old[k]) == float(new[k])
            parameters.append(dict(run_id=rid, base_scenario_id=base, parameter=k,
                                   original_value=old[k], analytic_value=new[k], exact_float_equal=same))
            check('physical_parameter_exact:' + rid + ':' + k, same)
        check('bundle_run_exact_lineage:' + rid, all(run[k] == line[k] for k in [
            'scenario_id', 'base_scenario_id', 'upstream_model_id', 'upstream_parameter_version', 'mechanism_id',
            'parameter_version', 'geometry_version', 'release_mapping_version']))
        check('original_release_case_lineage:' + rid,
              run['scenario_id'] == case['scenario_id'] == base and case['run_id'] == rid and
              source['model_id'] == old['model_id'] == outcome['model_id'] == case['upstream_model_id'] == line['upstream_model_id'] and
              source['mechanism_id'] == old['mechanism_id'] == line['mechanism_id'] == mechanism and
              source['parameter_version'] == old['parameter_version'] == new['parameter_version'] ==
              case['upstream_parameter_version'] == line['upstream_parameter_version'] == PARAMETER_VERSION and
              case['geometry_version'] == run['geometry_version'] == line['release_mapping_version'] == MAPPING_VERSION)
        check('separate_original_area_mechanical_and_mapped_geometry:' + rid,
              source['geometry_version'] == 'conditional_area_requires_q4_polygon_v1' and
              not present(source['source_polygon_or_release_raster']) and
              old['geometry_version'] == new['geometry_version'] == onset['geometry_version'] == 'conditional_plane_slab_v1' and
              case['source_mapping'] == 'Circular compact subsource centred on paper candidate centroid, clipped to that polygon, area solved exactly; no observed release geometry claim')
        area, normal, vertical, volume, density = map(float, [source['plan_area_m2'], source['release_thickness_normal_m'],
            source['release_thickness_vertical_m'], source['release_volume_m3'], source['density']])
        angle, resolution = float(old['theta_deg']), float(case['resolution_m'])
        check('original_area_thickness_volume_preserved:' + rid, close(normal, old['thickness_normal_m']) and
              close(vertical, normal / math.cos(math.radians(angle))) and close(volume, area * vertical) and
              close(area, case['source_plan_area_m2']) and close(vertical, case['release_thickness_m']) and resolution == 60)
        fractions, velocity = json.loads(source['phase_fractions']), json.loads(source['initial_velocity'])
        check('material_volume_composition_and_bulk_phase:' + rid, source['phase_fraction_basis'] == case['passive_material_fraction_basis'] == 'volume' and
              fractions == case['passive_material_volume_fractions'] and fractions['free_water'] == 0 and
              close(density, fractions['rock'] * 2700 + fractions['ice'] * 917) and
              close(density, case['bulk_density_kg_m3']) and close(density, old['density_kg_m3']) and case['phase_volume_fractions'] == [1])
        check('zero_initial_speed:' + rid, all(velocity[k] == 0 for k in ['x', 'y', 'z']) and case['initial_velocity_east_north_m_s'] == [0, 0])
        check('original_global_onset_preserved:' + rid, source['onset_status'] == case['upstream_onset_status'] ==
              line['upstream_onset_status'] == outcome['onset_status'])
        if mechanism == 'S_H':
            check('SH_no_start_if_released:' + rid, source['onset_status'] == 'never_crossed' and
                  onset['status'] == 'no_cross_observed_complete' and case['if_released_propagation'] and
                  flag(run['if_released_propagation']) and not present(onset['crossing_lower_utc']) and not present(onset['crossing_upper_utc']))
        else:
            check('STH_global_start_not_evaluation_window_start:' + rid, source['onset_status'] == 'interval_crossing' and
                  outcome['evaluation_onset_status'] == 'left_censored_already_unstable' and
                  onset['status'] == 'point_crossing_linear_between_samples' and
                  onset['crossing_lower_utc'] == '2026-07-01T11:00:00+00:00' and
                  onset['crossing_upper_utc'] == '2026-07-01T12:00:00+00:00' and
                  onset['crossing_point_utc'] == '2026-07-01T11:01:09.649776747+00:00' and not case['if_released_propagation'])
        check('lag_unknown_and_no_qualification:' + rid, case['initiation_to_release_delay_seconds'] is None and
              line['initiation_to_release_delay_seconds'] is None and not present(run['initiation_to_release_delay_seconds']) and
              all(not flag(run[k]) for k in ['scientifically_qualified_for_prediction', 'regional_accuracy_qualified',
                  'mass_conservation_qualified', 'include_in_arrival_envelope', 'accepted_arrival_envelope_run_membership']))
        check('paper_points_match_executed_case:' + rid,
              all(t['id'] in points and np.allclose(points[t['id']][:2], t['xy'], rtol=0, atol=1e-6) for t in case['targets']))
        actual_release = Path(case['release']).resolve()
        check('release_is_approved_role:' + rid, actual_release in roles['immutable native release thickness'])
        check('actual_release_hash_binding:' + rid, sha(actual_release) == case['release_sha256'] == case['source_release_reference']['sha256'])
        with rasterio.open(actual_release) as ds:
            supplied, transform, crs = ds.read(1).astype(float), ds.transform, str(ds.crs)
        check('release_grid_CRS:' + rid, crs == 'EPSG:32645' and transform.a == resolution and transform.e == -resolution and
              transform.b == transform.d == 0)
        positive, cell_area = supplied > 0, resolution ** 2
        actual_volume = float(supplied[positive].sum() * cell_area)
        equivalent_area = actual_volume / vertical
        check('actual_release_volume_and_equivalent_area:' + rid, close(actual_volume, case['release_grid_volume_m3'], rtol=1e-12) and
              close(actual_volume, volume, rtol=2e-7) and close(equivalent_area, area, rtol=2e-7))
        field = unique(bundle['files'], role='actual_official_process_fields', run_id=rid)
        check('actual_case_execution_log_binding:' + rid, sha(case_path) == field['case_sha256'] and
              sha(export / f'provenance/{rid}/execution.json') == field['execution_sha256'] and
              sha(export / f'provenance/{rid}/run.log') == field['log_sha256'])
        parser = export / 'provenance/postprocessing' / Path(field['parser_source_snapshot_path']).name
        check('actual_parser_binding:' + rid, parser in roles['actual parser source snapshot bound to selected process fields'] and
              sha(parser) == field['parser_sha256_at_start'])
        with np.load(field['path'], allow_pickle=False) as z:
            time, depth, tr, stored_volume = [z[k].copy() for k in ['time_s', 'depth_frames', 'transform', 'volume_m3']]
        check('saved_field_time_grid:' + rid, len(time) == depth.shape[0] == len(stored_volume) and depth.shape[1:] == supplied.shape and
              np.all(np.isfinite(depth)) and depth.min() >= 0 and np.all(np.diff(time) > 0) and close(time[0], 0) and
              np.array_equal(tr, np.array(tuple(transform))) and close(time[-1], field['time_end_seconds']) and close(time[-1], run['actual_end_time_seconds']))
        metric, raw_validation = unique(metrics, run_id=rid), json.loads(run['raw_validation_json'])
        with (export / f'provenance/{rid}/native_internal_summary.txt').open() as stream:
            native = [x for x in csv.DictReader(stream, delimiter='\t') if x['nout'].isdigit()]
        native_initial, native_final = float(native[0]['volume']), float(native[-1]['volume'])
        initial_saved_volume = float(depth[0].astype(float).sum() * cell_area)
        initial_depth_difference = float(np.abs(depth[0] - supplied).max())
        native_positive = depth[0] > 0
        lost_support = positive & ~native_positive
        lost_supplied_volume = float(supplied[lost_support].sum() * cell_area)
        check('saved_initial_state_input_rounding_audit:' + rid, initial_depth_difference <= 0.00051 and
              close(initial_saved_volume, stored_volume[0], rtol=1e-12) and
              abs(initial_saved_volume - actual_volume) <= 0.00051 * int(positive.sum()) * cell_area and
              close(initial_depth_difference, raw_validation['initial_depth_vs_supplied_max_difference_m'], rtol=1e-8))
        native_residual, saved_residual = native_final / native_initial - 1, float(stored_volume[-1] / stored_volume[0] - 1)
        check('native_internal_budget_reproduced:' + rid, native[0]['nout'] == '0' and close(native[0]['tsum'], 0) and
              close(native[-1]['tsum'], time[-1]) and close(native_initial, raw_validation['native_internal_summary_initial_phase_volumes_m3'][0]) and
              close(native_final, raw_validation['native_internal_summary_final_phase_volumes_m3'][0]) and
              close(native_residual, metric['native_internal_summary_mass_budget_relative_residual'], rtol=1e-8) and
              all(x == 0 for x in raw_validation['native_signed_entrainment_phase_volumes_m3']) and
              all(x == 0 for x in raw_validation['native_edge_store_outflow_phase_volumes_m3']))
        check('saved_raster_budget_reproduced_separately:' + rid,
              close(saved_residual, metric['ascii_raster_source_adjusted_budget_relative_residual'], rtol=1e-8))
        release_audit.append(dict(run_id=rid, base_scenario_id=base, original_release_geometry_version=source['geometry_version'],
            mapped_release_geometry_version=MAPPING_VERSION, declared_source_geometry_sha256=case['source_geometry_sha256'],
            source_mapping=case['source_mapping'], exact_compact_polygon_delivered=False, independent_mapping_table_delivered=False,
            exact_polygon_independently_audited=False, original_plan_area_m2=area, mechanism_normal_thickness_m=normal,
            mechanism_theta_deg=angle, release_vertical_thickness_m=vertical, original_release_volume_m3=volume,
            actual_release_TIFF_volume_m3=actual_volume, actual_TIFF_volume_relative_difference=actual_volume / volume - 1,
            actual_weighted_equivalent_area_m2=equivalent_area, positive_source_support_cells=int(positive.sum()),
            native_initial_positive_support_cells=int(native_positive.sum()),
            supplied_positive_cells_zero_in_native_t0=int(lost_support.sum()),
            supplied_volume_in_cells_zero_in_native_t0_m3=lost_supplied_volume,
            native_positive_cells_outside_supplied_support=int((native_positive & ~positive).sum()),
            positive_source_support_cell_area_m2=int(positive.sum()) * cell_area, equivalent_full_source_cells=area / cell_area,
            grid_resolution_m=resolution, density_kg_m3=density, passive_material_fractions=json.dumps(fractions, sort_keys=True),
            native_solver_phase='one equivalent_bulk phase; composition passive', actual_release_raster_sha256=sha(actual_release),
            saved_initial_depth_integral_m3=initial_saved_volume, native_internal_initial_volume_m3=native_initial,
            saved_initial_max_depth_difference_m=initial_depth_difference, I_O_rounding_audit_bound_m=0.00051,
            native_internal_budget_relative_residual=native_residual, saved_raster_budget_relative_residual=saved_residual,
            budget_representations_separate=True, mass_conservation_qualified=False, scientifically_qualified_for_prediction=False))
        onset_row = dict(run_id=rid, base_scenario_id=base, original_model_id=old['model_id'], analytic_model_id=new_model,
            original_full_history_onset_status=outcome['onset_status'], original_evaluation_window_onset_status=outcome['evaluation_onset_status'],
            analytic_evaluation_window_onset_status=analytic_outcome['evaluation_onset_status'],
            original_global_crossing_point_utc=outcome['crossing_time_utc'] or None,
            original_global_crossing_lower_hours=outcome['crossing_lower_hours'] or None,
            original_global_crossing_upper_hours=outcome['crossing_upper_hours'] or None,
            analytic_full_history_onset_status=onset['status'], analytic_crossing_lower_utc=onset['crossing_lower_utc'] or None,
            analytic_crossing_upper_utc=onset['crossing_upper_utc'] or None, analytic_interpolated_point_utc=onset['crossing_point_utc'] or None,
            analytic_trace_start_utc=onset['start_utc'], analytic_trace_end_utc=onset['end_utc'],
            evaluation_window_first_unstable_is_new_start=False, forecast_input_mode=onset['forecast_input_mode'],
            time_scope='analytic full supplied history; original later evaluation-window status retained separately')
        onset_audit.append(onset_row)
        lineage.append(dict(run_id=rid, base_scenario_id=base, source_release_scenario_id=source['scenario_id'], mechanism_id=mechanism,
            original_model_id=old['model_id'], analytic_model_id=new_model, analytic_scenario_id=onset['scenario_id'],
            parameter_version=PARAMETER_VERSION, mechanism_geometry_version=old['geometry_version'],
            original_release_geometry_version=source['geometry_version'], mapped_release_geometry_version=MAPPING_VERSION,
            physical_parameters_compared=20, physical_parameters_unchanged=True, analytic_contract_version=contract['contract_version'],
            if_released_propagation=case['if_released_propagation'], initiation_to_release_delay_seconds=None,
            adapter_lineage_status='accepted_exact_compact_parent_and_registered_SH_STH_analytic_replacement'))

        yy, xx = np.indices(supplied.shape)
        xx, yy = transform.c + (xx + 0.5) * transform.a, transform.f + (yy + 0.5) * transform.e
        half = resolution / 2
        rectangles = [(float(xx[j, i] - half), float(xx[j, i] + half), float(yy[j, i] - half), float(yy[j, i] + half))
                      for j, i in zip(*np.nonzero(positive))]
        distance = support_distance(xx, yy, rectangles)
        horizon, permitted = float(run['requested_horizon_seconds']), time <= float(run['requested_horizon_seconds'])
        requested_max, actual_max = depth[permitted].max(axis=0), depth.max(axis=0)
        check('impact_area_reproduces_saved_metric:' + rid, close(np.count_nonzero(actual_max >= 0.1) * cell_area, metric['impact_area_m2']))
        for scope, hmax, last in [('saved_outputs_through_requested_horizon', requested_max, float(time[permitted][-1])),
                                 ('all_actual_saved_outputs', actual_max, float(time[-1]))]:
            for threshold in [0.1, 1, 5]:
                wet = hmax >= threshold
                footprints.append(dict(run_id=rid, base_scenario_id=base, scope=scope, threshold_depth_m=threshold,
                    requested_horizon_seconds=horizon, last_included_saved_seconds=last, grid_resolution_m=resolution,
                    affected_cell_count=int(wet.sum()), affected_plan_area_m2=float(wet.sum() * cell_area),
                    maximum_affected_cell_centre_distance_from_release_support_m=float(distance[wet].max()) if wet.any() else None,
                    distance_definition='Euclidean affected cell-centre to union of positive actual release raster cell footprints',
                    metric_crs='EPSG:32645', exact_compact_polygon_distance=False, footprint_is_validated_hazard_zone=False,
                    validated_warning_distance_m=None, scientifically_qualified_for_prediction=False,
                    mass_conservation_qualified=False, arrival_probability=None, source_fields_sha256=field['sha256']))
        panels.append((base, requested_max, positive, xx, yy))
        for target in [x for x in targets if x['run_id'] == rid]:
            tid = target['target_id']
            check('target_exact_lineage:' + rid + ':' + tid, all(target[k] == run[k] for k in [
                'scenario_id', 'base_scenario_id', 'upstream_model_id', 'upstream_parameter_version', 'geometry_version', 'release_mapping_version', 'parameter_version']))
            check('target_no_qualification_or_lag:' + rid + ':' + tid, all(not flag(target[k]) for k in [
                'scientifically_qualified_for_prediction', 'mass_conservation_qualified', 'regional_accuracy_qualified',
                'include_in_arrival_envelope', 'accepted_arrival_envelope_run_membership']) and
                not present(target['probability_weight']) and not present(target['initiation_to_release_delay_seconds']))
            check('target_geometry_version:' + rid + ':' + tid, tid in points and points[tid][2] == target['target_geometry_version'])
            tx, ty, _ = points[tid]
            mask = np.hypot(xx - tx, yy - ty) <= 100
            actual, formal = saved_first_hit(time, depth, mask, float(time[-1])), saved_first_hit(time, depth, mask, horizon)
            agrees = actual['hit'] == flag(target['observed_hit']) and all(
                (actual[k] is None and not present(target[column])) or
                (actual[k] is not None and present(target[column]) and close(actual[k], target[column]))
                for k, column in [('lower', 'arrival_bracket_lower_seconds'), ('upper', 'arrival_bracket_upper_seconds')])
            check('actual_field_target_reproduction:' + rid + ':' + tid, agrees and
                  target['source_fields_sha256'] == field['sha256'] and flag(target['target_field_hash_matches']))
            target_audit.append(dict(run_id=rid, target_id=tid, grid_resolution_m=resolution, target_buffer_cell_count=int(mask.sum()),
                actual_last_saved_seconds=actual['last_saved'], actual_first_hit_lower_seconds=actual['lower'],
                actual_first_hit_upper_seconds=actual['upper'], recomputed_actual_status=actual['status'],
                requested_last_saved_seconds=formal['last_saved'], requested_first_hit_lower_seconds=formal['lower'],
                requested_first_hit_upper_seconds=formal['upper'], requested_horizon_status=formal['status'],
                original_actual_hit_and_bracket_agree=agrees, source_field_binding_agrees=True,
                target_point_to_release_raster_support_distance_m=float(support_distance(np.array(tx), np.array(ty), rectangles))))
            joined.append(dict(run_id=rid, scenario_id=base, base_scenario_id=base, event_id=bundle['common_context']['event_id'],
                source_analytic_scenario_id=onset['scenario_id'], original_upstream_model_id=old['model_id'], analytic_onset_model_id=new_model,
                propagation_model_id=run['model_id'], mechanism_id=mechanism, parameter_version=PARAMETER_VERSION,
                mechanism_geometry_version=old['geometry_version'], release_geometry_version=MAPPING_VERSION,
                release_mapping_version=MAPPING_VERSION, grid_resolution_m=resolution, target_id=tid,
                entity_id=target['entity_id'] or None, target_kind=target['target_kind'] or None, target_geometry_version=target['target_geometry_version'],
                source_first_passage_status=onset['status'], original_upstream_onset_status=source['onset_status'],
                original_full_history_onset_status=outcome['onset_status'],
                original_global_crossing_point_utc=outcome['crossing_time_utc'] or None,
                original_global_crossing_lower_hours=outcome['crossing_lower_hours'] or None,
                original_global_crossing_upper_hours=outcome['crossing_upper_hours'] or None,
                original_global_hours_origin_utc=contract['time_origin_utc'],
                original_evaluation_window_onset_status=outcome['evaluation_onset_status'], evaluation_window_first_unstable_is_new_start=False,
                analytic_evaluation_window_onset_status=analytic_outcome['evaluation_onset_status'],
                source_evaluation_onset_status=analytic_outcome['evaluation_onset_status'],
                source_history_risk_at_evaluation_start=('already_unstable_left_censored;not_a_new_observed_start_in_evaluation_window'
                    if outcome['evaluation_onset_status'] == 'left_censored_already_unstable' else None),
                conditional_onset_lower_utc=onset['crossing_lower_utc'] or None, conditional_onset_upper_utc=onset['crossing_upper_utc'] or None,
                conditional_onset_interpolated_point_utc=onset['crossing_point_utc'] or None, forecast_input_mode=onset['forecast_input_mode'],
                if_released_propagation=case['if_released_propagation'], initiation_to_release_delay_seconds=None, time_origin='bulk_release',
                physical_phase='conditional_bulk_release_to_target_arrival', raw_conditional_arrival_status=target['arrival_status'],
                diagnostic_bulk_release_arrival_lower_seconds=actual['lower'], diagnostic_bulk_release_arrival_upper_seconds=actual['upper'],
                diagnostic_arrival_within_requested_horizon=formal['hit'], requested_horizon_seconds=horizon,
                last_saved_within_requested_horizon_seconds=formal['last_saved'], actual_last_saved_seconds=actual['last_saved'],
                arrival_definition=target['arrival_definition'], diagnostic_observation_available=flag(target['diagnostic_observation_available']),
                conditional_diagnostic_range_eligible=flag(target['conditional_diagnostic_range_eligible']), diagnostic_eligibility_is_qualification=False,
                absolute_arrival_lower_utc=None, absolute_arrival_upper_utc=None, absolute_arrival_time_utc=None,
                qualified_arrival_lower_seconds=None, qualified_arrival_upper_seconds=None, arrival_probability=None, probability_weight=None,
                include_in_arrival_envelope=False, accepted_arrival_envelope_run_membership=False,
                numerical_qualification=run['numerical_qualification'], mass_conservation_qualified=False,
                regional_accuracy_qualified=False, scientifically_qualified_for_prediction=False,
                scientific_acceptance_decision_version=decision['version'], arrival_envelope_semantics_version=bundle['arrival_envelope_semantics_version'],
                event_timing_validated=False, arrival_is_initiation_truth=False, evaluation_stratum='conditional_scenario', independent_local_validation_events=0,
                adapter_lineage_status='accepted_exact_compact_SH_STH_lineage',
                arrival_status='unqualified_conditional_diagnostic;unknown_initiation_to_bulk_release_lag', source_fields_sha256=field['sha256']))

    check('all14_lineage_rows_retained', len(joined) == 14)
    check('two_junction_raw_hits_12_saved_nonhits', sum(x['actual_first_hit_upper_seconds'] is not None for x in target_audit) == 2 and
          all(x['target_id'] == 'paper_junction' for x in target_audit if x['actual_first_hit_upper_seconds'] is not None))
    check('absolute_qualified_probability_outputs_null', all(all(x[k] is None for k in ['absolute_arrival_lower_utc',
        'absolute_arrival_upper_utc', 'absolute_arrival_time_utc', 'qualified_arrival_lower_seconds', 'qualified_arrival_upper_seconds',
        'arrival_probability', 'probability_weight']) for x in joined))
    check('no_accepted_envelope_output', all(not x['include_in_arrival_envelope'] and not x['accepted_arrival_envelope_run_membership'] for x in joined))
    write_csv(out / 'lineage_audit.csv', lineage)
    write_csv(out / 'physical_parameter_audit.csv', parameters)
    write_csv(out / 'release_mapping_audit.csv', release_audit)
    write_csv(out / 'onset_scope_audit.csv', onset_audit)
    write_csv(out / 'conditional_arrivals.csv', joined)
    write_csv(out / 'saved_field_target_checks.csv', target_audit)
    write_csv(out / 'depth_footprint_diagnostics.csv', footprints)
    write_csv(out / 'rejected_pairings.csv', [], ['run_id', 'target_id', 'reason'])
    write_json(out / 'adapter_schema.json', dict(version='q3-compact-SH-STH-delta-v1', explicit_model_replacements=MODEL_REPLACEMENTS,
        matching='exact linear base/model/mechanism/parameter/geometry keys; no thaw-sibling or approximate match',
        physical_fields_compared=PHYSICAL_FIELDS, original_evaluation_window_status_retained=True,
        original_evaluation_first_unstable_is_new_start=False, unknown_release_lag=True,
        material_fractions_are_solver_phase_fractions=False, H_mechanism_implies_free_release_water=False,
        compact_polygon_delivered=False, exact_polygon_independently_audited=False,
        selected_runs_are_2048_weighted_ensemble=False, accepted_arrival_envelope_run_ids=[],
        adapter_QA_is_predictive_qualification=False))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, (base, hmax, positive, xx, yy) in zip(axes, panels):
        image = ax.pcolormesh(xx / 1000, yy / 1000, np.ma.masked_where(hmax < 0.1, hmax), cmap='viridis',
                              shading='nearest', vmin=0, vmax=60)
        ax.contour(xx / 1000, yy / 1000, positive.astype(float), levels=[0.5], colors=['red'], linewidths=1.1)
        for tid, (tx, ty, _) in points.items():
            ax.scatter(tx / 1000, ty / 1000, marker='x', color='black', s=13)
            if tid in ['paper_junction', 'paper_port_symbol']:
                ax.annotate(tid.replace('paper_', ''), (tx / 1000, ty / 1000), xytext=(3, 3), textcoords='offset points', fontsize=7)
        ax.set_aspect('equal')
        ax.set_title(base + '\nUNQUALIFIED; saved outputs <=1800s', fontsize=9)
        ax.set_xlabel('Easting (km; EPSG:32645)')
        ax.set_ylabel('Northing (km; EPSG:32645)')
    fig.colorbar(image, ax=axes, label='Saved-output maximum depth (m; shown >=0.1m)', shrink=0.8)
    fig.suptitle('Compact SH/STH diagnostics; red = release raster support; black x = target representatives\nNo absolute arrival time, probability or validated warning distance', fontsize=11)
    fig.savefig(out / 'conditional_footprints.png', dpi=180)
    plt.close(fig)
    summary = dict(status='compact_delta_v1_adapter_executed_unqualified_diagnostics_only', bundle_version=bundle['bundle_version'],
        bundle_sha256=PIN, producer_bundle_sha256=PRODUCER_PIN, delivered_files_verified=48,
        selected_physical_runs=2, unique_base_parameter_scenarios=2, representative_targets=7, osm_representative_points=5,
        osm_candidate_entities=3, paper_candidate_points=2, run_target_rows=14, accepted_lineage_pairs=14, rejected_lineage_pairs=0,
        raw_saved_junction_hits=2, raw_saved_target_nonhits=12, independent_local_validation_events=0,
        qualified_arrival_rows=0, qualified_arrival_envelope_rows=0, absolute_arrival_rows=0, probability_rows=0, probability_weights=None,
        selected_runs_are_2048_probability_ensemble=False, physical_parameters_compared_per_run=20,
        SH_no_start_if_released_preserved=True, STH_global_analytic_crossing_preserved=True,
        STH_original_evaluation_left_censored_preserved=True, evaluation_window_first_unstable_is_new_start=False,
        compact_exact_polygon_independently_audited=False, actual_compact_release_raster_volume_audited=True,
        release_mapping_version=MAPPING_VERSION, mass_conservation_qualified=False, regional_accuracy_qualified=False,
        scientifically_qualified_for_prediction=False, accepted_arrival_envelope_run_ids=[],
        scientific_acceptance_decision_version=decision['version'], no_physical_solver_rerun=True,
        no_old_v2_or_fullmask_v3_file_modified=True)
    write_json(out / 'summary.json', summary)
    write_json(out / 'status.json', summary)
    (out / 'RESULTS.md').write_text('''# Compact SH/STH delta adapter results

All **48 delivered role objects** and the producer snapshot were pinned and verified. Exact lineage succeeds for all **14 rows = 2 selected runs x 7 representative points**, with zero rejected pairs. These are two additional conditional numerical cases, not two independent events or a probability sample. Five OSM points represent three candidate entities; two paper points remain candidate objects.

Both exact linear branches preserve all **20 shared physical parameters**, parameter version, law policy and mechanical slab geometry through the registered model replacements `q2r3_SH_v1 -> q2r3_S_H_analytic_v1` and `q2r3_STH_v1 -> q2r3_S_T_H_analytic_v1`. Thaw siblings are excluded by exact base ID. The embedded original Q2-v1 release catalogue is byte-identical to the previously frozen Q3 copy and matches its original upstream hash.

The p0072 prescribed compact source has area **100,000m²**, normal thickness38.2499348559m, vertical thickness51.0000686576m and volume5,100,006.8658m³. p0255 has area **40,000m²**, normal thickness15.8932673403m, vertical thickness31.3878657458m and volume1,255,514.6298m³. Approved actual release TIFF integrals, equivalent areas, case parameters, passive rock/ice volume fractions, density and zero velocity agree. H does not mean nonzero free-water release: both parent catalogues explicitly prescribe free-water fraction0 and one equivalent bulk solver phase with passive composition. The original release table has only a conditional area; Q4 declares a compact-circle mapping. No compact vector polygon or independent mapping table was delivered, so that exact boundary is not independently certified. Positive raster cell support is larger than weighted plan area at partial edge cells.

p0072 retains **no_cross_observed_complete** with null onset time, and propagation is only **if released**. p0255 uses the analytic full-history **July1 11:00–12:00 UTC** bracket and new interpolation **11:01:09.649776747 UTC**, replacing the old global interpolation11:19:16.802118373. Its original later evaluation-window status **left_censored_already_unstable** is separately retained. A first already-unstable evaluation sample is not a new known start inside that evaluation window. All onset timestamps here are conditional retrospective ideal-weather mechanism outputs, not observed release or operational forecast truth.

Independent saved-field checks reproduce two paper-junction brackets: p0072 **(801.1,820.6]s**, p0255 **(1400.1,1420.5]s** after assumed bulk release. Detection uses h>=0.1m at registered cell centres within100m representative-point buffers, with previous-below/first-above saved-output brackets rather than solver-step precision. The other12 rows have no threshold hit at saved outputs; this does not establish continuous-time non-arrival or safety. Requested1800s, last saved output inside it, and actual final1800.9/1802.0s are separate fields.

Both remain **mass-conservation, regional and scientifically unqualified**. Native internal budget residuals **+11.66547% / +12.40282%** and saved-raster residuals remain separate in `release_mapping_audit.csv`; no passing tolerance is inferred from them. Decision05's accepted-run list is empty. Raw diagnostic availability/eligibility does not upgrade acceptance. All absolute arrival times, qualified intervals, probabilities and weights are null; initiation-to-bulk-release delay is unknown and never assumed zero.

Input/output quantization is explicit: p0072 has40 positive supplied TIFF cells but39 positive native initial cells. One supplied edge cell of depth0.0000740281m / volume0.2665011m³ rounds to zero in the three-decimal native output; maximum initial depth difference is0.000495911m. p0255 retains16 positive cells, with maximum initial difference0.000473022m. These are separate support definitions, not a claim of exact support identity or a scientific qualification pass.

Descriptive 0.1/1/5m footprint diagnostics use only actual stored fields, for outputs <=1800s and all actual saved outputs. Area is affected cell area; distance is affected cell-centre Euclidean distance to the union of positive **actual per-run release raster cell footprints**, not exact compact polygon runout, centroid/cost-path distance or a validated warning distance/hazard zone. The actual two-panel figure is explicitly unqualified. Together with the earlier two compact and three fullmask runs, root may compare seven numerical runs from four mechanical designs; none becomes an independent validation event or weighted2048-member result.

Reproduce from the Q3 worktree:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 track_b/.venv/bin/python track_b/research/q3/round3/scripts/join_compact_delta_v1.py
```

The independent `review/` directory is excluded from this adapter's own output index; root seals it together with the stable adapter results. No prior v2/fullmask-v3 script, result, imported packet or export is modified.
''')
    add_input(out / 'PROTOCOL.md', 'registered precomputation protocol')
    add_input(Path(__file__), 'actually executed compact delta adapter source')
    for entry in index.values():
        p = resolve(entry['path'])
        check('input_unchanged_during_adapter:' + entry['path'], p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256'])
    review_path = out / 'figure_review.json'
    if review_path.exists():
        visual = read_json(review_path)
        check('actual_visual_figure_binding', visual.get('passed') is True and len(visual.get('figures', [])) == 1 and
              visual['figures'][0]['actually_opened'] is True and resolve(visual['figures'][0]['path']) == out / 'conditional_footprints.png' and
              visual['figures'][0]['sha256'] == sha(out / 'conditional_footprints.png'))
    input_records = sorted(index.values(), key=lambda x: x['path'])
    check('deduplicated_input_index_paths', len(input_records) == len({x['path'] for x in input_records}))
    write_json(out / 'input_index.json', dict(files=input_records, file_list_excludes_self=True, exact_delivered_role_objects_verified=48,
        roles_merged_for_repeated_canonical_paths=True, path_resolution='Q3 ROOT-relative repository paths; exact approved cache paths',
        source_and_upstream_metadata_paths_are_not_read_permissions=True, no_active_other_question_worktree_reads=True))
    output_records = [file_record(p, 'new compact delta output') for p in sorted(out.iterdir()) if p.is_file() and
                      p.name not in ['output_index.json', 'validation.json']]
    write_json(out / 'output_index.json', dict(files=output_records, file_list_excludes_self=True,
        validation_excluded_to_avoid_cycle=True, independent_review_directory_excluded=True, no_recursive_output_traversal=True))
    write_json(out / 'validation.json', dict(passed=all(x['passed'] for x in checks), generated_at_utc=datetime.now(timezone.utc).isoformat(),
        check_count=len(checks), checks=checks, adapter_pass_is_predictive_qualification=False,
        input_index_sha256=sha(out / 'input_index.json'), output_index_sha256=sha(out / 'output_index.json'),
        figure_visual_qa='passed_external_visual_inspection' if review_path.exists() else 'pending_external_visual_inspection'))
    print(json.dumps(summary, ensure_ascii=False))
    print(f'Adapter QA: {len(checks)}/{len(checks)} passed; inputs={len(input_records)}, outputs={len(output_records)}')


if __name__ == '__main__':
    main()

