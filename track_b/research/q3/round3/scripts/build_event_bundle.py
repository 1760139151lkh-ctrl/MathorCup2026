#!/usr/bin/env python3
"""Freeze the first, local-only Q3 R3 exchange; no new scientific adoption."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

R=Path(__file__).resolve().parents[1]
ROOT=R.parents[3]
BASE='904d7257b899b9f71d1ac9e0eab7479e459eab52'
FROZEN='fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'
VERSION={'baseline_commit':BASE,'manifest_sha256':FROZEN}

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8') as s:
        w=csv.DictWriter(s,fieldnames=fields,lineterminator='\n');w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,bool)) or v is None else v for k,v in row.items()})

def main():
    target=R/'exports/event_v1'
    if (R/'exports/event_bundle.json').exists():
        raise SystemExit('v1 already published; preserve it and publish a separately versioned update')
    ledger=json.loads((ROOT/'track_b/data/external/event_remote/event_evidence_ledger.json').read_text())
    later=json.loads((ROOT/'track_b/research/q3/round2/results/us7000tc90_review.json').read_text())
    forecast=json.loads((ROOT/'track_b/research/q3/round2/results/gfs_f009_availability_chain.json').read_text())
    groups=[dict(event_id='B20260826_Chhochen',independent_event_group='B20260826_Chhochen',physical_phase='first_mechanical_initiation_at_source',
                 time_utc=None,time_uncertainty=None,space_object=None,variable_semantics=None,available_time=None,forecast_reference_time=None,issue_time=None,valid_time=None,
                 evidence_status='candidate_truth_unaccepted',data_role='exploration',input_version=VERSION,evaluation_stratum='local_observational',
                 approved_training_label=False,approved_independent_validation_label=False,notes='9 source records remain one case; exact first mechanical initiation not adopted'),
            dict(event_id='USGS:us7000tc90',independent_event_group=None,physical_phase=later['physical_phase'],time_utc=later['time_utc'],
                 time_uncertainty=later['time_uncertainty'],space_object=later['space_object'],variable_semantics=None,available_time=None,forecast_reference_time=None,issue_time=None,valid_time=None,
                 evidence_status='different_subevent_regional_sequence_causality_independence_unknown',data_role='exploration',input_version=VERSION,evaluation_stratum='local_observational',
                 approved_training_label=False,approved_independent_validation_label=False,notes='Excluded as primary first initiation; does not establish independent validation event')]
    labels=[]
    for row in ledger['records']:
        labels.append(dict(event_id=row['event_id'],evidence_id=row['evidence_id'],independent_event_group=row.get('independent_event_group'),
                           physical_phase=row.get('physical_stage'),time_utc=row.get('event_time_utc'),time_uncertainty={'source_seconds':row.get('time_uncertainty_seconds'),'mechanical_proxy_bias_seconds':None},
                           space_object=row.get('coordinates'),variable_semantics=None,available_time=None,forecast_reference_time=None,issue_time=None,valid_time=None,
                           data_role='exploration',evidence_status=row.get('label_role'),input_version=VERSION,
                           source_url=row.get('source_url'),approved_training_label=False,approved_independent_validation_label=False))
    labels.append(dict(groups[1],evidence_id='USGS_us7000tc90_R2',source_url=later['source_url']))
    labels.append(dict(groups[0],evidence_id='primary_prediction_target',source_url=None))
    availability=[]
    for mode,latency in [('historically_available',None),('assumed_latency',0),('assumed_latency',3),('assumed_latency',6),('assumed_latency',9)]:
        availability.append(dict(event_id='B20260826_Chhochen',physical_phase='environmental_forecast_background',forecast_reference_time=forecast['forecast_reference_time'],
                                 valid_time=forecast['valid_time'],available_time=None,issue_time=None,time_utc=None,time_uncertainty=None,space_object=None,variable_semantics='f009 snapshot only; cumulative fields retain message-specific interval',
                                 forecast_input_mode=mode,assumed_latency_hours=latency,assumption_is_historical_fact=False,
                                 evidence_status='unknown_historical_availability',data_role='exploration' if latency is None else 'scenario',input_version=VERSION,
                                 object_url=forecast['object_url'],historically_eligible=False))
    for name,rows in [('event_group_registry.csv',groups),('label_mapping.csv',labels),('forecast_availability.csv',availability)]:
        write_csv(R/'results'/name,rows);write_csv(target/name,rows)
    files=[]
    for p in sorted(target.iterdir()):files.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=digest(p),role=p.stem))
    bundle=dict(bundle_version='q3-r3-event-v1-local',producer_question='q3',created_at_utc=datetime.now(timezone.utc).isoformat(),input_version=VERSION,
                evaluation_stratum='local_observational',files=files,limitations=['Local exact first mechanical initiation remains unaccepted; independent accepted local training/validation=0',
                'Later us7000tc90 is a different subevent; causal relation and statistical independence unverified',
                'Historical GFS first availability unknown; latency values are assumptions only',
                'External real deformation and exposure acquisition is ongoing; later update will have a new version and paths'])
    (R/'exports/event_bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str((R/'exports/event_bundle.json').relative_to(ROOT)),sha256=digest(R/'exports/event_bundle.json'),files=len(files),label_rows=len(labels))))

if __name__=='__main__':main()
