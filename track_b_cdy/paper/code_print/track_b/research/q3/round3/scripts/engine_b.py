#!/usr/bin/env python3
"""Independent past-only inverse velocity and Kalman inverse-velocity models.
Not a port/reproduction of the PFTF R-tool. Model-internal uncertainty only.
"""
from __future__ import annotations
import hashlib,json,math,gzip
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];O=R/'results/engine_b';I=R/'inputs/deformation'
SEED=20261024;NS=512
Z=np.random.default_rng(SEED).standard_normal((NS*8,2))
def causal_vel(t,d,raw=None):
 if raw is not None and np.isfinite(raw).sum()>5:return np.abs(raw)/24
 v=np.full(len(t),np.nan)
 for i in range(4,len(t)):
  x=t[i-4:i+1];y=d[i-4:i+1];x=x-x.mean();den=x@x
  if den>0:v[i]=abs(float(x@(y-y.mean())/den))
 return v

def psd(c):
 c=(c+c.T)/2;v,a=np.linalg.eigh(c);return (a*np.maximum(v,1e-15))@a.T

def fit_roots(t,v,issue,model,w=16,qratio=.01):
 good=(t<=issue)&np.isfinite(v)&(v>0);x=t[good][-w:]-issue;y=1/v[good][-w:]
 if len(y)<6:return np.full(NS,np.inf),'insufficient_positive_velocities',None
 # Normalize inverse velocity scale for numerically stable fitting/filtering.
 scale=max(float(np.median(np.abs(y))),1e-30);y=y/scale
 X=np.c_[np.ones(len(x)),x];beta=np.linalg.lstsq(X,y,rcond=None)[0];res=y-X@beta
 var=max(float(res@res/max(len(x)-2,1)),1e-8)
 cov=psd(var*np.linalg.pinv(X.T@X))
 if model=='B_SS':
  noise=max(float(np.median(np.diff(y)**2)/2),1e-8)
  # Start filter from first three points only; never initialize with later fitted beta.
  x0=x[:3];X0=np.c_[np.ones(3),x0-x0[-1]];b0=np.linalg.lstsq(X0,y[:3],rcond=None)[0]
  m=b0.copy();P=np.diag([noise*10,noise/max(np.median(np.diff(x))**2,1e-6)])
  last=x[2]
  for xx,yy in zip(x[3:],y[3:]):
   delta=xx-last;F=np.array([[1.,delta],[0,1.]]);Q=noise*qratio*np.array([[delta**3/3,delta**2/2],[delta**2/2,delta]])
   m=F@m;P=F@P@F.T+Q;S=P[0,0]+noise;K=P[:,0]/S;m=m+K*(yy-m[0]);P=(np.eye(2)-np.outer(K,[1.,0.]))@P;P=psd(P);last=xx
  delta=-last;F=np.array([[1.,delta],[0,1.]]);m=F@m;P=F@P@F.T+noise*qratio*np.array([[delta**3/3,delta**2/2],[delta**2/2,delta]]) if delta>0 else P
  beta=m;cov=psd(P)
 eigvec=np.linalg.eigh(cov);L=eigvec[1]@np.diag(np.sqrt(np.maximum(eigvec[0],0)));pool=beta+Z@L.T
 if beta[0]<=0:return np.full(NS,np.inf),'fitted_nonpositive_inverse_velocity_abstain',None
 draw=pool[pool[:,0]>0][:NS]
 if len(draw)<NS:return np.full(NS,np.inf),'positive_state_sampling_tail_abstain',None
 roots=np.full(NS,np.inf);ok=draw[:,1]<0;roots[ok]=-draw[ok,0]/draw[ok,1];roots[roots<=0]=np.inf
 return roots,'ok',{'n_fit':len(y),'positive_state_pool_acceptance':float(np.mean(pool[:,0]>0)),'last_input_relative_hours':float(t[good][-1]),'window_n':w,'inverse_velocity_scale':scale,'q_ratio':qratio}

