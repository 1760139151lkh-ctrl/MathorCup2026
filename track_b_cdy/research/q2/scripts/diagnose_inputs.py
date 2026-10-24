#!/usr/bin/env python3
"""Q2 first-wave support/identifiability diagnostics; never estimates a trigger.

AI assistance: OpenAI Codex, 2026-10-24. Human review before scientific adoption.
All writes are restricted to this question. No network or common-data rewrites.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
Q = ROOT / 'track_b/research/q2'
CONFIG = Q / 'config/diagnostic.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, value):
    path = Q / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(name, rows):
    path = Q / name
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def main():
    config = json.loads(CONFIG.read_text())
    readiness = json.loads((Q / 'workspace_verification.json').read_text())
    if not readiness['passed']:
        raise RuntimeError('Wait for the advisor-confirmed successful workspace verification')
    if Path(sys.prefix).resolve() != (ROOT / 'track_b/.venv').resolve():
        raise RuntimeError('Use this worktree\'s isolated Python')

    import numpy as np
    import pandas as pd
    import pyproj
    import rasterio
    from rasterio.warp import Resampling, reproject
    import shapely
    from shapely.geometry import shape
    import xarray as xr

    baseline_path = ROOT / 'track_b/audit/stage4/baseline_manifest.json'
    baseline = json.loads(baseline_path.read_text())
    frozen = {e['path']: e for e in baseline['files']}
    inputs = {}

    def use(name):
        path = ROOT / name
        actual = {'path': name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
        if name in frozen:
            assert actual['bytes'] == frozen[name]['bytes'] and actual['sha256'] == frozen[name]['sha256'], name
        inputs[name] = actual
        return path

    def load(name):
        return json.loads(use(name).read_text())

    version = {'baseline_commit': config['baseline_commit'], 'baseline_manifest_sha256': digest(baseline_path),
               'diagnostic_config_sha256': digest(CONFIG)}
    meta = {'event_id': config['event_id'], 'physical_phase': config['physical_phase'],
            'time_utc': None, 'time_uncertainty': None,
            'available_time': None, 'forecast_reference_time': None, 'issue_time': None, 'valid_time': None,
            'data_role': 'exploration', 'input_version': version, 'evidence_status': 'local_fact',
            'space_object': {'id': 'NC_parameter_domain', 'crs': 'EPSG:32645', 'source_geometry_verified': False},
            'variable_semantics': 'see per-row metadata; finite does not imply physical or event validity'}
    spatial_manifest = load('track_b/data/processed/spatial/source_manifest.json')
    nc_names = [name for name in spatial_manifest if name.endswith('.nc')]
    assert len(nc_names) == 1
    nc_name = nc_names[0]
    nc_path = use(nc_name)

    stats = []
    with xr.open_dataset(nc_path, engine='h5netcdf', decode_cf=True, decode_coords='all') as ds:
        assert 'time' not in ds.dims
        mask = np.isfinite(ds.glacier_mask.values) & (ds.glacier_mask.values > 0)
        assert int(mask.sum()) == 7152
        xx, yy = np.meshgrid(ds.x.values, ds.y.values)
        crs = ds.spatial_ref.attrs.get('crs_wkt', ds.spatial_ref.attrs['spatial_ref'])
        transform = pyproj.Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
        lon, lat = transform.transform(xx[mask], yy[mask])
        points = shapely.points(lon, lat)
        for name in config['nc_variables']:
            a = ds[name].values[mask].astype(float)
            finite = np.isfinite(a)
            valid = a[finite]
            stats.append({'variable': name, 'units': ds[name].attrs.get('units'),
                          'domain': 'NC positive glacier_mask only; not failure polygon',
                          'support_cells': int(mask.sum()), 'finite_cells': int(finite.sum()),
                          'finite_fraction': float(finite.mean()), 'negative_cells': int((valid < 0).sum()),
                          'zero_cells': int((valid == 0).sum()),
                          'min': float(valid.min()), 'p05': float(np.quantile(valid, .05)),
                          'median': float(np.median(valid)), 'p95': float(np.quantile(valid, .95)),
                          'max': float(valid.max()), 'mean': float(valid.mean()),
                          'time_support': 'climatological 2014-2024' if name.startswith('v') else 'not a verified 2026 event-time measurement',
                          'metadata_description': ds[name].attrs.get('description', ds[name].attrs.get('long_name')),
                          'independent_samples': None, 'evidence_status': 'local_fact'})
        v_residual = np.abs(ds.v.values[mask].astype('float64') - np.hypot(ds.vx.values[mask].astype('float64'), ds.vy.values[mask].astype('float64')))
        velocity_consistency = {'max_abs_residual_m_per_year': float(np.nanmax(v_residual)),
                                'median_abs_residual_m_per_year': float(np.nanmedian(v_residual)),
                                'p95_abs_residual_m_per_year': float(np.nanquantile(v_residual, .95)),
                                'cells_abs_residual_above_1e_minus_4_m_per_year': int((v_residual > 1e-4).sum()),
                                'diagnostic_comparison_tolerance_m_per_year': 1e-4,
                                'tolerance_role': 'arithmetic discrepancy screen, not physical or trigger threshold',
                                'calculation_dtype': 'float64 using stored float32 values',
                                'stored_identity_confirmed_within_tolerance': bool(np.nanmax(v_residual) <= 1e-4),
                                'status': 'discrepancy_requires_product_processing_review',
                                'candidate_explanation_not_verified': 'Nonlinear magnitude calculation and interpolation may not commute; provenance must determine processing order.',
                                'meaning': 'no data correction; no event-time acceleration information'}
        nc_metadata = {'path': nc_name, 'dimensions': dict(ds.sizes), 'positive_mask_cells': int(mask.sum()),
                       'cell_area_m2': float(abs(np.diff(ds.x.values)[0] * np.diff(ds.y.values)[0])),
                       'parameter_domain_area_km2': float(mask.sum() * abs(np.diff(ds.x.values)[0] * np.diff(ds.y.values)[0]) / 1e6),
                       'global_attributes': dict(ds.attrs), 'time_dimension_present': False}
    write_csv('results/nc_parameter_support.csv', stats)

    # Re-read already aligned immutable rasters; do not choose or merge DEMs.
    with rasterio.open(use('track_b/data/processed/spatial/nc_glacier_mask.tif')) as ref:
        grid = {'shape': ref.shape, 'transform': ref.transform, 'crs': ref.crs}
        raster_mask = ref.read(1, masked=True).filled(0) > 0
        assert raster_mask.shape == mask.shape
    with rasterio.open(use('track_b/data/processed/spatial/nc_dem_native_grid.tif')) as src:
        native = src.read(1, masked=True)
    with rasterio.open(use('track_b/data/processed/spatial/dem_on_nc_grid.tif')) as src:
        other = src.read(1, masked=True)
    delta = (other - native)[raster_mask].compressed()
    dem_comparison = {'definition': 'independent DEM minus NC DEM, positive NC mask; not terrain change',
                      'cells': int(delta.size), 'min_m': float(delta.min()), 'max_m': float(delta.max()),
                      'mean_m': float(delta.mean()), 'median_m': float(np.median(delta)),
                      'vertical_reference_and_dates_reconciled': False}
    cover_path = use('track_b/data/external/event_remote/worldcover_2021_v200_test_aoi.tif')
    aligned = np.zeros(grid['shape'], dtype='uint8')
    with rasterio.open(cover_path) as src:
        reproject(source=src.read(1), destination=aligned, src_transform=src.transform, src_crs=src.crs,
                  src_nodata=0, dst_transform=grid['transform'], dst_crs=grid['crs'], dst_nodata=0,
                  resampling=Resampling.nearest)
    codes, counts = np.unique(aligned[raster_mask], return_counts=True)
    cover = {'source_year': 2021, 'resampling': 'nearest; background only',
             'positive_mask_cells': int(raster_mask.sum()), 'valid_background_cells': int((aligned[raster_mask] > 0).sum()),
             'class_counts': {str(int(k)): int(v) for k, v in zip(codes, counts)},
             'event_time_state_or_failure_geometry_verified': False}

    inventory = load('track_b/data/external/event_remote/scene_inventory.json')
    access = load('track_b/data/external/event_remote/asset_access_tests.json')
    access_index = {(r['provider'], r['item_id']): r for r in access}
    clocks = {k: datetime.fromisoformat(v) for k, v in config['reference_clocks'].items()}
    rows = []
    s1_records = []
    for scene in inventory['records']:
        when = datetime.fromisoformat(scene['datetime'].replace('Z', '+00:00'))
        fractions = {name: ('before' if when < clock else 'at_or_after') for name, clock in clocks.items()}
        geom = shape(scene['geometry'])
        assert geom.is_valid
        count = int(shapely.covers(geom, points).sum())
        tested = access_index.get((scene['provider'], scene['item_id']))
        phase = ('pre_event_remote_candidate' if all(v == 'before' for v in fractions.values())
                 else 'post_event_remote_candidate' if all(v == 'at_or_after' for v in fractions.values())
                 else 'ambiguous_across_candidate_clocks')
        row = {**meta, 'scene_id': scene['item_id'], 'provider': scene['provider'], 'time_utc': scene['datetime'],
               'physical_phase': phase,
               'scene_geometry_covers_nc_mask_centres': count, 'nc_mask_centre_count': len(points),
               'parameter_domain_coverage_fraction': count / len(points),
               'true_failure_polygon_coverage': None, 'reference_clock_classification': fractions,
               'scene_or_tile_cloud_percent': scene.get('cloud_cover_scene_or_tile_percent'),
               'aoi_clear_fraction': None, 'platform': scene.get('platform'),
               'relative_orbit': scene.get('relative_orbit'), 'orbit_state': scene.get('orbit_state'),
               'polarizations': scene.get('sar_polarizations'),
               'published_catalogue_metadata': scene.get('published'), 'created_catalogue_metadata': scene.get('created'),
               'available_time': scene.get('available_time_verified'),
               'access_test_this_scene': 'saved test: no usable image obtained' if tested else 'not tested',
               'saved_http_status': tested.get('http_status') if tested else None,
               'usable_2026_pixels_obtained': False, 'pixel_visibility_verified': False,
               'limitation': 'catalogue geometry support only; no true-source or image-quality acceptance', 'source_url': scene['self_url']}
        rows.append(row)
        if scene['provider'] == 'CDSE_Sentinel1_GRD':
            s1_records.append((scene, when))
    write_csv('results/remote_feasibility.csv', rows)

    # Identify metadata-compatible alternatives to an unsafe nearest-date pair.
    reference = clocks['problem_statement_unspecified_phase']
    pre = [(s, t) for s, t in s1_records if t < reference]
    post = [(s, t) for s, t in s1_records if t >= reference]
    nearest_pre = max(pre, key=lambda row: row[1])
    nearest_post = min(post, key=lambda row: row[1])
    def pair_key(s):
        return (s['platform'], s['orbit_state'], s['relative_orbit'], tuple(s['sar_polarizations'] or []))
    pairs = []
    for key in sorted({pair_key(s) for s, _ in s1_records}):
        before = [(s, t) for s, t in pre if pair_key(s) == key]
        after = [(s, t) for s, t in post if pair_key(s) == key]
        if before and after:
            a, ta = max(before, key=lambda row: row[1]); b, tb = min(after, key=lambda row: row[1])
            pairs.append({'platform': key[0], 'orbit_state': key[1], 'relative_orbit': key[2], 'polarizations': list(key[3]),
                          'pre_scene': a['item_id'], 'pre_time_utc': ta.isoformat(), 'post_scene': b['item_id'],
                          'post_time_utc': tb.isoformat(), 'gap_days': (tb - ta).total_seconds() / 86400,
                          'metadata_compatible': True, 'co_registration_verified': False, 'pixels_obtained': False,
                          'product': 'GRD; no interferometric phase', 'data_role': 'exploration'})
    pair_summary = {'nearest_pre': nearest_pre[0]['item_id'], 'nearest_post': nearest_post[0]['item_id'],
                    'nearest_pair_metadata_compatible': pair_key(nearest_pre[0]) == pair_key(nearest_post[0]),
                    'compatible_candidate_count': len(pairs), 'pairs': pairs,
                    'scope': 'metadata screening, not accepted change-detection pairs or image interpretation'}
    write_json('results/s1_pair_screen.json', pair_summary)

    dictionary = load('track_b/data/processed/temporal/data_dictionary.json')
    definitions = {r['variable_id']: r for r in dictionary['hourly']}
    variables = config['coverage_variables']
    numeric = pd.read_parquet(use('track_b/data/processed/temporal/hourly_raw_numeric.parquet'), columns=variables)
    strict = pd.read_parquet(use('track_b/data/processed/temporal/hourly_strict_qc0.parquet'), columns=variables)
    time_axis = pd.read_parquet(use('track_b/data/processed/temporal/hourly_time_axis.parquet'))
    coverage = []
    cutoff = clocks[config['coverage_clock']]
    times = time_axis.time_utc
    for hours in config['coverage_windows_hours']:
        window_start = cutoff - timedelta(hours=hours)
        selected = (times >= window_start) & (times < cutoff)
        assert selected.sum() == hours
        for name in variables:
            a = numeric.loc[selected.to_numpy(), name].to_numpy()
            present = np.isfinite(a) & (a != 9999.9)
            accepted = np.isfinite(strict.loc[selected.to_numpy(), name].to_numpy())
            coverage.append({'variable': name, 'hours': hours, 'window_start_utc': window_start.isoformat(),
                             'window_end_exclusive_utc': cutoff.isoformat(), 'clock_role': config['coverage_clock'],
                             'selected_hour_labels': int(selected.sum()), 'numeric_present_hours': int(present.sum()),
                             'strict_qc0_hours': int(accepted.sum()), 'qc_column_supplied': definitions[name]['qc_raw_column'] is not None,
                             'unit_label': definitions[name]['unit_label_standardized'],
                             'available_time': definitions[name]['available_time'], 'data_role': 'exploration',
                             'physical_phase': 'regional_station_pre_reference_window_not_source_state',
                             'limitation': 'raw support not event physics; unknown QC excluded from strict view, not declared physically invalid'})
    write_csv('results/window_support.csv', coverage)

    policy = load('track_b/config/temporal_policy.json')
    station = policy['hourly']['station']
    centre_lon, centre_lat = float(np.mean(lon)), float(np.mean(lat))
    geod = pyproj.Geod(ellps='WGS84')
    _, _, distance = geod.inv(station['longitude'], station['latitude'], centre_lon, centre_lat)
    scale = {'station_to_nc_parameter_domain_mean_centre_distance_km': distance / 1000,
             'station_metadata_status': station['metadata_status'],
             'distance_to_verified_failure_source_km': None,
             'meaning': 'representativeness diagnostic using a parameter-domain reference, not a source-location estimate'}
    forecast_summary = load('track_b/data/processed/forecast_sample/summary.json')
    with xr.open_dataset(use('track_b/data/processed/forecast_sample/gfs_2026082518_f009_aoi.nc'), engine='h5netcdf') as ds:
        scale['forecast_grid_shape'] = dict(ds.sizes)
        scale['forecast_grid_spacing_degrees'] = {'longitude': float(abs(np.diff(ds.longitude.values)[0])),
                                                   'latitude': float(abs(np.diff(ds.latitude.values)[0]))}
    scale['historical_forecast_available_time'] = forecast_summary['actual_operational_available_time']
    ledger = load('track_b/data/external/event_remote/event_evidence_ledger.json')
    approved_groups = {r['independent_event_group'] for r in ledger['records'] if r['approved_training_label']}
    labels = {'evidence_rows': len(ledger['records']), 'event_groups': len({r['independent_event_group'] for r in ledger['records']}),
              'approved_independent_groups': len(approved_groups), 'meaning': 'row count is not independent-event count'}

    parameters = []
    for row in stats:
        parameters.append({**meta, 'parameter': row['variable'], 'definition': row['metadata_description'],
                           'units': row['units'], 'observed_or_derived': 'supplied gridded product',
                           'space_scale': '30 m NC parameter grid', 'time_scale': row['time_support'],
                           'value_min': row['min'], 'value_max': row['max'], 'finite_support_cells': row['finite_cells'],
                           'source_path': nc_name, 'source_sha256': inputs[nc_name]['sha256'],
                           'identifiability_for_event': 'background_only', 'event_parameter_value': None,
                           'uncertainty': 'product/model/epoch and transfer uncertainty not quantified',
                           'next_action': 'Q4 verify source geometry and terrain; Q2 assess temporal/mechanistic transfer',
                           'cross_question_consumers': 'Q2,Q4; Q3 only after explicit reviewed transfer'})
    missing = [
        ('failure_polygon', '真实源区失稳边界', 'geometry', 'Q4核验灾前后影像及可追溯多边形'),
        ('sliding_surface_geometry', '滑动／接触面几何和厚度', 'm, degree', 'Q4几何与Q2机制证据；不能以地表坡度代替滑动面'),
        ('discontinuity_orientation', '结构面产状、间距和贯通性', 'degree, m', 'Q2取得原始地质／调查约束'),
        ('ice_rock_density', '事发物源组分和密度', 'kg m-3', 'Q2区分文献情景与现场组分约束'),
        ('cohesion', '相关结构／接触面的黏聚强度', 'Pa', 'Q2取得适用材料、试验条件及范围'),
        ('friction_angle', '相关结构／接触面的摩擦参数', 'degree', 'Q2核实接触类型与试验／校准独立证据'),
        ('pore_pressure', '源区孔隙或裂隙水压力', 'Pa', 'Q2需水文／水压约束，不能由区域站土壤含水率直接替代'),
        ('basal_ice_temperature', '源区接触面温度与冻结状态', 'degree C', 'Q2需源区温度约束，塔站气温不是接触面温度'),
        ('source_water_input', '源区降雨、融水输入及排泄', 'mm, m3 s-1', 'Q1质量／累计口径，Q2源区水量和排水证据'),
        ('event_velocity_acceleration', '事前源区速度变化与加速', 'm s-1, m s-2', 'Q2/Q4需事件前时序观测；气候态与GRD相位缺失不能补齐'),
        ('event_release_volume', '实际释放体积与冰岩组分', 'm3', 'Q4源区边界、滑动面与地形年代确认后再估计'),
        ('entrainable_material', '沿程可卷入松散物与含水状态', 'm3, dimensionless', 'Q2/Q4需沿程调查或独立遥感约束')]
    for symbol, definition, units, next_action in missing:
        parameters.append({**meta, 'evidence_status': 'candidate', 'parameter': symbol, 'definition': definition, 'units': units,
                           'observed_or_derived': 'not independently measured in supplied inputs',
                           'space_scale': 'event source or path not verified', 'time_scale': '2026 event state needed',
                           'event_parameter_value': None, 'source_path': None, 'source_sha256': None,
                           'identifiability_for_event': 'unconstrained', 'uncertainty': 'unquantified; no arbitrary default adopted',
                           'next_action': next_action, 'cross_question_consumers': 'Q2,Q4; selected state requirements to Q3'})
    for symbol, source, definition, units, status, next_action in [
        ('regional_weather', 'track_b/data/processed/temporal/data_dictionary.json', '区域站水热／辐射代理', 'per-variable metadata', 'proxy_only', 'Q1确认质量与时间语义；Q2检验空间代表性'),
        ('forecast_weather', 'track_b/data/processed/forecast_sample/summary.json', '0.25 degree GFS技术样本', 'per-variable metadata', 'coarse_proxy_only', 'Q3补充有界历史起报并核实业务时效'),
        ('landcover_background', 'track_b/data/external/event_remote/worldcover_2021_v200_test_aoi.tif', '2021背景分类', 'categorical code', 'background_only', 'Q2取得并检验2026实际像元，不能据分类判定破坏面'),
        ('remote_state_2026', 'track_b/data/external/event_remote/scene_inventory.json', '2026遥感场景元数据', 'none; no pixels interpreted', 'metadata_only', 'Q2合法获取最少必要影像并检查源区可见性'),
        ('trigger_threshold', 'track_b/data/external/event_remote/event_evidence_ledger.json', '可迁移触发临界条件', 'model-dependent', 'not_estimable_from_current_approved_labels', 'Q3审核同机制事件／对照；队员确认路线后估计并独立验证')]:
        parameters.append({**meta, 'evidence_status': 'candidate' if symbol == 'trigger_threshold' else 'local_fact',
                           'parameter': symbol, 'definition': definition, 'units': units,
                           'source_path': source, 'source_sha256': digest(ROOT / source), 'event_parameter_value': None,
                           'identifiability_for_event': status, 'uncertainty': 'support and transfer limitations retained',
                           'next_action': next_action, 'cross_question_consumers': 'Q1,Q2,Q3,Q4 as reviewed'})
    write_csv('results/parameter_evidence.csv', parameters)

    checks = [
        {'name': 'nine_parameter_fields_full_numeric_support_on_parameter_mask', 'passed': all(s['finite_cells'] == 7152 for s in stats)},
        {'name': 'all_41_catalogue_scenes_screened_without_pixel_acceptance', 'passed': len(rows) == 41 and not any(r['pixel_visibility_verified'] for r in rows)},
        {'name': 'background_worldcover_read_and_aligned', 'passed': cover['valid_background_cells'] == 7152},
        {'name': 'three_fixed_pre_reference_support_windows', 'passed': len(coverage) == len(variables) * 3},
        {'name': 'no_independent_approved_label_inflation', 'passed': labels['approved_independent_groups'] == 0},
        {'name': 'no_event_parameter_or_threshold_estimated', 'passed': all(p['event_parameter_value'] is None for p in parameters)}]
    result = {**meta, 'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': all(c['passed'] for c in checks),
              'scientific_model_acceptance': 'not_evaluated; velocity identity discrepancy remains unresolved',
              'scope': 'numerical support, metadata compatibility and parameter identifiability only',
              'nc': nc_metadata, 'velocity_arithmetic_consistency': velocity_consistency,
              'dem_comparison': dem_comparison, 'worldcover_background': cover,
              'remote_catalogue_count': len(rows), 's1_pair_screen': pair_summary, 'scale_support': scale,
              'label_support': labels, 'parameter_evidence_rows': len(parameters), 'checks': checks,
              'uncertainty_not_resolved': ['source geometry', 'vertical datum and terrain epoch', 'structural and hydraulic state',
                                           'forecast publication latency', 'actual 2026 pixel visibility', 'independent labels and controls']}
    write_json('results/input_check.json', result)
    write_json('results/input_manifest.json', {'input_version': version, 'files': list(inputs.values()),
                                              'config': {'path': str(CONFIG.relative_to(ROOT)), 'sha256': digest(CONFIG)},
                                              'script': {'path': str(Path(__file__).relative_to(ROOT)), 'sha256': digest(Path(__file__))}})
    if not result['passed']:
        raise RuntimeError('A diagnostic integrity check failed; inspect results/input_check.json')
    print(json.dumps({'passed': True, 'parameter_rows': len(parameters), 'scene_rows': len(rows),
                      'window_rows': len(coverage), 'compatible_s1_pairs': len(pairs), 'approved_labels': len(approved_groups)}))


if __name__ == '__main__':
    main()
