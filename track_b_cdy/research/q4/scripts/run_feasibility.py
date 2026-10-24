#!/usr/bin/env python3
"""Q4 first-round terrain diagnostics and explicitly synthetic numerical I/O.

OpenAI Codex assistance, 2026-10-24. No event routing or debris-flow solver.
Writes only track_b/research/q4; shared preparations remain unchanged.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[4]
Q = ROOT / 'track_b/research/q4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def table(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def stats(values):
    import numpy as np
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a)]
    if not a.size:
        return {'count': 0}
    return {'count': int(a.size), 'minimum': float(a.min()), 'maximum': float(a.max()),
            'mean': float(a.mean()), 'median': float(np.median(a)),
            'rmse_against_zero': float(np.sqrt(np.mean(a*a))),
            'quantiles_p05_p25_p75_p95': np.quantile(a, [.05, .25, .75, .95]).tolist()}


def readiness():
    if ROOT != Path(json.loads((Q / 'workspace_binding.json').read_text())['execution_root']).resolve():
        raise RuntimeError('Wrong execution worktree')
    if Path(sys.prefix).resolve() != (ROOT / 'track_b/.venv').resolve():
        raise RuntimeError('Use this worktree\'s isolated interpreter')
    report = Q / 'workspace_verification.json'
    if not report.exists() or not json.loads(report.read_text())['passed']:
        raise RuntimeError('Advisor workspace readiness has not passed')


def raster_read(path):
    import numpy as np
    import rasterio
    with rasterio.open(path) as ds:
        a = ds.read(1, masked=True).astype('float64').filled(np.nan)
        valid = np.isfinite(a)
        metadata = {'path': str(path.relative_to(ROOT)), 'sha256': digest(path),
                    'crs': str(ds.crs), 'shape_yx': list(ds.shape), 'transform_gdal': list(ds.transform.to_gdal()),
                    'bounds': list(ds.bounds), 'resolution_xy': list(ds.res),
                    'nodata': (str(ds.nodata) if ds.nodata is not None and not math.isfinite(ds.nodata) else ds.nodata),
                    'valid_cells': int(valid.sum()), 'total_cells': int(a.size), 'values': stats(a),
                    'acquisition_date_verified': False, 'vertical_datum_verified': False}
        return a, ds.profile.copy(), metadata


def terrain():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    import numpy as np
    import rasterio
    from rasterio.warp import reproject, Resampling
    import xarray as xr
    base = ROOT / 'track_b/data/processed/spatial'
    raw, raw_profile, raw_meta = raster_read(ROOT / '04_B赛道/07_DEM（2026-08-26）/DEM.tif')
    projected, projected_profile, projected_meta = raster_read(base / 'dem_utm45_30m.tif')
    independent, grid_profile, independent_meta = raster_read(base / 'dem_on_nc_grid.tif')
    nc_dem, nc_profile, nc_meta = raster_read(base / 'nc_dem_native_grid.tif')
    mask_array, mask_profile, mask_meta = raster_read(base / 'nc_glacier_mask.tif')
    same_grid = all(p['transform'] == grid_profile['transform'] and p['crs'] == grid_profile['crs'] and
                    p['width'] == grid_profile['width'] and p['height'] == grid_profile['height']
                    for p in (nc_profile, mask_profile))
    assert same_grid
    positive = np.isfinite(mask_array) & (mask_array > 0)
    supported = np.isfinite(independent) & np.isfinite(nc_dem)
    assert int(positive.sum()) == 7152
    assert supported[positive].all()
    diff = independent - nc_dem
    nearest = np.full(independent.shape, np.nan, dtype='float64')
    with rasterio.open(ROOT / raw_meta['path']) as source:
        reproject(rasterio.band(source, 1), nearest,
                  src_transform=source.transform, src_crs=source.crs, src_nodata=source.nodata,
                  dst_transform=grid_profile['transform'], dst_crs=grid_profile['crs'],
                  dst_nodata=np.nan, resampling=Resampling.nearest)
    sensitivity = nearest - independent
    profile = grid_profile.copy()
    profile.update(dtype='float64', nodata=np.nan, count=1, compress='deflate')
    diagnostic_path = Q / 'results/nearest_minus_bilinear_on_nc_grid.tif'
    with rasterio.open(diagnostic_path, 'w', **profile) as ds:
        ds.write(sensitivity, 1)
        ds.update_tags(role='exploration', purpose='resampling sensitivity; no terrain correction')
    with rasterio.open(diagnostic_path) as ds:
        np.testing.assert_array_equal(ds.read(1), sensitivity)
        assert ds.crs == grid_profile['crs'] and ds.transform == grid_profile['transform']
    spatial_report = json.loads((base / 'pipeline_report.json').read_text())
    nc_path = ROOT / spatial_report['netcdf']['source']
    with xr.open_dataset(nc_path, engine='h5netcdf', decode_cf=True, decode_coords='all') as ds:
        nc_semantics = {'path': str(nc_path.relative_to(ROOT)), 'sha256': digest(nc_path),
                        'dimensions': dict(ds.sizes), 'no_time_dimension': 'time' not in ds.dims,
                        'velocity_description': ds['v'].attrs.get('description'),
                        'velocity_units': ds['v'].attrs.get('units'),
                        'mask_description': ds['glacier_mask'].attrs.get('description'),
                        'thickness_description': ds['thickness'].attrs.get('description'),
                        'thickness_units': ds['thickness'].attrs.get('units'),
                        'thickness_on_inventory_mask_m': stats(ds['thickness'].values[positive]),
                        'climatological_speed_on_inventory_mask_m_per_year': stats(ds['v'].values[positive]),
                        'release_volume_inferred': False}
    timings = []
    with rasterio.open(base / 'dem_utm45_30m.tif') as ds:
        window = rasterio.windows.Window(100, 100, 128, 128)
        for _ in range(30):
            started = perf_counter()
            sample = ds.read(1, window=window, masked=True)
            timings.append(perf_counter() - started)
        assert sample.shape == (128, 128)
    result = {'same_grid_verified': same_grid, 'nc_parameter_grid_shape_yx': list(independent.shape),
              'nc_positive_parameter_mask_cells': int(positive.sum()),
              'nc_positive_parameter_mask_area_m2': float(positive.sum()*abs(grid_profile['transform'].a*grid_profile['transform'].e)),
              'nc_positive_mask_covered_by_independent_dem': bool(supported[positive].all()),
              'full_nc_grid_covered_by_independent_dem': bool(np.isfinite(independent).all()),
              'difference_independent_minus_nc_m': {'positive_parameter_mask': stats(diff[positive]), 'full_parameter_rectangle': stats(diff)},
              'resampling_nearest_minus_prepared_bilinear_m': {'positive_parameter_mask': stats(sensitivity[positive]), 'full_parameter_rectangle': stats(sensitivity)},
              'raster_inputs': [raw_meta, projected_meta, independent_meta, nc_meta, mask_meta],
              'netcdf_semantics': nc_semantics,
              'technical_window_io': {'window_shape': [128,128], 'read_repetitions': 30,
                                      'seconds': stats(timings), 'cache_state': 'warm/mixed OS-GDAL cache; not a simulation benchmark'},
              'terrain_correction_applied': False, 'hydrological_conditioning_applied': False,
              'source_polygon_verified': False, 'port_point_verified': False, 'channel_centreline_verified': False,
              'source_to_port_continuity_verified': False, 'actual_path_distance_m': None,
              'interpretation': 'Local grid support is verified; event release geometry, complete propagation corridor and vertical datum are not.'}
    save(Q / 'results/terrain_feasibility.json', result)
    fig, axes = plt.subplot_mosaic([['regional','difference'],['histogram','resampling']], figsize=(13,9))
    ax = axes['regional']
    b = projected_meta['bounds']
    extent = [b[0]/1000,b[2]/1000,b[1]/1000,b[3]/1000]
    image = ax.imshow(projected, extent=extent, cmap='terrain', origin='upper', rasterized=True)
    bounds = nc_meta['bounds']
    ax.add_patch(Rectangle((bounds[0]/1000,bounds[1]/1000),(bounds[2]-bounds[0])/1000,
                           (bounds[3]-bounds[1])/1000,fill=False,edgecolor='#D62D83',linewidth=2,
                           label='NC parameter rectangle'))
    ax.set(title='Available projected DEM and NC parameter domain',xlabel='UTM 45N easting (km)',ylabel='UTM 45N northing (km)')
    ax.legend(loc='upper left',fontsize=9)
    fig.colorbar(image, ax=ax, label='Elevation (m; datum unverified)',shrink=.85)
    ax = axes['difference']
    b = nc_meta['bounds']; extent = [b[0]/1000,b[2]/1000,b[1]/1000,b[3]/1000]
    limit = max(10, math.ceil(float(np.nanmax(np.abs(diff[positive])))/10)*10)
    image = ax.imshow(np.where(positive,diff,np.nan),extent=extent,cmap='RdBu_r',vmin=-limit,vmax=limit,origin='upper')
    xs = (grid_profile['transform'].c+(np.arange(diff.shape[1])+.5)*grid_profile['transform'].a)/1000
    ys = (grid_profile['transform'].f+(np.arange(diff.shape[0])+.5)*grid_profile['transform'].e)/1000
    ax.contour(xs,ys,positive.astype(float),levels=[.5],colors=['#252525'],linewidths=.7)
    ax.set(title='Independent minus NC DEM on inventory mask',xlabel='Easting (km)',ylabel='Northing (km)')
    fig.colorbar(image,ax=ax,label='Difference (m)')
    ax=axes['histogram']; ax.hist(diff[positive],bins=40,color='#406985',edgecolor='white',linewidth=.3)
    ax.axvline(0,color='black',linewidth=.7)
    ax.set(title='Differences on the NC positive mask (not a failure polygon)',xlabel='Independent DEM minus NC DEM (m)',ylabel='Grid cells')
    ax=axes['resampling']
    limit=max(5,math.ceil(float(np.nanmax(np.abs(sensitivity[positive])))/5)*5)
    image=ax.imshow(np.where(positive,sensitivity,np.nan),extent=extent,cmap='PuOr_r',vmin=-limit,vmax=limit,origin='upper')
    ax.contour(xs,ys,positive.astype(float),levels=[.5],colors=['#252525'],linewidths=.7)
    ax.set(title='Independent DEM: nearest minus bilinear',xlabel='Easting (km)',ylabel='Northing (km)')
    fig.colorbar(image,ax=ax,label='Resampling difference (m)')
    fig.suptitle('Q4 first-round terrain feasibility: exploration only',fontsize=15,y=.98)
    fig.text(.5,.025,'EPSG:32645; NC mask is not an event failure polygon. No event route is drawn; source-to-port continuity remains unverified.',ha='center',fontsize=9)
    fig.subplots_adjust(left=.07,right=.96,bottom=.11,top=.92,wspace=.25,hspace=.4)
    fig.savefig(Q/'figures/terrain_feasibility.png',dpi=160)
    plt.close(fig)
    return result


def synthetic(config):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    import xarray as xr
    settings = config['synthetic']
    L, c, T = settings['domain_length_m'], settings['speed_m_per_s'], settings['duration_s']
    def solve(n, courant_target):
        if not (0 < courant_target <= 1):
            raise ValueError('Synthetic monotone upwind test requires 0 < Courant <= 1')
        dx=L/n; steps=math.ceil(T/(courant_target*dx/c)); dt=T/steps; C=c*dt/dx
        x=(np.arange(n)+.5)*dx
        def exact(t):
            delta=(x-settings['initial_centre_m']-c*t+L/2)%L-L/2
            return np.exp(-.5*(delta/settings['initial_sigma_m'])**2)
        q=exact(0); initial=q.copy(); integral0=float(q.sum()*dx); frames=[q.copy()]; times=[0.0]
        max_integral_error=0.0; started=perf_counter()
        for step in range(1,steps+1):
            q=q-C*(q-np.roll(q,1))
            max_integral_error=max(max_integral_error,abs(float(q.sum()*dx)-integral0)/integral0)
            if step in (steps//2,steps): frames.append(q.copy()); times.append(step*dt)
        result={'cells':n,'dx_m':dx,'dt_s':dt,'steps':steps,'courant':C,
                'relative_integral_error_max':max_integral_error,'minimum':float(q.min()),'maximum':float(q.max()),
                'relative_l1_error':float(np.abs(q-exact(T)).sum()*dx/integral0),'compute_seconds':perf_counter()-started}
        assert np.isfinite(q).all() and q.min()>=-1e-14 and q.max()<=initial.max()+1e-14
        assert max_integral_error < 1e-12
        return result,x,initial,q,exact(T),np.array(frames),times
    runs=[solve(n,settings['courant_target']) for n in settings['cells']]
    shift=solve(settings['cells'][0],settings['exact_shift_courant'])
    np.testing.assert_allclose(shift[3],shift[4],atol=1e-14,rtol=0)
    errors=[r[0]['relative_l1_error'] for r in runs]
    assert all(a>b for a,b in zip(errors,errors[1:]))
    rejected=False
    try: solve(100,1.2)
    except ValueError: rejected=True
    assert rejected
    coarse=runs[0]
    ds=xr.Dataset({'tracer':(('time','x'),coarse[5])},coords={'time':coarse[6],'x':coarse[1]},
                  attrs={'data_role':'scenario','synthetic':'true','event_reconstruction':'false',
                         'description':'Passive scalar advection I/O test; no geographic CRS, hazard rheology or event parameters.'})
    ds['time'].attrs={'units':'s','long_name':'synthetic elapsed time'}
    ds['x'].attrs={'units':'m','long_name':'synthetic Cartesian x; not a river distance'}
    ds['tracer'].attrs={'units':'1','long_name':'dimensionless synthetic passive scalar'}
    path=Q/'results/synthetic_advection_frames.nc'; started=perf_counter(); ds.to_netcdf(path,engine='h5netcdf')
    with xr.open_dataset(path,engine='h5netcdf',decode_times=False,decode_timedelta=False) as reread:
        np.testing.assert_array_equal(reread.tracer.values,coarse[5]); np.testing.assert_array_equal(reread.x.values,coarse[1])
        assert reread.attrs['synthetic']=='true' and reread.tracer.attrs['units']=='1'
    io_seconds=perf_counter()-started
    summary={'data_role':'scenario','synthetic':True,'equation':settings['equation'],'settings':settings,
             'runs':[r[0] for r in runs], 'exact_shift_courant_one':shift[0],
             'invalid_courant_rejected':rejected,'grid_refinement_l1_error_decreases':True,
             'netcdf_roundtrip_exact':True,'netcdf_io_seconds':io_seconds,'output_frames':len(coarse[6]),
             'physical_event_validation_performed':False,
             'interpretation':'Finite-volume scalar integral/positivity/grid organisation/I-O test only; not debris-flow dynamics or event arrival.'}
    save(Q/'results/synthetic_numerics.json',summary)
    table(Q/'results/synthetic_grid_checks.csv',[r[0] for r in runs])
    fig,axs=plt.subplots(1,2,figsize=(12,4.5))
    axs[0].plot(coarse[1],coarse[2],color='#999999',linestyle='--',label='Initial scalar')
    axs[0].plot(coarse[1],coarse[4],color='black',label='Exact translated scalar')
    for r in runs: axs[0].plot(r[1],r[3],label=f"Upwind N={r[0]['cells']}")
    axs[0].set(title='SYNTHETIC passive scalar at t=300 s',xlabel='Synthetic Cartesian x (m)',ylabel='Dimensionless tracer')
    axs[0].legend(fontsize=8)
    axs[1].loglog([r[0]['dx_m'] for r in runs],errors,'o-',color='#406985')
    axs[1].set(title='SYNTHETIC grid-refinement check',xlabel='Grid spacing (m)',ylabel='Relative L1 error')
    axs[1].grid(alpha=.25)
    fig.suptitle('Technical numerical environment check; no hazard model or event parameters',fontsize=13)
    fig.tight_layout(rect=(0,0,1,.92));fig.savefig(Q/'figures/synthetic_numerics.png',dpi=160);plt.close(fig)
    return summary


def main():
    readiness()
    for folder in ('results','figures','sources'): (Q/folder).mkdir(exist_ok=True)
    config_path=Q/'config/feasibility.json'; config=json.loads(config_path.read_text())
    terrain_result=terrain(); synthetic_result=synthetic(config)
    manifest=ROOT/'track_b/audit/stage4/baseline_manifest.json'
    result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'experiment_id':config['experiment_id'],
            'event_id':config['event_id'],'physical_phase':'propagation_feasibility_only','time_utc':None,'time_uncertainty':None,
            'space_object':{'crs':'EPSG:32645','parameter_mask_is_event_source':False,
                            'source_area':None,'channel':None,'target_site':None},
            'variable_semantics':{'terrain':'m, unverified vertical datum; no correction','synthetic_tracer':'dimensionless'},
            'available_time':None,'forecast_reference_time':None,'issue_time':None,'valid_time':None,
            'data_role':'exploration','evidence_status':'local_fact',
            'input_version':{'common_baseline_commit':config['common_baseline_commit'],'manifest_sha256':digest(manifest),
                             'config_sha256':digest(config_path),'script_sha256':digest(Path(__file__))},
            'technical_checks':{'same_grid':terrain_result['same_grid_verified'],
                                'nc_mask_has_independent_dem_support':terrain_result['nc_positive_mask_covered_by_independent_dem'],
                                'resampling_diagnostic_geotiff_roundtrip':True,
                                'synthetic_conservation_positivity_refinement_and_netcdf':True},
            'source_to_port_continuity_verified':False,'event_reconstruction_performed':False,
            'synthetic_cases_are_independent_events':False,'human_core_model_selection':'pending'}
    save(Q/'results/run_summary.json',result)
    print(json.dumps({'technical_checks':result['technical_checks'],
                      'mask_dem_difference_m':terrain_result['difference_independent_minus_nc_m']['positive_parameter_mask'],
                      'synthetic_relative_l1_errors':[x['relative_l1_error'] for x in synthetic_result['runs']],
                      'source_to_port_continuity_verified':False},ensure_ascii=False))


if __name__=='__main__':
    main()
