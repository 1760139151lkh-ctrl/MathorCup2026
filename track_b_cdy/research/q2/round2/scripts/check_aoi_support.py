#!/usr/bin/env python3
"""Offline scene-footprint screening of an explicitly approved search AOI.

No image reads, georeferencing changes, inferred failure polygons or network calls.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'track_b/research/q2/round2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aoi', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--approval-record', type=Path, required=True)
    parser.add_argument('--expected-approval-sha256', required=True)
    args = parser.parse_args()
    aoi_path, approval_path = args.aoi.resolve(), args.approval_record.resolve()
    for path in [aoi_path, approval_path]:
        assert path.is_relative_to((OUT / 'inputs').resolve()), 'Use the advisor-distributed input copy only'
    assert sha(aoi_path) == args.expected_sha256
    assert sha(approval_path) == args.expected_approval_sha256
    approval = json.loads(approval_path.read_text())
    assert approval['reviewer'] == 'main_advisor_AI_technical_review'
    assert approval['status'] == 'adopted_for_search_only' and approval['consumer_question'] == 'q2'
    assert approval['geometry_sha256'] == args.expected_sha256
    assert approval['common_baseline_commit'] == '76ee1532cb2acf36fb82c5f4749a4288507dfcc8'
    evidence_path = aoi_path.parent / 'search_aoi_evidence.json'
    assert sha(evidence_path) == approval['evidence_sha256']
    evidence = json.loads(evidence_path.read_text())
    assert evidence['space_object']['crs'] == 'OGC:CRS84 (GeoJSON longitude,latitude)'
    uncertainty = {'positional_uncertainty_m': evidence['space_object']['positional_uncertainty_m'],
                   'original_map_accuracy_m': evidence['space_object']['original_map_accuracy_m'],
                   'source_datum_assumption': evidence['space_object']['source_datum_assumption'],
                   'search_padding_m': approval['checks']['search_padding_m'],
                   'padding_is_accuracy_or_confidence_bound': False,
                   'latitude_independent_holdout_available': False}

    from shapely.geometry import Point, shape
    data = json.loads(aoi_path.read_text())
    features = data['features'] if data['type'] == 'FeatureCollection' else [data]
    pair = json.loads((OUT / 'results/pair_access.json').read_text())
    rows = []
    for index, feature in enumerate(features):
        geometry = shape(feature['geometry'] if feature['type'] == 'Feature' else feature)
        assert geometry.is_valid and not geometry.is_empty
        for scene in pair['records']:
            footprint = shape(scene['space_object']['geometry'])
            row = {'event_id': 'B20260826_Chhochen', 'physical_phase': scene['physical_phase'],
                   'time_utc': scene['time_utc'], 'time_uncertainty': None,
                   'space_object': {'id': f'advisor_reviewed_search_AOI_feature_{index}', 'crs': 'OGC:CRS84 (longitude,latitude)',
                                    'purpose': 'search_only_not_release_or_failure_geometry',
                                    'positional_uncertainty': uncertainty,
                                    'aoi_sha256': args.expected_sha256},
                   'variable_semantics': {'product': 'Sentinel-1D GRD', 'polarization': 'VV', 'pixels': 'not_obtained'},
                   'available_time': None, 'forecast_reference_time': None, 'issue_time': None,
                   'valid_time': scene['valid_time'], 'data_role': 'exploration',
                   'input_version': {**scene['input_version'], 'aoi_sha256': args.expected_sha256,
                                     'approval_record_sha256': sha(approval_path)},
                   'evidence_status': 'local_fact', 'scene_id': scene['scene_id'],
                   'feature_id': feature.get('id', feature.get('properties', {}).get('id', index)),
                   'catalogue_footprint_contains_search_aoi': footprint.covers(geometry),
                   'catalogue_footprint_intersects_search_aoi': footprint.intersects(geometry),
                   'retrospective_map_symbol_anchor_containment': {name: footprint.covers(Point(coords)) for name, coords in evidence['anchors_assumed_wgs84_lon_lat'].items()},
                   'true_failure_polygon_coverage': None, 'usable_pixels_obtained': False,
                   'pixel_valid_fraction': None, 'pixel_crs_or_resolution_verified': False,
                   'co_registration_verified': False, 'terrain_visibility_verified': False,
                   'change_interpretation_verified': False, 'access_outcome': scene['access_outcome'],
                   'outcome': 'excluded_with_reason' if 'failure' in scene['access_outcome'] or 'not_read' in scene['access_outcome'] else 'unknown_with_evidence_and_next_action',
                   'reason': 'Anonymous VV access did not provide pixels; footprint support does not change this outcome.'}
            rows.append(row)
    path = OUT / 'results/aoi_pixel_support.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'offline': True,
              'aoi': str(aoi_path.relative_to(ROOT)), 'aoi_sha256': args.expected_sha256,
              'approval_record': str(approval_path.relative_to(ROOT)), 'approval_sha256': sha(approval_path),
              'producer_evidence_sha256': sha(evidence_path), 'producer_pending_fields_preserved': True,
              'features': len(features), 'rows': len(rows), 'all_search_features_contained_in_both_catalogue_footprints': all(r['catalogue_footprint_contains_search_aoi'] for r in rows),
              'all_search_features_intersect_both_catalogue_footprints': all(r['catalogue_footprint_intersects_search_aoi'] for r in rows),
              'all_three_retrospective_map_symbol_anchors_inside_both_footprints': all(all(r['retrospective_map_symbol_anchor_containment'].values()) for r in rows),
              'usable_pixels_obtained': False, 'network_requests_this_step': 0,
              'scope': 'Catalogue topology of reviewed search geometry; not exact ground coverage, failure geometry, image quality or change detection.'}
    (OUT / 'results/aoi_support_check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
