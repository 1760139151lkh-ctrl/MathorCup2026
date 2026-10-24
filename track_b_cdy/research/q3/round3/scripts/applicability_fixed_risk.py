#!/usr/bin/env python3
"""Fixed-history-risk primary applicability contrast; no physics rerun."""
from datetime import datetime,timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from applicability_sensitivity import R,O,A,PRIORS,summarize,rec,sha,dump
N=O/'risk_set_revision';POLICY='fixed_history_risk_out_of_domain_to_unknown';DIAG='revoke_out_of_domain_history_classification_diagnostic'

def fixed_summary(g,H,prior):
    r=summarize(g,H,prior,'original_design')
    margin=g.initial_margin_at_issue.to_numpy(float);risk=g.known_at_risk_under_conditional_history.to_numpy(bool)
    point=g.crossing_point_hours_after_issue.to_numpy(float);length=g.followup_hours.to_numpy(int);valid=g.strength_domain_fraction_observed.to_numpy(float)>=1-1e-12
    if prior==PRIORS[0]:w=np.ones(len(g))
    elif prior==PRIORS[1]:w=1/g.groupby('mechanism_id').mechanism_id.transform('size').to_numpy(float)
    else:w=np.exp(-np.clip(margin,0,10))
    w=w/w.sum();original_event=risk&np.isfinite(point)&(point<=H)
    original_no=risk&((np.isfinite(point)&(point>H))|(~np.isfinite(point)&(length>=H)))
    event=original_event&valid;no=original_no&valid;unknown=risk&~(event|no)
    rm=float(w[risk].sum());em=float(w[event].sum());nm=float(w[no].sum());um=float(w[unknown].sum())
    lo=em/rm if rm else None;hi=(em+um)/rm if rm else None;p=lo if rm and um<1e-12 else None;q=[None,None,None]
    if p is not None and em>0:
        x=point[event];ww=w[event];order=np.argsort(x);x=x[order];cw=np.cumsum(ww[order])/ww.sum();q=[float(x[min(np.searchsorted(cw,t),len(x)-1)]) for t in [.025,.5,.975]]
    r.update(applicability_policy=POLICY,probability_start_within_horizon=p,probability_no_start_within_horizon=1-p if p is not None else None,
      probability_start_lower=lo,probability_start_upper=hi,probability_no_start_lower=1-hi if hi is not None else None,probability_no_start_upper=1-lo if lo is not None else None,
      conditional_lower_hours=q[0],conditional_median_hours=q[1],conditional_upper_hours=q[2],
      event_prior_mass=em,no_start_prior_mass=nm,unresolved_future_prior_mass=um,positive_weight_event_count=int(event.sum()),
      positive_weight_unknown_count=int(unknown.sum()),event_physical_design_count=int(g.loc[event,'parameter_set_id'].nunique()),
      event_mass_transferred_to_unknown=float(w[original_event&~valid].sum()),no_start_mass_transferred_to_unknown=float(w[original_no&~valid].sum()),
      already_started_mass_transferred_to_unknown=0.,risk_set_definition='fixed_original_conditional_history',
      identification_status='no_original_risk' if not rm else 'identified_finite_discrete_design_only' if p is not None else 'positive_unknown_in_fixed_original_risk')
    return r

