#!/usr/bin/env python3
"""Operational status of the registered native cases, separate from numerical qualification."""
from pathlib import Path
import json,hashlib,datetime
from official_catalogue import registered_cases,applicability,EXCLUDED,PENDING,DIAGNOSTIC
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
items=registered_cases();decisions=applicability()
rows=[];counts={k:0 for k in ['complete','running','not_started','failed','held_not_run','not_run_material_applicability_exclusion']}
for item in items:
 f=Path(item['case']).parent;case=json.loads(Path(item['case']).read_text());log=f/'run.log';meta=f/'execution.json';state='not_started';last=None
 if log.exists():
  state='running'
  if case['model']=='dclaw':
   ts=sorted(f.glob('fort.t[0-9][0-9][0-9][0-9]'))
   if ts:
    try:last=float(ts[-1].read_text().split()[0])
    except (ValueError,IndexError):pass
  else:
   times=[]
   for line in log.read_text(errors='replace').splitlines():
    z=line.split()
    if len(z)>8 and z[0].isdigit():
     try:times.append(float(z[4]))
     except ValueError:pass
   last=max(times) if times else None
  if meta.exists():
   ex=json.loads(meta.read_text())
   if ex.get('log_sha256')==hashlib.sha256(log.read_bytes()).hexdigest():state='complete' if ex['returncode']==0 else 'failed'
 decision=decisions.get(item['run_id'],{}).get('decision','required')
 if state=='not_started' and decision in EXCLUDED|PENDING:state='held_not_run' if decision in PENDING else 'not_run_material_applicability_exclusion'
 rows.append({'run_id':item['run_id'],'state':state,'applicability_decision':decision,'last_actual_output_time_s_from_native_log':last});counts[state]+=1
out={'reported_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'registered_scientific_cases':len(items),'applicable_required_count':sum(decisions.get(x['run_id'],{}).get('decision','required') not in EXCLUDED|PENDING|DIAGNOSTIC for x in items),'diagnostic_only_count':sum(decisions.get(x['run_id'],{}).get('decision') in DIAGNOSTIC for x in items),'counts':counts,'cases':rows,'outside_primary':'old multiphaseSF2 configuration challenge, quarantinedsingleSF2, external official benchmarks and numericalstatic benchmarks separately','completion_scope':'native program exit and closed metadata; physical qualification assessed separately'}
(P/'results/official_execution_progress.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'utc':out['reported_utc'],'registered':len(items),'counts':counts,'running':[r for r in rows if r['state']=='running']}))
