#!/usr/bin/env python3
"""Trace candidate map objects and diagnose raster support, never event truth."""
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import numpy as np
from PIL import Image
from pyproj import Transformer
import rasterio
from rasterio.features import shapes,geometry_mask,geometry_window
from rasterio.errors import WindowError
from shapely import transform as shapely_transform
from shapely.geometry import Polygon,Point,LineString,box,shape,mapping
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[5]
R=ROOT/'track_b/research/q4/round2'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    cfgpath=R/'config/geometry_trace.json';cfg=json.loads(cfgpath.read_text())
    mapcfg=json.loads((R/'config/map_digitisation.json').read_text())
    review=json.loads((R/'results/georeference_review.json').read_text())
    fits=review['fit_coefficients']
    def ll(p):return [float(np.polyval(fits['longitude'],p[0])),float(np.polyval(fits['latitude'],p[1]))]
    forward=Transformer.from_crs(4326,32645,always_xy=True).transform
    def project(g):return shapely_transform(g,forward,interleaved=False)
    source=Polygon([ll(p) for p in cfg['source_outline_crop_pixels']])
    target=Point(ll(cfg['target_port_symbol_crop_pixels']))
    junction=Point(ll(cfg['junction_crop_pixels']))
    upper=LineString([ll(p) for p in cfg['chhochen_blue_river_crop_pixels']])
    lower=LineString([ll(p) for p in cfg['lende_blue_river_crop_pixels']])
    assert source.is_valid and upper.is_valid and lower.is_valid
    objects=[('paper_source_outline','source_outline',source),('paper_port_symbol','target_representative_point',target),
             ('paper_junction','junction',junction),('paper_chhochen_blue_trace','channel_candidate',upper),
             ('paper_lende_blue_trace','channel_candidate',lower)]
    georefsha=digest(R/'results/georeference_review.json')
    features=[];rows=[]
    for ident,kind,g in objects:
        props={'space_id':ident,'object_kind':kind,'version':cfg['version'],'event_id':'B20260826_Chhochen',
               'data_role':'exploration','evidence_status':'candidate','geometry_status':'retrospective_reconstruction_candidate',
               'accepted_event_geometry':False,'source_pdf_page':6,'source_doi':'10.1007/s11629-026-1482-y',
               'georeference_review_sha256':georefsha,'positional_uncertainty_m':None,'phase_time_utc':None,
               'source_datum_verified':False,'target_definition':cfg['target_definition'] if kind=='target_representative_point' else None,
               'actual_failure_area_or_path_distance':None}
        features.append({'type':'Feature','id':ident,'properties':props,'geometry':mapping(g)})
        rows.append({'space_id':ident,'object_kind':kind,'status':'retrospective_reconstruction_candidate',
                     'source':'JMS Fig.1c page6; original map datum/projection unknown',
                     'crs_assumption':'CRS84 WGS84 longitude-latitude for candidate mapping only',
                     'original_map_accuracy_m':'unknown','feature_identification_error_m':'unknown',
                     'acceptable_use':'search_and_candidate_coverage_only','excluded_use':'event_truth_release_volume_real_protection_distance',
                     'next_action':'independent georeferenced imagery or authoritative object definition and river data'})
    out=R/'results/geometry_candidates.geojson';save(out,{'type':'FeatureCollection','name':cfg['version'],'features':features})
    with (R/'results/geometry_evidence.csv').open('w',newline='',encoding='utf-8') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    aoi=shape(json.loads((R/'results/search_aoi.geojson').read_text())['features'][0]['geometry'])
    assert all(aoi.covers(g) for _,_,g in objects)
    channel=unary_union([project(upper),project(lower)])
    footprints={}; raster_inputs=[]; coverage=[]
    raster_paths={'independent_projected_DEM':'track_b/data/processed/spatial/dem_utm45_30m.tif',
                  'NC_DEM_parameter_rectangle':'track_b/data/processed/spatial/nc_dem_native_grid.tif'}
    projected_image=None;projected_bounds=None
    for name,rel in raster_paths.items():
        with rasterio.open(ROOT/rel) as ds:
            a=ds.read(1,masked=True);valid=(~np.ma.getmaskarray(a)) & np.isfinite(a.data)
            assert ds.crs.to_epsg()==32645
            fp=unary_union([shape(g) for g,value in shapes(valid.astype('uint8'),mask=valid,transform=ds.transform) if value==1])
            footprints[name]=fp
            raster_inputs.append({'name':name,'path':rel,'sha256':digest(ROOT/rel),'valid_pixels':int(valid.sum()),
                                  'total_pixels':int(valid.size),'crs':str(ds.crs),'bounds':list(ds.bounds)})
            if name=='independent_projected_DEM': projected_image=a;projected_bounds=list(ds.bounds)
            for half_width in cfg['candidate_corridor_half_widths_m']:
                corridor=channel.buffer(half_width)
                overlap=corridor.intersection(fp)
                fully_covered=fp.covers(corridor)
                raw_area_residual=corridor.area-overlap.area
                covered_area=corridor.area if fully_covered else min(corridor.area,max(0.0,overlap.area))
                try:
                    win=geometry_window(ds,[mapping(corridor)])
                    values=ds.read(1,window=win,masked=True)
                    inside=geometry_mask([mapping(corridor)],out_shape=values.shape,transform=ds.window_transform(win),invert=True)
                    good=(~np.ma.getmaskarray(values)) & np.isfinite(values.data)
                    inside_count=int(inside.sum());good_count=int((inside&good).sum())
                except WindowError: inside_count=0;good_count=0
                coverage.append({'raster':name,'corridor_half_width_m':half_width,'candidate_corridor_area_m2':corridor.area,
                                 'area_covered_m2':covered_area,'area_coverage_fraction':covered_area/corridor.area,
                                 'all_corridor_covered_by_valid_footprint':fully_covered,
                                 'boundary_margin_m_if_fully_covered':corridor.distance(fp.boundary) if fully_covered else None,
                                 'inside_raster_pixel_centres':inside_count,'valid_inside_pixel_centres':good_count,
                                 'internal_invalid_inside_pixel_centres':inside_count-good_count,
                                 'area_outside_valid_footprint_m2':corridor.area-covered_area,
                                 'raw_geos_area_residual_m2':raw_area_residual,
                                 'floating_area_policy':'Use exact full area when covers is true; retain raw GEOS roundoff residual separately.'})
    object_support=[]
    for ident,kind,g in objects:
        pg=project(g)
        object_support.append({'space_id':ident,'independent_DEM_fully_covers_candidate':footprints['independent_projected_DEM'].covers(pg),
                               'NC_DEM_fully_covers_candidate':footprints['NC_DEM_parameter_rectangle'].covers(pg),
                               'candidate_trace_length_m_not_actual_distance':pg.length if isinstance(g,LineString) else None})
    gap=project(source).distance(project(upper))
    context={'input_version':{'baseline_commit':'76ee1532cb2acf36fb82c5f4749a4288507dfcc8',
                             'manifest_sha256':digest(ROOT/'track_b/audit/stage4/round2/baseline_manifest.json'),
                             'geometry_sha256':digest(out),'config_sha256':digest(cfgpath),'script_sha256':digest(Path(__file__))},
             'event_id':'B20260826_Chhochen','physical_phase':'retrospective_candidate_corridor',
             'time_utc':None,'time_uncertainty':None,'space_object':{'crs':'EPSG:32645','event_geometry_accepted':False},
             'variable_semantics':{'coverage':'geometric valid-grid support only; corridor widths are diagnostic choices'},
             'available_time':None,'forecast_reference_time':None,'issue_time':None,'valid_time':None,
             'data_role':'exploration','evidence_status':'candidate'}
    result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),**context,'raster_inputs':raster_inputs,
            'candidate_objects':object_support,'candidate_corridors':coverage,'search_aoi_covers_all_candidate_objects':True,
            'source_outline_to_blue_river_candidate_gap_m':gap,'source_to_channel_connection_verified':False,
            'actual_source_to_target_continuity_verified':False,'actual_propagation_distance_m':None,
            'longitudinal_profile_generated':False,'profile_reason':'River trace is a paper reconstruction candidate, not an independently verified centreline.',
            'interpretation':'Independent DEM supports these candidate corridors; coverage is not event-geometry, terrain-epoch, datum or dynamics validation.'}
    save(R/'results/corridor_coverage.json',result)
    # Two scientific figures: readable axis constraints and candidate support.
    im=np.asarray(Image.open(ROOT/mapcfg['crop_image']))
    fig,ax=plt.subplots(figsize=(13,8));ax.imshow(im)
    for c in mapcfg['controls']:
        ax.plot(c['x'],c['y'],'r+',markersize=12,markeredgewidth=2)
        offset=(8,20) if c['axis']=='longitude' else (16,0)
        ax.annotate(c['id'],(c['x'],c['y']),xytext=offset,textcoords='offset points',fontsize=10,color='black',bbox=dict(facecolor='white',alpha=.8,edgecolor='none'))
    ax.set(xlabel='Crop pixel x',ylabel='Crop pixel y (down)',title='Fig.1c axis constraints: longitude holdout; latitude has no independent holdout')
    fig.text(.5,.02,'Axis ticks constrain one coordinate only. Original map datum and positional accuracy remain unknown.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.96));fig.savefig(R/'figures/georeference_controls.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(15,7))
    ax=axs[0];ax.imshow(im)
    ax.add_patch(MplPolygon(cfg['source_outline_crop_pixels'],fill=False,edgecolor='#d73027',linewidth=2,label='Paper source-outline candidate'))
    for key,label,color in [('chhochen_blue_river_crop_pixels','Paper Chhochen trace','#0069b4'),('lende_blue_river_crop_pixels','Paper Lende trace','#00a0b0')]:
        p=np.array(cfg[key]);ax.plot(p[:,0],p[:,1],color=color,linewidth=2,label=label)
    p=cfg['target_port_symbol_crop_pixels'];ax.plot(*p,'o',color='#c00080',label='Port symbol representative candidate')
    ax.set(xlim=(63,1647),ylim=(1018,50),xlabel='Fig.1c crop x (pixels)',ylabel='Fig.1c crop y (pixels)',title='Retrospective map reconstruction candidates')
    ax.legend(fontsize=8,loc='upper left')
    ax=axs[1];b=projected_bounds
    image=ax.imshow(projected_image,extent=[b[0]/1000,b[2]/1000,b[1]/1000,b[3]/1000],cmap='terrain',origin='upper')
    for ident,kind,g in objects:
        pg=project(g)
        if isinstance(pg,Polygon):x,y=pg.exterior.xy;ax.plot(np.array(x)/1000,np.array(y)/1000,color='#d73027',linewidth=2)
        elif isinstance(pg,LineString):x,y=pg.xy;ax.plot(np.array(x)/1000,np.array(y)/1000,color='#0069b4',linewidth=2)
        elif kind=='target_representative_point':ax.plot(pg.x/1000,pg.y/1000,'o',color='#c00080')
    ncfp=footprints['NC_DEM_parameter_rectangle'];x,y=ncfp.exterior.xy;ax.plot(np.array(x)/1000,np.array(y)/1000,color='#e67e00',linestyle='--',label='NC parameter DEM extent')
    aoip=project(aoi);x,y=aoip.exterior.xy;ax.plot(np.array(x)/1000,np.array(y)/1000,color='black',linestyle=':',label='Search-only AOI')
    bb=aoip.bounds;ax.set(xlim=(bb[0]/1000-.5,bb[2]/1000+.5),ylim=(bb[1]/1000-.5,bb[3]/1000+.5),
                        xlabel='UTM45N easting (km)',ylabel='UTM45N northing (km)',title='Independent DEM support for candidate geometry')
    fig.colorbar(image,ax=ax,label='Elevation (m; vertical datum unknown)',shrink=.7);ax.legend(fontsize=8,loc='upper left')
    fig.text(.5,.025,'Candidates are not verified release/river/target truth. No source-to-channel connector, actual propagation distance or event profile is inferred.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.06,1,.96));fig.savefig(R/'figures/candidate_geometry_coverage.png',dpi=160);plt.close(fig)
    print(json.dumps({'geometry_sha256':digest(out),'object_support':object_support,'corridor_coverage':coverage,
                      'source_to_channel_candidate_gap_m':gap},ensure_ascii=False))


if __name__=='__main__':main()
