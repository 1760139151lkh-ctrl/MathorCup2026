#!/usr/bin/env python3
"""Retrieve six complete GFS GRIB messages by byte range and decode an AOI.

AI assistance: Codex, OpenAI, 2026-10-23; exact model/version unavailable.
This is an I/O and metadata demonstration, not a disaster forecast or skill test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import cfgrib
import eccodes
import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
SELECTORS = {
    'temperature_2m': ':TMP:2 m above ground:9 hour fcst:',
    'relative_humidity_2m': ':RH:2 m above ground:9 hour fcst:',
    'wind_u_10m': ':UGRD:10 m above ground:9 hour fcst:',
    'wind_v_10m': ':VGRD:10 m above ground:9 hour fcst:',
    'precip_accum_6_9h': ':APCP:surface:6-9 hour acc fcst:',
    'precip_accum_0_9h': ':APCP:surface:0-9 hour acc fcst:',
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'track_b/data/external/forecast_sample')
    parser.add_argument('--processed', type=Path, default=ROOT / 'track_b/data/processed/forecast_sample')
    parser.add_argument('--refresh', action='store_true', help='Explicitly refetch cached messages.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.processed.mkdir(parents=True, exist_ok=True)
    origin = datetime(2026, 8, 25, 18, tzinfo=timezone.utc)
    valid = origin + timedelta(hours=9)
    base = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20260825/18/atmos/gfs.t18z.pgrb2.0p25.f009'
    index_path = args.output / 'gfs_2026082518_f009.idx'
    if args.refresh or not index_path.exists():
        with urlopen(base + '.idx', timeout=30) as response:
            raw = response.read(1024 * 1024 + 1)
            if response.status != 200 or len(raw) > 1024 * 1024:
                raise ValueError('Unexpected index response or excessive size.')
        index_path.write_bytes(raw)
    index_lines = index_path.read_text(encoding='utf-8').splitlines()
    records = []
    for line in index_lines:
        pieces = line.split(':')
        if len(pieces) < 6 or not pieces[0].isdigit() or not pieces[1].isdigit():
            raise ValueError(f'Invalid GRIB index record: {line[:80]}')
        records.append((int(pieces[1]), line))
    arrays = {}
    metadata = []
    network_bytes = 0
    bbox = [85.0, 28.0, 86.0, 29.0]  # I/O test covering regional source/station vicinity; not a validated hazard domain.
    for label, selector in SELECTORS.items():
        matches = [i for i, (_, line) in enumerate(records) if selector in line]
        if len(matches) != 1:
            raise ValueError(f'Expected one index match for {label}, got {len(matches)}.')
        index = matches[0]
        start = records[index][0]
        end = records[index + 1][0] - 1
        expected_bytes = end - start + 1
        if expected_bytes > 3 * 1024 * 1024:
            raise ValueError('Selected message exceeds the planned sample size.')
        path = args.output / f'{label}.grib2'
        provenance_path = args.output / f'{label}.http.json'
        if args.refresh or not path.exists():
            with urlopen(Request(base, headers={'Range': f'bytes={start}-{end}'}), timeout=45) as response:
                content_range = response.headers.get('Content-Range')
                status = response.status
                payload = response.read(expected_bytes + 1)
                etag = response.headers.get('ETag')
            if status != 206 or not content_range or not content_range.startswith(f'bytes {start}-{end}/'):
                raise ValueError(f'Range request not honoured for {label}: {status}/{content_range}')
            if len(payload) != expected_bytes:
                raise ValueError(f'Unexpected message length for {label}.')
            if payload[:4] != b'GRIB' or payload[7] != 2 or payload[-4:] != b'7777':
                raise ValueError(f'Invalid complete GRIB2 message for {label}.')
            if int.from_bytes(payload[8:16], 'big') != expected_bytes:
                raise ValueError(f'GRIB length does not match index byte range for {label}.')
            path.write_bytes(payload)
            provenance_path.write_text(json.dumps({'url': base, 'range': [start, end], 'http_status': status,
                                                 'content_range': content_range, 'etag': etag,
                                                 'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
                                                 'bytes': len(payload), 'sha256': sha256(path)}, indent=2) + '\n')
            network_bytes += len(payload)
        provenance = json.loads(provenance_path.read_text())
        if path.stat().st_size != expected_bytes or sha256(path) != provenance['sha256']:
            raise ValueError(f'Cached message integrity failed for {label}.')
        with path.open('rb') as handle:
            message = eccodes.codes_grib_new_from_file(handle)
            if message is None:
                raise ValueError(f'ecCodes did not decode {label}.')
            try:
                keys = ['edition', 'shortName', 'name', 'units', 'paramId', 'typeOfLevel', 'level',
                        'dataDate', 'dataTime', 'validityDate', 'validityTime', 'stepType',
                        'startStep', 'endStep', 'stepUnits', 'Ni', 'Nj', 'numberOfDataPoints']
                fields = {key: eccodes.codes_get(message, key) for key in keys}
                decoded_values = eccodes.codes_get_values(message)
                if not np.isfinite(decoded_values).all():
                    raise ValueError(f'Non-finite raw GRIB values for {label}.')
            finally:
                eccodes.codes_release(message)
            if eccodes.codes_grib_new_from_file(handle) is not None:
                raise ValueError(f'More than one message in {label}.')
        if fields['dataDate'] != 20260825 or fields['dataTime'] != 1800:
            raise ValueError(f'Wrong reference time for {label}.')
        if fields['validityDate'] != 20260826 or fields['validityTime'] != 300 or fields['endStep'] != 9:
            raise ValueError(f'Wrong valid time or lead for {label}.')
        if fields['stepUnits'] != 1:
            raise ValueError(f'Lead-time unit is not hours for {label}.')
        expected_start = 6 if label == 'precip_accum_6_9h' else 0 if label == 'precip_accum_0_9h' else 9
        if fields['startStep'] != expected_start:
            raise ValueError(f'Unexpected interval start for {label}: {fields["startStep"]}')
        with xr.open_dataset(path, engine='cfgrib', backend_kwargs={'indexpath': ''}) as dataset:
            variables = list(dataset.data_vars)
            if len(variables) != 1:
                raise ValueError(f'Expected a single decoded variable in {label}.')
            variable = dataset[variables[0]]
            if variable.dims != ('latitude', 'longitude'):
                raise ValueError(f'Unexpected grid dimensions for {label}: {variable.dims}')
            latitude = dataset.latitude.values
            longitude = dataset.longitude.values
            lat_selected = latitude[(latitude >= bbox[1]) & (latitude <= bbox[3])]
            lon_selected = longitude[(longitude >= bbox[0]) & (longitude <= bbox[2])]
            regional = variable.sel(latitude=lat_selected, longitude=lon_selected).load()
            if regional.size == 0:
                raise ValueError('AOI extraction is empty.')
            arrays[label] = xr.DataArray(regional.values.copy(), dims=('latitude', 'longitude'),
                                        coords={'latitude': regional.latitude.values, 'longitude': regional.longitude.values},
                                        attrs={'units': fields['units'], 'long_name': fields['name'],
                                               'source_grib_variable': variables[0], 'type_of_level': fields['typeOfLevel'],
                                               'level': fields['level'], 'step_type': fields['stepType'],
                                               'start_step_hours': fields['startStep'], 'end_step_hours': fields['endStep'],
                                               'message_sha256': sha256(path)})
            metadata.append({'label': label, 'index_line': records[index][1], 'raw_file': path.name,
                             'sha256': sha256(path), 'bytes': path.stat().st_size, 'grib': fields,
                             'global_decoded_shape': list(variable.shape), 'aoi_shape': list(regional.shape),
                             'aoi_min': float(regional.min()), 'aoi_max': float(regional.max()),
                             'accumulation_start_utc': (origin + timedelta(hours=fields['startStep'])).isoformat()
                             if fields['stepType'] == 'accum' else None,
                             'accumulation_end_utc': valid.isoformat() if fields['stepType'] == 'accum' else None})
    prepared = xr.Dataset(arrays, attrs={'title': 'GFS small AOI I/O sample; not a disaster prediction',
                                       'source_url': base, 'forecast_reference_time_utc': origin.isoformat(),
                                       'forecast_valid_time_utc': valid.isoformat(), 'lead_hours': 9,
                                       'actual_operational_available_time': 'unknown',
                                       'bbox_west_south_east_north': json.dumps(bbox),
                                       'spatial_interpolation': 'none; original grid-cell centres retained',
                                       'nominal_grid_degrees': 0.25})
    netcdf_path = args.processed / 'gfs_2026082518_f009_aoi.nc'
    prepared.to_netcdf(netcdf_path, engine='h5netcdf')
    with xr.open_dataset(netcdf_path, engine='h5netcdf') as reread:
        for label in arrays:
            np.testing.assert_array_equal(reread[label].values, arrays[label].values)
    if (arrays['precip_accum_6_9h'].values < 0).any() or (arrays['precip_accum_0_9h'].values < 0).any():
        raise ValueError('Negative precipitation in AOI sample.')
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'success': True,
              'source_url': base, 'index_sha256': sha256(index_path),
              'forecast_reference_time_utc': origin.isoformat(), 'valid_time_utc': valid.isoformat(),
              'actual_operational_available_time': None,
              'bbox_west_south_east_north': bbox, 'messages': metadata,
              'cached_grib_bytes': sum(item['bytes'] for item in metadata),
              'network_grib_bytes_this_run': network_bytes, 'netcdf_file': str(netcdf_path.relative_to(ROOT)),
              'netcdf_sha256': sha256(netcdf_path), 'netcdf_roundtrip_equal': True,
              'limitations': ['Six complete global-variable GRIB messages were retrieved, then cropped locally; no full model file was downloaded.',
                             'A 0.25-degree grid does not resolve the approximately 4-km glacier grid or local valley weather.',
                             'A forecast valid time later than the event is allowed; it is input availability at issue time that must be established.',
                             'Actual business publication time is unknown; this is not evidence of an operationally successful disaster warning.',
                             'No disaster model, feature selection, thresholds, or prediction-interval calibration is performed.']}
    (args.processed / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'success': True, 'messages': len(metadata), 'grib_bytes': result['cached_grib_bytes'],
                      'aoi_cells_per_variable': int(next(iter(arrays.values())).size),
                      'netcdf': result['netcdf_file']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
