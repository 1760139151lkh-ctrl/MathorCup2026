#!/usr/bin/env python3
"""Execute unchanged official physical/training examples in authorised work area."""
from pathlib import Path
import subprocess,json,datetime,time,hashlib
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');D='/work/q4/official/benchmarks';CON='mathorcup-r3-toolchain-build'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
info=json.loads(subprocess.check_output(['docker','inspect',CON]))[0]
commands=[('cascadia',"set -e; mkdir -p /work/q4/official/benchmarks/cascadia; cd /work/q4/official/benchmarks/cascadia; cat > run.sh <<'BASH'\nset -e\nr.in.gdal --overwrite -o input=DATA/ca_elev.tif output=ca_elev\nr.in.gdal --overwrite -o input=DATA/ca_avalanche.tif output=ca_avalanche\ng.region -s raster=ca_elev\nr.avaflow.40G -ae prefix=cascadia cellsize=20 aoicoords=4400,2200,1000,4000 phases=1 elevation=ca_elev hrelease=ca_avalanche density=2800 friction=35,15,-1000 cohesion=3.0 time=5,200\nBASH\ngrass --tmp-location XY --exec bash run.sh"),('gully',"set -e; mkdir -p /work/q4/official/benchmarks/gully; cd /work/q4/official/benchmarks/gully; cp /opt/clawpack/dclaw/examples/gully/{setrun.py,setinput.py,xdclaw} .; python3 setinput.py; python3 setrun.py; ./xdclaw")]
for name,script in commands:
 f=C/'benchmarks'/name;f.mkdir(parents=True,exist_ok=True);subprocess.run(['docker','exec',CON,'mkdir','-p',D+'/'+name],check=True)
 if name=='cascadia':subprocess.run(['docker','cp','/Users/maxchen/Documents/MathorCup/research_cache/round3/runtime/benchmarks/DATA',CON+':'+D+'/'+name+'/DATA'],check=True)
 cmd=['docker','exec','-e','CLAW=/opt/clawpack','-e','PYTHONPATH=/opt/clawpack','-e','GRASS_ADDON_BASE=/opt/grass-addons','-e','OMP_NUM_THREADS=2','-e','MPLBACKEND=Agg','-w',D+'/'+name,CON,'bash','-lc',script];start=time.time();log=f/'run.log'
 with log.open('w') as out:r=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
 cp=['docker','cp',CON+':'+D+'/'+name+'/.',str(f)];copy=subprocess.run(cp,capture_output=True,text=True)
 result={'benchmark':name,'container_id':info['Id'],'base_image_id':info['Image'],'published_solver_image_id':None,'started_utc':datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),'elapsed_seconds':time.time()-start,'returncode':r.returncode,'command':cmd,'copy_command':cp,'copy_returncode':copy.returncode,'log_sha256':sha(log),'role':'external_numerical_benchmark_not_local_event_validation'};(f/'execution.json').write_text(json.dumps(result,indent=2)+'\n');print(name,r.returncode,flush=True)
