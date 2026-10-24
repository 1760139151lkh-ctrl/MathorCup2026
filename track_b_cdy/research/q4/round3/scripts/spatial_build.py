from pathlib import Path
import json,hashlib,datetime,csv,math,argparse
import numpy as np,rasterio
from rasterio.warp import reproject,Resampling
from rasterio.transform import from_origin
from rasterio.features import rasterize
from pyproj import Transformer
from shapely.geometry import shape,mapping,LineString,Point
from shapely.ops import transform
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.ndimage import distance_transform_edt
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];W=R.parents[4];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');C.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--output-root');args=parser.parse_args()
if args.output_root:
 newroot=Path(args.output_root).resolve()
 if not newroot.is_relative_to(C):raise SystemExit('Replay root must be under assigned spatial cache')
 if newroot.exists():raise SystemExit('Replay root must be new, preserving immutable versions')
 R=newroot
 for folder in ['results','exports','figures']: (R/folder).mkdir(parents=True,exist_ok=True)
elif (R/'exports/geometry_bundle.json').exists():
 raise SystemExit('Frozen v1 exists; use --output-root <new spatial cache subdirectory> to replay without overwriting')

# W explicit because no dependence on associated chat cwd.
W=Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4')
old=json.loads((W/'track_b/research/q4/round2/results/geometry_candidates.geojson').read_text());tr=Transformer.from_crs(4326,32645,always_xy=True);back=Transformer.from_crs(32645,4326,always_xy=True)
g={f['id']:transform(tr.transform,shape(f['geometry'])) for f in old['features']}
src=g['paper_source_outline'];target=g['paper_port_symbol'];channel=LineString(list(g['paper_chhochen_blue_trace'].coords)+list(g['paper_lende_blue_trace'].coords)[1:]);allbounds=np.array([gg.bounds for gg in g.values()]);xmin,ymin=np.floor((allbounds[:,:2].min(axis=0)-1500)/120)*120;xmax,ymax=np.ceil((allbounds[:,2:].max(axis=0)+1500)/120)*120
cop=C/'Copernicus_DSM_COG_10_N28_00_E085_00_DEM.tif'; supplied=W/'track_b/data/processed/spatial/dem_utm45_30m.tif'
primary=cop if cop.exists() else supplied
version='q4-r3-spatial-copdem-v1' if primary==cop else 'q4-r3-spatial-supplied-v1'
def rec(p,role):
 b=p.read_bytes();return {'path':str(p.relative_to(W)) if p.is_relative_to(W) else str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'role':role}
