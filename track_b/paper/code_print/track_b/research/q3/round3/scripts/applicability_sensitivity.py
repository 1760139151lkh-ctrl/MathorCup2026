#!/usr/bin/env python3
"""Post-hoc experimental-domain reweighting of frozen scenarios; no physics run."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]
O=R/'results/applicability_sensitivity';A=R/'results/mechanistic_replay/analytic_erfc'
Q=R/'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1/files'
PRIORS=['uniform_design_assumption','equal_mechanism_then_design_assumption','fragile_issue_initial_margin_assumption']
POLICIES=['original_design','all_observed_states_in_experiment_domain','observed_domain_fraction_weight','out_of_domain_mass_to_unknown']
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def rec(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p))

def summarize(g,H,prior,policy):
    margin=g.initial_margin_at_issue.to_numpy(float);original_risk=g.known_at_risk_under_conditional_history.to_numpy(bool);risk=original_risk.copy()
    point=g.crossing_point_hours_after_issue.to_numpy(float);length=g.followup_hours.to_numpy(int)
    domain=g.strength_domain_fraction_observed.to_numpy(float)
    if prior==PRIORS[0]:base=np.ones(len(g))
    elif prior==PRIORS[1]:base=1/g.groupby('mechanism_id').mechanism_id.transform('size').to_numpy(float)
    else:base=np.exp(-np.clip(margin,0,10))
    base=base/base.sum()
    valid=domain>=1-1e-12
    factor=np.ones(len(g)) if policy in [POLICIES[0],POLICIES[3]] else valid.astype(float) if policy==POLICIES[1] else domain
    raw=base*factor;retained=float(raw.sum());w=raw/retained if retained>0 else np.zeros(len(g))
    original_event=original_risk&np.isfinite(point)&(point<=H)
    original_no=original_risk&((np.isfinite(point)&(point>H))|(~np.isfinite(point)&(length>=H)))
    original_unknown=original_risk&~(original_event|original_no)
    if policy==POLICIES[3]:
        risk=(original_risk&valid)|~valid
        event=original_event&valid;no=original_no&valid
    else:event=original_event;no=original_no
    unknown=risk&~(event|no);positive=w>0
    rm=float(w[risk].sum());em=float(w[event].sum());nm=float(w[no].sum());um=float(w[unknown].sum())
    lo=em/rm if rm>0 else None;hi=(em+um)/rm if rm>0 else None
    identified=rm>0 and um<1e-12;prob=lo if identified else None;qt=[None,None,None]
    if identified and em>0:
        use=event&positive;x=point[use];ew=w[use];order=np.argsort(x);x=x[order];cw=np.cumsum(ew[order])/ew.sum()
        qt=[float(x[min(np.searchsorted(cw,q),len(x)-1)]) for q in [.025,.5,.975]]
    _,inv=np.unique(g.parameter_set_id.to_numpy(),return_inverse=True)
    design_risk_mass=np.bincount(inv,weights=w*risk);positive_designs=int((design_risk_mass>0).sum())
    ess=float(rm*rm/np.square(design_risk_mass).sum()) if rm>0 else None
    status='no_positive_total_weight' if retained==0 else 'no_positive_at_risk_weight' if rm==0 else 'identified_finite_discrete_design_only' if identified else 'unresolved_future_positive_weight'
    return dict(horizon_hours=H,probability_prior=prior,applicability_policy=policy,
      probability_start_within_horizon=prob,probability_no_start_within_horizon=1-prob if prob is not None else None,
      probability_start_lower=lo,probability_start_upper=hi,probability_no_start_lower=1-hi if hi is not None else None,probability_no_start_upper=1-lo if lo is not None else None,
      conditional_lower_hours=qt[0],conditional_median_hours=qt[1],conditional_upper_hours=qt[2],conditional_interval_level=.95,
      already_started_prior_mass=float(w[~risk].sum()),at_risk_prior_mass=rm,event_prior_mass=em,no_start_prior_mass=nm,unresolved_future_prior_mass=um,
      original_history_already_started_prior_mass=float(base[~original_risk].sum()),
      out_of_domain_originally_already_started_mass=float(base[~original_risk&~valid].sum()),
      out_of_domain_prior_mass=float(base[~valid].sum()),
      original_prior_mass_retained=retained,original_prior_mass_zero_weighted=float(base[factor==0].sum()),
      event_original_prior_mass_removed=float((base[original_event]*(1-factor[original_event])).sum()),
      unknown_original_prior_mass_removed=float((base[original_unknown]*(1-factor[original_unknown])).sum()),
      already_started_original_prior_mass_removed=float((base[~original_risk]*(1-factor[~original_risk])).sum()),
      original_scenario_count=len(g),positive_weight_scenario_count=int(positive.sum()),zero_weight_scenario_count=int((~positive).sum()),
      original_at_risk_count=int(original_risk.sum()),positive_weight_at_risk_count=int((risk&positive).sum()),
      raw_event_scenario_count=int(original_event.sum()),positive_weight_event_count=int((event&positive).sum()),
      positive_weight_unknown_count=int((unknown&positive).sum()),original_unknown_count=int(original_unknown.sum()),
      positive_weight_at_risk_physical_design_count=positive_designs,at_risk_physical_design_ESS=ess,
      event_physical_design_count=int(g.loc[event&positive,'parameter_set_id'].nunique()),identification_status=status,
      conditional_interval_interpretation='posthoc_assumed_design_given_event; no interval without event support',
      data_role='scenario',evaluation_stratum='retrospective_model_applicability_sensitivity',available_time=None,
      domain_rule_uses_future_scenario=True,operational_filter_approved=False,local_material_domain_certified=False,
      independent_observed_events=0,empirical_coverage=None)

def main():
    O.mkdir(parents=True,exist_ok=True)
    assert (O/'PROTOCOL.md').exists()
    inputs=[A/'parameter_first_passages.parquet',A/'predictions.csv.gz',Q/'results/analytic_thermal/parameter_ensemble.csv',
      Q/'results/analytic_thermal/scenario_outcomes.csv',Q/'scripts/mechanism_engine.py',O/'PROTOCOL.md',Path(__file__)]
    assert sha(inputs[0])=='fd557599f6fa54ad21bd7a44dd19aa74f5578ce73533db1ad8aeef19de2688d5'
    assert sha(inputs[1])=='a3dc1602e9d4ea7c80173286f5e78e5ef6cc15b2e00a0b0fb5d33f5ff3fa122d'
    registration=dict(registered_at_utc=datetime.now(timezone.utc).isoformat(),base_research_commit='bb9258d791a6e9735c28528ff4408c7434c3d149',
       analysis_is_posthoc=True,physics_rerun=False,inputs=[rec(p) for p in inputs],policies=POLICIES,original_assumed_priors=PRIORS)
    dump(O/'input_registration.json',registration)
    params=pd.read_csv(inputs[2]);p=params[params.parameter_set_id.eq('q2r3-p0149')].copy()
    p['normal_stress_kpa_independent']=p.density_kg_m3*9.80665*p.thickness_normal_m*np.cos(np.deg2rad(p.theta_deg))/1000
    p.to_csv(O/'p0149_parameter_audit.csv',index=False)
    outcomes=pd.read_csv(inputs[3]);outcomes[outcomes.parameter_set_id.eq('q2r3-p0149')].to_csv(O/'p0149_full_history_outcomes.csv',index=False)
    predictions=[];crossings=[];partitions=[];offset=0;tracks=0;writer=None
    try:
      for batch in pq.ParquetFile(inputs[0]).iter_batches(batch_size=2048):
        f=batch.to_pandas();assert len(f)==2048 and f.base_scenario_id.nunique()==2048 and f.issue_time.nunique()==1
        assert f.followup_hours.nunique()==1 and f.forcing_status.nunique()==1
        domain=f.strength_domain_fraction_observed.to_numpy(float);assert np.isfinite(domain).all() and ((domain>=0)&(domain<=1)).all()
        audit=f[['issue_time','base_scenario_id','parameter_set_id','mechanism_id','law_policy','history_status','forecast_status','followup_hours','strength_domain_fraction_observed']].copy()
        audit['source_zero_based_row_number']=np.arange(offset,offset+len(f));audit['strict_observed_domain_factor']=domain>=1-1e-12
        audit['fraction_domain_factor']=domain
        tab=pa.Table.from_pandas(audit,preserve_index=False)
        if writer is None:writer=pq.ParquetWriter(O/'parameter_weight_audit.parquet',tab.schema,compression='zstd')
        writer.write_table(tab);offset+=len(f);tracks+=1
        crossed=f[f.crossing_point_hours_after_issue.notna()].copy()
        if len(crossed):crossings.append(crossed)
        groups=[('mechanism_policy_mixture','all_delivered_mechanisms','mixture_of_both_law_policies',f)]
        groups.extend((m,mech,law,g) for (m,mech,law),g in f.groupby(['model_id','mechanism_id','law_policy'],sort=True))
        common=f.iloc[0][['issue_time','forecast_input_mode','space_object','assumed_latency_hours','forecast_reference_time','forcing_status','followup_hours']].to_dict()
        for model,mech,law,g in groups:
          partitions.append(dict(common,model_id=model,mechanism_id=mech,law_policy=law,rows=len(g),
             fully_observed_in_domain=int((g.strength_domain_fraction_observed>=1-1e-12).sum()),
             no_observed_state_in_domain=int((g.strength_domain_fraction_observed==0).sum()),
             partially_in_domain=int(((g.strength_domain_fraction_observed>0)&(g.strength_domain_fraction_observed<1-1e-12)).sum())))
          for policy in POLICIES:
           for prior in PRIORS:
            for H in [24,48,72]:predictions.append(dict(common,model_id=model,mechanism_id=mech,law_policy=law,**summarize(g,H,prior,policy)))
        if tracks%150==0:print(json.dumps({'tracks':tracks,'physics_rerun':False}),flush=True)
    finally:
        if writer:writer.close()
    cf=pd.concat(crossings,ignore_index=True);cf.to_csv(O/'crossing_support_audit.csv',index=False)
    pd.DataFrame(partitions).to_csv(O/'domain_partition_by_track.csv',index=False)
    pred=pd.DataFrame(predictions);pred.to_csv(O/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    keys=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','model_id','mechanism_id','law_policy','horizon_hours','probability_prior']
    original=pd.read_csv(inputs[1]);same=pred[pred.applicability_policy.eq('original_design')].merge(original,on=keys,suffixes=('_new','_old'),validate='one_to_one')
    fields=['probability_start_within_horizon','probability_no_start_within_horizon','probability_start_lower','probability_start_upper','conditional_lower_hours','conditional_median_hours','conditional_upper_hours','already_started_prior_mass','at_risk_prior_mass','event_prior_mass','no_start_prior_mass','unresolved_future_prior_mass']
    deltas={};nullsame={}
    for k in fields:
        x=same[k+'_new'];y=same[k+'_old'];nullsame[k]=bool(x.isna().equals(y.isna()));d=(x-y).abs().dropna();deltas[k]=float(d.max()) if len(d) else 0.
    checks={'full_750_tracks_1536000_rows':tracks==750 and offset==1536000,
      'all_342_crossing_rows_have_zero_observed_domain_fraction':len(cf)==342 and cf.strength_domain_fraction_observed.eq(0).all(),
      'all_crossings_same_single_S_parameter_design':cf.parameter_set_id.nunique()==1 and cf.parameter_set_id.iloc[0]=='q2r3-p0149' and cf.mechanism_id.eq('S').all(),
      'original_60750_distributions_reproduced':len(same)==60750 and all(nullsame.values()) and max(deltas.values())<1e-12,
      'strict_and_fraction_zero_positive_weight_events':pred.loc[pred.applicability_policy.ne('original_design'),'positive_weight_event_count'].eq(0).all(),
      'unknown_positive_weight_never_exact_probability':pred.loc[pred.unresolved_future_prior_mass>1e-12,'probability_start_within_horizon'].isna().all(),
      'empty_positive_risk_has_null_probability':pred.loc[pred.at_risk_prior_mass.eq(0),'probability_start_within_horizon'].isna().all(),
      'zero_event_support_has_no_conditional_time_interval':pred.loc[pred.event_physical_design_count.eq(0),'conditional_lower_hours'].isna().all(),
      'no_historical_availability_or_local_validation_inferred':pred.available_time.isna().all() and pred.empirical_coverage.isna().all()}
    agg=pred.groupby(['applicability_policy','probability_prior','horizon_hours']).agg(rows=('model_id','size'),
      identified_probability_rows=('probability_start_within_horizon','count'),maximum_identified_probability=('probability_start_within_horizon','max'),
      maximum_probability_upper_bound=('probability_start_upper','max'),minimum_positive_weight_risk_designs=('positive_weight_at_risk_physical_design_count','min'),
      zero_risk_rows=('at_risk_prior_mass',lambda x:int(x.eq(0).sum())),unresolved_rows=('probability_start_within_horizon',lambda x:int(x.isna().sum())),
      maximum_event_support=('event_physical_design_count','max')).reset_index();agg.to_csv(O/'comparison_summary.csv',index=False)
    summary=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),physics_rerun=False,prediction_rows=len(pred),parameter_rows=offset,
      original_distribution_rows_verified=len(same),original_maximum_numeric_difference=deltas,original_null_patterns_identical=nullsame,
      crossing_rows=len(cf),crossing_unique_physical_designs=int(cf.parameter_set_id.nunique()),crossing_domain_fraction_all_zero=bool(cf.strength_domain_fraction_observed.eq(0).all()),
      p0149_normal_stress_kpa=float(p.normal_stress_kpa_independent.iloc[0]),
      checks={k:bool(v) for k,v in checks.items()},passed=all(checks.values()),
      interpretation='Current nonzero finite-design future-onset mass is wholly supported by trajectories outside implemented shear-law experiment domain. Retrospective reweighting removes that support; no safety, calibrated probability, material certification or operational eligibility is established.')
    dump(O/'summary.json',summary);dump(O/'validation.json',dict(checks=summary['checks'],passed=summary['passed'],local_truth_events=0,physics_rerun=False))
    assert summary['passed'],checks;print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
