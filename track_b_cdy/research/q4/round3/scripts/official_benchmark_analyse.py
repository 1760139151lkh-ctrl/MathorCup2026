#!/usr/bin/env python3
"""Numerical checks for true official examples, never local event validation."""
from pathlib import Path
import json,datetime,hashlib,numpy as np
from official_analyse import raster,frame_dclaw
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');result=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
f=C/'benchmarks/cascadia';e=f/'execution.json'
if e.exists():
 ex=json.loads(e.read_text());base=f/'cascadia_results/cascadia_ascii';files=f/'cascadia_results/cascadia_files';frames=sorted(base.glob('cascadia_hflow[0-9][0-9][0-9][0-9].asc'));arrays=[raster(p)[0] for p in frames];nout=files/'cascadia_nout1.txt';v=nout.read_text().split() if nout.exists() else []
 if arrays:
  first=arrays[0];last=arrays[-1];core=last[3:-3,3:-3].sum()*400;edge=float(v[26]) if v else None
  result.append({'benchmark':'official_Cascadia_exp1','execution_returncode':ex['returncode'],'execution_sha256':sha(e),'frames':len(arrays),'native_csuccess':int(v[1]) if v else None,'requested_horizon_s':200,'all_depth_finite':bool(np.isfinite(arrays).all()),'minimum_depth_m':float(np.min(arrays)),'initial_volume_m3':float(first.sum()*400),'final_raster_volume_m3':float(last.sum()*400),'final_native_active_core_volume_m3':float(core),'final_native_edge_store_volume_m3':edge,'native_core_plus_edge_volume_residual_fraction':float((core+edge)/(first.sum()*400)-1) if edge is not None else None,'native_global_cumulative_max_speed_m_s':float(v[15]) if v else None,'source_scope':'fixed originalCascadia2024bundle numerical parameters plusRev7 GRASSinterface,200s,20m','local_independent_validation_event':False})
f=C/'benchmarks/gully';e=f/'execution.json'
if e.exists():
 ex=json.loads(e.read_text());ts=sorted(f.glob('fort.t[0-9][0-9][0-9][0-9]'));hist=[]
 for tf in ts:
  t,patches=frame_dclaw(f,tf.name[-4:]);vol=0;mass=0;minh=float('inf');maxspeed=0;finite=True
  for q,x0,y0,dx,dy in patches:
   yy,xx=np.indices(q.shape[:2]);x=x0+(xx+.5)*dx;y=y0+(yy+.5)*dy;keep=np.ones(q.shape[:2],bool)
   for qf,xf,yf,dxf,dyf in patches:
    if dxf<dx-1e-9:keep &= ~((x>=xf)&(x<xf+qf.shape[1]*dxf)&(y>=yf)&(y<yf+qf.shape[0]*dyf))
   h=q[:,:,0];hm=q[:,:,3];vol+=float((h[keep]).sum()*dx*dy);mass+=float(((1000*h+1700*hm)[keep]).sum()*dx*dy);finite &= bool(np.isfinite(q).all());minh=min(minh,float(h.min()));v=np.hypot(q[:,:,1],q[:,:,2])/np.maximum(h,1e-30);maxspeed=max(maxspeed,float(v[(h>=.1)&keep].max()) if np.any((h>=.1)&keep) else 0)
  hist.append({'time_s':t,'volume_m3':vol,'total_mass_kg':mass,'min_depth_m':minh,'finite':finite,'max_horizontal_speed_m_s':maxspeed,'amr_patches':len(patches)})
 result.append({'benchmark':'official_DClaw_gully','execution_returncode':ex['returncode'],'execution_sha256':sha(e),'frames':len(hist),'requested_horizon_s':100,'actual_end_s':hist[-1]['time_s'] if hist else None,'history':hist,'all_states_finite':all(x['finite'] for x in hist),'minimum_depth_m':min((x['min_depth_m'] for x in hist),default=None),'end_mass_change_fraction':hist[-1]['total_mass_kg']/hist[0]['total_mass_kg']-1 if hist else None,'amr_accounting':'Coarse cellcentres coveredby finerpatches excluded; no doublecountingAMRlevels','optional_plotting_failure_and_bypass':'original numericalsource unchanged; skippedplotonly after registered compatibilityfailure','local_independent_validation_event':False})
(P/'results/official_benchmarks.json').write_text(json.dumps({'analysed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'benchmarks':result,'validates_local_event_accuracy':False},indent=2)+'\n');print(json.dumps([{k:v for k,v in r.items() if k!='history'} for r in result],indent=2))
