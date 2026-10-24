#!/usr/bin/env python3
"""Run inside immutable published Linux image. Does not compile or modify /opt."""
import os,json,sys,subprocess,shutil,math,importlib.util
from pathlib import Path
import numpy as np
from osgeo import gdal
CACHE=Path('/work')
def translatepath(p):return os.environ.get('OFFICIAL_WORK_ROOT','/work')+'/'+str(p).split('/q4/official/',1)[1]
def run_rava(case):
 folder=Path.cwd();dem=translatepath(case['dem']);rel=translatepath(case['release']);dx=case['resolution_m'];out=folder/'run_grass.sh'
 cmd=['r.avaflow.40G','-ae' if case.get('additional_output',True) else '-e',f'prefix={case["run_id"]}',f'cellsize={dx}','elevation=elev','ctopo=0',f'csurface={case.get("csurface",0)}',f'centrainment={case.get("centrainment",0)}','cstopping=0','cmelt=0','gravity=9.81','limiter=1',f'time={case["output_interval_seconds"]},{case["end_seconds"]}',f'cfl={case["extras"].get("cfl",.5)},0.01','thresholds=0.1,10000,10000,0.1,0.000001']
 delta=math.degrees(math.atan(case['mu_basal']))
 if case['model']=='ravaflow_single':cmd+=['phases=1','hrelease=release',f'density={case.get("bulk_density_kg_m3",2105)}',f'friction={case["extras"].get("internal_friction_degrees",35)},{delta},{-case["xi"]}','viscosity=-7']
 else:
  fractions=case['phase_volume_fractions'];delta2=delta
  cmd+=['phases=3','clayers=0','hrelease1=release1','hrelease2=release2','hrelease3=release3','density='+','.join(str(v) for v in case.get('densities_kg_m3',[2700,1850,1000])),f'friction=35,20,0,{delta},{delta2},0,{-case["xi"]},{-case["xi"]},{-case["xi"]}','viscosity=-7,-7,-7','transformation=0,0,0',f'drag={case["extras"].get("drag","1,3,1,0.1,1,1")}',f'virtualmass={case["extras"].get("virtualmass","10,0.12,1")}']
 import shlex
 lines=['#!/bin/bash','set -euo pipefail','command -v r.avaflow.main','sha256sum "$(command -v r.avaflow.main)"',f'r.in.gdal --overwrite input={shlex.quote(dem)} output=elev',f'r.in.gdal --overwrite input={shlex.quote(rel)} output=release','g.region -s raster=elev']
 if case.get('erodible_bed'):
  lines.extend([f'r.in.gdal --overwrite input={shlex.quote(translatepath(case["erodible_bed"]))} output=erodible_bed','r.univar -g map=erodible_bed','r.info -r map=erodible_bed']);cmd+=['hentrmax1=erodible_bed','entrainment='+case['extras']['entrainment']]
 if case['model']!='ravaflow_single':
  for i,x in enumerate(fractions,1):lines.append(f'r.mapcalc --overwrite expression="release{i}=release*{x}"')
 lines.append(shlex.join(cmd));out.write_text('\n'.join(lines)+'\n')
 subprocess.run(['grass','--tmp-location',dem,'--exec','bash',str(out)],check=True)
def dclaw(case):
 # Import official unmodified gully parameter baseline, then explicitly override all scenario-dependent fields.
 sys.path.insert(0,'/opt/clawpack/dclaw/examples/gully');import setrun as original
 d=original.setrun();c=d.clawdata;dx=case['resolution_m']
 dem=gdal.Open(translatepath(case['dem']));z=dem.ReadAsArray();tr=dem.GetGeoTransform();h=gdal.Open(translatepath(case['release'])).ReadAsArray();nx=dem.RasterXSize;ny=dem.RasterYSize
 x=tr[0]+(np.arange(nx)+.5)*dx;y=tr[3]-(np.arange(ny)+.5)*dx
 from clawpack.geoclaw import topotools
 # Boundary nodal padding ensures topography interpolation covers all domain faces.
 for name,arr in [('basal_topo.tt3',z),('thickness.tt3',h)]:
  topo=topotools.Topography();topo.x=np.r_[x[0]-dx,x,x[-1]+dx];topo.y=np.r_[y[-1]-dx,y[::-1],y[0]+dx];topo.Z=np.pad(arr[::-1],1,mode='edge');topo.write(name,topo_type=3,Z_format='%15.7e')
 c.lower=[float(tr[0]),float(tr[3]-ny*dx)];c.upper=[float(tr[0]+nx*dx),float(tr[3])];c.num_cells=[nx,ny];c.output_style=1;c.num_output_times=int(case['end_seconds']/case['output_interval_seconds']);c.tfinal=case['end_seconds'];c.output_t0=True;c.output_format='binary64';c.output_q_components='all';c.output_aux_components='none';c.verbosity=0;c.dt_variable=True;c.dt_initial=.01;c.cfl_desired=.4;c.cfl_max=.49;c.steps_max=100000;c.order=1;c.transverse_waves=0;c.bc_lower=['extrap','extrap'];c.bc_upper=['extrap','extrap'];c.checkpt_style=0
 a=d.amrdata;a.amr_levels_max=1;a.refinement_ratios_x=[1];a.refinement_ratios_y=[1];a.refinement_ratios_t=[1];a.verbosity_regrid=0;a.max1d=max(nx,ny)+4;d.regiondata.regions=[];d.flowgrades_data.flowgrades=[];d.fgmax_data.fgmax_grids=[];d.fgout_data.fgout_grids=[];d.gaugedata.gauges=[]
 d.geo_data.coordinate_system=1;d.geo_data.sea_level=-9999;d.geo_data.dry_tolerance=1e-3;d.geo_data.manning_coefficient=0.;d.geo_data.friction_forcing=True
 dc=d.dclaw_data;dc.rho_s=2700.;dc.rho_f=1000.;dc.m0=case['extras']['m0'];dc.mref=.63;dc.m_crit=.64;dc.kref=case['extras']['kref'];dc.phi=math.degrees(math.atan(case['mu_basal']));dc.mu=.005;dc.entrainment=0;dc.segregation=0;dc.bed_normal=0;dc.src2method=2;dc.alphamethod=1
 d.pinitdclaw_data.init_ptype=case['extras']['init_ptype'];d.topo_data.topofiles=[[3,'basal_topo.tt3']];d.qinitdclaw_data.qinitfiles=[[3,1,'thickness.tt3']];d.write()
 shutil.copy2('/opt/clawpack/dclaw/examples/gully/xdclaw','xdclaw');subprocess.run(['./xdclaw'],check=True)
if __name__=='__main__':
 case=json.loads(Path(sys.argv[1]).read_text());os.chdir(Path(sys.argv[1]).parent)
 if case['model'].startswith('ravaflow'):run_rava(case)
 else:dclaw(case)
