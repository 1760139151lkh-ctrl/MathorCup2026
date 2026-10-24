#!/usr/bin/env python3
"""Bind direct research inputs and all stable R3 packet outputs, without self entries."""
from pathlib import Path
import argparse,json,hashlib
R=Path(__file__).resolve().parents[1];ROOT=Path(__file__).resolve().parents[5]
OUT=R/'output_manifest.json';INP=R/'results/input_manifest.json'
EXCLUDE={'output_manifest.json','workspace_binding.json','workspace_verification.json'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stable(p):return p.is_file() and str(p.relative_to(R)) not in EXCLUDE and p.suffix!='.log' and '__pycache__' not in p.parts
def entry(p,root=ROOT,role=None):
 e={'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p)}
 if role:e['role']=role
 return e
def verify(items,root):
 for e in items:
  p=root/e['path'];assert p.resolve()==p and p.is_relative_to(root),e['path']
  assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],e['path']
def main():
 a=argparse.ArgumentParser();a.add_argument('--verify-only',action='store_true');args=a.parse_args()
 if not args.verify_only:
  public=['track_b/data/processed/temporal/'+s for s in ['hourly_raw_numeric.parquet','hourly_strict_qc0.parquet','hourly_mask_is_numeric_present.parquet','hourly_mask_strict_qc0_accepted.parquet','hourly_raw_qc.parquet','hourly_time_axis.parquet','data_dictionary.json']]
  public+=['track_b/config/temporal_policy.json','track_b/config/stage4_contract.json','track_b/config/stage4_round3_contract.json','track_b/audit/stage4/round3/baseline_manifest.json','track_b/requirements-lock.txt','track_b/research/q1/results/window_descriptives.csv','track_b/research/q1/round2/results/background_equal_year.csv','track_b/research/q1/round2/results/background_year_values.csv','track_b/research/q1/round2/results/semantic_adoption.csv','track_b/research/q1/round2/results/constant_segment_trace.json']
  own=['config/experiment.json','EXPERIMENT_PROTOCOL.md','PROTOCOL_DEVIATIONS.md','config/features.json','results/features.parquet','results/sample_metadata.csv','results/feature_support.csv','results/feature_contract.csv','exports/feature_bundle.json','evidence/access_log.json','source_register.json']
  paths=[ROOT/p for p in public]+[R/p for p in own]+list((R/'inputs').rglob('*'))+list((R/'evidence').glob('*.html'))
  paths=sorted(set(p for p in paths if p.is_file()))
  assert INP not in paths and OUT not in paths
  manifest={'input_version':json.loads((R/'config/experiment.json').read_text())['common_baseline_commit'],'scope':'Direct public inputs, frozen R1/R2 contrast, registered experiment, feature-v1 model inputs, preserved external response bytes and advisor-delivered Q3 inputs. Own input/output manifests excluded.','files':[entry(p) for p in paths]}
  INP.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
  outputs=[entry(p,R) for p in sorted(R.rglob('*')) if stable(p)]
  out={'packet_version':'q1-r3-complete-v1','producer_question':'q1','common_baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','context_ref':'results/model_context.json','files':outputs,'excluded_exact_paths':sorted(EXCLUDE),'excluded_patterns':['*.log','**/__pycache__/**'],'exclusion_reason':'Self reference or mutable execution/workspace logs; stable startup and executed research checks are included, mutable originals retained in Git.','scientific_adoption':'pending_team_review'}
  OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 im=json.loads(INP.read_text());om=json.loads(OUT.read_text());verify(im['files'],ROOT);verify(om['files'],R)
 assert str(INP.relative_to(ROOT)) not in {e['path'] for e in im['files']}
 assert {e['path'] for e in om['files']}=={str(p.relative_to(R)) for p in R.rglob('*') if stable(p)}
 b=json.loads((R/'exports/feature_bundle.json').read_text());verify(b['files'],ROOT)
 assert 'track_b/research/q1/round3/exports/feature_bundle.json' not in {e['path'] for e in b['files']}
 assert sha(R/'exports/feature_bundle.json')=='4e65566a1a473d7fdd16af10f209c2cb6841282b215e8c9d4981f748d6c1cc8e'
 print(json.dumps({'passed':True,'direct_inputs':len(im['files']),'stable_outputs':len(om['files']),'feature_v1_files_verified':len(b['files']),'output_manifest_sha256':sha(OUT)}))
if __name__=='__main__':main()
