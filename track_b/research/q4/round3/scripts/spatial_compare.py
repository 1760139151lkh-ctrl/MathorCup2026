from pathlib import Path
import rasterio,json,hashlib
from rasterio.warp import reproject,Resampling
from rasterio.transform import Affine
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
R=Path(__file__).resolve().parents[1];W=Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4');C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');p=W/'track_b/data/processed/spatial/dem_utm45_30m.tif'
with np.load(R/'results/spatial_inputs_60m.npz') as f:z=f['z'];aff=Affine(*f['transform'][:6]);mask=f['source_mask'].astype(bool);x=f['x'];y=f['y']
sup=np.full_like(z,-9999)
with rasterio.open(p) as s:reproject(rasterio.band(s,1),sup,src_transform=s.transform,src_crs=s.crs,dst_transform=aff,dst_crs='EPSG:32645',dst_nodata=-9999,resampling=Resampling.bilinear)
diff=z-sup
stats={}
for name,m in [('common_domain',(sup!=-9999)&(z!=-9999)),('candidate_source',mask&(sup!=-9999)&(z!=-9999))]:
 d=diff[m];stats[name]={'n':int(len(d)),'mean_new_minus_supplied_m':float(d.mean()),'median_m':float(np.median(d)),'rmse_m':float(np.sqrt(np.mean(d*d))),'p05_m':float(np.percentile(d,5)),'p95_m':float(np.percentile(d,95)),'min_m':float(d.min()),'max_m':float(d.max())}
out={'version':'q4-r3-dem-comparison-v1','new_source':'Copernicus GLO-30 AWS 2021 release','supplied_source':str(p.relative_to(W)),'supplied_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'grid':'same 60m EPSG32645 grid; each bilinear; no bias correction','difference':'new Copernicus - supplied regional DEM','statistics':stats,'interpretation':'Differences include unknown supplied product/epoch/baseline and interpolation; not temporal glacier elevation change or a validated vertical correction; original source independence unestablished'}
(R/'results/spatial_dem_comparison.json').write_text(json.dumps(out,indent=2)+'\n')
fig,ax=plt.subplots(figsize=(10,5));im=ax.imshow(diff,extent=[x[0]-30,x[-1]+30,y[-1]-30,y[0]+30],vmin=-80,vmax=80,cmap='RdBu_r');ax.contour(x,y,mask.astype(float),levels=[.5],colors='black');ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.0f}'));ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f'{v/1000:.0f}'));ax.set_xlabel('UTM45N easting (km)');ax.set_ylabel('northing (km)');ax.set_title('New product-identifiable Copernicus minus supplied DEM\nNot interpreted as temporal surface change');fig.colorbar(im,ax=ax,label='height difference (m), display clipped +/-80');fig.tight_layout();fig.savefig(R/'figures/spatial_dem_comparison.png',dpi=160);plt.close(fig);print(json.dumps(stats,indent=2))
