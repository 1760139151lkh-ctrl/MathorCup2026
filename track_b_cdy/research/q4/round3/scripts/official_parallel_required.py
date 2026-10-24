#!/usr/bin/env python3
"""Fill freed conceptual queue slots with registered required cases, never generic exclusions."""
from pathlib import Path
import json,subprocess,time,hashlib,datetime
from official_catalogue import registered_cases,applicability,EXCLUDED,PENDING,DIAGNOSTIC
P=Path(__file__).resolve().parents[1];PY=str(P.parents[2]/'.venv/bin/python');IMAGE='sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29'
def closed(item):
 f=Path(item['case']).parent;e=f/'execution.json';l=f/'run.log'
 return e.exists() and l.exists() and json.loads(e.read_text()).get('log_sha256')==hashlib.sha256(l.read_bytes()).hexdigest()
def legacy_reserved_queue_count():
 progress=json.loads((P/'results/official_sweep_v2_progress.json').read_text())['queues'];n=sum(progress.get(g,{}).get('status')!='done' for g in ['single','multi','dclaw'])
 # The already-running old composite launcher starts its matched control internally;
 # reserve its queue through both executions, including the gap between containers.
 n+=not all(closed(i) for i in json.loads((P/'config/official_cases_composite.json').read_text())['cases'])
 return n
def priority(rid):
 keys=['q2full_q2r3_p0036_S_T_linear__geomv2_60m','q2full_q2r3_p0036_S_T_linear__geomv2_120m','composite_RI_water_nodragvm','single_entrain1m','60_single_ref','single_cfl025','single_mu0p08','single_mu0p25','single_h136','single_h5','single_h30','single_xi500','single_xi2000','geomv2_120m']
 return next((k for k,v in enumerate(keys) if v in rid),len(keys)),rid
children={};statefile=P/'results/official_parallel_state.json';previous=json.loads(statefile.read_text()) if statefile.exists() else {};adopted=set(previous.get('extra_launchers',[]))|set(previous.get('adopted_extra_launchers',[]))
while True:
 for rid,child in list(children.items()):
  if child.poll() is not None:print('parallel_launcher_closed',rid,child.returncode,flush=True);del children[rid]
 cases=registered_cases();byid={i['run_id']:i for i in cases};adopted={rid for rid in adopted if rid in byid and not closed(byid[rid])};decisions=applicability();required=[i for i in cases if decisions.get(i['run_id'],{}).get('decision','required') not in EXCLUDED|PENDING|DIAGNOSTIC];remaining=[i for i in required if not closed(i)];reserved=legacy_reserved_queue_count();capacity=max(0,6-reserved)
 eligible=[]
 for item in remaining:
  rid=item['run_id'];f=Path(item['case']).parent
  if rid in children or rid in adopted or (f/'run.log').exists() or rid in ['composite_RI_water_120__sf0','composite_rock_water_120__sf0']:continue
  eligible.append(item)
 for item in sorted(eligible,key=lambda i:priority(i['run_id'])):
  if len(children)+len(adopted)>=capacity:break
  rid=item['run_id'];config=P/'config'/f'official_parallel_{rid}.json';config.write_text(json.dumps({'cases':[item]},indent=2)+'\n');cmd=[PY,str(P/'scripts/official_launch.py'),'--image',IMAGE,'--cases',str(config)];children[rid]=subprocess.Popen(cmd);print(json.dumps({'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_id':rid,'command':cmd,'legacy_reserved_queues':reserved,'extra_launchers':len(children),'max_total_native_processes':6}),flush=True)
 (P/'results/official_parallel_state.json').write_text(json.dumps({'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'registered':len(cases),'applicable_required':len(required),'remaining_required':len(remaining),'legacy_reserved_queues':reserved,'extra_launchers':list(children),'adopted_extra_launchers':sorted(adopted),'max_total_native_processes':6,'uniqueness':'futuremain/extra launchers share per-runfcntl lock; existingmatchedcomposite queue excludedextra'},indent=2)+'\n')
 if not remaining and not children and not adopted:break
 time.sleep(30)
