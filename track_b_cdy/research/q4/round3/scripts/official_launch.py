#!/usr/bin/env python3
"""Sequential official solvers; immutable local image, exclusive q4 cache only."""
from pathlib import Path
import argparse,json,subprocess,datetime,time,hashlib,shutil,fcntl
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3];CACHE=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');RT=CACHE.parents[1]/'runtime'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--image',required=True);a.add_argument('--cases');a.add_argument('--only',default='');a.add_argument('--benchmarks',action='store_true');a.add_argument('--resourcefix',action='store_true');args=a.parse_args()
 inspect=json.loads(subprocess.check_output(['docker','image','inspect',args.image]))[0]
 image=inspect['Id'];(P/'sources/official_image.json').write_text(json.dumps({'requested':args.image,'image_id':image,'repo_digests':inspect.get('RepoDigests',[]),'architecture':inspect['Architecture'],'os':inspect['Os'],'inspected_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
 base=['docker','run','--rm','--cpus','1','-e','OMP_NUM_THREADS=3','-e','CLAW=/opt/clawpack','-e','PYTHONPATH=/opt/clawpack','-e','GRASS_ADDON_BASE=/opt/grass-addons','-e','MPLBACKEND=Agg','-v',str(CACHE)+':/work','-v',str(ROOT)+':/repo:ro','-v',str(RT)+':/runtime:ro','-w','/work']
 if args.resourcefix:
  addon=RT/'diagnostics/q4_native_asan/derived/release_addon';base[base.index('GRASS_ADDON_BASE=/opt/grass-addons')]='GRASS_ADDON_BASE=/resourcefix';base+=['-v',str(addon)+':/resourcefix:ro']
 if args.benchmarks:
  b=CACHE/'benchmarks';b.mkdir(exist_ok=True)
  commands=[('cascadia',"set -e; mkdir -p /work/benchmarks/cascadia; cd /work/benchmarks/cascadia; cp -rn /runtime/benchmarks/DATA .; cat > run.sh <<'BASH'\nset -e\nr.in.gdal --overwrite -o input=DATA/ca_elev.tif output=ca_elev\nr.in.gdal --overwrite -o input=DATA/ca_avalanche.tif output=ca_avalanche\ng.region -s raster=ca_elev\nr.avaflow.40G -ae prefix=cascadia cellsize=20 aoicoords=4400,2200,1000,4000 phases=1 elevation=ca_elev hrelease=ca_avalanche density=2800 friction=35,15,-1000 cohesion=3.0 time=5,200\nBASH\ngrass --tmp-location XY --exec bash run.sh"),('gully',"set -e; mkdir -p /work/benchmarks/gully; cd /work/benchmarks/gully; cp /opt/clawpack/dclaw/examples/gully/{setrun.py,setinput.py,xdclaw} .; python3 setinput.py; python3 setrun.py; ./xdclaw")]
  for name,script in commands:
   log=b/f'{name}.log';meta=b/f'{name}_execution.json'
   if meta.exists() and json.loads(meta.read_text())['returncode']==0:continue
   cmd=base+[image,'bash','-lc',script]
   start=time.time()
   with log.open('w') as out:r=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
   meta.write_text(json.dumps({'name':name,'image_id':image,'command':cmd,'started_utc':datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),'elapsed_seconds':time.time()-start,'returncode':r.returncode,'log_sha256':sha(log),'role':'external_official_numerical_benchmark_not_local_event_validation'},indent=2)+'\n');print(name,r.returncode,flush=True)
  return
 if not args.cases:raise ValueError('--cases required')
 cases=json.loads(Path(args.cases).read_text())['cases']
 for item in cases:
  if args.only and args.only not in item['run_id']:continue
  # Current jobs are untouched. All future launchers cooperate on a per-run lock.
  locks=CACHE/'.locks';locks.mkdir(exist_ok=True)
  with (locks/(item['run_id']+'.lock')).open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX)
   while True:
    registry=P/'config/official_execution_applicability.json';decision='required'
    if registry.exists():decision=next((x['decision'] for x in json.loads(registry.read_text())['entries'] if x['run_id']==item['run_id']),'required')
    if decision!='pending_review_do_not_start':break
    print('held_pending_applicability_review',item['run_id'],flush=True);time.sleep(30)
   if decision in ['quarantined_not_run','not_run_material_applicability_exclusion']:print(decision,item['run_id'],flush=True);continue
   run_case(item,args,base,image)
def run_case(item,args,base,image):
  cp=Path(item['case']);folder=cp.parent;meta=folder/'execution.json'
  if meta.exists() and json.loads(meta.read_text()).get('log_sha256')==sha(folder/'run.log'):print('skip_closed_execution',item['run_id'],flush=True);return
  adapter=folder/'adapter_executed.py';shutil.copy2(P/'scripts/official_container.py',adapter)
  command=base+['-w','/work/runs/'+item['run_id'],image,'python3','/work/runs/'+item['run_id']+'/adapter_executed.py','/work/runs/'+item['run_id']+'/case.json'];start=time.time();log=folder/'run.log'
  with log.open('w') as out:r=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
  fixed=args.resourcefix or image=='sha256:3d8d8b4a31a520f64c52c2e8d3e23684181222c40ffd246f2d9e25d5cd511bce'
  d={'run_id':item['run_id'],'image_id':image,'solver_build':'explicit_resourcefix_build' if fixed else 'official_original','resourcefix_binary_sha256':'45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c' if fixed else None,'command':command,'case_sha256':sha(cp),'adapter_path':str(adapter),'adapter_sha256_at_start':sha(adapter),'started_utc':datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),'elapsed_seconds':time.time()-start,'returncode':r.returncode,'log_path':str(log),'log_sha256':sha(log),'per_run_advisory_lock':str(CACHE/'.locks'/(item['run_id']+'.lock'))};meta.write_text(json.dumps(d,indent=2)+'\n');print(item['run_id'],r.returncode,round(d['elapsed_seconds'],2),flush=True)
if __name__=='__main__':main()
