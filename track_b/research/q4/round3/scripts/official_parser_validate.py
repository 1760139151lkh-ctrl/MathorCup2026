#!/usr/bin/env python3
"""Validate native-time loss handling and hash-bound arrival interfaces, without solver reruns."""
from pathlib import Path
import importlib.util,json,csv,datetime,hashlib
import numpy as np
P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('official_analyse',P/'scripts/official_analyse.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 tests=[]
 assert m.native_ravaflow_times('','')=={};tests.append('missing native time produces empty mapping, including frame zero')
 actual='0 0 ----- ----- 0.0 9.9 0 3929 -----\n1 6 .347 517 27.3 9.930 3.83 3929.5 869\n2 7 .448 679.3 40.8 9.687 3.16 3929.9 1060'
 parsed=m.native_ravaflow_times('',actual);assert parsed=={0:0.,1:27.3,2:40.8};assert 3 not in parsed;tests.append('actual overshooting tsum retained; absent frame three not assigned nominal60s')
 assert m.native_ravaflow_times('','1 2 .1 10 20 ...')=={};tests.append('progress-only rows do not assign saved-output time')
 fields=json.loads((P/'results/official_fields.json').read_text())['fields'];index={f['run_id']:f for f in fields};checks={c['run_id']:c for c in json.loads((P/'results/official_validation.json').read_text())['checks']};bound=0
 for f in fields:
  assert sha(f['path'])==f['sha256'];d=np.load(f['path']);times=d['time_s'];assert np.all(np.diff(times)>=0);assert float(times[-1])==f['time_end_seconds']==checks[f['run_id']]['actual_last_time_seconds'];assert checks[f['run_id']]['source_fields_sha256']==f['sha256']
  if f['solver_build']=='explicit_resourcefix_build':assert f['executed_solver_source_modified'] and f['actual_binary_sha256']=='45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c' and f['readonly_addon_mount']
 for name in ['official_arrivals.csv','official_metrics.csv','official_runs.csv','official_histories.csv','official_target_arrivals_v2.csv']:
  for row in csv.DictReader((P/'results'/name).open()):
   if row['run_id'] not in index:continue
   f=index[row['run_id']]
   for key,fieldkey in [('source_fields_sha256','sha256'),('execution_sha256','execution_sha256'),('log_sha256','log_sha256')]:assert row[key]==f[fieldkey],(name,row['run_id'],key)
   if row.get('evaluation_end_time_seconds'):assert float(row['evaluation_end_time_seconds'])==f['time_end_seconds']
   bound+=1
 (P/'results/official_parser_validation.json').write_text(json.dumps({'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'parser_sha256':sha(P/'scripts/official_analyse.py'),'native_time_regressions':tests,'field_interfaces_checked':len(fields),'bound_csv_rows_checked':bound,'all_assertions_passed':True,'scope':'postprocessing provenance and time handling; no physics accuracy or conservation claim'},indent=2)+'\n');print(json.dumps({'fields':len(fields),'bound_rows':bound,'passed':True}))
if __name__=='__main__':main()
