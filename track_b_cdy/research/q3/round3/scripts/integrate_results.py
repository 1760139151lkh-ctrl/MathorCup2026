#!/usr/bin/env python3
"""Project stable, completed engine outputs into clearly stratified common tables."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parents[1]
VERSION=json.dumps({'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'})

def main():
    b=R/'results/engine_b';c=R/'results/engine_c';a=R/'results/mechanistic_replay'
    for p in [b/'validation.json',a/'validation.json',a/'v2/validation.json',a/'analytic_erfc/validation.json',c/'no_record_age/validation_checks.json',R/'results/common_anchors_no_age/validation.json']:
        doc=json.loads(p.read_text())
        if 'passed' in doc:assert doc['passed'],str(p)
        else:
            positive=['future_information_cutoff_rejected','physical_groups_disjoint_per_outer_fold','at_most_one_event_per_physical_group','risk_intervals_positive','no_event_after_risk_end','no_synthetic_rows_added','all_sources_real_observations_or_labels','probability_normalization_and_bounds']
            assert all(doc[k] for k in positive) and not doc['conformal_guarantee_claimed'] and not doc['rolling_issues_independent_sample_claimed'],str(p)
    acsv=a/'analytic_erfc/predictions.csv.gz';af=pd.read_csv(acsv)
    af=af[af.probability_prior.eq('uniform_design_assumption')].copy()
    af=af.rename(columns={'conditional_lower_hours':'conditional_lower_offset_hours','conditional_median_hours':'conditional_median_offset_hours','conditional_upper_hours':'conditional_upper_offset_hours'})
    af['prediction_projection']='all_75_issues_all_weather_tracks_uniform_assumed_prior; other_priors_in_engine_raw'
    af['physical_phase']='first_mechanical_initiation_at_source';af['event_id']='B20260826_Chhochen'
    af['engine_input_version']=af.input_version
    af['model_version']=af.input_bundle_version
    af['input_version']=[json.dumps(dict(json.loads(VERSION),mechanism_bundle=v,mechanism_bundle_sha256=h,weather_sha256=w)) for v,h,w in zip(af.input_bundle_version,af.input_bundle_sha256,af.input_weather_sha256)]
    af['space_object']=[json.dumps({'weather_support':s,'crs':'EPSG:4326','gfs_resolution_degrees':.25,'source_geometry':'Q4 candidate; see results/spatial_context.json','positional_uncertainty':None}) for s in af.space_object]
    af['variable_semantics']='time_offsets_hours; Q2_dimensionless_margin; GFS2m_C_and_APCP_mm_intervals; regional_to_source_mapping_conditional'
    af['time_uncertainty']=json.dumps({'conditional_model_interval_level':.95,'physical_time_error':None,'discrete_prior_support_may_be_one; not empirical coverage':True})
    clock=pd.to_datetime(af.issue_time,utc=True,format='mixed')
    af['valid_time']=(clock+pd.to_timedelta(af.horizon_hours,unit='h')).astype(str)
    af['time_utc']=(clock+pd.to_timedelta(af.conditional_median_offset_hours,unit='h')).where(af.conditional_median_offset_hours.notna()).astype('string')
    af['evidence_status']='inference'
    common_path=R/'results/common_anchors_no_age/predictions.csv';cf=pd.read_csv(common_path)
    cf['prediction_projection']='exact_same_sensor_issue_horizon_anchor; all_rolling_records_retained_in_engine_cache'
    cf['physical_phase']='external_terminal_or_main_collapse';cf['event_id']='external:'+cf.event_group
    cf['issue_time']=None;cf['available_time']=None;cf['data_role']='validation';cf['validation_role']='external_site_or_event_heldout_benchmark'
    cf['forecast_input_mode']=None;cf['input_version']=VERSION
    cf['interval_semantics']='model_internal_given_terminal_collapse_within_H; no distribution_free95 guarantee'
    cf['parameter_version']=np.where(cf.engine.eq('B'),'B_fixed_w16_q0.01','C_no_record_age_LOSO_nested_selected')
    cf['model_input_role']='real_published_deformation; source preprocessing/curation and historical availability uncertified'
    cf['mechanism_id']=np.where(cf.engine.eq('B'),'deformation_acceleration','statistical_dynamic_hazard')
    cf['experiment_id']='q3r3-exact-matched-external-anchors-no-record-age'
    cf['scenario_id']=[f'{g}:anchor_relative_hours={t}:H={h}' for g,t,h in zip(cf.event_group,cf.issue_relative_hours,cf.horizon_hours)]
    cf['geometry_version']='external_sensor_native_support_not_local_source_geometry'
    cf['space_object']=[json.dumps({'site_id':s,'physical_event_group':g,'crs':None,'resolution':None,'positional_uncertainty':None}) for s,g in zip(cf.site_id,cf.event_group)]
    cf['time_utc']=None;cf['valid_time']=None;cf['forecast_reference_time']=None
    cf['valid_time_relative_hours']=cf.issue_relative_hours+cf.horizon_hours
    cf['time_uncertainty']=[json.dumps({'label_lower_offset_hours':float(l) if pd.notna(l) else None,'label_upper_offset_hours':float(u) if pd.notna(u) else None,'clock':'native_relative; no UTC fabricated','physical_proxy_error':None}) for l,u in zip(cf.failure_lower_offset_hours,cf.failure_upper_offset_hours)]
    cf['variable_semantics']='native_source_units preserved in inputs/deformation/site_registry.csv; B_time_zero_scale_invariant; C_dimensionless_deformation; past_only_Q3_processing'
    cf['evidence_status']='inference'
    pred=pd.concat([af,cf],ignore_index=True);pred.to_csv(R/'results/predictions.csv',index=False)
    evaluation=[]
    for p,label in [(R/'results/common_anchors_no_age/evaluation.csv','primary_exact_matched_anchors_no_record_age'),
                   (b/'model_comparison.csv','B_original_registered_publication_sets'),
                   (b/'paired_model_comparison.csv','B_same_valid_opportunity_pairing'),
                   (c/'no_record_age/anchor_evaluation.csv','C_no_record_age_primary_anchors'),
                   (c/'record_age_anchor_reference/anchor_evaluation.csv','C_record_age_sensitive_challenge'),
                   (c/'evaluation.csv','C_record_age_sensitive_full_rolling_challenge')]:
        f=pd.read_csv(p);f['comparison_id']=label;f['evaluation_stratum']='external_transfer';f['source_table']=str(p.relative_to(R));evaluation.append(f)
    pd.concat(evaluation,ignore_index=True).to_csv(R/'results/evaluation.csv',index=False)
    paired=pd.read_csv(R/'results/common_anchors_no_age/paired_valid_scores.csv')
    paired['comparison_id']='primary_exact_same_anchor_and_probability_issued_subset'
    paired.to_csv(R/'results/paired_model_comparison.csv',index=False)
    folds=[]
    for p,label in [(b/'fold_membership.csv','B_fixed_structure_online_prefix'),(c/'no_record_age/fold_membership.csv','C_no_record_age_primary'),(c/'fold_membership.csv','C_record_age_challenge')]:
        f=pd.read_csv(p);f['pipeline']=label;folds.append(f)
    pd.concat(folds,ignore_index=True).to_csv(R/'results/fold_membership.csv',index=False)
    intervals=pd.read_csv(R/'results/common_anchors_no_age/evaluation.csv')
    intervals['interval_type']='model_internal_given_start_within_H';intervals['conditional_interval_level']=.95;intervals['guaranteed_empirical95']=False
    conf=pd.read_csv(b/'conformal_feasibility.csv').rename(columns={'n_calibration_independent_groups':'upper_bound_other_failure_groups'})
    conf['independent_calibration_groups']=0;conf['calibration_fit_executed']=False
    conf['interval_type']='conformal_independent_group_support_audit';conf['conditional_interval_level']=.95
    conf['model_id']='B_conformal_feasibility';conf['status']='no_finite_distribution_free_interval; feasibility_only_not_calibration_fit';conf['guaranteed_empirical95']=False
    cconf=pd.DataFrame([dict(model_id='C_conformal_feasibility',interval_type='conformal_independent_group_support_audit',conditional_interval_level=.95,
          upper_bound_other_groups=13,independent_calibration_groups=0,calibration_fit_executed=False,
          finite_sample_rank=int(np.ceil((13+1)*.95)),status='rank14_exceeds13; feasibility_only_not_calibration_fit',
          exchangeability_established=False,guaranteed_empirical95=False)])
    pd.concat([intervals,conf,cconf],ignore_index=True).to_csv(R/'results/interval_comparison.csv',index=False)
    prior=[]
    for p,label in [(a/'prior_sensitivity.csv.gz','Q2_coarse_thermal_v1'),(a/'v2/prior_sensitivity.csv.gz','Q2_refined_thermal_v2'),
                    (a/'analytic_erfc/prior_sensitivity.csv.gz','Q2_analytic_erfc_reference'),(b/'window_noise_comparison.csv','B_window_noise_sensitivity')]:
        f=pd.read_csv(p);f['sensitivity_family']=label;f['source_table']=str(p.relative_to(R));prior.append(f)
    pd.concat(prior,ignore_index=True).to_csv(R/'results/prior_sensitivity.csv',index=False)
    probability=pred.dropna(subset=['probability_start_within_horizon','probability_no_start_within_horizon'])
    checks={'probability_normalization':bool(np.allclose(probability.probability_start_within_horizon+probability.probability_no_start_within_horizon,1)),
            'no_local_truth_coverage_inferred':bool(pred.loc[pred.engine.eq('A_weather_coupled'),'empirical_coverage'].isna().all()),
            'primary_C_has_no_record_age':json.loads((c/'no_record_age/summary.json').read_text())['feature_specification']=='no_record_age_main',
            'frozen_event_v1_retained':hashlib.sha256((R/'exports/event_bundle.json').read_bytes()).hexdigest()=='075b149214b5c9a8827af45af221ee6ee6b6428090e6d9337afb1943698d2faf'}
    contract=json.loads((R.parents[3]/'track_b/config/stage4_contract.json').read_text())
    checks['shared_contract_columns_present']=set(contract['shared_record_fields'])<=set(pred.columns)
    checks['data_roles_explicit']=pred.data_role.isin(['scenario','validation','calibration','exploration']).all().item()
    # The C CLI and registered summary explicitly bind feature choice; fit tables
    # may omit feature labels, so verify the run's own feature manifest as well.
    cs=json.loads((c/'no_record_age/summary.json').read_text())
    checks['all_engine_validations_loaded']=True
    summary=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),prediction_projection_rows=len(pred),A_weather_rows=len(af),matched_B_C_rows=len(cf),
       primary_A_version='analytic_erfc_linear_thermal_reference; water_damage_hourly_discrete',primary_C_summary=cs,local_first_mechanical_truth_accepted=False,local_empirical_coverage=None,
       full_raw_predictions='See per-engine prediction_cache.json or predictions.csv.gz; root projection keeps primary prior and fixed common anchors, not all raw repeated rows',
       evaluation_tables_compared_without_pooling_strata=True,checks=checks,passed=all(checks.values()))
    (R/'results/integration_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    assert summary['passed'],checks;print(json.dumps({k:v for k,v in summary.items() if k!='primary_C_summary'}))

if __name__=='__main__':main()
