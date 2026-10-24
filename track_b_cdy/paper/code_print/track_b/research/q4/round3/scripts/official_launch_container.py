#!/usr/bin/env python3
"""Execute authorised shared container, distinct writable /work/q4/official only."""
from pathlib import Path
import argparse,json,subprocess,datetime,time,hashlib
P=Path(__file__).resolve().parents[1];C=Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q4/official');DEST='/work/q4/official'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--container',default='mathorcup-r3-toolchain-build');a.add_argument('--cases',required=True);a.add_argument('--only',default='');a.add_argument('--retry',action='store_true');args=a.parse_args()
 info=json.loads(subprocess.check_output(['docker','inspect',args.container]))[0];cid=info['Id'];cases=json.loads(Path(args.cases).read_text())['cases']
 context={'container_name':args.container,'container_id':cid,'base_image_id':info['Image'],'published_solver_image_id':None,'fixed_source_manifest':'<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/runtime/source_versions.json','source_versions_sha256':sha(C.parents[1]/'runtime/source_versions.json'),'scope':'authorised existing local compiled container; /opt sources untouched','inspected_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (P/'sources/official_container_context.json').write_text(json.dumps(context,indent=2)+'\n')
 subprocess.run(['docker','exec',args.container,'mkdir','-p',DEST+'/inputs',DEST+'/runs',DEST+'/scripts'],check=True)
 subprocess.run(['docker','cp',str(C/'inputs')+'/.',args.container+':'+DEST+'/inputs/'],check=True)
 subprocess.run(['docker','cp',str(P/'scripts/official_container.py'),args.container+':'+DEST+'/scripts/official_container.py'],check=True)
 for item in cases:
  rid=item['run_id']
  if args.only and args.only not in rid:continue
  cp=Path(item['case']);f=cp.parent;meta=f/'execution.json'
  if meta.exists() and not args.retry and json.loads(meta.read_text())['returncode']==0:print('skip',rid,flush=True);continue
  subprocess.run(['docker','exec',args.container,'mkdir','-p',DEST+'/runs/'+rid],check=True);subprocess.run(['docker','cp',str(cp),args.container+':'+DEST+'/runs/'+rid+'/case.json'],check=True)
  cmd=['docker','exec','-e','CLAW=/opt/clawpack','-e','PYTHONPATH=/opt/clawpack','-e','GRASS_ADDON_BASE=/opt/grass-addons','-e','MPLBACKEND=Agg','-e','OMP_NUM_THREADS=2','-e','OFFICIAL_WORK_ROOT='+DEST,'-w',DEST+'/runs/'+rid,args.container,'python3',DEST+'/scripts/official_container.py',DEST+'/runs/'+rid+'/case.json']
  start=time.time();log=f/'run.log'
  with log.open('w') as out:r=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
  copycmd=['docker','cp',args.container+':'+DEST+'/runs/'+rid+'/.',str(f)];cpres=subprocess.run(copycmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  d={'run_id':rid,'image_id':None,'container_id':cid,'base_image_id':info['Image'],'command':cmd,'copy_output_command':copycmd,'copy_returncode':cpres.returncode,'copy_stderr':cpres.stderr,'case_sha256':sha(cp),'started_utc':datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),'elapsed_seconds':time.time()-start,'returncode':r.returncode,'log_path':str(log),'log_sha256':sha(log),'shared_solver_source_unchanged':True};meta.write_text(json.dumps(d,indent=2)+'\n');print(rid,r.returncode,round(d['elapsed_seconds'],2),flush=True)
if __name__=='__main__':main()
