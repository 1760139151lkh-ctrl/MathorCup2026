from pathlib import Path
import requests,json,hashlib,datetime,time
R=Path(__file__).resolve().parents[1]; C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial'); C.mkdir(parents=True,exist_ok=True)
log=[]
def fetch(url,name,method='GET',**kw):
 t=datetime.datetime.now(datetime.UTC).isoformat(); p=C/name
 if p.exists():
  b=p.read_bytes(); rec={'url':url,'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'retrieved_at_utc':t,'cache_reuse':True,'actual_read_scope':'complete cached response'};log.append(rec);return b
 try:
  q=requests.request(method,url,timeout=180,**kw);b=q.content
  rec={'url':url,'method':method,'status':q.status_code,'retrieved_at_utc':t,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'actual_read_scope':'complete HTTP response','content_type':q.headers.get('content-type'),'etag':q.headers.get('etag'),'request_body':kw.get('json') or kw.get('data')}
  if q.ok: p.write_bytes(b);rec['path']=str(p)
  else: rec['failure_excerpt']=b[:300].decode(errors='replace')
  log.append(rec);return b if q.ok else None
 except Exception as e: log.append({'url':url,'retrieved_at_utc':t,'exception':str(e),'status':None,'bytes':None,'sha256':None});return None
try:
 fetch('https://copernicus-dem-30m.s3.amazonaws.com/readme.html','copdem_readme.html')
 name='Copernicus_DSM_COG_10_N28_00_E085_00_DEM'
 fetch(f'https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif',name+'.tif')
 # independently geocoded volunteer geographic objects; no authentication bypass.
 bbox='28.25,85.35,28.36,85.55'
 query=f'[out:json][timeout:60];(way["waterway"~"river|stream"]({bbox});way["bridge"]({bbox});node["barrier"="border_control"]({bbox});way["amenity"="customs"]({bbox});node["amenity"="customs"]({bbox}););out tags center geom;'
 fetch('https://overpass-api.de/api/interpreter','osm_overpass.json','POST',data={'data':query})
 # full catalogue responses preserved, not confused with acquired pixels.
 body={'collections':['sentinel-2-l2a'],'bbox':[85.35,28.25,85.55,28.36],'datetime':'2026-08-01T00:00:00Z/2026-09-30T23:59:59Z','limit':100}
 fetch('https://earth-search.aws.element84.com/v1/search','sentinel2_search.json','POST',json=body)
finally:
 (R/'sources/spatial_acquisition.json').write_text(json.dumps({'version':'q4-r3-spatial-source-v1','records':log},indent=2)+'\n')
 print(json.dumps([{k:r.get(k) for k in ['url','status','bytes','path','exception']} for r in log],indent=2))
