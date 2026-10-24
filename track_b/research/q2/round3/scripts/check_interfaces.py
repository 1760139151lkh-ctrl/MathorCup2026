"""Hash-verifies advisor-delivered own-tree inputs and uses their constraints."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from run_experiments import ROOT,BASE,write_json

BUNDLES={
 'q1':('inputs/q1/feature_bundle_q1-r3-feature-v1/bundle.json','765037010dadc269a6b3d89831abb61fc9d1163c2b9b989facbfcf4a2107b918'),
 'q3':('inputs/q3/event_bundle_q3-r3-event-v1-local/bundle.json','16ecf5a0e3af9ad572104490b79a56f59a78fc011e37cee2dd8f75e34d0a5a32'),
 'q4':('inputs/q4/bundle_q4-r3-spatial-copdem-v1-frozen-export/bundle.json','8eb6cbc1b85e60fe8a82906f4f025ec22b3bcf96d5c59bd0535ffbe0ccf8a0c5')}


def run():
    records=[];files={}
    for q,(path,expected) in BUNDLES.items():
        p=BASE/path;assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
        data=json.loads(p.read_text());files[q]={}
        for row in data['files']:
            f=Path(row['path']);f=f if f.is_absolute() else ROOT/f
            b=f.read_bytes();assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
            if not f.is_relative_to(BASE):assert str(f).startswith('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/')
            files[q][row['role']]=f
        records.append(dict(producer=q,bundle_version=data['bundle_version'],path=str(p.relative_to(ROOT)),sha256=expected,
          checked_files=len(data['files']),adoption_scope=data['advisor_review']['adoption_scope'],advisor_note=data['advisor_review']['note']))
    # Semantically read Q1 driver definitions and original-vs-unknown quality tracks.
    defs=pd.read_csv(files['q1']['feature_definitions'])
    drivers=pd.read_parquet(files['q1']['2026_regional_hourly_drivers'])
    forcing=pd.read_csv(BASE/'results/forcing_hourly_v1.csv',parse_dates=['time_utc'])
    checks={}
    for quality in ['original_qc_view','unknown_qc_exploration']:
        d=drivers[drivers.quality_track==quality].copy();d['time_utc']=pd.to_datetime(d.time_utc,utc=True)
        merged=forcing.merge(d,on='time_utc')
        good=merged[['station_air_temp_c','air_temperature_2m']].notna().all(axis=1)
        delta=np.abs(merged.loc[good,'station_air_temp_c']-merged.loc[good,'air_temperature_2m'])
        assert len(delta)>0 and delta.max()==0
        rain=merged[['precip_assumed_mm_h','precipitation_label']].notna().all(axis=1)
        if rain.any():assert np.allclose(merged.loc[rain,'precip_assumed_mm_h'],merged.loc[rain,'precipitation_label'],rtol=0,atol=0)
        checks[quality]=dict(overlap_hours=len(merged),finite_temperature_pairs=int(good.sum()),temperature_max_abs_difference_c=float(delta.max()),
          finite_rain_label_pairs=int(rain.sum()),rain_accumulation_accepted=False,source_representativeness_accepted=False)
    # Labels are read for constraints only, never converted into fitting targets.
    label=pd.read_csv(files['q3']['label_mapping']);groups=pd.read_csv(files['q3']['event_group_registry']);availability=pd.read_csv(files['q3']['forecast_availability'])
    result=dict(passed=True,inputs=records,q1_driver_compatibility=checks,q1_feature_definition_rows=len(defs),
      q3_label_rows=len(label),q3_event_group_rows=len(groups),q3_availability_rows=len(availability),
      accepted_local_training_events=0,accepted_local_validation_events=0,
      actual_use={'q1':'QC-separated regional temperature agrees exactly over overlap; precipitation remains label statistics; Q2 conversion only conditional assumption',
        'q3':'No exact first initiation truth accepted; no event-time calibration and no historical forecast availability claim',
        'q4':'Conditional geometry integrated separately in release_bundle_v2; top-level role paths used'},
      no_cross_worktree_activity_reads=True)
    write_json(BASE/'results/interface_use.json',result)
    print(json.dumps({'passed':True,'input_bundles':len(records),'q1_overlap':checks}))


if __name__=='__main__':run()
