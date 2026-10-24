from pathlib import Path
import json,csv,hashlib,datetime
import numpy as np
from shapely.geometry import shape,LineString,mapping,Point
from shapely.ops import transform,nearest_points
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra,breadth_first_order
import rasterio
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
R=Path(__file__).resolve().parents[1];g=json.loads((R/'results/computational_geometries.geojson').read_text());tr=Transformer.from_crs(4326,32645,always_xy=True);bt=Transformer.from_crs(32645,4326,always_xy=True)
gg={f['id']:transform(tr.transform,shape(f['geometry'])) for f in g['features']};src=gg['paper_source_outline'];river=gg['paper_chhochen_blue_trace'];source_near,river_near=nearest_points(src,river)
with np.load(R/'results/spatial_inputs_60m.npz') as f:z=f['z'];x=f['x'];y=f['y'];mask=f['source_mask'].astype(bool)
res=60;h,w=z.shape
rc=lambda p:(int(np.argmin(abs(y-p.y))),int(np.argmin(abs(x-p.x))))
# Predeclared source edge choices nearest edge, edge 300m clockwise, edge 300m anticlockwise.
boundary=src.exterior;s=boundary.project(source_near);starts=[boundary.interpolate((s+off)%boundary.length) for off in [0,300,-300]];goal=river_near
rr,cc=np.indices(z.shape);local=(x[None,:]>=min(p.x for p in starts+[goal])-500)&(x[None,:]<=max(p.x for p in starts+[goal])+500)&(y[:,None]>=min(p.y for p in starts+[goal])-500)&(y[:,None]<=max(p.y for p in starts+[goal])+500)
node=np.arange(z.size).reshape(z.shape);a=[];b=[];cost=[];downs=[];stepL=[]
for dr,dc in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
 r0=slice(max(0,-dr),min(h,h-dr));c0=slice(max(0,-dc),min(w,w-dc));r1=slice(max(0,dr),min(h,h+dr));c1=slice(max(0,dc),min(w,w+dc));ok=local[r0,c0]&local[r1,c1];dz=z[r1,c1]-z[r0,c0];step=res*np.hypot(dr,dc)
 a.append(node[r0,c0][ok]);b.append(node[r1,c1][ok]);cost.append((step+30*np.maximum(dz,0))[ok]);downs.append((dz<=0)[ok]);stepL.append(np.full(np.sum(ok),step))
a=np.concatenate(a);b=np.concatenate(b);cost=np.concatenate(cost);downs=np.concatenate(downs)
graph=coo_matrix((cost,(b,a)),shape=(z.size,z.size)).tocsr();gr,gc=rc(goal);dd,prev=dijkstra(graph,directed=True,indices=gr*w+gc,return_predecessors=True)
downgraph=coo_matrix((np.ones(np.sum(downs)),(a[downs],b[downs])),shape=(z.size,z.size)).tocsr();rows=[];features=[];stats=[]
for k,sp in enumerate(starts):
 sr,sc=rc(sp);v=sr*w+sc;ns=[v]
 for _ in range(z.size):
  if v==gr*w+gc:break
  v=int(prev[v]);
  if v<0:raise RuntimeError('no route in bounded window')
  ns.append(v)
 pts=[];length=0
 for j,v in enumerate(ns):
  r,c=divmod(v,w);p=(float(x[c]),float(y[r]),float(z[r,c]));
  if j:length+=np.hypot(p[0]-pts[-1][0],p[1]-pts[-1][1])
  pts.append(p);rows.append({'connector_id':f'C{k+1}','node_index':j,'x_m':p[0],'y_m':p[1],'elevation_m':p[2],'distance_m':length,'row':r,'col':c,'source_edge_offset_m':[0,300,-300][k]})
 dz=np.diff([p[2] for p in pts]);ds=np.hypot(np.diff([p[0] for p in pts]),np.diff([p[1] for p in pts]));reachable=breadth_first_order(downgraph,sr*w+sc,return_predecessors=False)
 st={'connector_id':f'C{k+1}','source_edge_offset_m':[0,300,-300][k],'source_edge_lonlat':list(bt.transform(sp.x,sp.y)),'source_edge_utm':[sp.x,sp.y],'river_candidate_nearest_utm':[goal.x,goal.y],'raster_snap_start_m':float(sp.distance(Point(x[sc],y[sr]))),'raster_snap_end_m':float(goal.distance(Point(x[gc],y[gr]))),'direct_geometric_gap_m':float(sp.distance(goal)),'path_length_m':length,'start_height_m':pts[0][2],'end_height_m':pts[-1][2],'net_drop_m':pts[0][2]-pts[-1][2],'cumulative_ascent_m':float(np.maximum(dz,0).sum()),'max_single_step_ascent_m':float(np.maximum(dz,0).max(initial=0)),'max_uphill_gradient':float(np.maximum(dz/ds,0).max(initial=0)),'strict_nonincreasing_height_reaches_goal':bool(gr*w+gc in reachable),'strict_test_scope':'8-neighbour current 60m bilinear DSM, bounded local window; not physical avalanche impossibility test','geometry_status':'conditional_connector_candidate; independently observed connection unknown'}
 stats.append(st);features.append({'type':'Feature','id':st['connector_id'],'properties':st,'geometry':mapping(transform(bt.transform,LineString([(p[0],p[1]) for p in pts])))})
