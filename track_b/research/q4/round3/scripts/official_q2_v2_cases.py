#!/usr/bin/env python3
"""Add fixed full-mask Q2 releases without replacing compact-source v1."""
from pathlib import Path
import json,hashlib,shutil,datetime
import rasterio,numpy as np
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
pp=P/'config/q2_fullmask_integration_protocol.json';d=json.loads(pp.read_text());items=[]
(P/'config/official_q2_v2_protocol.json').write_text(json.dumps({'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before_native_runs':True,'upstream_protocol_path':str(pp),'upstream_protocol_sha256':sha(pp),'selection':d['selected_scenario_ids'],'model':'fixed official native single homogeneous equivalent, composition passive','postrelease_parameters':{'mu_basal':.15,'xi':1000},'source_and_volume':'fullmask v2 distinct from compact v1; scenario suffix and base key retained'},indent=2)+'\n')
for record in d['records']:
 dx=int(record['grid_resolution_m']);ref=json.loads((C/f'runs/copdem_{dx}_single_ref/case.json').read_text());src=Path(record['release_raster_path']);assert sha(src)==record['release_raster_sha256'];f=C/'inputs/q2fullmask'/record['scenario_id'];f.mkdir(parents=True,exist_ok=True);target=f/'release.tif';shutil.copy2(src,target)
 with rasterio.open(target) as ds:vol=float(ds.read(1).astype(float).sum()*dx*dx)
 assert abs(vol/record['actual_grid_volume_m3']-1)<1e-9
 rid='q2full_'+record['scenario_id'].replace('-','_');folder=C/'runs'/rid;folder.mkdir(parents=True,exist_ok=True);ref.update({'run_id':rid,'scenario_id':record['scenario_id'],'base_scenario_id':record['base_scenario_id'],'geometry_version':record['geometry_version'],'release_mapping_version':record['release_mapping_version'],'upstream_model_id':record['model_id'],'upstream_parameter_version':record['parameter_version'],'upstream_onset_status':record['onset_status'],'if_released_propagation':record['if_released_propagation'],'not_an_initiation_prediction':True,'release':str(target),'release_sha256':sha(target),'release_grid_volume_m3':vol,'release_thickness_m':float(record['release_thickness_vertical_m']),'bulk_density_kg_m3':float(record['density']),'source_plan_area_m2':float(record['plan_area_m2']),'passive_material_volume_fractions':json.loads(record['phase_fractions']),'passive_material_fraction_basis':'volume','phase_volume_fractions':[1],'initial_velocity_east_north_m_s':[0,0],'initiation_to_release_delay_seconds':None,'evidence_role':'conditional_cross_question_scenario','upstream_fullmask_record':record,'source_geometry_sha256':sha(pp),'extras':{}})
 (folder/'case.json').write_text(json.dumps(ref,indent=2)+'\n');items.append({'run_id':rid,'case':str(folder/'case.json')})
(P/'config/official_cases_q2fullmask.json').write_text(json.dumps({'cases':items},indent=2)+'\n');print(len(items))