records=[];grids={};feats=[];paths=[]
for res in [60,120]:
 width=int(round((xmax-xmin)/res));height=int(round((ymax-ymin)/res));aff=from_origin(xmin,ymax,res,res)
 z=np.full((height,width),-9999,dtype='float32')
 with rasterio.open(primary) as ds:reproject(rasterio.band(ds,1),z,src_transform=ds.transform,src_crs=ds.crs,dst_transform=aff,dst_crs='EPSG:32645',dst_nodata=-9999,resampling=Resampling.bilinear)
 profile={'driver':'GTiff','dtype':'float32','width':width,'height':height,'count':1,'crs':'EPSG:32645','transform':aff,'nodata':-9999,'compress':'deflate'}
 dst=C/f'{version}_dem_{res}m.tif'
 if not dst.exists():
  with rasterio.open(dst,'w',**profile) as ds:ds.write(z,1)
 else:
  with rasterio.open(dst) as ds:np.testing.assert_allclose(ds.read(1),z)
 mask=rasterize([(src,1)],out_shape=z.shape,transform=aff,fill=0,dtype='uint8')
 channelmask=rasterize([(channel.buffer(res*.7),1)],out_shape=z.shape,transform=aff,fill=0,dtype='uint8');dist=distance_transform_edt(channelmask==0,sampling=res)
 sr,sc=rasterio.transform.rowcol(aff,src.centroid.x,src.centroid.y);tgtr,tgtc=rasterio.transform.rowcol(aff,target.x,target.y)
 arrays=R/f'results/spatial_inputs_{res}m.npz';np.savez_compressed(arrays,z=z,source_mask=mask,channel_distance_m=dist,x=xmin+(np.arange(width)+.5)*res,y=ymax-(np.arange(height)+.5)*res,dx=np.float64(res),source_rc=np.array([sr,sc]),target_rc=np.array([tgtr,tgtc]),transform=np.array(tuple(aff)),geometry_version=np.array(version))
 records.extend([rec(dst,f'primary_dem_{res}m'),rec(arrays,f'model_arrays_{res}m')])
 grids[str(res)]={'shape':[height,width],'resolution_m':res,'crs':'EPSG:32645','affine':list(aff)[:6],'bounds':[xmin,ymin,xmax,ymax],'valid_cells':int(np.sum(z!=-9999)),'source_cells':int(mask.sum()),'source_raster_area_m2':int(mask.sum())*res*res,'source_centroid_utm':[src.centroid.x,src.centroid.y],'source_rc':[int(sr),int(sc)],'target_paper_utm':[target.x,target.y],'target_rc':[int(tgtr),int(tgtc)],'dem_path':str(dst),'arrays_path':str(arrays.relative_to(W)) if arrays.is_relative_to(W) else str(arrays)}
 if res==60:
  rr,cc=np.indices(z.shape);valid=z!=-9999;node=np.arange(z.size).reshape(z.shape)
  for vi,(pid,uw,cw) in enumerate([('P1',12,0),('P2',30,1),('P3',60,2)]):
   a=[];b=[];cost=[]
   for dr,dc in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
    r0=slice(max(0,-dr),min(height,height-dr));c0=slice(max(0,-dc),min(width,width-dc));r1=slice(max(0,dr),min(height,height+dr));c1=slice(max(0,dc),min(width,width+dc));ok=valid[r0,c0]&valid[r1,c1];dz=z[r1,c1]-z[r0,c0];step=res*np.hypot(dr,dc)
    a.append(node[r0,c0][ok]);b.append(node[r1,c1][ok]);cost.append((step+uw*np.maximum(dz,0)+cw*step*np.minimum((dist[r0,c0]+dist[r1,c1])/600,5))[ok])
   # Reverse graph computes predecessor chain from the target to all possible sources.
   graph=coo_matrix((np.concatenate(cost),(np.concatenate(b),np.concatenate(a))),shape=(z.size,z.size)).tocsr();dd,prev=dijkstra(graph,directed=True,indices=tgtr*width+tgtc,return_predecessors=True)
   v=sr*width+sc;ns=[v]
   for j in range(z.size):
    if v==tgtr*width+tgtc:break
    v=int(prev[v]);
    if v<0:raise RuntimeError('route disconnected')
    ns.append(v)
   pts=[];ss=0;ascent=0
   for j,v in enumerate(ns):
    r,c=divmod(v,width);x=xmin+(c+.5)*res;y=ymax-(r+.5)*res
    if j:
     ss+=np.hypot(x-pts[-1][0],y-pts[-1][1]);ascent+=max(0,float(z[r,c])-pts[-1][2])
    pts.append((x,y,float(z[r,c])));paths.append({'path_id':pid,'node_index':j,'x_m':x,'y_m':y,'elevation_m':float(z[r,c]),'distance_m':ss,'row':r,'col':c,'geometry_version':version,'data_role':'conditional_scenario'})
   feats.append({'type':'Feature','id':pid,'properties':{'object_kind':'terrain_cost_path_candidate','geometry_version':version,'uphill_weight':uw,'corridor_weight':cw,'length_m':ss,'cumulative_ascent_m':ascent,'observed_path':False,'source':'Copernicus GLO-30 + paper candidates' if primary==cop else 'supplied DEM unknown product + paper candidates'},'geometry':mapping(transform(back.transform,LineString([(p[0],p[1]) for p in pts])))})
# Keep original candidate geometry IDs while explicitly separating object kinds.
for f in old['features']:
 q=dict(f);q['properties']=dict(f['properties'],geometry_version=version,role='conditional_computational_geometry',accepted_event_geometry=False);feats.append(q)