def one_prediction(t,v,issue,model,site,reg,grid,w=16,qratio=.01):
 roots,status,fit=fit_roots(t,v,issue,model,w,qratio);past=t[t<=issue];age=float(issue-past[-1]) if len(past) else np.nan;pastdif=np.diff(past[-33:]);cad=float(np.median(pastdif[pastdif>0])) if np.any(pastdif>0) else np.inf
 if len(past)<12:status='not_yet_monitored' if not len(past) else 'insufficient_history'
 if age>2*cad:status='stale_observation_abstain'
 lo=float(reg.failure_lower_hours);hi=float(reg.failure_upper_hours);out=[]
 for H in (24,48,72):
  finite=roots[(roots>0)&(roots<=H)];p=len(finite)/NS
  low,med,up=(np.quantile(finite,[.025,.5,.975])+issue) if len(finite) else (np.nan,np.nan,np.nan)
  target=1 if hi<=issue+H else (0 if lo>issue+H else np.nan)
  if status!='ok':p=np.nan;low=med=up=np.nan
  out.append({'engine':'B','model_id':model,'mechanism_id':'alpha2_inverse_velocity_local_trend','experiment_id':'fixed_past_only_w'+str(w)+'_q'+str(qratio),'scenario_id':'external_'+str(reg.event_group),'geometry_version':None,'parameter_version':'B_fixed_v1','event_group':reg.event_group,'site_id':site,'issue_time_relative_hours':float(issue),'issue_time_utc':None,'information_cutoff_relative_hours':float(issue),'horizon_hours':H,'issue_grid':grid,'probability_start_within_horizon':p,'probability_no_start_within_horizon':1-p,'conditional_lower_hours':low,'conditional_median_hours':med,'conditional_upper_hours':up,'conditional_interval_level':.95,'interval_semantics':'conditional_on_linear_zero_within_horizon_model_internal','failure_lower_hours':lo,'failure_upper_hours':hi,'failure_label_kind':reg.label_kind,'target_within_horizon':target,'brier':(p-target)**2 if np.isfinite(target) else np.nan,'coverage_full_label':float(low<=lo and up>=hi) if np.isfinite(low) and target==1 else np.nan,'coverage_intersects_label':float(low<=hi and up>=lo) if np.isfinite(low) and target==1 else np.nan,'coverage_full_label_all_known_events':float(np.isfinite(low) and low<=lo and up>=hi) if target==1 else np.nan,'coverage_intersects_label_all_known_events':float(np.isfinite(low) and low<=hi and up>=lo) if target==1 else np.nan,'conditional_width_hours':up-low,'point_error_to_label_interval_hours':(0 if lo<=med<=hi else min(abs(med-lo),abs(med-hi))) if np.isfinite(med) and target==1 else np.nan,'observation_age_hours':age,'last_input_relative_hours':fit['last_input_relative_hours'] if fit else (float(past[-1]) if len(past) else np.nan),'n_past_observations':len(past),'positive_state_pool_acceptance':fit['positive_state_pool_acceptance'] if fit else np.nan,'window_n':w,'q_ratio':qratio,'status':status,'data_role':'validation_online_past_observations','evaluation_stratum':'external_transfer','forecast_input_mode':None,'forecast_input_mode_reason':'no_weather_input_for_B','sensor_availability_role':'retrospective_sensor_replay_available_time_unknown','input_version':'canonical_deformation_v1','primary_evaluation_eligible':bool(reg.primary_evaluation_eligible),'external_failure_phase':'published_terminal_or_main_collapse','p_prior_note':'joint Gaussian estimation distribution conditional on positive current inverse velocity; not calibrated general hazard probability'})
 return out

