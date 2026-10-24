#!/bin/bash
set -euo pipefail
command -v r.avaflow.main
sha256sum "$(command -v r.avaflow.main)"
r.in.gdal --overwrite input=/work/inputs/copdem_120m/dem.tif output=elev
r.in.gdal --overwrite input=/work/inputs/copdem_120m/release_15m.tif output=release
g.region -s raster=elev
r.mapcalc --overwrite expression="release1=release*0.7"
r.mapcalc --overwrite expression="release2=release*0"
r.mapcalc --overwrite expression="release3=release*0.3"
r.avaflow.40G -ae prefix=composite_rock_water_120__sf0 cellsize=120.0 elevation=elev ctopo=0 csurface=0 centrainment=0 cstopping=0 cmelt=0 gravity=9.81 limiter=1 time=20,1800 cfl=0.5,0.01 thresholds=0.1,10000,10000,0.1,0.000001 phases=3 clayers=0 hrelease1=release1 hrelease2=release2 hrelease3=release3 density=2700,1850,1000 friction=35,20,0,8.530765609948133,8.530765609948133,0,-1000,-1000,-1000 viscosity=-7,-7,-7 transformation=0,0,0 drag=1,3,1,0.1,1,1 virtualmass=10,0.12,1
