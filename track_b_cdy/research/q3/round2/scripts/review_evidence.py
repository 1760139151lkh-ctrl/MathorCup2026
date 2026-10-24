#!/usr/bin/env python3
"""Bounded Q3 round-2 evidence collection and offline review; no GRIB GET.

AI assistance: OpenAI Codex, 2026-10-24. Only this round2 directory is writable.
Default is offline. --collect fills missing small official snapshots; --finalize
rechecks final file hashes. No event is accepted as an independent label here.
"""
from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

R = Path(__file__).resolve().parents[1]
ROOT = R.parents[3]
S = R / 'sources'
O = R / 'results'
BASE = '76ee1532cb2acf36fb82c5f4749a4288507dfcc8'
FROZEN_SHA = 'c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d'
GFS = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20260825/18/atmos/gfs.t18z.pgrb2.0p25.f009'
API = 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000tc90&format=geojson'
INPUTS = set()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    INPUTS.add(path)
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    if not path.is_relative_to(R) or path.resolve() != path:
        raise ValueError('Output escapes assigned round2 directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Naive timestamps are not approved UTC')
    return dt.astimezone(timezone.utc)


def epoch(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def headers(record):
    return {k.lower(): v for k, v in record.get('response_headers', {}).items()}


def validate_record(record, url, name, method):
    if record.get('url') != url or record.get('method') != method:
        raise ValueError('Cached request URL or method differs from assigned source')
    if record.get('error') or not 200 <= record.get('http_status', 0) < 300:
        raise ValueError('Failed request retained as a log, not usable source evidence')
    if method == 'HEAD':
        if record.get('saved_path') or record.get('body_bytes_transferred', 0):
            raise ValueError('HEAD log unexpectedly contains a response body')
    else:
        expected = S / name
        if record.get('saved_path') != str(expected.relative_to(ROOT)) or expected.resolve() != expected:
            raise ValueError('Cached payload path differs from assigned snapshot')
        if sha(expected) != record.get('sha256') or expected.stat().st_size != record.get('bytes'):
            raise ValueError('Cached source bytes differ from request record')
    return record


def request(url, name, method='GET', limit=524288):
    allowed = {'earthquake.usgs.gov', 'www.usgs.gov', 'noaa-gfs-bdp-pds.s3.amazonaws.com', 'www.nco.ncep.noaa.gov', 'docs.aws.amazon.com', 'gdex.ucar.edu'}
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname not in allowed:
        raise ValueError('Unapproved source host')
    if urlsplit(url).path.endswith('.f009') and method != 'HEAD':
        raise ValueError('GRIB payload downloads prohibited in round2')
    legacy_logs = {'us7000tc90.geojson': 'us7000tc90_request.json', 'us7000tc90_origin_quakeml.xml': 'us7000tc90_origin_request.json'}
    meta_path = S / (name + '.json' if method == 'HEAD' else legacy_logs.get(name, name + '_request.json'))
    if meta_path.exists():
        return validate_record(json.loads(meta_path.read_text()), url, name, method)
    S.mkdir(parents=True, exist_ok=True)
    meta = {'url': url, 'method': method, 'requested_at_utc': datetime.now(timezone.utc).isoformat(), 'max_body_bytes': limit,
            'body_bytes_transferred': 0, 'grib_body_downloaded': False}
    try:
        try:
            response = urlopen(Request(url, method=method, headers={'User-Agent': 'MathorCup-Q3-bounded-evidence/1.0'}), timeout=30)
        except HTTPError as error:
            response = error
        with response:
            meta.update({'http_status': response.code, 'response_headers': dict(response.headers.items()), 'final_url': response.geturl()})
            if method != 'HEAD':
                size = response.headers.get('Content-Length')
                if size and int(size) > limit:
                    raise ValueError('Declared response exceeds bounded snapshot size; body not read')
                payload = response.read(limit + 1)
                meta['body_bytes_transferred'] = len(payload)
                if len(payload) > limit:
                    raise ValueError('Response exceeded snapshot bound')
                path = S / name
                path.write_bytes(payload)
                meta.update({'saved_path': str(path.relative_to(ROOT)), 'bytes': len(payload), 'sha256': sha(path)})
        meta['received_at_utc'] = datetime.now(timezone.utc).isoformat()
    except Exception as error:
        meta['error'] = f'{type(error).__name__}: {error}'
    save(meta_path, meta)
    return validate_record(meta, url, name, method)


def collect():
    # Preserve the first successful acquisition logs made during this round.
    request(API, 'us7000tc90.geojson', limit=2097152)
    event = json.loads((S / 'us7000tc90.geojson').read_text())
    origin = event['properties']['products']['origin'][0]
    request(origin['contents']['quakeml.xml']['url'], 'us7000tc90_origin_quakeml.xml')
    request(GFS, 'gfs_f009_head', method='HEAD')
    request(GFS + '.idx', 'gfs_f009_idx_head', method='HEAD')
    request(GFS + '.idx', 'gfs_f009_current.idx', limit=131072)
    request('https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.md', 'aws_headobject.md')
    request('https://www.nco.ncep.noaa.gov/pmb/nwprod/prodstat/', 'ncep_current_production.html')
    request('https://gdex.ucar.edu/datasets/d084001/filelist/20260825/', 'gdex_20260825_listing.html', limit=2097152)
    request('https://www.usgs.gov/programs/landslide-hazards/science/2026-nepal-debris-avalanche-and-flash-flood', 'usgs_special_page.html')


def source_log():
    event = json.loads((S / 'us7000tc90.geojson').read_text())
    expected_requests = {
        'us7000tc90_request.json': (API, 'us7000tc90.geojson', 'GET'),
        'us7000tc90_origin_request.json': (event['properties']['products']['origin'][0]['contents']['quakeml.xml']['url'], 'us7000tc90_origin_quakeml.xml', 'GET'),
        'gfs_f009_head.json': (GFS, 'gfs_f009_head', 'HEAD'),
        'gfs_f009_idx_head.json': (GFS + '.idx', 'gfs_f009_idx_head', 'HEAD'),
        'gfs_f009_current.idx_request.json': (GFS + '.idx', 'gfs_f009_current.idx', 'GET'),
        'aws_headobject.md_request.json': ('https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.md', 'aws_headobject.md', 'GET'),
        'ncep_current_production.html_request.json': ('https://www.nco.ncep.noaa.gov/pmb/nwprod/prodstat/', 'ncep_current_production.html', 'GET'),
        'gdex_20260825_listing.html_request.json': ('https://gdex.ucar.edu/datasets/d084001/filelist/20260825/', 'gdex_20260825_listing.html', 'GET'),
        'usgs_special_page.html_request.json': ('https://www.usgs.gov/programs/landslide-hazards/science/2026-nepal-debris-avalanche-and-flash-flood', 'usgs_special_page.html', 'GET')}
    scopes = {'us7000tc90': 'Full returned GeoJSON products/properties and preferred-origin QuakeML; no raw waveform interpreted',
              'gfs_f009': 'HEAD metadata and one fixed f009 index; no GRIB body read',
              'aws_headobject': 'HEAD, Last-Modified, ETag and VersionId definitions only',
              'ncep_current': 'Current date/status and rolling-average schedule; no historical run log',
              'gdex_': 'Only target entry gfs.0p25.2026082518.f009.grib2; no linked data downloaded',
              'usgs_special': 'HTML title/metadata returned; targeted second-event explanation not located; not used as mechanism evidence'}
    records = []
    # Include manually captured HEAD/USGS logs from the initial, bounded queries.
    for path in sorted(S.glob('*.json')):
        obj = json.loads(path.read_text())
        if 'url' not in obj or 'method' not in obj:
            continue
        if path.name not in expected_requests:
            raise ValueError('Unexpected request record outside bounded source set')
        validate_record(obj, *expected_requests[path.name])
        row = {k: obj.get(k) for k in ['url', 'method', 'http_status', 'requested_at_utc', 'retrieved_at_utc', 'received_at_utc', 'final_url', 'error', 'saved_path', 'bytes', 'sha256', 'body_bytes_transferred', 'grib_body_downloaded']}
        row.update({'request_record_path': str(path.relative_to(ROOT)), 'request_record_sha256': sha(path),
                    'reading_scope': next((v for k, v in scopes.items() if path.name.startswith(k)), 'Bounded official metadata response'),
                    'version_metadata': {k: v for k, v in headers(obj).items() if k in ['etag', 'last-modified', 'x-amz-version-id', 'x-amz-meta-modified']}})
        records.append(row)
    if len(records) != len(expected_requests):
        raise ValueError('Bounded source set has missing request records')
    save(O / 'source_register.json', records)
    return records


def common():
    return {'input_version': {'baseline_commit': BASE, 'manifest_sha256': FROZEN_SHA}, 'event_id': None,
            'physical_phase': None, 'time_utc': None, 'time_uncertainty': None, 'space_object': None,
            'variable_semantics': None, 'forecast_reference_time': None, 'issue_time': None,
            'valid_time': None, 'available_time': None, 'data_role': 'exploration', 'evidence_status': 'external_source'}


def event_review():
    doc = read(S / 'us7000tc90.geojson')
    assert doc['id'] == 'us7000tc90' and doc['properties']['type'] == 'landslide'
    xml_path = S / 'us7000tc90_origin_quakeml.xml'
    INPUTS.add(xml_path)
    root = ET.parse(xml_path)
    ns = {'b': 'http://quakeml.org/xmlns/bed/1.2'}
    preferred = root.find('.//b:preferredOriginID', ns).text
    origin = next(o for o in root.findall('.//b:origin', ns) if o.attrib['publicID'] == preferred)
    def value(path):
        element = origin.find(path, ns)
        return element.text if element is not None else None
    time = utc(value('b:time/b:value')).isoformat()
    terr = float(value('b:time/b:uncertainty'))
    confidence = float(value('b:time/b:confidenceLevel'))
    horizontal = float(value('b:originUncertainty/b:horizontalUncertainty'))
    hconfidence = float(value('b:originUncertainty/b:confidenceLevel'))
    assert utc(epoch(doc['properties']['time'])) == utc(time)
    products = doc['properties']['products']
    selected_origin = products['origin'][0]
    declared_hash = selected_origin['contents']['quakeml.xml']['sha256']
    assert base64.b64encode(hashlib.sha256(xml_path.read_bytes()).digest()).decode() == declared_hash
    first = read(ROOT / 'track_b/data/external/event_remote/runs/20261024T034202Z/raw/usgs_event.json')
    first_xml = ROOT / 'track_b/data/external/event_remote/runs/20261024T034202Z/raw/usgs_origin_quakeml.xml'
    INPUTS.add(first_xml)
    first_tree = ET.parse(first_xml)
    first_preferred = first_tree.find('.//b:preferredOriginID', ns).text
    first_origin = next(o for o in first_tree.findall('.//b:origin', ns) if o.attrib['publicID'] == first_preferred)
    first_uncertainty = float(first_origin.find('b:time/b:uncertainty', ns).text)
    first_confidence = float(first_origin.find('b:time/b:confidenceLevel', ns).text)
    first_time = epoch(first['properties']['time'])
    first_header = '\n'.join(p['contents'].get('', {}).get('bytes', '') for p in first['properties']['products'].get('general-header', []))
    second_header = '\n'.join(p['contents'].get('', {}).get('bytes', '') for p in products.get('general-header', []))
    impact = '\n'.join(p['contents'].get('', {}).get('bytes', '') for p in products.get('impact-text', []))
    reciprocal = 'us7000tc90' in first_header and 'us7000tbwb' in second_header
    assert reciprocal and 'post-processing' in second_header and 'satellite' in second_header
    from pyproj import Geod
    a, b = first['geometry']['coordinates'], doc['geometry']['coordinates']
    _, _, separation = Geod(ellps='WGS84').inv(a[0], a[1], b[0], b[1])
    card = common()
    card.update({'event_id': 'USGS:us7000tc90', 'catalogue_id': 'us7000tc90', 'catalogue_type': doc['properties']['type'],
        'physical_phase': 'later_regional_landslide_catalogue_proxy', 'time_utc': time,
        'time_uncertainty': {'catalogue_seconds': terr, 'catalogue_confidence_level_percent': confidence,
                             'proxy_to_first_mechanical_initiation_bias_seconds': None, 'proxy_bias_quantified': False},
        'space_object': {'catalogue_coordinates_lon_lat_depth_km': b, 'crs': 'EPSG:4326', 'location_method': 'estimated_from_satellite_images_per_USGS',
                         'horizontal_uncertainty_m': horizontal, 'horizontal_uncertainty_confidence_level_percent': hconfidence,
                         'max_horizontal_uncertainty_m': float(value('b:originUncertainty/b:maxHorizontalUncertainty')),
                         'min_horizontal_uncertainty_m': float(value('b:originUncertainty/b:minHorizontalUncertainty')),
                         'preferred_uncertainty_description': value('b:originUncertainty/b:preferredDescription'),
                         'true_failure_geometry_verified': False},
        'catalogue_magnitude': doc['properties']['mag'], 'catalogue_magnitude_type': doc['properties']['magType'],
        'origin_public_id': preferred, 'origin_created_time_utc': value('b:creationInfo/b:creationTime'),
        'catalogue_updated_time_utc': epoch(doc['properties']['updated']), 'origin_product_id': selected_origin['id'],
        'origin_product_update_time_utc': epoch(selected_origin['updateTime']),
        'official_explanations': {'general_header_html': second_header, 'impact_text': impact},
        'mechanism_evidence': 'USGS post-processing of low-frequency records found characteristics consistent with landslide; no high-frequency energy; later event described as forming a temporary Trishuli River dam/lake',
        'reference_case_catalogue_id': 'us7000tbwb', 'reference_case_catalogue_time_utc': first_time,
        'catalogue_time_difference_seconds': (utc(time) - utc(first_time)).total_seconds(),
        'catalogue_point_geodesic_separation_m': separation,
        'separation_interpretation': 'Between catalogue centres only; quoted horizontal uncertainties do not permit precise source separation or travel distance inference',
        'relationship': {'different_physical_sub_event': True, 'same_regional_disaster_sequence_supported': reciprocal,
                         'strict_causal_same_chain_verified': False, 'strict_causal_link': None,
                         'statistical_independence_verified': False, 'independent_event_group': None},
        'first_mechanical_initiation_mapping': 'not_corresponding_to_primary_case_first_initiation; later-event catalogue proxy only',
        'adoption_proposal': 'adoptable_with_explicit_role_as_retrospective_regional_context; excluded_as_primary_first_initiation_truth',
        'approved_training_label': False, 'approved_independent_validation_label': False,
        'source_url': API, 'source_sha256': sha(S / 'us7000tc90.geojson'), 'quakeml_sha256': sha(xml_path),
        'remaining': ['raw waveform and onset detection method', 'proxy-to-mechanical onset bias', 'precise failure geometry', 'causal relation and statistical independence'],
        'post_event_label_policy': 'Late-created reliable labels may support retrospective evaluation after review; this version is not a pre-event predictor'})
    save(O / 'us7000tc90_review.json', card)
    target = dict(common(), event_id='B20260826_Chhochen', physical_phase='first_mechanical_initiation_at_source',
                  object_mapping='primary_target_exact_time_unaccepted', evidence_status='candidate', adoption='unknown_with_evidence_and_next_action')
    original = dict(common(), event_id='USGS:us7000tbwb', physical_phase='catalogue_seismic_reference_proxy', time_utc=first_time,
                    object_mapping='proxy_not_accepted_as_precise_primary_initiation', time_uncertainty={'catalogue_seconds': first_uncertainty, 'confidence_level_percent': first_confidence, 'mechanical_proxy_bias_seconds': None}, adoption='retrospective_reference_only')
    later = dict(card, object_mapping=card['first_mechanical_initiation_mapping'], adoption=card['adoption_proposal'])
    rows = [target, original, later]
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (O / 'mechanical_initiation_mapping.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row.get(k), ensure_ascii=False) if row.get(k) is None or isinstance(row.get(k), (dict, list, bool)) else row[k] for k in fields})
    return card


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']: self.skip += 1
        if tag in ['div', 'p', 'td', 'tr', 'dt', 'dd', 'li', 'br']: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ['script', 'style']: self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def forecast_review():
    head = read(S / 'gfs_f009_head.json')
    idx_head = read(S / 'gfs_f009_idx_head.json')
    h, ih = headers(head), headers(idx_head)
    summary = read(ROOT / 'track_b/data/processed/forecast_sample/summary.json')
    old_provenance = [read(path) for path in sorted((ROOT / 'track_b/data/external/forecast_sample').glob('*.http.json'))]
    assert len(old_provenance) == 6
    etags_match = all(item['etag'] == h.get('etag') for item in old_provenance)
    index = S / 'gfs_f009_current.idx'
    INPUTS.add(index)
    old_index = ROOT / 'track_b/data/external/forecast_sample/gfs_2026082518_f009.idx'
    INPUTS.add(old_index)
    index_equal = sha(index) == sha(old_index) == summary['index_sha256']
    archive = S / 'gdex_20260825_listing.html'
    INPUTS.add(archive)
    parser = Text(); parser.feed(archive.read_text(errors='replace'))
    text = re.sub(r'\s+', ' ', unescape(' '.join(parser.parts)))
    filename = 'gfs.0p25.2026082518.f009.grib2'
    position = text.find(filename)
    next_entry = text.find('gfs.0p25.', position + len(filename)) if position >= 0 else -1
    context = text[position:min(position + 350, next_entry if next_entry >= 0 else len(text))].strip() if position >= 0 else None
    archived = re.search(r'Date Archived\s+(\d{4}-\d{2}-\d{2})', context or '')
    row = dict(common(), event_id='B20260826_Chhochen', physical_phase='environmental_forecast_background',
        forecast_reference_time=summary['forecast_reference_time_utc'], valid_time=summary['valid_time_utc'])
    row.update({'object_url': GFS, 'source_scope': 'one fixed 18UTC f009; no new GRIB body downloaded',
        'current_object_head': {'http_status': head.get('http_status'), 'last_modified_time_utc': parsedate_to_datetime(h['last-modified']).isoformat(),
                                'etag': h.get('etag'), 'content_length': int(h['content-length']), 'version_id': h.get('x-amz-version-id'),
                                'received_at_utc': head.get('received_at_utc')},
        'current_index_head': {'http_status': idx_head.get('http_status'), 'last_modified_time_utc': parsedate_to_datetime(ih['last-modified']).isoformat(),
                               'etag': ih.get('etag'), 'content_length': int(ih['content-length']), 'version_id': ih.get('x-amz-version-id')},
        'etag_matches_six_saved_range_responses': etags_match, 'current_index_bytes_match_saved_index': index_equal,
        'full_historical_version_and_public_access_history_proven': False,
        'gdex_archive_entry': {'url': 'https://gdex.ucar.edu/datasets/d084001/filelist/20260825/', 'filename': filename,
                              'target_entry_found': position >= 0, 'date_archived_text': archived.group(1) if archived else None,
                              'date_timezone_or_time_of_day_verified': False, 'full_content_identity_with_S3_verified': False, 'target_entry_text': context},
        'available_time': None, 'available_time_verified': False,
        'historical_first_public_access_lower_bound': None, 'historical_first_public_access_upper_bound_before_event': None,
        'earliest_saved_successful_range_receipt_utc': min(item['fetched_at_utc'] for item in old_provenance),
        'range_receipt_bound_meaning': 'Public byte-range access observed no later than this October receipt; no August operational bound follows',
        'adoption_proposal': 'object/version-association metadata adoptable; historical first availability remains unknown; real-time replay not certified',
        'current_production_schedule_role': 'current status/rolling-average schedule only; not this historical run completion log',
        'requirements_for_stronger_bound': ['historical object-created/distribution record for this exact key', 'proof of public access at the claimed time', 'version identity and timestamp semantics'],
        'operational_gate_for_pre_event_issues': 'unknown_not_eligible', 'real_coverage': None})
    save(O / 'gfs_f009_availability_chain.json', row)
    return row


def finalize():
    excluded = {'input_manifest.json', 'output_manifest.json', 'workspace_binding.json', 'workspace_verification.json'}
    paths = [p for p in sorted(R.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name not in excluded]
    files = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths]
    for row in files:
        path = ROOT / row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
    save(O / 'output_manifest.json', {'files': files, 'file_count': len(files), 'all_hashes_rechecked': True,
        'excluded_names': sorted(excluded), 'exclusion_reason': 'Both manifests exclude themselves and each other; runtime binding/readiness are mutable and copied to results at run time.'})
    print(json.dumps({'outputs': len(files), 'output_manifest_sha256': sha(O / 'output_manifest.json'), 'hash_recheck_passed': True}))


def main():
    started = datetime.now(timezone.utc).isoformat()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--finalize', action='store_true')
    args = parser.parse_args()
    binding = json.loads((R / 'workspace_binding.json').read_text())
    assert ROOT == Path(binding['execution_root']).resolve() and Path(sys.prefix).resolve() == ROOT / 'track_b/.venv'
    readiness = json.loads((R / 'workspace_verification.json').read_text())
    assert readiness['passed'] and binding['common_baseline_commit'] == BASE
    frozen = ROOT / 'track_b/audit/stage4/round2/baseline_manifest.json'
    assert sha(frozen) == FROZEN_SHA
    INPUTS.add(frozen)
    read(ROOT / 'track_b/config/stage4_round2_contract.json')
    if args.finalize:
        finalize(); return
    O.mkdir(parents=True, exist_ok=True)
    save(O / 'workspace_binding_at_run.json', binding)
    save(O / 'workspace_readiness_at_run.json', readiness)
    if args.collect: collect()
    sources = source_log()
    event = event_review()
    forecast = forecast_review()
    for p in sorted(S.iterdir()):
        if p.is_file(): INPUTS.add(p)
    stable = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(INPUTS)
              if p.name not in ['input_manifest.json', 'output_manifest.json']]
    save(O / 'input_manifest.json', {'files': stable, 'file_count': len(stable), 'self_and_output_manifest_excluded': True})
    checks = {'event_id_matches': event['catalogue_id'] == 'us7000tc90', 'reciprocal_context_confirmed': event['relationship']['same_regional_disaster_sequence_supported'],
              'time_uncertainty_kept_at_original_confidence': event['time_uncertainty']['catalogue_confidence_level_percent'] == 90,
              'proxy_bias_still_unknown': event['time_uncertainty']['proxy_to_first_mechanical_initiation_bias_seconds'] is None,
              'strict_causal_link_not_claimed': event['relationship']['strict_causal_link'] is None,
              'label_not_auto_accepted': not event['approved_training_label'] and not event['approved_independent_validation_label'],
              's3_etag_correspondence': forecast['etag_matches_six_saved_range_responses'], 'index_matches_frozen_bytes': forecast['current_index_bytes_match_saved_index'],
              'first_availability_still_unknown': forecast['available_time'] is None,
              'no_grib_body_in_collection_logs': all(not r.get('grib_body_downloaded') for r in sources)}
    save(O / 'evidence_checks.json', {'passed': all(checks.values()), 'checks': checks, 'scope': 'Evidence consistency and bounded-query checks; no repeated R1 mechanics or forecast skill evaluation'})
    if not all(checks.values()): raise ValueError('Evidence consistency check failed')
    save(O / 'summary.json', {'round': 'round2', 'contract_version': 'stage4-r2-v1', 'input_version': {'baseline_commit': BASE, 'manifest_sha256': FROZEN_SHA},
        'run_started_at_utc': started, 'analysis_completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'runtime': {'python': sys.version, 'prefix': sys.prefix, 'execution_root': str(ROOT)},
        'event_outcome': event['adoption_proposal'], 'forecast_outcome': forecast['adoption_proposal'],
        'independent_training_events_added': 0, 'independent_validation_events_added': 0, 'accepted_independent_events_total': 0,
        'available_time': None, 'real_coverage': None, 'new_grib_body_bytes': 0, 'historical_catalogue_expansion': False,
        'evidence_checks_passed': True, 'source_request_records': len(sources), 'new_plots_created': False,
        'next_gate': 'round2 joint review and human scientific adoption'})
    finalize()
    print(json.dumps({'event_time_utc': event['time_utc'], 'time_uncertainty_s': event['time_uncertainty']['catalogue_seconds'],
                      'first_availability': None, 'independent_events_added': 0, 'passed': True}))


if __name__ == '__main__':
    main()
