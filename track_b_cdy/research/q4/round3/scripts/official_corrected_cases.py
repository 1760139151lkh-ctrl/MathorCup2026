#!/usr/bin/env python3
"""Version native configuration correction; no solver modification, old bytes retained."""
from pathlib import Path
import json,hashlib,datetime
P=Path(__file__).resolve().parents[1];C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
protocol=json.loads((P/'config/official_protocol.json').read_text());protocol.update({'protocol_version':'q4-r3-official-v2','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'registered_before_corrected_solver_runs':True,'supersedes_primary_ravaflow_configuration_only':'q4-r3-official-v1; DClaw unchanged','surface_control':0,'official_default_surface_control':0,'case_run_suffix':'__sf0','single_surface2':'quarantined due documented out-of-bounds risk; not comparison or Q3','multiphase_surface2':'retained as separate configuration challenge, not common primary','source_evidence_sha256':sha(P/'sources/official_csurface_source_evidence.json')});(P/'config/official_protocol_v2.json').write_text(json.dumps(protocol,indent=2)+'\n')
for suite in ['copdem','q2mapped','q2fullmask']:
 old=json.loads((P/f'config/official_cases_{suite}.json').read_text())['cases'];new=[]
 for item in old:
  case=json.loads(Path(item['case']).read_text())
  if case['model']=='dclaw':new.append(item);continue
  case['parent_configuration_run_id']=case['run_id'];case['run_id']+='__sf0';case['csurface']=0;case['official_protocol_version']='q4-r3-official-v2';folder=C/'runs'/case['run_id'];folder.mkdir(parents=True,exist_ok=True);cp=folder/'case.json';cp.write_text(json.dumps(case,indent=2)+'\n');new.append({'run_id':case['run_id'],'case':str(cp)})
 (P/f'config/official_cases_{suite}_v2.json').write_text(json.dumps({'protocol':'q4-r3-official-v2','cases':new},indent=2)+'\n')
bench=[]
for oldrid in ['flatrest_60_ravaflow_single','flatrest_60_ravaflow_multi','bowlrest_60_ravaflow_single']:
 case=json.loads((C/'runs'/oldrid/'case.json').read_text());case['run_id']+='__sf0';case['csurface']=0;case['official_protocol_version']='q4-r3-official-v2';folder=C/'runs'/case['run_id'];folder.mkdir(parents=True,exist_ok=True);cp=folder/'case.json';cp.write_text(json.dumps(case,indent=2)+'\n');bench.append({'run_id':case['run_id'],'case':str(cp)})
 if oldrid.startswith('bowlrest'):
  alt=dict(case);alt['run_id']=oldrid+'__sf1';alt['csurface']=1;folder=C/'runs'/alt['run_id'];folder.mkdir(parents=True,exist_ok=True);cp=folder/'case.json';cp.write_text(json.dumps(alt,indent=2)+'\n');bench.append({'run_id':alt['run_id'],'case':str(cp)})
  alt=dict(case);alt['model']='ravaflow_multi';alt['run_id']='bowlrest_60_ravaflow_multi__sf0';alt['phase_volume_fractions']=[0,0,1];folder=C/'runs'/alt['run_id'];folder.mkdir(parents=True,exist_ok=True);cp=folder/'case.json';cp.write_text(json.dumps(alt,indent=2)+'\n');bench.append({'run_id':alt['run_id'],'case':str(cp)})
(P/'config/official_cases_physics_v2.json').write_text(json.dumps({'protocol':'q4-r3-official-v2','cases':bench},indent=2)+'\n');print({'corrected_physics':len(bench)})
