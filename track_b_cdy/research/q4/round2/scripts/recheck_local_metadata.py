#!/usr/bin/env python3
"""Offline recheck of local DEM metadata; no raster/height modification."""
import hashlib
import html
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import rasterio
import xarray as xr

ROOT=Path(__file__).resolve().parents[5]
R=ROOT/'track_b/research/q4/round2'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    base=ROOT/'04_B赛道/07_DEM（2026-08-26）'
    xml=base/'DEM.tif.xml';raw=xml.read_text(encoding='utf-8-sig')
    tree=ET.fromstring(raw);dates=[];processes=[]
    for e in tree.iter():
        tag=e.tag.split('}')[-1]
        if any(v in tag.lower() for v in ('date','time')) and e.text and len(e.text.strip())<80:
            dates.append({'tag':tag,'text':e.text.strip(),'interpretation':'metadata/processing timestamp; not accepted as observation date'})
        if tag.lower()=='process':
            processes.append({'attributes':{k:v for k,v in e.attrib.items() if k.lower() in ('date','time','name')},
                              'contains_clip':bool(re.search(r'\bClip\b',e.text or '')),
                              'upstream_filename_present':'GeBainiDEM_30M.tif' in (e.text or '')})
    tiff=base/'DEM.tif'
    with rasterio.open(tiff) as ds:
        raster={'crs':str(ds.crs),'transform_gdal':list(ds.transform.to_gdal()),'bounds':list(ds.bounds),
                'tags':ds.tags(),'tiff_datetime':ds.tags().get('TIFFTAG_DATETIME'),'sha256':digest(tiff)}
    source=json.loads((ROOT/'track_b/data/processed/spatial/pipeline_report.json').read_text())['netcdf']['source']
    with xr.open_dataset(ROOT/source,engine='h5netcdf',decode_cf=True,decode_coords='all') as ds:
        nc={'path':source,'sha256':digest(ROOT/source),'dims':dict(ds.sizes),'time_dimension_present':'time' in ds.dims,
            'global_attributes':{k:ds.attrs[k] for k in ('title','source','Conventions','velocity_source') if k in ds.attrs},
            'dem_attributes':dict(ds.dem.attrs),'velocity_description':ds.v.attrs.get('description'),
            'velocity_epoch_not_dem_epoch':True}
    result={'purpose':'Offline metadata recheck only; no product identity or terrain epoch inferred',
            'source_xml_sha256':digest(xml),'xml_date_fields':dates,'xml_processes':processes,
            'vertical_names_from_xml':re.findall(r'(VERTCS|VDATUM)\s*\[\s*"([^"]+)"',html.unescape(html.unescape(raw))),
            'vertical_wkt_encoding_note':'The source WKT is doubly HTML-entity escaped inside XML; decode entities for semantic inspection, source bytes remain unchanged.',
            'tfw_sha256':digest(base/'DEM.tfw'),'tfw_six_values':[float(v) for v in (base/'DEM.tfw').read_text().split()],
            'aux_xml_sha256':digest(base/'DEM.tif.aux.xml'),'raster_metadata':raster,'nc_metadata':nc,
            'outcome':'product/observation_epoch/vertical_datum remain unknown; local processing chain is readable'}
    p=R/'results/local_metadata_recheck.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps({'vertical_names':result['vertical_names_from_xml'],'processes':processes,'output':str(p)},ensure_ascii=False))


if __name__=='__main__':main()
