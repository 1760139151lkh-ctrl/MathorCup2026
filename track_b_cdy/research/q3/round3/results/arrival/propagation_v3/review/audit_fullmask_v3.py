#!/usr/bin/env python3
"""Independent fullmask input/consumer audit; no solver or other worktree reads.
Writes only this new review directory. --consumer adds completed C outputs.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer

D = Path(__file__).resolve().parent
R = D.parents[3]
ROOT = R.parents[3]
B = R / 'inputs/q4/bundle_q4-r3-propagation-v3'
E = B / 'files/exports/propagation_v3'
OUT = D.parent
CACHE = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
PIN = '8457a9db624c33c0d0988ad8f4d8c8513ff21ac858ccff830bae577f77f0b683'
FIELDS = ['theta_deg', 'thickness_normal_m', 'rock_volume_fraction', 'bridge_fraction',
          'bridge_cohesion_kpa', 'rock_mu', 'initial_temp_c', 'diffusivity_m2_s',
          'interface_depth_m', 'station_source_offset_c', 'storativity', 'drainage_hours',
          'connected_depth_m', 'rain_multiplier', 'melt_mm_deg_day', 'damage_rate_h_inv',
          'damage_exponent', 'initial_damage', 'drainage_damage_coupling', 'density_kg_m3']
REPLACEMENTS = {'q2r3_S_v1': ('S', 'q2r3_S_analytic_v1'),
                'q2r3_ST_v1': ('S_T', 'q2r3_S_T_analytic_v1')}
inputs = {}


def resolve(s):
    p = Path(s)
    return (p if p.is_absolute() else ROOT / p).resolve()


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def register(p, role):
    p = Path(p).resolve()
    assert p.is_relative_to(ROOT) or p.is_relative_to(CACHE), str(p)
    if p.is_relative_to(ROOT):
        assert p.is_relative_to(R), 'No other active worktree or question tree reads'
    rec = dict(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
               bytes=p.stat().st_size, sha256=sha(p), role=role)
    if str(p) in inputs:
        prior = inputs[str(p)]
        assert prior['bytes'] == rec['bytes'] and prior['sha256'] == rec['sha256'], 'Input changed while reviewed'
        rec['roles'] = sorted(set(prior.get('roles', [prior.get('role')]) + [role]))
        del rec['role']
    inputs[str(p)] = rec
    return p


def read_json(p, role):
    return json.loads(register(p, role).read_text())


def rows(p, role):
    with register(p, role).open(newline='') as s:
        return list(csv.DictReader(s))


def one(data, **keys):
    found = [x for x in data if all(x.get(k) == v for k, v in keys.items())]
    assert len(found) == 1, (keys, len(found))
    return found[0]


def close(x, y, rtol=1e-11, atol=1e-8):
    return math.isclose(float(x), float(y), rel_tol=rtol, abs_tol=atol)


def flag(x):
    return x is True or str(x).lower() == 'true'


def first_hit(time, depth, mask):
    if not mask.any():
        return None, None
    idx = np.flatnonzero(np.any(depth[:, mask] >= .1, axis=1))
    if not len(idx):
        return None, None
    i = int(idx[0])
    return (float(time[i - 1]) if i else None), float(time[i])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--consumer', action='store_true')
    args = parser.parse_args()
    checks, runs, targets = {}, [], []
    bundle = read_json(B / 'bundle.json', 'pinned Q4 fullmask-v3 input manifest')
    checks['exact_approved_PIN'] = sha(B / 'bundle.json') == PIN
    checks['66_exact_roles_no_probability_weights'] = len(bundle['files']) == 66 and bundle['probability_weights'] is None
    approved_external = set()
    for f in bundle['files']:
        p = resolve(f['path'])
        assert p.is_relative_to(B) or f.get('storage') == 'immutable_external_cache' and p.is_relative_to(CACHE)
        register(p, f['role'])
        checks['delivered_file:' + str(p)] = p.stat().st_size == f['bytes'] and sha(p) == f['sha256']
        if p.is_relative_to(CACHE):
            approved_external.add(p)
    assert all(checks.values()), 'Do not open arrays if pinned input hashes/scope fail'
    qroot = R / 'inputs/q2/release_bundle_v2_q2-r3-release-v2-spatial-copdem-v1'
    qbundle = read_json(qroot / 'bundle.json', 'Q3 imported frozen Q2 fullmask release-v2 manifest')
    for f in qbundle['files']:
        p = resolve(f['path'])
        assert p.is_relative_to(qroot)
        register(p, 'frozen Q2 release-v2 role: ' + f['role'])
        checks['frozen_Q2_file:' + f['role']] = sha(p) == f['sha256'] and p.stat().st_size == f['bytes']
    imported_release = resolve(one(qbundle['files'], role='release_states_geometry_v2')['path'])
    packaged_release = E / 'provenance/upstream_q2_fullmask/release_states_geometry_v2.csv'
    release_rows = rows(packaged_release, 'Q4 embedded frozen fullmask release-v2 table')
    checks['embedded_Q2_release_table_exactly_matches_Q3_import'] = sha(packaged_release) == sha(imported_release)
    oldroot = R / 'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1'
    newroot = R / 'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1'
    oldpath = oldroot / 'files/results/parameter_ensemble.csv'
    newpath = newroot / 'files/results/analytic_thermal/parameter_ensemble.csv'
    contractpath = newroot / 'files/results/analytic_thermal/mechanism_contract.json'
    for root, pp in [(oldroot, [oldpath]), (newroot, [newpath, contractpath])]:
        meta = read_json(root / 'bundle.json', 'Q3 imported parameter/contract manifest')
        for p in pp:
            item = [f for f in meta['files'] if resolve(f['path']) == p.resolve()]
            assert len(item) == 1
            register(p, 'frozen original/analytic parameter or contract')
            checks['parameter_contract_hash:' + str(p)] = sha(p) == item[0]['sha256'] and p.stat().st_size == item[0]['bytes']
    original = rows(oldpath, 'original 2048-design parameter table; only selected bases used')
    analytic = rows(newpath, 'analytic 2048-design parameter table; only selected bases used')
    contract = read_json(contractpath, 'explicit analytic release-join contract')
    onsets = rows(R / 'results/engine_a/analytic_erfc/first_passages.csv', 'frozen analytic conditional first passages')
    run_rows = rows(E / 'model_runs.csv', '3 native fullmask run metadata')
    raw_targets = rows(E / 'target_arrivals.csv', '21 native saved-field target records')
    metrics = rows(E / 'comparison_metrics.csv', 'native and ASCII budget diagnostics kept separate')
    points = {x['target_id']: (float(x['x_m']), float(x['y_m'])) for x in rows(E / 'geometry/spatial_targets_v2.csv', '5 OSM representatives')}
    geo = read_json(E / 'geometry/computational_geometries.geojson', 'paper candidate points and computational geometries')
    project = Transformer.from_crs('EPSG:4326', 'EPSG:32645', always_xy=True)
    for f in geo['features']:
        if f['geometry']['type'] == 'Point':
            points[f['properties']['space_id']] = project.transform(*f['geometry']['coordinates'])
    checks['3_runs_21_target_rows_7_representatives'] = len(run_rows) == 3 and len(raw_targets) == 21 and len(set(x['target_id'] for x in raw_targets)) == 7
    checks['2_parent_designs_not_2048_weighted_ensemble'] = len(set(x['base_scenario_id'] for x in run_rows)) == 2 and bundle['independent_local_validation_events'] == 0
    checks['accepted_run_list_empty'] = bundle['accepted_arrival_envelope_run_ids'] == []
    for run in run_rows:
        rid, base = run['run_id'], run['base_scenario_id']
        prefix = rid + ':'
        c = read_json(E / f'provenance/{rid}/case.json', 'actual native case: ' + rid)
        lineage = one(bundle['lineage_by_run'], run_id=rid)
        release = one(release_rows, scenario_id=c['scenario_id'])
        old = one(original, scenario_id=base)
        mechanism, model = REPLACEMENTS[old['model_id']]
        new = one(analytic, base_scenario_id=base, model_id=model)
        onset = one(onsets, base_scenario_id=base, model_id=model)
        checks[prefix + 'exact_base_model_mapping'] = c['base_scenario_id'] == release['base_scenario_id'] == lineage['base_scenario_id'] == base and release['model_id'] == c['upstream_model_id'] == old['model_id'] and contract['model_ids'][mechanism] == model
        checks[prefix + '20_physical_parameters_preserved'] = all(close(old[k], new[k], rtol=1e-13, atol=1e-13) for k in FIELDS)
        checks[prefix + 'parameter_mechanism_geometry_identity_preserved'] = all(old[k] == new[k] for k in ['parameter_set_id', 'mechanism_id', 'law_policy', 'parameter_version', 'geometry_version'])
        checks[prefix + 'fullmask_geometry_version_not_compact'] = c['geometry_version'] == release['geometry_version'] == lineage['geometry_version'] == 'q4-r3-spatial-copdem-v1' and c['release_mapping_version'] == release['release_mapping_version'] == 'q2-r3-release-v2-spatial-copdem-v1'
        res = int(c['resolution_m'])
        role = 'source_mask_model_arrays_' + str(res) + 'm'
        maskpath = resolve(one(qbundle['files'], role=role)['path'])
        with np.load(maskpath, allow_pickle=False) as z:
            mask = z['source_mask'].astype(bool)
            mask_transform = z['transform'].copy()
        relpath = Path(c['release']).resolve()
        assert relpath in approved_external
        with rasterio.open(relpath) as ds:
            rel, tr, crs = ds.read(1).astype(float), ds.transform, str(ds.crs)
        positive = rel > 0
        area = int(positive.sum()) * res * res
        vol = float(rel[positive].sum() * res * res)
        check_cells = 257 if res == 60 else 67
        checks[prefix + 'actual_release_matches_frozen_Q2_mask'] = np.array_equal(positive, mask) and np.array_equal(np.array(tuple(tr)), mask_transform) and crs == 'EPSG:32645'
        checks[prefix + 'actual_support_cell_count_and_grid_area'] = int(positive.sum()) == c['source_mask_cells'] == check_cells and area == float(release['plan_area_m2']) == c['source_grid_area_m2']
        checks[prefix + 'actual_release_TIFF_Q2_and_case_volume_match'] = close(vol, release['integrated_volume_m3']) and close(vol, c['release_grid_volume_m3']) and sha(relpath) == c['release_sha256']
        reference = one(release_rows, base_scenario_id=base, grid_resolution_m='60')
        mechanism_vertical = float(old['thickness_normal_m']) / math.cos(math.radians(float(old['theta_deg'])))
        expected_vol = float(reference['plan_area_m2']) * mechanism_vertical
        checks[prefix + 'reference60_volume_and_grid_normalization'] = close(vol, expected_vol) and close(c['release_thickness_m'], expected_vol / area) and close(c['grid_thickness_normalization_factor'], float(reference['plan_area_m2']) / area)
        checks[prefix + 'mechanism_normal_thickness_not_refit'] = close(release['mechanism_thickness_normal_m'], old['thickness_normal_m']) and close(release['mechanism_plane_theta_deg'], old['theta_deg'])
        fractions = json.loads(release['phase_fractions'])
        checks[prefix + 'passive_material_and_bulk_density_preserved'] = fractions == c['passive_material_volume_fractions'] and c['phase_volume_fractions'] == [1] and close(c['bulk_density_kg_m3'], 917 * fractions['ice'] + 2700 * fractions['rock']) and c['initial_velocity_east_north_m_s'] == [0, 0]
        checks[prefix + 'legacy_expected_reference_is_not_actual_volume'] = c['expected_reference_grid_volume_m3'] == 13878000 and not close(vol, c['expected_reference_grid_volume_m3'], rtol=.01)
        fields = one(bundle['files'], role='actual_official_process_fields', run_id=rid)
        fieldpath = resolve(fields['path'])
        assert fieldpath in approved_external
        with np.load(fieldpath, allow_pickle=False) as z:
            time, depth, fieldtr = z['time_s'].copy(), z['depth_frames'].astype(float), z['transform'].copy()
        t0vol = float(depth[0].sum() * res * res)
        m = one(metrics, run_id=rid)
        checks[prefix + 'native_t0_time_support_and_volume'] = time[0] == 0 and np.array_equal(depth[0] > 0, positive) and close(t0vol, m['initial_volume_m3']) and abs(t0vol / vol - 1) < 1e-4
        checks[prefix + 'native_grid_times_and_depth_valid'] = np.array_equal(fieldtr, np.array(tuple(tr))) and depth.shape[1:] == rel.shape and np.all(np.diff(time) > 0) and np.isfinite(depth).all() and depth.min() >= 0
        internal = register(E / f'provenance/{rid}/native_internal_summary.txt', 'native internal t0 summary: ' + rid)
        native0 = next(x for x in csv.DictReader(internal.open(), delimiter='\t') if x['nout'] == '0')
        internal0vol = float(native0['volume'])
        checks[prefix + 'native_internal_t0_volume_close_to_actual_not_legacy'] = float(native0['tsum']) == 0 and abs(internal0vol / vol - 1) < 1e-4
        checks[prefix + 'unknown_lag_and_unqualified_flags_preserved'] = c['initiation_to_release_delay_seconds'] is None and not any(flag(run[k]) for k in ['include_in_arrival_envelope', 'mass_conservation_qualified', 'scientifically_qualified_for_prediction', 'accepted_arrival_envelope_run_membership'])
        checks[prefix + 'never_cross_only_if_released'] = onset['status'] != 'no_cross_observed_complete' or c['if_released_propagation'] is True and not onset['crossing_lower_utc'] and not onset['crossing_upper_utc']
        yy, xx = np.indices(rel.shape)
        xx, yy = tr.c + (xx + .5) * tr.a, tr.f + (yy + .5) * tr.e
        for target in [x for x in raw_targets if x['run_id'] == rid]:
            tid = target['target_id']
            tx, ty = points[tid]
            target_mask = np.hypot(xx - tx, yy - ty) <= 100
            lo, hi = first_hit(time, depth, target_mask)
            reported_lo = float(target['arrival_bracket_lower_seconds']) if target['arrival_bracket_lower_seconds'] else None
            reported_hi = float(target['arrival_bracket_upper_seconds']) if target['arrival_bracket_upper_seconds'] else None
            checks[prefix + 'target:' + tid] = lo == reported_lo and hi == reported_hi and not any(flag(target[k]) for k in ['include_in_arrival_envelope', 'mass_conservation_qualified', 'scientifically_qualified_for_prediction', 'accepted_arrival_envelope_run_membership']) and not target['initiation_to_release_delay_seconds']
            dx = np.maximum(np.abs(tx - xx[positive]) - res / 2, 0)
            dy = np.maximum(np.abs(ty - yy[positive]) - res / 2, 0)
            distance = float(np.hypot(dx, dy).min())
            targets.append(dict(run_id=rid, target_id=tid, native_lower_seconds=lo, native_upper_seconds=hi,
                                buffer_cell_centres=int(target_mask.sum()), independently_recomputed_release_support_distance_m=distance))
        runs.append(dict(run_id=rid, base_scenario_id=base, grid_m=res, source_cells=int(positive.sum()),
                         source_grid_area_m2=area, source_exact_polygon_area_m2=c['source_exact_area_m2'],
                         actual_release_volume_m3=vol, upstream_Q2_volume_m3=float(release['integrated_volume_m3']),
                         native_saved_t0_volume_m3=t0vol, native_saved_t0_relative_difference=t0vol / vol - 1,
                         native_internal_t0_volume_m3=internal0vol,
                         unused_legacy_expected_reference_grid_volume_m3=c['expected_reference_grid_volume_m3'],
                         actual_vertical_thickness_m=c['release_thickness_m'], original_mechanism_normal_m=float(old['thickness_normal_m']),
                         ascii_budget_relative_residual=float(m['ascii_raster_source_adjusted_budget_relative_residual']),
                         native_internal_budget_relative_residual=float(m['native_internal_summary_mass_budget_relative_residual']),
                         analytic_model_id=model, analytic_status=onset['status']))
    consumer = None
    if args.consumer:
        consumer = audit_consumer(checks, runs, targets, approved_external)
    register(Path(__file__), 'executed independent fullmask-v3 review source')
    report = dict(reviewed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  scope='independent local read-only review; only approved delivered Q4 cache roles and Q3 frozen imports; no physical solver rerun',
                  stage='final_consumer_and_input_review' if args.consumer else 'preliminary_input_review_consumer_pending',
                  review_source_sha256=sha(Path(__file__)), inputs=list(inputs.values()),
                  checks={k: bool(v) for k, v in checks.items()}, passed=all(checks.values()), runs=runs, native_target_recheck=targets,
                  consumer_review=consumer, physical_model_runs=3, distinct_parent_designs=2, independent_local_validation_events=0,
                  limitations=['Three conditional runs are not a 2048-design weighted ensemble.',
                               'Native t0 volume agreement is initialization QA, not conservation or predictive qualification.',
                               '60/120m normalization preserves released volume, not measured geometry or independent physical-thickness evidence.',
                               'Bulk-release lag is unknown; no absolute arrival, qualified delay, probability or local mechanical truth can be inferred.'])
    name = 'final_review.json' if args.consumer else 'preliminary_input_review.json'
    (D / name).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'stage': report['stage'], 'output': str((D / name).relative_to(ROOT))}))
    assert report['passed'], [k for k, v in checks.items() if not v]


def audit_consumer(checks, run_audit, target_audit, approved_external):
    src = register(R / 'scripts/join_propagation_v3.py', 'reviewed consumer source; not executed by this audit')
    summary = read_json(OUT / 'summary.json', 'consumer final summary')
    arrivals = rows(OUT / 'conditional_arrivals.csv', 'consumer 21 scenario-target outputs')
    releases = rows(OUT / 'release_mapping_audit.csv', 'consumer 3 fullmask volume/mapping audits')
    saved = rows(OUT / 'saved_field_target_checks.csv', 'consumer 21 saved-field target rechecks')
    parameters = rows(OUT / 'physical_parameter_audit.csv', 'consumer 60 parameter field checks')
    lineage = rows(OUT / 'lineage_audit.csv', 'consumer 3 exact analytic replacements')
    validation = read_json(OUT / 'validation.json', 'consumer validation, not physical qualification')
    schema = read_json(OUT / 'adapter_schema.json', 'consumer explicit geometry/model semantics')
    checks['consumer_21_pairs_3_runs_2_designs'] = len(arrivals) == 21 and len(releases) == len(lineage) == 3 and len(set(x['base_scenario_id'] for x in arrivals)) == 2
    checks['consumer_60_physical_parameter_checks'] = len(parameters) == 60 and all(flag(x['unchanged']) for x in parameters)
    checks['consumer_summary_zero_qualification_and_weights'] = summary['qualified_arrival_rows'] == summary['absolute_arrival_rows'] == summary['probability_rows'] == 0 and summary['probability_weights'] is None and summary['selected_runs_are_2048_probability_ensemble'] is False and summary['independent_local_validation_events'] == 0
    checks['consumer_accepted_list_empty_and_flags_false'] = summary['accepted_arrival_envelope_run_ids'] == [] and not any(summary[k] for k in ['mass_conservation_qualified', 'regional_accuracy_qualified', 'scientifically_qualified_for_prediction'])
    checks['consumer_legacy_reference_volume_not_used'] = summary['legacy_reference_volume_used_as_actual'] is False and schema['legacy_reference_field_is_actual_volume'] is False
    null_fields = ['absolute_arrival_lower_utc', 'absolute_arrival_upper_utc', 'absolute_arrival_time_utc',
                   'qualified_arrival_lower_seconds', 'qualified_arrival_upper_seconds', 'arrival_probability',
                   'probability_weight', 'initiation_to_release_delay_seconds']
    gates = ['include_in_arrival_envelope', 'accepted_arrival_envelope_run_membership', 'mass_conservation_qualified',
             'regional_accuracy_qualified', 'scientifically_qualified_for_prediction', 'arrival_is_initiation_truth']
    checks['consumer_all_21_null_lag_absolute_qualified_probability'] = all(all(not x[k] for k in null_fields) for x in arrivals)
    checks['consumer_all_21_qualification_gates_false'] = all(all(not flag(x[k]) for k in gates) for x in arrivals)
    for a in run_audit:
        rid = a['run_id']
        c = one(releases, run_id=rid)
        checks['consumer_release_volume_and_t0:' + rid] = close(c['actual_release_TIFF_volume_m3'], a['actual_release_volume_m3']) and close(c['Q2_frozen_release_volume_m3'], a['upstream_Q2_volume_m3']) and close(c['saved_initial_depth_integral_m3'], a['native_saved_t0_volume_m3']) and close(c['native_internal_initial_volume_m3'], a['native_internal_t0_volume_m3'])
        checks['consumer_support_and_grid:' + rid] = int(c['source_support_cells']) == a['source_cells'] and close(c['actual_grid_area_m2'], a['source_grid_area_m2']) and close(c['release_vertical_thickness_m'], a['actual_vertical_thickness_m'])
        checks['consumer_budget_representations_remain_separate:' + rid] = flag(c['budget_representations_separate']) and close(c['raster_budget_relative_residual'], a['ascii_budget_relative_residual']) and close(c['native_internal_budget_relative_residual'], a['native_internal_budget_relative_residual'])
        l = one(lineage, run_id=rid)
        checks['consumer_explicit_analytic_lineage:' + rid] = l['analytic_model_id'] == a['analytic_model_id'] and l['analytic_onset_status'] == a['analytic_status'] and flag(l['physical_parameters_unchanged'])
    for t in target_audit:
        c = one(arrivals, run_id=t['run_id'], target_id=t['target_id'])
        s = one(saved, run_id=t['run_id'], target_id=t['target_id'])
        parse = lambda x: float(x) if x else None
        checks['consumer_independent_target:' + t['run_id'] + ':' + t['target_id']] = parse(c['diagnostic_bulk_release_arrival_lower_seconds']) == t['native_lower_seconds'] and parse(c['diagnostic_bulk_release_arrival_upper_seconds']) == t['native_upper_seconds'] and parse(s['actual_first_hit_lower_seconds']) == t['native_lower_seconds'] and parse(s['actual_first_hit_upper_seconds']) == t['native_upper_seconds'] and int(s['target_buffer_cell_count']) == t['buffer_cell_centres'] and close(s['target_point_to_release_raster_support_distance_m'], t['independently_recomputed_release_support_distance_m'])
    never = [x for x in arrivals if x['base_scenario_id'] == 'q2r3-p0000-S-linear']
    checks['consumer_p0000_all7_never_if_released_no_onset'] = len(never) == 7 and all(flag(x['if_released_propagation']) and x['source_first_passage_status'] == 'no_cross_observed_complete' and not x['conditional_onset_lower_utc'] and not x['conditional_onset_upper_utc'] for x in never)
    checks['consumer_exact3_junction_hits18_saved_nonhits'] = sum(x['native_upper_seconds'] is not None for x in target_audit) == 3 and all(x['target_id'] == 'paper_junction' for x in target_audit if x['native_upper_seconds'] is not None)
    checks['consumer_validation_all_pass_no_predictive_upgrade'] = validation['passed'] is True and validation['check_count'] == len(validation['checks']) and all(x['passed'] for x in validation['checks']) and validation['adapter_pass_is_predictive_qualification'] is False
    index_counts = {}
    for name in ['input_index.json', 'output_index.json']:
        path = OUT / name
        index = read_json(path, 'consumer exact index: ' + name)
        canonical = []
        for f in index['files']:
            p = resolve(f['path'])
            assert p.is_relative_to(R) or p in approved_external
            canonical.append(p)
            register(p, 'consumer indexed input/output: ' + name)
            checks['consumer_index_hash:' + name + ':' + str(p)] = p.stat().st_size == f['bytes'] and sha(p) == f['sha256']
        checks['consumer_no_self_reference_or_duplicate:' + name] = path.resolve() not in canonical and len(canonical) == len(set(canonical))
        if name == 'output_index.json':
            checks['consumer_index_excludes_review_and_validation'] = not any(p.is_relative_to(D) or p == OUT / 'validation.json' for p in canonical) and index['independent_review_directory_excluded'] is True
        checks['consumer_validation_binds_index:' + name] = validation[name.split('_')[0] + '_index_sha256'] == sha(path)
        index_counts[name] = len(canonical)
    visual = read_json(OUT / 'figure_review.json', 'consumer actual visual inspection record')
    checks['consumer_figure_QA_bound'] = visual['passed'] is True and all(x['actually_opened'] is True and sha(resolve(x['path'])) == x['sha256'] for x in visual['figures'])
    return dict(source_sha256=sha(src), consumer_check_count=validation['check_count'], index_counts=index_counts,
                source_review=dict(exact_registered_model_replacements=True, fullmask_v2_not_compact=True,
                                   actual_TIFF_cell_support_distance=True, unknown_lag_and_qualification_gates=True,
                                   output_scope_is_only_new_propagation_v3=True, no_physics_solver_invocation=True),
                note='Manual source reading plus independent frozen-input/t0/target and output-index checks; consumer pass is not scientific acceptance.')


if __name__ == '__main__':
    main()
