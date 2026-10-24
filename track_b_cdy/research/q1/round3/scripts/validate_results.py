#!/usr/bin/env python3
"""Independent table arithmetic, purge, interface and artifact checks (no model rerun)."""
from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
import pandas as pd
import numpy as np
R=Path(__file__).resolve().parents[1];ROOT=Path(__file__).resolve().parents[5]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):return pd.read_csv(R/'results'/name)
def main():
 checks={}
 run=json.loads((R/'results/model_run_validation.json').read_text())
 assert run['passed'] and run['script_sha256']==sha(R/'scripts/run_models.py')
 checks['executed_source_matches_final_bytes']=True
 ranks=read('rankings.csv')
 keys=['quality_track','window_hours','variant','anchor_id','shift_hours','model_id']
 tie_groups=0
 for _,g in ranks.groupby(keys):
  z=g[g.score.notna()].copy();s=z.score.round(12).to_numpy();n=len(s)
  assert z.family_id.is_unique
  for (_,row),v in zip(z.iterrows(),s):
   above=int((s>v).sum());tied=int((s==v).sum());midrank=above+(tied+1)/2
   credit=min(1,max(0,(5-above)/tied))
   assert abs(row['rank']-midrank)<1e-10 and abs(row.top5_credit-credit)<1e-10
  assert abs(z.top5_credit.sum()-min(5,n))<1e-8
  tie_groups+=int(z['rank'].duplicated().any())
 checks['all_rank_midpoints_and_boundary_credits_recomputed']=True
 base=ranks[(ranks.variant=='primary')&(ranks.shift_hours==0)&(ranks.anchor_id=='problem_1030')]
 rec=read('recommended_factors.csv')
 for _,row in rec.iterrows():
  t=base[(base.quality_track==row.quality_track)&(base.family_id==row.family_id)]
  values=[]
  for w,g in t.groupby('window_hours'):
   three=[]
   for _,rr in g.iterrows():
    full=base[(base.quality_track==row.quality_track)&(base.window_hours==w)&(base.model_id==rr.model_id)]
    if pd.notna(rr['rank']):three.append(1-(rr['rank']-1)/max(full['rank'].notna().sum()-1,1))
   values.append(np.mean(three) if len(three)==3 else np.nan)
  expected=float(np.mean(values))
  assert (pd.isna(expected) and pd.isna(row.consensus_score)) or abs(expected-row.consensus_score)<1e-10
 checks['three_route_three_window_consensus_independently_recomputed']=True
 stability=read('stability_draws.csv');summary=read('ranking_stability.csv')
 skeys=['kind','quality_track','window_hours','model_id','family_id']
 grouped={k:g for k,g in stability.groupby(skeys)}
 for _,row in summary.iterrows():
  key=tuple(row[k] for k in skeys);g=grouped[key];valid=g[g['rank'].notna()]
  assert len(g)==row.n_requested and len(valid)==row.n_valid
  if len(valid):assert abs(valid.top5_credit.mean()-row.top5_frequency)<1e-10
  if row.kind=='hierarchical_bootstrap':assert row.n_requested==100
 checks['all_stability_valid_denominators_and_frequencies_recomputed']=True
 folds=read('fold_membership.csv')
 for _,f in folds.groupby('fold_id'):
  tr=f[f.role=='training'];te=f[f.role=='test_background']
  a=pd.to_datetime(tr.support_start_utc,utc=True).astype('int64').to_numpy();b=pd.to_datetime(tr.support_end_exclusive_utc,utc=True).astype('int64').to_numpy()
  for _,test in te.iterrows():
   left=pd.Timestamp(test.support_start_utc).value;right=pd.Timestamp(test.support_end_exclusive_utc).value
   assert not ((a<right)&(b>left)).any()
 checks['all_training_test_168h_supports_disjoint']=True
 analog=read('analog_matches.csv')
 assert (analog.observed_outside_family_matching_fraction>=.8-1e-12).all()
 ak=['quality_track','window_hours','variant','shift_hours','family_id','year']
 for k,g in analog.groupby(ak):
  assert g.process_id.is_unique
  variant=k[2];limit=int(variant.split('_')[1]) if variant.startswith('analogs_') else 2
  assert len(g)<=limit
 checks['all_saved_analogs_meet_support_and_distinct_process_rules']=True
 ef=read('effective_feature_support.csv');ff=read('effective_family_support.csv')
 assert (ef.actual_numeric_supported_years<=5).all()
 for _,r in ef.iterrows():
  years=json.loads(r.years_json);miss=json.loads(r.missing_years_json)
  assert len(years)==r.actual_numeric_supported_years and set(years).isdisjoint(miss) and set(years)|set(miss)==set(range(2021,2026))
 checks['actual_feature_years_not_confused_with_nominal_pool']=True
 for path in [R/'exports/feature_bundle.json',R/'inputs/q3/event_bundle_q3-r3-event-v1-local/bundle.json']:
  bundle=json.loads(path.read_text())
  for e in bundle['files']:
   p=ROOT/e['path'];assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256']
 checks['feature_v1_and_advisor_q3_bundle_hashes_verified']=True
 assert sha(R/'exports/feature_bundle.json')=='4e65566a1a473d7fdd16af10f209c2cb6841282b215e8c9d4981f748d6c1cc8e'
 assert sha(ROOT/'track_b/audit/stage4/round3/baseline_manifest.json')=='fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'
 checks['released_v1_and_frozen_baseline_unchanged']=True
 nr=json.loads((R/'results/independent_numerical_review.json').read_text())
 # The independent numerical report itself binds its reviewed production source.
 assert sha(R/'scripts/run_models.py') in json.dumps(nr)
 checks['independent_numerical_review_binds_current_source']=True
 for name in ['EXPERIMENT_PROTOCOL.md','PROTOCOL_DEVIATIONS.md','INTERFACE_HANDOFF.md','EVIDENCE_REVIEW.md','MODEL_COMPARISON.md','PAPER_OUTLINE.md','REPRODUCE.md','HANDOFF.md']:
  assert (R/name).stat().st_size>100
 vr=json.loads((R/'figures/visual_review.json').read_text())
 for e in vr['files']:assert sha(R/e['path'])==e['sha256']
 assert vr['passed']
 checks['required_reports_and_actual_visual_review_present']=True
 ctx=json.loads((R/'results/model_context.json').read_text())
 assert ctx['independent_accepted_training_events']==0 and ctx['independent_accepted_validation_events']==0 and ctx['available_time'] is None
 checks['event_truth_and_availability_boundaries_preserved']=True
 result={'passed':True,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'rank_groups_with_ties':tie_groups,'ranking_rows':len(ranks),'fold_groups':folds.fold_id.nunique(),'fold_membership_rows':len(folds),'stability_rows':len(stability),'feature_support_rows':len(ef),'family_support_rows':len(ff),'independent_disaster_training_events':0,'independent_disaster_validation_events':0,'scope':'Read-only independent arithmetic and artifact review plus validation.json write; no repeat model fitting or scientific adoption'}
 (R/'results/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
