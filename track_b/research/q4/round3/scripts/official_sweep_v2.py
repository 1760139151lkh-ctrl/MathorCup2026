#!/usr/bin/env python3
"""Registered corrected competition and Q2 transfers, all native fixed-image runs."""
from pathlib import Path
import json,subprocess,time,hashlib,concurrent.futures,threading,datetime
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');IMAGE='sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29';LOCK=threading.Lock();STATE={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finished(rid):
 f=C/'runs'/rid;e=f/'execution.json'
 return e.exists() and (f/'run.log').exists() and json.loads(e.read_text()).get('log_sha256')==sha(f/'run.log')
def progress(key,value):
 with LOCK:
  STATE[key]=value;(P/'results/official_sweep_v2_progress.json').write_text(json.dumps({'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_id':IMAGE,'queues':STATE},indent=2)+'\n');print(key,value,flush=True)
def worker(model,dependency,items):
 if dependency:
  progress(model,{'status':'waiting_existing_reference','dependency':dependency})
  while not finished(dependency):time.sleep(10)
 for item in items:
  rid=item['run_id'];progress(model,{'status':'running','run_id':rid});cf=P/'config'/f'official_sweep_v2_{model}_current.json';cf.write_text(json.dumps({'cases':[item]},indent=2)+'\n');cmd=[str(P.parents[2]/'.venv/bin/python'),str(P/'scripts/official_launch.py'),'--image',IMAGE,'--cases',str(cf)];subprocess.run(cmd,check=True)
 progress(model,{'status':'done','case_count':len(items)})
def main():
 groups={m:[] for m in ['single','multi','dclaw']}
 for item in json.loads((P/'config/official_cases_copdem_v2.json').read_text())['cases']:
  case=json.loads(Path(item['case']).read_text());model=case['model'];group='dclaw' if model=='dclaw' else model.split('_')[1]
  if item['run_id'] in ['copdem_120_dclaw_ref','copdem_60_dclaw_ref']:continue
  groups[group].append(item)
 for m in ['single','multi']:groups[m].sort(key=lambda x:(0 if '120_'+m+'_ref__sf0' in x['run_id'] else 2 if '60_'+m+'_ref__sf0' in x['run_id'] else 3,x['run_id']))
 q2=[]
 for suite in ['q2mapped','q2fullmask']:q2+=json.loads((P/f'config/official_cases_{suite}_v2.json').read_text())['cases']
 groups['single']=groups['single'][:1]+q2+groups['single'][1:]
 deps={'single':None,'multi':None,'dclaw':'copdem_60_dclaw_ref'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  for fut in [ex.submit(worker,m,deps[m],items) for m,items in groups.items()]:fut.result()
 progress('all',{'status':'done'})
if __name__=='__main__':main()
