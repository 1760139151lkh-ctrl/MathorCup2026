"""Delivery provenance and physical-ledger checks; freezes only reduced packet."""
from pathlib import Path
import json,csv,hashlib,datetime,py_compile
import numpy as np
from reduced_solver import file_record,write_json

R=Path(__file__).resolve().parents[1]

def main():
    runs=[json.loads(p.read_text()) for p in sorted((R/'results').glob('reduced_[12]d_*.json'))]
    checks={};cache_files={};max_mass=0.;max_vector_error=0.
    checks['expected_34_runs']=len(runs)==34
    checks['all_completed_1800s']=all(r['summary']['execution_status']=='completed' and abs(r['summary']['duration_actual_seconds']-1800)<1e-8 for r in runs)
    checks['all_common_source_volumes']=all(abs(r['summary']['initial_volume_m3']-925200*r['parameters']['thickness_m'])/(925200*r['parameters']['thickness_m'])<1e-12 for r in runs)
    checks['all_primary_null_not_reached_preserved']=all(r['summary']['target_arrivals']['paper_port_symbol']['travel_time_seconds'] is None and r['summary']['target_arrivals']['paper_port_symbol']['arrival_status']=='not_reached_within_horizon' for r in runs)
    files_ok=True;state_ok=True;vector_ok=True
    for r in runs:
        s=r['summary'];max_mass=max(max_mass,abs(s['relative_mass_balance_error']))
        for field_key in ['fields','raw_solver_fields']:
            if field_key not in r:continue
            rec=r[field_key];p=Path(rec['path']);actual=file_record(p,rec['role']);files_ok &= actual['bytes']==rec['bytes'] and actual['sha256']==rec['sha256'];cache_files[str(p)]=actual
        d=np.load(r['fields']['path']);state_ok &= np.isfinite(d['h_final']).all() and np.isfinite(d['maxspeed']).all() and d['h_final'].min()>=0 and np.all(d['maxdepth']+1e-5>=d['h_final']) and len(d['times'])==61 and d['times'][-1]==1800
        if r['model_id'].startswith('independent_1d'):
            speed=np.hypot(d['u_east_final'],d['v_north_final']);expected=np.abs(d['u_path_final']);err=float(np.max(np.abs(speed-expected)));max_vector_error=max(max_vector_error,err);vector_ok &= err<1e-4
    checks.update(cache_field_hashes_match=bool(files_ok),finite_nonnegative_states_and61_saved_times=bool(state_ok),one_d_utm_vector_norm_matches_path_speed=bool(vector_ok),maximum_relative_mass_error_lt_1e_minus12=max_mass<1e-12,all_negative_raw_depths_above_failure_threshold=all(r['summary']['minimum_preclip_depth_m']>=-1e-8 for r in runs))
    bench=json.loads((R/'results/reduced_numerical_validation.json').read_text())
    checks['actual_numba_compilation_signatures_present']=bench['jit_evidence']['all_jit_functions_have_signatures']
    checks['regional_accuracy_false_explicit']=bench['regional_thin_flow_accuracy_qualified'] is False
    rows=list(csv.DictReader((R/'results/reduced_delivery_metrics.csv').open()))
    checks['all_reduced_runs_excluded_from_arrival_envelope']=len(rows)==34 and all(x['include_in_arrival_envelope']=='False' for x in rows)
    targets=list(csv.DictReader((R/'results/reduced_osm_target_arrivals_v2.csv').open()))
    checks['all_170_additional_target_rows']=len(targets)==170 and len(set(x['target_id'] for x in targets))==5 and all(sum(x['run_id']==r['run_id'] for x in targets)==5 for r in runs)
    review=json.loads((R/'results/reduced_visual_review.json').read_text());checks['five_figures_actually_reviewed_and_hashes_match']=len(review['figures'])==5 and all(file_record(x['path'],'')['sha256']==x['sha256'] for x in review['figures'])
    for p in (R/'scripts').glob('reduced_*.py'):py_compile.compile(str(p),doraise=True)
    checks['source_scripts_compile']=True
    validation={'validated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'all_pass':all(checks.values()),'max_relative_mass_error':max_mass,'max_1d_velocity_vector_norm_difference_m_s':max_vector_error,'scope':'Data integrity, conservation and declared exclusions only; regional thin-flow timing remains unqualified.','scientific_adoption':'pending_team_review'}
    write_json(R/'results/reduced_delivery_validation.json',validation)
    if not validation['all_pass']:raise RuntimeError(checks)
    repo_files=[]
    for folder,pattern in [('scripts','reduced_*.py'),('config','reduced_*'),('results','reduced_*'),('figures','reduced_*.png')]:
        for p in sorted((R/folder).glob(pattern)):
            if not p.is_file() or p.name=='reduced_delivery_index.json':continue
            rec=file_record(p,'reduced-model '+folder+' artifact');rec['path']=str(p.relative_to(Path.cwd()));repo_files.append(rec)
    repo_files.append({**file_record(R/'REDUCED_MODELS.md','model equations, actual results, rejection evidence and reproduction'),'path':str((R/'REDUCED_MODELS.md').relative_to(Path.cwd()))})
    protocol=json.loads((R/'config/reduced_protocol.json').read_text())
    for source in protocol['sources']:
        if source.get('path') and Path(source['path']).exists():cache_files[source['path']]=file_record(source['path'],'bounded primary-source download; actual read scope recorded in protocol')
    index={'bundle_version':'q4-r3-reduced-delivery-v1','producer_question':'q4','input_version':'904d7257b899b9f71d1ac9e0eab7479e459eab52','evaluation_stratum':'conditional_scenario_and_numerical_benchmark_separately_labelled','runs':34,'files':repo_files,'cache_files':list(cache_files.values()),'exclusions':['this index, to avoid self-reference','Numba cache/venv and ephemeral logs; environment lock/version metadata retained','other research agents outputs'],'limitations':['both reduced routes excluded from arrival envelope because thin-flow HR accuracy is unqualified','no calibration or independent event validation','1D equivalent-width swept area is not a planar hazard footprint','all 120 new 1D-OSM pairs have no target-cell spatial support; retain missing'],'all_scoped_files_stable_at_delivery':True}
    write_json(R/'results/reduced_delivery_index.json',index)
    print(json.dumps({'all_pass':validation['all_pass'],'files':len(repo_files),'cache_files':len(cache_files),'index':file_record(R/'results/reduced_delivery_index.json','delivery index')}))

if __name__=='__main__':main()