def main():
 assert (R/'EXPERIMENT_PROTOCOL.md').exists();assert (R/'DEFORMATION_EVIDENCE.md').exists();O.mkdir(parents=True,exist_ok=True)
 obs=pd.read_csv(I/'observations.csv');regs=pd.read_csv(I/'site_registry.csv');pred=[];sens=[];fold=[];checks=[]
 # Freeze all protocol-defined groups/sensors; no learned shared hyperparameters, calibration separate.
 for reg in regs.itertuples():
  d=obs[obs.site_id==reg.site_id].sort_values('time_relative_hours');t=d.time_relative_hours.to_numpy(float);y=d.displacement.to_numpy(float);v=causal_vel(t,y,d.raw_velocity_per_day.to_numpy(float));L=float(reg.failure_lower_hours)
  start=max(t[11],L-30*24);issues=np.arange(math.ceil(start),math.floor(L)+1,dtype=float);issues=issues[issues<L]
  native=t[(t>=max(t[11],L-48))&(t<L)]
  for model in ('B_IV','B_SS'):
   for issue in issues:pred.extend(one_prediction(t,v,float(issue),model,reg.site_id,reg,'hourly',16))
   for issue in native:pred.extend(one_prediction(t,v,float(issue),model,reg.site_id,reg,'native_last48h',16))
   # Fixed retrospective lead anchors; same issue used for sensitivities, never pick by accuracy.
   for lead in (24,48,72):
    issue=L-lead
    for w in (8,16,32):
     for q in ((.001,.01,.1) if model=='B_SS' and w==16 else (.01,)):
      rr=one_prediction(t,v,float(issue),model,reg.site_id,reg,'fixed_label_lower_minus_'+str(lead)+'h',w,q)
      for row in rr:row['anchor_lead_hours']=lead
      sens.extend(rr)
  fold.append({'fold_id':'LOSO_'+str(reg.event_group),'test_group':reg.event_group,'test_sensor':reg.site_id,'training_groups':'|'.join(sorted(set(regs[regs.primary_evaluation_eligible].event_group)-{reg.event_group})),'model_parameter_training':'none_shared; fixed_structures; test_sensor_past_only_online_filter','calibration_groups':'other_primary_evaluation_eligible_physical_groups_only; no finite95 calibration performed','event_observed':bool(reg.event_observed),'failure_label_kind':reg.label_kind})
  # Direct truncation check for future perturbation; roots use only t<=issue.
  issue=float(issues[len(issues)//2]) if len(issues) else float(t[11]);v2=v.copy();v2[t>issue]=1e12
  for model in ('B_IV','B_SS'):
   a=fit_roots(t,v,issue,model)[0];b=fit_roots(t,v2,issue,model)[0];checks.append({'test':'future_velocity_rejection','site_id':reg.site_id,'model_id':model,'passed':bool(np.array_equal(np.isinf(a),np.isinf(b)) and np.allclose(a,b,rtol=1e-9,atol=1e-8)),'max_finite_root_difference_hours':float(np.max(np.abs(a[np.isfinite(a)&np.isfinite(b)]-b[np.isfinite(a)&np.isfinite(b)]))) if np.any(np.isfinite(a)&np.isfinite(b)) else 0.,'comparison_tolerance':'rtol1e-9 atol1e-8; infinity masks exactly equal'})
  yy=y.copy();yy[t>issue]+=1e8;vv=causal_vel(t,yy,d.raw_velocity_per_day.to_numpy(float));checks.append({'test':'future_displacement_preprocessing_rejection','site_id':reg.site_id,'passed':bool(np.allclose(vv[t<=issue],v[t<=issue],equal_nan=True))})
  print(reg.site_id,len(issues),len(native),flush=True)
 p=pd.DataFrame(pred);s=pd.DataFrame(sens);raw=p.to_csv(index=False,float_format='%.10g').encode();packed=gzip.compress(raw,mtime=0);digest=hashlib.sha256(packed).hexdigest();cache=Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q3/deformation/outputs');cache.mkdir(parents=True,exist_ok=True);cp=cache/('engine_b_predictions_'+digest+'.csv.gz');cp.write_bytes(packed) if not cp.exists() else None;assert hashlib.sha256(cp.read_bytes()).hexdigest()==digest;dump(O/'prediction_cache.json',{'cache_path':str(cp),'bytes':len(packed),'sha256':digest,'uncompressed_csv_sha256':hashlib.sha256(raw).hexdigest(),'rows':len(p),'columns':list(p.columns),'role':'all hourly and native rolling predictions, including stale/abstention and no-event mass','format':'CSV gzip, UTF8; deterministic gzip mtime0; immutable content address','reproduce':'track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_b.py'});s.to_csv(O/'sensitivity_predictions.csv',index=False,float_format='%.10g');pd.DataFrame(fold).to_csv(O/'fold_membership.csv',index=False)
 # Equal sensor within event, equal event across corpus. Anchors unlike hourly duplicates.
 evaluations=[]
 for name,d in [('hourly',p[p.issue_grid=='hourly']),('native_last48h',p[p.issue_grid=='native_last48h']),('fixed_anchors',s[(s.window_n==16)&(s.q_ratio==.01)])]:
  for (model,H),a in d.groupby(['model_id','horizon_hours']):
   for group,g in a.groupby('event_group'):
    evaluations.append({'evaluation_set':name,'model_id':model,'horizon_hours':H,'event_group':group,'independent_event_count':1,'sensor_count':g.site_id.nunique(),'publication_count':len(g),'ok_publications':int((g.status=='ok').sum()),'known_binary_publications':int(g.target_within_horizon.notna().sum()),'conditional_event_publications_with_interval':int(g.coverage_full_label.notna().sum()),'known_event_publications_including_no_interval':int(g.coverage_full_label_all_known_events.notna().sum()),'coverage_full_label_all_known_events':g.groupby('site_id').coverage_full_label_all_known_events.mean().mean(),'coverage_intersects_label_all_known_events':g.groupby('site_id').coverage_intersects_label_all_known_events.mean().mean(),'brier_sensor_equal':g.groupby('site_id').brier.mean().mean(),'coverage_full_label_sensor_equal':g.groupby('site_id').coverage_full_label.mean().mean(),'coverage_intersects_label_sensor_equal':g.groupby('site_id').coverage_intersects_label.mean().mean(),'conditional_width_hours_sensor_equal':g.groupby('site_id').conditional_width_hours.mean().mean(),'interval_point_error_hours_sensor_equal':g.groupby('site_id').point_error_to_label_interval_hours.mean().mean(),'coverage_semantics':'publication diagnostic within independent group; event counts not publications'})
 e=pd.DataFrame(evaluations);e['primary_evaluation_eligible']=e.event_group!='Veslemannen';e.to_csv(O/'evaluation.csv',index=False,float_format='%.10g')
 summary=e[e.primary_evaluation_eligible].groupby(['evaluation_set','model_id','horizon_hours']).agg(independent_groups=('event_group','nunique'),publications=('publication_count','sum'),ok_publications=('ok_publications','sum'),known_binary_group_denominator=('known_binary_publications',lambda x:int((x>0).sum())),coverage_opportunity_group_denominator=('known_event_publications_including_no_interval',lambda x:int((x>0).sum())),interval_issued_event_group_denominator=('conditional_event_publications_with_interval',lambda x:int((x>0).sum())),brier_group_equal=('brier_sensor_equal','mean'),coverage_full_label_group_equal=('coverage_full_label_sensor_equal','mean'),coverage_full_label_all_event_opportunities=('coverage_full_label_all_known_events','mean'),coverage_intersects_all_event_opportunities=('coverage_intersects_label_all_known_events','mean'),coverage_intersects_label_group_equal=('coverage_intersects_label_sensor_equal','mean'),mean_conditional_width_hours=('conditional_width_hours_sensor_equal','mean'),mean_interval_point_error_hours=('interval_point_error_hours_sensor_equal','mean')).reset_index();summary.to_csv(O/'model_comparison.csv',index=False,float_format='%.10g')
 # Finite-sample split-conformal feasibility using independent groups, not publication rows.
 ng=len(set(regs[regs.primary_evaluation_eligible].event_group));conf=[]
 for group in sorted(set(regs[regs.primary_evaluation_eligible].event_group)):
  ncal=ng-1;rank=math.ceil((ncal+1)*.95);conf.append({'test_group':group,'n_calibration_independent_groups':ncal,'rank95':rank,'finite_95_supported':rank<=ncal,'radius95_hours':None,'radius_status':'infinite_rank_exceeds_calibration_count' if rank>ncal else 'not_computed','exchangeability':'not_established_across_heterogeneous_sites','interpretation':'no finite95distribution_free guarantee'})
 pd.DataFrame(conf).to_csv(O/'conformal_feasibility.csv',index=False)
 tests_t=np.arange(20.,dtype=float);tests_v=1/(50-tests_t);roots=fit_roots(tests_t,tests_v,19.,'B_IV')[0];checks.append({'test':'numerical_alpha2_root_31h','passed':bool(abs(float(np.median(roots[np.isfinite(roots)]))-31)<.05),'evaluation_stratum':'numerical_benchmark'});roots=fit_roots(tests_t,np.ones_like(tests_t),19.,'B_IV')[0];checks.append({'test':'constant_velocity_no_start72h','passed':bool(not np.any((roots>0)&(roots<=72))),'evaluation_stratum':'numerical_benchmark'})
 probs=p[p.status=='ok'];checks.extend([{'test':'probability_normalization','passed':bool(np.allclose(probs.probability_start_within_horizon+probs.probability_no_start_within_horizon,1))},{'test':'conditional_interval_inside_horizon','passed':bool(((probs.conditional_lower_hours>=probs.issue_time_relative_hours)|(probs.conditional_lower_hours.isna())).all() and ((probs.conditional_upper_hours<=probs.issue_time_relative_hours+probs.horizon_hours)|(probs.conditional_upper_hours.isna())).all())},{'test':'past_input_cutoff','passed':bool(((p.last_input_relative_hours<=p.issue_time_relative_hours+1e-7)|p.last_input_relative_hours.isna()).all())},{'test':'no_overlap_test_calibration_groups','passed':all(x['test_group'] not in x['training_groups'].split('|') for x in fold)},{'test':'no_synthetic_in_empirical_groups','passed':not any('demo' in x.lower() for x in set(regs.event_group))}]);dump(O/'validation.json',{'checks':checks,'passed':all(x['passed'] for x in checks),'independent_physical_groups':ng,'sensors':len(regs),'main_rows':len(p),'sensitivity_rows':len(s),'seed':SEED,'draws_per_parameter_state_distribution':NS,'sampling_constraint':'positive current inverse velocity; nonpositive fitted mean abstains; nonnegative trend retained as no-future-zero mass','inputs':{str(q.relative_to(R)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [I/'observations.csv',I/'site_registry.csv',R/'EXPERIMENT_PROTOCOL.md',I/'engine_b_preregistered.md',I/'engine_b_domain_amendment.json']},'dependencies':{'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__}})
 if (O/'predictions.csv').exists():(O/'predictions.csv').unlink() # prior build large CSV now sealed in content-addressed gzip
 plot_results(p,s,regs,obs)
 supplementary(p,s,regs)
 run_censored_challenge()
 print(summary.to_string(index=False));print('checks',all(x['passed'] for x in checks))
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def plot_results(p,s,regs,obs):
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
 groups=['Galterengraben','Grabengufer','Preonzo','Brienz_Insel'];fig,axes=plt.subplots(2,2,figsize=(11,7.4),constrained_layout=True)
 for ax,grp in zip(axes.ravel(),groups):
  g=p[(p.event_group==grp)&(p.horizon_hours==72)&(p.issue_grid=='hourly')];site=sorted(set(g.site_id))[0] if len(g) else '';g=g[g.site_id==site]
  for model,c in [('B_IV','#266e9e'),('B_SS','#c46628')]:
   a=g[(g.model_id==model)&(g.issue_time_relative_hours>=g.failure_lower_hours-168)];x=a.issue_time_relative_hours-a.failure_lower_hours;med=a.conditional_median_hours-a.failure_lower_hours;low=a.conditional_lower_hours-a.failure_lower_hours;up=a.conditional_upper_hours-a.failure_lower_hours;ax.plot(x,med,label=model,color=c,lw=1.3);ax.fill_between(x,low,up,color=c,alpha=.13)
  ax.axhline(0,color='black',lw=.8,ls='--');ax.set_title(grp+' (one physical event)');ax.set_xlabel('Issue hours before label lower');ax.set_ylabel('Forecast offset from label lower (h)');ax.set_ylim(-180,80)
 axes[0,0].legend(frameon=False);fig.suptitle('External terminal-collapse replay: conditional 95% model intervals\nNot local first-motion validation; missing segments retain abstention/no in-horizon roots',fontsize=12);fig.savefig(O/'rolling_comparison.png',dpi=160);plt.close(fig)
 fig,ax=plt.subplots(figsize=(11,5.3),constrained_layout=True)
 a=s[(s.horizon_hours==72)&(s.window_n==16)&(s.q_ratio==.01)&(s.anchor_lead_hours==24)&s.primary_evaluation_eligible]
 groups=sorted(set(a.event_group));x=np.arange(len(groups));
 for model,delta,c in [('B_IV',-.17,'#266e9e'),('B_SS',.17,'#c46628')]:
  v=[a[(a.event_group==grp)&(a.model_id==model)].probability_start_within_horizon.mean() for grp in groups];ax.bar(x+delta,v,.32,color=c,label=model)
  for xx,vv in zip(x+delta,v):
   if not np.isfinite(vv):ax.plot([xx],[.015],marker='x',color='#9d2d2d');ax.text(xx,.045,'NA',ha='center',fontsize=8,color='#9d2d2d')
 ax.set_xticks(x,groups,rotation=42,ha='right');ax.set_ylim(0,1);ax.set_ylabel('p(collapse zero within 72h)');ax.set_title('Fixed retrospective issue = label lower minus 24h; 13 physical groups\nNA = stale / insufficient / not monitored; Veslemannen clock-uncertain excluded');ax.legend(frameon=False);fig.savefig(O/'event_probabilities.png',dpi=160);plt.close(fig)

def load_predictions():
 j=json.loads((O/'prediction_cache.json').read_text());p=Path(j['cache_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==j['sha256'];raw=gzip.decompress(p.read_bytes());assert hashlib.sha256(raw).hexdigest()==j['uncompressed_csv_sha256'];import io
 return pd.read_csv(io.BytesIO(raw))
def supplementary(p,s,regs):
 opportunities=[];alerts=[]
 for name,d in [('hourly',p[p.issue_grid=='hourly']),('native_last48h',p[p.issue_grid=='native_last48h']),('fixed_anchors',s[(s.window_n==16)&(s.q_ratio==.01)])]:
  d=d[d.primary_evaluation_eligible]
  for (model,H,grp),a in d.groupby(['model_id','horizon_hours','event_group']):
   known=a.target_within_horizon.notna();scored=a.brier.notna();positive=a.target_within_horizon.eq(1);negative=a.target_within_horizon.eq(0);warning=a.probability_start_within_horizon.ge(.5);L=float(a.failure_lower_hours.iloc[0])
   opportunities.append({'evaluation_set':name,'model_id':model,'horizon_hours':H,'event_group':grp,'independent_event_count':1,'opportunities':len(a),'known_binary_opportunities':int(known.sum()),'probability_scored_opportunities':int(scored.sum()),'abstain_or_no_prediction_opportunities':int(a.probability_start_within_horizon.isna().sum()),'known_positive_opportunities':int(positive.sum()),'positive_with_conditional_interval':int(a.coverage_full_label.notna().sum()),'primary_evaluation_eligible':True})
   alerts.append({'evaluation_set':name,'model_id':model,'horizon_hours':H,'event_group':grp,'threshold':.5,'threshold_status':'fixed descriptive convention, not optimized','known_negative_opportunities':int(negative.sum()),'false_alarm_opportunities':int((negative&warning).sum()),'known_positive_opportunities':int(positive.sum()),'detected_positive_opportunities':int((positive&warning).sum()),'missed_positive_including_abstentions':int((positive&~warning).sum()),'any_alarm_lead_to_label_lower_hours':L-a.loc[warning,'issue_time_relative_hours'].min() if warning.any() else np.nan,'first_correct_in_horizon_alarm_lead_to_label_lower_hours':L-a.loc[positive&warning,'issue_time_relative_hours'].min() if (positive&warning).any() else np.nan,'late_after_failure_hours':None,'late_reason':'replay stops before label lower; no post-failure publication','independent_event_count':1,'false_alarm_interpretation':'within failure-selected monitoring windows only; not general stable-slope false-alarm rate'})
 paired=[]
 for name,d in [('hourly',p[p.issue_grid=='hourly']),('native_last48h',p[p.issue_grid=='native_last48h']),('fixed_anchors',s[(s.window_n==16)&(s.q_ratio==.01)])]:
  d=d[d.primary_evaluation_eligible];keys=['site_id','event_group','issue_grid','issue_time_relative_hours','horizon_hours'];aa=d[d.model_id=='B_IV'][keys+['brier']];bb=d[d.model_id=='B_SS'][keys+['brier']];m=aa.merge(bb,on=keys,suffixes=('_IV','_SS'),validate='one_to_one');m=m.dropna(subset=['brier_IV','brier_SS'])
  for (H,grp),gg in m.groupby(['horizon_hours','event_group']):paired.append({'evaluation_set':name,'horizon_hours':H,'event_group':grp,'paired_publications':len(gg),'paired_brier_IV':gg.groupby('site_id').brier_IV.mean().mean(),'paired_brier_SS':gg.groupby('site_id').brier_SS.mean().mean(),'independent_group_count':1})
 pc=pd.DataFrame(paired);pc.to_csv(O/'paired_model_by_group.csv',index=False,float_format='%.10g');pc.groupby(['evaluation_set','horizon_hours']).agg(paired_group_denominator=('event_group','nunique'),paired_publications=('paired_publications','sum'),paired_brier_IV=('paired_brier_IV','mean'),paired_brier_SS=('paired_brier_SS','mean')).reset_index().to_csv(O/'paired_model_comparison.csv',index=False,float_format='%.10g')
 op=pd.DataFrame(opportunities);op.to_csv(O/'opportunity_denominators.csv',index=False);pd.DataFrame(alerts).to_csv(O/'alert_metrics.csv',index=False,float_format='%.10g')
 q=op.groupby(['evaluation_set','model_id','horizon_hours']).agg(probability_scored_group_denominator=('probability_scored_opportunities',lambda x:int((x>0).sum())),probability_scored_opportunities=('probability_scored_opportunities','sum'),abstain_or_no_prediction_opportunities=('abstain_or_no_prediction_opportunities','sum')).reset_index();m=pd.read_csv(O/'model_comparison.csv');m=m.drop(columns=[c for c in q.columns if c in m.columns and c not in ['evaluation_set','model_id','horizon_hours']]);m.merge(q,on=['evaluation_set','model_id','horizon_hours'],how='left').to_csv(O/'model_comparison.csv',index=False,float_format='%.10g')
 w=s[s.primary_evaluation_eligible].groupby(['model_id','horizon_hours','window_n','q_ratio','anchor_lead_hours','event_group']).agg(brier=('brier','mean'),issued_probability=('probability_start_within_horizon',lambda x:int(x.notna().sum())),opportunities=('probability_start_within_horizon','size'),full_event_coverage_including_abstentions=('coverage_full_label_all_known_events','mean'),interval_width_hours=('conditional_width_hours','mean')).reset_index();w.to_csv(O/'window_noise_comparison.csv',index=False,float_format='%.10g')
 # One fixed primary sensor per physical group, selected lexicographically without outcome scores.
 primary=regs[regs.primary_evaluation_eligible].sort_values('site_id').drop_duplicates('event_group').set_index('event_group').site_id.to_dict();an=s[(s.window_n==16)&(s.q_ratio==.01)&s.primary_evaluation_eligible].copy();an=an[an.apply(lambda row:row.site_id==primary[row.event_group],axis=1)];an.to_csv(O/'anchor_primary_sensor_predictions.csv',index=False,float_format='%.10g');ac=[]
 for (model,H,lead),g in an.groupby(['model_id','horizon_hours','anchor_lead_hours']):
  ev=g.target_within_horizon.eq(1);known=g.target_within_horizon.notna();sc=g.brier.notna();has=g.conditional_lower_hours.notna();ac.append({'model_id':model,'horizon_hours':H,'anchor_lead_hours':lead,'independent_group_opportunities':g.event_group.nunique(),'known_event_groups':int(ev.sum()),'known_binary_groups':int(known.sum()),'probability_scored_groups':int(sc.sum()),'abstain_groups':int(g.probability_start_within_horizon.isna().sum()),'brier_scored_groups':g.brier.mean(),'known_events_with_interval':int((ev&has).sum()),'full_label_covered_events_including_abstentions':int(g.coverage_full_label_all_known_events.fillna(0).sum()),'label_intersected_events_including_abstentions':int(g.coverage_intersects_label_all_known_events.fillna(0).sum()),'full_label_coverage_all_known_events':g.coverage_full_label_all_known_events.mean(),'label_intersection_all_known_events':g.coverage_intersects_label_all_known_events.mean(),'mean_conditional_interval_width_hours':g.loc[ev&has,'conditional_width_hours'].mean(),'sensor_policy':'lexicographic fixed primary per physical group; Brienz715; no performance selection','evaluation_role':'retrospective fixed lead from label lower; not prospective station enrollment'})
 pd.DataFrame(ac).to_csv(O/'anchor_event_counts.csv',index=False,float_format='%.10g')
 # Audit all returned horizons without treating repeated publications as independent failures.
 vp=p[p.status=='ok'].pivot_table(index=['model_id','site_id','issue_grid','issue_time_relative_hours'],columns='horizon_hours',values='probability_start_within_horizon');monotonic=bool(((vp[24]<=vp[48]+1e-12)&(vp[48]<=vp[72]+1e-12)).all())
 extra_checks=[]
 for model in ('B_IV','B_SS'):
  nt=np.arange(20.,dtype=float);nv=1/(50-nt);a=fit_roots(nt,nv,19.,model)[0];b=fit_roots(nt,nv*100,19.,model)[0];extra_checks.append({'test':'positive_unit_scale_invariant_zero_time_'+model,'passed':bool(np.allclose(a,b,rtol=1e-9,atol=1e-8)),'evaluation_stratum':'numerical_benchmark'})
 vj=json.loads((O/'validation.json').read_text());vj['checks']=[x for x in vj['checks'] if x['test']!='horizon_probability_monotonicity' and not x['test'].startswith('positive_unit_scale_invariant')];vj['checks'].extend(extra_checks);vj['checks'].append({'test':'horizon_probability_monotonicity','passed':monotonic,'publication_groups_checked':len(vp)});vj['passed']=all(x['passed'] for x in vj['checks']);vj['prediction_cache']=json.loads((O/'prediction_cache.json').read_text());dump(O/'validation.json',vj)
 p.assign(conditional_draw_count=lambda x:(x.probability_start_within_horizon*NS).round()).groupby(['model_id','horizon_hours','issue_grid']).conditional_draw_count.agg(['count','min','median',lambda x:int(((x>0)&(x<20)).sum())]).rename(columns={'<lambda_0>':'positive_conditional_draws_lt20'}).to_csv(O/'conditional_mc_quality.csv')
 # Diagnostic: how far is the last velocity point? Preserve rather than silently ignore sparse windows.
 p[p.status=='ok'].assign(last_velocity_age_hours=lambda x:x.issue_time_relative_hours-x.last_input_relative_hours).groupby('site_id').last_velocity_age_hours.agg(['count','median','max']).to_csv(O/'velocity_observation_age.csv')
def run_censored_challenge():
 from types import SimpleNamespace
 ip=R/'inputs/survival/stampa_observations.csv';rp=R/'inputs/survival/stampa_site_registry.csv'
 if not (ip.exists() and rp.exists()):dump(O/'censored_challenge.json',{'status':'not_executed_missing_stable_C_packet'});return
 a=pd.read_csv(ip);rr=pd.read_csv(rp).iloc[0];assert not bool(rr.event_observed) and bool(rr.censoring_verified)
 t=a.time_relative_hours.to_numpy(float);v=causal_vel(t,a.displacement.to_numpy(float));end=float(rr.followup_end_hours);reg=SimpleNamespace(failure_lower_hours=float('inf'),failure_upper_hours=float('inf'),label_kind='right_censored_terminal_collapse',event_group=rr.event_group,primary_evaluation_eligible=True);pred=[]
 for model in ('B_IV','B_SS'):
  for grid,issues in [('hourly_last30d',np.arange(max(math.ceil(t[11]),math.ceil(end-720)),math.floor(end)+1)),('native_full_censored_exposure',t[11:])]:
   for issue in issues:
    rows=one_prediction(t,v,float(issue),model,rr.site_id,reg,grid)
    for row in rows:
     row['failure_lower_hours']=None;row['failure_upper_hours']=None;row['target_within_horizon']=0 if issue+row['horizon_hours']<=end else np.nan;row['brier']=row['probability_start_within_horizon']**2 if np.isfinite(row['target_within_horizon']) else np.nan;row['evaluation_stratum']='external_transfer';row['unit_note']='original source displacement unit unknown; zero-crossing duration invariant under positive unit scale';row['label_semantics']='right-censored before documented later collapse; no failure time inferred';row['censor_time_hours']=end
    pred.extend(rows)
 p=pd.DataFrame(pred);raw=p.to_csv(index=False,float_format='%.10g').encode();packed=gzip.compress(raw,mtime=0);h=hashlib.sha256(packed).hexdigest();path=Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q3/deformation/outputs')/('engine_b_stampa_'+h+'.csv.gz');path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists():path.write_bytes(packed)
 dump(O/'censored_challenge.json',{'status':'executed','physical_sites':1,'observed_failure_events':0,'verified_right_censored_sites':1,'calendar_monitoring_days':725,'exposure_duration_hours':end,'source':'C-owned stable Stampa packet, official author MWCD data and primary article; sources/survival_stampa_article.html + results/survival_sources.json','data_inputs':[{'path':str(q.relative_to(R)),'sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'bytes':q.stat().st_size} for q in [ip,rp]],'full_prediction_cache':{'cache_path':str(path),'sha256':h,'bytes':len(packed),'rows':len(p),'uncompressed_csv_sha256':hashlib.sha256(raw).hexdigest()},'unit_note':'unknown source displacement unit; time-to-zero scale invariant; no physical speed threshold claimed','censoring_rule':'binarynegative only if full future horizon ends within verified followup; after-followup outcome unknown'})
 p['false_alarm_evaluable']=np.where(p.target_within_horizon.eq(0),p.probability_start_within_horizon.ge(.5).astype(float),np.nan)
 p.groupby(['issue_grid','model_id','horizon_hours']).agg(publications=('site_id','size'),probability_predictions=('probability_start_within_horizon','count'),known_negative_opportunities=('target_within_horizon','count'),probability_scored_negative_opportunities=('brier','count'),brier=('brier','mean'),mean_p_start=('probability_start_within_horizon','mean'),false_alarm_count_p_ge_half=('false_alarm_evaluable','sum')).reset_index().to_csv(O/'censored_evaluation.csv',index=False,float_format='%.10g')
if __name__=='__main__':
 import sys
 if '--summarize-only' in sys.argv:
  p=load_predictions();s=pd.read_csv(O/'sensitivity_predictions.csv');regs=pd.read_csv(I/'site_registry.csv');supplementary(p,s,regs);plot_results(p,s,regs,pd.read_csv(I/'observations.csv'));run_censored_challenge()
 else:main()

