#!/usr/bin/env python3
"""First-passage adapter for hash-delivered Q2 scenario state ensembles.

No supplied trajectory is re-labelled as a historically available forecast.
Range envelopes and explicitly assumed discrete-prior probabilities are separate.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore',message="The 'generic' unit for NumPy timedelta is deprecated",category=DeprecationWarning)

R=Path(__file__).resolve().parents[1]
ROOT=R.parents[3]
OUT=R/'results/engine_a'
BASE='904d7257b899b9f71d1ac9e0eab7479e459eab52'
FROZEN='fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'
REQUIRED={'scenario_id','model_id','mechanism_id','time_utc','elapsed_hours','failure_margin','margin_definition','data_role','forecast_input_mode'}
KEYS=['scenario_id','model_id','mechanism_id','geometry_version','parameter_version','forecast_input_mode']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jwrite(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def first_passage(frame,max_gap_hours=1.5):
    f=frame.sort_values('time_utc');t=pd.to_datetime(f.time_utc,utc=True)
    if t.duplicated().any():raise ValueError('Duplicate time within scenario/model/mechanism/version')
    m=pd.to_numeric(f.failure_margin,errors='coerce').to_numpy();finite=np.isfinite(m)
    gaps=t.diff().dt.total_seconds().div(3600).gt(max_gap_hours).to_numpy()
    rec={k:f.iloc[0][k] for k in KEYS}
    rec.update(start_utc=t.iloc[0].isoformat(),end_utc=t.iloc[-1].isoformat(),status='missing',crossing_lower_utc=None,crossing_upper_utc=None,
               crossing_point_utc=None,missing_state_count=int((~finite).sum()),time_gap_count=int(gaps.sum()),sample_count=len(f),initial_margin=float(m[0]) if finite[0] else None)
    if not finite.any():return rec
    first=int(np.flatnonzero(finite)[0]);hit=np.flatnonzero(finite & (m<=0))
    if len(hit):
        b=int(hit[0]);prior=np.flatnonzero(finite[:b] & (m[:b]>0))
        if b==first or not len(prior):
            rec.update(status='left_censored_already_unstable',crossing_upper_utc=t.iloc[b].isoformat());return rec
        a=int(prior[-1]);gap=(t.iloc[b]-t.iloc[a]).total_seconds()/3600
        unresolved=np.flatnonzero(gaps[:b+1] | ~finite[:b+1])
        lower=a
        if len(unresolved):
            before=np.flatnonzero(finite[:unresolved[0]] & (m[:unresolved[0]]>0))
            lower=int(before[-1]) if len(before) else first
        rec.update(crossing_lower_utc=t.iloc[lower].isoformat() if finite[0] else None,crossing_upper_utc=t.iloc[b].isoformat())
        if b==a+1 and gap<=max_gap_hours and not len(unresolved):
            point=t.iloc[a]+(t.iloc[b]-t.iloc[a])*(m[a]/(m[a]-m[b]))
            rec.update(status='point_crossing_linear_between_samples',crossing_point_utc=point.isoformat())
        else:rec['status']='interval_censored_crossing_or_prior_gap'
    else:rec['status']='no_cross_observed_complete' if finite.all() and not gaps.any() else 'unknown_missing_trajectory'
    return rec

_CLOCK_CACHE = {}

def probability_at_issue(crossings,issue,H,scheme):
    c=crossings
    if id(c) not in _CLOCK_CACHE:
        def clock(name):
            parsed=pd.to_datetime(c[name],utc=True,errors='coerce',format='mixed')
            if (c[name].notna() & parsed.isna()).any():raise ValueError('Nonempty trajectory clock could not be parsed')
            return parsed.array.as_unit('ns').asi8
        _CLOCK_CACHE[id(c)]=(c,{k:clock(k) for k in ['start_utc','end_utc','crossing_point_utc','crossing_lower_utc','crossing_upper_utc']})
    z=_CLOCK_CACHE[id(c)][1];nat=np.iinfo(np.int64).min
    start,finish,p,a,b=[z[k] for k in ['start_utc','end_utc','crossing_point_utc','crossing_lower_utc','crossing_upper_utc']]
    vp,va,vb=p!=nat,a!=nat,b!=nat;now=issue.value;end=(issue+pd.Timedelta(hours=H)).value
    status=c.status.to_numpy();left=status=='left_censored_already_unstable'
    if scheme=='uniform_scenario':w=np.ones(len(c))
    elif scheme=='equal_mechanism_then_scenario':w=1/c.groupby('mechanism_id').mechanism_id.transform('size').to_numpy(float)
    elif scheme=='fragile_initial_margin_sensitivity':
        initial=pd.to_numeric(c.initial_margin,errors='coerce').to_numpy(float);w=np.exp(-np.clip(np.nan_to_num(initial,nan=1),0,10))
    else:raise ValueError(scheme)
    w=w/w.sum()
    excluded=(vp&(p<=now))|(vb&(b<=now))
    unknown=(~excluded)&((left&vb&(b>now))|(now<start)|(va&(a<now)&~vp))
    risk=~excluded&~unknown
    point_hit=risk&vp&(p>now)&(p<=end)
    interval=risk&~vp&va&vb
    complete=risk&~vp&~interval&(status=='no_cross_observed_complete')
    other=risk&~vp&~interval&~complete
    lo=point_hit|(interval&(a>=now)&(b<=end))
    hi=point_hit|(interval&(a<end)&(b>now))|(complete&(finish<end))|other
    total=float(w[risk].sum());unknown_mass=float(w[unknown].sum());possible=total+unknown_mass
    lower=float(w[lo].sum()/possible) if possible else None
    upper=float((w[hi].sum()+unknown_mass)/possible) if possible else None
    identified=total>0 and unknown_mass<1e-12 and abs(lower-upper)<1e-12
    prob=lower if identified else None;quant=[None,None,None]
    if identified and prob>0 and point_hit.any() and abs(w[point_hit].sum()-w[lo].sum())<1e-10:
        x=(p[point_hit]-now)/3.6e12;ww=w[point_hit];order=np.argsort(x);x=x[order];cw=np.cumsum(ww[order])/ww.sum()
        quant=[float(x[min(np.searchsorted(cw,q,side='left'),len(x)-1)]) for q in [.025,.5,.975]]
    return dict(probability_start_within_horizon=prob,probability_no_start_within_horizon=1-prob if prob is not None else None,
                probability_start_lower=lower,probability_start_upper=upper,conditional_lower_hours=quant[0],conditional_median_hours=quant[1],conditional_upper_hours=quant[2],
                conditional_interval_level=.95,already_unstable_prior_mass=float(w[excluded].sum()),unknown_at_risk_prior_mass=unknown_mass,
                resolved_at_risk_prior_mass=total,probability_prior=scheme,probability_scope='assumed_discrete_scenario_prior_conditional_on_at_risk_with_unknown_bounds',
                scenario_count=len(c),known_crossing_points_in_horizon=int(point_hit.sum()))


def discover_states():
    found=[]
    for p in sorted((R/'inputs').rglob('*')):
        if p.suffix not in ['.csv','.parquet']:continue
        try:cols=set(pd.read_parquet(p).columns) if p.suffix=='.parquet' else set(pd.read_csv(p,nrows=0).columns)
        except Exception:continue
        if REQUIRED<=cols:found.append(p)
    return found

def full_design_records(bundle=None):
    bundle=Path(bundle) if bundle is not None else R/'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1/bundle.json'
    b=json.loads(bundle.read_text());files={f['role']:ROOT/f['path'] for f in b['files']}
    for f in b['files']:
        p=ROOT/f['path'];assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256']
    contract=json.loads(next(p for k,p in files.items() if k.endswith('mechanism_contract.json')).read_text())
    forcing=pd.read_csv(next(p for k,p in files.items() if 'forcing_hourly' in k));origin=pd.Timestamp(contract['time_origin_utc'])
    end=pd.to_datetime(forcing.time_utc,utc=True).max();records=[]
    for _,s in pd.read_csv(next(p for k,p in files.items() if k.endswith('scenario_outcomes.csv'))).iterrows():
        status={'interval_crossing':'point_crossing_linear_between_samples','never_crossed':'no_cross_observed_complete',
                'left_censored_already_unstable':'left_censored_already_unstable','missing':'unknown_missing_trajectory',
                'missing_before_possible_crossing':'interval_censored_crossing_or_prior_gap'}[s.onset_status]
        row={k:s[k] for k in KEYS};row.update(base_scenario_id=s.get('base_scenario_id',s.scenario_id),mechanism_bundle_version=b['bundle_version'],law_policy=s.get('law_policy'),start_utc=origin.isoformat(),end_utc=end.isoformat(),status=status,
             crossing_lower_utc=(origin+pd.Timedelta(hours=float(s.crossing_lower_hours))).isoformat() if pd.notna(s.crossing_lower_hours) else None,
             crossing_upper_utc=(origin+pd.Timedelta(hours=float(s.crossing_upper_hours))).isoformat() if pd.notna(s.crossing_upper_hours) else None,
             crossing_point_utc=s.crossing_time_utc if pd.notna(s.crossing_time_utc) else None,initial_margin=float(s.initial_margin),
             missing_state_count=None,time_gap_count=None,sample_count=len(forcing),trajectory_detail='full_2048_design_outcome_summary_not_64_representative_prior')
        records.append(row)
    return records,[bundle,*files.values()]

def run(paths,start,end,full_design=False,bundle=None):
    OUT.mkdir(parents=True,exist_ok=True)
    allframes=[];inputs=[]
    for path in paths:
        path=path.resolve()
        if not path.is_relative_to(R/'inputs'):raise ValueError('Use only main-advisor delivered round3 inputs')
        f=pd.read_parquet(path) if path.suffix=='.parquet' else pd.read_csv(path);assert REQUIRED<=set(f.columns)
        for k in ['geometry_version','parameter_version']:
            if k not in f:f[k]='unspecified_in_delivered_source'
        f.time_utc=pd.to_datetime(f.time_utc,utc=True,errors='raise')
        f['input_state_path']=str(path.relative_to(ROOT));allframes.append(f)
        inputs.append(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=sha(path)))
    if not allframes:raise ValueError('No delivered Q2 state table; acquisition and independent B/C continue')
    states=pd.concat(allframes,ignore_index=True)
    # A duplicate scenario/version/time across delivered files must not multiply weight.
    if states.duplicated(KEYS+['time_utc']).any():raise ValueError('Overlapping delivered trajectory keys; select one version')
    records=[first_passage(f) for _,f in states.groupby(KEYS,dropna=False,sort=True)]
    pd.DataFrame(records).to_csv(OUT/'representative_trajectory_audit.csv',index=False)
    if full_design:
        records,full_inputs=full_design_records(bundle)
        inputs.extend(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in full_inputs)
    crossings=pd.DataFrame(records);crossings.to_csv(OUT/'first_passages.csv',index=False)
    rows=[]
    for mode,c in crossings.groupby('forecast_input_mode',dropna=False):
      comparisons=[('mechanism_first_passage_mixture','mixture_over_delivered_mechanisms',c)]
      comparisons.extend((str(k[0]),str(k[1]),f) for k,f in c.groupby(['model_id','mechanism_id'],sort=True,dropna=False))
      for model,mechanism,subset in comparisons:
        for issue in pd.date_range(start,end,freq='h',tz='UTC'):
            for H in [24,48,72]:
                for scheme in ['uniform_scenario','equal_mechanism_then_scenario','fragile_initial_margin_sensitivity']:
                    row=probability_at_issue(subset,issue,H,scheme)
                    row.update(engine='A',model_id=model,mechanism_id=mechanism,scenario_id='delivered_ensemble',
                        geometry_version='see_first_passages',parameter_version=scheme,event_id='B20260826_Chhochen',physical_phase='first_mechanical_initiation_at_source',
                        issue_time=issue.isoformat(),information_cutoff_utc=issue.isoformat(),horizon_hours=H,forecast_input_mode=mode,
                        data_role='scenario',evaluation_stratum='conditional_scenario',truth_time_utc=None,empirical_coverage=None,
                        future_state_role='supplied_scenario_trajectory; not certified as issue-specific available forecast',
                        input_version=json.dumps({'baseline_commit':BASE,'manifest_sha256':FROZEN}),historically_operationally_certified=False)
                    rows.append(row)
    predictions=pd.DataFrame(rows);predictions.to_csv(OUT/'predictions.csv',index=False)
    # Range outputs carry no probability claim; never_cross/left/missing remain counted.
    range_rows=[]
    for keys,c in crossings.groupby(['model_id','mechanism_id','forecast_input_mode'],dropna=False):
        times=pd.to_datetime(c.crossing_point_utc,utc=True,errors='coerce')
        range_rows.append(dict(zip(['model_id','mechanism_id','forecast_input_mode'],keys),scenario_count=len(c),
                              finite_crossing_count=int(times.notna().sum()),earliest_resolved_point_utc=times.min().isoformat() if times.notna().any() else None,
                              latest_resolved_point_utc=times.max().isoformat() if times.notna().any() else None,
                              left_censored_count=int(c.status.eq('left_censored_already_unstable').sum()),never_cross_count=int(c.status.eq('no_cross_observed_complete').sum()),
                              unresolved_count=int(c.status.isin(['missing','unknown_missing_trajectory','interval_censored_crossing_or_prior_gap']).sum()),
                              range_definition='resolved_point_subset_only; not complete censored parameter envelope',role='parameter_range_only_no_probability'))
    pd.DataFrame(range_rows).to_csv(OUT/'scenario_ranges.csv',index=False)
    p=predictions.dropna(subset=['probability_start_within_horizon'])
    checks={'probability_normalized':bool(np.allclose(p.probability_start_within_horizon+p.probability_no_start_within_horizon,1)),
            'nonnegative_no_start_preserved':bool((p.probability_no_start_within_horizon>=0).all()),'no_false_local_coverage':bool(predictions.empirical_coverage.isna().all()),
            'historical_certification_not_inferred':not bool(predictions.historically_operationally_certified.any()),
            'left_censor_is_not_precise_first_sample':bool(crossings.loc[crossings.status.eq('left_censored_already_unstable'),'crossing_point_utc'].isna().all())}
    jwrite(OUT/'run_summary.json',dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),inputs=inputs,scenario_trajectories=len(crossings),
         status_counts=crossings.status.value_counts().to_dict(),prediction_rows=len(predictions),checks=checks,
         limitations=['Future trajectories are conditional scenarios unless delivered per-issue forecast provenance establishes otherwise',
                     'Discrete priors are explicit analyst sensitivity assumptions; parameter range alone does not imply probability',
                     'No accepted local initiation truth; no local empirical coverage or validated onset probability']))
    if not all(checks.values()):raise AssertionError(checks)
    print(json.dumps({'first_passages':len(crossings),'predictions':len(predictions),'checks':checks}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--states',action='append');p.add_argument('--full-design',action='store_true');p.add_argument('--bundle');p.add_argument('--outdir');p.add_argument('--start',default='2026-08-23T00:00:00');p.add_argument('--end',default='2026-08-26T02:00:00');a=p.parse_args()
    if a.outdir:
        OUT=(R/a.outdir).resolve();assert OUT.is_relative_to(R/'results')
    run([ROOT/x for x in a.states] if a.states else discover_states(),a.start,a.end,a.full_design,ROOT/a.bundle if a.bundle else None)
