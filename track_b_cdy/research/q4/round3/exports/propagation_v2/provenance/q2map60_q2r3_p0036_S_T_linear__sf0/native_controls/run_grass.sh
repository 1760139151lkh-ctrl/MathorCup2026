#!/bin/bash
set -euo pipefail
command -v r.avaflow.main
sha256sum "$(command -v r.avaflow.main)"
r.in.gdal --overwrite input=/work/inputs/copdem_60m/dem.tif output=elev
r.in.gdal --overwrite input=/work/inputs/q2mapped/q2r3-p0036-S_T-linear/release.tif output=release
g.region -s raster=elev
r.avaflow.40G -ae prefix=q2map60_q2r3_p0036_S_T_linear__sf0 cellsize=60.0 elevation=elev ctopo=0 csurface=0 centrainment=0 cstopping=0 cmelt=0 gravity=9.81 limiter=1 time=20,1800 cfl=0.5,0.01 thresholds=0.1,10000,10000,0.1,0.000001 phases=1 hrelease=release density=2158.626225168872 friction=35,8.530765609948133,-1000 viscosity=-7
