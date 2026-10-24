#!/usr/bin/env python3
"""Explicit mixture mechanism masses and conservative unknown transfers."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from applicability_sensitivity import R,O,A,PRIORS,POLICIES,summarize

def main():
    rows=[];transfers=[]
    for batch in pq.ParquetFile(A/'parameter_first_passages.parquet').iter_batches(batch_size=2048):
        f=batch.to_pandas();domain=f.strength_domain_fraction_observed.to_numpy(float);valid=domain>=1-1e-12
        risk=f.known_at_risk_under_conditional_history.to_numpy(bool);point=f.crossing_point_hours_after_issue.to_numpy(float)
        length=f.followup_hours.to_numpy(int);mech=f.mechanism_id.to_numpy();margin=f.initial_margin_at_issue.to_numpy(float)
        common=f.iloc[0][['issue_time','forecast_input_mode','space_object','assumed_latency_hours','forcing_status','followup_hours']].to_dict()
        for prior in PRIORS:
            base=np.exp(-np.clip(margin,0,10)) if prior==PRIORS[2] else np.ones(len(f))
            if prior==PRIORS[1]:base=1/f.groupby('mechanism_id').mechanism_id.transform('size').to_numpy(float)
            base=base/base.sum()
            for policy in POLICIES:
                factor=np.ones(len(f)) if policy in [POLICIES[0],POLICIES[3]] else valid.astype(float) if policy==POLICIES[1] else domain
                raw=base*factor;retained=raw.sum();w=raw/retained if retained else np.zeros(len(f))
                possible=(risk&valid)|~valid if policy==POLICIES[3] else risk
                for m in ['S','S_T','S_H','S_T_H']:
                    use=mech==m
                    rows.append(dict(common,probability_prior=prior,applicability_policy=policy,mechanism_id=m,
                      original_mixture_mechanism_mass=float(base[use].sum()),new_mixture_mechanism_mass=float(w[use].sum()),
                      original_at_risk_mechanism_mass=float(base[use&risk].sum()),new_possible_at_risk_mechanism_mass=float(w[use&possible].sum()),
                      original_domain_outside_mass=float(base[use&~valid].sum()),original_full_group_prior_mass_retained=float(retained)))
            for H in [24,48,72]:
                event=risk&np.isfinite(point)&(point<=H);no=risk&((np.isfinite(point)&(point>H))|(~np.isfinite(point)&(length>=H)))
                unknown=risk&~(event|no)
                transfers.append(dict(common,horizon_hours=H,probability_prior=prior,
                   original_event_mass=float(base[event].sum()),original_no_start_mass=float(base[no].sum()),
                   original_future_unknown_mass=float(base[unknown].sum()),original_already_started_mass=float(base[~risk].sum()),
                   event_mass_transferred_to_unknown=float(base[event&~valid].sum()),
                   no_start_mass_transferred_to_unknown=float(base[no&~valid].sum()),
                   already_started_mass_transferred_to_state_unknown=float(base[~risk&~valid].sum()),
                   preexisting_future_unknown_outside_domain_mass=float(base[unknown&~valid].sum()),
                   conservative_unknown_mass=float(base[unknown|~valid].sum()),
                   conservative_known_event_mass=float(base[event&valid].sum()),
                   conservative_known_no_start_mass=float(base[no&valid].sum()),conservative_known_past_mass=float(base[~risk&valid].sum())))
    mass=pd.DataFrame(rows);mass.to_csv(O/'mixture_mechanism_masses.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    trans=pd.DataFrame(transfers);trans.to_csv(O/'conservative_mass_transfers.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pred=pd.read_csv(O/'predictions.csv.gz');cons=pred[(pred.applicability_policy==POLICIES[3])&(pred.model_id=='mechanism_policy_mixture')]
    keys=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','horizon_hours','probability_prior']
    paired=cons.merge(trans,on=keys,validate='one_to_one')
    checks={'all_mixture_mechanism_masses_close_to_one_or_empty':bool(mass.groupby(keys[:4]+['probability_prior','applicability_policy'],dropna=False).new_mixture_mechanism_mass.sum().apply(lambda x:abs(x-1)<1e-12 or x==0).all()),
      'conservative_four_way_partition_preserved':bool(np.allclose(trans[['conservative_unknown_mass','conservative_known_event_mass','conservative_known_no_start_mass','conservative_known_past_mass']].sum(axis=1),1)),
      'conservative_unknown_mass_matches_main_predictions':bool(np.allclose(paired.unresolved_future_prior_mass,paired.conservative_unknown_mass)),
      'all_6750_mixture_conservative_rows_matched':len(paired)==6750}
    report={'checks':checks,'passed':all(checks.values()),'mixture_mechanism_rows':len(mass),'mass_transfer_rows':len(trans),'physics_rerun':False}
    (O/'mass_audit_validation.json').write_text(json.dumps(report,indent=2)+'\n');assert report['passed'],report;print(json.dumps(report))

if __name__=='__main__':main()
