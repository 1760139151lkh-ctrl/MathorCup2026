#!/usr/bin/env python3
"""Q3 label/time audit, strict availability gate and synthetic metric checks.

AI assistance: OpenAI Codex, 2026-10-24. No hazard model is fitted. Original,
shared and other-question files are read-only. CSVs are machine audit tables.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

Q = Path(__file__).resolve().parents[1]
ROOT = Q.parents[2]
RESULTS = Q / 'results'
EXTERNAL = ROOT / 'track_b/data/external/event_remote'
RAW = EXTERNAL / 'runs/20261024T034202Z/raw'
BASELINE = '1d64f91fe057075df7c9199b5c17c68839bc6153'
READ_INPUTS = set()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    READ_INPUTS.add(path)
    return json.loads(path.read_text(encoding='utf-8'))


def save(name, data):
    path = RESULTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def stamp(value):
    if value is None:
        return None
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Naive time is not allowed in the replay gate')
    return result.astimezone(timezone.utc)


def encoded(value):
    if value is None or isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def table(name, records):
    path = RESULTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in records for key in row))
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in records:
            writer.writerow({key: encoded(row.get(key)) for key in fields})
    with path.open(encoding='utf-8', newline='') as stream:
        reread = list(csv.DictReader(stream))
    if len(reread) != len(records):
        raise ValueError(f'CSV readback row mismatch: {name}')
    return len(reread)


def common():
    manifest = ROOT / 'track_b/audit/stage4/baseline_manifest.json'
    READ_INPUTS.add(manifest)
    return {'input_version': {'baseline_commit': BASELINE, 'manifest_sha256': digest(manifest)},
            'event_id': None, 'physical_phase': None, 'time_utc': None,
            'time_uncertainty': None, 'space_object': None, 'variable_semantics': None,
            'forecast_reference_time': None, 'issue_time': None, 'valid_time': None,
            'available_time': None, 'data_role': 'exploration', 'evidence_status': 'local_fact'}


def source_check():
    ledger = load(EXTERNAL / 'event_evidence_ledger.json')
    candidates = load(EXTERNAL / 'historical_candidates.json')
    official = load(RAW / 'usgs_event.json')
    READ_INPUTS.add(RAW / 'usgs_origin_quakeml.xml')
    tree = ET.parse(RAW / 'usgs_origin_quakeml.xml')
    ns = {'b': 'http://quakeml.org/xmlns/bed/1.2'}
    preferred = tree.find('.//b:preferredOriginID', ns).text
    origin = next(x for x in tree.findall('.//b:origin', ns) if x.attrib['publicID'] == preferred)
    time = origin.find('b:time/b:value', ns).text
    terr = origin.find('b:time/b:uncertainty', ns).text
    confidence = origin.find('b:time/b:confidenceLevel', ns).text
    horizontal = origin.find('b:originUncertainty/b:horizontalUncertainty', ns).text
    assert stamp(time) == stamp('2026-08-26T02:52:10Z')
    assert float(terr) == 7.9 and float(confidence) == 90 and float(horizontal) == 13390
    assert official['properties']['type'] == 'landslide'
    assert stamp(datetime.fromtimestamp(official['properties']['time'] / 1000, timezone.utc).isoformat()) == stamp(time)
    # Compare each saved catalogue feature to every carried source field. This
    # confirms transcription only, never occurrence time semantics or truth.
    raw_features = {}
    for geometry in ['Points', 'Polygons']:
        doc = load(RAW / f'nasa_COOLR_Reports_{geometry}.json')
        for feature in doc['features']:
            raw_features[(f'NASA_COOLR_Reports_{geometry}', feature['attributes']['objectid'])] = feature
    for row in candidates['records']:
        feature = raw_features[(row['catalogue'], row['objectid'])]
        for key, value in feature['attributes'].items():
            mapped = key if key in row else key.lower()
            if mapped not in row or row[mapped] != value:
                raise ValueError(f'NASA carried attribute mismatch: {row["event_id"]}/{key}')
        assert feature['geometry'] == row['geometry']
    return ledger, candidates, {'usgs_origin_time_utc': stamp(time).isoformat(),
        'usgs_time_uncertainty_seconds': float(terr), 'usgs_confidence_level_percent': float(confidence),
        'usgs_horizontal_uncertainty_m': float(horizontal), 'nasa_rows_compared_to_raw': len(candidates['records'])}


def paper_reading_audit():
    from pypdf import PdfReader
    path = EXTERNAL / 'jms_2026_uncorrected_proof.pdf'
    READ_INPUTS.add(path)
    reader = PdfReader(path)
    checks = {}
    for page, tokens in {9: ['10:51:50', '10:52:20'], 10: ['10:54:00'], 11: ['10:59:50'], 31: ['reasonable request']}.items():
        text = reader.pages[page - 1].extract_text()
        checks[str(page)] = {token: token in text for token in tokens}
    assert all(value for page in checks.values() for value in page.values())
    supplemental = load(EXTERNAL / 'supplemental_original_source.json')
    save('source_reading.json', {'source_path': str(path.relative_to(ROOT)), 'sha256': digest(path), 'pages': len(reader.pages),
        'reading_scope': 'Internal read-only reviewer read full extracted text on PDF pages 5-11 and 31; executor programmatically scanned full extracted text on pages 9-11 and 31 for these tokens. No new rendering or waveform interpretation.',
        'text_checks': checks, 'proof_state': 'Saved uncorrected proof; no raw waveform or arrival report obtained.',
        'yin_reading_scope': supplemental['direct_reading_scope'] + ' ' + supplemental['browser_search_reading_scope'],
        'source_timing_note': 'Post-event label evidence may support retrospective evaluation after label review; it cannot enter the pre-event predictor information set.'})


def review_labels(ledger, candidates):
    rows = []
    for record in ledger['records']:
        row = common()
        row.update({'record_id': record['evidence_id'], 'record_kind': 'case_evidence',
            'event_id': record['event_id'], 'independent_event_group': record['independent_event_group'],
            'physical_phase': record['physical_stage'], 'time_utc': record.get('event_time_utc'),
            'time_uncertainty': {'seconds': record.get('time_uncertainty_seconds', record.get('origin_time_uncertainty_seconds')),
                                  'confidence_level_percent': record.get('origin_time_confidence_level_percent'),
                                  'source_qualification': record['label_role']},
            'space_object': {'coordinate_precision': record.get('coordinate_precision'),
                             'coordinates_lon_lat_depth_km': record.get('coordinates_lon_lat_depth_km'), 'crs': 'EPSG:4326' if record.get('coordinates_lon_lat_depth_km') else None},
            'source_url': record.get('source_url'), 'source_path': record.get('source_path'),
            'source_kind': record['source_kind'], 'source_time_text': record.get('source_time_text'),
            'source_publication_time': record.get('source_publication_epoch_utc', record.get('source_publication_time')),
            'retrieved_at_utc': record.get('retrieved_at_utc'), 'source_product_updated_time': record.get('source_product_updated_time_utc'),
            'post_event_label_allowed_in_principle': True,
            'approved_training_label': False, 'approved_independent_validation_label': False,
            'review_status': 'pending_phase_source_uncertainty_and_human_acceptance',
            'review_reason': record['label_role'], 'evidence_status': 'external_source' if record.get('source_url') else 'local_fact',
            'reading_scope': 'saved source and ledger; JMS text scope recorded in source_reading.json; Yin fulltext not verified'})
        rows.append(row)
    by_url, exact = defaultdict(list), defaultdict(list)
    for record in candidates['records']:
        by_url[record.get('source_link')].append(record['event_id'])
        key = tuple(str(record.get(k)) for k in ['source_link', 'event_title', 'event_description', 'event_date', 'latitude', 'longitude', 'submitted_date'])
        exact[key].append(record['event_id'])
    exact_groups = [ids for ids in exact.values() if len(ids) > 1]
    for record in candidates['records']:
        row = common()
        event_id = record['event_id']
        duplicate = next((ids for ids in exact_groups if event_id in ids), [])
        epoch = stamp(record['catalogue_event_date_epoch_as_utc'])
        source_time = record.get('event_time')
        hhmm = bool(source_time and re.fullmatch(r'\d{2}:\d{2}', source_time))
        time_conflict = hhmm and epoch.strftime('%H:%M') != source_time
        source_missing = record.get('source_link') in [None, '', '<Null>', 'unknown']
        reasons = ['original_source_not_reviewed', 'physical_phase_and_mechanism_not_verified', 'timezone_not_verified', 'temporal_precision_not_verified', 'independence_not_verified']
        if duplicate:
            reasons.append('exact_record_duplicate_candidate')
        if time_conflict:
            reasons.append('hhmm_and_encoded_epoch_clock_differ')
        if record.get('event_date') == record.get('submitted_date'):
            reasons.append('event_date_equals_submission_epoch')
        if source_missing:
            reasons.append('missing_original_source_link')
        row.update({'record_id': f'{record["catalogue"]}:{record["objectid"]}', 'record_kind': 'historical_candidate',
            'event_id': f'NASA_catalogue:{event_id}', 'independent_event_group': None,
            'catalogue_event_id': event_id, 'catalogue_objectid': record['objectid'], 'catalogue': record['catalogue'],
            'physical_phase': None, 'time_utc': None,
            'time_uncertainty': {'source_event_time': source_time, 'timezone_verified': False, 'precision_verified': False},
            'catalogue_event_date_epoch_as_utc': record['catalogue_event_date_epoch_as_utc'],
            'catalogue_event_date_epoch_ms': record['event_date'], 'source_event_time_text': source_time,
            'source_title': record.get('event_title'), 'source_description': record.get('event_description'),
            'space_object': {'catalogue_geometry': record.get('geometry'), 'catalogue_crs': 'EPSG:4326', 'location_accuracy_text': record.get('location_accuracy'), 'actual_source_region_verified': False},
            'source_url': record.get('source_link'), 'source_name': record.get('source_name'),
            'mechanism_category': record.get('landslide_category'), 'mechanism_trigger': record.get('landslide_trigger'),
            'submitted_time_utc': record.get('submitted_date_epoch_as_utc'),
            'updated_time_utc': record.get('last_edited_date_epoch_as_utc'),
            'exact_duplicate_candidate_ids': duplicate, 'same_source_report_ids': by_url[record.get('source_link')],
            'clock_fields_differ': bool(time_conflict), 'source_link_missing': source_missing,
            'within_hourly_station_axis_by_catalogue_date': stamp('2021-01-01T00:00:00Z') <= epoch <= stamp('2026-12-31T23:59:59Z'),
            'approved_training_label': False, 'approved_independent_validation_label': False,
            'review_status': 'candidate_not_accepted', 'review_reason': reasons,
            'evidence_status': 'external_source', 'reading_scope': 'saved NASA catalogue attributes and geometry compared to raw; underlying source not reviewed'})
        rows.append(row)
    table('label_review.csv', rows)
    historical = [r for r in rows if r['record_kind'] == 'historical_candidate']
    stats = {'case_evidence_rows': len(ledger['records']),
        'case_independent_event_groups': len({r['independent_event_group'] for r in ledger['records']}),
        'historical_candidate_rows': len(historical), 'accepted_training_events': 0, 'accepted_independent_validation_events': 0,
        'candidate_mechanism_category_counts': dict(Counter(r['mechanism_category'] for r in historical)),
        'candidate_trigger_counts': dict(Counter(r['mechanism_trigger'] for r in historical)),
        'source_time_counts': {'null': sum(r['source_event_time_text'] is None for r in historical), 'unknown': sum(r['source_event_time_text'] == 'unknown' for r in historical), 'hhmm': sum(bool(r['source_event_time_text'] and re.fullmatch(r'\d{2}:\d{2}', r['source_event_time_text'])) for r in historical)},
        'exact_duplicate_candidate_groups': exact_groups,
        'same_source_multiple_record_groups': [ids for url, ids in by_url.items() if len(ids) > 1 and url not in [None, '', '<Null>', 'unknown']],
        'clock_conflict_catalogue_ids': [r['catalogue_event_id'] for r in historical if r['clock_fields_differ']],
        'within_hourly_axis_candidate_ids': [r['catalogue_event_id'] for r in historical if r['within_hourly_station_axis_by_catalogue_date']],
        'all_timezones_unverified': all(r.get('event_time_zone_verified') is None for r in candidates['records']),
        'interpretation': 'Zero accepted is an audit status, not evidence that no historical events occurred. Catalogue epoch is retained separately and is not approved occurrence UTC.'}
    save('label_summary.json', stats)
    return stats


def forecast_audit():
    import eccodes
    import numpy as np
    import xarray as xr
    summary = load(ROOT / 'track_b/data/processed/forecast_sample/summary.json')
    reference = stamp(summary['forecast_reference_time_utc'])
    nc = ROOT / summary['netcdf_file']
    READ_INPUTS.add(nc)
    rows, checks = [], []
    with xr.open_dataset(nc, engine='h5netcdf') as dataset:
        assert stamp(dataset.attrs['forecast_reference_time_utc']) == reference
        assert dataset.sizes['latitude'] == 5 and dataset.sizes['longitude'] == 5
        for saved in summary['messages']:
            path = ROOT / 'track_b/data/external/forecast_sample' / saved['raw_file']
            READ_INPUTS.add(path)
            provenance = load(path.with_suffix('.http.json'))
            assert digest(path) == saved['sha256'] == provenance['sha256']
            with path.open('rb') as stream:
                message = eccodes.codes_grib_new_from_file(stream)
                try:
                    keys = ['dataDate', 'dataTime', 'validityDate', 'validityTime', 'stepType', 'startStep', 'endStep', 'stepUnits', 'units', 'shortName']
                    fields = {key: eccodes.codes_get(message, key) for key in keys}
                finally:
                    eccodes.codes_release(message)
            assert all(fields[k] == saved['grib'][k] for k in keys)
            assert fields['stepUnits'] == 1
            ref = datetime.strptime(f'{fields["dataDate"]}{fields["dataTime"]:04}', '%Y%m%d%H%M').replace(tzinfo=timezone.utc)
            valid = datetime.strptime(f'{fields["validityDate"]}{fields["validityTime"]:04}', '%Y%m%d%H%M').replace(tzinfo=timezone.utc)
            assert ref == reference and valid == ref + timedelta(hours=fields['endStep'])
            variable = dataset[saved['label']]
            assert variable.attrs['units'] == fields['units']
            assert variable.attrs['start_step_hours'] == fields['startStep'] and variable.attrs['end_step_hours'] == fields['endStep']
            assert np.isfinite(variable.values).all()
            row = common()
            row.update({'record_id': saved['label'], 'event_id': 'B20260826_Chhochen',
                'physical_phase': 'environmental_forecast_background', 'input_kind': 'forecast',
                'time_utc': valid.isoformat(), 'forecast_reference_time': ref.isoformat(), 'valid_time': valid.isoformat(),
                'space_object': {'bbox_west_south_east_north': summary['bbox_west_south_east_north'], 'crs': 'EPSG:4326', 'grid_degrees': 0.25, 'aoi_shape': [5, 5], 'source_region_representativeness_verified': False},
                'variable_semantics': {'units': fields['units'], 'step_type': fields['stepType'], 'start_step_hours': fields['startStep'], 'end_step_hours': fields['endStep'], 'accumulation_start_utc': saved.get('accumulation_start_utc'), 'accumulation_end_utc': saved.get('accumulation_end_utc'), 'qc': 'finite_value_I/O_check_only'},
                'source_path': str(path.relative_to(ROOT)), 'source_sha256': digest(path), 'source_url': provenance['url'],
                'retrieved_at_utc': provenance['fetched_at_utc'], 'available_time': None, 'available_time_verified': False,
                'future_valid_time_allowed_for_forecast': True, 'prediction_feature_role': 'candidate_unapproved',
                'review_reason': 'Historical operational first availability not proven; valid time is not publication time'})
            rows.append(row)
            checks.append({'field': saved['label'], 'passed': True, 'metadata_keys_compared': keys, 'aoi_cells': int(variable.size)})
    table('availability_review.csv', rows)
    save('forecast_metadata_checks.json', {'passed': all(x['passed'] for x in checks), 'checks': checks,
        'actual_available_time': None, 'reference_time_utc': reference.isoformat(),
        'valid_time_utc': summary['valid_time_utc'], 'precipitation_intervals_overlap': True,
        'precipitation_interval_policy': 'Keep 0-9h and 6-9h distinct. Do not sum overlapping forecasts or treat accumulated amount as instantaneous intensity.'})
    return rows


def availability_gate(record, issue_time):
    issue = stamp(issue_time)
    if record.get('prediction_feature_role') == 'retrospective_label_only':
        return 'exclude', False, 'retrospective_reference_not_a_prediction_feature'
    created = stamp(record.get('known_version_created_time'))
    if created and created > issue:
        return 'exclude', False, 'this_product_version_created_after_issue_time'
    reference = stamp(record.get('forecast_reference_time'))
    if record.get('input_kind') == 'forecast' and reference and reference > issue:
        return 'exclude', False, 'forecast_not_initialized_by_issue_time'
    observation_end = stamp(record.get('observation_end_time'))
    if record.get('input_kind') == 'observation' and observation_end and observation_end > issue:
        return 'exclude', False, 'observation_or_accumulation_not_complete_at_issue_time'
    available = stamp(record.get('available_time'))
    if record.get('input_kind') == 'forecast' and reference and available and available < reference:
        return 'exclude', False, 'availability_precedes_forecast_initialization_inconsistent_metadata'
    if available is None:
        return 'unknown', False, 'actual_available_time_not_verified'
    if available > issue:
        return 'exclude', False, 'information_arrives_after_issue_time'
    if record.get('input_kind') == 'observation' and observation_end is None:
        return 'unknown', False, 'observation_interval_end_not_verified'
    return 'include', True, 'time_gate_only_other_quality_and_representativeness_checks_remain'


def replay(rows, config):
    records = list(rows)
    for name, kind, role in [('hourly_station_source', 'observation', 'candidate_unapproved'), ('county_daily_temperature_source', 'observation', 'candidate_unapproved'), ('worldcover_2021_background', 'background', 'candidate_unapproved'), ('jms_reconstruction', 'label', 'retrospective_label_only'), ('usgs_reviewed_origin', 'label', 'retrospective_label_only')]:
        row = common()
        row.update({'record_id': name, 'input_kind': kind, 'prediction_feature_role': role,
                    'event_id': config['event_id'], 'available_time': None})
        records.append(row)
    actual, scenario = [], []
    for issue in config['issue_times_utc']:
        for record in records:
            status, eligible, reason = availability_gate(record, issue)
            row = dict(record, issue_time=issue, gate_status=status, eligible=eligible, gate_reason=reason,
                       gate_scope='availability_only; does_not_approve_scientific_feature')
            actual.append(row)
        for delay in config['forecast_delay_scenarios_hours']:
            for record in rows:
                available = stamp(record['forecast_reference_time']) + timedelta(hours=delay)
                candidate = dict(record, available_time=available.isoformat())
                status, eligible, reason = availability_gate(candidate, issue)
                scenario.append(dict(candidate, issue_time=issue, data_role='scenario', delay_hours_assumed=delay,
                    gate_status=status, eligible=eligible, gate_reason=reason, actual_availability_verified=False,
                    assumption_status='explicit_unverified_delay_not_a_conservative_bound'))
    table('replay_gate.csv', actual)
    table('replay_delay_scenarios.csv', scenario)
    result = {'actual_gate_rows': len(actual), 'actual_gate_counts': dict(Counter(row['gate_status'] for row in actual)),
              'actual_eligible_rows': sum(row['eligible'] for row in actual), 'delay_scenario_rows': len(scenario),
              'scenario_gate_counts': dict(Counter(row['gate_status'] for row in scenario)),
              'real_coverage': None, 'accepted_independent_validation_events': 0,
              'scope': 'Input eligibility demonstration only. No warning, probability or interval was generated.'}
    save('replay_summary.json', result)
    return result


def event_evaluation(records, alpha=0.05):
    seen, result = set(), []
    for row in records:
        if row['event_id'] in seen:
            raise ValueError('Duplicate independent-event group in event evaluation')
        seen.add(row['event_id'])
        issue, true = stamp(row['issue_time']), stamp(row.get('truth'))
        lower, upper = stamp(row.get('lower')), stamp(row.get('upper'))
        has_interval = lower is not None and upper is not None
        if has_interval and lower > upper:
            raise ValueError('Reversed prediction interval')
        assessable = true is not None
        issued = has_interval and bool(row.get('warning_issued', True))
        lead = (true - issue).total_seconds() if assessable and issued else None
        hit = bool(lower <= true <= upper) if assessable and issued else None
        score = None
        if assessable and issued:
            score = (upper - lower).total_seconds() + 2 / alpha * max((lower - true).total_seconds(), 0) + 2 / alpha * max((true - upper).total_seconds(), 0)
        result.append({'event_id': row['event_id'], 'assessable': assessable, 'issued': issued, 'hit': hit,
                       'lead_seconds': lead, 'late': lead is not None and lead < 0,
                       'effective_coverage_hit': bool(hit and lead is not None and lead > 0), 'interval_score_seconds': score})
    assessed = [x for x in result if x['assessable']]
    issued = [x for x in assessed if x['issued']]
    return {'event_count': len(records), 'assessable_events': len(assessed), 'unassessable_events': len(records) - len(assessed),
            'issued_assessable_events': len(issued), 'missed_events': sum(not x['issued'] for x in assessed),
            'late_events': sum(x['late'] for x in assessed),
            'zero_lead_events': sum(x['lead_seconds'] == 0 for x in issued),
            'conditional_interval_coverage': sum(bool(x['hit']) for x in issued) / len(issued) if issued else None,
            'effective_event_coverage': sum(x['effective_coverage_hit'] for x in assessed) / len(assessed) if assessed else None,
            'rows': result}


def interval_truth_bounds(lower, upper, truth_lower, truth_upper):
    lo, hi, a, b = map(stamp, [lower, upper, truth_lower, truth_upper])
    if lo > hi or a > b:
        raise ValueError('Reversed prediction or truth interval')
    return {'certain_covered': lo <= a <= b <= hi, 'possible_covered': max(lo, a) <= min(hi, b)}


def synthetic_checks(alpha):
    if alpha != 0.05:
        raise ValueError('This preregistered first-round hand check fixes alpha=0.05; revise the protocol and expected values explicitly before changing it')
    checks = []
    def check(name, condition, observed=None):
        checks.append({'name': name, 'passed': bool(condition), 'observed': observed, 'data_role': 'scenario', 'synthetic': True})
    t = '2026-08-26T02:30:00Z'
    s, e, _ = availability_gate({'input_kind': 'forecast', 'available_time': t, 'valid_time': '2026-08-26T03:00:00Z'}, t)
    check('availability_equal_boundary_and_future_forecast_valid_time', s == 'include' and e)
    check('late_available_time_excluded', availability_gate({'available_time': '2026-08-26T02:30:01Z'}, t)[0] == 'exclude')
    check('unknown_available_time_never_eligible', availability_gate({'available_time': None}, t)[:2] == ('unknown', False))
    check('future_forecast_reference_excluded_even_with_early_availability', availability_gate({'input_kind': 'forecast', 'forecast_reference_time': '2026-08-26T03:00:00Z', 'available_time': '2026-08-26T02:00:00Z'}, t)[0] == 'exclude')
    check('future_forecast_reference_excluded_with_unknown_availability', availability_gate({'input_kind': 'forecast', 'forecast_reference_time': '2026-08-26T03:00:00Z', 'available_time': None}, t)[0] == 'exclude')
    check('availability_before_forecast_reference_is_inconsistent', availability_gate({'input_kind': 'forecast', 'forecast_reference_time': '2026-08-26T02:00:00Z', 'available_time': '2026-08-26T01:59:00Z'}, t)[0] == 'exclude')
    check('future_observation_excluded', availability_gate({'input_kind': 'observation', 'observation_end_time': '2026-08-26T03:00:00Z', 'available_time': t}, t)[0] == 'exclude')
    check('naive_timestamp_rejected', _raises(lambda: stamp('2026-08-26T02:30:00'), ValueError))
    check('timezone_conversion', stamp('2026-08-26T10:30:00+08:00') == stamp(t))
    cases = [
        {'event_id': 'synthetic_equal', 'issue_time': '2026-08-26T02:00:00Z', 'truth': t, 'lower': t, 'upper': '2026-08-26T02:31:00Z'},
        {'event_id': 'synthetic_late', 'issue_time': '2026-08-26T02:31:00Z', 'truth': t, 'lower': '2026-08-26T02:29:00Z', 'upper': '2026-08-26T02:31:00Z'},
        {'event_id': 'synthetic_missed', 'issue_time': '2026-08-26T02:00:00Z', 'truth': t, 'warning_issued': False},
        {'event_id': 'synthetic_missing_truth', 'issue_time': '2026-08-26T02:00:00Z', 'truth': None, 'lower': t, 'upper': t}]
    metrics = event_evaluation(cases, alpha=alpha)
    check('closed_interval_boundary_hit', metrics['rows'][0]['hit'] is True)
    check('negative_lead_preserved', metrics['rows'][1]['lead_seconds'] == -60)
    check('missed_event_kept_in_effective_denominator', metrics['assessable_events'] == 3 and metrics['missed_events'] == 1 and metrics['effective_event_coverage'] == 1 / 3, metrics)
    check('conditional_coverage_separated_from_effective', metrics['conditional_interval_coverage'] == 1 and metrics['effective_event_coverage'] == 1 / 3)
    check('missing_truth_not_scored', metrics['unassessable_events'] == 1 and metrics['rows'][3]['interval_score_seconds'] is None)
    check('zero_denominator_returns_null', event_evaluation([])['effective_event_coverage'] is None)
    zero = event_evaluation([dict(cases[0], issue_time=t)], alpha=alpha)
    check('zero_lead_not_advance_warning_and_counted', zero['effective_event_coverage'] == 0 and zero['zero_lead_events'] == 1)
    check('duplicate_event_rejected', _raises(lambda: event_evaluation([cases[0], cases[0]]), ValueError))
    check('reversed_interval_rejected', _raises(lambda: event_evaluation([dict(cases[0], lower='2026-08-26T03:00:00Z')]), ValueError))
    bounds = interval_truth_bounds('2026-08-26T02:30:00Z', '2026-08-26T02:31:00Z', '2026-08-26T02:29:00Z', '2026-08-26T02:30:30Z')
    check('ambiguous_truth_overlap_not_certain_coverage', bounds == {'certain_covered': False, 'possible_covered': True}, bounds)
    score_case = dict(cases[0], lower='2026-08-26T02:31:00Z', upper='2026-08-26T02:32:00Z')
    check('interval_score_width_and_penalty_seconds', event_evaluation([score_case], alpha=alpha)['rows'][0]['interval_score_seconds'] == 2460)
    result = {'passed': all(x['passed'] for x in checks), 'alpha_used': alpha, 'synthetic_test_count': len(checks), 'checks': checks,
              'synthetic_event_examples': len(cases), 'real_validation_events_added': 0,
              'scope': 'Hand-calculated boundary examples validate mechanics only, not forecast performance.'}
    save('synthetic_checks.json', result)
    if not result['passed']:
        raise ValueError('Synthetic mechanics checks failed')
    return result


def _raises(function, kind):
    try:
        function()
    except kind:
        return True
    return False


def source_snapshots():
    sources = [
        ('ncep_gfs_inventory.html', 'https://www.nco.ncep.noaa.gov/pmb/products/gfs/nomads/', 'GFS product table read; cycles/naming only, no historical first-availability proof'),
        ('ncep_current_production.html', 'https://www.nco.ncep.noaa.gov/pmb/nwprod/prodstat_new/prdst_main.html', 'Current status page read; not an archive for the event date'),
        ('conformal_2107_07511v6.html', 'https://arxiv.org/html/2107.07511v6', 'Read sections 1, 3.2-3.3, 4.6, 5.3 and appendix coverage theorem passages; not entire paper'),
        ('gneiting_raftery_2007.pdf', 'https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf', 'Read section 6.2, equation 43; not whole-paper independent derivation')]
    target = Q / 'sources'
    target.mkdir(exist_ok=True)
    register = []
    for filename, url, scope in sources:
        row = {'url': url, 'reading_scope': scope, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'reading_medium': 'official/author primary source, web tool plus saved snapshot', 'source_kind': 'primary', 'sha256': None}
        path = target / filename
        try:
            if path.exists():
                row['status'] = 'cached_saved_snapshot'
            else:
                with urlopen(Request(url, headers={'User-Agent': 'MathorCup-Q3-evidence-audit/1.0'}), timeout=30) as response:
                    payload = response.read(3 * 1024 * 1024 + 1)
                    if response.status != 200 or len(payload) > 3 * 1024 * 1024:
                        raise ValueError('Unexpected response or bounded snapshot size exceeded')
                path.write_bytes(payload)
                row['status'] = 'saved_snapshot'
            row.update({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': digest(path)})
        except Exception as exc:
            row.update({'status': 'snapshot_unavailable', 'error': f'{type(exc).__name__}: {exc}', 'web_reading_retained': True})
        register.append(row)
    save('source_register.json', register)
    return register


def finalize_manifest():
    excluded = {'output_manifest.json', 'workspace_verification.json', 'workspace_binding.json', 'environment_setup.log', 'TASK.md'}
    files = []
    for path in sorted(Q.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc' or path.name in excluded:
            continue
        files.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': digest(path)})
    for entry in files:
        path = ROOT / entry['path']
        if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError(f'Output changed during final manifest verification: {entry["path"]}')
    manifest = {'schema_version': 2, 'scope': 'Q3 authored protocols/scripts/config, results, source snapshots, figure and handoff; each file size and hash independently re-read before saving.',
                'excluded_names': sorted(excluded), 'exclusion_reason': 'Self-reference, mutable runtime/dispatch logs, and unchanged inherited TASK. Runtime readiness is copied as results/workspace_readiness_at_run.json.',
                'file_count': len(files), 'files': files, 'all_hashes_rechecked': True, 'verified_file_count': len(files)}
    save('output_manifest.json', manifest)
    print(json.dumps({'output_manifest_files': len(files), 'hash_recheck_passed': True, 'manifest_sha256': digest(RESULTS / 'output_manifest.json')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch-sources', action='store_true', help='Save at most four bounded primary-source snapshots; default is offline')
    parser.add_argument('--finalize-only', action='store_true', help='Rebuild and re-read all final deliverable hashes without rerunning experiments')
    args = parser.parse_args()
    binding = json.loads((Q / 'workspace_binding.json').read_text(encoding='utf-8'))
    if ROOT != Path(binding['execution_root']).resolve() or Path(sys.prefix).resolve() != ROOT / 'track_b/.venv':
        raise RuntimeError('Use this assigned worktree and its own isolated interpreter')
    readiness = json.loads((Q / 'workspace_verification.json').read_text(encoding='utf-8'))
    if not readiness['passed']:
        raise RuntimeError('Integrator workspace readiness is not passed')
    if args.finalize_only:
        finalize_manifest()
        return
    save('workspace_readiness_at_run.json', readiness)
    save('workspace_binding_at_run.json', binding)
    config = load(Q / 'config/replay.json')
    contract = load(ROOT / 'track_b/config/stage4_contract.json')
    if set(common()) != set(contract['shared_record_fields']):
        raise RuntimeError('Canonical shared record fields differ from the common contract')
    assert config['baseline_commit'] == BASELINE and not config['allow_model_fitting'] and not config['allow_real_coverage_claim']
    ledger, candidates, originals = source_check()
    paper_reading_audit()
    labels = review_labels(ledger, candidates)
    forecasts = forecast_audit()
    replay_result = replay(forecasts, config)
    mechanics = synthetic_checks(config['nominal_alpha_for_synthetic_formula_check'])
    if args.fetch_sources:
        source_snapshots()
    input_manifest = [{'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': digest(path)} for path in sorted(READ_INPUTS)]
    save('input_manifest.json', input_manifest)
    summary = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'question': 'q3', 'baseline_commit': BASELINE,
        'contract_version': 'stage4-r1-v1', 'original_source_checks': originals, 'labels': labels,
        'replay': replay_result, 'mechanics_passed': mechanics['passed'], 'synthetic_test_count': mechanics['synthetic_test_count'],
        'real_forecast_or_coverage_result': None, 'real_false_alarm_ratio': None, 'real_false_alarms_per_monitored_time': None,
        'real_false_positive_decision_rate': None, 'core_model_fitted': False,
        'scope': 'First-round evidence/method feasibility and input-gate mechanics; pending integrator and human scientific review.'}
    save('summary.json', summary)
    finalize_manifest()
    print(json.dumps({'accepted_independent_validation_events': 0, 'actual_gate_counts': replay_result['actual_gate_counts'], 'synthetic_checks': mechanics['synthetic_test_count'], 'passed': mechanics['passed'], 'summary': str((RESULTS / 'summary.json').relative_to(ROOT))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
