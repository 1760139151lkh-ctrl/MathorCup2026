#!/usr/bin/env python3
"""Replay the weather information set, separating assumptions and ideal inputs."""
from datetime import datetime,timezone
import hashlib,json,warnings
from pathlib import Path
import numpy as np
import pandas as pd
# pandas 2.3 / NumPy 2.5 internal date_range arithmetic emits this warning even
# for explicitly typed hourly Timedelta inputs; retain locked project packages.
warnings.filterwarnings('ignore',message="The 'generic' unit for NumPy timedelta is deprecated",category=DeprecationWarning)
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]

def main():
    fpath=R/'inputs/weather/gfs_hourly_summary.csv';lpath=R/'inputs/weather/local_weather_case.csv'
    f=pd.read_csv(fpath);local=pd.read_csv(lpath)
    for name in ['forecast_reference_time','valid_time']:f[name]=pd.to_datetime(f[name],utc=True)
    local.time_utc=pd.to_datetime(local.time_utc,utc=True);local=local.set_index('time_utc')
    rows=[];series=[]
    issues=pd.date_range('2026-08-23T00:00Z','2026-08-26T02:00Z',freq='h')
    for space,g in f.groupby('space_object',sort=True):
      refs=sorted(g.forecast_reference_time.unique())
      for issue in issues:
       for mode,latency in [('historically_available',None)]+[('assumed_latency',x) for x in [0,3,6,9]]:
        eligible=[] if latency is None else [r for r in refs if r+pd.Timedelta(hours=latency)<=issue]
        chosen=max(eligible) if eligible else None
        q=g[g.forecast_reference_time.eq(chosen)].set_index('valid_time') if chosen is not None else pd.DataFrame()
        for H in [24,48,72]:
          expected=pd.date_range(issue+pd.Timedelta(hours=1),periods=H,freq='h')
          s=q.reindex(expected) if len(q) else pd.DataFrame(index=expected,columns=['temperature_2m_C','precipitation_increment_mm','precipitation_interval_start','precipitation_interval_end'])
          t=pd.to_numeric(s.temperature_2m_C,errors='coerce');p=pd.to_numeric(s.precipitation_increment_mm,errors='coerce')
          interval_start=pd.to_datetime(s.precipitation_interval_start,utc=True,errors='coerce')
          interval_end=pd.to_datetime(s.precipitation_interval_end,utc=True,errors='coerce')
          verified=(interval_end.eq(s.index)&interval_start.eq(s.index-pd.Timedelta(hours=1)))
          p=p.where(verified)
          row=dict(issue_time=issue.isoformat(),horizon_hours=H,space_object=space,forecast_input_mode=mode,assumed_latency_hours=latency,
             selected_forecast_reference_time=chosen.isoformat() if chosen is not None else None,available_time=None,
             assumed_available_time=(chosen+pd.Timedelta(hours=latency)).isoformat() if chosen is not None else None,
             historically_certified=False,gate_status='unknown_no_historical_availability' if latency is None else ('eligible_under_explicit_latency_assumption' if chosen is not None else 'no_eligible_acquired_initialization'),
             temperature_hours=int(t.notna().sum()),precipitation_hours=int(p.notna().sum()),expected_hours=H,
             temperature_mean_C=float(t.mean()) if t.notna().all() else None,positive_degree_hours=float(t.clip(lower=0).sum()) if t.notna().all() else None,
             precipitation_sum_mm=float(p.sum()) if p.notna().all() else None,
             evaluation_stratum='conditional_scenario',data_role='scenario',future_weather_role='actual_archived_forecast_fields_with_assumed_release_not_perfect_weather')
          rows.append(row)
          if H==72 and chosen is not None:
            for vt,rr in s.iterrows():
              series.append(dict(issue_time=issue.isoformat(),valid_time=vt.isoformat(),space_object=space,forecast_reference_time=chosen.isoformat(),
                    assumed_latency_hours=latency,forecast_input_mode=mode,temperature_2m_C=t.loc[vt],precipitation_increment_mm=p.loc[vt],
                    precipitation_interval_start=rr.get('precipitation_interval_start'),precipitation_interval_end=rr.get('precipitation_interval_end'),available_time=None,
                    assumed_available_time=(chosen+pd.Timedelta(hours=latency)).isoformat(),data_role='scenario'))
    for issue in issues:
      for H in [24,48,72]:
        ix=pd.date_range(issue+pd.Timedelta(hours=1),periods=H,freq='h');s=local.reindex(ix);t=s.temperature_2m_C_qc0
        rows.append(dict(issue_time=issue.isoformat(),horizon_hours=H,space_object='Gyirong_regional_background',forecast_input_mode='ideal_weather',
            assumed_latency_hours=None,selected_forecast_reference_time=None,available_time=None,assumed_available_time=None,historically_certified=False,
            gate_status='retrospective_future_observation_oracle_not_operational',temperature_hours=int(t.notna().sum()),precipitation_hours=0,expected_hours=H,
            temperature_mean_C=float(t.mean()) if t.notna().all() else None,positive_degree_hours=float(t.clip(lower=0).sum()) if t.notna().all() else None,
            precipitation_sum_mm=None,evaluation_stratum='conditional_scenario',data_role='scenario',future_weather_role='future_observed_temperature_only; precip_interval_and_qc_unverified'))
    out=R/'results/weather_replay';out.mkdir(parents=True,exist_ok=True)
    result=pd.DataFrame(rows);result.to_csv(out/'issue_information_sets.csv',index=False)
    pd.DataFrame(series).to_csv(out/'forecast_replay_hourly.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    summary=result.groupby(['forecast_input_mode','assumed_latency_hours','space_object','horizon_hours'],dropna=False).agg(issues=('issue_time','size'),
      temperature_complete=('temperature_mean_C','count'),precip_complete=('precipitation_sum_mm','count'),historically_certified=('historically_certified','sum')).reset_index()
    summary.to_csv(out/'coverage.csv',index=False)
    checks={'historical_unknown_never_certified':not result.historically_certified.any(),
      'unknown_historical_gate_has_no_features':result.loc[result.forecast_input_mode.eq('historically_available'),'temperature_mean_C'].isna().all(),
      'no_partial_precip_sum':not ((result.precipitation_hours<result.expected_hours)&result.precipitation_sum_mm.notna()).any(),
      'assumed_availability_not_future':all(pd.Timestamp(x.assumed_available_time)<=pd.Timestamp(x.issue_time) for _,x in result.dropna(subset=['assumed_available_time']).iterrows())}
    report=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),issues=len(issues),rows=len(result),checks={k:bool(v) for k,v in checks.items()},
       inputs=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [fpath,lpath]],
       interpretation='Information-set and weather-feature replay; no local trigger validation; ideal future temperature remains an oracle')
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');assert all(checks.values()),checks
    print(json.dumps(report))

if __name__=='__main__':main()
