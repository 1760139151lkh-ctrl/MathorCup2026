#!/usr/bin/env python3
"""Independent delta audit; no physics. Writes only this new review directory."""
import argparse,csv,datetime as dt,hashlib,json,math
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer
D=Path(__file__).resolve().parent;R=D.parents[3];ROOT=R.parents[3];OUT=D.parent
B=R/'inputs/q4/bundle_q4-r3-compact-delta-v1';E=B/'files/exports/compact_delta_v1'
CACHE=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
PIN='044a9a08ce09e8b2b5470a6a4351942fb08054e52e9728e2bb4d51a2295841ac'
PRODUCER='28c67deb49d694e992c005365cf19c73d1db31a89126f64dbe8b6973adba61cb'
MAP={'q2r3_SH_v1':('S_H','q2r3_S_H_analytic_v1'),'q2r3_STH_v1':('S_T_H','q2r3_S_T_H_analytic_v1')}
FIELDS=['theta_deg','thickness_normal_m','rock_volume_fraction','bridge_fraction','bridge_cohesion_kpa','rock_mu','initial_temp_c','diffusivity_m2_s','interface_depth_m','station_source_offset_c','storativity','drainage_hours','connected_depth_m','rain_multiplier','melt_mm_deg_day','damage_rate_h_inv','damage_exponent','initial_damage','drainage_damage_coupling','density_kg_m3']
inputs={}
def resolve(s):
 p=Path(s);return (p if p.is_absolute() else ROOT/p).resolve()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def reg(p,role):
 p=Path(p).resolve();assert p.is_relative_to(R) or p.is_relative_to(CACHE)
 x={'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),'bytes':p.stat().st_size,'sha256':sha(p),'roles':[role]}
 if str(p) in inputs:
  old=inputs[str(p)];assert x['sha256']==old['sha256'] and x['bytes']==old['bytes'];x['roles']=sorted(set(old['roles']+[role]))
 inputs[str(p)]=x;return p
def js(p,role):return json.loads(reg(p,role).read_text())
def rows(p,role):
 with reg(p,role).open(newline='') as s:return list(csv.DictReader(s))
def one(data,**keys):
 x=[r for r in data if all(r.get(k)==v for k,v in keys.items())];assert len(x)==1,(keys,len(x));return x[0]
def close(a,b,rtol=1e-10,atol=1e-8):return math.isclose(float(a),float(b),rel_tol=rtol,abs_tol=atol)
def flag(x):return x is True or str(x).lower()=='true'
def val(x):return float(x) if x not in ('',None) else None
def main():
 cli=argparse.ArgumentParser();cli.add_argument('--consumer',action='store_true');args=cli.parse_args()
 checks={};case_audit=[];target_audit=[]
 b=js(B/'bundle.json','pinned delta consumer packet');producer=reg(B/'upstream_bundle.json','pinned producer packet snapshot')
 checks['pinned_consumer_and_producer']=sha(B/'bundle.json')==PIN and sha(producer)==PRODUCER
 checks['48_unique_role_paths']=len(b['files'])==len(set(f['path'] for f in b['files']))==48
 external=set()
 for f in b['files']:
  p=resolve(f['path']);assert p.is_relative_to(B) or p.is_relative_to(CACHE) and f.get('storage')=='immutable_external_cache'
  reg(p,f['role']);checks['role_hash:'+str(p)]=sha(p)==f['sha256'] and p.stat().st_size==f['bytes']
  if p.is_relative_to(CACHE):external.add(p)
 assert all(checks.values())
 compact=E/'provenance/upstream_q2/release_states.csv';release=rows(compact,'original compact Q2 release states')
 upstream=js(E/'provenance/upstream_q2/upstream_bundle.json','original compact release manifest')
 checks['original_compact_table_byte_binding']=sha(compact)==one(upstream['files'],role='results/release_states.csv')['sha256']
 oldroot=R/'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1';newroot=R/'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1'
 pp=oldroot/'files/results/parameter_ensemble.csv';ap=newroot/'files/results/analytic_thermal/parameter_ensemble.csv';cp=newroot/'files/results/analytic_thermal/mechanism_contract.json'
 oldout=oldroot/'files/results/scenario_outcomes.csv';newout=newroot/'files/results/analytic_thermal/scenario_outcomes.csv'
 for root,paths in [(oldroot,[pp,oldout]),(newroot,[ap,cp,newout])]:
  m=js(root/'bundle.json','frozen Q3-imported mechanism manifest')
  for p in paths:
   f=[f for f in m['files'] if resolve(f['path'])==p.resolve()];assert len(f)==1
   reg(p,'frozen original/analytic parameters, outcomes or contract');checks['Q2_hash:'+str(p)]=sha(p)==f[0]['sha256'] and p.stat().st_size==f[0]['bytes']
 checks['compact_original_parameters_same_frozen_design']=sha(pp)==one(upstream['files'],role='results/parameter_ensemble.csv')['sha256']
 oldpars=rows(pp,'original physical parameters');newpars=rows(ap,'analytic physical parameters');contract=js(cp,'explicit analytic model replacement contract')
 oldglobal=rows(oldout,'original global and evaluation statuses');newglobal=rows(newout,'analytic global and evaluation statuses')
 onsets=rows(R/'results/engine_a/analytic_erfc/first_passages.csv','frozen analytic global first passages')
 runrows=rows(E/'model_runs.csv','2 delta native runs');tr=rows(E/'target_arrivals.csv','14 native target records');metrics=rows(E/'comparison_metrics.csv','separate native and ASCII budget diagnostics')
 points={x['target_id']:(float(x['x_m']),float(x['y_m'])) for x in rows(E/'geometry/spatial_targets_v2.csv','5 OSM representatives')}
 geo=js(E/'geometry/computational_geometries.geojson','paper candidate geometry, not exact compact source');project=Transformer.from_crs('EPSG:4326','EPSG:32645',always_xy=True)
 for f in geo['features']:
  if f['geometry']['type']=='Point':points[f['properties']['space_id']]=project.transform(*f['geometry']['coordinates'])
 checks['2_runs14_pairs7_representatives']=len(runrows)==2 and len(tr)==len(set((x['run_id'],x['target_id']) for x in tr))==14 and len(set(x['target_id'] for x in tr))==7
 checks['no_statistical_weights_no_independent_events']=b['probability_weights'] is None and b['independent_local_validation_events']==0
 for run in runrows:
  rid,base=run['run_id'],run['base_scenario_id'];pre=rid+':'
  c=js(E/f'provenance/{rid}/case.json','actual case '+rid);q=one(release,scenario_id=base);o=one(oldpars,scenario_id=base)
  mechanism,model=MAP[o['model_id']];a=one(newpars,base_scenario_id=base,model_id=model);on=one(onsets,base_scenario_id=base,model_id=model)
  oldg=one(oldglobal,scenario_id=base);newg=one(newglobal,base_scenario_id=base,model_id=model)
  line=one(b['lineage_by_run'],run_id=rid)
  checks[pre+'explicit_exact_analytic_replacement']=contract['model_ids'][mechanism]==model and q['model_id']==c['upstream_model_id']==o['model_id']==line['upstream_model_id'] and q['parameter_version']==c['upstream_parameter_version']==a['parameter_version']=='q2r3-design-v1'
  checks[pre+'20_physical_parameters_and_mechanical_identity']=all(close(o[k],a[k],rtol=1e-13,atol=1e-13) for k in FIELDS) and all(o[k]==a[k] for k in ['parameter_set_id','mechanism_id','law_policy','geometry_version'])
  checks[pre+'compact_mapping_not_fullmask_alias']=q['geometry_version']=='conditional_area_requires_q4_polygon_v1' and c['geometry_version']==line['geometry_version']=='q4-r3-q2-mapped-release-v1' and c['scenario_id']==base
  fractions=json.loads(q['phase_fractions']);hv=float(q['release_thickness_vertical_m']);area=float(q['plan_area_m2']);v=float(q['release_volume_m3'])
  checks[pre+'normal_vertical_area_volume_preserved']=close(q['release_thickness_normal_m'],o['thickness_normal_m']) and close(hv,float(o['thickness_normal_m'])/math.cos(math.radians(float(o['theta_deg'])))) and close(hv,c['release_thickness_m']) and area==c['source_plan_area_m2'] and close(v,area*hv)
  checks[pre+'H_does_not_invent_released_free_water']=fractions==c['passive_material_volume_fractions'] and fractions['free_water']==0 and c['phase_volume_fractions']==[1] and close(c['bulk_density_kg_m3'],float(q['density'])) and close(float(q['density']),917*fractions['ice']+2700*fractions['rock'])
  rp=Path(c['release']).resolve();assert rp in external
  with rasterio.open(rp) as ds:rel=ds.read(1).astype(float);tf=ds.transform;crs=str(ds.crs)
  positive=rel>0;vol=float(rel[positive].sum()*3600)
  checks[pre+'actual_TIFFF_case_and_parent_volume']=sha(rp)==c['release_sha256']==c['source_release_reference']['sha256'] and close(vol,c['release_grid_volume_m3']) and close(vol,v,rtol=1e-7) and crs=='EPSG:32645' and tf.a==60 and tf.e==-60 and tf.b==tf.d==0
  fe=one(b['files'],role='actual_official_process_fields',run_id=rid);fp=resolve(fe['path']);assert fp in external
  with np.load(fp,allow_pickle=False) as z:time=z['time_s'].copy();depth=z['depth_frames'].astype(float);trf=z['transform'].copy()
  native=depth[0]>0;lost=positive&~native;gain=native&~positive;t0=float(depth[0].sum()*3600);m=one(metrics,run_id=rid)
  checks[pre+'native_grid_finite_clock_and_t0']=time[0]==0 and np.all(np.diff(time)>0) and depth.shape[1:]==rel.shape and np.isfinite(depth).all() and depth.min()>=0 and np.array_equal(trf,np.array(tuple(tf))) and close(t0,m['initial_volume_m3'])
  checks[pre+'native_support_loss_explicit_rounding_only']=int(positive.sum())==int(m['initial_supplied_support_cells']) and int(native.sum())==int(m['initial_native_support_cells']) and not gain.any() and (rel[lost]<.00051).all() and abs(depth[0]-rel).max()<=.00051
  internal=reg(E/f'provenance/{rid}/native_internal_summary.txt','native internal initial/final volume '+rid)
  with internal.open() as f:native_rows=[x for x in csv.DictReader(f,delimiter='\t') if x['nout'].isdigit()]
  internal0=float(native_rows[0]['volume']);internal_final=float(native_rows[-1]['volume']);budget=internal_final/internal0-1
  checks[pre+'native_internal_budget_reproduced_without_qualification']=close(budget,m['native_internal_summary_mass_budget_relative_residual'],rtol=1e-8) and not any(flag(run[k]) for k in ['scientifically_qualified_for_prediction','mass_conservation_qualified','regional_accuracy_qualified','include_in_arrival_envelope'])
  checks[pre+'unknown_lag_preserved']=c['initiation_to_release_delay_seconds'] is None and line['initiation_to_release_delay_seconds'] is None and not run['initiation_to_release_delay_seconds']
  if base=='q2r3-p0072-S_H-linear':checks[pre+'never_cross_only_if_released']=on['status']=='no_cross_observed_complete' and c['if_released_propagation'] is True and not on['crossing_point_utc']
  else:checks[pre+'global_July1_not_window_initiation']=on['status']=='point_crossing_linear_between_samples' and on['crossing_lower_utc']=='2026-07-01T11:00:00+00:00' and on['crossing_upper_utc']=='2026-07-01T12:00:00+00:00' and on['crossing_point_utc']=='2026-07-01T11:01:09.649776747+00:00' and newg['evaluation_onset_status']=='left_censored_already_unstable'
  yy,xx=np.indices(rel.shape);xx=tf.c+(xx+.5)*tf.a;yy=tf.f+(yy+.5)*tf.e
  for target in [x for x in tr if x['run_id']==rid]:
   tid=target['target_id'];tx,ty=points[tid];mask=np.hypot(xx-tx,yy-ty)<=100;idx=np.flatnonzero(np.any(depth[:,mask]>=.1,axis=1)) if mask.any() else []
   i=int(idx[0]) if len(idx) else None;lo=float(time[i-1]) if i is not None and i>0 else None;hi=float(time[i]) if i is not None else None
   dx=np.maximum(abs(tx-xx[positive])-30,0);dy=np.maximum(abs(ty-yy[positive])-30,0);distance=float(np.hypot(dx,dy).min())
   checks[pre+'target:'+tid]=lo==val(target['arrival_bracket_lower_seconds']) and hi==val(target['arrival_bracket_upper_seconds']) and not any(flag(target[k]) for k in ['include_in_arrival_envelope','scientifically_qualified_for_prediction','mass_conservation_qualified','regional_accuracy_qualified']) and not target['initiation_to_release_delay_seconds']
   target_audit.append(dict(run_id=rid,target_id=tid,lower_seconds=lo,upper_seconds=hi,buffer_cells=int(mask.sum()),support_distance_m=distance))
  case_audit.append(dict(run_id=rid,base_scenario_id=base,original_model_id=o['model_id'],analytic_model_id=model,
   original_evaluation_status=oldg['evaluation_onset_status'],analytic_evaluation_status=newg['evaluation_onset_status'],analytic_global_status=on['status'],old_global_point_utc=oldg['crossing_time_utc'],analytic_global_point_utc=on['crossing_point_utc'],
   source_area_m2=area,source_vertical_thickness_m=hv,source_normal_thickness_m=float(q['release_thickness_normal_m']),Q2_parent_volume_m3=v,actual_TIFF_volume_m3=vol,native_saved_t0_volume_m3=t0,
   supplied_support_cells=int(positive.sum()),native_saved_support_cells=int(native.sum()),lost_support_cells=int(lost.sum()),lost_support_depths_m=rel[lost].tolist(),lost_TIFF_volume_m3=float(rel[lost].sum()*3600),max_initial_depth_difference_m=float(abs(depth[0]-rel).max()),
   native_internal_t0_volume_m3=internal0,native_internal_budget_relative_residual=budget,ascii_budget_relative_residual=float(m['ascii_raster_source_adjusted_budget_relative_residual'])))
 consumer=audit_consumer(checks,case_audit,target_audit,external) if args.consumer else None
 reg(Path(__file__),'executed independent compact-delta review source')
 report=dict(reviewed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),stage='final_consumer_and_inputs' if args.consumer else 'preliminary_inputs_only',
  passed=all(checks.values()),checks={k:bool(v) for k,v in checks.items()},inputs=list(inputs.values()),cases=case_audit,native_target_rechecks=target_audit,consumer_review=consumer,
  scope='New compact_delta_v1/review only; frozen Q3 imports and exact48-role approved cache; no other active trees and no physics',
  limitations=['Global earlier onset and evaluation-left-censoring must remain distinct.','Compact exact vector polygon/mapping table not delivered; distances refer to actual supplied raster cell support.','ASCII initial support rounding is recorded, not a physical qualification.','No new absolute arrivals, probabilities, qualified delays, observed initiation truths or independent validation events.'])
 name='final_review.json' if args.consumer else 'preliminary_input_review.json';(D/name).write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
 print(json.dumps({'passed':report['passed'],'checks':len(checks),'output':str((D/name).relative_to(ROOT))}));assert report['passed'],[k for k,v in checks.items() if not v]