geo=R/'results/computational_geometries.geojson';geo.write_text(json.dumps({'type':'FeatureCollection','name':version,'crs_note':'GeoJSON CRS84 longitude/latitude; distances in EPSG32645','features':feats},indent=2)+'\n')
pathcsv=R/'results/spatial_paths.csv'
with pathcsv.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(paths[0]));w.writeheader();w.writerows(paths)
records.extend([rec(geo,'computational_geometry_candidates'),rec(pathcsv,'paths_60m_csv')])
# Native source metadata and derived terrain statistics are separate.
with rasterio.open(primary) as ds:origin={'source_path':str(primary),'sha256':hashlib.sha256(primary.read_bytes()).hexdigest(),'native_crs':str(ds.crs),'native_resolution':list(ds.res),'native_shape':list(ds.shape),'native_bounds':list(ds.bounds),'native_nodata':ds.nodata}
terrain={'geometry_version':version,'input_version':{'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','baseline_manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'},'primary':origin,'vertical_datum':'EGM2008 orthometric height' if primary==cop else None,'observation_epoch':'WorldDEM TanDEM-X principal acquisition 2011-2015; edited release 2021, not 2026 event topography' if primary==cop else None,'resampling':'bilinear, no vertical transformation, no hydrologic burn/fill','grids':grids,'files':records,'status':'conditional_scenario; source/target still paper candidates','unknowns':['original paper datum and positional accuracy','actual failure polygon','actual bridge/facility identity at paper point','statistical independence of supplied DEM from Copernicus']}
terrainpath=R/'results/terrain_bundle.json';terrainpath.write_text(json.dumps(terrain,indent=2)+'\n');records.append(rec(terrainpath,'terrain_bundle'))
with np.load(R/'results/spatial_inputs_60m.npz') as zz:
 z=zz['z'];x=zz['x'];y=zz['y'];mask=zz['source_mask']
fig,(ax,ax2)=plt.subplots(1,2,figsize=(13,6));im=ax.imshow(z,extent=[xmin,xmax,ymin,ymax],cmap='terrain',origin='upper');ax.contour(x,y,mask,levels=[.5],colors='red',linewidths=1.2)
for f in feats[:3]:
 p=transform(tr.transform,shape(f['geometry']));ax.plot(*p.xy,label=f['id']);pp=[p for p in paths if p['path_id']==f['id']];ax2.plot([p['distance_m']/1000 for p in pp],[p['elevation_m'] for p in pp],label=f['id'])
ax.scatter([target.x],[target.y],marker='*',s=100,c='black',label='paper port candidate');ax.set_title('Conditional terrain paths; no observed connector');ax.set_xlabel('UTM45N easting (m)');ax.set_ylabel('northing (m)');ax.legend(fontsize=8);fig.colorbar(im,ax=ax,label='height (m)');ax2.set_xlabel('conditional path distance (km)');ax2.set_ylabel('elevation (m)');ax2.set_title('Computed profiles; not observed travel distances');ax2.legend();fig.tight_layout();fp=R/'figures/spatial_terrain_paths.png';fig.savefig(fp,dpi=160);plt.close(fig)
records.append(rec(fp,'terrain_path_figure'))
bundle={'bundle_version':version,'producer_question':'q4','input_version':terrain['input_version'],'evaluation_stratum':'conditional_scenario','files':records,'limitations':terrain['unknowns']+['DEM route is not observed event trajectory; no bridge/facility equivalence accepted','No release thickness or initial speed inferred from NC; caller must supply scenarios'],'source_centroid_utm':[src.centroid.x,src.centroid.y],'target_paper_utm':[target.x,target.y],'grids':grids}
(R/'exports/geometry_bundle.json').write_text(json.dumps(bundle,indent=2)+'\n')
print(json.dumps({'version':version,'grids':grids,'route_stats':[f['properties'] for f in feats[:3]],'bundle':str(R/'exports/geometry_bundle.json')},indent=2))
