#!/usr/bin/env python3
"""Instantiate Q2 plan areas without substituting the full Q4 source area."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import math

import numpy as np
import rasterio
from affine import Affine
from scipy.optimize import brentq
from pyproj import Transformer
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import transform as transform_geometry

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
CACHE = Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q4/integrated_inputs/q4-r3-q2-mapped-release-v1')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def rec(p, role):
    return {'path': str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
            'bytes': p.stat().st_size, 'sha256': sha(p), 'role': role}


def main():
    protocol = json.loads((R/'config/q2_release_mapping_protocol.json').read_text())
    bundle_path = ROOT/protocol['q2_bundle_path']
    assert sha(bundle_path) == protocol['q2_bundle_sha256']
    bundle = json.loads(bundle_path.read_text())
    state_entry = next(f for f in bundle['files'] if f['role'] == 'results/release_states.csv')
    state_path = ROOT/state_entry['path']
    assert sha(state_path) == state_entry['sha256']
    states = {row['scenario_id']: row for row in csv.DictReader(state_path.open())}
    geom_path = R/'results/computational_geometries.geojson'
    gj = json.loads(geom_path.read_text())
    # The frozen input is RFC7946-style CRS84 longitude/latitude, with crs_note;
    # never assign a metric CRS to degree coordinates.
    source_ll = shape(next(f['geometry'] for f in gj['features'] if f['id'] == 'paper_source_outline'))
    assert -180 <= source_ll.bounds[0] <= 180 and -90 <= source_ll.bounds[1] <= 90
    source = transform_geometry(Transformer.from_crs(4326, 32645, always_xy=True).transform, source_ll)
    centre = source.centroid
    a = np.load(R/'results/spatial_inputs_60m.npz')
    z, dx = a['z'], float(a['dx'])
    transform = Affine(*a['transform'][:6])
    CACHE.mkdir(parents=True, exist_ok=True)
    features, records = [], []
    for ident in protocol['selected_scenario_ids']:
        row = states[ident]
        area = float(row['plan_area_m2'])
        height = float(row['release_thickness_vertical_m'])
        volume = float(row['release_volume_m3'])
        assert 0 < area < source.area and math.isclose(area*height, volume, rel_tol=1e-12)
        fractions = json.loads(row['phase_fractions'])
        assert row['phase_fraction_basis'] == 'volume' and math.isclose(sum(fractions.values()), 1, abs_tol=1e-12)
        density = float(row['density'])
        assert math.isclose(density, 2700*fractions['rock']+917*fractions['ice']+1000*fractions['free_water'], rel_tol=1e-12)
        radius = brentq(lambda radius: source.intersection(centre.buffer(radius, quad_segs=64)).area-area,
                        0.01, 10000, xtol=1e-9)
        polygon = source.intersection(centre.buffer(radius, quad_segs=64))
        fraction = np.zeros(z.shape, dtype=np.float64)
        # Domain is small; only polygon bounding-box cells need exact intersections.
        west, south, east, north = polygon.bounds
        r0, c0 = rasterio.transform.rowcol(transform, west, north)
        r1, c1 = rasterio.transform.rowcol(transform, east, south)
        for i in range(max(0, r0-1), min(z.shape[0], r1+2)):
            for j in range(max(0, c0-1), min(z.shape[1], c1+2)):
                x, y = transform*(j, i)
                fraction[i, j] = polygon.intersection(box(x, y-dx, x+dx, y)).area/(dx*dx)
        depth = (height*fraction).astype('float32')
        actual = float(depth.astype('float64').sum()*dx*dx)
        assert math.isclose(float(fraction.sum()*dx*dx), area, rel_tol=1e-10)
        assert math.isclose(actual, volume, rel_tol=1e-6)
        tag = ident.replace('-', '_')
        path = CACHE/f'{tag}_release_60m.tif'
        with rasterio.open(path, 'w', driver='GTiff', height=z.shape[0], width=z.shape[1],
                           count=1, dtype='float32', crs='EPSG:32645', transform=transform,
                           nodata=-9999, compress='deflate') as ds:
            ds.write(depth, 1)
        npz = R/'results'/f'q2_mapped_{tag}_60m.npz'
        np.savez_compressed(npz, release_depth=depth, source_fraction=fraction.astype('float32'),
                            transform=np.array(transform), x=a['x'], y=a['y'])
        metadata = {
            'scenario_id': ident, 'upstream_model_id': row['model_id'], 'mechanism_id': row['mechanism_id'],
            'upstream_parameter_version': row['parameter_version'], 'geometry_version': 'q4-r3-q2-mapped-release-v1',
            'source_plan_area_m2': area, 'actual_polygon_area_m2': polygon.area,
            'thickness_normal_m': float(row['release_thickness_normal_m']), 'thickness_vertical_m': height,
            'upstream_release_volume_m3': volume, 'grid_integrated_release_volume_m3': actual,
            'grid_volume_relative_error': (actual-volume)/volume, 'grid_resolution_m': dx,
            'fractional_source_cells': int((fraction > 0).sum()), 'equivalent_full_source_cells': area/(dx*dx),
            'fractional_area_method': 'Exact intersection area, mean vertical cell thickness; underresolved small sources explicitly retained',
            'phase_fraction_basis': 'volume', 'phase_fractions': fractions, 'bulk_density_kg_m3': density,
            'initial_velocity_east_north_m_s': [0, 0], 'initial_velocity_crs': 'EPSG:32645',
            'upstream_onset_status': row['onset_status'], 'if_released_propagation': row['onset_status'] == 'never_crossed',
            'not_an_initiation_prediction': True, 'initiation_to_release_delay_seconds': None,
            'evaluation_stratum': 'conditional_scenario', 'data_role': 'scenario', 'time_utc': None,
            'time_uncertainty': None, 'available_time': None,
            'source_mapping_assumption': 'Circular compact subsource centred on paper candidate centroid, clipped to that polygon, area solved exactly; no observed release geometry claim',
            'release_raster': rec(path, 'native_solver_mapped_release'), 'release_arrays': rec(npz, 'mapped_release_arrays')}
        features.append({'type': 'Feature', 'id': ident, 'geometry': mapping(polygon), 'properties': metadata})
        records.append(metadata)
    out = R/'results/q2_mapped_releases.geojson'
    save(out, {'type': 'FeatureCollection', 'name': 'q4-r3-q2-mapped-release-v1',
               'crs': {'type': 'name', 'properties': {'name': 'EPSG:32645'}}, 'features': features})
    save(R/'results/q2_release_mapping.json', {
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'protocol': rec(R/'config/q2_release_mapping_protocol.json', 'preregistration'),
        'upstream_bundle': rec(bundle_path, 'advisor_delivered_q2_bundle'), 'source_geometry': rec(geom_path, 'frozen_candidate_envelope'),
        'mapped_geometries': rec(out, 'mapped_compact_sources'), 'releases': records,
        'no_probability_weights': True, 'geometry_truth_accepted': False})
    print(json.dumps({'mapped': len(records), 'volumes_m3': [row['grid_integrated_release_volume_m3'] for row in records],
                      'if_released': [row['scenario_id'] for row in records if row['if_released_propagation']]}))


if __name__ == '__main__':
    main()
