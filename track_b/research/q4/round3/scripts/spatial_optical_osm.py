from pathlib import Path
import requests,json,hashlib,datetime,concurrent.futures
R=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');log=[]
def fetch(url,name):
 p=C/name;t=datetime.datetime.now(datetime.UTC).isoformat()
 try:
  if p.exists():b=p.read_bytes();status=None;reuse=True
  else:
   q=requests.get(url,headers={'User-Agent':'MathorCup-Q4-academic-spatial/1.0'},timeout=180);b=q.content;status=q.status_code;reuse=False
   if q.ok:p.write_bytes(b)
  r={'url':url,'path':str(p) if p.exists() else None,'retrieved_at_utc':t,'status':status,'cache_reuse':reuse,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'actual_read_scope':'complete HTTP response','available_time':None}
  if not p.exists():r['error_excerpt']=b[:300].decode(errors='replace')
  return r
 except Exception as e:return {'url':url,'retrieved_at_utc':t,'exception':str(e),'bytes':None,'sha256':None,'status':None}
a=json.loads((C/'sentinel2_search.json').read_text());ids=['S2B_45RUM_20260824_0_L2A','S2C_45RUM_20260812_0_L2A','S2C_45RUM_20260928_0_L2A'];jobs=[]
for id in ids:
 f=next(x for x in a['features'] if x['id']==id);(C/(id+'.json')).write_text(json.dumps(f,indent=2)+'\n')
 for band in ['visual','scl']:jobs.append((f['assets'][band]['href'],f'{id}_{band}.tif'))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for rec in ex.map(lambda args:fetch(*args),jobs):log.append(rec);print(json.dumps({k:rec.get(k) for k in ['path','status','bytes','exception']}),flush=True)
# GET alternative after POST Overpass 406; each response recorded.
for url,name in [('https://overpass.kumi.systems/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A60%5D%3B%28way%5B%22waterway%22%5D%2828.25%2C85.35%2C28.36%2C85.55%29%3Bway%5B%22bridge%22%5D%2828.25%2C85.35%2C28.36%2C85.55%29%3B%29%3Bout%20tags%20geom%3B','osm_overpass_get.json'),('https://api.openstreetmap.org/api/0.6/map?bbox=85.35,28.25,85.55,28.36','osm_map.osm')]:
 rec=fetch(url,name);log.append(rec);print(json.dumps({k:rec.get(k) for k in ['url','status','bytes','exception']}),flush=True)
 if rec.get('path'):break
(R/'sources/spatial_optical_osm_acquisition.json').write_text(json.dumps({'version':'q4-r3-optical-osm-v1','records':log},indent=2)+'\n')
