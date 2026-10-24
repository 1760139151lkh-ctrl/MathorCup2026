#!/usr/bin/env python3
"""One fixed DClaw domain sensitivity; core terrain/source preserved, not infinite-domain proof."""
from pathlib import Path
import json,hashlib,shutil,datetime
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
bp=P/'results/extended_domain_bundle.json';b=json.loads(bp.read_text());ref=json.loads((C/'runs/copdem_120_dclaw_ref/case.json').read_text());dest=C/'inputs/extended120';dest.mkdir(parents=True,exist_ok=True)
for f in b['files']:
 src=Path(f['path']);assert sha(src)==f['sha256'];name='dem.tif' if f['role']=='extended_dem' else 'release.tif';shutil.copy2(src,dest/name)
protocol={'version':'q4-r3-official-extended-domain-v1','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'before_native_extended_run':True,'upstream_bundle_path':str(bp),'upstream_bundle_sha256':sha(bp),'method':'same DClaw m0/kref/pinit/mu andV as120 reference, all4 domain boundaries extended10080m, original core values exactly retained','old_domain':'boundary affected beforepaperarrival; keep original result andnumerical limitations','not_infinite_domain_convergence_proof':True};(P/'config/official_extended_protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
ref.update({'run_id':'dclaw_ref_extended120','scenario_id':'conditional_h15_mu0.15_xiNone__extended_domain','geometry_version':b['version'],'dem':str(dest/'dem.tif'),'dem_sha256':sha(dest/'dem.tif'),'release':str(dest/'release.tif'),'release_sha256':sha(dest/'release.tif'),'release_grid_volume_m3':b['release_grid_volume_m3'],'domain_comparison_parent_run_id':'copdem_120_dclaw_ref','extended_domain_bundle_sha256':sha(bp)})
f=C/'runs'/ref['run_id'];f.mkdir(parents=True,exist_ok=True);cp=f/'case.json';cp.write_text(json.dumps(ref,indent=2)+'\n');(P/'config/official_cases_extended.json').write_text(json.dumps({'cases':[{'run_id':ref['run_id'],'case':str(cp)}]},indent=2)+'\n')
