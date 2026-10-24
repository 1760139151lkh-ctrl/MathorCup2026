#!/usr/bin/env python3
"""All preregistered independent OSM candidate centroids, postprocess existing fields."""
from pathlib import Path
import csv,json,hashlib,datetime
import numpy as np
P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 targetfile=P/'results/spatial_targets_v2.csv';protocol=P/'config/additional_target_protocol_v2.json'
 if not targetfile.exists():return
 targets=list(csv.DictReader(targetfile.open()));rows=[]
 fields=json.loads((P/'results/official_fields.json').read_text())['fields'];runs={d['run_id']:d for d in csv.DictReader((P/'results/official_runs.csv').open())}
 for item in fields:
  rid=item['run_id']
  if runs[rid].get('role')=='numerical_benchmark':continue
  data=np.load(item['path']);h=data['depth_frames'];times=data['time_s'];a=data['transform'];dx=a[0];dy=-a[4];yy,xx=np.indices(h.shape[1:]);xs=a[2]+(xx+.5)*dx;ys=a[5]-(yy+.5)*dy
  for target in targets:
   mask=(xs-float(target['x_m']))**2+(ys-float(target['y_m']))**2<=100**2;hit=np.any(h[:,mask]>=.1,axis=1) if mask.any() else np.zeros(len(times),bool);idx=np.flatnonzero(hit);status='out_of_domain' if not mask.any() else ('arrival' if len(idx) else ('not_arrived_by_horizon' if runs[rid]['status']=='completed' else 'numerical_failure'));first=int(idx[0]) if len(idx) else None
   rows.append({'run_id':rid,'target_id':target['target_id'],'entity_id':target['entity_id'],'target_kind':target['target_kind'],'geometry_version':target['geometry_version'],'evaluation_role':'postprocess_existing_solver_fields','arrival_definition':'all preregistered representative centroids,100m buffer,first saved output h>=0.1m; not exact structure intersection','status':status,'arrival_time_seconds':float(times[first]) if first is not None else None,'evaluation_end_time_seconds':float(times[-1]),'previous_below_threshold_time_seconds':float(times[first-1]) if first is not None and first>0 else None,'initiation_to_release_delay_seconds':None,'max_depth_m':float(h[:,mask].max()) if mask.any() else None,'target_observation_time_utc':target['observed_time_utc'] or None,'target_position_uncertainty_m':target['position_uncertainty_m'] or None,'source_fields_path':item['path'],'source_fields_sha256':item['sha256'],'execution_sha256':item['execution_sha256'],'log_sha256':item['log_sha256'],'case_sha256':item['case_sha256'],'solver_build':item['solver_build'],'actual_binary_sha256':item['actual_binary_sha256']})
 with (P/'results/official_target_arrivals_v2.csv').open('w',newline='') as f:
  if rows:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (P/'results/official_target_postprocess.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'targets_table_sha256':sha(targetfile),'protocol_sha256':sha(protocol),'all_preregistered_targets':len(targets),'rows':len(rows),'no_solver_rerun':True,'no_primary_target_replacement':True},indent=2)+'\n')
 print(len(rows))
if __name__=='__main__':main()
