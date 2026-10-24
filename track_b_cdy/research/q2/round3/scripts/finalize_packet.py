"""Offline packet verification and acyclic manifests; no model execution."""
import hashlib,importlib.metadata,json,platform
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from run_experiments import ROOT,BASE,INPUT_VERSION,write_json,digest

FROZEN_BUNDLES={
 'exports/mechanism_bundle.json':'250f25f180bfd2f7c6c296b679dd2c9aea18826411f5e7195f18b9ee07a56bc1',
 'exports/release_bundle.json':'a22c0949d16f3f1f50efc6f97a74734bed45a8553096ec3084c84298c474d56b',
 'exports/release_bundle_v2.json':'3a6924f3ca796b39fad65c3c300e5417b08ed5343347388af938242d35dc1de3',
 'exports/mechanism_bundle_v2.json':'dc53a9f805e96ff32b2c1fd064b0b7b33d90034e7d2c987f42403ae70bfcb093',
 'exports/numerical_supplement_bundle.json':'151a7c7f822f3970a7dbdc0194b4c1df18548dbb70afca19a5927f49f3206b03',
 'exports/composition_bundle.json':'14f96d7d1e8600154a831dba9921a9efbf70eeacfd71e54b12af78879b762335',
 'exports/analytic_thermal_bundle.json':'ff989d23894f9b2d44daf032418583430791ef5b8367d423aa5cb54763767684'}


def resolve(path):
    p=Path(path);return p if p.is_absolute() else ROOT/p


def check_record(row,size_key='bytes'):
    p=resolve(row['path']);b=p.read_bytes()
    assert len(b)==row[size_key] and hashlib.sha256(b).hexdigest()==row['sha256'],str(p)
    return p


