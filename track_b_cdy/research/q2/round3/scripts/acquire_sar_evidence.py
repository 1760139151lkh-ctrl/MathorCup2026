#!/usr/bin/env python3
"""Public ITS_LIVE bounded acquisition and offline pixel review; no credentials."""
import argparse, csv, hashlib, json, math, os, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import requests
ROOT=Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2')
BASE=ROOT/'track_b/research/q2/round3'
SOURCES=BASE/'sources/sar'
CACHE=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q2/sar_v1')
RESULTS=BASE/'results'
def sha(b): return hashlib.sha256(b).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def save_json(p,d): p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def fetch(url,name,params=None,cap=20*1024*1024,to_cache=False):
    """Record consumed bytes; bounded stream, no credential/env inheritance/retry."""
    dest=(CACHE if to_cache else SOURCES)/name
    record_path=SOURCES/(name+'.request.json')
    if dest.exists() and record_path.exists():
        rec=json.loads(record_path.read_text())
        if rec['sha256']!=sha(dest.read_bytes()): raise ValueError('immutable cache mismatch')
        return dest,rec
    sess=requests.Session(); sess.trust_env=False
    start=utc()
    rec={'requested_url':url,'params':params,'retrieved_at_utc':start,'method':'GET','authentication':'anonymous; trust_env=False','scope':'explicit response body, not HTTP/TLS overhead','byte_cap':cap}
    body=bytearray()
    try:
        with sess.get(url,params=params,stream=True,timeout=(15,120),allow_redirects=True) as r:
            rec.update({'effective_url':r.url,'http_status':r.status_code,'content_type':r.headers.get('Content-Type'),'last_modified':r.headers.get('Last-Modified'),'etag':r.headers.get('ETag')})
            if r.headers.get('Content-Length') and int(r.headers['Content-Length'])>cap: raise ValueError('Content-Length exceeds predeclared response cap')
            for chunk in r.iter_content(65536):
                if len(body)+len(chunk)>cap: raise ValueError('response exceeds cap')
                body.extend(chunk)
    except Exception as e: rec['exception']=str(e)
    rec.update({'completed_at_utc':utc(),'bytes_consumed':len(body),'sha256':sha(body),'path':str(dest),'available_time':None,'available_time_note':'Retrieval and Last-Modified do not establish historical publication availability.'})
    dest.write_bytes(body); save_json(record_path,rec)
    return dest,rec

def search():
    params={'bbox':'85.50,28.27,85.54,28.31','start':'2026-07-01','end':'2026-10-01','percent_valid_pixels':1,'min_interval':6,'max_interval':48,'version':2}
    p,r=fetch('https://nsidc.org/apps/itslive-search/velocities/urls/','itslive_query_event_2026.json',params)
    print(json.dumps(r)); print(p.read_text()[:1000])
    params.update({'start':'2024-07-01','end':'2024-10-01'})
    p,r=fetch('https://nsidc.org/apps/itslive-search/velocities/urls/','itslive_query_background_2024.json',params)
    print(json.dumps(r)); print(p.read_text()[:1000])
    p,r=fetch('https://its-live-data.s3.amazonaws.com/datacubes/catalog_v02.json','catalog_v02.json',cap=16*1024*1024,to_cache=True)
    print(json.dumps(r))

def online():
    search()
    queries=[
      ('itslive_official_index.html','https://its-live.jpl.nasa.gov/itslive-web/index.xml',None),
      ('itslive_2025_paper.html','https://tc.copernicus.org/articles/19/3517/2025/tc-19-3517-2025.html',None),
      ('itslive_stac_event.json','https://stac.itslive.cloud/search',{'collections':'itslive-granules','bbox':'85.50,28.27,85.54,28.31','datetime':'2026-07-01T00:00:00Z/2026-10-01T00:00:00Z','limit':100}),
      ('itslive_stac_background.json','https://stac.itslive.cloud/search',{'collections':'itslive-granules','bbox':'85.50,28.27,85.54,28.31','datetime':'2024-07-01T00:00:00Z/2024-10-01T00:00:00Z','limit':100}),
      ('itslive_stac_event_bracket.json','https://stac.itslive.cloud/search',{'collections':'itslive-granules','bbox':'85.50,28.27,85.54,28.31','datetime':'2026-08-15T00:00:00Z/2026-09-01T23:59:59Z','limit':200,'filter-lang':'cql2-text','filter':"platform='S1D' AND date_dt <= 24"})]
    for name,url,params in queries:
        fetch(url,name,params,cap=2*1024*1024)
    selections=json.loads((SOURCES/'selected_sar_pairs.json').read_text())['selected']
    for s in selections:
        fetch(s['feature']['assets']['data']['href'],f"itslive_s1d_{s['role']}.nc",cap=256*1024*1024,to_cache=True)

