#!/usr/bin/env python3
"""Prepare immutable official-solver cases in q4/official cache, no runtime writes."""
from pathlib import Path
import argparse,json,hashlib,datetime,math,shutil
import numpy as np,rasterio
from rasterio.warp import reproject,Resampling
from rasterio.transform import from_origin
from rasterio.features import rasterize
from shapely.geometry import shape,mapping
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parents[1]
CACHE=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--dem',required=True);a.add_argument('--geometry',required=True);a.add_argument('--terrain-id',default='legacy');a.add_argument('--resolutions',default='120,60');args=a.parse_args()
 g=json.loads(Path(args.geometry).read_text()); feats=g.get('features',[]);src=next(f for f in feats if f['geometry']['type'] in ('Polygon','MultiPolygon') and 'source' in str(f.get('properties',{})).lower())
 source=shape(src['geometry']); crs=g.get('crs',{}).get('properties',{}).get('name','EPSG:4326')
 if '32645' not in crs:source=transform(Transformer.from_crs(crs,'EPSG:32645',always_xy=True).transform,source)
 targets=[]
 for f in feats:
  if f['geometry']['type']=='Point':
   q=shape(f['geometry']);q=q if '32645' in crs else transform(Transformer.from_crs(crs,'EPSG:32645',always_xy=True).transform,q)
   targets.append({'id':f.get('properties',{}).get('object_id',f.get('properties',{}).get('geometry_id',f.get('id','point'))),'xy':[q.x,q.y],'buffer_m':100,'candidate':True})
 # bounds encompass candidate source/target paths with1km buffer, clipped to actual supplied terrain
 allgeoms=[source]
 for f in feats:
  q=shape(f['geometry']);q=q if '32645' in crs else transform(Transformer.from_crs(crs,'EPSG:32645',always_xy=True).transform,q);allgeoms.append(q)
 from shapely.ops import unary_union
 bounds=unary_union(allgeoms).buffer(1000).bounds
 cases=[]
 for dx in [int(x) for x in args.resolutions.split(',')]:
  dest=CACHE/'inputs'/f'{args.terrain_id}_{dx}m';dest.mkdir(parents=True,exist_ok=True)
  shared=np.load(P/'results'/f'spatial_inputs_{dx}m.npz')
  z=shared['z'];h,w=z.shape;dx=float(shared['dx']);x=shared['x'];y=shared['y'];l=float(x[0]-dx/2);t=float(y[0]+dx/2);r=l+w*dx;b=t-h*dx;tr=from_origin(l,t,dx,dx)
  if np.any(~np.isfinite(z)):raise ValueError('Nonfinite supplied shared terrain')
  reference=np.load(P/'results'/'spatial_inputs_60m.npz');reference_area=float(reference['source_mask'].sum()*3600)
  binary=shared['source_mask'].astype(float);rawarea=float(binary.sum()*dx*dx)
  frac=binary*(reference_area/rawarea)
  def tif(name,data):
   p=dest/name
   with rasterio.open(p,'w',driver='GTiff',width=w,height=h,count=1,dtype='float32',transform=tr,crs='EPSG:32645',nodata=-9999,compress='deflate') as out:out.write(np.asarray(data,np.float32),1)
   return p
  dem=tif('dem.tif',z)
  rels={th:tif(f'release_{th}m.tif',frac*th) for th in [5,15,30,136]}
  suite=[('single_ref','ravaflow_single',15,.15,1000,[1],{}),('multi_ref','ravaflow_multi',15,.15,1000,[.6,.1,.3],{}),('multi_dry','ravaflow_multi',15,.15,1000,[.8,.1,.1],{}),('multi_wet','ravaflow_multi',15,.15,1000,[.4,.1,.5],{}),('multi_nodrag','ravaflow_multi',15,.15,1000,[.6,.1,.3],{'drag':'-1,3,1,0.1,1,1','virtualmass':'1,0,0'}),('dclaw_ref','dclaw',15,.15,None,[.63,.37],{'init_ptype':0,'m0':.63,'kref':1e-10}),('dclaw_nopressure','dclaw',15,.15,None,[.63,.37],{'init_ptype':-1,'m0':.63,'kref':1e-10}),('dclaw_loose','dclaw',15,.15,None,[.55,.45],{'init_ptype':0,'m0':.55,'kref':1e-10}),('dclaw_permeable','dclaw',15,.15,None,[.63,.37],{'init_ptype':0,'m0':.63,'kref':1e-8})]
  if dx==120:
   suite += [('single_h136','ravaflow_single',136,.15,1000,[1],{})]
   suite += [(f'single_h{th}','ravaflow_single',th,.15,1000,[1],{}) for th in [5,30]]
   suite += [(f'single_mu{mu}','ravaflow_single',15,mu,1000,[1],{}) for mu in [.08,.25]]
   suite += [(f'single_xi{xi}','ravaflow_single',15,.15,xi,[1],{}) for xi in [500,2000]]
   suite += [('single_cfl025','ravaflow_single',15,.15,1000,[1],{'cfl':.25})]
  for name,model,th,mu,xi,fractions,extras in suite:
   runid=f'{args.terrain_id}_{int(dx)}_{name}'.replace('.','p');folder=CACHE/'runs'/runid;folder.mkdir(parents=True,exist_ok=True)
   case={'run_id':runid,'scenario_id':f'conditional_h{th}_mu{mu}_xi{xi}','model':model,'terrain_id':args.terrain_id,'resolution_m':dx,'dem':str(dem),'dem_sha256':sha(dem),'release':str(rels[th]),'release_sha256':sha(rels[th]),'source_geometry_sha256':sha(args.geometry),'source_exact_area_m2':source.area,'source_mask_cells':int(binary.sum()),'source_grid_area_m2':rawarea,'reference_source_grid_area_m2':reference_area,'grid_thickness_normalization_factor':reference_area/rawarea,'release_thickness_m':th,'release_grid_volume_m3':float(np.float64((frac*th).astype(np.float32)).sum()*dx*dx),'nominal_polygon_volume_m3':None,'expected_reference_grid_volume_m3':reference_area*th,'mu_basal':mu,'xi':xi,'phase_volume_fractions':fractions,'initial_velocity_east_north_m_s':[0,0],'initiation_to_release_delay_seconds':None,'end_seconds':1800,'output_interval_seconds':20,'targets':targets,'extras':extras,'evidence_role':'conditional_scenario','model_adoption':'pending_team_review'}
   (folder/'case.json').write_text(json.dumps(case,indent=2)+'\n');cases.append({'run_id':runid,'case':str(folder/'case.json')})
 (P/'config'/f'official_cases_{args.terrain_id}.json').write_text(json.dumps({'prepared_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_dem':{'path':args.dem,'sha256':sha(args.dem)},'geometry':{'path':args.geometry,'sha256':sha(args.geometry)},'cases':cases},indent=2)+'\n')
 print(json.dumps({'terrain':args.terrain_id,'cases':len(cases),'source_area_m2':source.area,'targets':targets}))
if __name__=='__main__':main()