def main():
    N.mkdir(parents=True,exist_ok=True);assert (N/'PROTOCOL.md').exists()
    paths=[A/'parameter_first_passages.parquet',O/'predictions.csv.gz',O/'conservative_mass_transfers.csv.gz',N/'PROTOCOL.md',Path(__file__),R/'scripts/applicability_sensitivity.py']
    dump(N/'input_registration.json',dict(registered_at_utc=datetime.now(timezone.utc).isoformat(),physics_rerun=False,inputs=[rec(p) for p in paths],primary_risk_set='original_conditional_history'))
    rows=[];tracks=0
    for b in pq.ParquetFile(paths[0]).iter_batches(batch_size=2048):
        f=b.to_pandas();assert len(f)==2048
        common=f.iloc[0][['issue_time','forecast_input_mode','space_object','assumed_latency_hours','forecast_reference_time','forcing_status','followup_hours']].to_dict()
        groups=[('mechanism_policy_mixture','all_delivered_mechanisms','mixture_of_both_law_policies',f)]
        groups.extend((m,mech,law,g) for (m,mech,law),g in f.groupby(['model_id','mechanism_id','law_policy'],sort=True))
        for model,mech,law,g in groups:
          for prior in PRIORS:
           for H in [24,48,72]:rows.append(dict(common,model_id=model,mechanism_id=mech,law_policy=law,**fixed_summary(g,H,prior)))
        tracks+=1
        if tracks%250==0:print(json.dumps({'tracks':tracks,'physics_rerun':False}),flush=True)
    fixed=pd.DataFrame(rows);fixed.to_csv(N/'fixed_history_risk_predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    old=pd.read_csv(paths[1],low_memory=False);old.loc[old.applicability_policy.eq('out_of_domain_mass_to_unknown'),'applicability_policy']=DIAG
    old['risk_set_definition']=np.where(old.applicability_policy.eq(DIAG),'out_of_domain_history_classification_revoked','original_conditional_history')
    combined=pd.concat([old,fixed],ignore_index=True);combined.to_csv(N/'five_policy_predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    keys=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','model_id','mechanism_id','law_policy','horizon_hours','probability_prior']
    origin=old[old.applicability_policy.eq('original_design')];pair=fixed.merge(origin,on=keys,suffixes=('_fixed','_original'),validate='one_to_one')
    trans=pd.read_csv(paths[2]);trans['fixed_risk_unknown_mass']=trans.original_future_unknown_mass+trans.event_mass_transferred_to_unknown+trans.no_start_mass_transferred_to_unknown
    trans['fixed_risk_known_event_mass']=trans.original_event_mass-trans.event_mass_transferred_to_unknown
    trans['fixed_risk_known_no_start_mass']=trans.original_no_start_mass-trans.no_start_mass_transferred_to_unknown
    trans['fixed_risk_already_started_mass']=trans.original_already_started_mass;trans['fixed_risk_already_started_mass_transferred_to_unknown']=0.
    trans.to_csv(N/'fixed_and_revoked_history_mass_comparison.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    mixture=fixed[fixed.model_id=='mechanism_policy_mixture'];mp=mixture.merge(trans,on=[k for k in keys if k not in ['model_id','mechanism_id','law_policy']],validate='one_to_one')
    checks={'750_tracks_and_60750_new_fixed_risk_rows':tracks==750 and len(fixed)==60750,'five_named_policies_303750_rows':len(combined)==303750 and combined.applicability_policy.nunique()==5,
       'original_history_risk_mass_unchanged':bool(np.allclose(pair.at_risk_prior_mass_fixed,pair.at_risk_prior_mass_original)),
       'original_already_started_mass_unchanged':bool(np.allclose(pair.already_started_prior_mass_fixed,pair.already_started_prior_mass_original)),
       'no_already_started_mass_transferred':fixed.already_started_mass_transferred_to_unknown.eq(0).all(),
       'fixed_risk_four_way_mass_preserved':bool(np.allclose(fixed[['already_started_prior_mass','event_prior_mass','no_start_prior_mass','unresolved_future_prior_mass']].sum(axis=1),1)),
       'mixture_unknown_matches_explicit_category_transfers':bool(np.allclose(mp.unresolved_future_prior_mass,mp.fixed_risk_unknown_mass)),
       'positive_unknown_never_precise_probability':fixed.loc[fixed.unresolved_future_prior_mass>1e-12,'probability_start_within_horizon'].isna().all(),
       'old_diagnostic_preserved_under_separate_name':len(old[old.applicability_policy.eq(DIAG)])==60750,
       'zero_event_support_no_conditional_interval':fixed.loc[fixed.event_physical_design_count.eq(0),'conditional_lower_hours'].isna().all()}
    combined.groupby(['applicability_policy','probability_prior','horizon_hours']).agg(rows=('model_id','size'),identified_probability_rows=('probability_start_within_horizon','count'),
      maximum_identified_probability=('probability_start_within_horizon','max'),minimum_upper_bound=('probability_start_upper','min'),maximum_upper_bound=('probability_start_upper','max')).reset_index().to_csv(N/'comparison_summary.csv',index=False)
    summary=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),physics_rerun=False,primary_policy=POLICY,secondary_history_revocation_diagnostic=DIAG,
      fixed_risk_rows=len(fixed),five_policy_rows=len(combined),fixed_precise_probability_rows=int(fixed.probability_start_within_horizon.notna().sum()),
      fixed_lower_bound_min=float(fixed.probability_start_lower.min()),fixed_upper_bound_min=float(fixed.probability_start_upper.min()),fixed_upper_bound_max=float(fixed.probability_start_upper.max()),
      checks={k:bool(v) for k,v in checks.items()},passed=all(checks.values()),local_truth_events=0,empirical_coverage=None)
    dump(N/'summary.json',summary);dump(N/'aggregation_validation.json',dict(checks=summary['checks'],passed=summary['passed']));assert summary['passed'],summary
    print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
