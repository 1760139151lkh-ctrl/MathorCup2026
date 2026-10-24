#!/usr/bin/env python3
"""Publish a new event/availability version without changing the frozen v1."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    output=R/'exports/event_bundle_v2_external.json'
    if output.exists():raise SystemExit('v2 published; preserve bytes and publish another version for new evidence')
    canonical=R/'inputs/deformation/site_registry.csv';reg=pd.read_csv(canonical)
    expected={'observations.csv':'355cfb1c8f44ef9048be8df4fdaaa5396019e0a4e0260665a1c5bb7acc662c3b',
              'site_registry.csv':'3414206069197b945d8286d404ff98d17988b00fb16945cef11966d346c80303'}
    for n,h in expected.items():assert sha(R/'inputs/deformation'/n)==h
    supplementary=R/'inputs/survival/stampa_site_registry.csv'
    if supplementary.exists():reg=pd.concat([reg,pd.read_csv(supplementary)],ignore_index=True)
    groups=pd.read_csv(R/'exports/event_v1/event_group_registry.csv');labels=pd.read_csv(R/'exports/event_v1/label_mapping.csv');newgroups=[];newlabels=[]
    for group,rows in reg.groupby('event_group',sort=True):
        r=rows.iloc[0];eligible=bool(str(r.get('primary_evaluation_eligible',True)).lower()=='true')
        event=bool(str(r.event_observed).lower()=='true');risk=str(r.get('risk_status','unspecified'))
        newgroups.append(dict(event_id='external:'+str(group),independent_event_group='external:'+str(group),physical_phase='published_terminal_or_main_collapse_external_target',
           time_utc=r.get('failure_time_utc'),time_uncertainty=json.dumps({'lower_relative_hours':r.get('failure_lower_hours'),'upper_relative_hours':r.get('failure_upper_hours'),'clock_alignment':r.get('clock_alignment'),'physical_onset_bias':None}),
           space_object='external_monitored_sensors; not local_source_geometry',variable_semantics='source-native deformation units; relative hours, sensor paths in canonical tables',
           available_time=None,forecast_reference_time=None,issue_time=None,valid_time=None,data_role='external_transfer',evidence_status=risk,
           input_version=json.dumps({'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'}),
           evaluation_stratum='external_transfer',approved_training_label=False,approved_independent_validation_label=False,
           external_benchmark_eligible=eligible,event_observed=event,sensor_count=len(rows),
           notes='Externally benchmarked terminal-collapse target; does not validate local first mechanical initiation'))
        for s in rows.itertuples():
            newlabels.append(dict(event_id='external:'+str(group),evidence_id='canonical:'+s.site_id,independent_event_group='external:'+str(group),physical_phase='terminal_collapse_or_monitored_right_censor',
               time_utc=getattr(s,'failure_time_utc',None),time_uncertainty=json.dumps({'failure_lower_relative_hours':getattr(s,'failure_lower_hours',None),'failure_upper_relative_hours':getattr(s,'failure_upper_hours',None),'unknown_mechanical_proxy_bias':True}),
               space_object=s.site_id,variable_semantics=getattr(s,'unit',None),available_time=None,data_role='external_transfer',
               evidence_status=getattr(s,'label_semantics','source_censoring_registry'),source_url=getattr(s,'label_source',None),
               approved_training_label=False,approved_independent_validation_label=False,external_benchmark_eligible=eligible))
    g=pd.concat([groups,pd.DataFrame(newgroups)],ignore_index=True);l=pd.concat([labels,pd.DataFrame(newlabels)],ignore_index=True)
    f=pd.read_csv(R/'inputs/weather/gfs_hourly_summary.csv').drop_duplicates(['forecast_reference_time','valid_time'])
    a=pd.read_csv(R/'exports/event_v1/forecast_availability.csv');new=[]
    for s in f.itertuples():new.append(dict(event_id='B20260826_Chhochen',physical_phase='environmental_forecast_background',forecast_reference_time=s.forecast_reference_time,valid_time=s.valid_time,
           available_time=None,issue_time=None,time_utc=None,time_uncertainty=None,space_object='85–86E,28–29N model AOI; 0.25 degree',
           variable_semantics='2m temperature K; APCP kg/m2 native0-lead accumulation differenced into1h intervals',forecast_input_mode='historically_available',
           assumed_latency_hours=None,assumption_is_historical_fact=False,evidence_status='unknown_historical_first_availability',data_role='scenario',historically_eligible=False,
           object_url='https://noaa-gfs-bdp-pds.s3.amazonaws.com/'+s.source_product_version))
    a=pd.concat([a,pd.DataFrame(new)],ignore_index=True)
    export=R/'exports/event_v2';export.mkdir(parents=True,exist_ok=True)
    for n,df in [('event_group_registry.csv',g),('label_mapping.csv',l),('forecast_availability.csv',a)]:
        df.to_csv(R/'results'/n,index=False);df.to_csv(export/n,index=False)
    paths=[*sorted(export.glob('*.csv')),R/'inputs/deformation/observations.csv',canonical,R/'inputs/deformation/metadata_audit.json',R/'inputs/deformation/publisher_checksum_verification.json']
    if supplementary.exists():paths.extend([supplementary,R/'inputs/survival/stampa_observations.csv'])
    v1=R/'exports/event_bundle.json';assert sha(v1)=='075b149214b5c9a8827af45af221ee6ee6b6428090e6d9337afb1943698d2faf'
    b=dict(bundle_version='q3-r3-event-v2-external',producer_question='q3',created_at_utc=datetime.now(timezone.utc).isoformat(),
       input_version={'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'},
       evaluation_stratum='external_transfer',files=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p),role=p.stem) for p in paths],
       local_accepted_training_events=0,local_accepted_validation_events=0,external_physical_groups=len(newgroups),
       limitations=['External terminal-collapse labels do not establish local first-mechanical-initiation truth or transportability',
          'Veslemannen clock-alignment-sensitive record excluded from main external evaluation; Vaiont conflicting label excluded from canonical',
          'Multiple sensors stay within their physical event/site group; monitored stable exposure is not general-population sampling',
          'Source-native naive clocks stay relative; label resolution intervals are not measured physical-onset error distributions',
          'All historical GFS available_time remain unknown; assumptions are separate replay modes',
          'Original event v1 bundle and three frozen files preserved byte-for-byte'])
    output.write_text(json.dumps(b,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'bundle':str(output.relative_to(ROOT)),'sha256':sha(output),'external_groups':len(newgroups),'files':len(paths)}))

if __name__=='__main__':main()
