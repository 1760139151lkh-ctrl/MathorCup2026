#!/usr/bin/env python3
"""Probe only the approved two VV assets with a persistent combined body budget.

No automatic redirects/retries, credentials, whole-scene requests or GDAL URL I/O.
An HTTP 200 answer to Range is closed before consuming response-body bytes.
Use --offline to rebuild the result from saved evidence without network access.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'track_b/research/q2/round2'
LIMIT = 134217728
IDS = [
    'S1D_IW_GRDH_1SDV_20260819T001036_20260819T001101_004187_007ABD_B38C_COG',
    'S1D_IW_GRDH_1SDV_20260831T001037_20260831T001102_004362_0080EC_65B9_COG',
]
BASE = '76ee1532cb2acf36fb82c5f4749a4288507dfcc8'
FROZEN_SHA = 'c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d'
LEDGER = OUT / 'network_budget.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def inventory():
    path = ROOT / 'track_b/data/external/event_remote/scene_inventory.json'
    value = json.loads(path.read_text())
    result = {s['item_id']: s for s in value['records'] if s['item_id'] in IDS}
    assert set(result) == set(IDS)
    for s in result.values():
        assert s['platform'] == 'sentinel-1d' and s['relative_orbit'] == 121 and s['orbit_state'] == 'descending'
    return result


def budget_load():
    if LEDGER.exists():
        value = json.loads(LEDGER.read_text())
        assert value['max_response_body_bytes_combined'] == LIMIT
    else:
        value = {'schema_version': 1, 'max_response_body_bytes_combined': LIMIT,
                 'consumed_response_body_bytes_combined': 0, 'requests': [],
                 'counting_scope': 'Response-body bytes explicitly consumed by this client, including failed responses and metadata/header ranges; not HTTP headers, TLS overhead or OS buffering.',
                 'persistence_policy': 'Never reset between scenes or online replays; previously attempted scene not automatically retried.',
                 'whole_scene_allowed': False, 'redirects_or_retries_enabled': False,
                 'authentication': 'anonymous only; session.trust_env=false; no credentials'}
    assert value['consumed_response_body_bytes_combined'] == sum(r['body_bytes_consumed'] for r in value['requests'])
    assert value['consumed_response_body_bytes_combined'] <= LIMIT
    return value


def probe(scene, label, budget):
    import requests
    asset = scene['assets']['vv']
    url = asset['alternate']['https']['href']
    assert url.startswith('https://download.dataspace.copernicus.eu/')
    request_bytes = 16384
    if LIMIT - budget['consumed_response_body_bytes_combined'] < request_bytes:
        raise RuntimeError('Insufficient combined budget before request')
    row = {'request_id': len(budget['requests']) + 1, 'scene_id': scene['item_id'],
           'purpose': 'VV COG header/range capability; no AOI pixels requested', 'method': 'GET',
           'url': url, 'range': 'bytes=0-16383', 'requested_max_success_body_bytes': request_bytes,
           'started_at_utc': datetime.now(timezone.utc).isoformat(), 'body_bytes_consumed': 0,
           'http_status': None, 'body_path': None, 'sha256': None, 'range_honoured': False,
           'usable_pixels_obtained': False, 'tiff_header_verified': False, 'outcome': 'request_not_completed'}
    budget['requests'].append(row)
    save(LEDGER, budget)
    session = requests.Session()
    session.trust_env = False
    response = None
    body = bytearray()
    try:
        response = session.get(url, headers={'Range': row['range'], 'Accept-Encoding': 'identity',
                                            'User-Agent': 'MathorCup-Q2-Round2-bounded-probe/1.0'},
                               stream=True, allow_redirects=False, timeout=(15, 25))
        row.update(http_status=response.status_code, content_type=response.headers.get('Content-Type'),
                   content_length=response.headers.get('Content-Length'), content_range=response.headers.get('Content-Range'),
                   accept_ranges=response.headers.get('Accept-Ranges'), location=response.headers.get('Location'),
                   etag=response.headers.get('ETag'), last_modified=response.headers.get('Last-Modified'))
        if response.status_code == 200:
            row['outcome'] = 'range_returned_200_body_not_read'
            return
        if 300 <= response.status_code < 400:
            row['outcome'] = 'redirect_not_followed_body_not_read'
            return
        maximum = min(65536, LIMIT - budget['consumed_response_body_bytes_combined'])
        if response.status_code == 206:
            match = re.fullmatch(r'bytes\s+(\d+)-(\d+)/(\d+|\*)', response.headers.get('Content-Range', ''))
            if not match or int(match[1]) != 0 or int(match[2]) >= request_bytes:
                row['outcome'] = 'invalid_content_range_body_not_read'
                return
            maximum = int(match[2]) + 1
            if response.headers.get('Content-Length') and int(response.headers['Content-Length']) > maximum:
                row['outcome'] = 'oversized_content_length_body_not_read'
                return
            row['range_honoured'] = True
        while len(body) < maximum:
            chunk = response.raw.read(min(8192, maximum - len(body)), decode_content=False)
            if not chunk:
                break
            body.extend(chunk)
            row['body_bytes_consumed'] += len(chunk)
            budget['consumed_response_body_bytes_combined'] += len(chunk)
            assert budget['consumed_response_body_bytes_combined'] <= LIMIT
            save(LEDGER, budget)
        if body:
            path = OUT / f'sources/sar/{label}_response.bin'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            row.update(body_path=str(path.relative_to(ROOT)), sha256=sha(path))
        if response.status_code in (401, 403):
            row['outcome'] = 'anonymous_authentication_or_authorization_failure'
        elif response.status_code != 206:
            row['outcome'] = 'non_partial_response_not_pixel_data'
        else:
            row['tiff_header_verified'] = bytes(body[:4]) in (b'II*\0', b'MM\0*', b'II+\0', b'MM\0+')
            row['outcome'] = 'bounded_tiff_header_only' if row['tiff_header_verified'] else 'partial_response_not_tiff'
    except Exception as exc:
        row.update(outcome='request_error', error=f'{type(exc).__name__}: {exc}')
    finally:
        if response is not None:
            response.close()
        session.close()
        row['ended_at_utc'] = datetime.now(timezone.utc).isoformat()
        row['combined_consumed_after_request'] = budget['consumed_response_body_bytes_combined']
        save(LEDGER, budget)


def summarise(budget, scenes):
    frozen = ROOT / 'track_b/audit/stage4/round2/baseline_manifest.json'
    assert sha(frozen) == FROZEN_SHA
    rows = []
    for sid in IDS:
        scene = scenes[sid]
        requests = [r for r in budget['requests'] if r['scene_id'] == sid]
        rows.append({'event_id': 'B20260826_Chhochen', 'physical_phase': 'pre_event_remote_candidate' if '20260819' in sid else 'post_event_remote_candidate',
                     'time_utc': scene['datetime'], 'time_uncertainty': None,
                     'space_object': {'id': 'scene_catalogue_footprint', 'crs': 'EPSG:4326', 'geometry': scene['geometry'], 'true_failure_geometry_verified': False},
                     'variable_semantics': {'polarization': 'VV', 'product': 'GRD COG', 'catalogue_type': scene['assets']['vv']['type']},
                     'available_time': None, 'forecast_reference_time': None, 'issue_time': None, 'valid_time': scene['datetime'],
                     'data_role': 'exploration', 'input_version': {'baseline_commit': BASE, 'baseline_manifest_sha256': FROZEN_SHA},
                     'evidence_status': 'local_fact', 'scene_id': sid, 'asset_url': scene['assets']['vv']['alternate']['https']['href'],
                     'catalogue_asset_size_bytes': scene['assets']['vv'].get('file:size'),
                     'requests': requests, 'access_outcome': requests[-1]['outcome'] if requests else 'not_attempted',
                     'usable_pixels_obtained': False, 'co_registration_verified': False, 'change_interpretation_verified': False})
    save(OUT / 'results/pair_access.json', {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'scene_count': 2,
         'scope': 'Only fixed orbit-121 VV pair; header probes do not establish AOI pixel support.', 'records': rows,
         'network_body_bytes': budget['consumed_response_body_bytes_combined'], 'max_network_body_bytes': LIMIT})
    print(json.dumps({'scenes': 2, 'outcomes': [r['access_outcome'] for r in rows],
                      'combined_body_bytes': budget['consumed_response_body_bytes_combined'], 'limit': LIMIT}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--online', action='store_true')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    assert args.online != args.offline, 'Choose exactly one of --online and --offline'
    ready = json.loads((OUT / 'workspace_verification.json').read_text())
    assert ready['passed'] and ready['round'] == 'round2'
    scenes = inventory()
    budget = budget_load()
    if args.online:
        for index, sid in enumerate(IDS):
            if not any(r['scene_id'] == sid for r in budget['requests']):
                probe(scenes[sid], 'pre' if index == 0 else 'post', budget)
    summarise(budget, scenes)


if __name__ == '__main__':
    main()
