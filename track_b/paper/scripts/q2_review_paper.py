#!/usr/bin/env python3
"""Independent paper-layer Q2 numeric/source/reference checks; no model execution."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,hashlib,io,json,math,re
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
ROOT=Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2')
PAPER=ROOT/'track_b/paper';R3=ROOT/'track_b/research/q2/round3'
OUT=PAPER/'evidence/q2_numeric_audit.json'
sources={};checks=[]
MANUAL_SECTION_SHA256='c6d55c822f99675f33f001839b7a02f732e3581d6ece50b63f74343759e9fed0'
VISUALLY_REVIEWED_PNGS={
 'q2_mechanism_comparison.png':'b951b355248495338353f2220740ffeac4ad39ec34970a02e6d90be7b6aa1520',
 'q2_critical_head_sensitivity.png':'d82a8fcc7e9d2470e58df59062154dfd4276cb60cec867ac78c7ea559ccf66b6',
 'q2_lab_grouped_validation.png':'4d61c13044ae56547e6c8552238e946412e7f6b18fe875beb526a6c62e771cda'}
def digest(b):return hashlib.sha256(b).hexdigest()
def read(p):
 p=Path(p);raw=p.read_bytes();sources[str(p.relative_to(ROOT))]={'path':str(p.relative_to(ROOT)),'bytes':len(raw),'sha256':digest(raw)};return raw
def csv(p):return pd.read_csv(io.BytesIO(read(p)))
def js(p):return json.loads(read(p))
def ck(name,condition,**facts):
 checks.append({'check':name,'passed':bool(condition),**facts})
 if not condition:raise AssertionError(name)
def safe(x):
 if isinstance(x,np.generic):return x.item()
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [safe(v) for v in x]
 return x

def extract():
 facts={};a=R3/'results/analytic_thermal'
 outcomes=csv(a/'scenario_outcomes.csv');comparison=csv(a/'model_comparison.csv');summary=js(a/'summary.json');config=js(a/'config.json');params=csv(a/'parameter_ensemble.csv')
 ck('analytic_2048_scenarios_256_common_designs',len(outcomes)==2048 and outcomes.scenario_id.is_unique and outcomes.parameter_set_id.nunique()==256 and len(params)==2048)
 table=[]
 for (mechanism,policy),d in outcomes.groupby(['mechanism_id','law_policy'],sort=False):
  counts=Counter(d.onset_status);m=float(d.min_margin_evaluation.median());ref=comparison[(comparison.mechanism_id==mechanism)&(comparison.law_policy==policy)].iloc[0]
  ck('count_and_median_'+mechanism+'_'+policy,len(d)==256 and counts['interval_crossing']==ref.interval_crossing_n and counts['left_censored_already_unstable']==ref.left_censored_n and counts['never_crossed']==ref.never_crossed_n and abs(m-ref.median_min_margin)<1e-12)
  table.append({'mechanism_id':mechanism,'law_policy':policy,'n':len(d),'interval_crossing':counts['interval_crossing'],'left_censored':counts['left_censored_already_unstable'],'never_crossed':counts['never_crossed'],'median_evaluation_min_margin':m,'p05_evaluation_min_margin':float(d.min_margin_evaluation.quantile(.05)),'p95_evaluation_min_margin':float(d.min_margin_evaluation.quantile(.95))})
 ck('all_statuses_retained_and_counts_not_event_probabilities',Counter(outcomes.onset_status)==Counter({'interval_crossing':137,'left_censored_already_unstable':248,'never_crossed':1663}) and summary['probabilities_assigned'] is False and summary['independent_observed_events']==0)
 finite=outcomes[outcomes.onset_status=='interval_crossing'];left=outcomes[outcomes.onset_status=='left_censored_already_unstable']
 ck('initial_left_censor_and_hourly_onset_brackets',left.onset_elapsed_hours.isna().all() and (left.initial_margin<=0).all() and (finite.initial_margin>0).all() and np.all(finite.onset_elapsed_hours>=finite.crossing_lower_hours) and np.all(finite.onset_elapsed_hours<=finite.crossing_upper_hours) and np.allclose(finite.crossing_upper_hours-finite.crossing_lower_hours,1))
 facts['analytic_mechanism_table']=table;facts['total_counts']={'parameter_designs':256,'mechanisms':4,'strength_policies':2,'scenarios':2048,'crossing':137,'left_censored':248,'never_crossed':1663,'interpretation':'conditional design counts, not event probabilities'}
 paired=csv(a/'paired_v2_fd0625.csv');pairs=paired.dropna(subset=['analytic_onset_elapsed_hours','fd0625_onset_elapsed_hours']);direct=(pairs.analytic_onset_elapsed_hours-pairs.fd0625_onset_elapsed_hours).abs();i=direct.idxmax();v2=(pairs.analytic_onset_elapsed_hours-pairs.v2_onset_elapsed_hours).abs();j=v2.idxmax()
 ck('analytic_vs_fineFD_time_difference_direct_recalculation',len(pairs)==137 and abs(direct.max()-summary['max_analytic_fd_onset_difference']['value'])<1e-10 and abs(v2.max()-summary['max_analytic_v2_onset_difference']['value'])<1e-10 and not paired.fd_onset_category_changed.any())
 facts['numeric_comparison']={'finite_pairs':len(pairs),'fineFD_dz_m':.0625,'max_onset_abs_difference_hours':float(direct.max()),'fineFD_max_base_scenario':paired.loc[i,'base_scenario_id'],'v2_FD_dz_m':.125,'v2_max_onset_abs_difference_hours':float(v2.max()),'v2_max_base_scenario':paired.loc[j,'base_scenario_id'],'all_category_changes':int(paired.fd_onset_category_changed.sum()),'max_margin_difference':float(paired.max_abs_margin_analytic_minus_fd.max()),'max_interface_temp_difference_c':float(paired.max_abs_interface_temperature_analytic_minus_fd_c.max()),'thaw_branch_mismatch_scenario_hours':int(paired.thaw_branch_mismatch_hours.sum()),'state_dt_hours':1,'scope':'linear heat-equation numerical reference; 1h water/damage integration and physical source uncertainties remain'}
 forcing=csv(a/'forcing_hourly.csv');reflection=csv(a/'reflection_bounds.csv');rp=params.drop_duplicates('parameter_set_id').set_index('parameter_set_id');reflection_rows=[];reflection_relerr=0.
 air=forcing.station_air_temp_c.to_numpy();horizon=(len(air)-1)*3600
 for row in reflection.itertuples():
  p=rp.loc[row.parameter_set_id];b=np.minimum(air+p.station_source_offset_c,0);db=np.r_[b[0]-p.initial_temp_c,np.diff(b)];tv=math.fsum(abs(float(v)) for v in db[:-1]);kernel=math.erfc((80-p.interface_depth_m)/(2*math.sqrt(p.diffusivity_m2_s*horizon)));bound=tv*kernel
  for actual,expected in [(tv,row.used_boundary_total_variation_c),(kernel,row.first_reflection_kernel_upper_bound),(bound,row.finite40_minus_halfspace_temperature_abs_bound_c)]:reflection_relerr=max(reflection_relerr,abs(actual/expected-1))
  reflection_rows.append({'parameter_set_id':row.parameter_set_id,'boundary_total_variation_c':tv,'first_reflection_kernel_bound':kernel,'temperature_bound_c':bound})
 max_reflection=max(reflection_rows,key=lambda x:x['temperature_bound_c']);box_kernel=math.erfc(60/(2*math.sqrt(2.1e-6*horizon)))
 ck('finite40_reflection_all256_bounds_recomputed_from_forcing',len(reflection)==256 and reflection_relerr<1e-11 and math.isclose(max_reflection['temperature_bound_c'],summary['max_actual_reflection_temperature_bound_c'],rel_tol=1e-11,abs_tol=0),max_relative_error=reflection_relerr)
 facts['finite40_reflection_bound']={**max_reflection,'bottom_m':40,'horizon_hours':2088,'conservative_parameter_box_kernel_bound':box_kernel,'box_kernel_times_max_actual_boundary_tv_bound_c':box_kernel*max(x['boundary_total_variation_c'] for x in reflection_rows),'scope':'actual 256 supplied boundary columns; homogeneous initial condition, linear Dirichlet-top/Neumann-bottom heat equation; no in-situ geometry or physics validation'}
 facts['parameter_design']={'ranges':config['ranges'],'seed':config['seed']}
 critical=csv(R3/'results/critical_relations.csv');cp=params[(params.mechanism_id=='S_T_H')&(params.law_policy=='linear_extension')].set_index('parameter_set_id');critical_error=0.;critical_types=True
 for r in critical.itertuples():
  p=cp.loc[r.parameter_set_id];theta=math.radians(p.theta_deg);sn=p.density_kg_m3*9.80665*p.thickness_normal_m*math.cos(theta)/1000;drive=p.density_kg_m3*9.80665*p.thickness_normal_m*math.sin(theta)/1000
  C=(1-p.initial_damage)*(p.bridge_fraction*p.bridge_cohesion_kpa+(1-p.bridge_fraction)*(53.3-73.5*r.temperature_c));mu=p.bridge_fraction*p.rock_mu+(1-p.bridge_fraction)*(.42-.21*r.temperature_c);cap=min(p.connected_depth_m,.98*sn/9.80665)
  root=None if C>drive else (sn-(drive-C)/mu)/9.80665;status='no_pressure_only_root' if root is None else ('dry_already_critical' if root<=0 else 'positive_pressure_root');critical_types=critical_types and status==r.root_status
  critical_error=max(critical_error,abs(cap-r.allowed_head_capacity_m));critical_error=max(critical_error,0 if root is None else abs(root-r.critical_head_m))
 ck('all_condition_critical_head_relations_independent_algebra',critical_types and critical_error<1e-10,n=len(critical),max_error_m=critical_error)
 facts['critical_p0036_example']=critical[critical.parameter_set_id=='q2r3-p0036'][['temperature_c','critical_head_m','root_status','allowed_head_capacity_m','root_reachable_before_capacity']].replace({np.nan:None}).to_dict('records')
 sens=csv(a/'joint_sensitivity.csv');top=[];maxrho=0.;maxbeta=0.
 for (m,p),d in outcomes.groupby(['mechanism_id','law_policy'],sort=False):
  par=params[(params.mechanism_id==m)&(params.law_policy==p)].set_index('parameter_set_id').loc[d.parameter_set_id]
  y=d.min_margin_evaluation.to_numpy();rows=[];keys=list(config['ranges']);cols=[]
  for key in keys:
   x=par[key].to_numpy();rho=float(spearmanr(x,y).statistic);ref=sens[(sens.mechanism_id==m)&(sens.law_policy==p)&(sens.parameter==key)].iloc[0];maxrho=max(maxrho,abs(rho-ref.spearman_rho));rows.append({'parameter':key,'rho':rho,'beta':float(ref.standardized_linear_coefficient)})
   cols.append(np.log(x) if config['ranges'][key]['scale']=='log' else x)
  X=np.column_stack(cols);z=(X-X.mean(0))/X.std(0);beta=np.linalg.lstsq(np.column_stack([np.ones(len(y)),z]),(y-y.mean())/y.std(),rcond=None)[0][1:]
  for k,b in zip(keys,beta):maxbeta=max(maxbeta,abs(float(b)-next(v['beta'] for v in rows if v['parameter']==k)))
  top.append({'mechanism_id':m,'law_policy':p,'rank_by_abs_spearman_top5':sorted(rows,key=lambda r:abs(r['rho']),reverse=True)[:5]})
 ck('all152_joint_sensitivity_rows_independently_recomputed',len(sens)==152 and maxrho<1e-12 and maxbeta<1e-12,max_rho_error=maxrho,max_beta_error=maxbeta)
 facts['joint_sensitivity']=top
 response=csv(R3/'results/thermal_response_times.csv');err=0.
 for r in response.itertuples():err=max(err,abs(math.erfc(r.depth_m/(2*math.sqrt(r.diffusivity_m2_s*r.hours*3600)))-r.step_response_fraction))
 ck('thermal_step_response_direct_math_erfc',err<1e-14,n=len(response),max_error=err)
 facts['thermal_response_72h_alpha1p5e6']=[{'depth_m':float(r.depth_m),'fraction':float(r.step_response_fraction),'diffusion_scale_hours':float(r.diffusion_scale_hours)} for r in response[(response.diffusivity_m2_s==1.5e-6)&(response.hours==72)].itertuples()]
 statepath=a/'state_trajectories.parquet';states=pd.read_parquet(io.BytesIO(read(statepath)));sp=params.set_index('scenario_id')
 pressure_error=0.;min_damage_diff=1.;cutoff_errors=0;inactive_H_error=0.;inactive_T_error=0.
 for sid,d in states.groupby('scenario_id',sort=False):
  d=d.sort_values('elapsed_hours');p=sp.loc[sid];pressure_error=max(pressure_error,float(abs(d.pressure_kpa-9.80665*d.storage_m/p.storativity).max()));min_damage_diff=min(min_damage_diff,float(d.damage.diff().dropna().min()))
  if p.mechanism_id in ['S','S_T']:inactive_H_error=max(inactive_H_error,float(abs(d.pressure_kpa).max()),float(abs(d.storage_m).max()))
  if p.mechanism_id in ['S','S_H']:inactive_T_error=max(inactive_T_error,float(abs(d.interface_temp_c-p.initial_temp_c).max()))
  tt=pd.to_datetime(d.time_utc,utc=True);cut=pd.to_datetime(d.forcing_cutoff_utc,utc=True);cutoff_errors+=int(((tt-cut).dt.total_seconds().iloc[1:]!=3600).sum())
 ck('representative_water_damage_and_causal_time_support',len(states)==133696 and states.scenario_id.nunique()==64 and pressure_error<1e-10 and min_damage_diff>=-1e-14 and inactive_H_error==0 and inactive_T_error<1e-12 and cutoff_errors==0,pressure_relation_error_kpa=pressure_error,min_damage_step=min_damage_diff,cutoff_errors=cutoff_errors)
 facts['water_damage_time_support']={'parameter_ranges':{k:config['ranges'][k] for k in ['storativity','drainage_hours','connected_depth_m','damage_rate_h_inv','damage_exponent','initial_damage','drainage_damage_coupling']},'states_per_scenario':2089,'run_horizon_hours':2088,'start_utc':str(states.time_utc.min()),'end_utc':str(states.time_utc.max()),'representative_scenarios':64,'representative_state_rows':133696,'max_water_budget_residual_m':summary['max_water_budget_error_m'],'hourly_state_dt':1,'pressure_relation':'u=9.80665*storage_m/storativity [kPa]','coupling_scope':'H includes rain/melt supply and damage-dependent drainage; noH closes the hydrologic pathway. NoT fixes interface temperature. Damage is phenomenological.'}
 ident=csv(R3/'results/identifiability.csv');ck('identifiability_benchmark_ranks',ident['rank'].tolist()==[1,1,2,3,4] and ident.independent_events.eq(0).all());facts['identifiability_ranks']=[{'design':r.design_id,'n_observations':int(r.n_observations),'rank':int(r.rank),'nullity':int(r.nullity)} for r in ident.itertuples()]
 lab=R3/'lab_strength';obs=csv(lab/'audit/results/observations.csv');fits=csv(lab/'model/results/fits.csv');pred=csv(lab/'model/results/holdout_predictions.csv');fold=csv(lab/'model/results/holdout_folds.csv');run=js(lab/'model/results/run_summary.json');labsummary=csv(lab/'model/results/holdout_summary.csv');calib=csv(lab/'model/results/calibration_residuals.csv')
 ck('lab_trial_and_fit_fold_counts',len(obs)==141 and obs.observation_id.is_unique and run['new_fits']==32 and len(fold)==576 and len(pred)==8796 and run['bootstrap_attempts']==32000 and run['bootstrap_usable']==31994 and run['bootstrap_failed_rank_or_nonfinite']==6)
 warmtable=[];max_lab_rmse_error=0.
 for m in ['mc_linear','mc_temperature_quadratic','mc_stress_quadratic','mc_stress_hinge_400']:
  c=calib[(calib.domain=='warm_all')&(calib.model==m)&(calib.weight=='row_ols')];train=float(np.sqrt(np.mean((c.predicted_kpa-c.observed_kpa)**2)));fr=fits[(fits.domain=='warm_all')&(fits.model==m)&(fits.weight=='row_ols')].iloc[0];max_lab_rmse_error=max(max_lab_rmse_error,abs(train-fr.rmse_kpa));row={'model':m,'train_rmse_kpa':train}
  for scheme,group_name in [('temperature','temperature_macro_rmse_kpa'),('normal_stress','stress_macro_rmse_kpa')]:
   pp=pred[(pred.domain=='warm_all')&(pred.model==m)&(pred.weight=='row_ols')&(pred.holdout_scheme==scheme)];squared=(pp.predicted_kpa-pp.observed_kpa)**2;means=squared.groupby(pp.heldout_group).mean();macro=math.sqrt(float(means.mean()));ref=labsummary[(labsummary.domain=='warm_all')&(labsummary.model==m)&(labsummary.weight=='row_ols')&(labsummary.holdout_scheme==scheme)].iloc[0];max_lab_rmse_error=max(max_lab_rmse_error,abs(macro-ref.group_macro_rmse_kpa));row[group_name]=macro
   if scheme=='normal_stress':
    hh=pp[pd.to_numeric(pp.heldout_group,errors='coerce')==800];row['heldout_800_rmse_kpa']=float(np.sqrt(np.mean((hh.predicted_kpa-hh.observed_kpa)**2)))
  warmtable.append(row)
 ck('lab_warm_comparison_RMSE_from_individual_residuals',max_lab_rmse_error<1e-8,max_abs_error=max_lab_rmse_error)
 high=obs[obs.normal_stress_target_kpa==800]
 facts['lab_strength']={'trials':141,'author_derived_summaries':14,'new_fits':32,'holdout_folds':576,'warm_all_trials':int(obs.temperature_target_c.between(-4,-.5).sum()),'warm_all_folds_both_weights':int((fold.domain=='warm_all').sum()),'nominal_800_trials':len(high),'actual_800_stress_range_kpa':[float(high.normal_stress_at_failure_kpa.min()),float(high.normal_stress_at_failure_kpa.max())],'actual_800_temperature_range_c':[float(high.temperature_at_failure_c.min()),float(high.temperature_at_failure_c.max())],'warm_row_OLS_comparison':warmtable,'macro_rmse_definition':'sqrt(mean(heldout_group_mean_squared_error)), distinct from pooled sample RMSE','interpretation':'external laboratory constitutive competition; repeated specimen identities uncertain; no local event validation; author Eq6 is reused fixed calibration reference, excluded from CV rankings'}
 coef=csv(lab/'model/results/coefficients.csv');coef=coef[(coef.domain=='warm_all')&(coef.model=='mc_linear')&(coef.weight=='row_ols')].set_index('term');design=np.array([1.,-.4,2.,-.8]);mean=float(np.dot(design,coef.loc[['1','t','s','t*s'],'coefficient_kpa']));draws=np.load(io.BytesIO(read(lab/'model/results/bootstrap_coefficient_draws.npz')));mean_bands=[]
 for scheme in ['within_cell_independent_tests','specimen_label_blocks_assumed']:
  bb=draws['warm_all__mc_linear__'+scheme];y=bb@design;usable=y[np.isfinite(y)];qq=np.quantile(usable,[.025,.5,.975]);mean_bands.append({'scheme':scheme,'mean_kpa':mean,'mean_percentiles_2p5_50_97p5_kpa':qq.tolist(),'usable_draws':len(usable)})
 ck('conditional_lab_mean_and_bands_recomputed_from_saved_coefficients',all(x['usable_draws']==1000 for x in mean_bands) and coef.shape[0]==4 and all(np.isfinite(x['mean_percentiles_2p5_50_97p5_kpa']).all() for x in mean_bands))
 facts['lab_strength']['fixed_nominal_design_mean']={'temperature_c':-2,'normal_stress_kpa':800,'design_scaling':'t=T/5, s=sigma/400; columns[1,t,s,t*s]','row':design.tolist(),'schemes':mean_bands,'scope':'conditional fitted mean sensitivity from saved draws, not individual prediction interval or event coverage'}
 author=csv(lab/'model/author_results/source_stage2_weight_sensitivity.csv');selected=author[['block','selection','temperature_layers']].drop_duplicates();facts['author_selected_layers']=selected[selected.selection.isin(['published_significant_layers','warm_published_significant_layers'])].to_dict('records')
 sar=csv(R3/'results/sar_evidence_summary.csv');facts['SAR_local_symbol_window']=sar[sar.region=='candidate_symbol_pm1500m_square'][['role','grid_cells','valid_velocity_cells','v_median_m_year','v_error_median_m_year']].to_dict('records')
 mech=read(R3/'scripts/mechanism_engine.py').decode();facts['mechanical_implementation']={'failure_margin':'(resistance-driving)/driving, positive stable','damage_rate':'a*min(driving/max(resistance,1e-6),10)^p; exponential state update of1-D; numerical upper capD=.999999','water_pressure_kpa_per_m_head':9.80665,'reservoir_capacity':'min(connected_depth,.98*sigma_n/G)*storativity','source_scope':'conditional plane slab and mixture; separate bridge-area fraction and bulk composition'}
 return facts

def tex_args(text,command):
 pattern=re.escape(chr(92)+command)+'(?:'+re.escape('[')+'[^]]*'+re.escape(']')+')?'+re.escape('{')+'([^}]+)'+re.escape('}')
 return re.findall(pattern,text)

def claims_numeric_check(claims,facts):
 c={x['claim_id']:x['value'] for x in claims};close=lambda a,b:math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-10)
 ck('claim_19_parameter_ranges_and_design_counts',c['q2-C04']['parameter_count']==19 and c['q2-C04']['parameter_sets']==256 and c['q2-C04']['scenario_outcomes']==2048 and c['q2-C04']['probability_prior'] is False)
 ck('claim_all_parameter_endpoints_scales_and_fixed_seed',c['q2-C04']['parameter_ranges']==facts['parameter_design']['ranges'] and c['q2-C04']['seed']==facts['parameter_design']['seed'])
 ck('claim_hourly_boundary_counts',c['q2-C05']['hourly_states']==2089 and c['q2-C05']['state_dt_hours']==1 and c['q2-C05']['initial_W_m']==0)
 ck('claim_causal_FFT_padding',c['q2-C06']['nfft']==8192 and c['q2-C06']['minimum_linear_padding']==2*2089-1 and c['q2-C06']['K0']==0 and c['q2-C06']['causal_j_lt_k'])
 for row in c['q2-C07']:
  reference=next(x for x in facts['thermal_response_72h_alpha1p5e6'] if x['depth_m']==row['depth_m']);ck('claim_step_response_depth'+str(row['depth_m']),close(reference['fraction'],row['step_response_fraction']))
 ck('claim_water_budget_and_gamma_units',close(c['q2-C08']['gamma_w_kpa_per_m'],9.80665) and close(c['q2-C08']['max_water_budget_error_m'],facts['water_damage_time_support']['max_water_budget_residual_m']))
 for row in c['q2-C09']['examples']:
  reference=next(x for x in facts['critical_p0036_example'] if x['temperature_c']==row['temperature_c']);ck('claim_p0036_critical_'+str(row['temperature_c']),reference['root_status']==row['root_status'] and close(reference['allowed_head_capacity_m'],row['allowed_head_capacity_m']) and (row['critical_head_m'] is None if reference['critical_head_m'] is None else close(reference['critical_head_m'],row['critical_head_m'])))
 for row in c['q2-C10']:
  reference=next(x for x in facts['analytic_mechanism_table'] if x['mechanism_id']==row['mechanism_id'] and x['law_policy']=='linear_extension')
  ck('claim_final_mechanism_'+row['mechanism_id'],reference['interval_crossing']==row['interval_crossing_n'] and reference['left_censored']==row['left_censored_n'] and reference['never_crossed']==row['never_crossed_n'] and close(reference['median_evaluation_min_margin'],row['median_min_margin']) and close(reference['p05_evaluation_min_margin'],row['p05_min_margin']) and close(reference['p95_evaluation_min_margin'],row['p95_min_margin']))
 ck('claim_total_censor_counts_and_no_probability',c['q2-C11']['status_counts']=={'interval_crossing':137,'never_crossed':1663,'left_censored_already_unstable':248} and c['q2-C11']['probabilities_assigned'] is False)
 sensitivity=next(x['rank_by_abs_spearman_top5'] for x in facts['joint_sensitivity'] if x['mechanism_id']=='S_T_H' and x['law_policy']=='linear_extension')
 ck('claim_joint_sensitivity_order_and_values',[x['parameter'] for x in c['q2-C12']]==[x['parameter'] for x in sensitivity] and all(close(x['spearman_rho'],y['rho']) for x,y in zip(c['q2-C12'],sensitivity)))
 n=facts['numeric_comparison'];v=c['q2-C13'];ck('claim_FD_comparison_time_and_margin',v['finite_pairs']==137 and close(v['fd00625_max_hours']['value'],n['max_onset_abs_difference_hours']) and close(v['fd0125_max_hours']['value'],n['v2_max_onset_abs_difference_hours']) and close(v['max_margin_difference']['value'],n['max_margin_difference']))
 ck('claim_finite40_actual_temperature_bound_relative_tolerance',math.isclose(v['finite40_vs_halfspace_max_temperature_bound_c'],facts['finite40_reflection_bound']['temperature_bound_c'],rel_tol=1e-11,abs_tol=0))
 ck('claim_local_jacobian_rank_sequence',[x['rank'] for x in c['q2-C14']]==[x['rank'] for x in facts['identifiability_ranks']])
 lab=facts['lab_strength'];v=c['q2-C15'];ck('claim_lab_counts_and_actual800_support',v['tests']==141 and v['derived_temperature_summaries']==14 and v['high_class']['tests']==20 and close(v['high_class']['measured_normal_stress_min_kpa'],lab['actual_800_stress_range_kpa'][0]) and close(v['high_class']['measured_normal_stress_max_kpa'],lab['actual_800_stress_range_kpa'][1]))
 ck('claim_lab_design_and_resampling_counts',c['q2-C16']['fits']==32 and c['q2-C16']['folds']==576 and c['q2-C16']['warm_common_tests']==83 and c['q2-C16']['bootstrap_attempts']==32000 and c['q2-C16']['bootstrap_usable']==31994)
 for row in c['q2-C17']['grouped_row_ols']:
  if row['holdout_scheme'] not in ['temperature','normal_stress']:continue
  reference=next(x for x in lab['warm_row_OLS_comparison'] if x['model']==row['model']);key='temperature_macro_rmse_kpa' if row['holdout_scheme']=='temperature' else 'stress_macro_rmse_kpa';ck('claim_lab_macro_'+row['model']+'_'+row['holdout_scheme'],close(reference[key],row['group_macro_rmse_kpa']))
 for row in c['q2-C17']['only_800_holdout']:
  reference=next(x for x in lab['warm_row_OLS_comparison'] if x['model']==row['model']);ck('claim_800_holdout_'+row['model'],close(reference['heldout_800_rmse_kpa'],row['rmse_kpa']))
 ck('claim_warm_selected_layer_sets',c['q2-C18']['selected_warm_low_c']==[-4,-2,-.5] and c['q2-C18']['selected_warm_all_c']==[-4,-2,-1,-.5] and c['q2-C18']['local_engine_replaced'] is False)
 for row in c['q2-C19']:
  reference=next(x for x in lab['fixed_nominal_design_mean']['schemes'] if x['scheme']==row['scheme']);ck('claim_conditional_mean_percentiles_'+row['scheme'],row['temperature_c']==-2 and row['normal_stress_kpa']==800 and row['model']=='mc_linear' and row['usable_draws']==reference['usable_draws'] and close(row['mean_kpa'],reference['mean_kpa']) and np.allclose(row['mean_percentiles_2p5_50_97p5_kpa'],reference['mean_percentiles_2p5_50_97p5_kpa'],rtol=1e-12,atol=1e-10) and row['not_individual_prediction_interval_or_event_probability'] is True)

def check_paper(facts):
 section=PAPER/'sections/q2.tex';claims=PAPER/'evidence/q2_claims.json';references=PAPER/'evidence/q2_references.tex'
 if not all(p.exists() for p in [section,claims,references]):return {'status':'pending_section_claims_or_references','files_present':{p.name:p.exists() for p in [section,claims,references]}}
 tex=read(section).decode();rtext=read(references).decode();cl=js(claims);cl=cl.get('claims',cl) if isinstance(cl,dict) else cl
 verified=0
 claims_numeric_check(cl,facts)
 for c in cl:
  for item in c['source_files']:
   p=ROOT/item['path'];ck('claim_source_hash_'+c['claim_id']+'_'+p.name,p.resolve().is_relative_to(ROOT) and p!=OUT and digest(read(p))==item['sha256']);verified+=1
 cites=set(v.strip() for g in tex_args(tex,'cite') for v in g.split(','));bib=set(tex_args(rtext,'bibitem'));labels=tex_args(tex,'label');refs=set(tex_args(tex,'eqref')+tex_args(tex,'ref')+tex_args(tex,'autoref'))
 ck('paper_q2_citations_resolve_and_prefix',bool(cites) and cites<=bib and all(k.startswith('q2-') for k in cites),citations=sorted(cites),bibitems=sorted(bib))
 ck('paper_q2_labels_unique_and_references_resolve',bool(labels) and len(labels)==len(set(labels)) and all(k.startswith('q2') for k in labels) and all(k in labels for k in refs if k.startswith('q2')),labels=labels)
 ck('all_claims_have_source_files_and_resolved_paper_anchor',all(x['source_files'] and x['paper_anchor'] in labels for x in cl))
 for mechanism,display in [('S','S'),('S_T','ST'),('S_H','SH'),('S_T_H','STH')]:
  rr=next(x for x in facts['analytic_mechanism_table'] if x['mechanism_id']==mechanism and x['law_policy']=='linear_extension');expected=f"{display} & {rr['interval_crossing']} & {rr['left_censored']} & {rr['never_crossed']} & {rr['median_evaluation_min_margin']:.4f}"
  ck('displayed_mechanism_table_'+display,expected in tex)
 for model,display,npar in [('mc_linear','温度线性 MC',4),('mc_temperature_quadratic','温度二次 MC',6),('mc_stress_quadratic','应力二次',6),('mc_stress_hinge_400','400 kPa 铰链',6)]:
  rr=next(x for x in facts['lab_strength']['warm_row_OLS_comparison'] if x['model']==model);expected=f"{display} & {npar} & {rr['train_rmse_kpa']:.2f} & {rr['heldout_800_rmse_kpa']:.2f}"
  ck('displayed_lab_table_'+model,expected in tex)
 figures=[]
 for fig in tex_args(tex,'includegraphics'):
  candidates=[PAPER/fig,PAPER/'figures'/fig,PAPER/'figures/q2'/fig]
  found=next((p for p in candidates if p.exists()),None);ck('paper_figure_exists_'+Path(fig).name,found is not None)
  if found is not None:figures.append({'path':str(found.relative_to(ROOT)),'sha256':digest(read(found))})
 style_warnings=[w for w in ['尚未验证','未达到','未实现','资格未接受'] if w in tex]
 manual_match=MANUAL_SECTION_SHA256==digest(tex.encode());visual=[]
 for name,expected in VISUALLY_REVIEWED_PNGS.items():
  p=PAPER/'figures/q2'/name;actual=digest(read(p));visual.append({'path':str(p.relative_to(ROOT)),'sha256':actual,'matches_actually_opened_snapshot':actual==expected})
 final=manual_match and len(visual)==3 and all(x['matches_actually_opened_snapshot'] for x in visual)
 return {'status':'passed_including_manual_numeric_prose_and_visual_review' if final else 'source_hash_reference_checks_passed_manual_snapshot_pending','claims':len(cl),'source_file_references_verified':verified,'citations':sorted(cites),'figure_files':figures,'style_warnings':style_warnings,'manual_prose_snapshot_matches':manual_match,'visual_review':visual,'manual_review_scope':'All numerical statements, seven equation groups, three tables, captions and 22 claim values against independent facts and actual sources. Gamma_w units, source screening cohorts, conditional means and formula scope checked. Figures reviewed from actual PNG snapshots, not inferred from generation success. No new mechanism calibration or event validation.'}

def main():
 if Path.cwd().resolve()!=ROOT:raise RuntimeError('explicit Q2 workdir required')
 ap=argparse.ArgumentParser();ap.add_argument('--paper',action='store_true');args=ap.parse_args();facts=extract();review=check_paper(facts) if args.paper else {'status':'source_facts_extracted_pending_paper_review'}
 payload={'audit_version':'q2-paper-independent-numeric-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'data_role':'paper_evidence_postprocessing_only_no_model_execution','review_script_sha256':digest(Path(__file__).read_bytes()),'independent_local_events':0,'checks':checks,'facts':facts,'source_files':list(sources.values()),'paper_review':review,'command':'track_b/.venv/bin/python track_b/paper/scripts/q2_review_paper.py'+(' --paper' if args.paper else ''),'scope':'Read historical results only; independent counts, medians, sensitivity ranks, response erfc, reflection bounds, state/time invariants and lab RMSE from individual residuals; saved bootstrap coefficient arithmetic only, no resampling. No historical files modified.'}
 OUT.write_text(json.dumps(safe(payload),ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'passed':all(c['passed'] for c in checks),'checks':len(checks),'sources':len(sources),'paper_review':review},ensure_ascii=False))
if __name__=='__main__':main()