def safe(o):
    if isinstance(o,np.ndarray): return o.tolist()
    if isinstance(o,np.generic): return o.item()
    if isinstance(o,dict): return {k:safe(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return [safe(v) for v in o]
    return o

def write_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def stats(v):
    a=np.asarray(v,dtype=float);a=a[np.isfinite(a)]
    return None if not len(a) else {'n':int(len(a)),'p10':float(np.percentile(a,10)),'median':float(np.median(a)),'p90':float(np.percentile(a,90))}

def analyze():
    """Entirely offline: read real cached NC pixels, not catalogue proxies."""
    import xarray as xr
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform
    import shapely
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    plt.rcParams.update({'font.size':9,'figure.dpi':120})
    aoi_path=ROOT/'track_b/research/q2/round2/inputs/search_aoi.geojson'
    expected='14db392ea6d318c2df34152af950b227653fd1f938aed1f4aa9eedf92c29579f'
    assert sha(aoi_path.read_bytes())==expected
    geo=json.loads(aoi_path.read_text())
    geom=shape(geo['features'][0]['geometry']) if geo['type']=='FeatureCollection' else shape(geo.get('geometry',geo))
    project=Transformer.from_crs(4326,32645,always_xy=True)
    geom=transform(project.transform,geom)
    cx,cy=project.transform(85.52525662048475,28.28784980517179)
    selection=json.loads((SOURCES/'selected_sar_pairs.json').read_text())['selected']
    summaries=[];metadata=[];arrays={};pixel_rows=[];outputs=[]
    figure,axes=plt.subplots(2,3,figsize=(13,8),sharex=True,sharey=True,layout='constrained')
    for col,s in enumerate(selection):
        role=s['role'];path=CACHE/f'itslive_s1d_{role}.nc';rec=json.loads((SOURCES/(path.name+'.request.json')).read_text())
        assert rec['http_status']==200 and 'exception' not in rec and rec['sha256']==sha(path.read_bytes())
        with xr.open_dataset(path,engine='h5netcdf',mask_and_scale=False) as raw:
            assert int(raw.mapping.attrs['spatial_epsg'])==32645
            assert raw.attrs['scene_pair_type']=='radar'
            assert raw.img_pair_info.attrs['flight_direction_img1']=='descending'
            assert raw.img_pair_info.attrs['flight_direction_img2']=='descending'
            assert raw.img_pair_info.attrs['id_img1']==s['feature']['properties']['scene_1_id']
            assert raw.img_pair_info.attrs['id_img2']==s['feature']['properties']['scene_2_id']
            meta={'role':role,'product_id':s['feature']['id'],'source_file':str(path),'source_sha256':rec['sha256'],'attributes':safe(dict(raw.attrs)),'image_pair_attributes':safe(dict(raw.img_pair_info.attrs)),'variable_attributes':{v:safe(dict(raw[v].attrs)) for v in raw.variables},'stac_properties':s['feature']['properties']}
            metadata.append(meta)
            west,south,east,north=geom.bounds
            subset=raw.sel(x=slice(west-120,east+120),y=slice(north+120,south-120))
            # Preserve raw flags and fill values in a small, hash-addressed local subset.
            keep=['mapping','img_pair_info','vx','vy','v','v_error','vr','va','chip_size_width','chip_size_height','interp_mask']
            subset=subset[keep].load()
            crop=SOURCES/f'derived_{role}_search.nc'
            encoding={v:{'zlib':True,'complevel':2} for v in keep if subset[v].ndim>=2}
            subset.to_netcdf(crop,engine='h5netcdf',encoding=encoding)
            outputs.append(crop)
        X,Y=np.meshgrid(subset.x.values,subset.y.values)
        in_aoi=shapely.contains_xy(geom,X,Y)
        window=(np.abs(X-cx)<=1500)&(np.abs(Y-cy)<=1500)
        data={v:np.squeeze(subset[v].values).astype(float) for v in ['vx','vy','v','v_error','vr','va','chip_size_width','chip_size_height','interp_mask']}
        valid=np.isfinite(data['v'])&(data['v']!=subset.v.attrs['_FillValue'])
        for v in ['vx','vy','v_error','vr','va']:
            data[v][data[v]==subset[v].attrs.get('_FillValue',-999999)]=np.nan
        data['v'][~valid]=np.nan
        assert np.isfinite(data['vx'][valid]).all() and np.isfinite(data['vy'][valid]).all()
        assert np.isfinite(data['v_error'][valid]).all()
        assert set(np.unique(data['interp_mask'])).issubset({0.,1.})
        # raw flag 0 equals _FillValue; do not use default decoded NaNs as evidence of absent measurements.
        interpolated=(data['interp_mask']==1)&valid
        raw_zero=(data['interp_mask']==0)&valid
        for region,mask in [('approved_search_aoi',in_aoi),('candidate_symbol_pm1500m_square',window)]:
            m=mask&valid
            row={'role':role,'region':region,'grid_cells':int(mask.sum()),'valid_velocity_cells':int(m.sum()),'valid_fraction':float(m.sum()/mask.sum()),'raw_interp0_valid_cells':int((mask&raw_zero).sum()),'raw_interp1_valid_cells':int((mask&interpolated).sum()),'v_median_m_year':float(np.nanmedian(data['v'][m])),'v_p10_m_year':float(np.nanpercentile(data['v'][m],10)),'v_p90_m_year':float(np.nanpercentile(data['v'][m],90)),'v_error_median_m_year':float(np.nanmedian(data['v_error'][m])),'error_le50_valid_cells':int((m&(data['v_error']<=50)).sum()),'vx_median_m_year':float(np.nanmedian(data['vx'][m])),'vy_median_m_year':float(np.nanmedian(data['vy'][m])),'chip_width_median_m':float(np.nanmedian(data['chip_size_width'][m])),'chip_height_median_m':float(np.nanmedian(data['chip_size_height'][m])),'start_utc':s['feature']['properties']['start_datetime'],'end_utc':s['feature']['properties']['end_datetime'],'product_id':s['feature']['id'],'evidence_tier':'local_regional_real_measurement_search_only','data_role':'exploration','event_id':'B20260826_Chhochen','independent_event_count_increment':0}
            summaries.append(row)
        local=subset.sel(x=slice(cx-1500,cx+1500),y=slice(cy+1500,cy-1500))
        local_data={v:np.squeeze(local[v].values).astype(float) for v in data}
        for v in ['v','vx','vy','v_error','vr','va']:
            local_data[v][local_data[v]==local[v].attrs.get('_FillValue',-999999)]=np.nan
        local_valid=np.isfinite(local_data['v'])
        arrays[role]={'data':local_data,'valid':local_valid,'x':local.x.values,'y':local.y.values,'vx_error':float(subset.vx.attrs['error']),'vy_error':float(subset.vy.attrs['error'])}
        for iy,y in enumerate(local.y.values):
            for ix,x in enumerate(local.x.values):
                pixel_rows.append({'role':role,'x_epsg32645':float(x),'y_epsg32645':float(y),'valid_velocity':bool(local_valid[iy,ix]),'vx_m_year':None if not np.isfinite(local_data['vx'][iy,ix]) else float(local_data['vx'][iy,ix]),'vy_m_year':None if not np.isfinite(local_data['vy'][iy,ix]) else float(local_data['vy'][iy,ix]),'v_m_year':None if not np.isfinite(local_data['v'][iy,ix]) else float(local_data['v'][iy,ix]),'v_error_m_year':None if not np.isfinite(local_data['v_error'][iy,ix]) else float(local_data['v_error'][iy,ix]),'interp_mask_raw':int(local_data['interp_mask'][iy,ix]),'interp0_fillvalue_conflict':True})
        extent=[(local.x.values[0]-cx-60)/1000,(local.x.values[-1]-cx+60)/1000,(local.y.values[-1]-cy-60)/1000,(local.y.values[0]-cy+60)/1000]
        for j,(variable,vmax) in enumerate([('v',120),('v_error',120)]):
            ax=axes[j,col]; vals=local_data[variable].copy(); vals[~local_valid]=np.nan
            im=ax.imshow(vals,extent=extent,origin='upper',vmin=0,vmax=vmax,cmap='viridis')
            ax.plot(0,0,'r+',markersize=12);ax.set_facecolor('#d8d8d8');ax.set_aspect('equal')
            if j==0: ax.set_title(f"{role}: {s['feature']['properties']['start_datetime'][5:10]} to {s['feature']['properties']['end_datetime'][5:10]} UTC")
            if col==0: ax.set_ylabel(('Speed [m/year]' if j==0 else 'Product error [m/year]')+'\nNorth offset [km]')
            if j==1: ax.set_xlabel('East offset from map symbol [km]')
            figure.colorbar(im,ax=ax,shrink=.75,label='m/year',extend='max')
    figure.suptitle('2026 real SAR feature-tracking pixels near candidate map symbol (search only)\n120 m grid; gray=missing velocity; red+=uncertain map symbol; no causal inference',fontsize=12)
    fig_path=RESULTS/'sar_evidence_pixels.png';figure.savefig(fig_path);plt.close(figure);outputs.append(fig_path)
    comparison=[]
    common=arrays['pre']['valid']&arrays['straddle']['valid']&arrays['post']['valid']
    for a,b in [('pre','straddle'),('straddle','post'),('pre','post')]:
        aa,bb=arrays[a],arrays[b]
        assert np.array_equal(aa['x'],bb['x']) and np.array_equal(aa['y'],bb['y'])
        mask=aa['valid']&bb['valid']; mask_raw0=mask&(aa['data']['interp_mask']==0)&(bb['data']['interp_mask']==0)
        for support,m in [('pairwise_valid',mask),('three_pair_common_valid',common),('pairwise_raw_flag0_with_fill_conflict',mask_raw0)]:
            dx=bb['data']['vx'][m]-aa['data']['vx'][m];dy=bb['data']['vy'][m]-aa['data']['vy'][m]
            comparison.append({'earlier':a,'later':b,'support':support,'grid_cells':int(m.sum()),'delta_vx_median_m_year':float(np.median(dx)),'delta_vy_median_m_year':float(np.median(dy)),'delta_v_median_m_year':float(np.median(bb['data']['v'][m]-aa['data']['v'][m])),'nominal_vx_error_rss_m_year':float(np.hypot(aa['vx_error'],bb['vx_error'])),'nominal_vy_error_rss_m_year':float(np.hypot(aa['vy_error'],bb['vy_error'])),'error_rss_is_statistical_test':False,'shared_image_correlation_unknown':True,'interpretation':'descriptive, spatially correlated pixels; no acceleration significance or causal attribution'})
    summary_path=RESULTS/'sar_evidence_summary.csv';write_csv(summary_path,summaries);outputs.append(summary_path)
    pixel_path=RESULTS/'sar_evidence_source_window_pixels.csv';write_csv(pixel_path,pixel_rows);outputs.append(pixel_path)
    comparison_path=RESULTS/'sar_evidence_pair_comparison.csv';write_csv(comparison_path,comparison);outputs.append(comparison_path)
    attrs_path=RESULTS/'sar_evidence_product_attributes.json';save_json(attrs_path,metadata);outputs.append(attrs_path)
    requests_records=[json.loads(p.read_text()) for p in sorted(SOURCES.glob('*.request.json'))]
    for rec in requests_records:
        p=Path(rec['path']);assert p.exists() and sha(p.read_bytes())==rec['sha256']
    register={'version':'q2-r3-sar-v1','generated_at_utc':utc(),'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','event_id':'B20260826_Chhochen','physical_phase':'background_and_interval_surface_motion','data_role':'exploration','evidence_status':'local_fact_product_pixel_values; event source identity/causality unverified','available_time':None,'available_time_note':'NetCDF date_created / STAC created retained as production metadata, not certified first public availability. No real-time hindcast availability acceptance.','input_version':{'approved_search_aoi_path':str(aoi_path),'sha256':expected,'geometry_version':'q4-r2-fig1-search-v1','scope':'search only; no source boundary acceptance'},'requests':requests_records,'sar_nc_bytes':sum(r['bytes_consumed'] for r in requests_records if r['path'].endswith('.nc')),'all_recorded_http_body_bytes':sum(r['bytes_consumed'] for r in requests_records),'read_scope':{'source_nc':'All objects acquired; offline pixel reads limited to search AOI bounding rectangle plus120m and candidate symbol +/-1500m square, selected velocity/error/chip/mask fields. Scalar and coordinate metadata read.','actual_pixel_rows':len(pixel_rows),'three_pair_common_valid_source_window_cells':int(common.sum()),'no_sar_grd_amplitude_or_slc_phase_read':True,'source_material':'Radar autoRIFT offset/feature tracking L2 surface velocity, not raw SLC phase/InSAR.'},'source_reading':{'itslive_official_index.html':'Data Access STAC API and Global Image-pair Velocities sections','itslive_2025_paper.html':'Sections3.1.2 SAR processing,3.1.3 velocity uncertainty,4.1 limitations, plus infrastructure/matching paragraphs. HTML text; no claim of manual source-figure QA.','stac_responses':'Actual selected features and acquisition start/end, orbit state, product/asset URLs; broad first pages are not complete historical inventories.','catalog':'Catalogue feature containing candidate symbol; full catalogue only parsed for geometry selection, no pixels inferred.'},'limitations':['Original figure geolocation uncertainty unknown; +/-1500m is sensitivity search window, not release polygon/confidence region.','120m posting; chip footprints may be larger; not native30m strain/crack monitoring.','Raw interp_mask flag0 equals _FillValue0. Default CF decoding masks zeros; preserve raw0 separately and do not certify measured status from missing decoded mask.','Per-product bias correction metadata not independent local registration validation. No independently surveyed stable controls, DEM-based layover/shadow mask or SAR co-registration/coherence inspection.','Velocity errors are product estimates, not guaranteed95% pixel intervals. Spatially correlated pixels and shared scene pairs prevent naive significance tests.','A 12-day interval velocity spanning event cannot establish first initiation time or distinguish temperature from water mechanisms.'],'outputs':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes()),'role':'derived_real_sar_pixel_evidence'} for p in outputs]}
    save_json(RESULTS/'sar_evidence_register.json',register)
    print(json.dumps({'sar_nc_bytes':register['sar_nc_bytes'],'source_window_rows':len(pixel_rows),'common_valid':int(common.sum()),'region_stats':summaries,'comparison':comparison},ensure_ascii=False))

def main():
    if Path.cwd().resolve()!=ROOT: raise RuntimeError('explicit execution root required')
    SOURCES.mkdir(parents=True,exist_ok=True); CACHE.mkdir(parents=True,exist_ok=True)
    ap=argparse.ArgumentParser(); ap.add_argument('--search',action='store_true'); ap.add_argument('--online',action='store_true'); ap.add_argument('--offline',action='store_true'); ap.add_argument('--download-url'); ap.add_argument('--filename'); args=ap.parse_args()
    if args.search: search()
    if args.online: online()
    if args.offline or (not args.search and not args.download_url and not args.online): analyze()
    if args.download_url:
        p,r=fetch(args.download_url,args.filename,cap=256*1024*1024,to_cache=True)
        print(json.dumps(r))
if __name__=='__main__': main()
