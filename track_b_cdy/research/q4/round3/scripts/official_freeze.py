#!/usr/bin/env python3
"""Index complete native runs and full raw-field manifests, without self inclusion."""
from pathlib import Path
import argparse,json,hashlib,datetime,subprocess
from official_catalogue import registered_cases,applicability,EXCLUDED,PENDING,DIAGNOSTIC
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def record(p,role):return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'role':role}
def main():
 a=argparse.ArgumentParser();a.add_argument('--allow-interim',action='store_true');args=a.parse_args();registered=registered_cases();decisions=applicability();expected=[x for x in registered if decisions.get(x['run_id'],{}).get('decision','required') not in EXCLUDED|PENDING];diagnostics=[x['run_id'] for x in registered if decisions.get(x['run_id'],{}).get('decision') in DIAGNOSTIC];held=[x['run_id'] for x in registered if decisions.get(x['run_id'],{}).get('decision') in PENDING];quarantined=[x['run_id'] for x in registered if decisions.get(x['run_id'],{}).get('decision') in EXCLUDED]
 missing=[]
 for case in expected:
  f=Path(case['case']).parent;e=f/'execution.json'
  if not e.exists() or json.loads(e.read_text()).get('log_sha256')!=sha(f/'run.log'):missing.append(case['run_id'])
 if (missing or held) and not args.allow_interim:raise RuntimeError('Applicable required native runs unfinished: '+', '.join(missing)+'; applicabilitypending: '+', '.join(held))
 for script in ['official_analyse.py','official_targets.py','official_parser_validate.py','official_control_index.py','official_replay_validate.py','official_benchmark_analyse.py','official_status.py','official_result_matrix.py']:subprocess.run([str(P.parents[2]/'.venv/bin/python'),str(P/'scripts'/script)],check=True)
 entries=[]
 for folder in sorted((C/'runs').glob('*'))+sorted((C/'benchmarks').glob('*')):
  e=folder/'execution.json';log=folder/'run.log'
  if not e.exists() or not log.exists():continue
  ex=json.loads(e.read_text())
  if ex.get('log_sha256')!=sha(log):continue
  files=[record(p,'actual_native_output_or_input') for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='raw_output_manifest.json' and '__pycache__' not in p.parts]
  manifest=folder/'raw_output_manifest.json';manifest.write_text(json.dumps({'run_id':folder.name,'execution_sha256':sha(e),'files':files,'exclusions':['this manifest','__pycache__'],'scientific_role':'quarantined_configuration' if ex.get('quality_gate') else 'actual_native_experiment','source_implementation':'fixed original source/image or explicitly named derivative only'},indent=2)+'\n');entries.append(record(manifest,'full_raw_native_file_index'))
 cancelled=[];registry=P/'results/official_superseded_cancellations.json'
 if registry.exists():
  for item in json.loads(registry.read_text())['records']:
   folder=Path(item['partial_snapshot']);manifest=folder/'raw_output_manifest.json';files=[record(p,'cancelled_retry_partial_native_evidence') for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='raw_output_manifest.json' and '__pycache__' not in p.parts];manifest.write_text(json.dumps({'run_id':item['run_id'],'status':item['status'],'not_formal_numerical_failure':True,'cancellation_registry_sha256':sha(registry),'files':files,'exclusions':['this manifest','__pycache__'],'scientific_role':'excluded_superseded_configuration_partial'},indent=2)+'\n');cancelled.append(record(manifest,'cancelled_partial_raw_file_index'))
 (P/'results/official_raw_output_index.json').write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'registered_native_scientific_cases':len(registered),'applicable_required_cases':len(expected)-len(diagnostics),'diagnostic_only_cases':diagnostics,'not_run_material_applicability_exclusion':quarantined,'applicability_pending_cases':held,'unfinished_applicable_required_cases':[x for x in missing if x not in diagnostics],'unfinished_diagnostic_cases':[x for x in missing if x in diagnostics],'unfinished_registered_cases':missing+held,'final_delivery_complete':not missing and not held,'local_only':True,'raw_run_manifests':entries,'cancelled_retry_partial_manifests':cancelled,'self_inclusion':False,'not_event_validation':True},indent=2)+'\n');print(json.dumps({'registered':len(registered),'required':len(expected)-len(diagnostics),'diagnostic':len(diagnostics),'unfinished':len(missing),'held_pending':len(held),'indexed_runs':len(entries),'cancelled_retry_partial_manifests':len(cancelled)}))
if __name__=='__main__':main()
