#!/usr/bin/env python3
"""Exploratory optical/model agreement, explicitly not independent validation."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json

import numpy as np
from affine import Affine
from pyproj import Transformer
import rasterio.features
from rasterio.warp import reproject, Resampling
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[5]
R = ROOT/'track_b/research/q4/round3'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    protocol = json.loads((R/'config/optical_agreement_protocol.json').read_text())
    mask_path = Path(protocol['mask_path'])
    assert sha(mask_path) == protocol['mask_sha256']
    optical = np.load(mask_path)
    valid = optical['valid_pair'].astype(bool)
    target_transform = Affine(*optical['affine'][:6])
    gj = json.loads((R/'results/computational_geometries.geojson').read_text())
    project = Transformer.from_crs(4326, 32645, always_xy=True).transform
    paths = [transform(project, shape(f['geometry'])) for f in gj['features'] if f['id'] in ['P1', 'P2', 'P3']]
    corridor = unary_union(paths).buffer(250)
    in_corridor = rasterio.features.geometry_mask([mapping(corridor)], valid.shape,
                                                 target_transform, invert=True)
    models = []
    for p in sorted((R/'results').glob('reduced_2d_*.json')):
        record = json.loads(p.read_text())
        if 'fields' not in record:
            continue
        assert record['summary']['execution_status'] == 'completed'
        q = Path(record['fields']['path'])
        assert sha(q) == record['fields']['sha256']
        data = np.load(q)
        dx = float(record['resolution_m'])
        source_transform = Affine(dx, 0, float(data['x'][0])-dx/2,
                                  0, -dx, float(data['y'][0])+dx/2)
        models.append({'run_id': record['run_id'], 'model_id': record['model_id'],
                       'source': q, 'depth': data['snapshots'].max(axis=0), 'transform': source_transform,
                       'spatial_resolution_m': dx, 'stored_interval_s': 30,
                       'stored_time_definition': 'fixed requested 30 s outputs; actual fields retained',
                       'actual_end_time_s': float(data['times'][-1]) if 'times' in data else 1800.0,
                       'numerical_qualification': 'regional_thin_flow_accuracy_unqualified',
                       'evaluation_stratum': 'conditional_scenario'})
    index_path = R/'results/official_fields.json'
    runs_path = R/'results/official_runs.csv'
    if index_path.exists() and runs_path.exists():
        rows = {row['run_id']: row for row in csv.DictReader(runs_path.open())}
        decision = json.loads((R/'config/model_applicability_decision_03.json').read_text())
        generic_proxy_ids = set(decision['applicability_classes']['generic_material_proxy_diagnostic_only']['run_ids'])
        for f in json.loads(index_path.read_text())['fields']:
            row = rows[f['run_id']]
            if row['status'] != 'completed' or row.get('role') not in {'conditional_scenario', 'conditional_cross_question_scenario', 'conditional_component_closure_challenge', 'bounded_entrainment_conditional_sensitivity'} or f['run_id'] in generic_proxy_ids:
                continue
            q = Path(f['path'])
            assert sha(q) == f['sha256']
            data = np.load(q)
            models.append({'run_id': f['run_id'], 'model_id': row['model'], 'source': q,
                           'depth': data['depth_frames'].max(axis=0), 'transform': Affine(*data['transform'][:6]),
                           'spatial_resolution_m': float(row['resolution_m']), 'stored_interval_s': None,
                           'stored_time_definition': 'actual native time_s array; no frame-index times inferred',
                           'actual_end_time_s': float(data['time_s'][-1]),
                           'numerical_qualification': 'see native numerical validation; not event validated',
                           'evaluation_stratum': 'conditional_scenario'})
    results = []
    for model in models:
        mapped = np.zeros(valid.shape, dtype='uint8')
        reproject((model['depth'] >= .1).astype('uint8'), mapped,
                  src_transform=model['transform'], src_crs='EPSG:32645',
                  dst_transform=target_transform, dst_crs='EPSG:32645', resampling=Resampling.nearest)
        predicted = mapped.astype(bool)
        for name, domain in [('full_paired_valid', valid), ('path250m_paired_valid', valid & in_corridor)]:
            for mask_name in ['change_candidate', 'change_candidate_ge9']:
                candidate = optical[mask_name].astype(bool)
                n = int(domain.sum())
                nc = int((candidate & domain).sum())
                nm = int((predicted & domain).sum())
                ni = int((predicted & candidate & domain).sum())
                nu = int(((predicted | candidate) & domain).sum())
                results.append({key: model[key] for key in ['run_id', 'model_id', 'spatial_resolution_m', 'stored_interval_s', 'stored_time_definition', 'actual_end_time_s', 'numerical_qualification', 'evaluation_stratum']} | {
                    'domain': name, 'optical_mask': mask_name, 'paired_valid_area_m2': n*100,
                    'candidate_change_area_m2': nc*100, 'model_footprint_area_within_valid_m2': nm*100,
                    'intersection_area_m2': ni*100, 'union_area_m2': nu*100,
                    'intersection_over_union': ni/nu if nu else None,
                    'candidate_change_covered_fraction': ni/nc if nc else None,
                    'model_area_with_candidate_change_fraction': ni/nm if nm else None,
                    'fields_path': str(model['source']), 'fields_sha256': sha(model['source']),
                    'role': 'exploratory_spatial_agreement_not_independent_validation'})
    assert results, 'No executed gridded models found'
    with (R/'results/optical_model_agreement.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'protocol_path': 'config/optical_agreement_protocol.json',
              'protocol_sha256': sha(R/'config/optical_agreement_protocol.json'),
              'models': len(models), 'rows': len(results), 'independent_validation_events': 0,
              'interpretation': '47-day vegetation-change screen is an ambiguous retrospective candidate. Nearest upsampling adds no model resolution. No tuning, probability or event-validation claim.'}
    (R/'results/optical_model_agreement.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
