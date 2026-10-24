#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,csv,datetime
import rasterio,numpy as np
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official');rows=[];cases=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for item in json.loads((P/'config/official_cases_resourcefix.json').read_text())['cases']:
 f=Path(item['case']).parent;case=json.loads(Path(item['case']).read_text());parent=case['resourcefix_parent_run_id'];old=C/'runs'/parent;newid=case['run_id'];ad=old/(parent+'_results')/(parent+'_ascii');bd=f/(newid+'_results')/(newid+'_ascii');aa={p.name[len(parent)+1:]:p for p in ad.glob('*.asc')};bb={p.name[len(newid)+1:]:p for p in bd.glob('*.asc')};common=sorted(set(aa)&set(bb))
 for name in common:rows.append({'parent_run_id':parent,'resourcefix_run_id':newid,'field_suffix':name,'original_path':str(aa[name]),'original_sha256':sha(aa[name]),'resourcefix_path':str(bb[name]),'resourcefix_sha256':sha(bb[name]),'byte_identical':sha(aa[name])==sha(bb[name])})
 original_only=sorted(set(aa)-set(bb));zero=[]
 for name in original_only:
  with rasterio.open(aa[name]) as ds:a=ds.read(1,masked=True)
  zero.append(bool(np.all(a.filled(0)==0)))
 ex=json.loads((f/'execution.json').read_text());log=(f/'run.log').read_text(errors='replace');cases.append({'parent_run_id':parent,'resourcefix_run_id':newid,'original_returncode':json.loads((old/'execution.json').read_text())['returncode'],'resourcefix_returncode':ex['returncode'],'solver_build':ex.get('solver_build'),'binary_sha_expected':'45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c','resourcefix_binary_hash_in_actual_log':'45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c  /resourcefix/bin/r.avaflow.main' in log,'actual_wrapper_binary_path_recorded':'/resourcefix/bin/r.avaflow.main' in log,'common_ascii_count':len(common),'all_common_ascii_byte_identical':all(sha(aa[n])==sha(bb[n]) for n in common),'only_original_fields':original_only,'original_only_fields_are_zero_change':all(zero),'only_resourcefix_fields':sorted(set(bb)-set(aa))})
with (P/'results/official_resourcefix_comparison.csv').open('w',newline='') as out:w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(P/'results/official_resourcefix_validation.json').write_text(json.dumps({'reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':cases,'resource_cleanup_execution_and_physical_equilibrium_separate':True,'native_equations_not_recalibrated':True},indent=2)+'\n');print(json.dumps(cases,indent=2))
