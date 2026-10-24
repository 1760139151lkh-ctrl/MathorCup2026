from pathlib import Path
import json,hashlib,datetime,ast
import numpy as np
from shapely.geometry import shape
R=Path(__file__).resolve().parents[1];W=Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4');C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial');checks=[]
def add(name,ok,details):checks.append({'name':name,'passed':bool(ok),'details':details})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
bp=R/'exports/geometry_bundle.json';bb=json.loads(bp.read_text());expected='64cd8369ce79d599890d4ed726a87833b63f64472c4dbea54408e39e79a40561';add('v1_bundle_original_bytes',sha(bp)==expected,sha(bp))
for rec in bb['files']:
 p=Path(rec['path']);p=p if p.is_absolute() else W/p;add('v1_bound_file_'+p.name,p.exists() and p.stat().st_size==rec['bytes'] and sha(p)==rec['sha256'],rec['path'])
for res,sh,count in [(60,(154,300),257),(120,(77,150),67)]:
 with np.load(R/f'results/spatial_inputs_{res}m.npz') as f:
  add(f'grid_{res}',f['z'].shape==sh and np.isfinite(f['z']).all() and (f['z']!=-9999).all() and int(f['source_mask'].astype(bool).sum())==count,{'shape':list(f['z'].shape),'source_cells':int(f['source_mask'].astype(bool).sum())})
for name in ['computational_geometries.geojson','spatial_edge_connectors_v2.geojson','spatial_osm_objects_v2.geojson','spatial_spectral_change_candidates.geojson']:
 g=json.loads((R/'results'/name).read_text());invalid=[f.get('id',i) for i,f in enumerate(g['features']) if not shape(f['geometry']).is_valid];add('geometry_valid_'+name,len(invalid)==0,{'feature_count':len(g['features']),'invalid':invalid})
e=json.loads((R/'results/spatial_edge_review_v2.json').read_text());add('local_connectors_no_silent_uphill',all(x['cumulative_ascent_m']==0 and x['strict_nonincreasing_height_reaches_goal'] for x in e['stats']),[x['path_length_m'] for x in e['stats']])
o=json.loads((R/'results/spatial_optical_quality.json').read_text());ok=len(o['scenes'])==3
for scene in o['scenes']:
 for scope,r in scene['quality'].items():
  vals=sum(r['class_counts'].values());ok=ok and vals==r['n'] and all(0<=v<=1 for k,v in r.items() if k.endswith('fraction'))
add('three_scene_SCL_denominators',ok,{'scene_count':len(o['scenes']),'source_dark2':[s['quality']['paper_source']['topographic_dark_2_fraction'] for s in o['scenes']]})
q=json.loads((R/'results/spatial_radiometry_check.json').read_text());add('same_product_conversion_nonfloor',all(r['product_uri_equal'] and r['C1_minus_legacy_DN_nonfloor_unique']==[1000] and r['max_abs_nonfloor_reflectance_residual']<1e-12 for r in q['results']),{'windows':len(q['results']),'pixels_per_window':10000})
idx=json.loads((R/'results/spatial_spectral_mask_index.json').read_text());mp=Path(idx['files'][0]['path']);add('spectral_mask_frozen_hash',sha(mp)=='b350e6022beadd7f0bbecd53f29415b3d15fbc756cd90a33d595509ed9b0562b',sha(mp))
with np.load(mp) as f:
 add('spectral_mask_schema_and_subset',f['valid_pair'].dtype==bool and f['valid_pair'].shape==(924,1800) and np.all(~f['change_candidate']|f['valid_pair']) and np.all(~f['change_candidate_ge9']|f['change_candidate']) and f['crs'].item()=='EPSG:32645',{'shape':list(f['valid_pair'].shape),'valid_pair_pixels':int(f['valid_pair'].sum()),'candidate_change_pixels':int(f['change_candidate'].sum()),'candidate_ge9_pixels':int(f['change_candidate_ge9'].sum())})
bad=json.loads((R/'results/spatial_spectral_naive_offset_rejected.json').read_text());add('failed_conversion_explicitly_rejected',bad['not_for_use'] and bad['status']=='REJECTED_RADIOMETRIC_CONVERSION',bad['status'])
for p in (R/'scripts').glob('spatial_*.py'):
 ast.parse(p.read_text());add('python_AST_'+p.name,True,'parsed, no __pycache__ written')
v=R/'results/spatial_visual_review.json'
if v.exists():
 va=json.loads(v.read_text());add('viewed_figure_hashes',all(sha(W/q['path'])==q['sha256'] for q in va['figures']),len(va['figures']))
