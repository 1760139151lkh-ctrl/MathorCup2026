#!/usr/bin/env python3
"""Read-only partial native output monitor; never a frozen scientific interface."""
from pathlib import Path
import json,re,datetime
import rasterio,numpy as np
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');rows=[]
for f in (C/'runs').glob('*'):
 if not (f/'case.json').exists() or not (f/'run.log').exists():continue
 case=json.loads((f/'case.json').read_text());rid=case['run_id']
 if not (rid.endswith('__sf0') and rid.startswith('copdem')):continue
 text=(f/'run.log').read_text(errors='replace');ts={0:0.}
 for line in text.splitlines():
  z=line.split()
  if len(z)>8 and z[0].isdigit():
   try:ts[int(z[0])]=float(z[4])
   except ValueError:pass
 with rasterio.open(case['dem']) as ds:shape=ds.shape;tr=ds.transform
 yy,xx=np.indices(shape);x=tr.c+(xx+.5)*tr.a;y=tr.f+(yy+.5)*tr.e;masks=[(x-t['xy'][0])**2+(y-t['xy'][1])**2<=100**2 for t in case['targets']];hits=[None]*len(masks);last=0;count=0
 files=sorted((f/(rid+'_results')/(rid+'_ascii')).glob(rid+'_hflow[0-9][0-9][0-9][0-9].asc'))
 for af in files[:-1]:
  ix=int(af.stem[-4:])
  if ix not in ts:continue
  try:
   with rasterio.open(af) as ds:h=ds.read(1)
  except Exception:continue
  if h.shape!=shape:continue
  count+=1;last=ts[ix]
  for k,mask in enumerate(masks):
   if hits[k] is None and np.any(h[mask]>=.1):hits[k]=last
 rows.append({'run_id':rid,'completed_output_times_read':count,'last_completed_time_read_s':last,'targets':[{'target_id':t['id'],'provisional_first_h01_in100m_s':a} for t,a in zip(case['targets'],hits)],'role':'operational_partial_progress_only_not_scientific_export'})
(P/'results/official_live_progress.json').write_text(json.dumps({'reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':rows,'raw_ascii_header_not_used_for_target_coordinates':True},indent=2)+'\n');print(json.dumps(rows,indent=2))
