from pathlib import Path
import json,datetime,hashlib
import numpy as np,rasterio,certifi
from rasterio.windows import from_bounds
from rasterio.warp import reproject,Resampling
from rasterio.features import rasterize,shapes
from shapely.geometry import shape,mapping
from shapely.ops import transform
from pyproj import Transformer
from scipy.ndimage import label
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
R=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');cfg=json.loads((R/'config/spatial_spectral_protocol_v2.json').read_text());bb=json.loads((R/'results/terrain_bundle.json').read_text())['grids']['60']['bounds'];allbands=[];quality=[];records=[]
for id in [cfg['pre_scene'],cfg['post_scene']]:
 item=json.loads((C/(id+'.json')).read_text());bands=[]
 for band in ['red','nir']:
  asset=item['assets'][band];url=asset['href'];p=C/(id+'_'+band+'_crop.tif');now=datetime.datetime.now(datetime.UTC).isoformat()
  if not p.exists():
   with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_TIMEOUT='45',GDAL_HTTP_CA_BUNDLE=certifi.where()):
    with rasterio.open(url) as ds:
     win=from_bounds(*bb,transform=ds.transform).round_offsets().round_lengths();a=ds.read(1,window=win);aff=ds.window_transform(win);profile=ds.profile.copy();profile.update(width=a.shape[1],height=a.shape[0],transform=aff,compress='deflate')
     with rasterio.open(p,'w',**profile) as dest:dest.write(a,1)
  with rasterio.open(p) as ds:a=ds.read(1);aff=ds.transform
  spec=asset['raster:bands'][0];scale=spec['scale'];declared_offset=spec['offset'];offset=0.0 if item['properties'].get('earthsearch:boa_offset_applied') is True else declared_offset;bands.append((a.astype(float)*scale+offset,a>1))
  records.append({'item_id':id,'band':band,'url':url,'product_version':item['properties'].get('s2:processing_baseline'),'read_at_utc':now,'retrieved_at_utc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.UTC).isoformat(),'retrieval_time_basis':'derived cache file completion mtime from original write, not scene availability','actual_read_scope':{'type':'COG 10m raster window','bounds_utm45n':bb,'shape':list(a.shape)},'derived_path':str(p),'derived_bytes':p.stat().st_size,'derived_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_complete_sha256':None,'source_complete_bytes':None,'source_null_reason':'HTTP byte-range window, full source object not downloaded','scale':scale,'declared_offset':declared_offset,'effective_offset':offset,'earthsearch_boa_offset_applied':item['properties'].get('earthsearch:boa_offset_applied'),'available_time':None})
 red,rv=bands[0];nir,nv=bands[1];den=nir+red;ndvi=np.divide(nir-red,den,out=np.full_like(red,np.nan),where=np.abs(den)>1e-8);allbands.append(ndvi)
 scl=np.zeros_like(red,dtype='uint8')
 with rasterio.open(C/(id+'_scl.tif')) as ds:reproject(rasterio.band(ds,1),scl,src_transform=ds.transform,src_crs=ds.crs,dst_transform=aff,dst_crs='EPSG:32645',resampling=Resampling.nearest)
 quality.append(np.isin(scl,[4,5])&rv&nv&np.isfinite(ndvi))
pre,post=allbands;valid=quality[0]&quality[1];delta=post-pre
geo=json.loads((R/'results/computational_geometries.geojson').read_text());tr=Transformer.from_crs(4326,32645,always_xy=True);bt=Transformer.from_crs(32645,4326,always_xy=True);lines=[transform(tr.transform,shape(f['geometry'])) for f in geo['features'] if f['id'] in ['P1','P2','P3']];corr=rasterize([(l.buffer(250),1) for l in lines],out_shape=pre.shape,transform=aff,dtype='uint8').astype(bool);outer=rasterize([(l.buffer(1000),1) for l in lines],out_shape=pre.shape,transform=aff,dtype='uint8').astype(bool);inner=rasterize([(l.buffer(500),1) for l in lines],out_shape=pre.shape,transform=aff,dtype='uint8').astype(bool);control=outer&~inner
rows=[]
for threshold in cfg['sensitivity_deltaNDVI_thresholds']:
 change=valid&(pre>.4)&(post<.3)&(delta<threshold)
 for name,m in [('candidate_corridor_250m',corr),('control_annulus_500_1000m',control)]:
  v=valid&m;rows.append({'region':name,'delta_threshold':threshold,'region_pixels':int(m.sum()),'paired_usable_pixels':int(v.sum()),'paired_usable_area_m2':int(v.sum())*100,'candidate_change_pixels':int((change&m).sum()),'candidate_change_area_m2':int((change&m).sum())*100,'change_fraction_of_paired_usable':float((change&m).sum()/v.sum()) if v.sum() else None,'median_deltaNDVI_paired':float(np.median(delta[v])) if v.any() else None})
change=valid&(pre>.4)&(post<.3)&(delta<-.3);labels,n=label(change,structure=np.array([[0,1,0],[1,1,1],[0,1,0]]));counts=np.bincount(labels.ravel());kept=(counts>=9);kept[0]=False;change9=kept[labels];features=[]
maskpath=C/'q4-r3-spectral-screen-v2_masks.npz'
mask_arrays={'valid_pair':valid.astype(bool),'change_candidate':change.astype(bool),'change_candidate_ge9':change9.astype(bool),'affine':np.array(tuple(aff))[:6],'crs':np.array('EPSG:32645'),'geometry_version':np.array('q4-r3-spectral-screen-v2'),'pre_scene':np.array(cfg['pre_scene']),'post_scene':np.array(cfg['post_scene'])}
if maskpath.exists():
 with np.load(maskpath) as existing:
  for key,val in mask_arrays.items():np.testing.assert_array_equal(existing[key],val)
else:np.savez_compressed(maskpath,**mask_arrays)
(R/'results/spatial_spectral_mask_index.json').write_text(json.dumps({'version':'q4-r3-spectral-screen-v2','files':[{'path':str(maskpath),'bytes':maskpath.stat().st_size,'sha256':hashlib.sha256(maskpath.read_bytes()).hexdigest(),'role':'exploratory paired spectral masks; not accepted event footprint'}],'schema':{'valid_pair':'bool HxW: both SCL4/5, DN>1 and finite NDVI','change_candidate':'bool HxW: valid_pair, preNDVI>0.4 postNDVI<0.3 delta<-0.3','change_candidate_ge9':'bool HxW: change_candidate retained 4-neighbor components>=9pixels','affine':'6 floats [a,b,c,d,e,f], x=a*col+b*row+c y=d*col+e*row+f','crs':'scalar EPSG:32645; rows north-to-south','geometry_version':'scalar q4-r3-spectral-screen-v2','pre_scene':'scalar scene ID','post_scene':'scalar scene ID'},'shape':list(valid.shape),'resolution_m':10,'data_role':'exploration','evaluation_stratum':'local_observational','observation_role':'exploratory spectral proxy, not accepted event footprint','limitations':cfg['attribution_limits']+['Spatial agreement measured only on valid_pair; masked/unobservable pixels are not negative observations','Centerline and structure duplicates are not independent targets; repeated pixels are not independent events','For comparison, reproject model inundation to this 10m grid with nearest; this adds no model resolution, record 60m/120m support']},indent=2)+'\n')

for g,v in shapes(change9.astype('uint8'),mask=change9,transform=aff):
 poly=shape(g);features.append({'type':'Feature','properties':{'geometry_version':'q4-r3-spectral-screen-v2','object_kind':'exploratory_vegetation_change_candidate','pre_scene':cfg['pre_scene'],'post_scene':cfg['post_scene'],'accepted_event_footprint':False,'area_m2_utm45n':poly.area,'positional_uncertainty_m':None,'data_role':'exploration'},'geometry':mapping(transform(bt.transform,poly))})
(R/'results/spatial_spectral_change_candidates.geojson').write_text(json.dumps({'type':'FeatureCollection','name':'q4-r3-spectral-screen-v2','features':features},indent=2)+'\n')
out={'version':'q4-r3-spectral-screen-v2','protocol':cfg,'rows':rows,'connected_candidate_components_ge9pixels':len(features),'radiometric_QA':{'policy':'legacy boa_offset_applied true => scale only; C1 pixel spot-check separate','pre_paired_NDVI_min':float(np.min(pre[valid])),'pre_paired_NDVI_max':float(np.max(pre[valid])),'post_paired_NDVI_min':float(np.min(post[valid])),'post_paired_NDVI_max':float(np.max(post[valid]))},'paired_usable_total_pixels':int(valid.sum()),'limits':cfg['attribution_limits']};(R/'results/spatial_spectral_screen.json').write_text(json.dumps(out,indent=2)+'\n');(R/'sources/spatial_spectral_reads.json').write_text(json.dumps({'reads':records},indent=2)+'\n')
fig,axs=plt.subplots(1,3,figsize=(16,6));extent=[bb[0],bb[2],bb[1],bb[3]]
for ax,a,title in [(axs[0],np.where(quality[0],pre,np.nan),'08-12 NDVI; SCL4/5 only'),(axs[1],np.where(quality[1],post,np.nan),'09-28 NDVI; SCL4/5 only')]:
 im=ax.imshow(a,extent=extent,vmin=0,vmax=.9,cmap='YlGn');fig.colorbar(im,ax=ax,fraction=.03);ax.set_title(title)
im=axs[2].imshow(np.where(valid,delta,np.nan),extent=extent,vmin=-.6,vmax=.6,cmap='RdYlGn');fig.colorbar(im,ax=axs[2],fraction=.03,label='post - pre NDVI');axs[2].contour(np.linspace(bb[0]+5,bb[2]-5,change9.shape[1]),np.linspace(bb[3]-5,bb[1]+5,change9.shape[0]),change9.astype(float),levels=[.5],colors='purple',linewidths=.25);axs[2].set_title('Paired NDVI difference / change candidates\nNot an accepted event inundation footprint')
for ax in axs:
 for l in lines:ax.plot(*l.xy,c='black',lw=.5,alpha=.5)
 ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.0f}'));ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.0f}'));ax.set_xlabel('UTM45N easting (km)');ax.set_ylabel('northing (km)')
fig.tight_layout();fig.savefig(R/'figures/spatial_spectral_screen.png',dpi=180);plt.close(fig);print(json.dumps(out,indent=2))
