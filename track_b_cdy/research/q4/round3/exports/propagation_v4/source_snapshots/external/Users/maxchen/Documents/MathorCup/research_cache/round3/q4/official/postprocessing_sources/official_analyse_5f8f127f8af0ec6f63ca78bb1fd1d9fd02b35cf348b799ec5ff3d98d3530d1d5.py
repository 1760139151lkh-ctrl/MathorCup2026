#!/usr/bin/env python3
"""Parse actual official outputs, never substitute solver exit status for science checks."""
from pathlib import Path
import hashlib
PARSER_SOURCE_BYTES=Path(__file__).read_bytes();PARSER_SHA256=hashlib.sha256(PARSER_SOURCE_BYTES).hexdigest();FIELDS_SCHEMA='v4_phase_depth_stationary'
import numpy as np,rasterio,json,csv,re,hashlib,datetime
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from official_catalogue import applicability
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
PARSER_ARCHIVE=C/'postprocessing_sources'/('official_analyse_'+PARSER_SHA256+'.py');PARSER_ARCHIVE.parent.mkdir(exist_ok=True)
if not PARSER_ARCHIVE.exists():PARSER_ARCHIVE.write_bytes(PARSER_SOURCE_BYTES)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def native_ravaflow_times(summary_text,log_text):
 """Only explicit native nout/tsum rows; never infer t from frame index."""
 times={}
 for text in [summary_text,log_text]:
  for line in text.splitlines():
   z=line.split()
   if len(z)>8 and z[0].isdigit():
    try:
     t=float(z[4])
     if np.isfinite(t):times[int(z[0])]=t
    except ValueError:pass
 return times
def solver_identity(folder,case,ex):
 """Describe the binary actually selected, separately from archived official source."""
 log=(folder/'run.log').read_text(errors='replace');build=ex.get('solver_build',case.get('solver_build','official_original'));resourcefix=build=='explicit_resourcefix_build';binary=None;path=None;evidence=None
 if case['model'].startswith('ravaflow'):
  matches=re.findall(r'(?m)^([a-f0-9]{64})\s+(/\S*/r\.avaflow\.main)\s*$',log)
  if matches:binary,path=matches[-1];evidence='sha256sum_in_this_execution_log'
 else:
  p=folder/'xdclaw'
  if p.exists():binary=sha(p);path=str(p);evidence='copied_executed_xdclaw_in_this_run'
 if binary is None:
  snapshot=P/'sources/official_source_identity.json'
  if snapshot.exists():
   verified=json.loads(snapshot.read_text());target='r.avaflow.main' if case['model'].startswith('ravaflow') else 'xdclaw'
   for line in verified.get('binary_hash_stdout','').splitlines():
    z=line.split()
    if len(z)==2 and z[1].endswith('/'+target):binary,path=z;evidence='same_shared_container_binary_snapshot_'+verified['checked_utc']
 command=ex.get('command',[]);addon=[x for x in command if isinstance(x,str) and x.endswith(':/resourcefix:ro')]
 return {'solver_build':build,'actual_binary_sha256':binary,'actual_binary_path':path,'binary_identity_evidence':evidence,'execution_image_id':ex.get('image_id'),'base_image_id':ex.get('base_image_id',ex.get('image_id')),'container_id':ex.get('container_id'),'readonly_addon_mount':addon[0] if addon else None,'official_source_archive_preserved':True,'executed_solver_source_modified':resourcefix,'source_modification_scope':'45 resource cleanup Segment_release to Segment_close calls only' if resourcefix else 'official fixed native source','physical_equations_modified':False}
def raster(p):
 with rasterio.open(p) as d:a=d.read(1).astype(float);nodata=d.nodata;tr=d.transform
 if nodata is not None:a[a==nodata]=0
 return a,tr
