#!/usr/bin/env python3
"""Analytic first-passage benchmark, never counted as observed events."""
from datetime import datetime,timezone
import json
import numpy as np
import pandas as pd
from engine_a import R,first_passage,probability_at_issue

def frame(name,margin,times=None):
    n=len(margin);times=np.arange(n) if times is None else np.array(times)
    return pd.DataFrame(dict(scenario_id=name,model_id='analytic_benchmark',mechanism_id='linear_margin',geometry_version='not_applicable',parameter_version='known_equation',
         forecast_input_mode='ideal_weather',time_utc=pd.Timestamp('2026-08-23T00:00Z')+pd.to_timedelta(times,unit='h'),failure_margin=margin))

def main():
    checks={};linear=first_passage(frame('linear',2.5-np.arange(101)))
    checks['linear_root_2_5h']=linear['crossing_point_utc']=='2026-08-23T02:30:00+00:00'
    left=first_passage(frame('left',[-1,-2,-3]));checks['left_censored_not_exact']=left['status']=='left_censored_already_unstable' and left['crossing_point_utc'] is None
    missing=first_passage(frame('missing',[2.5,1.5,np.nan,-.5]));checks['missing_gap_not_interpolated']=missing['status']=='interval_censored_crossing_or_prior_gap'
    absent=first_passage(frame('missing_whole_hour',[1,1,1],[0,1,3]));checks['missing_whole_time_row_not_fake_no_start']=absent['status']=='unknown_missing_trajectory' and absent['time_gap_count']==1
    stable=first_passage(frame('stable',np.ones(101)));checks['never_cross_retained']=stable['status']=='no_cross_observed_complete'
    early_left=first_passage(frame('early_left',[np.nan,-1,-2]));r=probability_at_issue(pd.DataFrame([early_left]),pd.Timestamp('2026-08-23T00:00Z'),24,'uniform_scenario')
    checks['pre_left_censor_detection_remains_unknown']=r['unknown_at_risk_prior_mass']==1 and r['probability_start_within_horizon'] is None
    leading=first_passage(frame('leading_gap',[np.nan,2,-1]));checks['leading_gap_not_shrunk_to_first_positive']=leading['crossing_lower_utc'] is None and leading['crossing_point_utc'] is None
    ensemble=pd.DataFrame([linear,stable]);p=probability_at_issue(ensemble,pd.Timestamp('2026-08-23T00:00Z'),24,'uniform_scenario')
    checks['no_start_half_mass_retained']=p['probability_start_within_horizon']==.5 and p['probability_no_start_within_horizon']==.5
    rows=[]
    c=pd.DataFrame([first_passage(frame('root20',20-np.arange(101))),first_passage(frame('root40',40-np.arange(101))),stable])
    probabilities=[]
    for H in [24,48,72]:
        r=probability_at_issue(c,pd.Timestamp('2026-08-23T00:00Z'),H,'uniform_scenario');r['horizon_hours']=H;rows.append(r);probabilities.append(r['probability_start_within_horizon'])
    checks['horizon_monotone_and_analytic']=np.allclose(probabilities,[1/3,2/3,2/3])
    limited=first_passage(frame('right_censor',[1,1,1]));r=probability_at_issue(pd.DataFrame([limited]),pd.Timestamp('2026-08-23T00:00Z'),24,'uniform_scenario')
    checks['short_followup_not_fake_no_start']=r['probability_start_within_horizon'] is None and r['probability_start_upper']==1
    out=R/'results/numerical_benchmark';out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'analytic_probabilities.csv',index=False)
    (out/'checks.json').write_text(json.dumps(dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),evaluation_stratum='numerical_benchmark',independent_observed_events=0,
        passed=all(bool(v) for v in checks.values()),checks={k:bool(v) for k,v in checks.items()}),indent=2)+'\n')
    assert all(checks.values()),checks
    print(json.dumps({k:bool(v) for k,v in checks.items()}))

if __name__=='__main__':main()