def audit_consumer(checks,cases,targets,external):
 source=reg(R/'scripts/join_compact_delta_v1.py','manually reviewed consumer source; not executed by this audit')
 summary=js(OUT/'summary.json','consumer final summary');validation=js(OUT/'validation.json','consumer final QA, not scientific qualification')
 arrivals=rows(OUT/'conditional_arrivals.csv','14 final conditional diagnostic target rows')
 release=rows(OUT/'release_mapping_audit.csv','2 final compact mapping/initialization audits')
 saved=rows(OUT/'saved_field_target_checks.csv','14 final saved-field target checks')
 lineage=rows(OUT/'lineage_audit.csv','2 explicit SH/STH analytic model replacements')
 onset=rows(OUT/'onset_scope_audit.csv','global and evaluation-clock roles separately audited')
 params=rows(OUT/'physical_parameter_audit.csv','40 exact shared physical parameter checks')
 checks['consumer_2cases14pairs40parameter_fields']=len(arrivals)==14 and len(release)==len(lineage)==len(onset)==2 and len(params)==40 and all(flag(x['exact_float_equal']) for x in params)
 checks['consumer_no_weights_events_or_2048_ensemble']=summary['probability_weights'] is None and summary['selected_runs_are_2048_probability_ensemble'] is False and summary['independent_local_validation_events']==0
 checks['consumer_no_accepted_arrival_or_predictive_probability']=summary['qualified_arrival_rows']==summary['absolute_arrival_rows']==summary['probability_rows']==0 and summary['accepted_arrival_envelope_run_ids']==[] and not any(summary[k] for k in ['mass_conservation_qualified','regional_accuracy_qualified','scientifically_qualified_for_prediction'])
 nulls=['initiation_to_release_delay_seconds','absolute_arrival_lower_utc','absolute_arrival_upper_utc','absolute_arrival_time_utc','qualified_arrival_lower_seconds','qualified_arrival_upper_seconds','arrival_probability','probability_weight']
 gates=['include_in_arrival_envelope','accepted_arrival_envelope_run_membership','mass_conservation_qualified','regional_accuracy_qualified','scientifically_qualified_for_prediction','arrival_is_initiation_truth','evaluation_window_first_unstable_is_new_start']
 checks['consumer_all14_null_lag_absolute_qualified_probability']=all(all(not x[k] for k in nulls) for x in arrivals)
 checks['consumer_all14_gates_false']=all(all(not flag(x[k]) for k in gates) for x in arrivals)
 for a in cases:
  rid=a['run_id'];r=one(release,run_id=rid);l=one(lineage,run_id=rid);o=one(onset,run_id=rid)
  checks['consumer_exact_lineage:'+rid]=l['original_model_id']==a['original_model_id'] and l['analytic_model_id']==a['analytic_model_id'] and flag(l['physical_parameters_unchanged'])
  checks['consumer_original_and_analytic_clocks:'+rid]=o['original_global_crossing_point_utc']==a['old_global_point_utc'] and o['analytic_interpolated_point_utc']==a['analytic_global_point_utc'] and o['original_evaluation_window_onset_status']==a['original_evaluation_status'] and o['analytic_evaluation_window_onset_status']==a['analytic_evaluation_status']
  checks['consumer_actual_and_parent_volume:'+rid]=close(r['original_release_volume_m3'],a['Q2_parent_volume_m3']) and close(r['actual_release_TIFF_volume_m3'],a['actual_TIFF_volume_m3']) and close(r['saved_initial_depth_integral_m3'],a['native_saved_t0_volume_m3'])
  checks['consumer_source_native_support_and_loss_explicit:'+rid]=int(r['positive_source_support_cells'])==a['supplied_support_cells'] and int(r['native_initial_positive_support_cells'])==a['native_saved_support_cells'] and int(r['supplied_positive_cells_zero_in_native_t0'])==a['lost_support_cells'] and close(r['supplied_volume_in_cells_zero_in_native_t0_m3'],a['lost_TIFF_volume_m3']) and close(r['saved_initial_max_depth_difference_m'],a['max_initial_depth_difference_m'])
  checks['consumer_separate_budget_representations:'+rid]=flag(r['budget_representations_separate']) and close(r['native_internal_budget_relative_residual'],a['native_internal_budget_relative_residual']) and close(r['saved_raster_budget_relative_residual'],a['ascii_budget_relative_residual'])
  for x in [x for x in arrivals if x['run_id']==rid]:
   checks['consumer_row_global_vs_evaluation:'+rid+':'+x['target_id']]=x['source_first_passage_status']==a['analytic_global_status'] and x['conditional_onset_interpolated_point_utc']==a['analytic_global_point_utc'] and x['original_global_crossing_point_utc']==a['old_global_point_utc'] and x['original_evaluation_window_onset_status']==a['original_evaluation_status'] and x['analytic_evaluation_window_onset_status']==a['analytic_evaluation_status']
 for t in targets:
  r=one(arrivals,run_id=t['run_id'],target_id=t['target_id']);s=one(saved,run_id=t['run_id'],target_id=t['target_id'])
  checks['consumer_independent_target_and_raster_distance:'+t['run_id']+':'+t['target_id']]=val(r['diagnostic_bulk_release_arrival_lower_seconds'])==val(s['actual_first_hit_lower_seconds'])==t['lower_seconds'] and val(r['diagnostic_bulk_release_arrival_upper_seconds'])==val(s['actual_first_hit_upper_seconds'])==t['upper_seconds'] and int(s['target_buffer_cell_count'])==t['buffer_cells'] and close(s['target_point_to_release_raster_support_distance_m'],t['support_distance_m'])
 sh=[x for x in arrivals if x['base_scenario_id']=='q2r3-p0072-S_H-linear'];sth=[x for x in arrivals if x['base_scenario_id']=='q2r3-p0255-S_T_H-linear']
 checks['consumer_SH7_never_if_released']=len(sh)==7 and all(flag(x['if_released_propagation']) and not x['conditional_onset_lower_utc'] and x['source_first_passage_status']=='no_cross_observed_complete' for x in sh)
 checks['consumer_STH7_leftcensored_not_new_window_start']=len(sth)==7 and all(x['source_evaluation_onset_status']=='left_censored_already_unstable' and not flag(x['evaluation_window_first_unstable_is_new_start']) and x['conditional_onset_lower_utc']=='2026-07-01T11:00:00+00:00' and x['conditional_onset_upper_utc']=='2026-07-01T12:00:00+00:00' for x in sth)
 checks['consumer_2junction_hits12_saved_nonhits']=sum(x['upper_seconds'] is not None for x in targets)==2 and all(x['target_id']=='paper_junction' for x in targets if x['upper_seconds'] is not None)
 checks['consumer_final328_QA_no_upgrade']=validation['passed'] is True and validation['check_count']==len(validation['checks'])==328 and all(x['passed'] for x in validation['checks']) and validation['adapter_pass_is_predictive_qualification'] is False
 counts={}
 for name in ['input_index.json','output_index.json']:
  p=OUT/name;m=js(p,'consumer canonical index '+name);paths=[]
  for f in m['files']:
   q=resolve(f['path']);assert q.is_relative_to(R) or q in external;paths.append(q);reg(q,'consumer indexed object '+name)
   checks['consumer_index_binding:'+name+':'+str(q)]=sha(q)==f['sha256'] and q.stat().st_size==f['bytes']
  checks['consumer_index_unique_no_self:'+name]=len(paths)==len(set(paths)) and p.resolve() not in paths
  checks['consumer_validation_binds_index:'+name]=validation[name.split('_')[0]+'_index_sha256']==sha(p)
  if name=='output_index.json':checks['consumer_index_excludes_review_and_validation']=m['independent_review_directory_excluded'] is True and all(not q.is_relative_to(D) and q!=OUT/'validation.json' for q in paths)
  counts[name]=len(paths)
 visual=js(OUT/'figure_review.json','actual consumer visual inspection binding')
 checks['consumer_actual_figure_QA_binding']=visual['passed'] is True and all(x['actually_opened'] is True and sha(resolve(x['path']))==x['sha256'] for x in visual['figures'])
 old_v3=reg(R/'results/arrival/propagation_v3/summary.json','previous fullmask-v3 summary unchanged')
 old_review=reg(R/'results/arrival/propagation_v3/review/final_review.json','previous fullmask-v3 final review unchanged')
 checks['old_fullmask_summary_and_review_unchanged']=sha(old_v3)=='3b162f359018664a154e1ded01d38ad01c2365cd11362261d32c2c4d60b99cd1' and sha(old_review)=='c5f3b467c0008477f5630e2351f8d3666e753f42cf773b31600ac73e6c636d39'
 return dict(source_sha256=sha(source),QA_checks=validation['check_count'],index_counts=counts,
  source_review={'exact_declared_SH_STH_replacements':True,'compact_parent_not_fullmask':True,'global_vs_evaluation_clocks_separate':True,'unknown_lag_and_unqualified_gates':True,'source_vs_native_support_loss_explicit':True,'actual_supplied_raster_support_distance':True,'writes_only_new_delta_output':True,'no_physics_solver_call':True},
  note='Manual source review and independent input/native/target/table/index rechecks; software QA is not predictive qualification.')
if __name__=='__main__':main()
