#!/usr/bin/env python3
"""Official numerical gully inputs, bypass only broken optional plotting call."""
from pathlib import Path
import json,hashlib,shutil,subprocess,time,datetime
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');RT=C.parents[1]/'runtime';f=C/'benchmarks/gully';a=f/'attempts/01_optional_plotting_failure';a.mkdir(parents=True,exist_ok=True)
for name in ['run.log','execution.json']:
 if (f/name).exists():shutil.copy2(f/name,a/name)
protocol={'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before_solver_retry':True,'failure':'setinput.py numericalfiles generated, then optionalpylabcolormaps collision raises AttributeError; solver not started','fix':'import unmodified officialsetinput, callmaketopo only, then officialsetrun.write andsame officialxdclaw; numericalparameters unchanged','image_id':'sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29'};(P/'config/official_gully_retry_protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
for name in ['setinput.py','setrun.py']:shutil.copy2(RT/'sources/dclaw-1.0.0/examples/gully'/name,f/name)
cmd=['docker','run','--rm','--cpus','2','-e','CLAW=/opt/clawpack','-e','PYTHONPATH=/opt/clawpack','-e','OMP_NUM_THREADS=2','-e','MPLBACKEND=Agg','-v',str(C)+':/work','-w','/work/benchmarks/gully',protocol['image_id'],'python3','-c',"import setinput,setrun,subprocess;setinput.maketopo();setrun.setrun().write();subprocess.run(['/opt/clawpack/dclaw/examples/gully/xdclaw'],check=True)"]
log=f/'run.log';start=time.time()
with log.open('w') as out:r=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
(f/'execution.json').write_text(json.dumps({'benchmark':'gully','image_id':protocol['image_id'],'command':cmd,'started_utc':datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),'elapsed_seconds':time.time()-start,'returncode':r.returncode,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'role':'official_external_numerical_benchmark_not_local_event_validation','optional_plotting_bypassed':True,'native_numerical_source_unchanged':True},indent=2)+'\n');print(r.returncode)