def frame_dclaw(folder,suffix):
 text=(folder/f'fort.t{suffix}').read_text().splitlines();vals=[x.split()[0] for x in text if x.strip()];t=float(vals[0]);ng=int(vals[2]);ghost=int(vals[5]);nq=int(vals[1])
 qlines=[x for x in (folder/f'fort.q{suffix}').read_text().splitlines() if x.strip()]
 if vals[6].lower()=='ascii':
  cursor=0;patches=[]
  for j in range(ng):
   hh=[x.split()[0] for x in qlines[cursor:cursor+8]];cursor+=8;nx=int(hh[2]);ny=int(hh[3]);q=np.array([[float(y.replace('D','E')) for y in x.split()] for x in qlines[cursor:cursor+nx*ny]]).reshape(ny,nx,nq);cursor+=nx*ny;patches.append((q,float(hh[4]),float(hh[5]),float(hh[6]),float(hh[7])))
  return t,patches
 head=[x.split()[0] for x in qlines]
 raw=np.fromfile(folder/f'fort.b{suffix}',dtype='<f8');off=0;patches=[]
 for j in range(ng):
  hh=head[j*8:(j+1)*8];nx=int(hh[2]);ny=int(hh[3]);x0=float(hh[4]);y0=float(hh[5]);dx=float(hh[6]);dy=float(hh[7]);n=nq*(nx+2*ghost)*(ny+2*ghost)
  q=raw[off:off+n].reshape(ny+2*ghost,nx+2*ghost,nq)[ghost:-ghost,ghost:-ghost,:];off+=n;patches.append((q,x0,y0,dx,dy))
 if off!=len(raw):raise ValueError('DClaw binary byte layout mismatch')
 return t,patches

