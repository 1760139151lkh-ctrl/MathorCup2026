#!/usr/bin/env python3
"""Recompute B at C's exactly matched, predeclared sensor/issue anchors."""
from datetime import datetime,timezone
import argparse
import hashlib,json,math,os
from pathlib import Path
from types import SimpleNamespace
os.environ.setdefault('MPL_IGNORE_SYSTEM_FONTS','1')
os.environ.setdefault('MPLCONFIGDIR','<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q3/plot_runtime')
import numpy as np
import pandas as pd
import engine_b as B
R=Path(__file__).resolve().parents[1]

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--c-predictions',default='results/engine_c/anchor_predictions.csv');cli.add_argument('--outdir',default='results/common_anchors');args=cli.parse_args()
    protocol=R/'COMMON_ANCHOR_PROTOCOL.md';assert protocol.exists()
    anchor_path=R/args.c_predictions;c=pd.read_csv(anchor_path)
    c=c[c.horizon_role.eq('common_hours') & c.horizon_hours.isin([24,48,72])].copy()
    if c.duplicated(['event_group','site_id','model_id','horizon_hours']).any():raise ValueError('Nonunique C anchor')
    obs=pd.read_csv(R/'inputs/deformation/observations.csv');reg=pd.read_csv(R/'inputs/deformation/site_registry.csv')
    so=R/'inputs/survival/stampa_observations.csv';sr=R/'inputs/survival/stampa_site_registry.csv'
    obs=pd.concat([obs,pd.read_csv(so)],ignore_index=True);reg=pd.concat([reg,pd.read_csv(sr)],ignore_index=True)
    # A case can have no issuable anchor in the selected observation window.
    # Retain it in the all-case opportunity denominator without inventing a
    # prediction or assuming the file start was the deployment date.
    c['status']='ok';c['anchor_publication_status']='issuable_in_selected_record';missing=[]
    for group in sorted(c.event_group.unique()):
      base=c[c.event_group.eq(group)].iloc[0];source=reg[reg.site_id.eq(base.site_id)].iloc[0]
      for model in c.model_id.unique():
       for H in [24,48,72]:
        if ((c.event_group==group)&(c.model_id==model)&(c.horizon_hours==H)).any():continue
        r=base.to_dict();end=float(source.followup_end_hours);issue=end-H
        event=str(source.event_observed).lower()=='true';lower=float(source.failure_lower_hours) if event else math.inf;upper=float(source.failure_upper_hours) if event else math.inf
        r.update(model_id=model,horizon_hours=H,issue_relative_hours=issue,information_cutoff_relative_hours=np.nan,observation_age_hours=np.nan,
          probability_start_within_horizon=np.nan,probability_no_start_within_horizon=np.nan,conditional_lower95_offset_hours=np.nan,
          conditional_median_offset_hours=np.nan,conditional_upper95_offset_hours=np.nan,hazard_per_hour=np.nan,
          failure_lower_offset_hours=lower-issue if event else np.nan,failure_upper_offset_hours=upper-issue if event else np.nan,
          outcome_known=True,event_within_horizon=int(event and upper<=issue+H),status='no_issuable_anchor_in_selected_record',anchor_publication_status='no_issuable_anchor_in_selected_record')
        missing.append(r)
    if missing:c=pd.concat([c,pd.DataFrame(missing)],ignore_index=True)
    anchors=c.drop_duplicates(['event_group','site_id','horizon_hours']);rows=[]
    for x in anchors.itertuples():
        source=reg[reg.site_id.eq(x.site_id)].iloc[0];s=obs[obs.site_id.eq(x.site_id)].sort_values('time_relative_hours')
        t=s.time_relative_hours.to_numpy(float);d=s.displacement.to_numpy(float)
        raw=pd.to_numeric(s.get('raw_velocity_per_day',pd.Series(np.nan,index=s.index)),errors='coerce').to_numpy(float)
        v=B.causal_vel(t,d,raw);r=source.to_dict()
        if str(r.get('event_observed')).lower()!='true':r['failure_lower_hours']=math.inf;r['failure_upper_hours']=math.inf;r['label_kind']='verified_right_censor_within_monitored_record'
        r['primary_evaluation_eligible']=True;r=SimpleNamespace(**r)
        for model in ['B_IV','B_SS']:
            pred=next(y for y in B.one_prediction(t,v,float(x.issue_relative_hours),model,x.site_id,r,'C_matched_anchor',16,.01) if y['horizon_hours']==x.horizon_hours)
            issue=float(x.issue_relative_hours);lo=pred['conditional_lower_hours']-issue;hi=pred['conditional_upper_hours']-issue
            rows.append(dict(engine='B',model_id=model,event_group=x.event_group,site_id=x.site_id,issue_relative_hours=issue,horizon_hours=x.horizon_hours,
                information_cutoff_relative_hours=pred['last_input_relative_hours'],probability_start_within_horizon=pred['probability_start_within_horizon'],
                probability_no_start_within_horizon=pred['probability_no_start_within_horizon'],conditional_lower_offset_hours=lo,conditional_upper_offset_hours=hi,
                conditional_median_offset_hours=pred['conditional_median_hours']-issue,status=pred['status'],outcome_known=x.outcome_known,event_within_horizon=x.event_within_horizon,
                failure_lower_offset_hours=x.failure_lower_offset_hours,failure_upper_offset_hours=x.failure_upper_offset_hours,right_censored=x.right_censored,
                conditional_interval_level=.95,interval_semantics='model_internal_given_failure_within_H; same_C_anchor',anchor_publication_status=x.anchor_publication_status,evaluation_stratum='external_transfer'))
    for x in c.itertuples():rows.append(dict(engine='C',model_id=x.model_id,event_group=x.event_group,site_id=x.site_id,issue_relative_hours=x.issue_relative_hours,horizon_hours=x.horizon_hours,
                information_cutoff_relative_hours=x.information_cutoff_relative_hours,probability_start_within_horizon=x.probability_start_within_horizon,
                probability_no_start_within_horizon=x.probability_no_start_within_horizon,conditional_lower_offset_hours=x.conditional_lower95_offset_hours,
                conditional_upper_offset_hours=x.conditional_upper95_offset_hours,conditional_median_offset_hours=x.conditional_median_offset_hours,status=x.status,anchor_publication_status=x.anchor_publication_status,
                outcome_known=x.outcome_known,event_within_horizon=x.event_within_horizon,failure_lower_offset_hours=x.failure_lower_offset_hours,
                failure_upper_offset_hours=x.failure_upper_offset_hours,right_censored=x.right_censored,conditional_interval_level=.95,interval_semantics=x.interval_semantics,evaluation_stratum='external_transfer'))
    f=pd.DataFrame(rows);known=f.outcome_known.astype(str).str.lower().eq('true');y=pd.to_numeric(f.event_within_horizon,errors='coerce');p=f.probability_start_within_horizon
    f['brier_known']=(p-y).pow(2).where(known);f['brier_lower']=(p-y).pow(2).where(known,np.minimum(p.pow(2),(1-p).pow(2)))
    f['brier_upper']=(p-y).pow(2).where(known,np.maximum(p.pow(2),(1-p).pow(2)))
    positive=known & y.eq(1);lo=f.conditional_lower_offset_hours;hi=f.conditional_upper_offset_hours
    f['interval_issued']=lo.notna() & hi.notna();f['coverage_full_label']=((lo<=f.failure_lower_offset_hours)&(hi>=f.failure_upper_offset_hours)).astype(float).where(positive)
    f['coverage_intersects_label']=((lo<=f.failure_upper_offset_hours)&(hi>=f.failure_lower_offset_hours)).astype(float).where(positive)
    f['conditional_width_hours']=hi-lo;f['alert_at_fixed_half']=p.ge(.5).where(p.notna())
    summary=[]
    for (model,H),g in f.groupby(['model_id','horizon_hours'],sort=True):
        k=g.outcome_known.astype(str).str.lower().eq('true');yy=pd.to_numeric(g.event_within_horizon,errors='coerce');pos=k&yy.eq(1);neg=k&yy.eq(0);pp=g.probability_start_within_horizon
        summary.append(dict(model_id=model,horizon_hours=H,physical_groups=g.event_group.nunique(),known_outcome_groups=int(k.sum()),unknown_outcome_groups=int((~k).sum()),
           probability_scored_groups=int((k&pp.notna()).sum()),abstain_groups=int(pp.isna().sum()),known_event_groups=int(pos.sum()),known_no_event_groups=int(neg.sum()),
           issuable_anchor_groups=int(g.anchor_publication_status.eq('issuable_in_selected_record').sum()),no_issuable_anchor_groups=int(g.anchor_publication_status.ne('issuable_in_selected_record').sum()),
           brier_known_group_equal=g.brier_known.mean(),probability_available_groups=int(pp.notna().sum()),brier_bound_denominator=int(g.brier_lower.notna().sum()),
           brier_lower_mean_conditional_on_probability_issued=g.brier_lower.mean(),brier_upper_mean_conditional_on_probability_issued=g.brier_upper.mean(),
           brier_bound_scope='issued_probabilities_only; unknown_labels_bounded; abstentions_unscored',
           coverage_full_including_no_interval=g.coverage_full_label.mean(),coverage_intersects_including_no_interval=g.coverage_intersects_label.mean(),
           issued_interval_event_groups=int((pos&g.interval_issued).sum()),conditional_interval_width_hours=g.loc[g.interval_issued,'conditional_width_hours'].mean(),
           coverage_full_conditional_on_interval=g.loc[pos&g.interval_issued,'coverage_full_label'].mean(),coverage_intersects_conditional_on_interval=g.loc[pos&g.interval_issued,'coverage_intersects_label'].mean(),
           true_alert_groups=int((pos&pp.ge(.5)).sum()),missed_alert_groups=int((pos&pp.lt(.5)).sum()),event_abstain_groups=int((pos&pp.isna()).sum()),
           false_alert_groups=int((neg&pp.ge(.5)).sum()),noevent_abstain_groups=int((neg&pp.isna()).sum()),evaluation_stratum='external_transfer',
           protocol='exact_same_C_anchor_and_lexical_sensor; retrospective_case_conditioned'))
    out=(R/args.outdir).resolve();assert out.is_relative_to(R/'results');out.mkdir(parents=True,exist_ok=True);f.to_csv(out/'predictions.csv',index=False);pd.DataFrame(summary).to_csv(out/'evaluation.csv',index=False)
    pairwise=[]
    from itertools import combinations
    for H,part in f.groupby('horizon_hours'):
      pivot=part.pivot(index='event_group',columns='model_id',values='probability_start_within_horizon')
      truth=part.drop_duplicates('event_group').set_index('event_group');yy=pd.to_numeric(truth.event_within_horizon,errors='coerce');kk=truth.outcome_known.astype(str).str.lower().eq('true')
      for one,two in combinations(sorted(pivot.columns),2):
        use=kk&pivot[one].notna()&pivot[two].notna();n=int(use.sum())
        pairwise.append(dict(model_one=one,model_two=two,horizon_hours=H,total_physical_cases=len(pivot),same_known_probability_groups=n,
            positive_groups=int((yy[use]==1).sum()),negative_groups=int((yy[use]==0).sum()),
            brier_one=float(((pivot.loc[use,one]-yy[use])**2).mean()) if n else None,brier_two=float(((pivot.loc[use,two]-yy[use])**2).mean()) if n else None,
            interpretation='same valid opportunity subset; abstentions and nonissuable case remain in separate total-case denominators'))
    pd.DataFrame(pairwise).to_csv(out/'paired_valid_scores.csv',index=False)
    checks=dict(same_anchors=f.groupby(['model_id','horizon_hours']).size().nunique()==1,
                no_future_input=bool(((f.information_cutoff_relative_hours<=f.issue_relative_hours+1e-7)|f.information_cutoff_relative_hours.isna()).all()),
                probability_mass_normalized=bool(np.allclose((f.probability_start_within_horizon+f.probability_no_start_within_horizon).dropna(),1)),
                unique_model_group_horizon=not f.duplicated(['model_id','event_group','horizon_hours']).any())
    report=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),C_input_path=str(anchor_path.relative_to(R)),C_input_sha256=hashlib.sha256(anchor_path.read_bytes()).hexdigest(),B_code_sha256=hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest(),rows=len(f),physical_groups=f.event_group.nunique(),
                checks={k:bool(v) for k,v in checks.items()},passed=all(checks.values()),interpretation='Exactly matched external terminal-collapse anchors; no local first-motion coverage')
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');assert report['passed'],report;print(json.dumps(report))

if __name__=='__main__':main()
