from pathlib import Path
import json,datetime,hashlib
import numpy as np,rasterio
from rasterio.windows import from_bounds,Window
from rasterio.features import rasterize
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
import certifi
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial'); B=json.loads((R/'results/terrain_bundle.json').read_text());bb=B['grids']['60']['bounds']; geo=json.loads((R/'results/computational_geometries.geojson').read_text());tr=Transformer.from_crs(4326,32645,always_xy=True)
src=transform(tr.transform,shape(next(f for f in geo['features'] if f['id']=='paper_source_outline')['geometry']));paths=[transform(tr.transform,shape(f['geometry'])) for f in geo['features'] if f['id'] in ['P1','P2','P3']]; records=[];rows=[];fig,axs=plt.subplots(1,3,figsize=(16,6));ids=['S2C_45RUM_20260812_0_L2A','S2B_45RUM_20260824_0_L2A','S2C_45RUM_20260928_0_L2A']
for ax,id in zip(axs,ids):
 item=json.loads((C/(id+'.json')).read_text());dt=item['properties']['datetime'];rgbpath=C/(id+'_visual_crop.tif');url=item['assets']['visual']['href']; now=datetime.datetime.now(datetime.UTC).isoformat()
 try:
  if not rgbpath.exists():
   local=C/(id+'_visual.tif');loc=str(local) if local.exists() else url
   with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_TIMEOUT='45',GDAL_HTTP_CA_BUNDLE=certifi.where()):
    with rasterio.open(loc) as ds:
     w=from_bounds(*bb,transform=ds.transform).round_offsets().round_lengths();rgb=ds.read(window=w);aff=ds.window_transform(w);profile=ds.profile.copy();profile.update(width=rgb.shape[2],height=rgb.shape[1],transform=aff,compress='deflate')
     with rasterio.open(rgbpath,'w',**profile) as dst:dst.write(rgb)
  with rasterio.open(rgbpath) as ds:rgb=ds.read();aff=ds.transform;extent=list(ds.bounds);resolution=ds.res
  rec={'item_id':id,'acquisition_time_utc':dt,'asset_url':url,'product_version':item['properties'].get('s2:processing_baseline'),'read_at_utc':now,'retrieved_at_utc':datetime.datetime.fromtimestamp(rgbpath.stat().st_mtime,datetime.UTC).isoformat(),'retrieval_time_basis':'derived cache file completion mtime from original write, not scene availability','actual_read_scope':{'type':'full-resolution TCI raster window','bounds_utm45n':bb,'derived_shape':list(rgb.shape),'note':'TCI visualization; no surface-reflectance quantitative change inference'},'derived_path':str(rgbpath),'derived_bytes':rgbpath.stat().st_size,'derived_sha256':hashlib.sha256(rgbpath.read_bytes()).hexdigest(),'source_object_complete_bytes':None,'source_object_complete_sha256':None,'null_reason':'source COG read by HTTP byte ranges unless full cached acquisition separately recorded','available_time':None}
  records.append(rec)
  sclpath=C/(id+'_scl.tif')
  if sclpath.exists():
   with rasterio.open(sclpath) as ds:
    w=from_bounds(*bb,transform=ds.transform).round_offsets().round_lengths();scl=ds.read(1,window=w);sa=ds.window_transform(w)
   sm=rasterize([(src,1)],out_shape=scl.shape,transform=sa,dtype='uint8').astype(bool);pm=rasterize([(p.buffer(250),1) for p in paths],out_shape=scl.shape,transform=sa,dtype='uint8').astype(bool)
   stats={}
   for name,m in [('aoi',np.ones(scl.shape,dtype=bool)),('paper_source',sm),('path_250m_corridor',pm)]:
    vals=scl[m];unique,n=np.unique(vals,return_counts=True);stats[name]={'n':int(len(vals)),'class_counts':{str(int(k)):int(v) for k,v in zip(unique,n)},'valid_observed_fraction':float((vals!=0).mean()),'configured_clear_land_water_snow_fraction':float(np.isin(vals,[4,5,6,11]).mean()),'snow_ice_11_fraction':float((vals==11).mean()),'configured_clear_excluding_snow_fraction':float(np.isin(vals,[4,5,6]).mean()),'unclassified_7_fraction':float((vals==7).mean()),'saturated_defective_1_fraction':float((vals==1).mean()),'topographic_dark_2_fraction':float((vals==2).mean()),'cloud_shadow_3_fraction':float((vals==3).mean()),'medium_high_cloud_8_9_fraction':float(np.isin(vals,[8,9]).mean()),'cirrus_10_fraction':float((vals==10).mean()),'dark_shadow_cloud_fraction':float(np.isin(vals,[2,3,8,9,10]).mean())}
   rows.append({'item_id':id,'observation_time_utc':dt,'tile_cloud_percent':item['properties'].get('eo:cloud_cover'),'quality':stats})
  ax.imshow(np.moveaxis(rgb,0,-1),extent=[extent[0],extent[2],extent[1],extent[3]]);ax.plot(*src.exterior.xy,c='red',lw=1)
  for p in paths:ax.plot(*p.xy,c='yellow',lw=.6,alpha=.6)
  ax.set_title(dt[:10]+' TCI pixels\nred=paper source; yellow=conditional paths');ax.ticklabel_format(style='plain');ax.set_xlabel('UTM45N easting (m)');ax.set_xticks([340000,350000]);ax.set_ylabel('northing (m)')
 except Exception as e:records.append({'item_id':id,'asset_url':url,'read_at_utc':now,'retrieved_at_utc':None,'exception':str(e)});ax.set_title(id+' access failed');print('FAIL',id,str(e),flush=True)
fig.tight_layout();fp=R/'figures/spatial_optical_candidates.png';fig.savefig(fp,dpi=160);plt.close(fig)
(R/'results/spatial_optical_quality.json').write_text(json.dumps({'schema_version':1,'TCI_is_visualization_not_reflectance':True,'scl_classes_configured_clear':[4,5,6,11],'scl_classes_dark_shadow_cloud':[2,3,8,9,10],'quality_acceptance_note':'SCL is algorithmic product classification; configured clear is not independent visual/registration accuracy validation; class7 kept unclassified','missing_SCL_quality':'NA; TCI availability alone does not imply pixel quality','scenes':rows},indent=2)+'\n')
(R/'sources/spatial_optical_reads.json').write_text(json.dumps({'reads':records},indent=2)+'\n');print(json.dumps(rows,indent=2))
