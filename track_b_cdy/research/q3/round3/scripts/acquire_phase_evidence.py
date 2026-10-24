#!/usr/bin/env python3
"""Preserve an official phase product; catalogue origin is not mechanical truth."""
from datetime import datetime,timezone
import hashlib,json
import base64
from pathlib import Path
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]
URL='https://earthquake.usgs.gov/product/phase-data/us7000tbwb/us/1792791413040/quakeml.xml'

def main():
    sources=R/'sources';sources.mkdir(parents=True,exist_ok=True)
    p=sources/'us7000tbwb_phase_1792791413040.xml';log=sources/'us7000tbwb_phase_1792791413040.request.json'
    if not p.exists():
        start=datetime.now(timezone.utc).isoformat()
        with urlopen(Request(URL,headers={'User-Agent':'MathorCup-Q3-phase-evidence/round3'}),timeout=40) as response:
            assert response.status==200
            data=response.read(2097153);assert len(data)<=2097152
            meta=dict(canonical_url_or_product_id=URL,product_version='phase-data/us7000tbwb/us/1792791413040',request_started_at_utc=start,
                 retrieved_at_utc=datetime.now(timezone.utc).isoformat(),response_headers=dict(response.headers.items()),http_status=response.status,
                 actual_read_scope='all QuakeML origin, pick and arrival metadata; no raw seismic waveform',data_role='retrospective_label_evidence',available_time=None)
        p.write_bytes(data);meta.update(cache_path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest());log.write_text(json.dumps(meta,indent=2)+'\n')
    meta=json.loads(log.read_text());assert meta['canonical_url_or_product_id']==URL and meta['bytes']==p.stat().st_size and meta['sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    root=ET.parse(p);ns={'b':'http://quakeml.org/xmlns/bed/1.2'}
    origins=[];picks=[];arrivals=[]
    for o in root.findall('.//b:origin',ns):
        def value(key):
            x=o.find(key,ns);return x.text if x is not None else None
        origins.append(dict(origin_id=o.attrib.get('publicID'),time_utc=value('b:time/b:value'),time_uncertainty_seconds=value('b:time/b:uncertainty'),confidence_level=value('b:time/b:confidenceLevel'),
                            method_id=value('b:methodID'),earth_model_id=value('b:earthModelID'),evaluation_mode=value('b:evaluationMode'),evaluation_status=value('b:evaluationStatus')))
        for a in o.findall('b:arrival',ns):
            record={'origin_id':o.attrib.get('publicID')}
            for key in ['pickID','phase','distance','azimuth','timeResidual','timeWeight']:
                v=a.find('b:'+key,ns);record[key]=v.text if v is not None else None
            arrivals.append(record)
    for pck in root.findall('.//b:pick',ns):
        t=pck.find('b:time/b:value',ns);wave=pck.find('b:waveformID',ns);phase=pck.find('b:phaseHint',ns)
        mode=pck.find('b:evaluationMode',ns)
        picks.append(dict(pick_id=pck.attrib.get('publicID'),time_utc=t.text if t is not None else None,waveform_id=wave.attrib if wave is not None else None,phase_hint=phase.text if phase is not None else None,evaluation_mode=mode.text if mode is not None else None))
    headers={k.lower():v for k,v in meta['response_headers'].items()};declared=headers.get('x-amz-meta-sha256')
    if declared:assert base64.b64encode(hashlib.sha256(p.read_bytes()).digest()).decode()==declared
    report=dict(source=meta,origins=origins,picks=picks,arrivals=arrivals,counts={'origins':len(origins),'picks':len(picks),'arrivals':len(arrivals)},
       source_event='us7000tbwb',physical_phase='catalogue_seismic_reference_proxy',mechanical_first_onset_truth=None,
       nearest_pick_distance_degrees=min(float(a['distance']) for a in arrivals if a['distance'] is not None),
       manual_pick_count=sum(x['evaluation_mode']=='manual' for x in picks),
       nearby_KKN_or_EVN_used=any(x['waveform_id'] and x['waveform_id'].get('stationCode') in ['KKN','EVN'] for x in picks),
       server_declared_sha256_matches=bool(declared),
       independent_events_added=0,limitations=['Pick timestamps are station observations; travel-time origin inversion is a catalogue proxy',
         'Quoted origin error is conditional on the catalogue model, not the unmeasured mechanical-onset proxy bias',
         'No waveform signal, clock calibration or emission-to-first-motion mapping reviewed here; no new primary truth accepted'])
    out=R/'results/phase_evidence';out.mkdir(parents=True,exist_ok=True)
    (out/'phase_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['counts']))

if __name__=='__main__':main()
