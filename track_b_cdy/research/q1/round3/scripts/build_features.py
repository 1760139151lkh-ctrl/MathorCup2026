#!/usr/bin/env python3
"""Extract the preregistered Q1 R3 features without changing public inputs.

Uses the original locked 44-package environment.  Every driver is evaluated on
accepted hourly labels before derivatives; no interpolation or coverage cut is
applied here. Published v1 bytes are immutable: reruns compare before writing.
AI assistance: OpenAI Codex, 2026-10-24; human scientific adoption pending.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
R3 = ROOT / 'track_b/research/q1/round3'
TEMP = ROOT / 'track_b/data/processed/temporal'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def emit(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f'Published v1 file differs; create a new version, do not overwrite: {path}')
    else:
        path.write_bytes(data)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def emit_csv(path, frame):
    emit(path, frame.to_csv(index=False, lineterminator='\n').encode())


def emit_parquet(path, frame):
    stream = io.BytesIO()
    frame.to_parquet(stream, index=False, engine='pyarrow', compression='zstd')
    emit(path, stream.getvalue())


def drivers():
    specifications = [
        ('air_temperature_2m', 'air_thermal', ['MET__Ta_2m'], 'identity', 'degC', 'Ta_2m'),
        ('air_temperature_gradient', 'air_thermal', ['MET__Ta_20m','MET__Ta_2m'], 'difference18', 'degC m-1', '(Ta_20m - Ta_2m)/18 m; nominal measurement heights'),
        ('relative_humidity_2m', 'air_moisture', ['MET__RH_2m'], 'identity', '%', 'RH_2m'),
        ('relative_humidity_gradient', 'air_moisture', ['MET__RH_20m','MET__RH_2m'], 'difference18', 'percentage_point m-1', '(RH_20m - RH_2m)/18 m; nominal measurement heights'),
        ('wind_speed_10m', 'mean_wind', ['MET__WS_10m'], 'identity', 'm s-1', 'WS_10m'),
        ('wind_speed_gradient', 'mean_wind', ['MET__WS_20m','MET__WS_2m'], 'difference18', 's-1', '(WS_20m - WS_2m)/18 m; not friction velocity'),
        ('wind_direction_sin_10m', 'mean_wind', ['MET__WD_10m'], 'sin_degrees', '1', 'sin(WD_10m*pi/180); not a vector-mean direction'),
        ('wind_direction_cos_10m', 'mean_wind', ['MET__WD_10m'], 'cos_degrees', '1', 'cos(WD_10m*pi/180); not a vector-mean direction'),
        ('air_pressure', 'air_pressure', ['MET__Pressure'], 'identity', 'hPa', 'Pressure'),
        ('shortwave_down', 'shortwave', ['RADM__Rsd'], 'identity', 'W m-2', 'Rsd'),
        ('shortwave_difference', 'shortwave', ['RADM__Rsd','RADM__Rsu'], 'difference', 'W m-2', 'Rsd - Rsu; instrument sign convention remains unverified'),
        ('longwave_down', 'longwave', ['RADM__Rld'], 'identity', 'W m-2', 'Rld'),
        ('longwave_difference', 'longwave', ['RADM__Rld','RADM__Rlu'], 'difference', 'W m-2', 'Rld - Rlu; instrument sign convention remains unverified'),
        ('soil_temperature_0p1m', 'soil_thermal', ['SOIL__soilT_0.1m'], 'identity', 'degC', 'soilT_0.1m'),
        ('soil_temperature_gradient', 'soil_thermal', ['SOIL__soilT_0.1m','SOIL__soilT_0.8m'], 'difference0p7', 'degC m-1', '(soilT_0.1m - soilT_0.8m)/0.7 m; shallow-minus-deep nominal gradient'),
        ('soil_vwc_0p1m', 'soil_moisture', ['SOIL__VWC_0.1m'], 'identity', 'm3 m-3', 'VWC_0.1m'),
        ('soil_vwc_gradient', 'soil_moisture', ['SOIL__VWC_0.1m','SOIL__VWC_0.8m'], 'difference0p7', 'm3 m-4', '(VWC_0.1m - VWC_0.8m)/0.7 m; shallow-minus-deep nominal gradient'),
        ('soil_heat_flux_0p1m', 'soil_heat_flux', ['SOIL__G_0.1m'], 'identity', 'W m-2', 'G_0.1m; sign convention remains unverified'),
        ('vapour_pressure_deficit', 'air_moisture', ['FLUX__VPD'], 'identity', 'hPa', 'VPD; unknown FLUX QC, processing and averaging interval'),
        ('precipitation_label', 'precipitation', ['MET__Precip'], 'identity', 'mm (label value; integration period unknown)', 'Precip label; not cumulative rainfall'),
        ('latent_heat_flux', 'turbulent_heat', ['FLUX__LE'], 'identity', 'W m-2', 'LE; unknown QC/sign/processing; not integrated energy'),
        ('sensible_heat_flux', 'turbulent_heat', ['FLUX__H'], 'identity', 'W m-2', 'H; unknown QC/sign/processing; not integrated energy'),
        ('friction_velocity', 'turbulent_mechanics', ['FLUX__USTAR'], 'identity', 'm s-1', 'USTAR; unknown QC/processing'),
        ('turbulent_kinetic_energy', 'turbulent_mechanics', ['FLUX__TKE'], 'identity', 'm2 s-2', 'TKE; unknown QC/processing'),
    ]
    result = []
    for driver_id, family, variables, operation, unit, formula in specifications:
        unknown = driver_id in {'vapour_pressure_deficit','precipitation_label','latent_heat_flux','sensible_heat_flux','friction_velocity','turbulent_kinetic_energy'}
        result.append({'driver_id':driver_id, 'family_id':family, 'source_variables':variables,
            'operation':operation, 'unit':unit, 'formula':formula,
            'quality_requirement':'numeric_present for supplied no-QC variables; unknown never promoted to QC0' if unknown else 'all source values finite, numeric-present and original QC=0 at same hour',
            'availability_track':'unknown_qc_exploration_only' if unknown else 'both_tracks_original_qc0',
            'statistics':['median'] if 'wind_direction_' in driver_id else ['median','p95','max','positive_fraction','longest_positive_fraction'] if driver_id=='precipitation_label' else ['median','p05','p95','trend_per24h','longest_increase_fraction']})
    return result


def longest_true(mask):
    if not np.any(mask):
        return 0
    padded = np.concatenate(([False], np.asarray(mask, dtype=bool), [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return int(np.max(edges[1::2] - edges[::2]))


def extract(values, hours, stats):
    finite = np.isfinite(values)
    count = int(finite.sum())
    n = len(values)
    result = {s:np.nan for s in stats}
    minimum = float(np.min(values[finite])) if count else np.nan
    maximum = float(np.max(values[finite])) if count else np.nan
    if count >= 2:
        selected = values[finite]
        ordered = np.sort(selected)
        for stat, q in [('median',.5),('p05',.05),('p95',.95)]:
            if stat in result:
                position = (count-1)*q
                lower = int(position)
                upper = min(lower+1,count-1)
                fraction = position-lower
                result[stat] = float(ordered[lower] + (ordered[upper]-ordered[lower])*fraction)
        if 'max' in result:
            result['max'] = maximum
        if 'positive_fraction' in result:
            result['positive_fraction'] = float(np.count_nonzero(selected > 0) / count)
        if 'longest_positive_fraction' in result:
            result['longest_positive_fraction'] = longest_true(finite & (values > 0)) / n
        if 'longest_increase_fraction' in result:
            increases = finite[1:] & finite[:-1] & (np.diff(hours)==1) & (np.diff(values)>0)
            result['longest_increase_fraction'] = longest_true(increases) / n
    if count >= 6 and 'trend_per24h' in result:
        x = hours[finite].astype(float)
        x -= np.mean(x)
        y = values[finite]
        result['trend_per24h'] = float(np.dot(x, y-np.mean(y)) / np.dot(x,x) * 24)
    return result, {'n_valid':count,'n_labels':n,'coverage':count/n,'max_gap_hours':longest_true(~finite)}, minimum, maximum


def main():
    assert Path(sys.prefix).resolve() == (ROOT/'track_b/.venv').resolve()
    experiment_path = R3/'config/experiment.json'
    experiment = json.loads(experiment_path.read_text())
    binding = json.loads((R3/'workspace_binding.json').read_text())
    assert Path(binding['execution_root']) == ROOT
    assert experiment['common_baseline_commit'] == binding['common_baseline_commit']
    assert experiment['baseline_manifest_sha256'] == binding['manifest_sha256']
    assert json.loads((R3/'workspace_verification.json').read_text())['passed']
    definitions = drivers()
    configuration = {'schema_version':'q1-r3-features-v1',
        'input_version':{'common_baseline_commit':binding['common_baseline_commit'],
                         'baseline_manifest_sha256':binding['manifest_sha256'],
                         'experiment_config_sha256':digest(experiment_path.read_bytes()),
                         'experiment_protocol_sha256':digest((R3/'EXPERIMENT_PROTOCOL.md').read_bytes())},
        'feature_id_pattern':'<driver_id>__<statistic>',
        'quality_tracks':experiment['quality_tracks'], 'drivers':definitions,
        'minimum_valid_for_distribution_or_persistence':2,'minimum_valid_for_trend':6,
        'coverage_filter_applied':False,
        'positive_run_definition':'adjacent accepted positive labels; missing breaks; chain label count / nominal window labels',
        'increase_run_definition':'adjacent +1h accepted pairs with positive difference; maximum consecutive increment hours / nominal window labels',
        'time_support':'[anchor-window, anchor) on source hourly labels; timestamp integration semantics unverified',
        'export_time_support_source_clock':['2026-07-01T00:00:00+08:00','2026-08-26T11:30:00+08:00'],
        'v1_immutability':'Existing bytes must match on rerun; changes require a new version and fresh export path'}
    emit(R3/'config/features.json',json_bytes(configuration))
    source_paths=[experiment_path,R3/'EXPERIMENT_PROTOCOL.md',R3/'workspace_binding.json',
        ROOT/'track_b/config/stage4_round3_contract.json',TEMP/'data_dictionary.json',
        TEMP/'hourly_raw_numeric.parquet',TEMP/'hourly_strict_qc0.parquet',
        TEMP/'hourly_mask_is_numeric_present.parquet',TEMP/'hourly_time_axis.parquet',
        ROOT/'track_b/research/q1/results/window_descriptives.csv']
    before={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in source_paths}
    dictionary=json.loads((TEMP/'data_dictionary.json').read_text())['hourly']
    all_variables=[v['variable_id'] for v in dictionary]
    known={v['variable_id'] for v in dictionary if v['qc_raw_column'] is not None}
    unknown=set(all_variables)-known
    assert len(known)==37 and len(unknown)==26
    raw=pd.read_parquet(TEMP/'hourly_raw_numeric.parquet')
    strict=pd.read_parquet(TEMP/'hourly_strict_qc0.parquet')
    present=pd.read_parquet(TEMP/'hourly_mask_is_numeric_present.parquet')
    clock=pd.read_parquet(TEMP/'hourly_time_axis.parquet')
    assert len(raw)==len(strict)==len(present)==len(clock)==52584
    time_ns=clock['time_utc'].astype('int64').to_numpy()
    hour_indices=clock['hour_index'].to_numpy()
    assert np.all(np.diff(time_ns)==3_600_000_000_000) and np.array_equal(hour_indices,np.arange(len(clock)))
    assert strict[list(unknown)].isna().all().all()
    expanded=strict.copy()
    for variable in unknown:
        expanded[variable]=raw[variable].where(present[variable] & np.isfinite(raw[variable]))
    assert expanded[sorted(known)].equals(strict[sorted(known)])
    hourly={}
    for track, table in zip(experiment['quality_tracks'],[strict,expanded]):
        arrays={}
        for d in definitions:
            source=[table[v].to_numpy(dtype=float) for v in d['source_variables']]
            operation=d['operation']
            if operation=='identity': values=source[0].copy()
            elif operation=='sin_degrees':values=np.sin(np.deg2rad(source[0]))
            elif operation=='cos_degrees':values=np.cos(np.deg2rad(source[0]))
            else:
                divisor={'difference':1.,'difference18':18.,'difference0p7':.7}[operation]
                values=(source[0]-source[1])/divisor
            values[~np.isfinite(values)]=np.nan
            arrays[d['driver_id']]=values
        hourly[track]=arrays

    metadata=[]
    for track in experiment['quality_tracks']:
        anchors=[]
        for year in experiment['background_years']:
            for day_offset in range(-30,31):
                date=pd.Timestamp(f'{year}-08-26T10:30:00',tz='Asia/Shanghai')+pd.Timedelta(days=day_offset)
                for shift in experiment['anchor_shifts_hours']:
                    anchors.append((year,day_offset,shift,'problem_1030',False,date+pd.Timedelta(hours=shift)))
        for anchor in experiment['anchor_sources']:
            for shift in experiment['anchor_shifts_hours']:
                anchors.append((2026,0,shift,anchor['anchor_id'],True,pd.Timestamp(anchor['source_time'])+pd.Timedelta(hours=shift)))
        for year,day_offset,shift,anchor_id,target,anchor in anchors:
            for window in experiment['windows_hours']:
                start=anchor-pd.Timedelta(hours=window)
                first=int(np.searchsorted(time_ns,start.tz_convert('UTC').value,side='left'))
                stop=int(np.searchsorted(time_ns,anchor.tz_convert('UTC').value,side='left'))
                assert stop-first==window
                sid=f'{track}|{year}|d{day_offset:+03d}|h{shift:+02d}|{anchor_id}|w{window}'
                metadata.append({'sample_id':sid,'quality_track':track,'year':year,'day_offset':day_offset,
                    'shift_hours':shift,'anchor_id':anchor_id,'window_hours':window,'is_target':target,
                    'anchor_time_utc':anchor.tz_convert('UTC').isoformat(),
                    'support_start_utc':start.tz_convert('UTC').isoformat(),
                    'support_end_utc':anchor.tz_convert('UTC').isoformat(),
                    'first_hour_index':first,'last_hour_index':stop-1,
                    'process_id':f'{year}:calendar7:{(day_offset+30)//7:02d}', 'n_labels':stop-first})
    metadata_frame=pd.DataFrame(metadata)
    assert len(metadata)==5526 and metadata_frame['sample_id'].is_unique
    feature_rows=[]; support_rows=[]; extrema_rows=[]; extraction_cache={}
    for sample in metadata:
        first,last=sample['first_hour_index'],sample['last_hour_index']
        track=sample['quality_track']; sid=sample['sample_id']
        features={'sample_id':sid}
        for d in definitions:
            driver_id=d['driver_id']
            known_driver=d['availability_track']=='both_tracks_original_qc0'
            cache_key=(driver_id,'known_qc' if known_driver else track,first,last)
            if not known_driver and track=='original_qc_view':
                cache_key=(driver_id,'all_unknown_null',last-first+1)
            if cache_key not in extraction_cache:
                extraction_cache[cache_key]=extract(hourly[track][driver_id][first:last+1],hour_indices[first:last+1],d['statistics'])
            extracted,support,minimum,maximum=extraction_cache[cache_key]
            features.update({driver_id+'__'+s:value for s,value in extracted.items()})
            support_rows.append({'sample_id':sid,'driver_id':driver_id,**support})
            extrema_rows.append({'sample_id':sid,'driver_id':driver_id,'n_valid':support['n_valid'],'minimum':minimum,'maximum':maximum})
        feature_rows.append(features)
    feature_frame=pd.DataFrame(feature_rows)
    for column in feature_frame.columns[1:]:feature_frame[column]=feature_frame[column].astype('float64')
    support_frame=pd.DataFrame(support_rows)
    emit_parquet(R3/'results/features.parquet',feature_frame)
    emit_csv(R3/'results/sample_metadata.csv',metadata_frame)
    emit_csv(R3/'results/feature_support.csv',support_frame)
    emit_csv(R3/'results/feature_extrema.csv',pd.DataFrame(extrema_rows))

    contract=[]
    for d in definitions:
        for stat in d['statistics']:
            unit='1' if stat.endswith('_fraction') else d['unit']+' per 24 nominal hours' if stat=='trend_per24h' else d['unit']
            statistic_formula={'median':'linear sample quantile q=0.5','p05':'linear sample quantile q=0.05','p95':'linear sample quantile q=0.95',
                'max':'maximum accepted label value; no accumulation',
                'trend_per24h':'OLS on accepted value versus true hourly index, slope multiplied by 24; >=6 accepted labels',
                'longest_increase_fraction':configuration['increase_run_definition'],
                'positive_fraction':'accepted labels >0 / count(accepted labels)',
                'longest_positive_fraction':configuration['positive_run_definition']}[stat]
            contract.append({'feature_id':d['driver_id']+'__'+stat,'driver_id':d['driver_id'],
                'family_id':d['family_id'],'statistic':stat,'ranking_enabled':True,'unit':unit,
                'source_variables':json.dumps(d['source_variables']), 'formula':d['formula']+'; '+statistic_formula,
                'quality_requirement':d['quality_requirement']+'; '+d['availability_track'],
                'available_time':None,'space_object':'Gyirong_regional_background; metadata longitude85.29 latitude28.86 elevation4140m; coordinate datum and error unknown; local equivalence and source-area representativeness unverified',
                'physical_phase':'background','data_role':'exploration','timestamp_integration_interval':None})
    contract_frame=pd.DataFrame(contract)
    assert list(feature_frame.columns[1:])==contract_frame['feature_id'].tolist()
    emit_csv(R3/'results/feature_contract.csv',contract_frame)
    mappings=[]
    for v in dictionary:
        variable=v['variable_id']; selected=[d for d in definitions if variable in d['source_variables']]
        if selected:
            reason='pre-registered primary measurement or paired nominal gradient'
        elif variable=='FLUX__amb_e_sat':reason='diagnostic only: 4317-label constant segment and processing origin unresolved'
        elif variable.startswith('FLUX__FETCH'):reason='diagnostic footprint/representativeness; not an independent physical trigger factor'
        elif variable=='FLUX__FC_mass':reason='diagnostic only: species and raw unit interpretation unresolved'
        else:reason='not pre-registered; redundant height/depth/component or ambiguous derived quantity; raw input retained'
        if selected:families=sorted({d['family_id'] for d in selected})
        elif variable.startswith('MET__Ta') or variable=='FLUX__T_SONIC':families=['air_thermal']
        elif variable.startswith('MET__RH') or variable in {'FLUX__amb_e','FLUX__amb_e_sat','FLUX__e','FLUX__e_sat','FLUX__e_probe','FLUX__e_sat_probe','FLUX__H2O_probe','FLUX__H2O_density','FLUX__VPD'}:families=['air_moisture']
        elif variable.startswith('MET__WS') or variable.startswith('MET__WD') or variable in {'FLUX__Ux','FLUX__Uy','FLUX__Uz'}:families=['mean_wind']
        elif variable=='FLUX__PA':families=['air_pressure']
        elif variable.startswith('SOIL__soilT'):families=['soil_thermal']
        elif variable.startswith('SOIL__VWC'):families=['soil_moisture']
        elif variable.startswith('SOIL__G'):families=['soil_heat_flux']
        elif variable in {'FLUX__TSTAR'}:families=['turbulent_heat']
        elif variable in {'FLUX__TAU'}:families=['turbulent_mechanics']
        else:families=['excluded_diagnostic']
        mappings.append({'variable_id':variable,'family_ids':json.dumps(families),'driver_ids':json.dumps([d['driver_id'] for d in selected]),
            'ranking_enabled':bool(selected),'selection_status':'included' if selected else 'excluded_from_ranking_preserved_raw',
            'reason':reason,'raw_unit_label':v['raw_unit_label'],'supplied_qc_column':v['qc_raw_column'],
            'quality_status':'original_qc0_required' if variable in known else 'unknown_qc_not_promoted'})
    assert len(mappings)==63
    emit_csv(R3/'results/variable_family_map.csv',pd.DataFrame(mappings))

    start_export=pd.Timestamp(configuration['export_time_support_source_clock'][0]).tz_convert('UTC')
    end_export=pd.Timestamp(configuration['export_time_support_source_clock'][1]).tz_convert('UTC')
    selection=(clock['time_utc']>=start_export)&(clock['time_utc']<=end_export)
    export=[]
    for track in experiment['quality_tracks']:
        part=clock.loc[selection,['hour_index','time_utc']].copy()
        part['quality_track']=track
        for d in definitions:part[d['driver_id']]=hourly[track][d['driver_id']][selection.to_numpy()]
        export.append(part)
    export_frame=pd.concat(export,ignore_index=True)
    emit_parquet(R3/'exports/hourly_drivers.parquet',export_frame)

    # Check actual anchor sets and the previously frozen median diagnostic.
    target=metadata_frame[metadata_frame['is_target']]
    shifts=[]
    for (track,anchor_id,window), group in target.groupby(['quality_track','anchor_id','window_hours'],sort=False):
        group=group.sort_values('shift_hours')
        firsts=group['first_hour_index'].tolist();lasts=group['last_hour_index'].tolist()
        assert np.all(np.diff(firsts)==1) and np.all(np.diff(lasts)==1)
        shifts.append({'quality_track':track,'anchor_id':anchor_id,'window_hours':int(window),'first_hour_indices':firsts,'last_hour_indices':lasts,'changed_by_one_label_each_shift':True})
    r1=pd.read_csv(ROOT/'track_b/research/q1/results/window_descriptives.csv')
    comparison=[]
    mapping={'MET__Ta_2m':'air_temperature_2m','RADM__Rsd':'shortwave_down','SOIL__soilT_0.1m':'soil_temperature_0p1m','SOIL__VWC_0.1m':'soil_vwc_0p1m','FLUX__LE':'latent_heat_flux','MET__Precip':'precipitation_label'}
    by_id=feature_frame.set_index('sample_id')
    for v,driver_id in mapping.items():
        track='unknown_qc_exploration' if v in unknown else 'original_qc_view'
        for _,old in r1[r1['variable_id'].eq(v)].iterrows():
            q=metadata_frame[metadata_frame['quality_track'].eq(track)&metadata_frame['year'].eq(old['year'])&metadata_frame['day_offset'].eq(0)&metadata_frame['shift_hours'].eq(0)&metadata_frame['window_hours'].eq(old['window_hours'])&metadata_frame['anchor_id'].eq(old['anchor_id'])]
            if q.empty:continue  # Historical usgs anchor intentionally de-duplicated.
            assert len(q)==1
            actual=float(by_id.loc[q.iloc[0]['sample_id'],driver_id+'__median']);expected=float(old['median'])
            ok=(np.isnan(actual) and np.isnan(expected)) or bool(np.isclose(actual,expected,rtol=1e-12,atol=1e-12))
            assert ok,(v,old['year'],old['window_hours'],actual,expected)
            comparison.append({'variable_id':v,'year':int(old['year']),'anchor_id':old['anchor_id'],'window_hours':int(old['window_hours']),'matches_saved_r1_median':True})
    assert all(d['driver_id'] not in strict.columns for d in definitions)
    for d in definitions:
        if d['availability_track']=='unknown_qc_exploration_only':assert np.isnan(hourly['original_qc_view'][d['driver_id']]).all()
    assert all(digest((ROOT/p).read_bytes())==value for p,value in before.items())
    # Mechanical cases test exactly the data behavior relied upon downstream.
    a,s,_,_=extract(np.array([1.,2.,np.nan,3.,4.,5.]),np.arange(6),['longest_increase_fraction','trend_per24h'])
    assert a['longest_increase_fraction']==2/6 and np.isnan(a['trend_per24h']) and s['max_gap_hours']==1
    a,_,_,_=extract(np.array([0.,1.,2.,np.nan,3.,4.]),np.arange(6),['positive_fraction','longest_positive_fraction'])
    assert a['positive_fraction']==4/5 and a['longest_positive_fraction']==2/6
    validation={'schema_version':'q1-r3-feature-build-validation-v1','passed':True,
        'sample_count':len(metadata_frame),'feature_count':len(contract),'driver_count':len(definitions),
        'historical_samples':int((~metadata_frame['is_target']).sum()),'target_samples':int(metadata_frame['is_target'].sum()),
        'quality_tracks':experiment['quality_tracks'],'known_qc_variable_count':len(known),'unknown_qc_variable_count':len(unknown),
        'all_63_variables_mapped':True,'sample_ids_unique':True,'derived_gradients_require_all_sources':True,
        'known_qc_values_identical_between_tracks':True,'unknown_drivers_empty_in_original_qc_track':True,
        'coverage_filter_applied':False,'feature_support_rows':len(support_frame),
        'nonfinite_features_preserved_as_null':True,'all_float_feature_columns':True,
        'source_inputs_unchanged':True,'input_sha256':before,
        'anchor_shift_checks':shifts,'saved_r1_median_checks':comparison,
        'mechanical_checks':['missing breaks growth','growth counted in adjacent hour increments','trend requires at least 6 valid labels','precip positive fraction denominator is valid labels','positive-chain denominator is nominal labels'],
        'hourly_export_rows':len(export_frame),'hourly_export_first_utc':export_frame['time_utc'].min().isoformat(),
        'hourly_export_last_utc':export_frame['time_utc'].max().isoformat(),
        'rankings_or_event_labels_created':False}
    emit(R3/'results/feature_build_validation.json',json_bytes(validation))

    paths_roles=[('config/features.json','frozen_driver_definitions'),('scripts/build_features.py','offline_feature_builder'),
        ('results/feature_contract.csv','feature_definitions'),('results/variable_family_map.csv','all_input_variables_selection_and_exclusion'),
        ('results/features.parquet','wide_features_by_sample'),('results/sample_metadata.csv','time_support_process_and_anchor_metadata'),
        ('results/feature_support.csv','driver_validity_coverage_and_gap_counts'),('results/feature_extrema.csv','diagnostic_driver_extrema'),
        ('results/feature_build_validation.json','executed_feature_checks'),('exports/hourly_drivers.parquet','2026_regional_hourly_drivers')]
    bundle={'bundle_version':'q1-r3-feature-v1','producer_question':'q1','input_version':configuration['input_version'],
        'evaluation_stratum':'local_observational','event_id':experiment['event_id'],'physical_phase':'background',
        'data_role':'exploration','time_utc':None,'time_uncertainty':None,'available_time':None,
        'forecast_reference_time':None,'issue_time':None,'valid_time':None,
        'space_object':{'id':'Gyirong_regional_background','crs':None,'longitude':85.29,'latitude':28.86,'elevation_m':4140,'coordinate_datum_status':'unknown; metadata provides coordinates but no datum or positional error','status':'metadata assertion; source-area representativeness unverified'},
        'model_id':'not_applicable_feature_extraction','mechanism_id':experiment['mechanism_id'],
        'experiment_id':experiment['experiment_id'],'scenario_id':experiment['scenario_id'],
        'geometry_version':experiment['geometry_version'],'parameter_version':experiment['parameter_version'],
        'variable_semantics':{'driver_configuration':'track_b/research/q1/round3/config/features.json','timestamp_integration_interval':None,
            'quality_view':'original_qc_view plus separate unknown_qc_exploration; original 37 QC columns remain QC0 in both'},
        'files':[{'path':str((R3/p).relative_to(ROOT)),'bytes':(R3/p).stat().st_size,'sha256':digest((R3/p).read_bytes()),'role':role} for p,role in paths_roles],
        'limitations':['Hourly labels do not prove averaging or accumulation intervals',
            'available_time unknown: cannot establish historical operational eligibility',
            'Regional station drivers do not constitute measured source-area forcing',
            'No precipitation accumulation or energy integral was constructed',
            'No coverage cutoff in this bundle; downstream applies preregistered 0.75/0.50/0.90 thresholds',
            'Background windows/weather blocks are not independent disaster labels',
            'Feature extraction does not select a final scientific model or factor ranking',
            'Existing v1 bytes are immutable; changed outputs require a new bundle version and paths']}
    emit(R3/'exports/feature_bundle.json',json_bytes(bundle))
    bundle_hash=digest((R3/'exports/feature_bundle.json').read_bytes())
    text=f'''# Q1 第三轮早交：区域站特征 v1

本接口已实际提取并通过检查；尚未进行因素排序。只交主参谋核验后分发。

- bundle：`exports/feature_bundle.json`，SHA-256 `{bundle_hash}`。
- 共同基线：`{binding['common_baseline_commit']}`；冻结清单 SHA-256 `{binding['manifest_sha256']}`。
- {len(metadata_frame)}个样本（背景{validation['historical_samples']}、目标{validation['target_samples']}），{len(definitions)}驱动、{len(contract)}排名描述量，完整63原变量选择／排除表。
- `results/features.parquet`为`sample_id`加浮点feature_id列；元数据、覆盖支持另表，以sample_id连接。feature_id=`driver_id__statistic`，模型须先按每驱动coverage筛选。
- 每个quality_track有2021—2025×61日×3锚点小时偏移×3窗口背景，以及2026两参考×3偏移×3窗口目标。背景去重为problem_1030；分钟参考相同样本不得多投票。
- 24/72/168h的support_start/end为左闭右开请求区间，实际标签由first/last_hour_index精确确定。process_id是季节首日开始7日历日块代理，不是真实天气事件。
- 原QC轨仅37个原QC0变量；扩展轨只添加原本无QC变量，37列仍QC0。派生量逐小时取原量有效交集，不填补。unknown不升级质量。
- 构建器只要求分布／持续性>=2有效标签、趋势>=6；不套75%阈值。增长持续按正相邻小时增量数/名义窗标签数；缺口打断。降水仅标签统计，未做累计。
- `exports/hourly_drivers.parquet`按quality_track长表，UTC时间与24个驱动，2026-07-01 00:00至2026-08-26 11:30（UTC+8）内实际整点标签，共{len(export_frame)}行。时效未知，不代表历史实时可获得。
- 离线命令：`track_b/.venv/bin/python track_b/research/q1/round3/scripts/build_features.py`。再次运行必须产生逐字节相同产物；v1有变化即拒写，须新版本。
- 实际检查：5526唯一样本、24/72/168标签数、±1h支持集合、37QC列跨轨相同、unknown主轨全空、63变量映射、R1固定median对照、缺口持续和趋势机械用例、公共输入哈希不变。详见`results/feature_build_validation.json`。

空间、时区等价、小时起止／中心、FLUX处理及真实业务时效仍未核实。因素族只是区域观测候选，不是源区触发证明；论文最终科学采用待队员审视。v1清单不包含自身，所有文件按真实bytes/SHA-256列出。
'''
    emit(R3/'INTERFACE_HANDOFF.md',text.encode())
    print(json.dumps({'passed':True,'samples':len(metadata_frame),'drivers':len(definitions),'features':len(contract),'bundle_sha256':bundle_hash},ensure_ascii=False))


if __name__=='__main__':
    main()
