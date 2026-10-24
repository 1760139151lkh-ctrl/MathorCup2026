#!/usr/bin/env python3
"""Audit an explicitly mapped Q4 packet without rerunning propagation physics.

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
PIN = '9fec7f2083ab43f81b19da2c1cca3cef9b2ad0b5db36441495162412d1e8dda4'
DEFAULT_BUNDLE = R / 'inputs/q4/bundle_q4-r3-propagation-v2/bundle.json'
DEFAULT_OUT = R / 'results/arrival/propagation_v2'
MODEL_REPLACEMENTS = {
    'q2r3_S_v1': ('S', 'q2r3_S_analytic_v1'),
    'q2r3_ST_v1': ('S_T', 'q2r3_S_T_analytic_v1'),
}
PARAMETER_VERSION = 'q2r3-design-v1'
MAPPING_VERSION = 'q4-r3-q2-mapped-release-v1'
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
    if not bp.is_relative_to(R / 'inputs/q4') or out != DEFAULT_OUT:
        raise ValueError('Only the imported Q4 packet and owned propagation_v2 output are allowed')
    if args.expected_sha256 != PIN or sha(bp) != PIN:
        raise ValueError('Unregistered Q4 packet SHA256')
    if not (out / 'PROTOCOL.md').exists():
        raise ValueError('Read/retain the registered protocol before running')
    out.mkdir(parents=True, exist_ok=True)
    checks, inputs, role_files = [], [file_record(bp, 'pinned delivered packet')], {}

    def check(name, passed, detail=None):
        entry = dict(name=name, passed=bool(passed))
        if detail is not None:
            entry['detail'] = detail
        checks.append(entry)
        if not passed:
            raise ValueError(f'Failed adapter check: {name}; {detail}')

    bundle = read_json(bp)
    for f in bundle['files']:
        p = resolve(f['path']).resolve()
        allowed = p.is_relative_to(bp.parent) or (
            f.get('storage') == 'immutable_external_cache' and p.is_relative_to(CACHE))
        check('delivered_path_scope:' + relative(p), allowed)
        check('delivered_hash:' + relative(p),
              p.stat().st_size == f['bytes'] and sha(p) == f['sha256'])
        role_files.setdefault(f['role'], []).append(p)
        inputs.append(file_record(p, f['role']))
    check('exact_delivered_file_count', len(bundle['files']) == 39)

    def role(name):
        pp = role_files.get(name, [])
        check('unique_role:' + name, len(pp) == 1)
        return pp[0]

    export = role('model_runs').parent
    run_rows, target_rows = rows(role('model_runs')), rows(role('target_arrivals'))
    metrics = rows(role('comparison_metrics'))
    source_release = export / 'provenance/upstream_q2/release_states.csv'
    original_bundle = read_json(export / 'provenance/upstream_q2/bundle.json')
    original_upstream = read_json(export / 'provenance/upstream_q2/upstream_bundle.json')
    release_rows = rows(source_release)
    check('compact_original_release_hash_from_upstream',
          sha(source_release) == unique(original_upstream['files'], role='results/release_states.csv')['sha256'])
    check('compact_received_and_original_bundle_agree',
          unique(original_bundle['files'], role='results/release_states.csv')['sha256'] == sha(source_release))
    check('only_two_registered_runs', set(x['run_id'] for x in run_rows) == set(bundle['selected_run_ids'])
          and len(run_rows) == 2)
    check('14_rows_7_representative_targets', len(target_rows) == 14 and
          len(set(x['target_id'] for x in target_rows)) == 7)

    oldroot = R / 'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1'
    newroot = R / 'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1'
    pp = oldroot / 'files/results/parameter_ensemble.csv'
    ap = newroot / 'files/results/analytic_thermal/parameter_ensemble.csv'
    cp = newroot / 'files/results/analytic_thermal/mechanism_contract.json'
    fp = R / 'results/engine_a/analytic_erfc/first_passages.csv'
    gp = R / 'inputs/q2/release_bundle_v2_q2-r3-release-v2-spatial-copdem-v1/files/results/release_states_geometry_v2.csv'
    oldscript = R / 'scripts/join_propagation.py'
    for p, description in [(pp, 'original shared physical parameters'), (ap, 'analytic shared physical parameters'),
                           (cp, 'analytic explicit release-join contract'), (fp, 'frozen analytic first passages'),
                           (gp, 'different broad-source release-v2 comparison'), (oldscript, 'previous adapter source')]:
        inputs.append(file_record(p, description))
    for rootp, required in [(oldroot, [pp]), (newroot, [ap, cp])]:
        imported = read_json(rootp / 'bundle.json')
        inputs.append(file_record(rootp / 'bundle.json', 'existing Q3 imported Q2 manifest'))
        for p in required:
            match = [f for f in imported['files'] if resolve(f['path']).resolve() == p.resolve()]
            check('existing_import_hash:' + relative(p), len(match) == 1 and
                  sha(p) == match[0]['sha256'] and p.stat().st_size == match[0]['bytes'])
    check('same_original_parameter_ensemble_as_compact_release',
          sha(pp) == unique(original_upstream['files'], role='results/parameter_ensemble.csv')['sha256'])
    contract = read_json(cp)
    check('analytic_contract_allows_release_join',
          contract['parameter_version'] == PARAMETER_VERSION and
          contract['base_scenario_join'] == 'base_scenario_id joins v1/v2 and release-geometry-v2; release states unchanged, use this model version onset/censoring when combined')
    original_parameters, analytic_parameters = rows(pp), rows(ap)
    onsets, broad_sources = rows(fp), rows(gp)
    lineage_audit, parameter_audit, release_audit, geometry_comparison, legacy_comparison = [], [], [], [], []
    joined, target_checks, footprints, arrays = [], [], [], []
    resolved_by_run = {}
    # Raster readers are used only after every approved external object was hashed.
    import rasterio
    from pyproj import Transformer
    target_points = {x['target_id']: (float(x['x_m']), float(x['y_m']), x['geometry_version'])
                     for x in rows(export / 'geometry/spatial_targets_v2.csv')}
    geometries = read_json(export / 'geometry/computational_geometries.geojson')
    lonlat_to_metric = Transformer.from_crs('EPSG:4326', 'EPSG:32645', always_xy=True)
    for f in geometries['features']:
        if f['geometry']['type'] == 'Point':
            p = f['properties']
            tx, ty = lonlat_to_metric.transform(*f['geometry']['coordinates'])
            target_points[p['space_id']] = (tx, ty, p['geometry_version'])

    for run in run_rows:
        rid, base = run['run_id'], run['base_scenario_id']
        lineage = unique(bundle['lineage_by_run'], run_id=rid)
        case_path = export / f'provenance/{rid}/case.json'
        case = read_json(case_path)
        check('paper_lonlat_to_metric_matches_executed_case:' + rid,
              all(t['id'] in target_points and np.allclose(target_points[t['id']][:2], t['xy'],
                  rtol=0, atol=1e-6) for t in case['targets']))
        release = unique(release_rows, scenario_id=base)
        old = unique(original_parameters, scenario_id=base)
        check('registered_model_replacement:' + rid, release['model_id'] in MODEL_REPLACEMENTS)
        mechanism, new_model = MODEL_REPLACEMENTS[release['model_id']]
        check('contract_model_replacement:' + rid, contract['model_ids'][mechanism] == new_model)
        new = unique(analytic_parameters, base_scenario_id=base, model_id=new_model)
        onset = unique(onsets, base_scenario_id=base, model_id=new_model,
                       mechanism_id=mechanism, parameter_version=PARAMETER_VERSION,
                       geometry_version=old['geometry_version'])
        keys = ['base_scenario_id', 'upstream_model_id', 'upstream_parameter_version',
                'mechanism_id', 'parameter_version', 'release_mapping_version', 'geometry_version']
        check('bundle_lineage_matches_model_run:' + rid, all(lineage[k] == run[k] for k in keys))
        check('explicit_original_release_lineage:' + rid,
              release['model_id'] == old['model_id'] == lineage['upstream_model_id'] == case['upstream_model_id'] and
              release['mechanism_id'] == old['mechanism_id'] == lineage['mechanism_id'] == mechanism and
              release['parameter_version'] == old['parameter_version'] == new['parameter_version'] ==
              case['upstream_parameter_version'] == lineage['upstream_parameter_version'] == PARAMETER_VERSION and
              case['scenario_id'] == lineage['scenario_id'] == base and
              case['geometry_version'] == lineage['geometry_version'] == lineage['release_mapping_version'] == MAPPING_VERSION)
        check('mechanism_geometry_preserved_across_model_replacement:' + rid,
              old['geometry_version'] == new['geometry_version'] == onset['geometry_version'])
        check('same_nonphysical_design_identity:' + rid,
              all(old[k] == new[k] for k in ['parameter_set_id', 'mechanism_id', 'law_policy',
                                            'parameter_version', 'geometry_version', 'design_role', 'prior_weight']))
        for key in PHYSICAL_FIELDS:
            same = close(old[key], new[key], rtol=1e-13, atol=1e-13)
            parameter_audit.append(dict(run_id=rid, base_scenario_id=base, parameter=key,
                                        original_value=old[key], analytic_value=new[key], identical=same))
            check(f'physical_parameter_preserved:{rid}:{key}', same)

        fractions = json.loads(release['phase_fractions'])
        iv = json.loads(release['initial_velocity'])
        area, normal, vertical, volume, density = map(float, [release['plan_area_m2'],
            release['release_thickness_normal_m'], release['release_thickness_vertical_m'],
            release['release_volume_m3'], release['density']])
        expected_vertical = normal / math.cos(math.radians(float(old['theta_deg'])))
        check('release_area_thickness_volume_and_density:' + rid,
              close(area, case['source_plan_area_m2']) and close(normal, old['thickness_normal_m']) and
              close(vertical, expected_vertical) and close(vertical, case['release_thickness_m']) and
              close(volume, area * vertical) and close(density, case['bulk_density_kg_m3']) and
              close(density, old['density_kg_m3']) and close(density, fractions['ice'] * 917 + fractions['rock'] * 2700))
        check('material_volume_composition_not_solver_phase:' + rid,
              release['phase_fraction_basis'] == case['passive_material_fraction_basis'] == 'volume' and
              fractions == case['passive_material_volume_fractions'] and
              close(sum(fractions.values()), 1) and case['phase_volume_fractions'] == [1])
        check('initial_zero_velocity:' + rid, all(iv[k] == 0 for k in ['x', 'y', 'z']) and
              case['initial_velocity_east_north_m_s'] == [0, 0])
        check('original_onset_kept_in_propagation_record:' + rid,
              release['onset_status'] == lineage['upstream_onset_status'] == case['upstream_onset_status'])
        never = onset['status'] == 'no_cross_observed_complete'
        check('never_cross_is_only_if_released:' + rid,
              not never or (flag(run['if_released_propagation']) and case['if_released_propagation'] and
                            not present(onset['crossing_lower_utc']) and not present(onset['crossing_upper_utc'])))
        check('unknown_release_lag_preserved:' + rid,
              case['initiation_to_release_delay_seconds'] is None and
              lineage['initiation_to_release_delay_seconds'] is None and
              not present(run['initiation_to_release_delay_seconds']))
        check('quality_does_not_upgrade:' + rid, not flag(run['include_in_arrival_envelope']) and
              not flag(run['mass_conservation_qualified']) and not flag(run['scientifically_qualified_for_prediction']) and
              run['numerical_qualification'] == 'unqualified_compact_source_underresolution_and_budget_discrepancy')

        release_path = Path(case['release']).resolve()
        check('release_array_is_explicitly_approved:' + rid,
              release_path in role_files['immutable native release thickness'] and
              sha(release_path) == case['release_sha256'] == case['source_release_reference']['sha256'])
        with rasterio.open(release_path) as ds:
            rel = ds.read(1).astype(float)
            transform = ds.transform
            check('release_crs_and_affine:' + rid, str(ds.crs) == 'EPSG:32645' and
                  transform.a == 60 and transform.e == -60 and transform.b == transform.d == 0)
        positive = rel > 0
        grid_volume = float(rel[positive].sum() * abs(transform.a * transform.e))
        effective_area = grid_volume / vertical
        check('raster_integrated_release_volume:' + rid,
              close(grid_volume, case['release_grid_volume_m3'], rtol=2e-7) and
              close(grid_volume, volume, rtol=2e-7) and close(effective_area, area, rtol=2e-7))
        m = unique(metrics, run_id=rid)
        check('underresolution_support_cells_match:' + rid, int(positive.sum()) == int(run['source_support_cells']) and
              close(area / 3600, run['source_equivalent_full_cells']))
        release_audit.append(dict(run_id=rid, base_scenario_id=base,
            original_release_geometry_version=release['geometry_version'], mapped_geometry_version=case['geometry_version'],
            original_plan_area_m2=area, normal_thickness_m=normal, theta_deg=float(old['theta_deg']),
            original_vertical_thickness_m=vertical, executed_vertical_thickness_m=case['release_thickness_m'],
            original_volume_m3=volume, supplied_raster_volume_m3=grid_volume,
            supplied_volume_relative_difference=grid_volume / volume - 1,
            raster_equivalent_area_m2=effective_area, positive_support_cell_count=int(positive.sum()),
            support_footprint_area_m2=int(positive.sum()) * 3600, equivalent_full_cells=area / 3600,
            density_kg_m3=density, material_fraction_basis='volume', material_fractions=json.dumps(fractions, sort_keys=True),
            native_solver_phase_fraction='[1] equivalent_bulk', initial_velocity='[0,0] m/s east,north',
            release_raster_sha256=sha(release_path), declared_source_geometry_sha256=case['source_geometry_sha256'],
            exact_compact_polygon_delivered=False, independent_mapping_table_delivered=False,
            exact_compact_polygon_area_independently_verified=False, case_to_original_release_audit_passed=True,
            ascii_budget_relative_residual=float(m['ascii_raster_source_adjusted_budget_relative_residual']),
            native_internal_budget_relative_residual=float(m['native_internal_summary_mass_budget_relative_residual']),
            numerical_qualification=run['numerical_qualification']))
        for b in broad_sources:
            if b['base_scenario_id'] == base:
                geometry_comparison.append(dict(run_id=rid, base_scenario_id=base,
                    executed_mapping_version=MAPPING_VERSION, executed_plan_area_m2=area,
                    executed_volume_m3=volume, different_release_scenario_id=b['scenario_id'],
                    different_geometry_version=b['geometry_version'], different_mapping_version=b['release_mapping_version'],
                    different_grid_resolution_m=b['grid_resolution_m'], different_area_m2=b['plan_area_m2'],
                    different_volume_m3=b['release_volume_m3'], interchangeable=False,
                    reason='broad_paper_mask_changes_release_area_and_volume; not_compact_mapping_alias'))
        la = dict(run_id=rid, base_scenario_id=base, mechanism_id=mechanism,
            original_model_id=old['model_id'], replacement_model_id=new_model,
            replacement_scenario_id=onset['scenario_id'], parameter_version=PARAMETER_VERSION,
            physical_parameter_fields_compared=len(PHYSICAL_FIELDS), all_physical_parameters_preserved=True,
            replacement_contract_version=contract['contract_version'],
            replacement_reason='explicit analytic-erfc thermal model version; same physical parameter design and release state',
            mechanism_geometry_version=old['geometry_version'], original_release_geometry_version=release['geometry_version'],
            mapped_release_geometry_version=MAPPING_VERSION, upstream_onset_status=release['onset_status'],
            analytic_onset_status=onset['status'], conditional_onset_lower_utc=onset['crossing_lower_utc'] or None,
            conditional_onset_upper_utc=onset['crossing_upper_utc'] or None,
            conditional_onset_interpolated_point_utc=onset['crossing_point_utc'] or None,
            forecast_input_mode=onset['forecast_input_mode'], if_released_propagation=flag(run['if_released_propagation']),
            initiation_to_release_delay_seconds=None, lineage_adapter_status='accepted_explicit_versioned_mapping',
            arrival_is_initiation_truth=False)
        lineage_audit.append(la)
        resolved_by_run[rid] = la

        field_rec = unique(bundle['files'], role='actual_official_process_fields', run_id=rid)
        check('field_provenance_binding:' + rid,
              sha(case_path) == field_rec['case_sha256'] and
              sha(export / f'provenance/{rid}/execution.json') == field_rec['execution_sha256'] and
              sha(export / f'provenance/{rid}/run.log') == field_rec['log_sha256'])
        with np.load(field_rec['path'], allow_pickle=False) as z:
            time = z['time_s'].copy()
            depth = z['depth_frames'].copy()
            tr = z['transform'].copy()
            cumulative = z['depth_max_native_cumulative'].copy()
        check('saved_depth_time_grid:' + rid, depth.shape[0] == len(time) and
              depth.shape[1:] == rel.shape and np.all(np.isfinite(depth)) and np.min(depth) >= 0 and
              np.all(np.diff(time) > 0) and np.array_equal(tr, np.array(tuple(transform))))
        check('actual_native_end_time:' + rid, close(time[-1], field_rec['time_end_seconds']) and
              close(time[-1], run['actual_end_time_seconds']))
        yy, xx = np.indices(rel.shape)
        xx = transform.c + (xx + 0.5) * transform.a
        yy = transform.f + (yy + 0.5) * transform.e
        rectangles = [(float(xx[j, i] - 30), float(xx[j, i] + 30),
                       float(yy[j, i] - 30), float(yy[j, i] + 30))
                      for j, i in zip(*np.nonzero(positive))]
        distance = support_distance(xx, yy, rectangles)
        horizon = float(run['requested_horizon_seconds'])
        upto = time <= horizon
        requested_max = np.max(depth[upto], axis=0)
        actual_max = np.max(depth, axis=0)
        check('saved_footprint_reproduces_delivered_area:' + rid,
              close(np.count_nonzero(actual_max >= 0.1) * 3600, m['impact_area_m2']))
        for scope, hmax, end in [('saved_outputs_through_requested_horizon', requested_max, float(time[upto][-1])),
                                 ('all_actual_saved_outputs', actual_max, float(time[-1]))]:
            for threshold in [0.1, 1.0, 5.0]:
                wet = hmax >= threshold
                footprints.append(dict(run_id=rid, base_scenario_id=base, scope=scope,
                    requested_horizon_seconds=horizon, last_included_saved_output_seconds=end,
                    threshold_depth_m=threshold, affected_cell_count=int(wet.sum()),
                    affected_plan_area_m2=int(wet.sum()) * 3600,
                    maximum_affected_cell_centre_distance_from_release_support_m=float(distance[wet].max()) if wet.any() else None,
                    distance_definition='max over affected cell centres of Euclidean distance to union of positive supplied-release cell footprints',
                    source_geometry='actual supplied compact release raster support, not broad candidate polygon',
                    metric_crs='EPSG:32645', grid_resolution_m=60, scientifically_qualified_for_prediction=False,
                    mass_conservation_qualified=False, validated_warning_distance_m=None,
                    footprint_is_validated_hazard_zone=False, arrival_probability=None,
                    source_fields_sha256=field_rec['sha256'], release_raster_sha256=sha(release_path)))
        arrays.append((base, requested_max, cumulative, positive, xx, yy))
        for target in [x for x in target_rows if x['run_id'] == rid]:
            tid = target['target_id']
            for key in ['scenario_id', 'base_scenario_id', 'upstream_model_id', 'upstream_parameter_version',
                        'geometry_version', 'release_mapping_version', 'parameter_version']:
                check(f'target_exact_lineage:{rid}:{tid}:{key}', target[key] == run[key])
            check('target_unknown_lag:' + rid + ':' + tid, not present(target['initiation_to_release_delay_seconds']))
            check('target_quality_exclusion_retained:' + rid + ':' + tid,
                  not flag(target['include_in_arrival_envelope']) and
                  not flag(target['scientifically_qualified_for_prediction']) and
                  not flag(target['mass_conservation_qualified']))
            check('target_explicit_geometry:' + rid + ':' + tid, tid in target_points and
                  target_points[tid][2] == target['target_geometry_version'])
            tx, ty, _ = target_points[tid]
            mask = np.hypot(xx - tx, yy - ty) <= 100
            actual = saved_first_hit(time, depth, mask, float(time[-1]))
            formal = saved_first_hit(time, depth, mask, horizon)
            hit_matches = actual['hit'] == flag(target['observed_hit'])
            bracket_matches = ((actual['lower'] is None and not present(target['arrival_bracket_lower_seconds'])) or
                (actual['lower'] is not None and close(actual['lower'], target['arrival_bracket_lower_seconds']))) and (
                (actual['upper'] is None and not present(target['arrival_bracket_upper_seconds'])) or
                (actual['upper'] is not None and close(actual['upper'], target['arrival_bracket_upper_seconds'])))
            check('independent_actual_field_arrival:' + rid + ':' + tid, hit_matches and bracket_matches and
                  field_rec['sha256'] == target['source_fields_sha256'] and flag(target['target_field_hash_matches']))
            target_checks.append(dict(run_id=rid, target_id=tid, target_buffer_cell_count=actual['cells'],
                recomputed_actual_status=actual['status'], actual_first_hit_lower_seconds=actual['lower'],
                actual_first_hit_upper_seconds=actual['upper'], actual_last_saved_seconds=actual['last_saved'],
                requested_horizon_status=formal['status'], requested_first_hit_lower_seconds=formal['lower'],
                requested_first_hit_upper_seconds=formal['upper'], requested_last_saved_seconds=formal['last_saved'],
                original_actual_hit_agrees=hit_matches, original_bracket_agrees=bracket_matches,
                bound_source_field_hash_agrees=True,
                target_point_distance_to_release_raster_support_m=float(support_distance(np.array(tx), np.array(ty), rectangles))))
            joined.append(dict(run_id=rid, base_scenario_id=base, source_scenario_id=onset['scenario_id'],
                original_upstream_model_id=old['model_id'], analytic_onset_model_id=new_model,
                propagation_model_id=run['model_id'], mechanism_id=mechanism, parameter_version=PARAMETER_VERSION,
                release_mapping_version=MAPPING_VERSION, target_id=tid, entity_id=target['entity_id'] or None,
                target_kind=target['target_kind'] or None, target_geometry_version=target['target_geometry_version'],
                source_first_passage_status=onset['status'], original_upstream_onset_status=release['onset_status'],
                conditional_onset_lower_utc=onset['crossing_lower_utc'] or None,
                conditional_onset_upper_utc=onset['crossing_upper_utc'] or None,
                if_released_propagation=flag(run['if_released_propagation']),
                initiation_to_release_delay_seconds=None, time_origin='bulk_release',
                raw_conditional_arrival_status=target['arrival_status'],
                diagnostic_bulk_release_arrival_lower_seconds=actual['lower'],
                diagnostic_bulk_release_arrival_upper_seconds=actual['upper'],
                diagnostic_arrival_within_requested_horizon=formal['hit'],
                requested_horizon_seconds=horizon, last_saved_within_requested_horizon_seconds=formal['last_saved'],
                actual_last_saved_seconds=actual['last_saved'],
                arrival_definition=target['arrival_definition'],
                absolute_arrival_lower_utc=None, absolute_arrival_upper_utc=None, absolute_arrival_time_utc=None,
                qualified_arrival_lower_seconds=None, qualified_arrival_upper_seconds=None,
                arrival_probability=None, probability_weight=None, include_in_arrival_envelope=False,
                numerical_qualification=run['numerical_qualification'], mass_conservation_qualified=False,
                scientifically_qualified_for_prediction=False, event_timing_validated=False,
                arrival_is_initiation_truth=False, physical_phase='conditional_bulk_release_to_target_arrival',
                evaluation_stratum='conditional_scenario', independent_local_validation_events=0,
                adapter_lineage_status='accepted_explicit_versioned_mapping',
                arrival_status='unqualified_diagnostic_only;unknown_initiation_to_release_lag',
                source_fields_sha256=field_rec['sha256']))
            legacy_comparison.append(dict(run_id=rid, target_id=tid, same_v2_input=True,
                previous_adapter_result_on_same_headers='reject_missing_explicit_parent_lineage',
                previous_missing_fields='mechanism_id,parent_geometry_version',
                previous_exact_model_would_match_new_analytic=False,
                previous_implicit_geometry_conflation_allowed=False,
                v2_result='accepted_explicit_versioned_mapping_unqualified_diagnostic',
                fix='mechanism from verified per-run lineage; separate geometry roles; registered analytic model replacement',
                physical_qualification_changed=False, previous_adapter_source_sha256=sha(oldscript)))

    check('all_targets_retained_without_rejection', len(joined) == len(target_rows) == 14)
    check('one_pair_per_run_target', len({(x['run_id'], x['target_id']) for x in joined}) == 14)
    check('no_probability_or_absolute_arrival_created', all(
        all(x[k] is None for k in ['absolute_arrival_lower_utc', 'absolute_arrival_upper_utc',
            'absolute_arrival_time_utc', 'arrival_probability', 'probability_weight',
            'qualified_arrival_lower_seconds', 'qualified_arrival_upper_seconds']) for x in joined))
    check('all_excluded_from_qualified_arrival_envelope', all(not x['include_in_arrival_envelope'] for x in joined))
    check('p0000_no_start_retained', all(x['if_released_propagation'] and
        x['source_first_passage_status'] == 'no_cross_observed_complete' for x in joined
        if x['base_scenario_id'] == 'q2r3-p0000-S-linear'))
    check('p0036_actual_analytic_crossing_used', resolved_by_run[
        'q2map60_q2r3_p0036_S_T_linear__sf0']['analytic_onset_status'] == 'point_crossing_linear_between_samples')
    write_csv(out / 'lineage_audit.csv', lineage_audit)
    write_csv(out / 'physical_parameter_audit.csv', parameter_audit)
    write_csv(out / 'release_mapping_audit.csv', release_audit)
    write_csv(out / 'different_geometry_comparison.csv', geometry_comparison)
    write_csv(out / 'conditional_arrivals.csv', joined)
    write_csv(out / 'saved_field_target_checks.csv', target_checks)
    write_csv(out / 'depth_footprint_diagnostics.csv', footprints)
    write_csv(out / 'previous_adapter_comparison.csv', legacy_comparison)
    write_csv(out / 'rejected_pairings.csv', [], ['run_id', 'target_id', 'reason'])
    schema = dict(version='q3-q4-explicit-mapped-adapter-v2',
        field_resolution={
            'original_upstream_model_id': 'target.upstream_model_id = model_run.upstream_model_id = bundle.lineage_by_run.upstream_model_id = Q2 compact release.model_id',
            'mechanism_id': 'verified bundle.lineage_by_run.mechanism_id; absent target header is not a missing scientific quantity',
            'parameter_version': 'target.upstream_parameter_version = Q2 original release and original/analytic parameter ensemble version',
            'mechanism_geometry_version': 'original/analytic parameter ensemble and analytic first_passages.geometry_version',
            'original_release_geometry_version': 'original compact release.geometry_version; conceptual conditional area only',
            'mapped_release_geometry_version': 'executed case.geometry_version = bundle/run/target.release_mapping_version',
            'target_geometry_version': 'target.target_geometry_version checked against delivered representative point geometry',
            'initiation_to_release_delay_seconds': 'delivered null; same physical quantity as old mechanical_to_release_delay_seconds alias',
        }, model_replacements=MODEL_REPLACEMENTS, matching='exact keys; no approximate strings or cross-product',
        missing_compact_vector_not_reconstructed=True, independent_mapping_table_missing=True,
        adapter_pass_is_physical_qualification=False, rejected_pair_count=0)
    write_json(out / 'adapter_schema.json', schema)

    # Standalone scientific diagnostic figure, using actual stored fields.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, (base, hmax, cumulative, positive, xx, yy) in zip(axes, arrays):
        masked = np.ma.masked_where(hmax < 0.1, hmax)
        image = ax.pcolormesh(xx / 1000, yy / 1000, masked, cmap='viridis', shading='nearest', vmin=0, vmax=60)
        ax.contour(xx / 1000, yy / 1000, positive.astype(float), levels=[0.5], colors=['red'], linewidths=1.2)
        for tid, (tx, ty, _) in target_points.items():
            ax.scatter(tx / 1000, ty / 1000, s=15, marker='x', color='black')
            if tid in ['paper_junction', 'paper_port_symbol']:
                ax.annotate(tid.replace('paper_', ''), (tx / 1000, ty / 1000), xytext=(3, 3), textcoords='offset points', fontsize=7)
        ax.set_aspect('equal')
        ax.set_xlabel('Easting (km; EPSG:32645)')
        ax.set_ylabel('Northing (km; EPSG:32645)')
        ax.set_title(base + '\nUNQUALIFIED; saved outputs <=1800s', fontsize=9)
    fig.colorbar(image, ax=axes, label='Saved-output maximum depth (m; shown >=0.1m)', shrink=0.8)
    fig.suptitle('Conditional diagnostics; red = release raster support; black x = target representatives\nNo absolute arrival time, probability or validated warning distance', fontsize=11)
    fig.savefig(out / 'conditional_footprints.png', dpi=180)
    plt.close(fig)

    summary = dict(status='mapped_adapter_executed_unqualified_diagnostics_only',
        bundle_version=bundle['bundle_version'], bundle_sha256=PIN,
        delivered_files_verified=39, physical_model_runs=2, independent_local_validation_events=0,
        representative_target_count=7, osm_representative_count=5, osm_entity_count=3,
        paper_candidate_point_count=2, run_target_rows=14, accepted_lineage_rows=14, rejected_lineage_rows=0,
        raw_saved_target_hits=sum(x['actual_first_hit_upper_seconds'] is not None for x in target_checks),
        requested_horizon_saved_target_hits=sum(x['requested_first_hit_upper_seconds'] is not None for x in target_checks),
        qualified_arrival_rows=0, qualified_arrival_envelope_rows=0, absolute_arrival_rows=0,
        arrival_probability_rows=0, source_geometry_version=MAPPING_VERSION,
        compact_polygon_independently_audited=False, mapping_table_delivered=False,
        compact_raster_volume_audited=True, parameter_fields_checked_per_run=len(PHYSICAL_FIELDS),
        numerical_qualification='unqualified_compact_source_underresolution_and_budget_discrepancy',
        adapter_checks_passed=True, predictive_qualification=False,
        scientific_adoption='pending_team_review',
        no_physical_solver_rerun=True, no_existing_frozen_result_modified=True)
    write_json(out / 'status.json', summary)
    write_json(out / 'summary.json', summary)
    text = f'''# Mapped propagation adapter v2 results

All **39 delivered file hashes** verified. Exact lineage succeeds for **14 run-target rows = 2 physical runs x 7 representative points**, with no rejected pairing. Five OSM points describe three entities; two paper points remain candidate objects. No independent local validation event is added.

The original compact Q2 release table is embedded in the packet and matches the upstream frozen SHA256. Each run preserves all {len(PHYSICAL_FIELDS)} shared physical parameters through the explicitly documented analytic-erfc thermal-model replacement. The original conceptual area geometry, mechanism slab geometry, Q4 mapped compact raster, and later broad-source release-v2 geometry are distinct. The broad-source table has a different area and volume and is not used for this adapter. A compact vector polygon and independent mapping table were not delivered; those geometry details remain unaudited. The actual supplied compact release raster, volume, grid alignment, support cells, composition and density were audited.

p0000 remains `no_cross_observed_complete`, with no onset timestamp, and all of its propagation records remain **if released**. p0036 uses the actual analytic `point_crossing_linear_between_samples`, bracket **2026-07-08 15:00–16:00 UTC** and interpolation **15:34:17.258933921 UTC**. These are conditional ideal-weather retrospective mechanical first-crossing results, not bulk-release truth or operational verified predictions.

The saved-field check finds **{summary['raw_saved_target_hits']} raw target hit**: p0036 at the paper junction, bracket **1360.5–1380.1 seconds after assumed bulk release**, at h>=0.1m within the registered 100m representative-point buffer. It remains **unqualified**. The other 13 rows have no threshold hit at the stored outputs; this does not establish continuous-time non-arrival or safety. Requested 1800s and actual final 1800.1/1801.7s are retained separately; last outputs within the requested horizon are recorded explicitly.

Both runs retain the compact-source underresolution and unresolved mass-budget qualification failure. Native internal residuals are **+21.372917% / +12.716325%**; raster-source-adjusted residuals are **+21.153363% / +12.613015%**. These are different representations and are not averaged or relabelled as conserved. All qualified travel intervals, absolute arrival times, probabilities and arrival-envelope inclusion remain null/false. Unknown mechanical-initiation-to-bulk-release lag is never set to zero.

`depth_footprint_diagnostics.csv` and `conditional_footprints.png` use actual hashed fields, without a physics rerun. The 0.1/1/5m thresholds are descriptive. Area is affected grid-cell area; distance is maximum affected cell-centre distance to the union of **positive actual release raster cell footprints**, not to a centroid, the broad candidate source, or a cost path. At 60m the 8/16-cell source support exceeds the exact partial-cell compact polygon; exact polygon distance is unavailable. No footprint or distance is a validated hazard zone or warning distance.

`previous_adapter_comparison.csv` evaluates the previous adapter's header/exact-model rule against these same v2 rows. Its old required aliases would reject the absent target mechanism/parent-geometry columns. The new adapter resolves explicit delivered lineage and a registered model replacement while preserving distinct geometry semantics. QA success checks the adapter and provenance; physical qualification stays unchanged.

Reproduce from the Q3 worktree:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 track_b/.venv/bin/python track_b/research/q3/round3/scripts/join_propagation_v2.py
```
'''
    (out / 'RESULTS.md').write_text(text)
    inputs.append(file_record(out / 'PROTOCOL.md', 'precalculation adapter protocol'))
    inputs.append(file_record(Path(__file__), 'executed adapter source'))
    for entry in inputs:
        p = resolve(entry['path'])
        check('input_unchanged_during_adapter:' + entry['path'],
              p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256'])
    # No self-reference: input index excludes outputs; output index excludes itself and validation.
    write_json(out / 'input_index.json', dict(files=inputs, file_list_excludes_self=True,
        external_read_scope='exact39 delivered-role files only; q4/official allowed objects only',
        no_active_other_question_worktree_reads=True))
    write_json(out / 'output_index.json', dict(files=[file_record(p, 'incremental adapter output')
        for p in sorted(out.iterdir()) if p.is_file() and p.name not in ['output_index.json', 'validation.json']],
        file_list_excludes_self=True, validation_excluded_to_avoid_cycle=True))
    visual_path = out / 'figure_review.json'
    visual = read_json(visual_path) if visual_path.exists() else None
    if visual is not None:
        check('external_visual_review_matches_figure', visual.get('passed') is True and
              visual.get('figure_sha256') == sha(out / 'conditional_footprints.png'))
    report = dict(generated_at_utc=datetime.now(timezone.utc).isoformat(), passed=all(x['passed'] for x in checks),
                  adapter_pass_is_predictive_qualification=False, check_count=len(checks), checks=checks,
                  input_index_sha256=sha(out / 'input_index.json'), output_index_sha256=sha(out / 'output_index.json'),
                  figure_visual_qa='passed_external_visual_inspection' if visual is not None else
                    'pending_external_visual_inspection; not claimed by this script')
    write_json(out / 'validation.json', report)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Adapter QA: {len(checks)}/{len(checks)} passed; output {out}")


if __name__ == '__main__':
    main()
