#!/usr/bin/env python3
"""Bind actual saved native controls; never reconstruct a missing historical adapter hash."""
from pathlib import Path
import json,hashlib,datetime
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for folder in sorted((C/'runs').glob('*')):
 meta=folder/'execution.json';log=folder/'run.log';cp=folder/'case.json'
 if not meta.exists() or not log.exists() or not cp.exists():continue
 ex=json.loads(meta.read_text());case=json.loads(cp.read_text())
 if ex.get('log_sha256')!=sha(log):continue
 controls=[]
 for f in sorted(folder.rglob('*')):
  if not f.is_file():continue
  if f.suffix in ['.data','.tt3'] or f.name=='run_grass.sh' or ('param' in f.name and f.suffix=='.txt') or f.name=='xdclaw':
   role='native_executed_binary' if f.name=='xdclaw' else 'native_terrain' if f.name=='basal_topo.tt3' else 'native_release' if f.name=='thickness.tt3' else 'native_control_text'
   controls.append({'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f),'role':role,'hash_observation':'index_time_saved_generated_bytes; not a retrospective execution-time adapterhash'})
 adapter=ex.get('adapter_path');expected=ex.get('adapter_sha256_at_start');available=bool(adapter and expected and Path(adapter).exists() and sha(Path(adapter))==expected)
 rows.append({'run_id':case['run_id'],'model':case['model'],'execution_sha256':sha(meta),'case_sha256':sha(cp),'log_sha256':sha(log),'native_input_controls':controls,'saved_executed_adapter_path':adapter if available else None,'saved_executed_adapter_sha256':expected if available else None,'historical_adapter_identity_status':'saved_per_run_and_hash_bound_at_start' if available else 'not_saved_at_execution_start; do_not_retroactively_substitute_currentadapter','exact_native_replay_route':'use saved *.data + basal_topo/thickness.tt3 withsameverifiedxdclaw' if case['model']=='dclaw' else 'use savedrun_grass.sh + fullyexpandednativeparamcomm andcaseinputrasters withsameverifiedbinary','original_execution_metadata_unchanged':True})
(P/'results/official_native_control_index.json').write_text(json.dumps({'indexed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runs':rows,'historical_missing_runner_not_reconstructed':True,'scope':'actualsaved nativecontrols, independentlyhashable; doesnotassert historicalPython sourcehashwhen absent'},indent=2)+'\n');print(json.dumps({'control_index_runs':len(rows),'early_adapter_not_hash_bound':sum(r['saved_executed_adapter_sha256'] is None for r in rows)}))
