#!/usr/bin/env python3
"""Active-run coordinator: refresh interfaces only when a registered native case closes."""
from pathlib import Path
import json,subprocess,time,hashlib,datetime
from official_catalogue import registered_cases,applicability,EXCLUDED,PENDING,DIAGNOSTIC
P=Path(__file__).resolve().parents[1];PY=str(P.parents[2]/'.venv/bin/python');items=registered_cases()
def closed():
 out=set()
 for item in items:
  folder=Path(item['case']).parent;meta=folder/'execution.json';log=folder/'run.log'
  if not meta.exists() or not log.exists():continue
  try:ex=json.loads(meta.read_text())
  except json.JSONDecodeError:continue
  if ex.get('log_sha256')==hashlib.sha256(log.read_bytes()).hexdigest():out.add(item['run_id'])
 return out
def run(script,*args):subprocess.run([PY,str(P/'scripts'/script),*args],check=True)
seen=set()
while True:
 items=registered_cases();decisions=applicability();required={x['run_id'] for x in items if decisions.get(x['run_id'],{}).get('decision','required') not in EXCLUDED|PENDING|DIAGNOSTIC};diagnostic={x['run_id'] for x in items if decisions.get(x['run_id'],{}).get('decision') in DIAGNOSTIC};pending={x['run_id'] for x in items if decisions.get(x['run_id'],{}).get('decision') in PENDING}
 now=closed();run('official_status.py')
 if now!=seen:
  print(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'newly_closed':sorted(now-seen),'registered_closed':len(now)}),flush=True)
  for script in ['official_analyse.py','official_targets.py','official_parser_validate.py']:run(script)
  seen=now
  (P/'results/official_monitor_state.json').write_text(json.dumps({'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'closed_count':len(now),'registered_count':len(items),'applicable_required_count':len(required),'applicability_pending_count':len(pending),'closed_run_ids':sorted(now),'last_postprocess_passed':True,'physics_accuracy_or_conservation_claim':False},indent=2)+'\n')
 if required|diagnostic<=now and not pending:
  run('official_freeze.py');print('All registered native executions closed; raw provenance frozen, scientific review remains separate.',flush=True);break
 time.sleep(45)
