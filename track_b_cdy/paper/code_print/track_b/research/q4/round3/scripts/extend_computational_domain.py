#!/usr/bin/env python3
"""Extend same-product borders while preserving the original core for comparison."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import numpy as np
import rasterio
from affine import Affine
from rasterio.warp import reproject, Resampling

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'
CACHE = Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q4/integrated_inputs/domain_extension_v1')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rec(p, role):
    return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p), 'role': role}


def main():
    protocol = json.loads((R/'config/domain_extension_protocol.json').read_text())
    terrain = json.loads((R/'results/terrain_bundle.json').read_text())
    p = int(protocol['pad_cells_each_side'])
    base = np.load(R/'results/spatial_inputs_120m.npz')
    old = base['z']
    dx = float(base['dx'])
    tr = Affine(*base['transform'][:6]) * Affine.translation(-p, -p)
    z = np.full((old.shape[0]+2*p, old.shape[1]+2*p), np.nan, dtype='float32')
    raw = Path(terrain['primary']['source_path'])
    assert sha(raw) == terrain['primary']['sha256']
    with rasterio.open(raw) as src:
        reproject(rasterio.band(src, 1), z, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=tr, dst_crs='EPSG:32645', resampling=Resampling.bilinear,
                  dst_nodata=np.nan)
    assert np.isfinite(z).all()
    old_slice = (slice(p, p+old.shape[0]), slice(p, p+old.shape[1]))
    difference = z[old_slice].astype('float64')-old
    comparison = {'mean_m': float(difference.mean()), 'rmse_m': float(np.sqrt(np.mean(difference**2))),
                  'max_abs_m': float(np.max(np.abs(difference)))}
    # Explicit same-source core preservation removes a resampling-domain confound.
    z[old_slice] = old
    h = np.pad(base['source_mask'].astype('float64')*(925200/964800)*15, p).astype('float32')
    CACHE.mkdir(parents=True, exist_ok=True)
    files = []
    for name, data in [('dem_120m.tif', z), ('release_h15_120m.tif', h)]:
        path = CACHE/name
        with rasterio.open(path, 'w', driver='GTiff', width=z.shape[1], height=z.shape[0],
                           count=1, dtype='float32', crs='EPSG:32645', transform=tr,
                           nodata=-9999, compress='deflate') as ds:
            ds.write(data, 1)
        files.append(rec(path, 'extended_dem' if name.startswith('dem') else 'same_reference_release'))
    result = {'version': protocol['extended_geometry_version'], 'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'protocol_sha256': sha(R/'config/domain_extension_protocol.json'),
              'base_grid_path': 'results/spatial_inputs_120m.npz', 'base_grid_sha256': sha(R/'results/spatial_inputs_120m.npz'),
              'source_product': rec(raw, 'same_native_Copernicus_tile'), 'shape': list(z.shape),
              'affine': list(tr)[:6], 'resolution_m': dx, 'pad_cells': p,
              'same_source_resampling_difference_before_core_preservation': comparison,
              'core_dem_exactly_preserved': bool(np.array_equal(z[old_slice], old)),
              'release_grid_volume_m3': float(h.astype('float64').sum()*dx*dx),
              'files': files,
              'target_policy': 'Copy unchanged actual targets directly from the original DClaw reference case.',
              'evaluation_stratum': 'conditional_scenario'}
    (R/'results/extended_domain_bundle.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'shape': list(z.shape), 'release_volume_m3': result['release_grid_volume_m3'],
                      'core_preserved': result['core_dem_exactly_preserved'], 'resampling_diff': comparison}))


if __name__ == '__main__':
    main()
