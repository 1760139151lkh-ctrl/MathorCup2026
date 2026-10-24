#!/usr/bin/env python3
"""Read only the advisor-delivered Q4 geometry and record weather support."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from pyproj import Transformer,Geod
import rasterio
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]

def main():
    p=R/'inputs/q4/bundle_q4-r3-spatial-copdem-v1-frozen-export/bundle.json'
    b=json.loads(p.read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()=='b6c02508acbe7bf131a0414ef7a90cafef2c5580597e2bc3b6f990e6892c4955'
    checked=[];dems=[]
    for f in b['files']:
        path=Path(f['path']);path=path if path.is_absolute() else ROOT/path
        assert path.stat().st_size==f['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==f['sha256']
        checked.append(f)
        if f['role'].startswith('primary_dem'):
            with rasterio.open(path) as src:
                a=src.read(1,masked=True);dems.append(dict(role=f['role'],crs=src.crs.to_string(),shape=list(a.shape),finite_cells=int(np.isfinite(a.filled(np.nan)).sum()),bounds=list(src.bounds),resolution=list(src.res)))
    lon,lat=Transformer.from_crs(32645,4326,always_xy=True).transform(*b['source_centroid_utm'])
    grid=pd.read_csv(R/'inputs/weather/gfs_hourly_source_grid.csv',usecols=['latitude','longitude']).drop_duplicates()
    grid['distance_m']=[Geod(ellps='WGS84').inv(lon,lat,x.longitude,x.latitude)[2] for x in grid.itertuples()]
    near=grid.sort_values('distance_m').iloc[0]
    result=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),geometry_version=b['geometry_version'],bundle_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
       verified_files=checked,dem_read_checks=dems,conditional_source_centroid_lon_lat=[lon,lat],
       nearest_GFS_grid_centre=dict(latitude=float(near.latitude),longitude=float(near.longitude),distance_m=float(near.distance_m)),
       weather_grid_spacing_degrees=.25,source_raster_areas_m2={k:v['source_raster_area_m2'] for k,v in b['grids'].items()},
       evaluation_stratum='conditional_scenario',limitations=['Source is a computational candidate, not an accepted release boundary',
       'GFS 0.25 degree cells and regional station are environmental background, not source-slope thermohydrology measurements',
       'COPDEM acquisition2011-2015/release2021 is not 2026 event topography; EGM2008 height reference',
       'No propagation delay supplied yet; geometry does not establish initiation or arrival truth'])
    out=R/'results/spatial_context.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['geometry_version','conditional_source_centroid_lon_lat','nearest_GFS_grid_centre']}))

if __name__=='__main__':main()
