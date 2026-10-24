from pathlib import Path
import xml.etree.ElementTree as E,json,hashlib,datetime,csv
from shapely.geometry import Point,LineString,Polygon,shape,mapping
from shapely.ops import transform,unary_union
from pyproj import Transformer
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
R=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');p=C/'osm_map_direct.osm';r=E.parse(p).getroot();nodes={e.get('id'):(float(e.get('lon')),float(e.get('lat'))) for e in r.findall('node')};tr=Transformer.from_crs(4326,32645,always_xy=True);bt=Transformer.from_crs(32645,4326,always_xy=True)
old=json.loads((R/'results/computational_geometries.geojson').read_text());gg={f['id']:transform(tr.transform,shape(f['geometry'])) for f in old['features']};src=gg['paper_source_outline'];port=gg['paper_port_symbol'];feats=[];rivers=[];objects=[]
selected_targets={'1552746552':'temporary_bridge_centerline_candidate','1552746560':'temporary_bridge_structure_candidate','1443180803':'former_resuo_bridge_centerline_candidate','1552746559':'former_resuo_bridge_structure_candidate','1553369440':'china_immigration_facility_candidate'}
for e in list(r.findall('way'))+list(r.findall('node')):
 t={q.attrib['k']:q.attrib['v'] for q in e.findall('tag')};kind=None;geom=None
 if e.tag=='way':
  if t.get('waterway') in ['river','stream']:kind='volunteer_river_or_stream'
  elif any('bridge' in k for k in t):kind='bridge_or_former_bridge_candidate'
  elif e.get('id') in selected_targets:kind=selected_targets[e.get('id')]
  elif any(t.get(k)=='border_control' for k in ['barrier','destroyed:barrier']):kind='border_control_facility_candidate'
  if not kind:continue
  pts=[nodes[n.get('ref')] for n in e.findall('nd') if n.get('ref') in nodes]
  if len(pts)<2:continue
  geom=Polygon(pts) if len(pts)>3 and pts[0]==pts[-1] and (t.get('area')=='yes' or 'building' in ''.join(t.keys())) else LineString(pts)
 elif e.tag=='node' and (t.get('barrier')=='border_control' or t.get('amenity')=='customs'):
  kind='border_control_or_customs_point_candidate';geom=Point(nodes[e.get('id')])
 if geom is None:continue
 gp=transform(tr.transform,geom);id=f"osm_{e.tag}_{e.get('id')}";pr={'geometry_version':'q4-r3-osm-objects-v2','object_kind':selected_targets.get(e.get('id'),kind),'osm_type':e.tag,'osm_id':e.get('id'),'osm_version':e.get('version'),'osm_last_edit_time_utc':e.get('timestamp'),'canonical_url':f"https://www.openstreetmap.org/{e.tag}/{e.get('id')}",'coordinate_crs':'CRS84','distance_crs':'EPSG:32645','positional_accuracy_m':None,'observed_time_utc':None,'available_time':None,'evidence_status':'independent_machine_geometry_from_volunteer_mapping; survey/source independence and accuracy unverified','accepted_event_geometry':False,'tags':t,'distance_to_paper_port_m':gp.distance(port),'distance_to_paper_source_m':gp.distance(src)}
 feats.append({'type':'Feature','id':id,'properties':pr,'geometry':mapping(geom)})
 if kind=='volunteer_river_or_stream':rivers.append((id,gp,pr))
 if e.get('id') in selected_targets:
  c=gp.centroid;objects.append({'target_id':id,'entity_id':('temporary_resuo_bridge' if e.get('id') in ['1552746552','1552746560'] else 'former_resuo_bridge' if e.get('id') in ['1443180803','1552746559'] else 'china_immigration_facility'),'target_kind':selected_targets[e.get('id')],'x_m':c.x,'y_m':c.y,'longitude':geom.centroid.x,'latitude':geom.centroid.y,'distance_to_paper_point_m':gp.distance(port),'centroid_to_paper_point_m':c.distance(port),'osm_version':e.get('version'),'osm_last_edit_time_utc':e.get('timestamp'),'position_uncertainty_m':None,'data_role':'conditional_scenario','geometry_version':'q4-r3-osm-objects-v2','observed_time_utc':None})
