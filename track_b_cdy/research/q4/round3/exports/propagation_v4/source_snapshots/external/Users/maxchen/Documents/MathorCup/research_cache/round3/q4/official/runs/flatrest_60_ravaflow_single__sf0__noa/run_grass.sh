#!/bin/bash
set -euo pipefail
r.in.gdal --overwrite input=/work/inputs/flatrest/dem.tif output=elev
r.in.gdal --overwrite input=/work/inputs/flatrest/release.tif output=release
g.region -s raster=elev
r.avaflow.40G -e prefix=flatrest_60_ravaflow_single__sf0__noa cellsize=60 elevation=elev ctopo=0 csurface=0 centrainment=0 cstopping=0 cmelt=0 gravity=9.81 limiter=1 time=20,100 cfl=0.5,0.01 thresholds=0.1,10000,10000,0.1,0.000001 phases=1 hrelease=release density=2105 friction=35,8.530765609948133,-1000 viscosity=-7
