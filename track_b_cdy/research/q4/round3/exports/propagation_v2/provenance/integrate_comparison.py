"""Integrate actual Q4 records without rerunning solvers or changing frozen packets.

Default writes provisional root tables. --freeze requires settled current plans,
stable source hashes, and a NEW version directory; failure records remain visible.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, io, itertools, json, math, re, shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
R=ROOT/'track_b/research/q4/round3'
C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
INPUT_VERSION={'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52',
               'baseline_manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'}
ACTIVE=['official_cases_copdem_v2.json','official_cases_q2mapped_v2.json',
        'official_cases_q2fullmask_v2.json','official_cases_extended.json',
        'official_cases_physics_v2.json','official_cases_output_flag.json',
        'official_cases_resourcefix.json','official_cases_composite.json']

def utc():return datetime.now(timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def file_digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def number(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None
def truth(x):
    if isinstance(x,bool):return x
    if x is None or x=='':return None
    return str(x).lower() in ['true','1','yes']
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)
def write_json(path,obj):
    tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def dump_csv(path,rows):
    names=list(dict.fromkeys(k for row in rows for k in row))
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader()
        for row in rows:w.writerow({k:canonical(v) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    tmp.replace(path)

class Inputs:
    def __init__(self):self.bytes={};self.records={};self.warnings=[]
    def read(self,path,role,required=True):
        path=Path(path)
        if not path.exists():
            if required:raise FileNotFoundError(path)
            return None
        key=str(path.resolve())
        if key not in self.bytes:
            b=path.read_bytes();self.bytes[key]=b
            self.records[key]={'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                 'bytes':len(b),'sha256':digest(b),'role':role,'read_at_utc':utc()}
        return self.bytes[key]
    def js(self,path,role,required=True):
        b=self.read(path,role,required);return json.loads(b) if b is not None else None
    def csv(self,path,role,required=True):
        b=self.read(path,role,required);return list(csv.DictReader(io.StringIO(b.decode('utf-8-sig')))) if b is not None else []
    def check_bound(self,rec):
        if not rec:return False
        p=Path(rec['path']);p=p if p.is_absolute() else ROOT/p
        if not p.exists():return False
        key=str(p.resolve())
        if key not in self.records:
            self.records[key]={'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),'bytes':p.stat().st_size,'sha256':file_digest(p),'role':rec.get('role','indexed process field'),'read_at_utc':utc(),'hash_operation_scope':'complete byte stream hashed in 1MiB blocks; later array reads for independent target/final residual checks are recorded separately'}
        actual=self.records[key]
        return actual['bytes']==rec['bytes'] and actual['sha256']==rec['sha256']
    def note_array_read(self,path,purpose):
        key=str(Path(path).resolve())
        if key not in self.records:raise RuntimeError('Array input must first be byte-hash bound: '+key)
        operations=self.records[key].setdefault('array_read_operations',[])
        if purpose not in operations:operations.append(purpose)
    def changed(self):
        changed=[]
        for key,rec in self.records.items():
            p=Path(key)
            if not p.exists() or file_digest(p)!=rec['sha256']:changed.append(str(p))
        return changed

def stratum(role):
    return 'numerical_benchmark' if 'benchmark' in str(role) else 'conditional_scenario'

def common_context(runs,arrivals):
    return {'event_id':'B20260826_Chhochen',
        'physical_phase':'bulk_release_propagation_and_target_arrival',
        'time_utc':None,'time_uncertainty':None,'available_time':None,
        'forecast_reference_time':None,'issue_time':None,'valid_time':None,
        'null_time_reasons':{'time_utc':'Absolute UTC of modeled bulk release is unknown; scenario-relative travel times do not supply it',
            'time_uncertainty':'No independently audited absolute release-time uncertainty is available',
            'available_time':'Scenario evidence has no established historical forecast information-availability cutoff',
            'forecast_reference_time':'Not applicable: these are conditional propagation scenarios',
            'issue_time':'Not applicable: this package is not an issued forecast',
            'valid_time':'Not applicable: no absolute forecast-valid timestamp is established'},
        'time_origin':'bulk_release','initiation_to_release_delay_seconds':None,
        'space_object':{'source_geometry_versions':sorted({x['geometry_version'] for x in runs if x.get('geometry_version')}),
            'target_geometry_versions':sorted({x['target_geometry_version'] for x in arrivals if x.get('target_geometry_version')}),
            'crs':'EPSG:32645','crs_code':32645,'axis_order':['easting','northing'],
            'coordinate_unit':'m','position_uncertainty_m':None,
            'position_uncertainty_reason':'Candidate source/target geometry lacks independently quantified positional error',
            'target_detection_geometry':'registered cell centres inside 100m buffers; entity_id distinguishes five OSM representatives from three candidate objects'},
        'variable_semantics':{'time':{'unit':'s','reference':'relative to modeled bulk release',
                'detection_interval':'previous saved output below threshold to first above; not numerical solver-step timing'},
            'depth':{'unit':'m','definition':'model flow depth; native representation and initial depth/terrain differences retained per run'},
            'horizontal_speed':{'unit':'m/s','definition':'horizontal east/north magnitude or explicitly marked along-path equivalent'},
            'native_scalar_speed':{'unit':'m/s','definition':'ravaflow terrain-corrected scalar, retained separately from horizontal speed'},
            'stationary_residual':{'depth_threshold_m':.1,'horizontal_speed_threshold_m_s':.1,
                'definition':'last saved-state h>=0.1m and horizontal speed<0.1m/s; multiphase uses maximum over phases with h_phase>=1e-6m',
                'interpretation':'finite-time stationary residual, not permanent or observed deposit; missing conservative phase velocity remains unavailable'},
            'quality_control':['input/case/execution/log/field byte-hash binding','finite and nonnegative saved states',
                'actual native saved times and requested horizon distinguished','arrival threshold h>=0.1m within registered 100m buffers',
                'sampling definitions, boundary evidence and native mass-budget limitations retained'],
            'qualification':'QC gates do not establish predictive or mass-conservation qualification'},
        'data_role':'scenario','evidence_status':'candidate','row_evaluation_stratum_is_authoritative':True,
        'input_version':dict(INPUT_VERSION),'human_scientific_adoption':'pending_team_review',
        'statistical_weights':None,'independent_local_event_validation_count':0}

def attach_quality_contract(ins,runs,metrics,arrivals):
    audit=ins.js(R/'results/dclaw_mass_audit.json','independent raw-state DClaw mass audit',False)
    ins.read(R/'sources/dclaw_mass_source_audit.json','fixed-source DClaw mass audit provenance',False)
    audit_by={x['run_id']:x for x in (audit or {}).get('runs',[])}
    by={x['run_id']:x for x in runs}
    for row in runs:
        row['scientifically_qualified_for_prediction']=False
        row['mass_conservation_qualified']=False
        row['mass_conservation_qualification_status']='unresolved_native_flux_source_qfix_ledger' if row.get('model_id')=='dclaw' else 'not_demonstrated_as_regional_physical_qualification'
        row['passes_execution_and_time_gates']=bool(row.get('execution_status')=='completed' and row.get('state_horizon_complete') and row.get('fields_hash_matches_index'))
    for row in arrivals:
        run=by[row['run_id']]
        row['passes_execution_time_boundary_gates']=bool(run['passes_execution_and_time_gates']
            and row.get('source_snapshot_stable') and not row.get('domain_affected_before_arrival')
            and row.get('arrival_status') in ['arrived','not_arrived_by_horizon']
            and row.get('formal_requested_horizon_status') in ['arrived_by_requested_horizon','not_arrived_at_saved_outputs_through_requested_horizon'])
        row['conditional_diagnostic_range_eligible']=bool(row.get('include_in_arrival_envelope'))
        row['scientifically_qualified_for_prediction']=False
        row['mass_conservation_qualified']=False
        row['mass_conservation_qualification_status']=run['mass_conservation_qualification_status']
        row['arrival_envelope_gate_scope']='conditional diagnostic eligibility only; execution/time/field/boundary gates do not imply numerical, mass-conservation or predictive qualification'
    for row in runs:
        row['conditional_diagnostic_range_eligible']=any(x['conditional_diagnostic_range_eligible'] for x in arrivals if x['run_id']==row['run_id'])
    for row in metrics:
        run=by[row['run_id']]
        for key in ['scientifically_qualified_for_prediction','mass_conservation_qualified','mass_conservation_qualification_status','conditional_diagnostic_range_eligible']:
            row[key]=run[key]
        if row['run_id'] in audit_by:
            evidence=audit_by[row['run_id']]
            row['raw_state_mass_audit_reference']='results/dclaw_mass_audit.json'
            row['raw_state_mass_audit_final_adjusted_residual_fraction']=evidence['estimated_boundary_adjusted_final_residual_fraction']
            row['raw_state_mass_audit_causal_attribution']=(audit or {}).get('causal_attribution')
            row['raw_state_mass_audit_selected_saved_states']=[{k:x.get(k) for k in ['time_s','mass_change_fraction','boundary_h_max_m','boundary_abs_hu_hv_max_m2_s']} for x in evidence['rows'] if x['time_s'] in [20.,180.]]
    return audit

def apply_q2_compact_quality(ins,runs,metrics,arrivals):
    review=ins.js(R/'config/q2_compact_quality_review_04.json','registered compact-source numerical qualification review',False)
    if not review:return None
    evidence_path=ROOT/review['evidence']['path'];evidence=ins.js(evidence_path,'independently crosschecked Q2 compact ASCII/native budget evidence')
    if digest(ins.bytes[str(evidence_path.resolve())])!=review['evidence']['sha256']:raise RuntimeError('Compact-source quality evidence hash mismatch')
    evidence_by={x['run_id']:x for x in evidence['runs']};by={x['run_id']:x for x in runs}
    for i,rid in enumerate(review['run_ids']):
        if rid not in by:continue
        run=by[rid];item=evidence_by[rid];bound=item['bound_fields']
        binding_ok=ins.check_bound(bound) and bound.get('execution_sha256')==run.get('execution_sha256') and bound.get('log_sha256')==run['raw_execution_json'].get('log_sha256')
        run.update(include_in_arrival_envelope=False,conditional_diagnostic_range_eligible=False,
            scientifically_qualified_for_prediction=False,mass_conservation_qualified=False,
            mass_conservation_qualification_status='unresolved_compact_source_budget_discrepancy',
            numerical_qualification='unqualified_compact_source_underresolution_and_budget_discrepancy',
            source_quality_review_version=review['version'],source_quality_evidence_binding_matches=binding_ok,
            source_support_cells=review['source_support_cells'][i],source_equivalent_full_cells=review['source_equivalent_full_cells'][i],
            source_quality_reason=review['quality_reason'])
    for row in metrics:
        if row['run_id'] not in evidence_by:continue
        run=by[row['run_id']];item=evidence_by[row['run_id']]
        for key in ['numerical_qualification','source_quality_review_version','source_quality_evidence_binding_matches','source_support_cells','source_equivalent_full_cells','source_quality_reason','mass_conservation_qualification_status']:
            row[key]=run[key]
        row.update(include_in_arrival_envelope=False,conditional_diagnostic_range_eligible=False,
            scientifically_qualified_for_prediction=False,mass_conservation_qualified=False,
            ascii_raster_source_adjusted_budget_relative_residual=item['ascii_raster_source_adjusted_budget_relative_residual'],
            native_internal_summary_mass_budget_relative_residual=item['native_internal_summary_mass_budget_relative_residual'],
            budget_representations_are_separate=True)
    for row in arrivals:
        if row['run_id'] not in evidence_by:continue
        run=by[row['run_id']]
        for key in ['numerical_qualification','source_quality_review_version','source_quality_reason','source_support_cells','source_equivalent_full_cells','mass_conservation_qualification_status']:
            row[key]=run[key]
        row.update(include_in_arrival_envelope=False,conditional_diagnostic_range_eligible=False,
            scientifically_qualified_for_prediction=False,mass_conservation_qualified=False)
    return review

def stationary_residual_metrics(ins,runs,metrics):
    """Last-state kinematic residual, never inferred from cumulative maxima."""
    import numpy as np
    by={x['run_id']:x for x in runs}
    definition='last saved state with h>=0.1m and finite horizontal speed<0.1m/s; stationary residual, not measured deposit'
    for row in metrics:
        run=by[row['run_id']];field=run.get('field_reference')
        row.update(stationary_residual_definition=definition,stationary_residual_evaluation_time_seconds=run.get('actual_end_time_seconds'),
            stationary_residual_area_m2=None,stationary_residual_equivalent_width_area_m2=None,
            stationary_residual_volume_m3=None,stationary_residual_max_depth_m=None)
        if run.get('execution_status')!='completed' or not field or not run.get('fields_hash_matches_index'):
            row['stationary_residual_status']='not_evaluated_without_completed_bound_saved_state';continue
        path=Path(field['path']);path=path if path.is_absolute() else ROOT/path
        ins.note_array_read(path,'NumPy last-state depth and available horizontal velocity inspected for stationary residual; finite/missing velocity guards applied; 1D width or 2D affine geometry used when evaluable')
        with np.load(path,allow_pickle=False) as a:
            if run['producer']=='reduced':
                h=a['h_final'];speed=np.hypot(a['u_east_final'],a['v_north_final'])
                dx=number(run['parameters'].get('resolution_m'))
                is1d=run['model_id'].startswith('independent_1d')
                cell_area=dx*number(run['raw_record_json'].get('width')) if is1d else dx*dx
            else:
                h=a['depth_final'];is1d=False
                if 'stationary_criterion_speed_final' in a.files:
                    speed=a['stationary_criterion_speed_final']
                    row['stationary_residual_velocity_basis']='dedicated native final horizontal criterion; multiphase uses maximum speed among phases with h_phase>=1e-6m'
                elif run.get('model_id')=='ravaflow_multi' or run.get('comparison_model_subgroup') in ['composite_solid_water','generic_three_material_proxy']:
                    row['stationary_residual_status']='conservative_wet_phase_final_velocity_unavailable';continue
                else:
                    horizontal=a['horizontal_speed_frames'] if 'horizontal_speed_frames' in a.files else None
                    if horizontal is None or horizontal.size==0:
                        row['stationary_residual_status']='horizontal_velocity_unavailable';continue
                    speed=horizontal[-1]
                    row['stationary_residual_velocity_basis']='native single-phase or DClaw final horizontal velocity'
                tr=a['transform'];cell_area=abs(float(tr[0]*tr[4]-tr[1]*tr[3]))
            if h.shape!=speed.shape or not np.isfinite(h).all() or not np.isfinite(speed[h>=.1]).all():
                row['stationary_residual_status']='missing_or_nonfinite_last_state';continue
            mask=(h>=.1)&np.isfinite(speed)&(speed<.1)
            area=float(mask.sum()*cell_area)
            row['stationary_residual_status']='saved_state_kinematic_statistic_only'
            row['stationary_residual_equivalent_width_area_m2' if is1d else 'stationary_residual_area_m2']=area
            row['stationary_residual_volume_m3']=float(h[mask].sum()*cell_area)
            row['stationary_residual_max_depth_m']=float(h[mask].max()) if mask.any() else 0.
            row['stationary_residual_speed_definition']='horizontal E/N magnitude' if not is1d else 'mapped along-path speed magnitude; equivalent-width geometry'
            row['stationary_residual_source_fields_sha256']=field['sha256']

def bind_existing_replays(ins):
    replay=ins.js(R/'results/replay_execution_comparison.json','actual reproduction of existing cases; not new model cases or independent events',False)
    if replay:
        for row in replay.get('replayed_cases',[]):
            for key in ['original_fields','replayed_fields']:
                field=row.get(key)
                if not field:continue
                p=Path(field['path'])
                if not p.exists() or not ins.check_bound({**field,'bytes':p.stat().st_size,'role':'existing-case replay field evidence'}):
                    raise RuntimeError('Existing-case replay field hash mismatch: '+str(p))
    return replay

def bind_native_controls(ins,explicit_indexes=None):
    """Bind acquired effective native controls, never infer a past runner hash."""
    indexes=[Path(x) if Path(x).is_absolute() else R/Path(x) for x in explicit_indexes or []]
    if not indexes:indexes=sorted((R/'results').glob('official*control*index*.json'))
    records=[];issues=[];owner_runs=[]
    def walk(obj):
        if isinstance(obj,dict):
            if all(k in obj for k in ['path','bytes','sha256']):yield obj
            for value in obj.values():yield from walk(value)
        elif isinstance(obj,list):
            for value in obj:yield from walk(value)
    for path in indexes:
        packet=ins.js(path,'acquired actual native input/control provenance index')
        owner_runs+=packet.get('runs',[])
        for entry in walk(packet):
            p=Path(entry['path']);p=p if p.is_absolute() else ROOT/p
            role=entry.get('role','actual acquired native input/control bytes')
            if not ins.check_bound({**entry,'path':str(p),'role':role}):
                issues.append({'path':str(p),'issue':'missing_or_hash_mismatch','expected':entry});continue
            if p.stat().st_size<=256*1024:
                b=p.read_bytes()
                try:b.decode('utf-8')
                except UnicodeDecodeError:pass
                else:ins.read(p,'small acquired actual native control text snapshot: '+role)
            records.append({'path':str(p),'bytes':entry['bytes'],'sha256':entry['sha256'],'role':role})
    unique={x['path']:x for x in records}
    return {'status':'indexed_actual_generated_controls' if indexes and unique and not issues else 'index_missing' if not indexes else 'control_dependency_mismatch',
        'index_paths':[str(x.relative_to(ROOT)) if x.is_relative_to(ROOT) else str(x) for x in indexes],
        'unique_file_count':len(unique),'issues':issues,
        'owner_indexed_run_count':len(owner_runs),
        'historical_adapter_identity_status_counts':dict(collections.Counter(x.get('historical_adapter_identity_status','unreported') for x in owner_runs)),
        'control_role_counts':dict(collections.Counter(x['role'] for x in unique.values())),
        'provenance_scope':'Actual acquired generated *.data/native parameter/run scripts and raster/topo inputs; execution-time provenance only where explicitly recorded by runtime owner',
        'unknown_historical_runner_hashes_are_not_reconstructed':True,
        'current_or_repository_adapter_hash_is_not_a_substitute_for_unrecorded_historical_runner_hash':True}

def build_reduced(ins):
    runs=[];metrics=[];arrivals=[]
    packet=ins.js(R/'results/reduced_delivery_index.json','immutable adopted reduced delivery index')
    if digest(ins.bytes[str((R/'results/reduced_delivery_index.json').resolve())])!='cd82c52cc772ed7702a6f4452f4bfbbe5c9a092bbbeeed46d356d09709a4a7dc':raise RuntimeError('Adopted reduced index bytes changed; do not silently replace frozen input')
    for entry in packet['files']:
        if not ins.check_bound(entry):raise RuntimeError('Frozen reduced artifact mismatch: '+entry['path'])
    raw=ins.csv(R/'results/reduced_delivery_metrics.csv','frozen reduced regional delivery')
    for row in raw:
        rid=row['run_id'];rec=ins.js(R/f'results/reduced_{rid}.json','frozen reduced raw run')
        summary=rec['summary'];is1d=rec['model_id'].startswith('independent_1d');s=row['scenario_id']
        base={'run_id':rid,'producer':'reduced','model_id':row['model_id'],'scenario_id':s,
          'base_scenario_id':s,'parameter_version':row['parameter_version'],'geometry_version':row['geometry_version'],
          'upstream_model_id':None,'upstream_parameter_version':None,'upstream_onset_status':None,
          'release_mapping_version':'common_reference','mechanism_id':rec['mechanism_id'],
          'experiment_id':'path_and_material_sensitivity' if is1d else 'regional_ofat_grid_timestep','path_id':rec.get('path_id'),
          'evaluation_stratum':'conditional_scenario','plan_scope':'current_registered',
          'execution_attempted':True,'native_solver_started':True,'execution_status':summary['execution_status'],
          'raw_execution_status':summary['execution_status'],'requested_horizon_seconds':summary['duration_requested_seconds'],
          'actual_end_time_seconds':summary['duration_actual_seconds'],'wall_seconds':summary['wall_seconds'],
          'parameters':rec['parameters'],'initial_velocity_east_north_m_s':[0,0],
          'initiation_to_release_delay_seconds':None,'if_released_propagation':True,
          'time_origin':'bulk_release','state_horizon_complete':summary['duration_actual_seconds']>=summary['duration_requested_seconds']-1e-8,
          'pipeline_returncode':0,'finite_state':True,'nonnegative_state':summary['minimum_preclip_depth_m']>=-1e-8,
          'fields_hash_matches_index':ins.check_bound(rec['fields']),'field_reference':rec['fields'],
          'numerical_qualification':'unqualified_thin_flow_HR_acceleration_bias',
          'include_in_scientific_parameter_comparison':True,'include_in_arrival_envelope':False,
          'event_timing_validated':False,'independent_event_validation_count':0,
          'raw_record_json':rec,'source_table_row_json':row}
        runs.append(base)
        initial=summary['initial_volume_m3'];inflow=summary['inflow_volume_m3']
        metrics.append({'run_id':rid,'model_id':base['model_id'],'scenario_id':s,'evaluation_stratum':'conditional_scenario',
          'initial_volume_m3':initial,'final_domain_volume_m3':summary['final_domain_volume_m3'],
          'initial_mass_kg':summary.get('initial_mass_kg'),'final_domain_mass_kg':summary.get('final_mass_kg'),
          'outflow_volume_m3':summary['outflow_volume_m3'],'inflow_volume_m3':inflow,
          'boundary_inflow_fraction_of_initial':inflow/initial if initial else None,
          'implicit_boundary_supply':inflow>initial*1e-6,
          'native_mass_budget_relative_residual':summary['relative_mass_balance_error'],
          'mass_budget_definition':'step-level conservative volume ledger; incoming flux and clipping booked; constant prescribed density',
          'max_depth_m':summary['max_depth_m'],'speed_peak_m_s':summary['maximum_speed_any_wet_m_s'],
          'speed_definition':'horizontal along-path magnitude' if is1d else 'horizontal E/N magnitude',
          'speed_wet_depth_cutoff_m':1e-9,'peak_sampling_definition':'every solver step',
          'impact_area_m2':None if is1d else summary['footprint_area_hmax_ge_01_m2'],
          'equivalent_width_swept_area_m2':summary['footprint_area_hmax_ge_01_m2'] if is1d else None,
          'impact_area_definition':'not comparable to 2D area' if is1d else 'planar grid area where step cumulative hmax>=.1m',
          'numerical_qualification':base['numerical_qualification'],'include_in_arrival_envelope':False})
        for target,a in summary['target_arrivals'].items():
            travel=a['travel_time_seconds'];bracket=a.get('arrival_time_bracket_seconds')
            arrivals.append({'run_id':rid,'scenario_id':s,'base_scenario_id':s,'model_id':base['model_id'],
              'target_id':target,'target_geometry_version':row['geometry_version'],'geometry_version':row['geometry_version'],
              'parameter_version':row['parameter_version'],'raw_status':a['arrival_status'],
              'arrival_status':'arrived' if travel is not None else 'not_arrived_by_horizon' if 'not_reached' in a['arrival_status'] else a['arrival_status'],
              'observed_hit':travel is not None,'observed_hit_time_seconds':travel,
              'travel_time_seconds':travel,'arrival_bracket_lower_seconds':bracket[0] if bracket else None,
              'arrival_bracket_upper_seconds':bracket[1] if bracket else None,
              'arrival_definition':a['definition'],'evaluation_end_time_seconds':base['actual_end_time_seconds'],
              'requested_horizon_seconds':base['requested_horizon_seconds'],'include_in_arrival_envelope':False,
              'domain_affected_before_arrival':None,'numerical_qualification':base['numerical_qualification'],
              'evaluation_stratum':'conditional_scenario','initiation_to_release_delay_seconds':None,'time_origin':'bulk_release',
              'if_released_propagation':True,'probability_weight':None,'event_timing_validated':False})
    for row in ins.csv(R/'results/reduced_osm_target_arrivals_v2.csv','frozen reduced five-object postprocessing'):
        runs_by_id={x['run_id']:x for x in runs};base=runs_by_id[row['run_id']]
        arrivals.append({'run_id':row['run_id'],'scenario_id':row['scenario_id'],'base_scenario_id':base['base_scenario_id'],
          'model_id':row['model_id'],'target_id':row['target_id'],'target_kind':row['target_kind'],
          'target_geometry_version':row['geometry_version'],'geometry_version':base['geometry_version'],
          'parameter_version':row['parameter_version'],'raw_status':row['arrival_status'],
          'arrival_status':'not_arrived_by_horizon' if 'not_reached' in row['arrival_status'] else row['arrival_status'],
          'observed_hit':number(row['travel_time_seconds']) is not None,'observed_hit_time_seconds':number(row['travel_time_seconds']),
          'travel_time_seconds':number(row['travel_time_seconds']),
          'arrival_bracket_lower_seconds':number(row['arrival_lower_seconds']),'arrival_bracket_upper_seconds':number(row['arrival_upper_seconds']),
          'arrival_definition':row['definition'],'evaluation_end_time_seconds':number(row['actual_horizon_seconds']),
          'requested_horizon_seconds':1800,'include_in_arrival_envelope':False,
          'domain_affected_before_arrival':None,'numerical_qualification':base['numerical_qualification'],
          'evaluation_stratum':'conditional_scenario','initiation_to_release_delay_seconds':None,'time_origin':'bulk_release',
          'if_released_propagation':True,'probability_weight':None,'event_timing_validated':False,'raw_source_row_json':row})
    return runs,metrics,arrivals

def collect_official(ins,active_configs):
    active=set();active_sources={};planned={}
    applicability=ins.js(R/'config/model_applicability_decision_03.json','registered material applicability and necessary-case decision',False) or {}
    classes=applicability.get('applicability_classes',{})
    diagnostic_ids=set(classes.get('generic_material_proxy_diagnostic_only',{}).get('run_ids',[]))
    excluded_ids=set(classes.get('target_material_proxy_inapplicable_not_run',{}).get('run_ids',[]))
    replacement=applicability.get('replacement',{})
    retry_budget=ins.js(R/'config/execution_budget_amendment_02.json','registered legacy retry process and cancellation scope',False) or {}
    cancellation_index=ins.js(R/'results/official_superseded_cancellations.json','independent stopped-retry cancellation receipts',False) or {}
    cancellation_by_id={x['run_id']:x for x in cancellation_index.get('records',[])}
    upstream={}
    for path in sorted((R/'inputs/q2').glob('**/release_states*.csv')):
        for state in ins.csv(path,'delivered Q2 upstream state and mechanism keys'):
            upstream[state['scenario_id']]=state
    # Only this explicitly authorized supplemental family is discovered dynamically;
    # historical generic/surface2 preparation packets remain outside the active plan.
    supplemental=sorted(set((R/'config').glob('official_cases_entrain*.json')))
    for protocol in sorted((R/'config').glob('official_entrain*protocol*.json')):
        ins.js(protocol,'preregistered bounded native entrainment scenario protocol')
    for name in list(active_configs)+supplemental:
        path=Path(name);path=path if path.is_absolute() else R/'config'/path
        packet=ins.js(path,'current registered official plan',False)
        if packet:
            for item in packet.get('cases',[]):
                active.add(item['run_id']);planned[item['run_id']]=item
                active_sources.setdefault(item['run_id'],[]).append(str(path))
    if replacement.get('new_run_id'):
        rid=replacement['new_run_id'];active.add(rid)
        planned[rid]={'run_id':rid,'case':str(C/'runs'/rid/'case.json'),'model':'ravaflow_multi','evidence_role':'conditional_scenario'}
        active_sources.setdefault(rid,[]).append(str(R/'config/model_applicability_decision_03.json'))
    tables={x['run_id']:x for x in ins.csv(R/'results/official_runs.csv','official parsed run snapshot')}
    metrics={x['run_id']:x for x in ins.csv(R/'results/official_metrics.csv','official parsed metric snapshot')}
    validation=ins.js(R/'results/official_validation.json','official numerical evidence snapshot')
    checks={x['run_id']:x for x in validation['checks']}
    fields={x['run_id']:x for x in ins.js(R/'results/official_fields.json','official process field index')['fields']}
    raw_arrivals=ins.csv(R/'results/official_arrivals.csv','official primary target snapshot')
    history=ins.csv(R/'results/official_histories.csv','official saved-time mass/volume history',False)
    initial_history={}
    for row in history:
        rid=row['run_id']
        if rid not in initial_history or number(row['time_s'])<number(initial_history[rid]['time_s']):initial_history[rid]=row
    extra=ins.csv(R/'results/official_target_arrivals_v2.csv','official OSM target snapshot',False)
    cases={};executions={}
    for folder in sorted((C/'runs').glob('*')):
        if not (folder/'case.json').exists():continue
        case=ins.js(folder/'case.json','official case inventory');rid=case['run_id'];cases[rid]=case
        ex=ins.js(folder/'execution.json','official actual execution/classification',False)
        if ex is not None:executions[rid]=ex
    for rid in active-cases.keys():
        item=planned[rid];path=Path(item.get('case',C/'runs'/rid/'case.json'))
        case=ins.js(path,'registered case outside prepared cache',False)
        cases[rid]=case or {'run_id':rid,'model':item.get('model','unprepared_unknown'),
            'evidence_role':item.get('evidence_role','conditional_scenario'),
            'unprepared_plan_entry':item}
    runs=[];outmetrics=[]
    for rid,case in sorted(cases.items()):
        raw=tables.get(rid,{});m=metrics.get(rid,{});check=checks.get(rid,{});ex=executions.get(rid,{});original=ex.get('original_execution_record') or {}
        gate=ex.get('quality_gate') or check.get('quality_gate') or raw.get('quality_gate')
        csurface=case.get('csurface',2) if case['model'].startswith('ravaflow') else None
        quarantine=bool(gate) or case['model']=='ravaflow_single' and csurface==2
        scope='current_registered' if rid in active else 'superseded_configuration' if quarantine or csurface==2 else 'historical_preparation'
        log_exists=(C/'runs'/rid/'run.log').exists()
        attempted=bool(ex.get('command') or ex.get('started_utc') or original.get('command') or original.get('started_utc') or log_exists or 'cancel' in str(ex.get('status','')))
        evaluation_stratum=stratum(case.get('evidence_role'))
        if rid in excluded_ids:applicability_class='target_material_proxy_inapplicable_not_run'
        elif rid in diagnostic_ids:applicability_class='generic_material_proxy_diagnostic_only'
        elif scope=='current_registered' and evaluation_stratum=='conditional_scenario':applicability_class='target_applicable_required' if applicability else 'pending_review'
        else:applicability_class='numerical_benchmark' if evaluation_stratum=='numerical_benchmark' else 'outside_current_required_scope'
        required=applicability_class=='target_applicable_required'
        completion_required=required or rid in diagnostic_ids and attempted or not applicability and scope=='current_registered' and evaluation_stratum=='conditional_scenario'
        returncode=ex.get('returncode');actual_end=number(check.get('actual_last_time_seconds',m.get('last_time_s')))
        requested=number(case.get('end_seconds'));complete=actual_end is not None and requested is not None and actual_end>=requested-.01
        field=fields.get(rid);field_ok=ins.check_bound(field) if field else False
        case_path=C/'runs'/rid/'case.json'
        case_sha=digest(ins.bytes[str(case_path.resolve())]) if str(case_path.resolve()) in ins.bytes else None
        execution_case_matches=bool(not ex or ex.get('case_sha256')==case_sha)
        log_path=Path(ex.get('log_path',C/'runs'/rid/'run.log'))
        log_matches=ins.check_bound({'path':str(log_path),'bytes':log_path.stat().st_size,'sha256':ex['log_sha256'],'role':'native execution log bound to actual attempt'}) if ex.get('log_sha256') and log_path.exists() else None
        execution_path=C/'runs'/rid/'execution.json'
        execution_sha=digest(ins.bytes[str(execution_path.resolve())]) if str(execution_path.resolve()) in ins.bytes else None
        def bound_attempt_matches(record):
            comparisons=[record.get('execution_sha256')==execution_sha if record.get('execution_sha256') else None,
                record.get('log_sha256')==ex.get('log_sha256') if record.get('log_sha256') else None,
                record.get('source_fields_sha256')==field.get('sha256') if record.get('source_fields_sha256') and field else None]
            return False if False in comparisons else True if any(x is not None for x in comparisons) else None
        parsed_attempt_matches=bound_attempt_matches(check)
        metric_attempt_matches=bound_attempt_matches(m)
        field_attempt_matches=bound_attempt_matches(field or {})
        bed_path=Path(case['erodible_bed']) if case.get('erodible_bed') else None
        bed_hash_matches=ins.check_bound({'path':str(bed_path),'bytes':bed_path.stat().st_size,
            'sha256':case['erodible_bed_sha256'],'role':'preregistered finite erodible-bed thickness input'}) if bed_path and bed_path.exists() and case.get('erodible_bed_sha256') else None
        stale_prior_retry=rid==retry_budget.get('run_id') and 'active at report time' in retry_budget.get('actual_execution_context','') and log_matches is False
        cancellation=cancellation_by_id.get(rid) or ins.js(C/'runs'/rid/'cancellation.json','separate retry cancellation receipt',False) or {}
        cancelled_retry_confirmed=bool(cancellation.get('status')=='cancelled_superseded_compute_priority'
            and cancellation.get('native_stop_returncode')==0 and cancellation.get('prior_attempt_execution_sha256')==execution_sha
            and cancellation.get('retry_log_sha256_at_cancellation')==file_digest(log_path)) if cancellation and log_path.exists() else False
        parsed_current=bool(check) and (not check.get('case_sha256') or check['case_sha256']==case_sha)
        if 'exit_code' in check:parsed_current=parsed_current and check['exit_code']==returncode
        parsed_current=parsed_current and execution_case_matches and log_matches is not False and parsed_attempt_matches is not False and metric_attempt_matches is not False and field_attempt_matches is not False
        field_case_matches=not field or field.get('case_sha256')==case_sha
        finite=truth(check.get('finite'));nonnegative=truth(check.get('nonnegative_to_1e-8'))
        if rid in excluded_ids and not attempted:status='not_run_material_applicability_exclusion'
        elif 'cancel' in str(ex.get('status','')).lower() or ex.get('cancelled'):status='cancelled'
        elif stale_prior_retry and cancelled_retry_confirmed:status='cancelled_superseded_compute_priority'
        elif stale_prior_retry:status='running_retry_with_stale_prior_attempt_metadata'
        elif quarantine:status='quarantined_configuration'
        elif not ex and attempted:status='running_unfinalized'
        elif not ex:status='planned_without_execution'
        elif returncode is None:status=str(ex.get('status') or 'missing_execution_result')
        elif returncode!=0:status='pipeline_failure'
        elif not parsed_current:status='finished_unanalysed'
        elif check.get('solver_success_field')==0 or check.get('log_contains_numerical_failure') or finite is False or nonnegative is False:status='numerical_failure'
        elif not complete:status='early_terminated_before_requested_horizon'
        elif not field_ok or not field_case_matches:status='field_missing_or_index_stale'
        else:status='completed'
        q2=case.get('upstream_fullmask_record') or case.get('upstream_release_record') or upstream.get(case.get('scenario_id'),{})
        onset=case.get('upstream_onset_status',q2.get('onset_status'))
        if_released=truth(case.get('if_released_propagation'))
        if onset=='never_crossed':if_released=True
        if if_released is None and stratum(case.get('evidence_role'))=='conditional_scenario':if_released=True
        geometry=case.get('geometry_version') or ('q4-r3-spatial-copdem-v1' if case.get('terrain_id')=='copdem' else None)
        qual='excluded_single_phase_surface2' if quarantine else 'conditional_native_execution_only' if status=='completed' else 'unqualified_'+status
        base={'run_id':rid,'producer':'official','model_id':case['model'],'scenario_id':case.get('scenario_id'),
          'base_scenario_id':case.get('base_scenario_id',case.get('scenario_id')),
          'parameter_version':case.get('upstream_parameter_version') or case.get('official_protocol_version','q4-r3-official-v1'),
          'geometry_version':geometry,'upstream_model_id':case.get('upstream_model_id',q2.get('model_id')),
          'upstream_parameter_version':case.get('upstream_parameter_version',q2.get('parameter_version')),
          'upstream_onset_status':onset,'release_mapping_version':case.get('release_mapping_version', 'q4-r3-q2-mapped-release-v1' if rid.startswith('q2') else 'common_reference'),
          'mechanism_id':q2.get('mechanism_id') or case.get('upstream_mechanism_id') or ('pore_pressure' if case['model']=='dclaw' else 'multiphase_coupling' if case['model']=='ravaflow_multi' else 'homogeneous_frictional_mixture'),
          'propagation_mechanism_id':'pore_pressure' if case['model']=='dclaw' else 'multiphase_coupling' if case['model']=='ravaflow_multi' else 'homogeneous_frictional_mixture',
          'experiment_id':'q2_release_transfer' if rid.startswith('q2') else 'domain_sensitivity' if 'extended' in rid else 'official_regional_or_benchmark',
          'evaluation_stratum':stratum(case.get('evidence_role')),'plan_scope':scope,
          'applicability_decision_version':applicability.get('version'),'applicability_class':applicability_class,
          'applicable_required':required,'completion_required':completion_required,
          'not_run_exclusion_but_execution_attempted':rid in excluded_ids and attempted,
          'comparison_model_subgroup':'composite_solid_water' if rid.startswith('composite_') else 'generic_three_material_proxy' if case['model']=='ravaflow_multi' else 'homogeneous_frictional_mixture' if case['model']=='ravaflow_single' else 'solid_fluid_porepressure' if case['model']=='dclaw' else case['model'],
          'comparison_reference_run_id':replacement.get('reference_run_id') if rid==replacement.get('new_run_id') else case.get('comparison_reference_run_id',case.get('reference_comparison_run_id',case.get('domain_comparison_parent_run_id'))),
          'ablation_scope':replacement.get('label') if rid==replacement.get('new_run_id') else None,
          'current_plan_sources':active_sources.get(rid,[]),'execution_attempted':attempted,
          'native_solver_started':True if stale_prior_retry else False if ex.get('solver_started') is False else None,
          'execution_status':status,'raw_execution_status':raw.get('status',ex.get('status')),
          'quality_gate':gate,'requested_horizon_seconds':requested,'actual_end_time_seconds':actual_end,
          'wall_seconds':ex.get('elapsed_seconds'),'initial_velocity_east_north_m_s':case.get('initial_velocity_east_north_m_s'),
          'initiation_to_release_delay_seconds':None,'if_released_propagation':if_released,
          'time_origin':'bulk_release','state_horizon_complete':complete,'pipeline_returncode':None if stale_prior_retry else returncode,
          'prior_attempt_returncode':returncode if stale_prior_retry else None,'current_retry_with_prior_execution_record':stale_prior_retry,
          'separate_cancellation_receipt':cancellation or None,
          'cancellation_receipt_hashes_confirmed':cancelled_retry_confirmed,
          'cancellation_is_numerical_failure':False if cancelled_retry_confirmed else None,
          'native_success_field':check.get('solver_success_field'),'finite_state':finite,'nonnegative_state':nonnegative,
          'fields_hash_matches_index':field_ok,'field_case_hash_matches':field_case_matches,'parsed_case_hash_matches':parsed_current,'field_reference':field,
          'numerical_qualification':qual,'include_in_scientific_parameter_comparison':status=='completed' and not quarantine and rid not in diagnostic_ids|excluded_ids and bed_hash_matches is not False,
          'include_in_generic_material_diagnostic_comparison':status=='completed' and rid in diagnostic_ids,
          'include_in_arrival_envelope':status=='completed' and not quarantine and stratum(case.get('evidence_role'))!='numerical_benchmark' and rid not in diagnostic_ids|excluded_ids and bed_hash_matches is not False,
          'event_timing_validated':False,'independent_event_validation_count':0,
          'regional_numerical_accuracy_qualified':False,'scientifically_adopted_for_prediction':False,
          'arrival_envelope_gate_scope':'execution, bound fields, actual time and boundary threshold only; scientific qualification still pending',
          'csurface':csurface,'image_id':ex.get('image_id'),'container_id':ex.get('container_id'),
          'base_image_id':ex.get('base_image_id'),'runtime_image_identity_complete':bool(ex.get('image_id')),
          'solver_build':case.get('solver_build','official_original_frozen_source'),
          'resourcefix_parent_run_id':case.get('resourcefix_parent_run_id'),
          'solver_binary_sha256':ex.get('resourcefix_binary_sha256'),
          'historical_adapter_sha256_at_start':ex.get('adapter_sha256_at_start'),
          'historical_adapter_hash_status':'recorded_at_execution_start' if ex.get('adapter_sha256_at_start') else 'unknown_no_contemporaneous_hash',
          'entrainment_configuration':{**{k:v for k,v in case.items() if any(term in k.lower() for term in ['entrain','erodible','bed_scenario','max_available_bed'])},'native_extra_parameters':{k:v for k,v in case.get('extras',{}).items() if 'entrain' in k.lower()}},
          'entrainment_bed_input_hash_matches':bed_hash_matches,
          'entrainment_evidence_scope':'prescribed bounded scenario; added material requires separate native source and boundary ledger; no inference from domain mass change',
          'execution_case_hash_matches':execution_case_matches,'execution_log_hash_matches':log_matches,
          'parsed_execution_attempt_hash_matches':parsed_attempt_matches,'metric_execution_attempt_hash_matches':metric_attempt_matches,
          'field_execution_attempt_hash_matches':field_attempt_matches,'execution_sha256':execution_sha,
          'boundary_definition':'three-cell edge-store/absorbing native domain' if case['model'].startswith('ravaflow') else 'zero-gradient/extrapolation native ghost cells; signed net flow',
          'parameters':{k:case.get(k) for k in ['resolution_m','release_thickness_m','mu_basal','xi','extras','drag','virtualmass','cmelt','entrain','entrainment','entrainmax','entrainment_coefficient','centrainment','erodible_bed','erodible_bed_sha256','max_available_bed_volume_m3','erodible_bed_density_kg_m3','phase_volume_fractions','densities_kg_m3','bulk_density_kg_m3','material_volume_fractions','passive_material_volume_fractions']},
          'raw_case_json':case,'raw_execution_json':ex,'raw_validation_json':check,'raw_metrics_json':m,'raw_runs_row_json':raw}
        runs.append(base)
        outmetrics.append({'run_id':rid,'model_id':case['model'],'scenario_id':base['scenario_id'],'solver_build':base['solver_build'],
          'evaluation_stratum':base['evaluation_stratum'],'max_depth_m':number(m.get('max_depth_over_saved_outputs_m')),
          'speed_peak_m_s':number(m.get('max_speed_over_saved_outputs_m_s')),'speed_definition':m.get('speed_definition'),
          'speed_wet_depth_cutoff_m':.1,'horizontal_speed_peak_m_s':number(m.get('max_horizontal_speed_over_saved_outputs_m_s')),
          'native_cumulative_speed_scalar_peak_m_s':number(m.get('native_global_cumulative_speed_scalar_m_s',m.get('native_cumulative_max_speed_m_s'))),
          'native_cumulative_max_depth_m':number(m.get('native_cumulative_max_depth_m')),
          'peak_sampling_definition':m.get('peak_sampling_definition'),'impact_area_m2':number(m.get('impact_area_m2')),
          'impact_area_definition':'planar area where saved-output hmax>=.1m; undersamples native maxima',
          'initial_volume_m3':check.get('first_output_volume_m3'),'final_domain_volume_m3':number(m.get('end_volume_m3')),
          'initial_mass_kg':number(initial_history.get(rid,{}).get('mass_kg')),'final_domain_mass_kg':number(m.get('end_mass_kg')),
          'domain_mass_change_fraction':number(m.get('mass_change_fraction')),
          'significant_mass_change_without_recorded_boundary_depth':abs(number(m.get('mass_change_fraction')) or 0)>.01 and check.get('first_boundary_threshold_time_seconds') is None,
          'initial_volume_relative_difference':check.get('initial_volume_relative_difference'),
          'initial_depth_vs_supplied_max_difference_m':check.get('initial_depth_vs_supplied_max_difference_m'),
          'initial_depth_normalized_L1_difference':check.get('initial_depth_normalized_L1_difference'),
          'initial_supplied_support_cells':check.get('initial_supplied_support_cells'),'initial_native_support_cells':check.get('initial_native_support_cells'),
          'initial_effective_bed_vs_input_mae_m':check.get('initial_effective_bed_vs_input_mae_m'),
          'initial_effective_bed_vs_input_rmse_m':check.get('initial_effective_bed_vs_input_rmse_m'),
          'initial_effective_bed_vs_input_max_abs_m':check.get('initial_effective_bed_vs_input_max_abs_m'),
          'first_boundary_threshold_time_seconds':check.get('first_boundary_threshold_time_seconds'),
          'native_mass_budget_relative_residual':check.get('native_mass_budget_relative_residual'),
          'estimated_boundary_adjusted_mass_residual_fraction':check.get('estimated_boundary_adjusted_mass_residual_fraction'),
          'mass_budget_definition':check.get('boundary_estimate_scope') if case['model']=='dclaw' else check.get('native_budget_definition'),
          'native_entrainment_source_budget_evidence':{scope:{k:v for k,v in obj.items() if any(term in k.lower() for term in ['entrain','erosion','source_mass','source_volume','mass_budget','volume_budget'])} for scope,obj in [('validation',check),('metrics',m)]},
          'entrainment_reference_run_id':base['comparison_reference_run_id'] if case.get('erodible_bed') else None,
          'prescribed_erodible_bed_capacity_volume_m3':number(case.get('max_available_bed_volume_m3')),
          'prescribed_erodible_bed_density_kg_m3':number(case.get('erodible_bed_density_kg_m3')),
          'prescribed_erodible_bed_capacity_mass_kg':number(case['max_available_bed_volume_m3'])*number(case['erodible_bed_density_kg_m3']) if case.get('max_available_bed_volume_m3') is not None and case.get('erodible_bed_density_kg_m3') is not None else None,
          'native_conservation_verified':False if case['model']=='dclaw' else None,
          'boundary_flux_sampling_sensitivity':check.get('boundary_flux_sampling_sensitivity_residual_fractions'),
          'numerical_qualification':qual,'raw_metric_json':m})
    by={x['run_id']:x for x in runs};arrivals=[]
    additional=ins.csv(R/'results/spatial_targets_v2.csv','all currently registered OSM target representatives',False)
    saved_arrival_cache={}
    def independent_saved_check(base,row):
        """Bind an observer row to actual immutable NPZ time/depth, without solving."""
        import numpy as np
        rid=base['run_id'];tid=row.get('target',row.get('target_id'))
        if rid not in saved_arrival_cache:
            target_list=list(cases[rid].get('targets',[]))+[{**x,'id':x['target_id'],'xy':[float(x['x_m']),float(x['y_m'])],'buffer_m':100} for x in additional]
            with np.load(base['field_reference']['path'],allow_pickle=False) as a:
                t=a['time_s'];h=a['depth_frames'];tr=a['transform'];ny,nx=h.shape[1:]
                ins.note_array_read(base['field_reference']['path'],'NumPy time_s/depth_frames/transform loaded to independently re-evaluate registered target masks and saved-output arrival intervals')
                rr,cc=np.indices((ny,nx));xx=tr[0]*(cc+.5)+tr[1]*(rr+.5)+tr[2];yy=tr[3]*(cc+.5)+tr[4]*(rr+.5)+tr[5]
                found={}
                for target in target_list:
                    mask=(xx-target['xy'][0])**2+(yy-target['xy'][1])**2<=target.get('buffer_m',100)**2
                    hit=np.flatnonzero((h[:,mask]>=.1).any(axis=1)) if mask.any() else []
                    k=int(hit[0]) if len(hit) else None
                    found[target['id']]={'outside':not bool(mask.any()),'time':float(t[k]) if k is not None else None,
                        'lower':float(t[k-1]) if k is not None and k>0 else 0. if k==0 and t[0]==0 else None,'actual_end':float(t[-1]),
                        'last_saved_output_at_or_before_requested_horizon':float(t[t<=base['requested_horizon_seconds']][-1]) if (t<=base['requested_horizon_seconds']).any() else None}
            saved_arrival_cache[rid]=found
        expected=saved_arrival_cache[rid].get(tid)
        if expected is None:return False,'target_missing_from_preregistered_geometry',None
        raw_time=number(row.get('arrival_seconds',row.get('arrival_time_seconds')))
        time_match=(raw_time==expected['time'])
        observer_end=number(row.get('evaluation_end_time_seconds'))
        end_match=observer_end is None or abs(observer_end-expected['actual_end'])<.01
        run_end_match=abs(expected['actual_end']-(base['actual_end_time_seconds'] or -1))<.01
        return bool(time_match and end_match and run_end_match),'independently_recomputed_from_hashed_saved_depth_and_actual_times',expected
    for row in raw_arrivals+extra:
        rid=row['run_id']
        if rid not in by:continue
        base=by[rid];check=base['raw_validation_json'];raw_time=number(row.get('arrival_seconds',row.get('arrival_time_seconds')))
        observed=raw_time is not None;boundary=number(row.get('first_boundary_threshold_time_seconds',check.get('first_boundary_threshold_time_seconds')))
        affected=boundary is not None and (raw_time is None or boundary<raw_time)
        target_field_matches=row.get('source_fields_sha256')==fields.get(rid,{}).get('sha256') if row.get('source_fields_sha256') else None
        target_attempt_matches=(not row.get('execution_sha256') or row['execution_sha256']==base.get('execution_sha256')) and (not row.get('log_sha256') or row['log_sha256']==base['raw_execution_json'].get('log_sha256'))
        binding_method='observer_explicit_fields_sha256' if target_field_matches is not None else 'missing_observer_field_hash'
        expected=None
        if base['execution_status']=='completed' and base['field_reference']:
            independently_matches,binding_method,expected=independent_saved_check(base,row)
            target_field_matches=independently_matches and target_field_matches is not False and target_attempt_matches
        raw_status=row.get('status');valid=base['execution_status']=='completed' and target_field_matches
        if not valid:status=base['execution_status'];travel=None
        elif raw_status in ['out_of_domain','outside_domain','missing']:status='outside_domain' if 'domain' in raw_status else 'missing';travel=None
        elif observed:status='arrived';travel=raw_time
        else:status='not_arrived_by_horizon';travel=None
        arrivals.append({'run_id':rid,'scenario_id':base['scenario_id'],'base_scenario_id':base['base_scenario_id'],
          'model_id':base['model_id'],'upstream_model_id':base['upstream_model_id'],'upstream_parameter_version':base['upstream_parameter_version'],
          'solver_build':base['solver_build'],
          'upstream_onset_status':base['upstream_onset_status'],'if_released_propagation':base['if_released_propagation'],
          'geometry_version':base['geometry_version'],'target_geometry_version':row.get('geometry_version') or 'q4-r3-spatial-copdem-v1',
          'release_mapping_version':base['release_mapping_version'],'parameter_version':base['parameter_version'],
          'target_id':row.get('target',row.get('target_id')),'entity_id':row.get('entity_id'),'target_kind':row.get('target_kind'),
          'raw_status':raw_status,'arrival_status':status if target_field_matches is not False else 'stale_target_field_reference','observed_hit':observed,'observed_hit_time_seconds':raw_time,
          'travel_time_seconds':travel,'arrival_bracket_lower_seconds':expected['lower'] if expected and valid else number(row.get('previous_below_threshold_time_seconds')),
          'arrival_bracket_upper_seconds':raw_time,'arrival_definition':row.get('arrival_definition'),
          'requested_horizon_seconds':base['requested_horizon_seconds'],'evaluation_end_time_seconds':base['actual_end_time_seconds'],
          'first_boundary_threshold_time_seconds':boundary,'domain_affected_before_arrival':affected,
          'include_in_arrival_envelope':bool(base['include_in_arrival_envelope'] and not affected and status in ['arrived','not_arrived_by_horizon']),
          'numerical_qualification':base['numerical_qualification'],'evaluation_stratum':base['evaluation_stratum'],
          'regional_numerical_accuracy_qualified':False,'scientifically_adopted_for_prediction':False,
          'arrival_envelope_gate_scope':base['arrival_envelope_gate_scope'],
          'event_timing_validated':False,'initiation_to_release_delay_seconds':None,'time_origin':'bulk_release',
          'probability_weight':None,'target_field_hash_matches':target_field_matches,'target_binding_method':binding_method,
          'independent_saved_field_arrival_check':expected,'source_fields_sha256':fields.get(rid,{}).get('sha256'),'raw_source_row_json':row})
    # Preserve target rows for planned/unanalysed/failure cases with no parsed output.
    seen={(x['run_id'],x['target_id']) for x in arrivals}
    for rid,base in by.items():
        target_list=list(cases[rid].get('targets',[]))
        if base['evaluation_stratum']=='conditional_scenario':target_list += [{**x,'id':x['target_id']} for x in additional]
        for target in target_list:
            if (rid,target['id']) in seen:continue
            arrivals.append({'run_id':rid,'scenario_id':base['scenario_id'],'base_scenario_id':base['base_scenario_id'],
              'model_id':base['model_id'],'target_id':target['id'],'entity_id':target.get('entity_id'),'target_kind':target.get('target_kind'),
              'target_geometry_version':target.get('geometry_version') or 'q4-r3-spatial-copdem-v1','geometry_version':base['geometry_version'],
              'parameter_version':base['parameter_version'],'upstream_onset_status':base['upstream_onset_status'],
              'if_released_propagation':base['if_released_propagation'],'arrival_status':base['execution_status'],
              'observed_hit':False,'observed_hit_time_seconds':None,'travel_time_seconds':None,
              'arrival_definition':'no parsed saved fields; target definition retained in raw case',
              'requested_horizon_seconds':base['requested_horizon_seconds'],'evaluation_end_time_seconds':base['actual_end_time_seconds'],
              'include_in_arrival_envelope':False,'numerical_qualification':base['numerical_qualification'],
              'evaluation_stratum':base['evaluation_stratum'],'initiation_to_release_delay_seconds':None,'time_origin':'bulk_release',
              'event_timing_validated':False,'probability_weight':None})
    return runs,outmetrics,arrivals,validation,active

def archived_attempts(ins,runs,arrivals):
    """Keep distinct adapter/native attempts; a duplicate archive is one attempt."""
    by={x['run_id']:x for x in runs};extra=[];extra_arrivals=[]
    def identity(ex):
        ex=ex.get('original_execution_record') or ex
        return canonical({k:ex.get(k) for k in ['command','started_utc','case_sha256']})
    seen={identity(x['raw_execution_json']) for x in runs if x.get('raw_execution_json') and not x.get('current_retry_with_prior_execution_record')}
    for path in sorted((C/'runs').glob('*/attempts/*/execution.json')):
        ex=ins.js(path,'archived actual execution attempt');key=identity(ex)
        archive_log=path.parent/'run.log'
        if archive_log.exists():
            ins.check_bound({'path':str(archive_log),'bytes':archive_log.stat().st_size,'sha256':ex.get('log_sha256',file_digest(archive_log)),'role':'archived attempt log'})
        if key in seen:continue
        seen.add(key);parent=path.parents[2].name;base=by.get(parent)
        if not base:raise RuntimeError('Archived execution has no case inventory: '+str(path))
        rid=parent+'::attempt::'+path.parent.name
        row={**base,'run_id':rid,'record_kind':'archived_execution_attempt','parent_case_run_id':parent,
            'plan_scope':'historical_preparation','execution_attempted':True,
            'native_solver_started':False if 'mapcalc_adapter_failure' in path.parent.name else ex.get('solver_started'),
            'execution_status':'pipeline_failure' if ex.get('returncode') else 'historical_attempt_unanalysed',
            'pipeline_returncode':ex.get('returncode'),'current_retry_with_prior_execution_record':False,
            'prior_attempt_returncode':None,'actual_end_time_seconds':None,'state_horizon_complete':False,
            'wall_seconds':ex.get('elapsed_seconds'),'field_reference':None,'fields_hash_matches_index':False,
            'include_in_scientific_parameter_comparison':False,'include_in_arrival_envelope':False,
            'numerical_qualification':'archived_adapter_failure' if 'mapcalc_adapter_failure' in path.parent.name else 'historical_attempt_unqualified',
            'raw_execution_json':ex,'raw_validation_json':{},'raw_metrics_json':{},'raw_runs_row_json':{},
            'archived_attempt_metadata_path':str(path),'image_id':ex.get('image_id'),'base_image_id':ex.get('base_image_id'),
            'execution_sha256':digest(ins.bytes[str(path.resolve())]),'execution_log_hash_matches':file_digest(archive_log)==ex.get('log_sha256') if archive_log.exists() else None}
        extra.append(row)
        for target in [x for x in arrivals if x['run_id']==parent]:
            extra_arrivals.append({**target,'run_id':rid,'arrival_status':row['execution_status'],'observed_hit':False,
                'observed_hit_time_seconds':None,'travel_time_seconds':None,'arrival_bracket_lower_seconds':None,
                'arrival_bracket_upper_seconds':None,'include_in_arrival_envelope':False,'evaluation_end_time_seconds':None,
                'numerical_qualification':row['numerical_qualification'],'raw_source_row_json':{},'target_field_hash_matches':None})
    return extra,extra_arrivals

def benchmarks(ins):
    evidence=ins.js(R/'results/reduced_numerical_validation.json','frozen reduced numerical benchmarks');rows=[]
    for case in evidence['cases']:
        for i,run in enumerate(case.get('runs',[{'summary':case.get('summary',{})}])):
            s=run.get('summary',{});rows.append({'run_id':f"reduced_benchmark::{case['case_id']}::{i}",
              'producer':'reduced','model_id':'independent_rigid_ode' if 'rigid' in case['case_id'] else 'independent_fv_numerical_benchmark',
              'scenario_id':case['case_id'],'evaluation_stratum':'numerical_benchmark','plan_scope':'current_registered',
              'execution_attempted':True,'execution_status':s.get('execution_status','completed_configuration'),
              'actual_end_time_seconds':s.get('duration_actual_seconds'),'requested_horizon_seconds':s.get('duration_requested_seconds'),
              'wall_seconds':s.get('wall_seconds'),'check_pass':case['pass'],'numerical_qualification':'declared_property_check_only',
              'include_in_arrival_envelope':False,'event_timing_validated':False,'raw_case_json':case,'raw_config_json':run})
    for p in sorted((C/'benchmarks').glob('**/*execution.json')):
        ex=ins.js(p,'external official benchmark execution');name=ex.get('name',p.parent.name)
        rows.append({'run_id':'official_external_benchmark::'+str(p.relative_to(C/'benchmarks')),
          'producer':'official_external_benchmark','model_id':'dclaw' if 'gully' in name else 'ravaflow',
          'scenario_id':name,'evaluation_stratum':'numerical_benchmark','plan_scope':'current_registered',
          'execution_attempted':True,'execution_status':'completed_pipeline_only' if ex.get('returncode')==0 else 'pipeline_failure',
          'pipeline_returncode':ex.get('returncode'),'wall_seconds':ex.get('elapsed_seconds'),
          'include_in_arrival_envelope':False,'event_timing_validated':False,'numerical_qualification':'inspect_official_benchmark_fields_separately','raw_execution_json':ex})
    return rows,evidence

def within_framework_pairs(runs,metrics):
    mm={x['run_id']:x for x in metrics};pairs=[]
    eligible=[x for x in runs if x.get('evaluation_stratum')=='conditional_scenario' and x.get('execution_status')=='completed' and x.get('plan_scope')=='current_registered']
    def group_key(x):return (x['model_id'],x.get('comparison_model_subgroup',x['model_id']),x.get('solver_build','independent_frozen_r3'))
    for (model,subgroup,build),items in itertools.groupby(sorted(eligible,key=group_key),key=group_key):
        group=list(items)
        explicit_refs={x.get('comparison_reference_run_id') for x in group}
        refs=[x for x in group if re.search(r'(?:_ref(?:_|$)|_P[123]_ref$)',x['run_id']) or x['run_id'] in explicit_refs]
        for ref in refs:
            for other in group:
                if other['run_id']==ref['run_id']:continue
                # Same release/base key or explicit domain-parent comparison; never a cross-framework gain.
                parent=other.get('comparison_reference_run_id') or other.get('raw_case_json',{}).get('domain_comparison_parent_run_id')
                same_release_key=other.get('base_scenario_id')==ref.get('base_scenario_id')
                common_ofat=ref.get('release_mapping_version')=='common_reference' and other.get('release_mapping_version')=='common_reference'
                if not same_release_key and parent!=ref['run_id'] and not common_ofat:continue
                if ref.get('path_id')!=other.get('path_id'):continue
                a=mm.get(ref['run_id'],{});b=mm.get(other['run_id'],{})
                pair={'model_id':model,'comparison_model_subgroup':subgroup,'solver_build':build,'reference_run_id':ref['run_id'],'other_run_id':other['run_id'],
                  'ablation_scope':other.get('ablation_scope'),
                  'comparison_scope':'within-framework conditional sensitivity; not calibrated model gain',
                  'scientifically_qualified_for_prediction':False,'mass_conservation_qualified':False,
                  'reference_conditional_diagnostic_range_eligible':ref.get('conditional_diagnostic_range_eligible'),
                  'other_conditional_diagnostic_range_eligible':other.get('conditional_diagnostic_range_eligible'),
                  'reference_parameters':ref.get('parameters'),'other_parameters':other.get('parameters'),
                  'same_geometry_version':ref.get('geometry_version')==other.get('geometry_version'),
                  'same_base_scenario_key':same_release_key,
                  'same_initial_volume_within1e_minus6':abs(a.get('initial_volume_m3',0)-b.get('initial_volume_m3',0))/max(abs(a.get('initial_volume_m3') or 0),1)<1e-6 if a.get('initial_volume_m3') is not None and b.get('initial_volume_m3') is not None else None,
                  'same_initial_mass_within1e_minus6':abs(a.get('initial_mass_kg',0)-b.get('initial_mass_kg',0))/max(abs(a.get('initial_mass_kg') or 0),1)<1e-6 if a.get('initial_mass_kg') is not None and b.get('initial_mass_kg') is not None else None,
                  'changed_parameter_fields':[k for k in set(ref.get('parameters',{}))|set(other.get('parameters',{})) if ref.get('parameters',{}).get(k)!=other.get('parameters',{}).get(k)],
                  'ref_numerical_qualification':ref.get('numerical_qualification'),'other_numerical_qualification':other.get('numerical_qualification')}
                for key in ['max_depth_m','impact_area_m2','stationary_residual_area_m2','stationary_residual_volume_m3']:
                    av,bv=number(a.get(key)),number(b.get(key));pair[key+'_difference']=bv-av if av is not None and bv is not None else None
                pairs.append(pair)
    return pairs

def decorate_time_contract(row):
    """Separate actual saved-output detection from the requested evaluation horizon."""
    upper=number(row.get('observed_hit_time_seconds'));lower=number(row.get('arrival_bracket_lower_seconds'))
    horizon=number(row.get('requested_horizon_seconds'));travel=number(row.get('travel_time_seconds'))
    valid=row.get('arrival_status')=='arrived' and travel is not None
    row['arrival_interval_definition']='between previous saved output below threshold and first saved output above; no solver-step precision claim'
    if upper==0:
        row['arrival_bracket_lower_seconds']=0.;row['arrival_bracket_upper_seconds']=0.
        row['arrival_interval_type']='initial_condition_already_above_threshold'
    elif upper is not None and lower is None:
        row['arrival_interval_type']='left_censored_at_first_saved_output'
    else:row['arrival_interval_type']='saved_output_detection_interval' if upper is not None else 'right_censored_or_missing_as_status'
    row['arrival_within_requested_horizon']=bool(valid and horizon is not None and travel<=horizon) if valid else None
    row['formal_requested_travel_time_seconds']=travel if row['arrival_within_requested_horizon'] is True else None
    if valid and horizon is not None and travel>horizon:
        row['formal_requested_horizon_status']='arrival_interval_straddles_requested_horizon' if lower is None or lower<horizon else 'not_arrived_at_saved_outputs_through_requested_horizon'
        row['include_in_arrival_envelope']=False
    elif valid:row['formal_requested_horizon_status']='arrived_by_requested_horizon'
    elif row.get('arrival_status')=='not_arrived_by_horizon':row['formal_requested_horizon_status']='not_arrived_at_saved_outputs_through_requested_horizon'
    else:row['formal_requested_horizon_status']='unqualified_or_missing_observation'
    row['requested_horizon_claim_scope']='formal requested horizon fields; actual evaluation end may exceed requested time'

def early_export(ins,runs,metrics,arrivals,numerical,summary,version,selection='dclaw'):
    """Freeze a selected completed partial packet; rolling root tables stay provisional."""
    if not re.fullmatch(r'propagation_v[0-9]+',version):raise ValueError('version must be propagation_vN')
    dest=R/'exports'/version
    if dest.exists():raise FileExistsError('Never overwrite an early or final frozen version')
    packet_status='frozen_partial_q2mapped_for_adapter_review' if selection=='q2mapped' else 'frozen_partial_for_q3_review'
    q2_review=ins.js(R/'config/q2_compact_quality_review_04.json','registered compact-source numerical qualification review',selection=='q2mapped') if selection=='q2mapped' else None
    requested_ids=set(q2_review['run_ids']) if q2_review else None
    selected=[dict(x,integration_status=packet_status) for x in runs
        if x.get('producer')=='official' and (x['run_id'] in requested_ids if requested_ids is not None else x.get('model_id')=='dclaw')
        and x.get('evaluation_stratum')=='conditional_scenario' and x.get('execution_status')=='completed']
    if not selected or requested_ids is not None and {x['run_id'] for x in selected}!=requested_ids:raise RuntimeError('Selected partial packet cases are not all completed/parsed/hash-bound')
    ids={x['run_id'] for x in selected}
    selected_metrics=[dict(x,integration_status=packet_status) for x in metrics if x['run_id'] in ids]
    selected_arrivals=[dict(x,integration_status=packet_status) for x in arrivals if x['run_id'] in ids]
    if not all(x.get('target_field_hash_matches') is True for x in selected_arrivals):
        raise RuntimeError('Early package requires every selected target to match immutable saved fields')
    # Only selected case/attempt/log/fields and physical input dependencies gate this partial export.
    external=[];metadata=[];metadata_origins={}
    controls_packet=ins.js(R/'results/official_native_control_index.json','actual native controls index for selected early packet')
    controls_by={x['run_id']:x for x in controls_packet['runs']}
    for run in selected:
        rid=run['run_id'];case=run['raw_case_json'];ex=run['raw_execution_json']
        for path,sha,role in [(case.get('dem'),case.get('dem_sha256'),'immutable native input terrain'),
                              (case.get('release'),case.get('release_sha256'),'immutable native release thickness')]:
            if path and sha:
                p=Path(path)
                if not p.exists() or not ins.check_bound({'path':path,'bytes':p.stat().st_size,'sha256':sha,'role':role}):
                    raise RuntimeError('Selected physical input hash mismatch: '+str(path))
                external.append({**ins.records[str(p.resolve())],'storage':'immutable_external_cache'})
        for p,role in [(C/'runs'/rid/'case.json','native case'),(C/'runs'/rid/'execution.json','native execution record')]:
            b=ins.read(p,role)
            if digest(p.read_bytes())!=digest(b):raise RuntimeError('Selected metadata changed during early snapshot: '+str(p))
            metadata.append((Path('provenance')/rid/p.name,b,role))
        field=run['field_reference'];p=Path(field['path'])
        if not ins.check_bound(field) or file_digest(p)!=field['sha256']:raise RuntimeError('Selected field bytes changed: '+str(p))
        external.append({**field,'storage':'immutable_external_cache'})
        if ex.get('log_path'):
            p=Path(ex['log_path'])
            if not ex.get('log_sha256') or not p.exists() or file_digest(p)!=ex['log_sha256']:
                raise RuntimeError('Selected execution log no longer matches actual attempt')
            external.append({'path':str(p),'bytes':p.stat().st_size,'sha256':ex['log_sha256'],
                             'role':'immutable native execution log','storage':'immutable_external_cache'})
            if selection=='q2mapped':
                relative=Path('provenance')/rid/'run.log';metadata.append((relative,p.read_bytes(),'actual native execution log snapshot'));metadata_origins[str(relative)]=str(p)
        if selection=='q2mapped':
            if rid not in controls_by:raise RuntimeError('Selected native control index missing case: '+rid)
            for control in controls_by[rid]['native_input_controls']:
                if not ins.check_bound(control):raise RuntimeError('Selected actual native control hash mismatch: '+control['path'])
                p=Path(control['path']);b=p.read_bytes()
                if len(b)<=256*1024:
                    try:b.decode('utf-8')
                    except UnicodeDecodeError:external.append({**control,'storage':'immutable_external_cache'})
                    else:
                        relative=Path('provenance')/rid/'native_controls'/p.name;metadata.append((relative,b,control.get('role','actual native control text')));metadata_origins[str(relative)]=str(p)
                else:external.append({**control,'storage':'immutable_external_cache'})
            saved=controls_by[rid].get('saved_executed_adapter_path');saved_sha=controls_by[rid].get('saved_executed_adapter_sha256')
            if saved and saved_sha:
                p=Path(saved)
                if file_digest(p)!=saved_sha:raise RuntimeError('Saved actual adapter hash mismatch')
                relative=Path('provenance')/rid/'adapter_executed.py';metadata.append((relative,p.read_bytes(),'saved actual executed adapter; contemporaneous hash retained'));metadata_origins[str(relative)]=str(p)
            check=run['raw_validation_json']
            if check.get('native_summary_path'):
                p=Path(check['native_summary_path'])
                if file_digest(p)!=check.get('native_summary_sha256'):raise RuntimeError('Selected native internal summary hash mismatch')
                relative=Path('provenance')/rid/'native_internal_summary.txt';metadata.append((relative,p.read_bytes(),'actual native internal unscaled volume summary'));metadata_origins[str(relative)]=str(p)
                for nout in p.parent.glob('*nout1.txt'):
                    relative=Path('provenance')/rid/nout.name;metadata.append((relative,nout.read_bytes(),'actual native nout success/source/edge accounting output'));metadata_origins[str(relative)]=str(nout)
    fields=list({x['path']:x for x in external}.values())
    selected_by={x['run_id']:x for x in selected}
    for row in selected_arrivals:
        row['source_snapshot_stable']=True
        row['source_snapshot_stability_scope']='selected run case/execution/log/native input/field hashes; unrelated rolling observer tables may advance'
        row['include_in_arrival_envelope']=bool(selected_by[row['run_id']]['include_in_arrival_envelope'] and not row.get('domain_affected_before_arrival') and row['arrival_status'] in ['arrived','not_arrived_by_horizon'])
    attach_quality_contract(ins,selected,selected_metrics,selected_arrivals)
    if selection=='q2mapped':
        apply_q2_compact_quality(ins,selected,selected_metrics,selected_arrivals)
        if not all(x.get('source_quality_evidence_binding_matches') is True for x in selected):raise RuntimeError('Selected compact-source budget evidence must match actual attempt')
        for name in ['config/q2_compact_quality_review_04.json',q2_review['evidence']['path'].removeprefix('track_b/research/q4/round3/')]:
            source=R/name;relative=Path('quality')/source.name
            metadata.append((relative,ins.read(source,'selected compact-source numerical qualification evidence'),'compact source quality review/evidence'));metadata_origins[str(relative)]=str(source)
        upstream=R/'inputs/q2/release_bundle_q2-r3-release-v1'
        for source in [upstream/'bundle.json',upstream/'upstream_bundle.json',upstream/'files/results/release_states.csv']:
            relative=Path('provenance/upstream_q2')/source.name
            metadata.append((relative,ins.read(source,'actual delivered Q2 compact release lineage'),'delivered Q2 compact source lineage'));metadata_origins[str(relative)]=str(source)
    specific_limits=[
        'Only completed Q2 compact p0000/p0036 mapped-release diagnostics; full-source geometry and other required native cases remain outside this partial packet',
        'All selected runs and targets excluded from arrival envelope; computed raw travel and saved-output brackets retained solely for adapter/diagnostic review',
        'Compact supports are8/16 raster cells and2.7778/11.1111 equivalent full cells; source underresolution and mass discrepancy remain unresolved',
        'ASCII source-adjusted budget residuals +21.1534%/+12.6130% and separate native-internal summary residuals +21.3729%/+12.7163%; no tolerance declared to certify pass',
        'Upstream never_crossed remains if-released propagation; absolute bulk-release UTC and initiation-to-release delay remain unknown'] if selection=='q2mapped' else [
        'Early partial DClaw packet only; all-route and Q2 mapping comparisons remain pending',
        'Boundary-affected arrivals are conditional diagnostics, excluded from the arrival envelope',
        'copdem_120_dclaw_ref historical build-container image ID is unavailable; base image/container and exact execution/log/fields retained']
    partial_summary={'status':packet_status,'early_selection':selection,'generated_at_utc':utc(),
        'partial':True,'provisional_compare_scope':True,'selected_run_ids':sorted(ids),
        'selected_run_count':len(ids),'all_routes_completed':False,
        'full_inventory_snapshot_count':summary['run_inventory_count'],
        'full_actual_regional_attempts_snapshot':summary['actual_regional_execution_attempted_count'],
        'remaining_and_excluded_run_statuses':[{k:x.get(k) for k in ['run_id','model_id','evaluation_stratum','plan_scope','execution_attempted','execution_status','solver_build']} for x in runs if x['run_id'] not in ids],
        'arrival_status_counts':dict(collections.Counter(x['arrival_status'] for x in selected_arrivals)),
        'arrival_envelope_eligible_count':sum(x['include_in_arrival_envelope'] for x in selected_arrivals),
        'within_framework_pairs':within_framework_pairs(selected,selected_metrics),
        'independent_local_training_events':0,'independent_local_validation_events':0,
        'probability_weights':None,'coverage_probability_claimed':False,
        'time_origin':'bulk_release','initiation_to_release_delay_seconds':None,
        'limitations':specific_limits+[
            'Saved-output target detection was independently re-evaluated against hashed native NPZ times/depth; not solver-step arrival precision',
            'Five OSM representatives refer to three distinct candidate entities, not five independent validation targets',
            'No independent validation events, statistical weighting, predictive adoption or probability coverage claim']}
    selected_numerical={'status':partial_summary['status'],'generated_at_utc':utc(),
        'qualification_by_run':[{k:x.get(k) for k in ['run_id','execution_status','numerical_qualification','state_horizon_complete','finite_state','nonnegative_state','fields_hash_matches_index','execution_case_hash_matches','execution_log_hash_matches','runtime_image_identity_complete','source_quality_review_version','source_support_cells','source_equivalent_full_cells','source_quality_evidence_binding_matches','scientifically_qualified_for_prediction','mass_conservation_qualified']} for x in selected],
        'official':{'checks':[x for x in numerical['official']['checks'] if x['run_id'] in ids or selection=='dclaw' and x['run_id']=='flatrest_60_dclaw']},
        'independent_local_event_validation_count':0,'native_conservation_verified':False,
        'declared_property_pass_is_not_regional_accuracy':True}
    dest.mkdir(parents=True);manifest=[]
    def record(path,role,source_path=None):
        manifest.append({'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':file_digest(path),'role':role,'storage':'copied_versioned_metadata',**({'source_path':source_path} if source_path else {})})
    for name,rows in [('model_runs.csv',selected),('comparison_metrics.csv',selected_metrics),('target_arrivals.csv',selected_arrivals)]:
        p=dest/name;dump_csv(p,rows);record(p,name.removesuffix('.csv'))
    for name,obj in [('comparison_summary.json',partial_summary),('numerical_validation.json',selected_numerical),('fields_index.json',{'fields':[x for x in fields if x.get('role')=='actual_official_process_fields']})]:
        p=dest/name;write_json(p,obj);record(p,name.removesuffix('.json'))
    for relative,b,role in metadata:
        p=dest/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);record(p,role,metadata_origins.get(str(relative)))
    if selection=='q2mapped':
        p=dest/'native_controls_index.json';write_json(p,{'runs':[controls_by[rid] for rid in sorted(ids)],'source_index_path':'results/official_native_control_index.json','scope':'selected actual saved generated controls; source_path in manifest maps copied control bytes'});record(p,'selected actual native controls provenance index')
    for name in ['spatial_targets_v2.csv','computational_geometries.geojson']:
        source=R/'results'/name;b=ins.read(source,'shared target and spatial definition',False)
        if b is not None:
            p=dest/'geometry'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);record(p,'target geometry')
    code=dest/'provenance/integrate_comparison.py';code.write_bytes(ins.bytes[str(Path(__file__).resolve())]);record(code,'exact early-package postprocessor source')
    index={'files':manifest+fields,'all_entries_have_path_bytes_sha256_role':True,'file_list_excludes_self':True,
        'source_observer_snapshot_hashes':[rec for rec in ins.records.values() if rec['path'].startswith('track_b/research/q4/round3/results/official_')],
        'dependency_scope':'copied selected-run metadata; immutable byte-hash-bound external native fields, logs and initial rasters',
        'rolling_root_input_index_at_export':{'path':'results/comparison_input_index.json','sha256':file_digest(R/'results/comparison_input_index.json')}}
    p=dest/'input_index.json';write_json(p,index);record(p,'selected dependency and observer snapshot index')
    bundle={'bundle_version':'q4-r3-'+version.replace('_','-'),'producer_question':'q4',
        'input_version':INPUT_VERSION,'status':partial_summary['status'],
        'common_context':common_context(selected,selected_arrivals),
        'early_selection':selection,
        'lineage_by_run':[{k:x.get(k) for k in ['run_id','scenario_id','base_scenario_id','upstream_model_id','upstream_parameter_version','mechanism_id','parameter_version','release_mapping_version','geometry_version','upstream_onset_status','if_released_propagation','initiation_to_release_delay_seconds']} for x in selected],
        'scientifically_qualified_for_prediction':False,'mass_conservation_qualified':False,
        'partial':True,'provisional_compare_scope':True,'all_routes_completed':False,
        'generated_at_utc':utc(),'selected_run_ids':sorted(ids),'evaluation_stratum':'conditional_scenario',
        'files':manifest+fields,'file_list_excludes_self':True,
        'table_paths':{name:str((dest/(name+'.csv')).relative_to(ROOT)) for name in ['model_runs','comparison_metrics','target_arrivals']},
        'probability_weights':None,'independent_local_validation_events':0,'coverage_probability_claimed':False,
        'time_origin':'bulk_release','initiation_to_release_delay_seconds':None,
        'limitations':partial_summary['limitations'],'human_scientific_adoption':'pending_team_review'}
    write_json(dest/'bundle.json',bundle);write_json(R/'exports/propagation_bundle.json',bundle)
    return {'bundle_path':str((dest/'bundle.json').relative_to(ROOT)),'bundle_sha256':file_digest(dest/'bundle.json'),
        'files':len(bundle['files']),'run_ids':sorted(ids),'arrivals':partial_summary['arrival_status_counts'],
        'arrival_envelope_eligible':partial_summary['arrival_envelope_eligible_count']}

def main():
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group();mode.add_argument('--freeze',action='store_true');mode.add_argument('--early-freeze',action='store_true');parser.add_argument('--early-selection',choices=['dclaw','q2mapped'],default='dclaw');parser.add_argument('--version',default='propagation_v1');parser.add_argument('--active-config',action='append');parser.add_argument('--control-index',action='append');args=parser.parse_args()
    ins=Inputs();ins.read(Path(__file__),'integration source code');policy=ins.js(R/'config/comparison_policy.json','preregistered comparison policy')
    reduced,rm,ra=build_reduced(ins);official,om,oa,ov,active=collect_official(ins,args.active_config or ACTIVE);br,rv=benchmarks(ins)
    archived,archived_arrivals=archived_attempts(ins,official,oa);official+=archived;oa+=archived_arrivals
    runs=reduced+official+br;metrics=rm+om;arrivals=ra+oa
    run_by_id={x['run_id']:x for x in runs}
    target_entities={x['target_id']:x.get('entity_id') for x in ins.csv(R/'results/spatial_targets_v2.csv','all currently registered OSM target representatives',False)}
    for row in arrivals:
        row['inundation_or_runout_reference']=run_by_id[row['run_id']].get('field_reference')
        if not row.get('entity_id'):row['entity_id']=target_entities.get(row.get('target_id'))
        decorate_time_contract(row)
    stationary_residual_metrics(ins,runs,metrics)
    replay_evidence=bind_existing_replays(ins)
    native_controls=bind_native_controls(ins,args.control_index)
    ins.js(R/'results/dclaw_mass_audit.json','independent raw-state DClaw mass audit',False)
    ins.read(R/'sources/dclaw_mass_source_audit.json','fixed-source DClaw mass audit provenance',False)
    ins.js(R/'config/q2_compact_quality_review_04.json','registered compact-source numerical qualification review',False)
    ins.js(R/'sources/q2_compact_budget_review_v1.json','independently crosschecked Q2 compact ASCII/native budget evidence',False)
    changed=ins.changed();provisional=not args.freeze
    for row in arrivals:
        row['source_snapshot_stable']=not changed
        if changed:row['include_in_arrival_envelope']=False
    mass_audit=attach_quality_contract(ins,runs,metrics,arrivals)
    q2_quality=apply_q2_compact_quality(ins,runs,metrics,arrivals)
    statuses=collections.Counter(x['execution_status'] for x in runs)
    summary={'integration_version':'q4-r3-comparison-v1','generated_at_utc':utc(),'status':'provisional' if provisional else 'final_freeze_requested',
      'input_version':dict(INPUT_VERSION),'common_context':common_context(runs,arrivals),
      'source_input_index':'results/comparison_input_index.json','source_inputs_changed_during_read':changed,
      'run_inventory_count':len(runs),'reduced_regional_count':len(reduced),'official_case_inventory_count':sum(x.get('record_kind')!='archived_execution_attempt' for x in official),'archived_distinct_attempt_records':len(archived),'numerical_configuration_records':len(br),
      'actual_execution_attempted_count':sum(bool(x.get('execution_attempted')) for x in runs),
      'actual_regional_execution_attempted_count':sum(bool(x.get('execution_attempted')) for x in runs if x.get('evaluation_stratum')=='conditional_scenario'),
      'official_current_registered_count':sum(x['plan_scope']=='current_registered' for x in official),
      'official_current_conditional_registered_count':sum(x['plan_scope']=='current_registered' and x['evaluation_stratum']=='conditional_scenario' for x in official),
      'official_current_conditional_status_counts':dict(collections.Counter(x['execution_status'] for x in official if x['plan_scope']=='current_registered' and x['evaluation_stratum']=='conditional_scenario')),
      'registered_applicability_completion':{'registered_count':sum(x['plan_scope']=='current_registered' for x in official),
          'registered_conditional_count':sum(x['plan_scope']=='current_registered' and x['evaluation_stratum']=='conditional_scenario' for x in official),
          'applicable_required_count':sum(x.get('applicable_required',False) for x in official),
          'applicable_required_run_ids':[x['run_id'] for x in official if x.get('applicable_required')],
          'applicable_required_completed_count':sum(x.get('applicable_required',False) and x['execution_status']=='completed' for x in official),
          'quarantined_not_run_count':sum(x['execution_status']=='not_run_material_applicability_exclusion' for x in official),
          'quarantined_not_run_run_ids':[x['run_id'] for x in official if x['execution_status']=='not_run_material_applicability_exclusion'],
          'generic_diagnostic_only_statuses':{x['run_id']:x['execution_status'] for x in official if x.get('applicability_class')=='generic_material_proxy_diagnostic_only'},
          'applicability_review_status':'registered decision03; mathematical implementation invalidity not claimed for excluded material proxies',
          'completed_registered_count':sum(x['plan_scope']=='current_registered' and x['execution_status']=='completed' for x in official)},
      'existing_case_reproduction':{'replayed_existing_case_count':len((replay_evidence or {}).get('replayed_cases',[])),
          'adds_new_model_case_count':0,'adds_independent_event_validation_count':0,
          'evidence_path':'results/replay_execution_comparison.json' if replay_evidence else None},
      'actual_native_input_control_provenance':native_controls,
      'official_plan_scope_counts':dict(collections.Counter(x['plan_scope'] for x in official)),
      'execution_status_counts':dict(statuses),'arrival_status_counts':dict(collections.Counter(x['arrival_status'] for x in arrivals)),
      'execution_status_by_stratum':{scope:dict(collections.Counter(x['execution_status'] for x in runs if x.get('evaluation_stratum')==scope)) for scope in sorted(set(x['evaluation_stratum'] for x in runs))},
      'official_execution_status_counts':dict(collections.Counter(x['execution_status'] for x in official)),
      'conditional_valid_hit_count':sum(x['arrival_status']=='arrived' and x.get('travel_time_seconds') is not None for x in arrivals),
      'boundary_affected_valid_hit_count':sum(x['arrival_status']=='arrived' and x.get('domain_affected_before_arrival') is True for x in arrivals),
      'current_pending_runs':[x['run_id'] for x in official if x.get('completion_required') and x['execution_status'] in ['planned_without_execution','running_unfinalized','running_retry_with_stale_prior_attempt_metadata','finished_unanalysed','field_missing_or_index_stale','missing_execution_result','historical_attempt_unanalysed']],
      'actual_attempts_unsettled':[x['run_id'] for x in official if x['execution_attempted'] and x['execution_status'] in ['running_unfinalized','running_retry_with_stale_prior_attempt_metadata','finished_unanalysed','field_missing_or_index_stale','missing_execution_result','historical_attempt_unanalysed']],
      'within_framework_pairs':within_framework_pairs(runs,metrics),'cross_framework_incremental_physics_gain_claimed':False,
      'statistical_weights':None,'independent_local_training_events':0,'independent_local_validation_events':0,
      'confidence_interval_or_95pct_coverage_claim':False,'human_scientific_adoption':'pending_team_review',
      'arrival_envelope_gate_scope':'execution, bound fields, actual time and boundary threshold only; no numerical/physical accuracy qualification',
      'limitations':['inventory is not number of completed formal experiments; plan_scope and actual attempts separated',
        'reduced 1D/2D unqualified for thin-flow arrival timing; 1D area is equivalent-width only',
        'ravaflow scalar terrain-corrected speed differs from horizontal magnitude; sampling/cutoffs retained',
        'DClaw nodal-to-cell effective terrain/release differ; signed sampled boundary flux is not native conservation verification',
        'DClaw extended reference has about 4.15% domain mass loss without recorded boundary depth >=.1m; do not attribute all mass discrepancy to outflow',
        'Raw-state audit finds extended DClaw mass -2.1612% at180s and permeable +11.6012% at20s while saved boundary h/hu/hv are zero; cause remains unresolved without native per-step ledger',
        'arrival envelope inclusion passes only execution/field/time/boundary gates; regional numerical accuracy and predictive adoption remain unqualified',
        'failed-pipeline and early-terminated hits retained as observed_hit only, valid travel time null',
        'all travel times relative to scenario bulk release; initiation-to-release delay unknown']}
    freeze_blocked=bool(changed or summary['current_pending_runs'] or summary['actual_attempts_unsettled'] or native_controls['status']!='indexed_actual_generated_controls')
    summary['freeze_block_reasons']=[label for label,condition in [
        ('source_files_changed_during_read',bool(changed)),('required_or_active_diagnostic_runs_unfinished',bool(summary['current_pending_runs'])),
        ('actual_attempts_unsettled',bool(summary['actual_attempts_unsettled'])),('native_input_control_index_missing_or_mismatched',native_controls['status']!='indexed_actual_generated_controls')] if condition]
    if args.freeze and not freeze_blocked:
        if not re.fullmatch(r'propagation_v[0-9]+',args.version):raise ValueError('version must be propagation_vN')
        if (R/'exports'/args.version).exists():raise FileExistsError('Frozen version already exists; choose new version')
        summary['status']='frozen_for_joint_review'
    elif args.freeze:summary['status']='provisional'
    numerical={'generated_at_utc':utc(),'status':summary['status'],'reduced':rv,'official':ov,
      'dclaw_raw_state_mass_audit':mass_audit,
      'existing_case_reproduction_evidence':replay_evidence,
      'actual_native_input_control_provenance':native_controls,
      'qualification_by_run':[{k:x.get(k) for k in ['run_id','execution_status','numerical_qualification','state_horizon_complete','finite_state','nonnegative_state','fields_hash_matches_index','event_timing_validated']} for x in runs],
      'independent_local_event_validation_count':0,'declared_property_pass_is_not_regional_accuracy':True,
      'source_inputs_changed_during_read':changed}
    for row in runs:row['integration_status']=summary['status']
    for row in metrics:row['integration_status']=summary['status']
    for row in arrivals:row['integration_status']=summary['status']
    dump_csv(R/'results/model_runs.csv',runs);dump_csv(R/'results/comparison_metrics.csv',metrics);dump_csv(R/'results/target_arrivals.csv',arrivals)
    write_json(R/'results/numerical_validation.json',numerical);write_json(R/'results/comparison_summary.json',summary)
    index={'generated_at_utc':utc(),'integration_status':summary['status'],'files':list(ins.records.values()),'no_self_reference':True,'mutability_note':'read-time snapshot; rerun integration after official observer tables have settled'}
    write_json(R/'results/comparison_input_index.json',index)
    log={'utc':utc(),'command_mode':'freeze' if args.freeze else 'provisional','source_index_sha256':digest((R/'results/comparison_input_index.json').read_bytes()),'source_count':len(ins.records),'source_files_changed':changed,'outputs_written':['model_runs.csv','comparison_metrics.csv','target_arrivals.csv','numerical_validation.json','comparison_summary.json'],'final_bundle_written':False}
    if args.freeze:
        if freeze_blocked:
            log['freeze_refused']=summary['freeze_block_reasons'];write_json(R/'results/comparison_integration_log.json',log)
            raise RuntimeError('Cannot freeze: '+', '.join(summary['freeze_block_reasons'])+'; tables remain provisional')
        dest=R/'exports'/args.version
        dest.mkdir(parents=True);files=[]
        for name in ['model_runs.csv','comparison_metrics.csv','target_arrivals.csv','numerical_validation.json','comparison_summary.json','comparison_input_index.json']:
            source=R/'results'/name;target=dest/'files/results'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            b=target.read_bytes();files.append({'path':str(target.relative_to(ROOT)),'bytes':len(b),'sha256':digest(b),'role':name.removesuffix('.csv').removesuffix('.json')})
        for key,rec in ins.records.items():
            if key in ins.bytes:
                original=Path(rec['path'])
                relative=original if not original.is_absolute() else Path('external')/str(original).lstrip('/')
                target=dest/'source_snapshots'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(ins.bytes[key])
                files.append({'path':str(target.relative_to(ROOT)),'bytes':target.stat().st_size,'sha256':file_digest(target),
                    'role':rec['role'],'storage':'copied_read_time_source_snapshot','source_path':rec['path']})
            else:
                files.append({**rec,'storage':'immutable_external_byte_hash_bound_dependency'})
        bundle={'bundle_version':'q4-r3-'+args.version.replace('_','-'),'producer_question':'q4','input_version':INPUT_VERSION,
          'common_context':summary['common_context'],
          'evaluation_stratum':'conditional_scenario; numerical_benchmark rows explicitly separated','files':files,
          'status':'frozen_for_joint_review','probability_weights':None,'independent_local_validation_events':0,
          'time_origin':'bulk release','initiation_to_release_delay_seconds':None,'limitations':summary['limitations'],
          'human_scientific_adoption':'pending_team_review','file_list_excludes_self':True}
        write_json(dest/'bundle.json',bundle);write_json(R/'exports/propagation_bundle.json',bundle);log['final_bundle_written']=True;log['bundle_version']=bundle['bundle_version']
    if args.early_freeze:
        log['early_partial_bundle']=early_export(ins,runs,metrics,arrivals,numerical,summary,args.version,args.early_selection)
        log['early_partial_bundle_written']=True
    write_json(R/'results/comparison_integration_log.json',log)
    print(canonical({'status':summary['status'],'inventory':len(runs),'official_current_pending':len(summary['current_pending_runs']),'actual_regional_attempts':summary['actual_regional_execution_attempted_count'],'arrivals':dict(summary['arrival_status_counts']),'final_bundle_written':log['final_bundle_written'],'source_input_index_sha256':log['source_index_sha256'],'early_partial_bundle':log.get('early_partial_bundle')}))

if __name__=='__main__':main()