output=R/'results/spatial_osm_objects_v2.geojson';output.write_text(json.dumps({'type':'FeatureCollection','name':'q4-r3-osm-objects-v2','source_snapshot_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'features':feats},ensure_ascii=False,indent=2)+'\n')
with (R/'results/spatial_targets_v2.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(objects[0]));w.writeheader();w.writerows(objects)
river_union=unary_union([q[1] for q in rivers]);comparisons={}
for id in ['paper_chhochen_blue_trace','paper_lende_blue_trace','P1','P2','P3']:
 line=gg[id];pts=[line.interpolate(v) for v in np.arange(0,line.length+1,120)];ds=np.array([p.distance(river_union) for p in pts]);comparisons[id]={'n_120m_samples':len(pts),'distance_to_nearest_any_mapped_waterway_median_m':float(np.median(ds)),'p95_m':float(np.percentile(ds,95)),'max_m':float(ds.max()),'scope':'nearest among all retrieved river/stream lines; tributary ambiguity, not matched true route'}
closest=sorted(rivers,key=lambda q:q[1].distance(src))[:10]
report={'version':'q4-r3-osm-objects-v2','source_snapshot':{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':'https://api.openstreetmap.org/api/0.6/map?bbox=85.35,28.25,85.55,28.36','query_bbox_crs84':[85.35,28.25,85.55,28.36]},'counts':{'river_stream_lines':len(rivers),'selected_objects':len(feats),'target_geometry_representations':len(objects),'distinct_target_entities':len({q['entity_id'] for q in objects})},'comparisons':comparisons,'closest_waterways_to_source':[{'id':q[0],'distance_to_source_polygon_m':q[1].distance(src),'name':q[2]['tags'].get('name:en',q[2]['tags'].get('name')),'osm_last_edit_time_utc':q[2]['osm_last_edit_time_utc']} for q in closest],'target_definitions':objects,'limitations':['Volunteer geometry is an independent machine-readable source, not independently surveyed event truth','Many last edits are post-event and some damage tags cite Wikipedia; geometry/label evidential independence from literature is unestablished','OSM timestamp is last edit, not feature observation time or historical availability','Temporary bridge and former bridge are distinct lifecycle/object candidates; no damage-state claim accepted; centerline/structure are duplicate representations within each entity, not independent targets','China immigration footprint is a facility candidate, not the entire port polygon; actual protected facility extent remains unknown','Nearest-waterway proximity does not identify the event path or close source geometry truth'],'license':'OpenStreetMap contributors; ODbL attribution required'}
(R/'results/spatial_osm_review_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
# Background actual before image only, shows target objects separately.
with __import__('rasterio').open(C/'S2C_45RUM_20260812_0_L2A_visual_crop.tif') as ds:rgb=ds.read();bb=list(ds.bounds)
fig,(ax,ax2)=plt.subplots(1,2,figsize=(13,7));ax.imshow(np.moveaxis(rgb,0,-1),extent=[bb[0],bb[2],bb[1],bb[3]]);ax2.imshow(np.moveaxis(rgb,0,-1),extent=[bb[0],bb[2],bb[1],bb[3]])
for id,gp,pr in rivers:
 if gp.distance(unary_union([gg['paper_chhochen_blue_trace'],gg['paper_lende_blue_trace']]))<500:
  ax.plot(*gp.xy,c='cyan',lw=.7,alpha=.8)
for id in ['P1','P2','P3']:ax.plot(*gg[id].xy,lw=.6,c='yellow',alpha=.7)
ax.plot(*src.exterior.xy,c='red',lw=1);ax.set_xlim(bb[0],bb[2]);ax.set_ylim(bb[1],bb[3]);ax.set_title('Independent OSM waterways over actual 08-12 TCI\ncyan=volunteer geometry; yellow=conditional DEM routes')
for q in objects:
 f=next(f for f in feats if f['id']==q['target_id']);gp=transform(tr.transform,shape(f['geometry']));xy=gp.exterior.xy if gp.geom_type=='Polygon' else gp.xy;lab=q['target_kind'].replace('_candidate','').replace('_',' ');ax2.plot(*xy,label=lab,lw=2)
ax2.scatter(port.x,port.y,c='black',marker='*',s=80,label='paper port point');ax2.set_xlim(port.x-400,port.x+300);ax2.set_ylim(port.y-400,port.y+300);ax2.set_title('Port / temporary bridge / former bridge / facility\nSeparate candidate objects, no accepted common target')
for a in [ax,ax2]:a.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.2f}'));a.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.2f}'));a.set_xlabel('UTM45N easting (km)');a.set_ylabel('northing (km)')
ax2.legend(fontsize=7,loc='lower left');fig.tight_layout();fig.savefig(R/'figures/spatial_osm_objects_v2.png',dpi=180);plt.close(fig)
print(json.dumps({'counts':report['counts'],'closest':report['closest_waterways_to_source'][:3],'target_definitions':objects,'comparison':comparisons},indent=2))
