#!/usr/bin/env python3
"""Register and prepare a constant quiescent-state native-solver benchmark."""
import json,datetime,hashlib
from pathlib import Path
import numpy as np,rasterio
from rasterio.transform import from_origin
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
reg={'protocol':'q4-r3-official-flatrest-v1','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before_execution':True,'state':'flat b=0,constant h=10m,zero momentum,open/extrapolation boundaries; exact static depth and zero velocity','domain':'2400m east x1800m north,60m grid','end_seconds':100,'models':['ravaflow_single','ravaflow_multi','dclaw'],'dclaw_pore_pressure':'hydrostatic,m=.63,actual sourced terms atzero speed andhydrostatic excesszero','role':'numerical_benchmark_not_local_event'}
(P/'config/official_physics_protocol.json').write_text(json.dumps(reg,indent=2)+'\n')
d=C/'inputs/flatrest';d.mkdir(parents=True,exist_ok=True)
for name,value in [('dem.tif',0),('release.tif',10)]:
 with rasterio.open(d/name,'w',driver='GTiff',width=40,height=30,count=1,dtype='float32',crs='EPSG:32645',transform=from_origin(0,1800,60,60),nodata=-9999) as out:out.write(np.full((30,40),value,np.float32),1)
cases=[]
for model,fracs,ex in [('ravaflow_single',[1],{}),('ravaflow_multi',[.6,.1,.3],{}),('dclaw',[.63,.37],{'m0':.63,'kref':1e-10,'init_ptype':0})]:
 rid='flatrest_60_'+model;f=C/'runs'/rid;f.mkdir(parents=True,exist_ok=True)
 case={'run_id':rid,'scenario_id':'numerical_flatrest','model':model,'terrain_id':'analytic_flat','resolution_m':60,'dem':str(d/'dem.tif'),'dem_sha256':sha(d/'dem.tif'),'release':str(d/'release.tif'),'release_sha256':sha(d/'release.tif'),'release_thickness_m':10,'release_grid_volume_m3':43200000.,'mu_basal':.15,'xi':1000 if model!='dclaw' else None,'phase_volume_fractions':fracs,'initial_velocity_east_north_m_s':[0,0],'initiation_to_release_delay_seconds':None,'end_seconds':100,'output_interval_seconds':20,'targets':[],'extras':ex,'evidence_role':'numerical_benchmark'}
 (f/'case.json').write_text(json.dumps(case,indent=2)+'\n');cases.append({'run_id':rid,'case':str(f/'case.json')})
(P/'config/official_cases_flatrest.json').write_text(json.dumps({'cases':cases},indent=2)+'\n');print(len(cases))