def main():
    assert ROOT==Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2')
    checks=[];inputs={}
    def add_input(path,role):
        p=resolve(path);key=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        b=p.read_bytes();inputs[key]={'path':key,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'role':role}
    def passed(name,details):checks.append({'check':name,'passed':True,'details':details})
    for name,sha in FROZEN_BUNDLES.items():
        p=BASE/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
        d=json.loads(p.read_text())
        for row in d['files']:check_record(row);assert resolve(row['path'])!=p
        passed(name,{'members':len(d['files']),'sha256':sha})
    envlock=(ROOT/'track_b/requirements-lock.txt').read_bytes();(BASE/'config/environment_lock.txt').write_bytes(envlock)
    versions={}
    for line in envlock.decode().splitlines():
        name,version=line.split('==');actual=importlib.metadata.version(name);assert actual==version,(name,actual,version);versions[name]=actual
    write_json(BASE/'config/environment.json',{'python':platform.python_version(),'implementation':platform.python_implementation(),
      'platform':platform.platform(),'locked_distribution_count':len(versions),'versions':versions,'new_dependencies_installed':False,
      'source_lock':digest(ROOT/'track_b/requirements-lock.txt','original shared exact lock; unchanged')})
    passed('original_exact_environment',{'distributions':len(versions),'python':platform.python_version()})
    shared=['track_b/audit/stage4/round3/baseline_manifest.json','track_b/config/stage4_round3_contract.json','track_b/config/stage4_contract.json',
      'track_b/data/processed/temporal/hourly_time_axis.parquet','track_b/data/processed/temporal/hourly_strict_qc0.parquet',
      'track_b/data/processed/temporal/hourly_raw_numeric.parquet','track_b/data/processed/temporal/data_dictionary.json',
      'track_b/research/q2/results/nc_parameter_support.csv','track_b/research/q2/results/input_check.json',
      'track_b/research/q2/round2/HANDOFF.md','track_b/research/q2/round2/VELOCITY_REVIEW.md',
      'track_b/research/q2/round2/inputs/search_aoi.geojson','track_b/research/q2/round2/inputs/search_aoi_evidence.json',
      'track_b/research/q2/sources/jms_abstract.html','track_b/research/q2/sources/yin_abstract.html','track_b/requirements-lock.txt']
    for p in shared:add_input(p,'frozen shared/background input; semantics documented in protocol/evidence review')
    assert hashlib.sha256((ROOT/shared[0]).read_bytes()).hexdigest()==INPUT_VERSION['baseline_manifest_sha256']
    for p in (BASE/'inputs').rglob('*'):
        if p.is_file():add_input(str(p),'advisor delivered own-tree copy; top-level role usage in interface_use.json')
    iface=json.loads((BASE/'results/interface_use.json').read_text());assert iface['passed'];passed('advisor_interfaces',iface['q1_driver_compatibility'])
    for imported in iface['inputs']:
        for record in json.loads(resolve(imported['path']).read_text())['files']:
            if Path(record['path']).is_absolute():
                add_input(record['path'],'advisor-approved immutable cache input; '+record['role'])
    strength=json.loads((BASE/'sources/strength/source_register.json').read_text())
    sources=[]
    for s in strength['sources']:
        check_record(s);add_input(s['path'],'official strength/thermal/hydrology source snapshot');sources.append(s)
    for s in strength['rendered_pages_opened']:
        p=resolve(s.get('path',s.get('saved_path','')))
        if p.is_file() and s.get('sha256'):assert hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256']
    sar=json.loads((BASE/'results/sar_evidence_register.json').read_text())
    for s in sar['requests']:
        check_record(s,'bytes_consumed');add_input(s['path'],'public acquisition response; actual role/scope in SAR register')
        sources.append({'canonical_url_or_product_id':s.get('effective_url',s['requested_url']),
          'product_version':'ITS_LIVE V02 SAR feature-tracking NetCDF' if s['path'].endswith('.nc') else 'as saved response; version in upstream source record',
          'retrieved_at_utc':s['retrieved_at_utc'],'actual_read_scope':s['scope'],'path':s['path'],'bytes':s['bytes_consumed'],'sha256':s['sha256'],
          'data_role':'exploration','available_time_or_unknown':s.get('available_time'),'http_status':s.get('http_status')})
    assert sar['sar_nc_bytes']==52149417
    remote=json.loads((BASE/'results/sar_evidence_validation.json').read_text());assert all(s['passed'] for s in remote['checks'])
    passed('real_sar',{'full_netcdf_bytes':sar['sar_nc_bytes'],'http_body_bytes':sar['all_recorded_http_body_bytes'],'checks':len(remote['checks'])})
    review=json.loads((BASE/'results/independent_physics_review.json').read_text())
    assert review['engine_sha256']==hashlib.sha256((BASE/'scripts/mechanism_engine.py').read_bytes()).hexdigest()
    assert all(s['status']=='passed' for s in review['checks']);passed('independent_physics',{'checks':len(review['checks'])})
    outcome=pd.read_csv(BASE/'results/refined_v2/scenario_outcomes.csv');states=pd.read_parquet(BASE/'results/refined_v2/state_trajectories.parquet')
    assert len(outcome)==2048 and outcome.scenario_id.is_unique and len(states)==133696
    assert not outcome.onset_status.str.contains('missing').any()
    assert (outcome.groupby(['mechanism_id','law_policy']).size()==256).all()
    assert (outcome.loc[outcome.onset_status.str.startswith('left_censored'),'onset_elapsed_hours'].isna()).all()
    assert (outcome.loc[outcome.onset_status=='never_crossed','onset_elapsed_hours'].isna()).all()
    assert states.available_time.isna().all() and set(states.data_role)=={'scenario'}
    for sid,g in states.groupby('scenario_id',sort=False):
        t=pd.to_datetime(g.time_utc,utc=True);assert len(t)==2089 and t.is_monotonic_increasing
        assert (t.diff().dropna().dt.total_seconds()==3600).all()
    passed('retained_outcomes_time_and_censoring',{'outcomes':len(outcome),'representative_state_rows':len(states),'independent_events':0})
    geometry=json.loads((BASE/'results/geometry_integration_summary.json').read_text());assert geometry['two_grid_volume_equality_passed'] and geometry['two_grid_mass_equality_passed']
    passed('geometry_volume_mass',{'rows':geometry['release_rows'],'max_volume_relative_error':geometry['max_volume_relative_error']})
    ident=pd.read_csv(BASE/'results/identifiability.csv');assert list(ident['rank'])==[1,1,2,3,4]
    passed('identifiability_benchmark',{'ranks':list(ident['rank']),'independent_events':0})
    composition=json.loads((BASE/'results/composition_sensitivity/summary.json').read_text())
    assert composition['new_integrations']==128 and composition['new_state_rows']==267392
    assert composition['all_noncomposition_parameters_pairwise_unchanged'] and composition['bridge_area_fraction_unchanged']
    passed('composition_density_intervention',{'new_integrations':128,'new_state_rows':267392,'old_bundles_retained':composition['all_consumed_published_inputs_unchanged']})
    analytic=json.loads((BASE/'results/analytic_thermal/summary.json').read_text())
    independent_analytic=json.loads((BASE/'results/analytic_thermal_independent_review.json').read_text())
    assert analytic['scenario_outcomes']==2048 and analytic['benchmark_all_passed']
    assert all(c['passed'] for c in independent_analytic['checks'])
    for reviewed in independent_analytic['files_reviewed']:
        assert hashlib.sha256(resolve(reviewed['path']).read_bytes()).hexdigest()==reviewed['sha256']
    passed('analytic_thermal_independent_checks',{'checks':len(independent_analytic['checks']),'outcomes':2048,
      'finite_onset_pairs_vs_fd0625':analytic['finite_analytic_fd_onset_pairs'],
      'max_onset_difference':analytic['max_analytic_fd_onset_difference'],
      'actual_finite_bottom_approximation_bound_c':analytic['max_actual_reflection_temperature_bound_c'],
      'scope':'linear heat equation numeric reference; 1h mechanical/water state and physical/source uncertainties retained'})
    workspace=json.loads((BASE/'workspace_verification.json').read_text());assert workspace['passed']
    startup=json.loads((BASE/'results/startup_workspace_verification.json').read_text());assert startup['passed']
    passed('workspace_end_and_preserved_startup',{'end_passed':True,'startup_passed':True})
    visual=json.loads((BASE/'results/visual_review.json').read_text())
    for row in visual['opened_images']:check_record(row)
    passed('actually_opened_model_and_sar_images',{'images':len(visual['opened_images'])})
    write_json(BASE/'results/source_register.json',{'register_version':'q2r3-source-index-v1','sources':sources,
      'strength_register':digest(BASE/'sources/strength/source_register.json','detailed actual reading / coefficient domain / PDF views'),
      'sar_register':digest(BASE/'results/sar_evidence_register.json','actual public responses / pixels / source reading'),
      'composition_protocol':digest(BASE/'results/composition_sensitivity/protocol.json','actual frozen abstracts reread; precise volume from advisor; candidate bulk-to-slab mapping'),
      'advisor_interfaces':iface['inputs'],'historical_available_time_warning':'Retrieval/Last-Modified is not historical first availability'})
    write_json(BASE/'results/validation.json',{'passed':True,'checks':checks,'scientific_adoption':'pending_team_review',
      'independent_local_training_events':0,'independent_local_validation_events':0,'scope':'software/byte/physics implementation and conditional-model checks; not local mechanism validation'})
    validation=json.loads((BASE/'results/validation.json').read_text())
    full=json.loads((BASE/'results/refined_v2/full_reference_summary.json').read_text())
    validation['numerical_precision']={'uniform_margin_0p02_target_passed':full['margin_0p02_target_met'],
      'model_version':'FD 0.125m v2 control only; analytic thermal branch reported separately',
      'failed_trajectories':full['margin_0p02_target_failed_n'],'comparisons':full['comparisons'],
      'finite_onset_pairs':137,'largest_observed_onset_difference_hours':18.943779,
      'interpretation':'passed above refers to integrity/implementation checks; full design timing precision NOT uniformly established; observed two-grid difference is not strict bound or95% interval',
      'supplement':'exports/numerical_supplement_bundle.json'}
    write_json(BASE/'results/validation.json',validation)
    add_input(str(BASE/'config/experiment_v1.json'),'preregistered local design configuration')
    write_json(BASE/'input_manifest.json',{'input_version':INPUT_VERSION,'files':list(sorted(inputs.values(),key=lambda x:x['path'])),'file_count':len(inputs),'self_entry':False})
    write_json(BASE/'results/result_index.json',{'input_version':INPUT_VERSION,'status':'ready_for_joint_scientific_review',
      'event_id':'B20260826_Chhochen_case_reference_not_independent_truth','physical_phase':'initiation',
      'time_utc':None,'time_uncertainty':'exact local first initiation truth unaccepted','available_time':None,'forecast_reference_time':None,'issue_time':None,'valid_time':None,
      'space_object':{'id':'conditional_plane_slab_and_Q4_candidate_source','crs':'EPSG:32645 for supplied geometry; local plane for stresses','positional_error':None},
      'variable_semantics':{'failure_margin':'(R-tau)/tau dimensionless; positive stable','source_forcing':'regional station transfer scenario; ideal_weather','quality':'strictQC0 temperature; unknown precip label as conditional hourly rate'},
      'data_role':'scenario','evidence_status':'conditional mechanism competition; local remote pixels exploratory; external_transfer strength; numerical_benchmarks',
      'model_ids':outcome.model_id.unique().tolist()+pd.read_csv(BASE/'results/analytic_thermal/scenario_outcomes.csv').model_id.unique().tolist(),'experiment_id':'q2r3-competing-mechanisms-v1 plus thermal-v2 and analytic challenge',
      'geometry_version':'q4-r3-spatial-copdem-v1 conditional geometry','parameter_version':'q2r3-design-v1',
      'recommended_main':'four-way conditional mechanism competition; analytic-erfc heat module as numerical reference within registered domain; FD v1/v2 controls retained',
      'challengers':['S_T','S_H','warm thawed-rock contact policy','S structural baseline'],
      'bundles':[{**digest(BASE/p,p),'frozen_sha256':h} for p,h in FROZEN_BUNDLES.items()],
      'independent_local_training_events':0,'independent_local_validation_events':0,
      'not_resolved':['actual release plane/material/bridge/damage','joint temperature/head and source forcing','local exact initiation truth','historical weather availability','latent/advective/3D processes'],
      'technical_validation':'results/validation.json','full_reference_supplement':'results/refined_v2; supplementary files separate from frozen v2 bundle','human_scientific_adoption':'pending_team_review'})
    rows=[]
    for p in sorted(BASE.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name in {'output_manifest.json','HANDOFF.md'}:continue
        rows.append(digest(p,'committed Q2R3 packet artifact'))
    write_json(BASE/'output_manifest.json',{'input_version':INPUT_VERSION,'file_count':len(rows),'files':rows,
      'excluded':['output_manifest.json self','HANDOFF.md bound by Git commit','__pycache__ and ignored runtime environments','large immutable caches referenced in input_manifest'],
      'self_entry':False})
    print(json.dumps({'passed':True,'check_groups':len(checks),'input_files':len(inputs),'output_files':len(rows)}))


if __name__=='__main__':main()
