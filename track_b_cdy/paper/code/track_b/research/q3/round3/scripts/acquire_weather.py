#!/usr/bin/env python3
"""Acquire bounded NOAA GFS fields, then offline derive hourly regional weather.

AI assistance: OpenAI Codex, 2026-10-24. No claim of operational availability.
Original project environment is read only; this script uses its existing packages.
"""
from __future__ import annotations
import argparse, concurrent.futures, csv, hashlib, json, re, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import eccodes
import numpy as np

R = Path(__file__).resolve().parents[1]
ROOT = R.parents[3]
CACHE = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/weather')
OUT = R / 'inputs/weather'
RES = R / 'results/weather'
CYCLES = ['2026082318', '2026082418', '2026082518']
MAX_LEAD = 96
BASE = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com/'

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
def stamp(x): return x.isoformat().replace('+00:00', 'Z')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
def writecsv(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def product(cycle, lead):
    return f'gfs.{cycle[:8]}/{cycle[8:]}/atmos/gfs.t{cycle[8:]}z.pgrb2.0p25.f{lead:03d}'

def fetch(url, path, byte_range=None):
    log = path.with_suffix(path.suffix+'.http.json')
    if path.exists() and log.exists():
        record=json.loads(log.read_text())
        expected_range=list(byte_range) if byte_range else None
        expected_status=206 if byte_range else 200
        consistent=(record['canonical_url_or_product_id']==url and
            record['byte_range']==expected_range and record['cache_path']==str(path) and
            record['http_status']==expected_status and record['bytes']==path.stat().st_size and
            sha(path)==record['sha256'])
        if byte_range:
            h={k.lower():v for k,v in record['response_headers'].items()}
            consistent=consistent and record['bytes']==byte_range[1]-byte_range[0]+1 and h.get('content-range','').startswith(f'bytes {byte_range[0]}-{byte_range[1]}/')
        if not consistent:raise ValueError(f'Cache provenance/hash mismatch {path}')
        return record
    if path.exists() or log.exists(): raise ValueError(f'Incomplete immutable cache {path}')
    headers={'User-Agent':'MathorCup-Q3-research/round3'}
    if byte_range: headers['Range']=f'bytes={byte_range[0]}-{byte_range[1]}'
    error=None
    for attempt in range(3):
        try:
            begin=now()
            with urlopen(Request(url, headers=headers), timeout=60) as response:
                status=response.status; h=dict(response.headers.items())
                if byte_range:
                    expected=byte_range[1]-byte_range[0]+1
                    cr=response.headers.get('Content-Range','')
                    if status!=206 or not cr.startswith(f'bytes {byte_range[0]}-{byte_range[1]}/'):
                        raise ValueError(f'Range not honored {status} {cr}')
                    raw=response.read(expected+1)
                    if len(raw)!=expected:raise ValueError('range length mismatch')
                    if raw[:4]!=b'GRIB' or raw[-4:]!=b'7777' or int.from_bytes(raw[8:16],'big')!=expected:
                        raise ValueError('not one complete GRIB2 message')
                else:
                    if status!=200:raise ValueError(f'index status {status}')
                    raw=response.read(1000001)
                    if len(raw)>1000000:raise ValueError('index size out of scope')
            end=now();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            record={'canonical_url_or_product_id':url,'request_started_at_utc':begin,'retrieved_at_utc':end,
                    'http_status':status,'response_headers':h,'bytes':len(raw),'sha256':sha(path),
                    'byte_range':list(byte_range) if byte_range else None,'cache_path':str(path),
                    'actual_read_scope':'one complete global GRIB2 field; derive only 85–86E,28–29N' if byte_range else 'field names and byte offsets only',
                    'available_time':None,'data_role':'conditional_scenario',
                    'product_version':{'exact_key':url.removeprefix(BASE),'etag':h.get('ETag') or h.get('Etag')}}
            dump(log,record);return record
        except Exception as exc:
            error=exc
            if attempt<2:time.sleep(1+attempt)
    raise RuntimeError(f'{url}: {error}')

def acquire_one(cycle,lead):
    key=product(cycle,lead);d=CACHE/cycle/f'f{lead:03d}';d.mkdir(parents=True,exist_ok=True)
    idx=d/'inventory.idx';records=[fetch(BASE+key+'.idx',idx)]
    lines=idx.read_text().splitlines();offsets=[int(x.split(':')[1]) for x in lines]
    selected=[]
    temp=[i for i,l in enumerate(lines) if ':TMP:2 m above ground:' in l]
    if len(temp)!=1:raise ValueError(f'TMP unique {cycle}/{lead}')
    selected.append(('temperature_2m',temp[0]))
    if lead:
        # Two APCP messages can share 0-N text at initial bucket. Last is the
        # explicit full-run accumulation (record 597 in initial audited sample).
        p=[i for i,l in enumerate(lines) if ':APCP:surface:' in l and
           (f':0-{lead} hour acc fcst:' in l or
            (lead%24==0 and f':0-{lead//24} day acc fcst:' in l))]
        if not p:raise ValueError(f'No full-run accumulation {cycle}/{lead}')
        selected.append(('precipitation_cumulative',p[-1]))
    for name,i in selected:
        record=fetch(BASE+key,d/(name+'.grib2'),(offsets[i],offsets[i+1]-1))
        record=dict(record,index_line=lines[i],index_sha256=sha(idx),variable=name)
        records.append(record)
    return records

def decode(path,cycle,lead):
    with path.open('rb') as f:g=eccodes.codes_grib_new_from_file(f)
    try:
        fields={k:eccodes.codes_get(g,k) for k in ['shortName','units','typeOfLevel','level','dataDate','dataTime',
          'validityDate','validityTime','startStep','endStep','stepUnits','stepType','Ni','Nj',
          'latitudeOfFirstGridPointInDegrees','longitudeOfFirstGridPointInDegrees',
          'iDirectionIncrementInDegrees','jDirectionIncrementInDegrees','jScansPositively',
          'centre','generatingProcessIdentifier']}
        ref=datetime.strptime(cycle,'%Y%m%d%H').replace(tzinfo=timezone.utc)
        valid=ref+timedelta(hours=lead)
        assert fields['dataDate']==int(cycle[:8]) and fields['dataTime']==int(cycle[8:])*100
        assert fields['endStep']==lead and fields['stepUnits']==1
        assert fields['validityDate']==int(valid.strftime('%Y%m%d')) and fields['validityTime']==int(valid.strftime('%H%M'))
        lat=fields['latitudeOfFirstGridPointInDegrees']+np.arange(fields['Nj'])*fields['jDirectionIncrementInDegrees']*(1 if fields['jScansPositively'] else -1)
        lon=fields['longitudeOfFirstGridPointInDegrees']+np.arange(fields['Ni'])*fields['iDirectionIncrementInDegrees']
        yi=np.flatnonzero((lat>=28)&(lat<=29));xi=np.flatnonzero((lon>=85)&(lon<=86))
        vals=eccodes.codes_get_values(g).reshape(fields['Nj'],fields['Ni'])[np.ix_(yi,xi)]
        assert vals.shape==(5,5) and np.isfinite(vals).all()
        return lat[yi],lon[xi],vals,fields
    finally:eccodes.codes_release(g)

def derive():
    protocol=R/'EXPERIMENT_PROTOCOL.md'
    if not protocol.exists():raise RuntimeError('Experiment protocol not registered')
    grid=[];means=[];metadata=[];negative=[];sources=[]
    proxy_path=ROOT/'track_b/data/external/event_remote/runs/20261024T034202Z/raw/usgs_event.json'
    proxy_lon,proxy_lat,_=json.loads(proxy_path.read_text())['geometry']['coordinates']
    sources.append({'canonical_url_or_product_id':'repo-input:'+str(proxy_path.relative_to(ROOT)),
        'product_version':'frozen-round3-baseline-file-sha256','retrieved_at_utc':None,
        'actual_read_scope':'original us7000tbwb catalogue geometry only; not accepted physical source geometry',
        'bytes':proxy_path.stat().st_size,'sha256':sha(proxy_path),'cache_path':str(proxy_path),
        'data_role':'proxy_spatial_reference','available_time':None})
    for cycle in CYCLES:
        ref=datetime.strptime(cycle,'%Y%m%d%H').replace(tzinfo=timezone.utc)
        prev=np.zeros((5,5));origin_cum=None
        for lead in range(MAX_LEAD+1):
            d=CACHE/cycle/f'f{lead:03d}'
            sources.append(json.loads((d/'inventory.idx.http.json').read_text()))
            lat,lon,temp,tmeta=decode(d/'temperature_2m.grib2',cycle,lead)
            assert tmeta['shortName']=='2t' and tmeta['typeOfLevel']=='heightAboveGround' and tmeta['level']==2
            t_record=json.loads((d/'temperature_2m.grib2.http.json').read_text())
            sources.append(dict(t_record,variable='temperature_2m'))
            if lead:
                _,_,cum,pmeta=decode(d/'precipitation_cumulative.grib2',cycle,lead)
                assert pmeta['startStep']==0 and pmeta['stepType']=='accum'
                assert pmeta['shortName']=='tp' and pmeta['typeOfLevel']=='surface' and pmeta['level']==0
                assert pmeta['units']=='kg m**-2' and tmeta['units']=='K'
                raw_increment=cum-prev
                # Quantisation can cause tiny negative differences; preserve raw
                # value in CSV and mark it, never silently sum overlapping totals.
                negative.extend([{'cycle':cycle,'lead':lead,'raw_increment_mm':float(v)} for v in raw_increment[raw_increment<0]])
                inc=raw_increment.copy();inc[inc<0]=np.nan
                p_record=json.loads((d/'precipitation_cumulative.grib2.http.json').read_text())
                th={k.lower():v for k,v in t_record['response_headers'].items()}
                ph={k.lower():v for k,v in p_record['response_headers'].items()}
                assert th.get('etag') and th['etag']==ph.get('etag'), 'T/APCP object versions differ'
                sources.append(dict(p_record,variable='precipitation_cumulative'))
                prev=cum
            else:
                cum=np.zeros((5,5));inc=np.full((5,5),np.nan);raw_increment=inc;pmeta=None
            valid=ref+timedelta(hours=lead)
            common={'forecast_reference_time':stamp(ref),'valid_time':stamp(valid),'lead_hours':lead,
                'issue_time':None,
                'precipitation_interval_start':stamp(valid-timedelta(hours=1)) if lead else None,
                'precipitation_interval_end':stamp(valid) if lead else None,'available_time':None,
                'available_time_status':'unknown_historical_first_public_availability',
                'source_product_version':product(cycle,lead),'data_role':'conditional_scenario'}
            for j,la in enumerate(lat):
                for i,lo in enumerate(lon):
                    grid.append(dict(common,latitude=float(la),longitude=float(lo),temperature_2m_K=float(temp[j,i]),
                       precipitation_increment_mm=float(inc[j,i]) if np.isfinite(inc[j,i]) else None,
                       precipitation_increment_raw_mm=float(raw_increment[j,i]) if np.isfinite(raw_increment[j,i]) else None,
                       precipitation_cumulative_mm=float(cum[j,i]) if lead else 0.0,
                       precipitation_qc='negative_difference_missing' if lead and not np.isfinite(inc[j,i]) else 'full_run_difference' if lead else 'no_preceding_forecast_interval'))
            # AOI mean is an unweighted diagnostic, not observed source climate.
            # Proxy-point nearest grid: original USGS centre 28.271N,85.515E;
            # use immutable original GeoJSON centre when source map is required.
            j=int(np.argmin(abs(lat-proxy_lat)));i=int(np.argmin(abs(lon-proxy_lon)))
            for space,tt,pp,cc in [('aoi_unweighted_mean',float(temp.mean()),float(np.nanmean(inc)) if lead else None,float(cum.mean())),
                ('proxy_nearest_grid_28.25N_85.5E',float(temp[j,i]),float(inc[j,i]) if lead and np.isfinite(inc[j,i]) else None,float(cum[j,i]))]:
                means.append(dict(common,space_object=space,temperature_2m_K=tt,temperature_2m_C=tt-273.15,
                    precipitation_increment_mm=pp,precipitation_cumulative_mm=cc))
            metadata.append({'cycle':cycle,'lead':lead,'temperature':tmeta,'precipitation':pmeta})
    groups={}
    for row in grid:
        groups.setdefault((row['forecast_reference_time'],row['latitude'],row['longitude']),[]).append(row)
    check_groups=[]
    for key,rows in groups.items():
        ordered=sorted(rows,key=lambda x:x['lead_hours'])
        check_groups.append(list(x['lead_hours'] for x in ordered)==list(range(MAX_LEAD+1)) and
            abs(sum(x['precipitation_increment_raw_mm'] for x in ordered[1:])-ordered[-1]['precipitation_cumulative_mm'])<1e-8 and
            all(x['precipitation_interval_start']==ordered[n-1]['valid_time'] for n,x in enumerate(ordered) if n))
    checks={'expected_grid_rows':len(grid)==len(CYCLES)*(MAX_LEAD+1)*25,
        'expected_summary_rows':len(means)==len(CYCLES)*(MAX_LEAD+1)*2,
        'unique_time_grid_keys':len({(x['forecast_reference_time'],x['lead_hours'],x['latitude'],x['longitude']) for x in grid})==len(grid),
        'complete_leads_intervals_and_precipitation_telescope':all(check_groups),
        'finite_plausible_temperature':all(np.isfinite(x['temperature_2m_K']) and 150<x['temperature_2m_K']<350 for x in grid),
        'nonnegative_cumulative_precipitation':all(x['precipitation_cumulative_mm']>=0 for x in grid),
        'f000_interval_and_increment_missing':all(x['precipitation_increment_mm'] is None and x['precipitation_interval_start'] is None for x in grid if x['lead_hours']==0),
        'unknown_historical_availability_preserved':all(x['available_time'] is None and x['issue_time'] is None for x in grid)}
    if not all(checks.values()):raise ValueError(f'Weather validation failed {checks}')
    dump(RES/'validation.json',{'checks':checks,'passed':all(checks.values()),'grid_point_cycle_series_count':len(groups),
        'independent_disaster_events_evaluated':0,'source_metadata_assertions':'variable/level/reference/valid/interval/units/T-APCP_ETag checked on decoding'})
    writecsv(OUT/'gfs_hourly_source_grid.csv',grid)
    writecsv(OUT/'gfs_hourly_summary.csv',means)
    dump(RES/'decoded_metadata.json',metadata)
    dump(RES/'precipitation_difference_qc.json',{'negative_difference_cells':len(negative),'negative_values':negative,
       'rule':'negative raw values preserved, usable increments missing; no silent clipping or overlapping sum'})
    local_summary,local_sources=local_case()
    sources.extend(local_sources)
    documentation=OUT/'docs/sources.json'
    if documentation.exists():
        for item in json.loads(documentation.read_text()):
            item['cache_path']=str(ROOT/item['path'])
            sources.append(item)
    dump(R/'results/weather_sources.json',{'schema_version':'q3-weather-v1','sources':sources,
       'script_sha256':sha(Path(__file__)),'protocol_sha256':sha(protocol)})
    summary={'schema_version':'q3-weather-v1','cycles':CYCLES,'forecast_hours':list(range(MAX_LEAD+1)),
      'original_grid_cells':25,'grid_rows':len(grid),'summary_rows':len(means),'negative_increment_cells':len(negative),
      'first_valid_time':min(x['valid_time'] for x in grid),'last_valid_time':max(x['valid_time'] for x in grid),
      'historically_available_records':0,'available_time':None,'historically_available_status':'not_established',
      'assumed_latency_hours':[0,3,6,9],
      'raw_cached_grib_bytes':sum(x['bytes'] for x in sources if x.get('byte_range')),
      'all_source_hashes_rechecked':all(sha(Path(x['cache_path']))==x['sha256'] for x in sources),
      'local_observational_case':local_summary,
      'outputs':[{ 'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in [OUT/'gfs_hourly_source_grid.csv',OUT/'gfs_hourly_summary.csv']],
      'limitations':['0.25 degree forecast grid does not resolve source slope/valley weather',
        'Weather sequences are model forecasts, not observations; no local meteorological skill calibration',
        'Source target exact location remains uncertain; AOI and proxy nearest point are exploratory',
        'Historical first availability unknown; Last-Modified not substituted for it',
        'Hourly increments are differences of independently packed full-run accumulations; negative rounding differences are missing',
        'f000 has no precipitation interval; cumulative zero there is mathematical empty-interval boundary']}
    dump(RES/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))

def local_case():
    """Keep actual regional station observations distinct from model forecasts."""
    import pandas as pd
    d=ROOT/'track_b/data/processed/temporal'
    inputs=['hourly_time_axis.parquet','hourly_raw_numeric.parquet','hourly_strict_qc0.parquet',
            'hourly_raw_qc.parquet','data_dictionary.json']
    axis=pd.read_parquet(d/inputs[0],columns=['hour_index','time_utc'])
    selected=axis[(axis.time_utc>='2026-08-22')&(axis.time_utc<'2026-08-30')]
    ix=selected.hour_index
    strict=pd.read_parquet(d/'hourly_strict_qc0.parquet',columns=['MET__Ta_2m']).iloc[ix]
    raw=pd.read_parquet(d/'hourly_raw_numeric.parquet',columns=['MET__Ta_2m','MET__Precip']).iloc[ix]
    qc=pd.read_parquet(d/'hourly_raw_qc.parquet',columns=['MET__Ta_2m']).iloc[ix]
    rows=[]
    for k,(_,x) in enumerate(selected.iterrows()):
        t=strict.iloc[k,0];r=raw.iloc[k,1]
        tval=float(t) if pd.notna(t) else None
        rain=float(r) if pd.notna(r) and np.isfinite(r) and r!=9999.9 else None
        rows.append({'time_utc':x.time_utc.isoformat().replace('+00:00','Z'),
          'station_id':'Gyirong_regional_background',
          'temperature_2m_C_qc0':tval,'temperature_2m_K_qc0':tval+273.15 if tval is not None else None,
          'temperature_qc_raw':qc.iloc[k,0],
          'precipitation_header_mm_raw':rain,'precipitation_interval_start':None,'precipitation_interval_end':None,
          'precipitation_qc_status':'no_QC_column; finite_non_sentinel_only',
          'timezone_status':'UTC+8_assumed_from_same_title_metadata_mirror; file_equivalence_not_hash_verified',
          'timestamp_label_semantics':'unverified_instant_start_end_or_centre',
          'available_time':None,'data_role':'local_observational_ideal_input_only'})
    writecsv(OUT/'local_weather_case.csv',rows)
    records=[{'canonical_url_or_product_id':'repo-input:track_b/data/processed/temporal/'+p,
       'product_version':'frozen-round3-baseline-file-sha256',
       'retrieved_at_utc':None,'actual_read_scope':'2026-08-22 through 29 UTC; temp2m,precip only; dictionary and time axis',
       'bytes':(d/p).stat().st_size,'sha256':sha(d/p),'cache_path':str(d/p),
       'data_role':'local_observational_ideal_input_only','available_time':None} for p in inputs]
    return {'rows':len(rows),'temperature_qc0_present':sum(x['temperature_2m_C_qc0'] is not None for x in rows),
       'precipitation_finite_non_sentinel_present':sum(x['precipitation_header_mm_raw'] is not None for x in rows),
       'precipitation_interval_verified':False,'first_valid_temp':next((x['time_utc'] for x in rows if x['temperature_2m_C_qc0'] is not None),None),
       'last_valid_temp':next((x['time_utc'] for x in reversed(rows) if x['temperature_2m_C_qc0'] is not None),None)},records

def main():
    a=argparse.ArgumentParser();a.add_argument('--collect',action='store_true');a.add_argument('--workers',type=int,default=8);args=a.parse_args()
    assert ROOT==Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3')
    if args.collect:
        jobs=[(c,h) for c in CYCLES for h in range(MAX_LEAD+1)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            for n,records in enumerate(ex.map(lambda t:acquire_one(*t),jobs),1):
                if n%12==0:print(f'acquired {n}/{len(jobs)} forecast hours',flush=True)
    derive()
if __name__=='__main__':main()
