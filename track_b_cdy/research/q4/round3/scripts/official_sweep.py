#!/usr/bin/env python3
"""Full preregistered official competition, separate model queues and exact published image."""
from pathlib import Path
import json,subprocess,time,hashlib,concurrent.futures,threading,datetime
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');IMAGE='sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29';LOCK=threading.Lock();STATE={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finished(rid):
 f=C/'runs'/rid;e=f/'execution.json'
 return e.exists() and (f/'run.log').exists() and json.loads(e.read_text()).get('log_sha256')==sha(f/'run.log')
def progress(key,value):
 with LOCK:
  STATE[key]=value;(P/'results/official_sweep_progress.json').write_text(json.dumps({'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_id':IMAGE,'queues':STATE},indent=2)+'\n');print(key,value,flush=True)
def worker(model,dependency,items):
 progress(model,{'status':'waiting_existing_reference','dependency':dependency})
 while not finished(dependency):time.sleep(10)
 for item in items:
  rid=item['run_id'];progress(model,{'status':'running','run_id':rid})
  cf=P/'config'/f'official_sweep_{model}_current.json';cf.write_text(json.dumps({'cases':[item]},indent=2)+'\n')
  cmd=[str(P.parents[2]/'.venv/bin/python'),str(P/'scripts/official_launch.py'),'--image',IMAGE,'--cases',str(cf)]
  subprocess.run(cmd,check=True)
 progress(model,{'status':'done','case_count':len(items)})
def main():
 data=json.loads((P/'config/official_cases_copdem.json').read_text())['cases'];groups={m:[] for m in ['single','multi','dclaw']};skip={'copdem_120_single_ref','copdem_120_multi_ref','copdem_120_dclaw_ref','copdem_60_dclaw_ref'}
 for it in data:
  if it['run_id'] in skip:continue
  case=json.loads(Path(it['case']).read_text());model=case['model'];group='dclaw' if model=='dclaw' else model.split('_')[1];groups[group].append(it)
 for group,items in groups.items():items.sort(key=lambda x:('60_'+group+'_ref' not in x['run_id'],x['run_id']))
 deps={'single':'copdem_120_single_ref','multi':'copdem_120_multi_ref','dclaw':'copdem_60_dclaw_ref'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  futs=[ex.submit(worker,m,deps[m],items) for m,items in groups.items()]
  for fut in futs:fut.result()
 progress('all',{'status':'done'})
if __name__=='__main__':main()
