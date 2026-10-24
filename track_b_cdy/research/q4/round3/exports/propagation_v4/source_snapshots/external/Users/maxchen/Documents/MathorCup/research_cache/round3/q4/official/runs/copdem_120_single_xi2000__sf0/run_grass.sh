#!/bin/bash
set -euo pipefail
command -v r.avaflow.main
sha256sum "$(command -v r.avaflow.main)"
r.in.gdal --overwrite input=/work/inputs/copdem_120m/dem.tif output=elev
r.in.gdal --overwrite input=/work/inputs/copdem_120m/release_15m.tif output=release
g.region -s raster=elev
r.avaflow.40G -ae prefix=copdem_120_single_xi2000__sf0 cellsize=120.0 elevation=elev ctopo=0 csurface=0 centrainment=0 cstopping=0 cmelt=0 gravity=9.81 limiter=1 time=20,1800 cfl=0.5,0.01 thresholds=0.1,10000,10000,0.1,0.000001 phases=1 hrelease=release density=2105 friction=35,8.530765609948133,-2000 viscosity=-7