p=R/'results/spatial_edge_connectors_v2.geojson';p.write_text(json.dumps({'type':'FeatureCollection','name':'q4-r3-edge-connectors-v2','features':features},indent=2)+'\n')
with (R/'results/spatial_edge_connectors_v2.csv').open('w',newline='') as f:ww=csv.DictWriter(f,fieldnames=list(rows[0]));ww.writeheader();ww.writerows(rows)
(R/'results/spatial_edge_review_v2.json').write_text(json.dumps({'version':'q4-r3-edge-connectors-v2','source_to_river_continuous_gap_m':src.distance(river),'method':'3 edge points at nearest boundary point and +/-300m perimeter; local Dijkstra length+30*positive rise; no fill or burn','stats':stats,'conclusions':['Multiple DEM-conditioned connectors exist as computational candidates; actual trajectory remains unobserved','Strict descent reachability does not include momentum, depth, entrainment, lateral forces, DSM/georegistration error','Positive uphill is reported, never silently clipped or called validated terrain connectivity']},indent=2)+'\n')
# Revise visual tick presentation in new image only; earlier bundle remains byte immutable.
fig,(ax,ax2)=plt.subplots(1,2,figsize=(13,6));bb=[x[0]-30,x[-1]+30,y[-1]-30,y[0]+30];im=ax.imshow(z,extent=bb,cmap='terrain');ax.contour(x,y,mask.astype(float),levels=[.5],colors='red',linewidths=1.2)
for id in ['P1','P2','P3']:
 p=gg[id];ax.plot(*p.xy,label=id)
pp=np.genfromtxt(R/'results/spatial_paths.csv',delimiter=',',names=True,dtype=None,encoding='utf-8')
for id in ['P1','P2','P3']:
 m=pp['path_id']==id;ax2.plot(pp['distance_m'][m]/1000,pp['elevation_m'][m],label=id)
for target in ['paper_port_symbol']:p=gg[target];ax.scatter(p.x,p.y,marker='*',s=100,c='black',label='paper port candidate')
ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.0f}'));ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.0f}'));ax.set_xlabel('UTM45N easting (km)');ax.set_ylabel('northing (km)');ax.set_title('Conditional terrain paths; not event reconstruction');ax.legend(fontsize=8);fig.colorbar(im,ax=ax,label='DSM elevation (m)');ax2.set_xlabel('conditional path distance (km)');ax2.set_ylabel('elevation (m)');ax2.set_title('60m DSM route profiles');ax2.legend();fig.tight_layout();fig.savefig(R/'figures/spatial_terrain_paths_review_v2.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,7));r,c=np.where(local);b=[x[c.min()]-30,x[c.max()]+30,y[r.max()]-30,y[r.min()]+30];ax.imshow(z[r.min():r.max()+1,c.min():c.max()+1],extent=b,cmap='terrain');ax.plot(*src.exterior.xy,c='red',label='paper source boundary');ax.plot(*river.xy,c='blue',label='paper river candidate')
for f in features:p=transform(tr.transform,shape(f['geometry']));ax.plot(*p.xy,label=f['id'])
ax.set_xlim(b[:2]);ax.set_ylim(b[2:]);ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.2f}'));ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.2f}'));ax.set_xlabel('UTM45N easting (km)');ax.set_ylabel('northing (km)');ax.set_title('Local edge connectors; conditional, no verified observed path');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(R/'figures/spatial_edge_connectors_v2.png',dpi=160);plt.close(fig)
print(json.dumps(stats,indent=2))
