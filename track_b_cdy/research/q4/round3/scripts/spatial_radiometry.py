from pathlib import Path
import json,hashlib,datetime
import rasterio,certifi,numpy as np
from rasterio.windows import from_bounds
R=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');rows=[];bounds=[345000,3134000,346000,3135000]
pairs=[('S2C_45RUM_20260812_0_L2A','S2C_T45RUM_20260812T050239_L2A'),('S2C_45RUM_20260928_0_L2A','S2C_T45RUM_20260928T045730_L2A')]
for leg,c1 in pairs:
 l=json.loads((C/(leg+'.json')).read_text());c=json.loads((C/(c1+'_c1.json')).read_text());assert l['properties']['s2:product_uri']==c['properties']['s2:product_uri']
 for band in ['red','nir']:
  cp=C/(c1+'_'+band+'_radiometry_sample.tif');url=c['assets'][band]['href'];now=datetime.datetime.now(datetime.UTC).isoformat()
  if not cp.exists():
   with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_TIMEOUT='45',GDAL_HTTP_CA_BUNDLE=certifi.where()):
    with rasterio.open(url) as ds:w=from_bounds(*bounds,transform=ds.transform).round_offsets().round_lengths();a=ds.read(1,window=w);prof=ds.profile.copy();prof.update(width=a.shape[1],height=a.shape[0],transform=ds.window_transform(w),compress='deflate')
   with rasterio.open(cp,'w',**prof) as ds:ds.write(a,1)
  with rasterio.open(cp) as ds:a=ds.read(1)
  with rasterio.open(C/(leg+'_'+band+'_crop.tif')) as ds:w=from_bounds(*bounds,transform=ds.transform).round_offsets().round_lengths();b=ds.read(1,window=w)
  mask=(a!=0)&(b!=0);diff=a[mask].astype(int)-b[mask].astype(int);cs=c['assets'][band]['raster:bands'][0];ls=l['assets'][band]['raster:bands'][0];dd=a[mask]*cs['scale']+cs['offset']-b[mask]*ls['scale']
  rows.append({'legacy_item':leg,'c1_item':c1,'product_uri_equal':True,'product_uri':l['properties']['s2:product_uri'],'band':band,'sample_bounds_utm45n':bounds,'sample_shape':list(a.shape),'valid_n':int(mask.sum()),'legacy_floor_DN1_pixels':int((b[mask]==1).sum()),'C1_minus_legacy_DN_nonfloor_unique':np.unique(diff[b[mask]>1]).tolist(),'C1_minus_legacy_DN_min':int(diff.min()),'C1_minus_legacy_DN_max':int(diff.max()),'reflectance_C1_scaled_offset_minus_legacy_scaled_max_abs':float(np.abs(dd).max()),'max_abs_nonfloor_reflectance_residual':float(np.abs(dd[b[mask]>1]).max()),'legacy_item_boa_offset_applied':l['properties']['earthsearch:boa_offset_applied'],'legacy_declared_band_offset':ls['offset'],'legacy_effective_offset':0.0,'c1_declared_offset_used':cs['offset'],'C1_url':url,'read_at_utc':now,'retrieved_at_utc':datetime.datetime.fromtimestamp(cp.stat().st_mtime,datetime.UTC).isoformat(),'retrieval_time_basis':'derived cache file completion mtime from original write, not scene availability','derived_sample_path':str(cp),'derived_bytes':cp.stat().st_size,'derived_sha256':hashlib.sha256(cp.read_bytes()).hexdigest(),'actual_read_scope':'1km x 1km, 100x100 full-resolution pixels, identical product_uri; not whole-scene cross-validation','source_full_bytes':None,'source_full_sha256':None})
result={'version':'q4-r3-radiometric-QA-v1','provider_guidance':'https://github.com/Element84/earth-search/issues/41','test':'same product_uri; legacy adjusted DN compared with alternate C1 COG representation of same observation','results':rows,'conclusion':'Nonfloor legacy pixels use scale only: C1 raw DN minus legacy adjusted DN equals 1000; legacy DN1 floor pixels differ and are excluded from spectral screen; band offset -0.1 double application rejected','scope_limit':'4 band-window comparisons at one 1km-square terrain region; supports these two products conversion, not a global guarantee or local reflectance accuracy validation'}
(R/'results/spatial_radiometry_check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
