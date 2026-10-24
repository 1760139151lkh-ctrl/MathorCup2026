#!/usr/bin/env python3
"""Validate delivery bindings and semantic invariants; no R1 experiments/network."""
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from PIL import Image
from pyproj import Transformer
from shapely import transform
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(rel):
    return json.loads((R/rel).read_text())


def check_index():
    counts = {}
    for name in ['input_manifest.json', 'output_manifest.json']:
        path = R/'results'/name
        data = json.loads(path.read_text())
        names = set()
        for entry in data['files']:
            item = ROOT/entry['path']
            assert item != path and entry['path'] not in names
            names.add(entry['path'])
            assert item.stat().st_size == entry['bytes'], entry['path']
            assert sha(item) == entry['sha256'], entry['path']
        counts[name] = len(names)
    out = read('results/output_manifest.json')
    assert out['file_count'] == counts['output_manifest.json']
    actual = {str(path.relative_to(ROOT)) for path in R.rglob('*')
              if path.is_file() and path != R/'results/output_manifest.json'
              and '__pycache__' not in path.parts and path.suffix != '.pyc'}
    assert actual == {entry['path'] for entry in out['files']}
    print(json.dumps({'read_only_index_check_passed': True, 'counts': counts}))


def main():
    if sys.argv[1:] == ['--check-index']:
        check_index()
        return
    assert not sys.argv[1:], 'Use no argument or --check-index'
    checks = []
    def passed(name, evidence):
        checks.append({'name': name, 'passed': True, 'evidence': evidence})

    expected = {'results/search_aoi.geojson': '14db392ea6d318c2df34152af950b227653fd1f938aed1f4aa9eedf92c29579f',
                'results/search_aoi_evidence.json': '78ff69266903ee77626679b0bba542ec36f1e73e3d39581909543d63ba262d14'}
    for rel, digest in expected.items():
        assert sha(R/rel) == digest, f'Adopted early artifact changed: {rel}'
    early = read('results/search_aoi_evidence.json')
    assert early['input_version']['config_sha256'] == sha(R/'config/map_digitisation.json')
    assert early['input_version']['script_sha256'] == sha(R/'scripts/build_search_aoi.py')
    assert early['review']['latitude_holdout'] is None
    assert early['review']['original_map_positional_accuracy_m'] is None
    receipt = read('sources/advisor_aoi_receipt.json')
    assert receipt['search_aoi_sha256'] == expected['results/search_aoi.geojson']
    assert receipt['early_evidence_sha256'] == expected['results/search_aoi_evidence.json']
    assert receipt['approved_role'] == 'search_only' and not receipt['event_geometry_accepted']
    replay = R/'results/replay_check/results/search_aoi.geojson'
    assert replay.read_bytes() == (R/'results/search_aoi.geojson').read_bytes()
    passed('adopted_AOI_and_safe_replay', 'Early geometry/evidence bytes, script/config bindings and isolated geometry replay match.')

    gj = read('results/geometry_candidates.geojson')
    aoi = shape(read('results/search_aoi.geojson')['features'][0]['geometry'])
    geometries = {f['id']: shape(f['geometry']) for f in gj['features']}
    assert len(geometries) == 5 and aoi.is_valid
    for f in gj['features']:
        assert geometries[f['id']].is_valid and aoi.covers(geometries[f['id']])
        assert not f['properties']['accepted_event_geometry']
        assert f['properties']['geometry_status'] == 'retrospective_reconstruction_candidate'
    with (R/'results/geometry_evidence.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 5 and {row['space_id'] for row in rows} == set(geometries)
    cov = read('results/corridor_coverage.json')
    assert cov['input_version']['geometry_sha256'] == sha(R/'results/geometry_candidates.geojson')
    assert cov['input_version']['config_sha256'] == sha(R/'config/geometry_trace.json')
    assert cov['input_version']['script_sha256'] == sha(R/'scripts/build_candidates.py')
    for raster in cov['raster_inputs']:
        assert sha(ROOT/raster['path']) == raster['sha256']
    project = Transformer.from_crs(4326, 32645, always_xy=True).transform
    source = transform(geometries['paper_source_outline'], project, interleaved=False)
    upper = transform(geometries['paper_chhochen_blue_trace'], project, interleaved=False)
    gap = source.distance(upper)
    assert math.isclose(gap, cov['source_outline_to_blue_river_candidate_gap_m'], abs_tol=1e-6)
    assert not cov['source_to_channel_connection_verified'] and not cov['actual_source_to_target_continuity_verified']
    assert cov['actual_propagation_distance_m'] is None and not cov['longitudinal_profile_generated']
    passed('five_candidate_objects_and_gap', {'count': 5, 'gap_m_not_true_connection': gap})

    assert len(cov['candidate_corridors']) == 6
    assert {(c['raster'], c['corridor_half_width_m']) for c in cov['candidate_corridors']} == {
        (name, width) for name in ['independent_projected_DEM', 'NC_DEM_parameter_rectangle'] for width in [100, 250, 500]}
    for row in cov['candidate_corridors']:
        assert 0 <= row['area_coverage_fraction'] <= 1
        assert 0 <= row['valid_inside_pixel_centres'] <= row['inside_raster_pixel_centres']
        assert math.isclose(row['area_covered_m2'] + row['area_outside_valid_footprint_m2'], row['candidate_corridor_area_m2'], abs_tol=1e-6)
        if row['raster'] == 'independent_projected_DEM':
            assert row['all_corridor_covered_by_valid_footprint'] and row['area_coverage_fraction'] == 1
            assert row['internal_invalid_inside_pixel_centres'] == 0 and row['boundary_margin_m_if_fully_covered'] > 0
        else:
            assert not row['all_corridor_covered_by_valid_footprint'] and 0.11 < row['area_coverage_fraction'] < 0.13
    for row in cov['candidate_objects']:
        assert row['independent_DEM_fully_covers_candidate']
        assert row['NC_DEM_fully_covers_candidate'] == (row['space_id'] == 'paper_source_outline')
    passed('candidate_corridor_coverage_semantics', 'Six conditional coverage rows coherent; no acceptance of real connectivity or terrain provenance.')

    status = read('results/geometry_independent_status.json')
    assert status['geometry_sha256'] == sha(R/'results/geometry_candidates.geojson')
    assert status['evidence_csv_sha256'] == sha(R/'results/geometry_evidence.csv')
    assert status['bounded_review_sha256'] == sha(R/'sources/independent_geography_review.json')
    assert {obj['space_id'] for obj in status['objects']} == set(geometries)
    assert all(not obj['independent_machine_geometry_obtained'] and not obj['event_geometry_accepted'] for obj in status['objects'])
    metadata = read('results/local_metadata_recheck.json')
    assert metadata['vertical_names_from_xml'] == [['VERTCS', 'unknown'], ['VDATUM', 'unknown']]
    assert all(p['contains_clip'] for p in metadata['xml_processes'])
    passed('independent_geometry_and_vertical_datum_remain_unknown', True)

    visual = read('results/visual_review.json')
    for item in visual['figures']:
        path = ROOT/item['path']
        assert item['actually_opened'] and sha(path) == item['sha256']
        with Image.open(path) as im:
            assert im.width > 1000 and im.height > 500
    for path in (R/'scripts').glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    for path in R.rglob('*.json'):
        json.loads(path.read_text())
    for name in ['HANDOFF.md', 'ROUTE_UPDATE.md']:
        for target in re.findall(r'\]\(([^)]+)\)', (R/name).read_text()):
            if '://' not in target:
                # This invocation creates its own linked report immediately below.
                assert (R/target).exists() or target == 'results/delivery_validation.json', (name, target)
    passed('visual_bindings_syntax_json_and_document_links', 'Actual visual review hashes match; scripts parse and local handoff links exist.')
    report = {'schema_version': 'q4-r2-delivery-validation-v1',
              'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': True, 'checks': checks,
              'scope': 'Artifact integrity and conditional diagnostic consistency only; no truth geometry, dynamics, independent validation or human scientific adoption.'}
    (R/'results/delivery_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'check_groups': len(checks)}))


if __name__ == '__main__':
    main()
