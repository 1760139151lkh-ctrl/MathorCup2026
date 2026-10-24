from pathlib import Path
import requests,json,datetime,hashlib
R=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');records=[]
items=[('copdem_registry.html','https://registry.opendata.aws/copernicus-dem/','GET',None),('copdem_cdse_description.html','https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM','GET',None),('osm_map_direct.osm','https://api.openstreetmap.org/api/0.6/map?bbox=85.35,28.25,85.55,28.36','GET',None),('sentinel2_c1_search.json','https://earth-search.aws.element84.com/v1/search','POST',{'collections':['sentinel-2-c1-l2a'],'bbox':[85.35,28.25,85.55,28.36],'datetime':'2026-08-01T00:00:00Z/2026-09-30T23:59:59Z','limit':100}),('earthsearch_issue41_comments.json','https://api.github.com/repos/Element84/earth-search/issues/41/comments','GET',None)]
for name,url,method,body in items:
 p=C/name;cached=p.exists();now=datetime.datetime.now(datetime.UTC).isoformat();status=None
 if not cached:
  q=requests.request(method,url,json=body,timeout=180);q.raise_for_status();status=q.status_code;p.write_bytes(q.content)
 b=p.read_bytes();records.append({'url':url,'method':method,'request_json':body,'cache_reuse':cached,'read_at_utc':now,'retrieved_at_utc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.UTC).isoformat(),'retrieval_time_basis':'original cache write completion mtime, original HTTP receipts retained in dedicated source logs','status':status,'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'actual_read_scope':'complete cached response; product definition / original object attributes / same-product C1 metadata / provider offset guidance selected'})
# Store selected C1 item metadata as a derivative of the complete original search response.
a=json.loads((C/'sentinel2_c1_search.json').read_text())
for f in a['features']:
 if '20260812' in f['id'] or '20260928' in f['id']:
  p=C/(f['id']+'_c1.json')
  if not p.exists():p.write_text(json.dumps(f,indent=2)+'\n')
(R/'sources/spatial_auxiliary_acquisition.json').write_text(json.dumps({'version':'q4-r3-spatial-aux-v1','records':records},indent=2)+'\n')
print('auxiliary sources',len(records),'cache only',all(x['cache_reuse'] for x in records))