result={'schema_version':1,'generated_at_utc':datetime.datetime.now(datetime.UTC).isoformat(),'scope':'spatial packet only; does not test model solvers or establish event truth','all_passed':all(q['passed'] for q in checks),'checks':checks};(R/'results/spatial_validation.json').write_text(json.dumps(result,indent=2)+'\n');print('spatial checks',len(checks),'passed',sum(q['passed'] for q in checks));assert result['all_passed'],[q for q in checks if not q['passed']]
# Source/input index: no output/self entries; observed cache artifacts distinguish full originals and derived windows.
context={'input_version':{'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','baseline_manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'},'event_id':'B20260826_Chhochen','physical_phase':'spatial_background_and_conditional_propagation_geometry','time_utc':None,'time_uncertainty':{'reason':'event geometry measurement time unverified; scene times separately in source logs'},'space_object':{'geometry_version':'q4-r3-spatial-copdem-v1 plus explicitly separate v2 supplements','crs':'CRS84 geometry / EPSG32645 metric grids','positional_uncertainty_m':None},'variable_semantics':{'DEM':'metres EGM2008 for Copernicus; supplied DEM datum unknown','NDVI':'unitless; corrected legacy scale only after C1 check; paired SCL4/5 DN>1','QC':'classwise SCL, all missing masks retained'},'forecast_reference_time':None,'issue_time':None,'valid_time':None,'available_time':None,'data_role':'exploration','downstream_model_use':'conditional scenarios require separate supplied release state','evidence_status':'not accepted event geometry or independent event validation','evaluation_stratum':'local_observational','downstream_evaluation_stratum':'conditional_scenario','null_policy':'not applicable forecast times or unknown historical availability retained null; file retrieval UTC does not imply issue-time availability'}
def rec(p,role):return {'path':str(p.relative_to(W)) if p.is_relative_to(W) else str(p),'bytes':p.stat().st_size,'sha256':sha(p),'role':role}
cache=[rec(p,'immutable acquired or derived spatial cache; provenance and actual read scope in dedicated source records') for p in sorted(C.iterdir()) if p.is_file()]
sources=[rec(p,'acquisition/read receipt') for p in sorted((R/'sources').glob('spatial_*.json'))]
protocols=[rec(p,'precalculation protocol or explicit QA revision') for p in sorted((R/'config').glob('spatial_*.json'))]
fixed=[rec(W/'track_b/research/q4/round2/results/geometry_candidates.geojson','frozen retrospective paper geometry candidates'),rec(W/'track_b/data/processed/spatial/dem_utm45_30m.tif','supplied unknown-product DEM derived grid for new comparison only')]
source_index={'schema_version':1,'generated_at_utc':datetime.datetime.now(datetime.UTC).isoformat(),'context':context,'cache_files':cache,'source_logs':sources,'protocols':protocols,'fixed_inputs':fixed,'exclusions':['this source index','output supplement bundle','future audit/operational files','other question active outputs','runtime'],'bytes_semantics':'cache SHA is complete actual cached artifact, not full remote source COG SHA for byte-window reads; HTTP complete response and interpreted pixel windows are separately recorded'}
(R/'results/spatial_source_index.json').write_text(json.dumps(source_index,indent=2)+'\n')
# Versioned supplemental delivery excludes itself and original v1 files, which remain separately immutable.
files=[p for p in (R/'results').glob('spatial_*') if p.is_file() and p.name not in ['spatial_inputs_60m.npz','spatial_inputs_120m.npz','spatial_paths.csv','spatial_supplement_bundle_v2.json']]+[p for p in (R/'figures').glob('spatial_*') if p.name!='spatial_terrain_paths.png']+[R/'spatial_report.md']
bundle={'bundle_version':'q4-r3-spatial-supplement-v2','producer_question':'q4','input_version':context['input_version'],'evaluation_stratum':'conditional_scenario','observation_role':'supplement includes explicitly separated local observational proxies','files':[rec(p,'spatial supplement; per-file evidence boundaries in report') for p in sorted(files)],'limitations':['No accepted event failure boundary, actual path, protected-facility extent, or causal inundation footprint','Spectral agreement is exploration only; rejected offset trial cannot be used','OSM object representations are not independent entities; last edit not observation time','Original v1 geometry bundle and bound artifacts remain byte unchanged']}
(R/'results/spatial_supplement_bundle_v2.json').write_text(json.dumps(bundle,indent=2)+'\n');print('source index',len(cache),'cache files;',len(files),'supplement files')