def main():
 runs=[];metrics=[];arrivals=[];hist=[];validation=[];fields=[]
 for folder in sorted((C/'runs').glob('*')):
  if not (folder/'case.json').exists() or not (folder/'execution.json').exists():continue
  case=json.loads((folder/'case.json').read_text());ex=json.loads((folder/'execution.json').read_text())
  if ex.get('log_sha256')!=sha(folder/'run.log'):continue # Active retry log must not inherit previous attempt metadata.
  identity=solver_identity(folder,case,ex);identity['applicability_decision']=applicability().get(case['run_id'],{}).get('decision','required')
  if ex.get('quality_gate'):
   runs.append({'run_id':case['run_id'],'scenario_id':case['scenario_id'],'model':case['model'],'resolution_m':case['resolution_m'],'status':'quarantined_configuration','role':'excluded_configuration','quality_gate':ex['quality_gate'],'image_id':ex.get('image_id')});validation.append({'run_id':case['run_id'],'quality_gate':ex['quality_gate'],'excluded_from_scientific_comparison':True,'reason':'single phase SURFACE2 source bounds risk, original logs/partialfields retained'});continue
  runid=case['run_id'];dx=case['resolution_m'];frames=[];speedframes=[];phaseframes=[];pbframes=[];mframes=[];boundary_flux_rates=[];horizontal_speedframes=[];initial_effective_bed=None;stationary_criterion_speed_final=None;base_change_final=None;source=raster(Path(case['release']))[0]
  status='missing';check={'run_id':runid,'exit_code':ex['returncode'],'case_sha256':sha(folder/'case.json'),'execution_sha256':sha(folder/'execution.json'),'log_sha256':sha(folder/'run.log'),'warnings':[]}
  check['case_matches_execution_record']=ex.get('case_sha256')==check['case_sha256'];check['dem_sha256']=sha(case['dem']);check['release_sha256']=sha(case['release']);check['input_hashes_match_case']=check['dem_sha256']==case.get('dem_sha256') and check['release_sha256']==case.get('release_sha256');check['phase_fraction_basis']='volume';check['initial_phase_volume_fractions']=case['phase_volume_fractions'];check['phase_fractions_sum']=float(sum(case['phase_volume_fractions']))
  if case['model'].startswith('ravaflow'):
   ascii_dir=folder/f'{runid}_results'/f'{runid}_ascii';files=folder/f'{runid}_results'/f'{runid}_files';nout=files/f'{runid}_nout1.txt';summ=files/f'{runid}_summary.txt'
   if nout.exists():
    vals=nout.read_text().split();check['solver_success_field']=int(vals[1]);check['nout']=int(vals[0]);check['native_global_cumulative_speed_scalar_m_s']=float(vals[15]);check['reported_outflow_volume_m3']=[float(x) for x in vals[26:29]];check['native_signed_entrainment_phase_volumes_m3']=[float(x) for x in vals[23:26]]
    status='completed' if int(vals[1])==1 and ex['returncode']==0 else 'numerical_failure'
   elif ex['returncode']!=0:status='numerical_failure'
   log=(folder/'run.log').read_text(errors='replace');check['log_contains_ERROR']='ERROR:' in log;check['log_contains_numerical_failure']='NUMERICAL FAILURE' in log;check['pipeline_returncode']=ex['returncode'];check['program_sigsegv_minus11_reported']='return code -11' in log or 'Segmentation fault' in log
   if check['log_contains_ERROR'] or check['log_contains_numerical_failure']:status='numerical_failure'
   # A SIGSEGV before fclose can leave summary unflushed; stdout contains actual tsum.
   times=native_ravaflow_times(summ.read_text() if summ.exists() else '',log)
   check['native_output_time_resolution_seconds']=.1;check['frame_index_times_interval_used']=False;check['frames_without_native_time']=[]
   for f in sorted(ascii_dir.glob(f'{runid}_hflow[0-9][0-9][0-9][0-9].asc')):
    ix=int(f.stem[-4:])
    if ix not in times:check['frames_without_native_time'].append(ix);continue
    h,tr=raster(f);t=times[ix];frames.append((t,h));s=[];ph=[]
    if case['model']=='ravaflow_single':
     vf=ascii_dir/f'{runid}_vflow{ix:04d}.asc';s=raster(vf)[0] if vf.exists() else np.full_like(h,np.nan);ph=[h]
    else:
     for k in range(1,4):
      ph.append(raster(ascii_dir/f'{runid}_hflow{k}{ix:04d}.asc')[0]);vf=ascii_dir/f'{runid}_vflow{k}{ix:04d}.asc';s.append(raster(vf)[0] if vf.exists() else np.full_like(h,np.nan))
     s=np.maximum.reduce(s)
    speedframes.append(s);phaseframes.append(ph)
    hspeed=[];residual_speed=[]
    for phaseindex,tag in enumerate([''] if case['model']=='ravaflow_single' else ['1','2','3']):
     xf=ascii_dir/f'{runid}_vflowx{tag}{ix:04d}.asc';yf=ascii_dir/f'{runid}_vflowy{tag}{ix:04d}.asc'
     if xf.exists() and yf.exists():
      raw_norm=np.hypot(raster(xf)[0],raster(yf)[0]);hspeed.append(np.where(ph[phaseindex]>=.1,raw_norm/np.maximum(ph[phaseindex],1e-30),0));residual_speed.append(np.where(ph[phaseindex]>=1e-6,raw_norm/np.maximum(ph[phaseindex],1e-30),0))
     else:hspeed.append(np.full_like(h,np.nan));residual_speed.append(np.full_like(h,np.nan))
    horizontal_speedframes.append(np.maximum.reduce(hspeed))
    stationary_criterion_speed_final=np.maximum.reduce(residual_speed)
   check['native_output_time_evidence_complete']=not check['frames_without_native_time']
   if check['frames_without_native_time']:status='missing'
   bc=ascii_dir/f'{runid}_basechange_fin.asc'
   if bc.exists():base_change_final=raster(bc)[0]
   pc=files/f'{runid}_paramcomm.txt'
   if pc.exists():
    params=pc.read_text();check['native_paramcomm_path']=str(pc);check['native_paramcomm_sha256']=sha(pc)
    if case.get('erodible_bed'):check['native_entrainment_parameter_lines']=[line for line in params.splitlines() if 'Entrainment and deposition control' in line or 'Maximum height of entrainment MIXTURE' in line or 'Log 10 of entrainment coefficient' in line];check['native_entrainment_input_slot_verified']='Maximum height of entrainment MIXTURE or PHASE 1 map\terodible_bed' in params and 'Entrainment and deposition control (0=no, 1-4=type of approach)\t1' in params and 'Log 10 of entrainment coefficient\t-7.00' in params
  else:
   ts=sorted(folder.glob('fort.t[0-9][0-9][0-9][0-9]'));lastt=0
   for tf in ts:
    t,patches=frame_dclaw(folder,tf.name[-4:]);lastt=t
    if len(patches)!=1:raise ValueError('Regional configured AMR1 expected one patch')
    q,x0,y0,gdx,gdy=patches[0];q=q[::-1].copy();h=q[:,:,0];tr=rasterio.transform.from_origin(x0,y0+q.shape[0]*gdy,gdx,gdy);frames.append((t,h));v=np.hypot(q[:,:,1],q[:,:,2])/np.maximum(h,1e-30);v[h<.1]=0;speedframes.append(v);horizontal_speedframes.append(v);initial_effective_bed=q[:,:,7]-h if t==0 else initial_effective_bed;phaseframes.append([q[:,:,3],h-q[:,:,3]]);pbframes.append(q[:,:,4]);mframes.append(np.where(h>.1,q[:,:,3]/np.maximum(h,1e-30),np.nan));rho_local=1000+1700*np.where(h>1e-12,q[:,:,3]/np.maximum(h,1e-30),0);boundary_flux_rates.append(float(dx*(np.sum(rho_local[:,-1]*q[:,-1,1])-np.sum(rho_local[:,0]*q[:,0,1])+np.sum(rho_local[0,:]*q[0,:,2])-np.sum(rho_local[-1,:]*q[-1,:,2]))))
   status='completed' if ex['returncode']==0 and lastt>=case['end_seconds']-.01 else ('numerical_failure' if ex['returncode']!=0 else 'missing')
   check['actual_last_time_seconds']=lastt
   stationary_criterion_speed_final=horizontal_speedframes[-1] if horizontal_speedframes else None
  row={'run_id':runid,'scenario_id':case['scenario_id'],'model':case['model'],'resolution_m':dx,'thickness_m':case['release_thickness_m'],'mu_basal':case['mu_basal'],'xi':case['xi'],'status':status,'frames':len(frames),'elapsed_seconds':ex['elapsed_seconds'],'image_id':ex['image_id'],'csurface':case.get('csurface',2) if case['model'].startswith('ravaflow') else None,'official_protocol_version':case.get('official_protocol_version','q4-r3-official-v1'),'role':case.get('evidence_role','conditional_scenario'),**identity};runs.append(row);check.update(identity)
  if not frames:
   validation.append(check)
   for target in case['targets']:arrivals.append({'run_id':runid,'target':target['id'],'status':'numerical_failure' if status=='numerical_failure' else 'missing','arrival_seconds':None,'evaluation_end_time_seconds':None,'source_fields_path':None,'source_fields_sha256':None,'execution_sha256':check['execution_sha256'],'log_sha256':check['log_sha256'],'case_sha256':check['case_sha256'],'arrival_definition':'first saved output at any cell centre within100m, h>=0.1m','initiation_to_release_delay_seconds':None,**identity})
   continue
  if case['model'].startswith('ravaflow'):
   raw_ascii_transform=list(tr)
   with rasterio.open(case['dem']) as executed_dem:
    if executed_dem.shape!=frames[0][1].shape:raise ValueError('Output-vs-executed DEM shape differs; cannot silently remap')
    tr=executed_dem.transform
   check['raw_ascii_header_transform']=raw_ascii_transform;check['evaluated_computational_grid_transform']=list(tr);check['coordinate_rule']='Known regional execution DEM affine; rawASCII usesxllcenter/yllcenter forboundaries, halfcell audit sources/official_ascii_georeference_review.json; rawbytes unchanged'
  hs=np.stack([h for t,h in frames]);times=np.array([t for t,h in frames]);vs=np.stack(speedframes);maxh=hs.max(0);velocity_available=bool(np.isfinite(vs).any());maxv=np.where(hs>=.1,vs,0).max(0) if velocity_available else np.full_like(maxh,np.nan);horizontal=np.stack(horizontal_speedframes);horizontal_available=bool(np.isfinite(horizontal).any());max_horizontal=np.where(hs>=.1,horizontal,0).max(0) if horizontal_available else np.full_like(maxh,np.nan);total=hs.sum((1,2))*dx*dx;phasevol=np.array([[ph.sum()*dx*dx for ph in phases] for phases in phaseframes]);rho=np.array([case.get('bulk_density_kg_m3',2105)] if case['model']=='ravaflow_single' else (case.get('densities_kg_m3',[2700,1850,1000]) if case['model']=='ravaflow_multi' else [2700,1000]));mass=phasevol@rho
  boundary_mask=np.zeros(maxh.shape,bool);boundary_mask[[0,-1],:]=True;boundary_mask[:,[0,-1]]=True;boundary_hit=np.any(hs[:,boundary_mask]>=.1,axis=1);first_boundary_time=float(times[np.flatnonzero(boundary_hit)[0]]) if boundary_hit.any() else None
  yy,xx=np.indices(maxh.shape);xs=tr.c+(xx+.5)*dx;ys=tr.f-(yy+.5)*dx
  for target in case['targets']:
   dist=(xs-target['xy'][0])**2+(ys-target['xy'][1])**2;mask=dist<=target['buffer_m']**2
   if not mask.any():ast='out_of_domain';arr=None
   else:
    hit=np.any(hs[:,mask]>=.1,axis=1);arr=float(times[np.flatnonzero(hit)[0]]) if hit.any() else None;ast='arrival' if arr is not None else ('not_arrived_by_horizon' if status=='completed' else ('missing' if status=='missing' else 'numerical_failure'))
    if check.get('frames_without_native_time'):arr=None;ast='missing'
   arrivals.append({'run_id':runid,'target':target['id'],'status':ast,'arrival_seconds':arr,'evaluation_end_time_seconds':float(times[-1]),'requested_horizon_seconds':case['end_seconds'],'first_boundary_threshold_time_seconds':first_boundary_time,'domain_affected_before_arrival':first_boundary_time is not None and (arr is None or first_boundary_time<arr),'previous_below_threshold_time_seconds':float(times[np.flatnonzero(hit)[0]-1]) if arr is not None and np.flatnonzero(hit)[0]>0 else None,'arrival_definition':'first saved output at any cell centre within100m, h>=0.1m','max_target_depth_m':float(maxh[mask].max()) if mask.any() else None,'initiation_to_release_delay_seconds':None})
  edge=np.zeros(maxh.shape,bool);edge[[0,-1],:]=True;edge[:,[0,-1]]=True
  chk={'finite':bool(np.isfinite(hs).all() and (not velocity_available or np.isfinite(vs).all())),'velocity_fields_available':velocity_available,'first_boundary_threshold_time_seconds':first_boundary_time,'minimum_depth_m':float(hs.min()),'nonnegative_to_1e-8':bool(hs.min()>=-1e-8),'boundary_depth_ge01':bool(np.any(maxh[edge]>=.1)),'first_output_volume_m3':float(total[0]),'requested_release_volume_m3':case['release_grid_volume_m3'],'initial_volume_relative_difference':float((total[0]-case['release_grid_volume_m3'])/case['release_grid_volume_m3']),'initial_depth_normalized_L1_difference':float(np.sum(np.abs(hs[0]-source))/np.sum(source)) if hs[0].shape==source.shape else None,'initial_supplied_support_cells':int((source>1e-6).sum()),'initial_native_support_cells':int((hs[0]>1e-6).sum()),'initial_depth_vs_supplied_mae_m':float(np.mean(np.abs(hs[0]-source))) if hs[0].shape==source.shape else None,'initial_depth_vs_supplied_max_difference_m':float(np.max(np.abs(hs[0]-source))) if hs[0].shape==source.shape else None,'end_volume_change_fraction':float(total[-1]/total[0]-1),'end_total_mass_change_fraction':float(mass[-1]/mass[0]-1),'conservation_scope':'DClaw volume may evolve through dilation; total solid+fluid mass diagnostic; open boundary loss is not residual correction','actual_last_time_seconds':float(times[-1])};check.update(chk);check['state_field_horizon_complete']=bool(times[-1]>=case['end_seconds']-.01);check['native_integration_success_flag']=check.get('solver_success_field');check['pipeline_status']='completed' if ex['returncode']==0 else 'nonzero_program_or_postprocessing_failure'
  if case['model'].startswith('ravaflow'):
   core=np.zeros(maxh.shape,bool);core[3:-3,3:-3]=True;corevol=np.array([ph[core].sum()*dx*dx for ph in phaseframes[-1]]);outvol=np.array(check.get('reported_outflow_volume_m3',[0,0,0])[:len(rho)]);signed_entr=np.array(check.get('native_signed_entrainment_phase_volumes_m3',[0,0,0])[:len(rho)]);added_mass=float(-signed_entr@rho);check['native_active_interior_final_phase_volumes_m3']=corevol.tolist();check['native_edge_store_outflow_phase_volumes_m3']=outvol.tolist();check['native_entrained_added_mass_kg']=added_mass;check['native_mass_budget_relative_residual']=float((corevol@rho+outvol@rho-mass[0]-added_mass)/mass[0]);check['native_budget_definition']='Mfinal active interior excluding3edge rings + Mofficial edgestore - Minitial - Mentrained; Mentrained=-signednativeVE*density; no phase transformation; notdoublecountingedge rasters';check['native_mass_budget_estimate_representation']='activecore andinitialphasevolumes fromsavedASCII, roundedheight output; separate nativeinternal unscaledsummary budget whenavailable'
   native_summary_volumes=[]
   if summ.exists():
    check['native_summary_path']=str(summ);check['native_summary_sha256']=sha(summ)
    for line in summ.read_text().splitlines():
     z=line.split()
     if z and z[0].isdigit():
      try:
       vv=[float(z[7])] if case['model']=='ravaflow_single' else [float(x) for x in z[11:14]]
       if len(vv)==len(rho):native_summary_volumes.append((int(z[0]),float(z[4]),np.array(vv)))
      except (ValueError,IndexError):pass
   if native_summary_volumes and native_summary_volumes[0][0]==0 and abs(native_summary_volumes[-1][1]-times[-1])<.051:
    nv0=native_summary_volumes[0][2];nvf=native_summary_volumes[-1][2];check['native_internal_summary_initial_phase_volumes_m3']=nv0.tolist();check['native_internal_summary_final_phase_volumes_m3']=nvf.tolist();check['native_internal_summary_mass_budget_relative_residual']=float((nvf@rho+outvol@rho-nv0@rho-added_mass)/(nv0@rho));check['native_internal_summary_volume_units']='m3 fromunscaled *_summary.txt, notstdout volumes/1000; sourceC4808-4820/8323-8347; excludes cstopped/dry states per7619'
   if case.get('erodible_bed'):
    check['erodible_bed_sha256']=sha(case['erodible_bed']);check['erodible_bed_hash_matches_case']=check['erodible_bed_sha256']==case['erodible_bed_sha256'];check['available_bed_volume_m3']=case['max_available_bed_volume_m3'];check['native_entrained_added_volume_m3']=float(-signed_entr.sum());check['remaining_bed_capacity_m3']=float(case['max_available_bed_volume_m3']+signed_entr.sum());check['entrainment_within_prescribed_volume_capacity']=bool(-signed_entr.sum()<=case['max_available_bed_volume_m3']+.5)
    bed=raster(case['erodible_bed'])[0];check['native_bed_import_all_domain_valid']=f'n={bed.size}' in log and 'null_cells=0' in log;check['native_bed_import_min0_max1']='min=0' in log and 'max=1' in log;check['input_bed_grid_volume_m3']=float(bed.sum()*dx*dx)
    if base_change_final is not None:check['basechange_final_min_m']=float(base_change_final.min());check['basechange_final_max_m']=float(base_change_final.max());check['basechange_grid_signed_volume_m3']=float(base_change_final.sum()*dx*dx);check['basechange_outside_erodible_mask_max_abs_m']=float(np.abs(base_change_final[bed==0]).max());check['basechange_cellwise_within_bed_capacity']=bool(np.all(base_change_final>=-bed-.00101));check['remaining_bed_from_saved_basechange_m3']=float(np.maximum(bed+base_change_final,0).sum()*dx*dx)
  if initial_effective_bed is not None:
   supplied_bed=raster(Path(case['dem']))[0];delta_bed=initial_effective_bed-supplied_bed;check['initial_effective_bed_vs_input_mae_m']=float(np.mean(np.abs(delta_bed)));check['initial_effective_bed_vs_input_rmse_m']=float(np.sqrt(np.mean(delta_bed**2)));check['initial_effective_bed_vs_input_max_abs_m']=float(np.max(np.abs(delta_bed)))
  if pbframes:
   pb=np.stack(pbframes);m=np.stack(mframes);wet=hs>=.1;overburden=(1000+1700*np.nan_to_num(m))*9.81*hs;check['pressure_all_finite']=bool(np.isfinite(pb).all());check['wet_pressure_min_Pa']=float(pb[wet].min());check['wet_pressure_max_Pa']=float(pb[wet].max());check['wet_solid_fraction_min']=float(np.nanmin(m));check['wet_solid_fraction_max']=float(np.nanmax(m));check['wet_max_pressure_over_total_overburden']=float((pb/np.maximum(overburden,1e-30))[wet].max());check['wet_min_effective_stress_Pa']=float((overburden-pb)[wet].min());integrated=float(np.trapezoid(boundary_flux_rates,times));check['estimated_boundary_mass_out_kg']=integrated;check['estimated_boundary_adjusted_mass_residual_fraction']=float((mass[-1]+integrated-mass[0])/mass[0]);check['boundary_estimate_scope']='trapezoidal integration of saved boundary-cell rho*hu/rho*hv; diagnostic approximation, not native timestep flux budget';check['boundary_flux_sampling_sensitivity_residual_fractions']={str(step*case['output_interval_seconds']):float((mass[-1]+np.trapezoid(np.array(boundary_flux_rates)[list(range(0,len(times),step))+([] if (len(times)-1)%step==0 else [len(times)-1])],times[list(range(0,len(times),step))+([] if (len(times)-1)%step==0 else [len(times)-1])])-mass[0])/mass[0]) for step in [1,2,3]};check['native_mass_conservation_claim']=False
  phase_stack=np.array(phaseframes);phase_sum_difference=phase_stack.sum(axis=1)-hs;check['phase_depth_sum_vs_total_max_abs_m']=float(np.max(np.abs(phase_sum_difference)));check['phase_depth_sum_vs_total_normalized_L1']=float(np.sum(np.abs(phase_sum_difference))/np.sum(hs));check['phase_depth_all_finite']=bool(np.isfinite(phase_stack).all());check['phase_depth_min_m']=float(phase_stack.min())
  empty_phases=[k for k,name in enumerate(case.get('phase_material_names',[])) if name=='empty']
  if empty_phases:check['prescribed_empty_phase_max_abs_depth_m']={str(k+1):float(np.abs(phase_stack[:,k]).max()) for k in empty_phases};check['prescribed_empty_phase_max_abs_volume_m3']={str(k+1):float(np.abs(phasevol[:,k]).max()) for k in empty_phases}
  validation.append(check)
  native_h=None;native_v=None
  if case['model'].startswith('ravaflow'):
   nf=ascii_dir/f'{runid}_hflow_max.asc'
   if nf.exists():native_h=raster(nf)[0]
   vfiles=[ascii_dir/f'{runid}_vflow_max.asc'] if case['model']=='ravaflow_single' else [ascii_dir/f'{runid}_vflow{k}_max.asc' for k in range(1,4)]
   if all(f.exists() for f in vfiles):native_v=np.maximum.reduce([raster(f)[0] for f in vfiles])
  metrics.append({'run_id':runid,'native_cumulative_max_depth_m':float(native_h.max()) if native_h is not None else None,'native_cumulative_max_speed_m_s':float(native_v.max()) if native_v is not None else None,'model':case['model'],'resolution_m':dx,'status':status,'max_depth_over_saved_outputs_m':float(maxh.max()),'max_speed_over_saved_outputs_m_s':float(maxv.max()) if velocity_available else None,'speed_definition':'native terrain-corrected scalar' if case['model'].startswith('ravaflow') else 'horizontalE/N hypot(hu,hv)/h withbed_normal0','max_horizontal_speed_over_saved_outputs_m_s':float(max_horizontal.max()) if horizontal_available else None,'native_global_cumulative_speed_scalar_m_s':check.get('native_global_cumulative_speed_scalar_m_s'),'peak_sampling_definition':'saved outputs, nominal20s with actual native times','state_field_horizon_complete':check['state_field_horizon_complete'],'pipeline_returncode':ex['returncode'],'csurface':case.get('csurface',2) if case['model'].startswith('ravaflow') else None,'impact_area_m2':int((maxh>=.1).sum())*dx*dx,'end_volume_m3':float(total[-1]),'end_mass_kg':float(mass[-1]),'mass_change_fraction':chk['end_total_mass_change_fraction'],'native_mass_budget_relative_residual':check.get('native_mass_budget_relative_residual'),'native_internal_summary_mass_budget_relative_residual':check.get('native_internal_summary_mass_budget_relative_residual'),'estimated_boundary_adjusted_mass_residual_fraction':check.get('estimated_boundary_adjusted_mass_residual_fraction'),'boundary_touched':chk['boundary_depth_ge01'],'last_time_s':float(times[-1])})
  for k,t in enumerate(times):hist.append({'run_id':runid,'time_s':float(t),'volume_m3':float(total[k]),'mass_kg':float(mass[k]),'max_depth_m':float(hs[k].max()),'max_speed_m_s':float(np.where(hs[k]>=.1,vs[k],0).max()) if velocity_available else None,'max_horizontal_speed_m_s':float(np.where(hs[k]>=.1,horizontal[k],0).max()) if horizontal_available else None,'phase_volumes_m3':json.dumps(phasevol[k].tolist()),'mean_wet_pressure_Pa':float(np.mean(pbframes[k][hs[k]>=.1])) if pbframes and np.any(hs[k]>=.1) else None,'mean_solid_volume_fraction':float(np.nanmean(mframes[k])) if mframes else None})
  output=folder/('summary_fields_'+FIELDS_SCHEMA+'_'+PARSER_SHA256[:12]+'.npz')
  if not output.exists():np.savez_compressed(output,time_s=times,depth_max=maxh,speed_max=maxv,depth_max_native_cumulative=np.array([]) if native_h is None else native_h,speed_max_native_cumulative=np.array([]) if native_v is None else native_v,depth_final=hs[-1],depth_frames=hs.astype('float32'),phase_depth_frames=np.array(phaseframes,dtype='float32'),phase_material_names=np.array(case.get('phase_material_names',['equivalent_bulk'] if case['model']=='ravaflow_single' else ['solid','fluid'] if case['model']=='dclaw' else ['native_phase_1','native_phase_2','native_phase_3'])),speed_frames=vs.astype('float32'),horizontal_speed_frames=horizontal.astype('float32'),stationary_criterion_speed_final=np.array([]) if stationary_criterion_speed_final is None else stationary_criterion_speed_final,base_change_final_m=np.array([]) if base_change_final is None else base_change_final,initial_effective_bed=np.array([]) if initial_effective_bed is None else initial_effective_bed,volume_m3=total,mass_kg=mass,phase_volume_m3=phasevol,transform=np.array(tr),boundary_mass_flux_kg_s=np.array(boundary_flux_rates),pressure_frames=np.array(pbframes,dtype='float32'),solid_fraction_frames=np.array(mframes,dtype='float32'))
  fieldhash=sha(output);exec_hash=sha(folder/'execution.json');loghash=sha(folder/'run.log');check.update({'source_fields_path':str(output),'source_fields_sha256':fieldhash,'execution_sha256':exec_hash,'log_sha256':loghash,'parser_sha256_at_start':PARSER_SHA256,'parser_source_snapshot_path':str(PARSER_ARCHIVE),'fields_schema':FIELDS_SCHEMA})
  for linked in runs+metrics+arrivals+hist:
   if linked.get('run_id')==runid:linked.update({'source_fields_path':str(output),'source_fields_sha256':fieldhash,'execution_sha256':exec_hash,'log_sha256':loghash,'case_sha256':sha(folder/'case.json'),'parser_sha256_at_start':PARSER_SHA256,'parser_source_snapshot_path':str(PARSER_ARCHIVE),'fields_schema':FIELDS_SCHEMA,**identity})
  fields.append({'run_id':runid,'path':str(output),'bytes':output.stat().st_size,'sha256':fieldhash,'role':'actual_official_process_fields','case_sha256':sha(folder/'case.json'),'execution_sha256':exec_hash,'log_sha256':loghash,'image_id':ex['image_id'],'time_end_seconds':float(times[-1]),'native_time_evidence':'flushed summary or native stdout tsum; no frame index time inference','parser_sha256_at_start':PARSER_SHA256,'parser_source_snapshot_path':str(PARSER_ARCHIVE),'fields_schema':FIELDS_SCHEMA,**identity})
 def writecsv(name,rows):
  if not rows:return
  names=list(dict.fromkeys(k for d in rows for k in d))
  with (P/'results'/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)
 writecsv('official_runs.csv',runs);writecsv('official_metrics.csv',metrics);writecsv('official_arrivals.csv',arrivals);writecsv('official_histories.csv',hist)
 (P/'results/official_validation.json').write_text(json.dumps({'analysed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':validation,'independent_local_event_validation_count':0,'official_source_archive_preserved':True,'executed_solver_modification_identity':'reported per run; resourcefix binaries explicitly modified'},indent=2)+'\n');(P/'results/official_fields.json').write_text(json.dumps({'fields':fields},indent=2)+'\n')
 # Common axes/maps for baseline competitors, actual file hashes later recorded by root visual review.
 baselines=[f for f in fields if f['run_id'] in ['copdem_120_single_ref__sf0','copdem_120_multi_ref__sf0','copdem_120_dclaw_ref']]
 if baselines:
  fig,ax=plt.subplots(1,len(baselines),figsize=(5*len(baselines),4),layout='constrained');ax=np.atleast_1d(ax)
  for axis,f in zip(ax,baselines):
   d=np.load(f['path']);h=d['depth_max'];im=axis.imshow(np.where(h>=.1,np.log10(np.maximum(h,1e-30)),np.nan),origin='upper',vmin=-1,vmax=2,cmap='magma');axis.set_title(f['run_id'].replace('copdem_120_',''));axis.set_xlabel('Grid column, east');axis.set_ylabel('Grid row, south')
  fig.colorbar(im,ax=ax.tolist(),label='log10(max depth / m)');fig.suptitle('Official solvers: conditional source and terrain; 120 m');fig.savefig(P/'figures/official_max_depth.png',dpi=160);plt.close(fig)
 if hist and baselines:
  fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained')
  for f in baselines:
   hh=[x for x in hist if x['run_id']==f['run_id']];ax[0].plot([x['time_s'] for x in hh],[x['max_horizontal_speed_m_s'] for x in hh],label=f['run_id'].replace('copdem_120_',''));m0=hh[0]['mass_kg'];ax[1].plot([x['time_s'] for x in hh],[x['mass_kg']/m0 for x in hh],label=f['run_id'].replace('copdem_120_',''))
  ax[0].set(xlabel='Seconds after sizeable release',ylabel='Peak wet horizontal speed (m/s)');ax[1].set(xlabel='Seconds after sizeable release',ylabel='Domain mass / initial mass');ax[0].legend();ax[1].legend();fig.suptitle('Saved native states; domain mass is not a boundary-corrected budget');fig.savefig(P/'figures/official_process_histories.png',dpi=160);plt.close(fig)
 print(json.dumps({'runs':len(runs),'completed':sum(x['status']=='completed' for x in runs),'fields':len(fields)}))
if __name__=='__main__':main()
