#!/usr/bin/env python3
"""Offline integration checks for stage-3 real data I/O and saved provenance.

AI assistance: Codex, OpenAI, 2026-10-23; exact model/version unavailable.
These checks establish technical data readiness, not model validity or hazard skill.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import eccodes
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, reproject
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'track_b'
OUT = WORK / 'audit/stage3'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify_manifest(base, entries):
    count = 0
    if isinstance(entries, dict):
        entries = [dict(file=name, **value) for name, value in entries.items()]
    for entry in entries:
        path = base / entry.get('file', entry.get('path'))
        assert path.is_file(), str(path)
        assert path.stat().st_size == entry['bytes'], str(path)
        assert digest(path) == entry['sha256'], str(path)
        count += 1
    return count


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, function):
        try:
            evidence = function()
            checks.append({'name': name, 'passed': True, 'evidence': evidence})
            print(f'PASS {name}', flush=True)
        except Exception as exc:
            checks.append({'name': name, 'passed': False, 'error': f'{type(exc).__name__}: {exc}'})
            print(f'FAIL {name}: {type(exc).__name__}: {exc}', flush=True)

    def runtime():
        assert Path(sys.prefix).resolve() == (WORK / '.venv').resolve()
        env = load(OUT / 'environment.json')
        assert env['isolated_venv'] and env['lock_matches_installed'] and env['pip_check_exit_code'] == 0
        assert env['lock_sha256'] == digest(WORK / 'requirements-lock.txt')
        return {'python': sys.version.split()[0], 'native_libraries': env['native_libraries']}
    check('isolated_runtime_and_lock', runtime)

    def source_formats():
        csv_path = ROOT / '04_B赛道/01_逐小时地气观测（2021-2026）/MET_Gyirong_2026.csv'
        book = ROOT / '04_B赛道/02_逐日平均气温（2005-2025）/2米气温数据_2025.xlsx'
        frame = pd.read_csv(csv_path, nrows=3)
        daily = pd.read_excel(book, engine='openpyxl')
        assert len(frame) == 3 and len(daily) == 214
        shape = next((ROOT / '04_B赛道/06_历史灾点').glob('*.shp'))
        history = gpd.read_file(shape)
        assert len(history) == 84 and history.crs.to_epsg() == 4490
        dem = ROOT / '04_B赛道/07_DEM（2026-08-26）/DEM.tif'
        with rasterio.open(dem) as dataset:
            sample = dataset.read(1, window=rasterio.windows.Window(0, 0, 16, 16), masked=True)
            assert dataset.shape == (1148, 1816) and sample.count() == 256
        nc = next((ROOT / '04_B赛道/04_冰川地形、冰厚及表面速度').glob('*.nc'))
        with xr.open_dataset(nc, engine='h5netcdf', decode_cf=True, decode_coords='all') as dataset:
            assert dataset.sizes['y'] == 138 and dataset.sizes['x'] == 145
            assert 'time' not in dataset.dims
            assert int(((dataset.glacier_mask > 0) & np.isfinite(dataset.glacier_mask)).sum()) == 7152
        grib = WORK / 'data/external/forecast_sample/temperature_2m.grib2'
        with grib.open('rb') as handle:
            message = eccodes.codes_grib_new_from_file(handle)
            assert message is not None
            try:
                assert eccodes.codes_get(message, 'dataDate') == 20260825
                assert eccodes.codes_get(message, 'dataTime') == 1800
                assert eccodes.codes_get(message, 'units') == 'K'
            finally:
                eccodes.codes_release(message)
        return {'actual_input_formats': ['CSV', 'XLSX', 'SHP', 'GeoTIFF', 'NetCDF4', 'GRIB2']}
    check('six_real_input_formats', source_formats)

    def temporal():
        base = WORK / 'data/processed/temporal'
        summary = load(base / 'quality_summary.json')
        assert summary['verification_passed'] and load(base / 'verification.json')['passed']
        assert summary['script_sha256'] == digest(WORK / 'scripts/prepare_temporal.py')
        assert summary['config_sha256'] == digest(WORK / 'config/temporal_policy.json')
        input_count = verify_manifest(ROOT, load(base / 'input_manifest.json'))
        output_count = verify_manifest(base, load(base / 'output_manifest.json'))
        raw = pd.read_parquet(base / 'hourly_raw_numeric.parquet')
        quality = pd.read_parquet(base / 'hourly_raw_qc.parquet')
        strict = pd.read_parquet(base / 'hourly_strict_qc0.parquet')
        mask = pd.read_parquet(base / 'hourly_mask_strict_qc0_accepted.parquet')
        assert raw.shape == (52584, 63) and quality.shape == (52584, 37)
        values = raw.to_numpy()
        eligible = np.isfinite(values) & (values != 9999.9)
        independent = np.zeros(raw.shape, dtype=bool)
        for i, column in enumerate(raw.columns):
            if column in quality:
                independent[:, i] = eligible[:, i] & (quality[column].to_numpy() == '0')
        np.testing.assert_array_equal(independent, mask.to_numpy())
        expected = np.where(independent, values, np.nan)
        np.testing.assert_array_equal(expected, strict.to_numpy())
        assert not (strict.to_numpy() == 9999.9).any()
        unknown_columns = [column for column in raw.columns if column not in quality]
        assert len(unknown_columns) == 26 and strict[unknown_columns].isna().all().all()
        time_axis = pd.read_parquet(base / 'hourly_time_axis.parquet')
        restored = time_axis['time_utc'].dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
        assert restored.equals(time_axis['time_source_naive'])
        return {'input_hashes': input_count, 'output_hashes': output_count,
                'cells_independently_compared': int(raw.size), 'unknown_qc_columns': len(unknown_columns),
                'strict_qc0_cells': int(independent.sum()), 'component_checks': summary['verification_check_count']}
    check('temporal_values_masks_time_and_hashes', temporal)

    def spatial():
        base = WORK / 'data/processed/spatial'
        report = load(base / 'pipeline_report.json')
        assert all(report['source_integrity_after_run'].values())
        inputs = verify_manifest(ROOT, load(base / 'source_manifest.json'))
        outputs = verify_manifest(base, load(base / 'output_manifest.json'))
        for item in report['verification']['raster_readbacks']:
            assert item['readback_ok']
            with rasterio.open(base / item['file']) as dataset:
                assert list(dataset.shape) == item['shape_yx'] and dataset.crs.to_epsg() == 32645
        for layer, item in report['verification']['geopackage_readbacks'].items():
            assert item['records'] == item['valid_geometry_count']
            frame = gpd.read_file(base / 'spatial_diagnostic.gpkg', layer=layer)
            assert len(frame) == item['records'] and bool(frame.geometry.is_valid.all())
        historical = pd.read_csv(base / 'history_dem_coverage.csv')
        assert len(historical) == 84
        visual = load(base / 'visual_review.json')
        assert visual['figure_sha256'] == digest(base / visual['figure'])
        assert report['historical_inventory_coverage']['positive_area_overlap'] == 23
        return {'input_hashes': inputs, 'output_hashes': outputs, 'raster_readbacks': len(report['verification']['raster_readbacks']),
                'geopackage_layers': len(report['verification']['geopackage_readbacks']),
                'history_positive_area_overlap': 23, 'source_to_port_continuity_verified': False}
    check('formal_spatial_readbacks_and_manifest', spatial)

    def forecast():
        base = WORK / 'data/processed/forecast_sample'
        summary = load(base / 'summary.json')
        assert summary['success'] and summary['netcdf_roundtrip_equal'] and len(summary['messages']) == 6
        assert summary['actual_operational_available_time'] is None
        assert digest(ROOT / summary['netcdf_file']) == summary['netcdf_sha256']
        with xr.open_dataset(ROOT / summary['netcdf_file'], engine='h5netcdf') as region:
            for item in summary['messages']:
                raw = WORK / 'data/external/forecast_sample' / item['raw_file']
                assert digest(raw) == item['sha256']
                with xr.open_dataset(raw, engine='cfgrib', backend_kwargs={'indexpath': ''}) as global_field:
                    var = global_field[item['grib']['shortName']] if item['grib']['shortName'] in global_field else next(iter(global_field.data_vars.values()))
                    crop = var.sel(latitude=region.latitude, longitude=region.longitude)
                    np.testing.assert_array_equal(crop.values, region[item['label']].values)
                assert item['grib']['endStep'] == 9 and item['grib']['stepUnits'] == 1
        return {'complete_grib_messages': 6, 'retrieved_grib_bytes': summary['cached_grib_bytes'],
                'cells_per_variable': 25, 'operational_availability_verified': False}
    check('forecast_complete_messages_and_regional_roundtrip', forecast)

    def remote():
        base = WORK / 'data/external/event_remote'
        summary = load(base / 'summary.json')
        count = verify_manifest(base, load(base / 'manifest.json')['files'])
        assert summary['scene_count'] > 0 and summary['worldcover_crop_success']
        assert summary['accepted_independent_historical_training_events'] == 0
        ledger = load(base / 'event_evidence_ledger.json')
        assert all(not item['approved_training_label'] for item in ledger['records'])
        with rasterio.open(base / 'worldcover_2021_v200_test_aoi.tif') as source:
            with rasterio.open(WORK / 'data/processed/spatial/nc_glacier_mask.tif') as mask_grid:
                mask = mask_grid.read(1, masked=True).filled(0) > 0
                aligned = np.zeros(mask.shape, dtype=np.uint8)
                reproject(source=rasterio.band(source, 1), destination=aligned,
                          src_transform=source.transform, src_crs=source.crs, src_nodata=source.nodata,
                          dst_transform=mask_grid.transform, dst_crs=mask_grid.crs, dst_nodata=0,
                          resampling=Resampling.nearest)
                valid = aligned[mask] != 0
                assert int(mask.sum()) == 7152 and valid.all()
                codes, counts = np.unique(aligned[mask], return_counts=True)
                coverage = {'worldcover_year': 2021, 'source_sha256': digest(base / 'worldcover_2021_v200_test_aoi.tif'),
                            'method': 'Rasterio reproject to NC grid, nearest resampling; original class codes retained.',
                            'mask_cells': 7152, 'valid_class_cells': int(valid.sum()),
                            'class_code_counts': {str(int(code)): int(value) for code, value in zip(codes, counts)},
                            'limitation': '2021 background classification; not an observed 2026 failure polygon or event-time land-cover map.'}
        (OUT / 'worldcover_nc_alignment.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + '\n')
        return {'saved_file_hashes': count, 'scenes': summary['scene_count'],
                'accepted_training_events': 0, 'worldcover_2021_valid_nc_mask_cells': 7152}
    check('remote_provenance_and_worldcover_cross_module_alignment', remote)

    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'passed': all(item['passed'] for item in checks), 'check_count': len(checks), 'checks': checks,
              'scope': 'Technical minimum data loop and offline saved-evidence checks. No hazard model or statistical coverage validation.',
              'remaining': ['Human-reviewed event labels and controls', 'Actual historical forecast publication latency',
                            'Confirmed failure polygon, port target and river corridor', 'DEM dates, vertical references and discrepancies',
                            'Hourly interval semantics, no-QC physical checks, and daily temperature preprocessing']}
    (OUT / 'integration_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'checks': len(checks),
                      'failed': [item for item in checks if not item['passed']]}, ensure_ascii=False, indent=2))
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
