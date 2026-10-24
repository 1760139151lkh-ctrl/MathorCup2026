#!/usr/bin/env python3
"""Dry-boundary shallow-water lake at rest; preserve full-wet flat failure."""
import json,datetime,hashlib
from pathlib import Path
import numpy as np,rasterio
from rasterio.transform import from_origin
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
reg={'protocol':'q4-r3-official-bowlrest-v1','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before_execution':True,'motivating_failure':'all-wet flatrest ravaflow single SIGSEGV -11 and native edge outflow; original kept','equilibrium':'b=100+4e-5*((x-1200)^2+(y-900)^2),h=max(110-b,0),u=v=0; constantfree surface anddryboundary','solver':'unmodified r.avaflow phases1 withfluiddensity1000,internal/basalfriction0,cmelt0,centraint0','end_seconds':100,'role':'numerical_benchmark_not_event_validation'};(P/'config/official_bowl_protocol.json').write_text(json.dumps(reg,indent=2)+'\n')
d=C/'inputs/bowlrest';d.mkdir(parents=True,exist_ok=True);y=1800-(np.arange(30)+.5)*60;x=(np.arange(40)+.5)*60;xx,yy=np.meshgrid(x,y);z=100+4e-5*((xx-1200)**2+(yy-900)**2);h=np.maximum(110-z,0)
for name,arr in [('dem.tif',z),('release.tif',h)]:
 with rasterio.open(d/name,'w',driver='GTiff',width=40,height=30,count=1,dtype='float32',crs='EPSG:32645',transform=from_origin(0,1800,60,60),nodata=-9999) as out:out.write(arr.astype('float32'),1)
f=C/'runs/bowlrest_60_ravaflow_single';f.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
case={'run_id':f.name,'scenario_id':'numerical_bowlrest','model':'ravaflow_single','terrain_id':'analytic_bowl','resolution_m':60,'dem':str(d/'dem.tif'),'dem_sha256':sha(d/'dem.tif'),'release':str(d/'release.tif'),'release_sha256':sha(d/'release.tif'),'release_thickness_m':None,'release_grid_volume_m3':float(h.astype('float32').astype(float).sum()*3600),'bulk_density_kg_m3':1000,'mu_basal':0,'xi':1000,'phase_volume_fractions':[1],'initial_velocity_east_north_m_s':[0,0],'initiation_to_release_delay_seconds':None,'end_seconds':100,'output_interval_seconds':20,'targets':[],'extras':{'internal_friction_degrees':0},'evidence_role':'numerical_benchmark'};(f/'case.json').write_text(json.dumps(case,indent=2)+'\n');(P/'config/official_cases_bowlrest.json').write_text(json.dumps({'cases':[{'run_id':f.name,'case':str(f/'case.json')}]},indent=2)+'\n')
