#!/usr/bin/env python3
"""Reproduce a search-only AOI from Fig.1 printed axis constraints.

No georeferenced event truth is accepted. Codex assistance 2026-10-24.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from pyproj import Geod, Transformer
from shapely.geometry import MultiPoint, box, mapping
from shapely.ops import transform

ROOT=Path(__file__).resolve().parents[5]
R=ROOT/'track_b/research/q4/round2'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    config_path=R/'config/map_digitisation.json';cfg=json.loads(config_path.read_text())
    assert ROOT==Path(json.loads((R/'workspace_binding.json').read_text())['execution_root']).resolve()
    assert json.loads((R/'workspace_verification.json').read_text())['passed']
    controls=cfg['controls']; geod=Geod(ellps='WGS84')
    fits={}; rows=[]
    for axis,coordinate in [('longitude','x'),('latitude','y')]:
        subset=[v for v in controls if v['axis']==axis]
        p=np.array([v[coordinate] for v in subset]);y=np.array([v['degrees'] for v in subset])
        coefficients=np.polyfit(p,y,1);fits[axis]=coefficients.tolist()
        for item in subset:
            predicted=float(np.polyval(coefficients,item[coordinate]))
            if axis=='longitude': error=abs(geod.inv(item['degrees'],28.3,predicted,28.3)[2])
            else: error=abs(geod.inv(85.45,item['degrees'],85.45,predicted)[2])
            rows.append(dict(item,predicted_degrees=predicted,residual_degrees=predicted-item['degrees'],
                             residual_equivalent_m=error,other_coordinate_status='unconstrained; axis tick is not a full 2D ground control point'))
    training=[v for v in controls if v['axis']=='longitude' and v['role']=='train']
    held=next(v for v in controls if v['role']=='holdout_then_final_fit')
    coeff=np.polyfit([v['x'] for v in training],[v['degrees'] for v in training],1)
    prediction=float(np.polyval(coeff,held['x']))
    held_error=abs(geod.inv(held['degrees'],28.3,prediction,28.3)[2])
    def xy_to_lonlat(xy): return [float(np.polyval(fits['longitude'],xy[0])),float(np.polyval(fits['latitude'],xy[1]))]
    anchors={name:xy_to_lonlat(xy) for name,xy in cfg['search_anchors_crop_pixels'].items()}
    forward=Transformer.from_crs(4326,32645,always_xy=True).transform
    backward=Transformer.from_crs(32645,4326,always_xy=True).transform
    points=transform(forward,MultiPoint(list(anchors.values())))
    bounds=points.bounds;pad=cfg['search_padding_m']
    aoi_utm=box(bounds[0]-pad,bounds[1]-pad,bounds[2]+pad,bounds[3]+pad)
    aoi=transform(backward,aoi_utm)
    feature={'type':'Feature','id':cfg['version'],'properties':{'purpose':'search_only','event_id':'B20260826_Chhochen',
             'geometry_status':'retrospective_map_reconstruction_candidate','release_geometry':False,
             'source_datum_verified':False,'positional_accuracy_m':None,'search_padding_m':pad,
             'padding_is_error_bound':False,'advisor_review_status':'pending','version':cfg['version']},'geometry':mapping(aoi)}
    save(R/'results/search_aoi.geojson',{'type':'FeatureCollection','name':'Q4 search-only AOI; not release geometry','features':[feature]})
    with (R/'results/georeference_controls.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    review={'calibration_model':cfg['calibration_model'],'fit_coefficients':fits,'axis_constraints':rows,
            'longitude_holdout':{'id':held['id'],'prediction_degrees':prediction,'reference_degrees':held['degrees'],
                                 'equivalent_error_m':held_error,'fit_used_for_holdout':'two endpoint longitude ticks only'},
            'latitude_holdout':None,'latitude_holdout_reason':'Only two latitude ticks; exact two-point fit has no independent residual degree of freedom.',
            'cross_axis_rotation_or_shear_verified':False,
            'five_render_pixel_sensitivity_equivalent_m':{'longitude':abs(geod.inv(85.45,28.3,85.45+cfg['digitising_sensitivity_pixels']*fits['longitude'][0],28.3)[2]),
                                                        'latitude':abs(geod.inv(85.45,28.3,85.45,28.3+cfg['digitising_sensitivity_pixels']*fits['latitude'][0])[2])},
            'sensitivity_is_accuracy_bound':False,'original_map_positional_accuracy_m':None,'source_datum_error_m':None,
            'feature_identification_error_m':None,'search_padding_m':pad,'padding_is_confidence_bound':False,
            'outcome':'adoptable_with_explicit_role_search_only; not acceptable as event truth or survey geometry'}
    save(R/'results/georeference_review.json',review)
    manifest=ROOT/'track_b/audit/stage4/round2/baseline_manifest.json'
    evidence={'version':cfg['version'],'generated_at_utc':datetime.now(timezone.utc).isoformat(),
              'event_id':'B20260826_Chhochen','physical_phase':'retrospective_search_geometry','time_utc':None,'time_uncertainty':None,
              'space_object':{'crs':'OGC:CRS84 (GeoJSON longitude,latitude)','source_datum_assumption':cfg['datum_assumption'],
                              'bbox_west_south_east_north':list(aoi.bounds),'area_m2_in_epsg32645':aoi_utm.area,
                              'positional_uncertainty_m':None,'original_map_accuracy_m':None},
              'variable_semantics':{'geometry':'search_only; not a release polygon','pixel_axis':'x right/y down; crop coordinates'},
              'data_role':'exploration','evidence_status':'candidate','forecast_reference_time':None,'issue_time':None,
              'valid_time':None,'available_time':None,'retrospective_not_pre_event_information':True,
              'input_version':{'baseline_commit':'76ee1532cb2acf36fb82c5f4749a4288507dfcc8','manifest_sha256':digest(manifest),
                               'config_sha256':digest(config_path),'script_sha256':digest(Path(__file__)),
                               'pdf_sha256':digest(ROOT/cfg['source_pdf']),'render_crop_sha256':digest(ROOT/cfg['crop_image'])},
              'reading_scope':'Actually opened full rendered PDF page6 Fig.1/caption and 300dpi panel-c plus longitude-tick crops; axis labels and three search anchors visually identified.',
              'source_doi':'10.1007/s11629-026-1482-y','source_pdf_page':6,'anchors_assumed_wgs84_lon_lat':anchors,
              'review':review,'advisor_review_status':'pending','q2_delivery_status':'not_claimed; advisor reads and distributes',
              'search_aoi_sha256':digest(R/'results/search_aoi.geojson')}
    save(R/'results/search_aoi_evidence.json',evidence)
    print(json.dumps({'aoi_sha256':evidence['search_aoi_sha256'],'evidence_sha256':digest(R/'results/search_aoi_evidence.json'),
                      'bounds':list(aoi.bounds),'area_km2':aoi_utm.area/1e6,'longitude_holdout_m':held_error},ensure_ascii=False))


if __name__=='__main__': main()
