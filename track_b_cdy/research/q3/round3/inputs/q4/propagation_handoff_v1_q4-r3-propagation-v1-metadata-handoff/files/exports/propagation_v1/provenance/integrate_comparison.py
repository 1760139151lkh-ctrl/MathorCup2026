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
ACTIVE=['official_cases_copdem_v2.json','official_cases_q2mapped_v2.json',
        'official_cases_q2fullmask_v2.json','official_cases_extended.json',
        'official_cases_physics_v2.json','official_cases_output_flag.json',
        'official_cases_resourcefix.json']

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
            self.records[key]={'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),'bytes':p.stat().st_size,'sha256':file_digest(p),'role':rec.get('role','indexed process field'),'read_at_utc':utc(),'actual_read_scope':'complete byte stream hashed in 1MiB blocks; no binary arrays loaded by integrator'}
        actual=self.records[key]
        return actual['bytes']==rec['bytes'] and actual['sha256']==rec['sha256']
    def changed(self):
        changed=[]
        for key,rec in self.records.items():
            p=Path(key)
            if not p.exists() or file_digest(p)!=rec['sha256']:changed.append(str(p))
        return changed

def stratum(role):
    return 'numerical_benchmark' if 'benchmark' in str(role) else 'conditional_scenario'

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
    upstream={}
    for path in sorted((R/'inputs/q2').glob('**/release_states*.csv')):
        for state in ins.csv(path,'delivered Q2 upstream state and mechanism keys'):
            upstream[state['scenario_id']]=state
    for name in active_configs:
        path=Path(name);path=path if path.is_absolute() else R/'config'/path
        packet=ins.js(path,'current registered official plan',False)
        if packet:
            for item in packet.get('cases',[]):
                active.add(item['run_id']);planned[item['run_id']]=item
                active_sources.setdefault(item['run_id'],[]).append(str(path))
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
        returncode=ex.get('returncode');actual_end=number(check.get('actual_last_time_seconds',m.get('last_time_s')))
        requested=number(case.get('end_seconds'));complete=actual_end is not None and requested is not None and actual_end>=requested-.01
        field=fields.get(rid);field_ok=ins.check_bound(field) if field else False
        case_path=C/'runs'/rid/'case.json'
        case_sha=digest(ins.bytes[str(case_path.resolve())]) if str(case_path.resolve()) in ins.bytes else None
        execution_case_matches=bool(not ex or ex.get('case_sha256')==case_sha)
        log_path=Path(ex.get('log_path',C/'runs'/rid/'run.log'))
        log_matches=ins.check_bound({'path':str(log_path),'bytes':log_path.stat().st_size,'sha256':ex['log_sha256'],'role':'native execution log bound to actual attempt'}) if ex.get('log_sha256') and log_path.exists() else None
        parsed_current=bool(check) and (not check.get('case_sha256') or check['case_sha256']==case_sha)
        if 'exit_code' in check:parsed_current=parsed_current and check['exit_code']==returncode
        parsed_current=parsed_current and execution_case_matches and log_matches is not False
        field_case_matches=not field or field.get('case_sha256')==case_sha
        finite=truth(check.get('finite'));nonnegative=truth(check.get('nonnegative_to_1e-8'))
        if 'cancel' in str(ex.get('status','')).lower() or ex.get('cancelled'):status='cancelled'
        elif quarantine:status='quarantined_configuration'
        elif not ex and attempted:status='running_unfinalized'
        elif not ex:status='planned_without_execution'
        elif returncode is None:status=str(ex.get('status') or 'missing_execution_result')
        elif not parsed_current:status='finished_unanalysed'
        elif returncode!=0:status='pipeline_failure'
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
          'current_plan_sources':active_sources.get(rid,[]),'execution_attempted':attempted,
          'native_solver_started':False if ex.get('solver_started') is False else None,
          'execution_status':status,'raw_execution_status':raw.get('status',ex.get('status')),
          'quality_gate':gate,'requested_horizon_seconds':requested,'actual_end_time_seconds':actual_end,
          'wall_seconds':ex.get('elapsed_seconds'),'initial_velocity_east_north_m_s':case.get('initial_velocity_east_north_m_s'),
          'initiation_to_release_delay_seconds':None,'if_released_propagation':if_released,
          'time_origin':'bulk_release','state_horizon_complete':complete,'pipeline_returncode':returncode,
          'native_success_field':check.get('solver_success_field'),'finite_state':finite,'nonnegative_state':nonnegative,
          'fields_hash_matches_index':field_ok,'field_case_hash_matches':field_case_matches,'parsed_case_hash_matches':parsed_current,'field_reference':field,
          'numerical_qualification':qual,'include_in_scientific_parameter_comparison':status=='completed' and not quarantine,
          'include_in_arrival_envelope':status=='completed' and not quarantine and stratum(case.get('evidence_role'))!='numerical_benchmark',
          'event_timing_validated':False,'independent_event_validation_count':0,
          'csurface':csurface,'image_id':ex.get('image_id'),'container_id':ex.get('container_id'),
          'base_image_id':ex.get('base_image_id'),'runtime_image_identity_complete':bool(ex.get('image_id')),
          'solver_build':case.get('solver_build','official_original_frozen_source'),
          'resourcefix_parent_run_id':case.get('resourcefix_parent_run_id'),
          'execution_case_hash_matches':execution_case_matches,'execution_log_hash_matches':log_matches,
          'boundary_definition':'three-cell edge-store/absorbing native domain' if case['model'].startswith('ravaflow') else 'zero-gradient/extrapolation native ghost cells; signed net flow',
          'parameters':{k:case.get(k) for k in ['resolution_m','release_thickness_m','mu_basal','xi','extras','phase_volume_fractions','bulk_density_kg_m3','passive_material_volume_fractions']},
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
                rr,cc=np.indices((ny,nx));xx=tr[0]*(cc+.5)+tr[1]*(rr+.5)+tr[2];yy=tr[3]*(cc+.5)+tr[4]*(rr+.5)+tr[5]
                found={}
                for target in target_list:
                    mask=(xx-target['xy'][0])**2+(yy-target['xy'][1])**2<=target.get('buffer_m',100)**2
                    hit=np.flatnonzero((h[:,mask]>=.1).any(axis=1)) if mask.any() else []
                    k=int(hit[0]) if len(hit) else None
                    found[target['id']]={'outside':not bool(mask.any()),'time':float(t[k]) if k is not None else None,
                        'lower':float(t[k-1]) if k is not None and k>0 else None,'actual_end':float(t[-1])}
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
        binding_method='observer_explicit_fields_sha256' if target_field_matches is not None else 'missing_observer_field_hash'
        expected=None
        if base['execution_status']=='completed' and base['field_reference']:
            independently_matches,binding_method,expected=independent_saved_check(base,row)
            target_field_matches=independently_matches and target_field_matches is not False
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
    def group_key(x):return (x['model_id'],x.get('solver_build','independent_frozen_r3'))
    for (model,build),items in itertools.groupby(sorted(eligible,key=group_key),key=group_key):
        group=list(items)
        refs=[x for x in group if re.search(r'(?:_ref(?:_|$)|_P[123]_ref$)',x['run_id'])]
        for ref in refs:
            for other in group:
                if other['run_id']==ref['run_id']:continue
                # Same release/base key or explicit domain-parent comparison; never a cross-framework gain.
                parent=other.get('raw_case_json',{}).get('domain_comparison_parent_run_id')
                same_release_key=other.get('base_scenario_id')==ref.get('base_scenario_id')
                common_ofat=ref.get('release_mapping_version')=='common_reference' and other.get('release_mapping_version')=='common_reference'
                if not same_release_key and parent!=ref['run_id'] and not common_ofat:continue
                if ref.get('path_id')!=other.get('path_id'):continue
                a=mm.get(ref['run_id'],{});b=mm.get(other['run_id'],{})
                pair={'model_id':model,'solver_build':build,'reference_run_id':ref['run_id'],'other_run_id':other['run_id'],
                  'comparison_scope':'within-framework conditional sensitivity; not calibrated model gain',
                  'reference_parameters':ref.get('parameters'),'other_parameters':other.get('parameters'),
                  'same_geometry_version':ref.get('geometry_version')==other.get('geometry_version'),
                  'same_base_scenario_key':same_release_key,
                  'same_initial_volume_within1e_minus6':abs(a.get('initial_volume_m3',0)-b.get('initial_volume_m3',0))/max(abs(a.get('initial_volume_m3') or 0),1)<1e-6 if a.get('initial_volume_m3') is not None and b.get('initial_volume_m3') is not None else None,
                  'changed_parameter_fields':[k for k in set(ref.get('parameters',{}))|set(other.get('parameters',{})) if ref.get('parameters',{}).get(k)!=other.get('parameters',{}).get(k)],
                  'ref_numerical_qualification':ref.get('numerical_qualification'),'other_numerical_qualification':other.get('numerical_qualification')}
                for key in ['max_depth_m','impact_area_m2']:
                    av,bv=number(a.get(key)),number(b.get(key));pair[key+'_difference']=bv-av if av is not None and bv is not None else None
                pairs.append(pair)
    return pairs

def early_export(ins,runs,metrics,arrivals,numerical,summary,version):
    """Freeze only completed DClaw observations; rolling root tables stay provisional."""
    if not re.fullmatch(r'propagation_v[0-9]+',version):raise ValueError('version must be propagation_vN')
    dest=R/'exports'/version
    if dest.exists():raise FileExistsError('Never overwrite an early or final frozen version')
    selected=[dict(x,integration_status='frozen_partial_for_q3_review') for x in runs
        if x.get('producer')=='official' and x.get('model_id')=='dclaw'
        and x.get('evaluation_stratum')=='conditional_scenario' and x.get('execution_status')=='completed']
    if not selected:raise RuntimeError('No completed, parsed, hash-bound DClaw scenarios available')
    ids={x['run_id'] for x in selected}
    selected_metrics=[dict(x,integration_status='frozen_partial_for_q3_review') for x in metrics if x['run_id'] in ids]
    selected_arrivals=[dict(x,integration_status='frozen_partial_for_q3_review') for x in arrivals if x['run_id'] in ids]
    if not all(x.get('target_field_hash_matches') is True for x in selected_arrivals):
        raise RuntimeError('Early package requires every selected target to match immutable saved fields')
    # Only selected case/attempt/log/fields and physical input dependencies gate this partial export.
    external=[];metadata=[]
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
    fields=list({x['path']:x for x in external}.values())
    selected_by={x['run_id']:x for x in selected}
    for row in selected_arrivals:
        row['source_snapshot_stable']=True
        row['source_snapshot_stability_scope']='selected run case/execution/log/native input/field hashes; unrelated rolling observer tables may advance'
        row['include_in_arrival_envelope']=bool(selected_by[row['run_id']]['include_in_arrival_envelope'] and not row.get('domain_affected_before_arrival') and row['arrival_status'] in ['arrived','not_arrived_by_horizon'])
    partial_summary={'status':'frozen_partial_for_q3_review','generated_at_utc':utc(),
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
        'limitations':summary['limitations']+[
            'Early partial DClaw packet only; all-route and Q2 mapping comparisons remain pending',
            'Boundary-affected arrivals are conditional diagnostics, excluded from the arrival envelope',
            'Saved-output target detection was independently re-evaluated against hashed native NPZ times/depth; not solver-step arrival precision',
            'Five OSM representatives refer to three distinct candidate entities, not five independent validation targets',
            'copdem_120_dclaw_ref historical build-container image ID is unavailable; base image/container and exact execution/log/fields retained']}
    selected_numerical={'status':partial_summary['status'],'generated_at_utc':utc(),
        'qualification_by_run':[{k:x.get(k) for k in ['run_id','execution_status','numerical_qualification','state_horizon_complete','finite_state','nonnegative_state','fields_hash_matches_index','execution_case_hash_matches','execution_log_hash_matches','runtime_image_identity_complete']} for x in selected],
        'official':{'checks':[x for x in numerical['official']['checks'] if x['run_id'] in ids or x['run_id']=='flatrest_60_dclaw']},
        'independent_local_event_validation_count':0,'native_conservation_verified':False,
        'declared_property_pass_is_not_regional_accuracy':True}
    dest.mkdir(parents=True);manifest=[]
    def record(path,role):
        manifest.append({'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':file_digest(path),'role':role,'storage':'copied_versioned_metadata'})
    for name,rows in [('model_runs.csv',selected),('comparison_metrics.csv',selected_metrics),('target_arrivals.csv',selected_arrivals)]:
        p=dest/name;dump_csv(p,rows);record(p,name.removesuffix('.csv'))
    for name,obj in [('comparison_summary.json',partial_summary),('numerical_validation.json',selected_numerical),('fields_index.json',{'fields':[x for x in fields if x.get('role')=='actual_official_process_fields']})]:
        p=dest/name;write_json(p,obj);record(p,name.removesuffix('.json'))
    for relative,b,role in metadata:
        p=dest/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);record(p,role)
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
        'input_version':'904d7257b899b9f71d1ac9e0eab7479e459eab52','status':partial_summary['status'],
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
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group();mode.add_argument('--freeze',action='store_true');mode.add_argument('--early-freeze',action='store_true');parser.add_argument('--version',default='propagation_v1');parser.add_argument('--active-config',action='append');args=parser.parse_args()
    ins=Inputs();ins.read(Path(__file__),'integration source code');policy=ins.js(R/'config/comparison_policy.json','preregistered comparison policy')
    reduced,rm,ra=build_reduced(ins);official,om,oa,ov,active=collect_official(ins,args.active_config or ACTIVE);br,rv=benchmarks(ins)
    runs=reduced+official+br;metrics=rm+om;arrivals=ra+oa
    run_by_id={x['run_id']:x for x in runs}
    target_entities={x['target_id']:x.get('entity_id') for x in ins.csv(R/'results/spatial_targets_v2.csv','all currently registered OSM target representatives',False)}
    for row in arrivals:
        row['inundation_or_runout_reference']=run_by_id[row['run_id']].get('field_reference')
        if not row.get('entity_id'):row['entity_id']=target_entities.get(row.get('target_id'))
    changed=ins.changed();provisional=not args.freeze
    for row in arrivals:
        row['source_snapshot_stable']=not changed
        if changed:row['include_in_arrival_envelope']=False
    statuses=collections.Counter(x['execution_status'] for x in runs)
    summary={'integration_version':'q4-r3-comparison-v1','generated_at_utc':utc(),'status':'provisional' if provisional else 'final_freeze_requested',
      'source_input_index':'results/comparison_input_index.json','source_inputs_changed_during_read':changed,
      'run_inventory_count':len(runs),'reduced_regional_count':len(reduced),'official_case_inventory_count':len(official),'numerical_configuration_records':len(br),
      'actual_execution_attempted_count':sum(bool(x.get('execution_attempted')) for x in runs),
      'actual_regional_execution_attempted_count':sum(bool(x.get('execution_attempted')) for x in runs if x.get('evaluation_stratum')=='conditional_scenario'),
      'official_current_registered_count':sum(x['plan_scope']=='current_registered' for x in official),
      'official_plan_scope_counts':dict(collections.Counter(x['plan_scope'] for x in official)),
      'execution_status_counts':dict(statuses),'arrival_status_counts':dict(collections.Counter(x['arrival_status'] for x in arrivals)),
      'execution_status_by_stratum':{scope:dict(collections.Counter(x['execution_status'] for x in runs if x.get('evaluation_stratum')==scope)) for scope in sorted(set(x['evaluation_stratum'] for x in runs))},
      'official_execution_status_counts':dict(collections.Counter(x['execution_status'] for x in official)),
      'conditional_valid_hit_count':sum(x['arrival_status']=='arrived' and x.get('travel_time_seconds') is not None for x in arrivals),
      'boundary_affected_valid_hit_count':sum(x['arrival_status']=='arrived' and x.get('domain_affected_before_arrival') is True for x in arrivals),
      'current_pending_runs':[x['run_id'] for x in official if x['plan_scope']=='current_registered' and x['execution_status'] in ['planned_without_execution','running_unfinalized','finished_unanalysed','field_missing_or_index_stale','missing_execution_result']],
      'actual_attempts_unsettled':[x['run_id'] for x in official if x['execution_attempted'] and x['execution_status'] in ['running_unfinalized','finished_unanalysed','field_missing_or_index_stale','missing_execution_result']],
      'within_framework_pairs':within_framework_pairs(runs,metrics),'cross_framework_incremental_physics_gain_claimed':False,
      'statistical_weights':None,'independent_local_training_events':0,'independent_local_validation_events':0,
      'confidence_interval_or_95pct_coverage_claim':False,'human_scientific_adoption':'pending_team_review',
      'limitations':['inventory is not number of completed formal experiments; plan_scope and actual attempts separated',
        'reduced 1D/2D unqualified for thin-flow arrival timing; 1D area is equivalent-width only',
        'ravaflow scalar terrain-corrected speed differs from horizontal magnitude; sampling/cutoffs retained',
        'DClaw nodal-to-cell effective terrain/release differ; signed sampled boundary flux is not native conservation verification',
        'failed-pipeline and early-terminated hits retained as observed_hit only, valid travel time null',
        'all travel times relative to scenario bulk release; initiation-to-release delay unknown']}
    freeze_blocked=bool(changed or summary['current_pending_runs'] or summary['actual_attempts_unsettled'])
    if args.freeze and not freeze_blocked:
        if not re.fullmatch(r'propagation_v[0-9]+',args.version):raise ValueError('version must be propagation_vN')
        if (R/'exports'/args.version).exists():raise FileExistsError('Frozen version already exists; choose new version')
        summary['status']='frozen_for_joint_review'
    elif args.freeze:summary['status']='provisional'
    numerical={'generated_at_utc':utc(),'status':summary['status'],'reduced':rv,'official':ov,
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
            log['freeze_refused']='changing inputs or unfinished/unanalysed registered plans/actual attempts';write_json(R/'results/comparison_integration_log.json',log)
            raise RuntimeError('Cannot freeze: changing inputs or current registered unfinished/unanalysed runs; tables remain provisional')
        dest=R/'exports'/args.version
        dest.mkdir(parents=True);files=[]
        for name in ['model_runs.csv','comparison_metrics.csv','target_arrivals.csv','numerical_validation.json','comparison_summary.json','comparison_input_index.json']:
            source=R/'results'/name;target=dest/'files/results'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            b=target.read_bytes();files.append({'path':str(target.relative_to(ROOT)),'bytes':len(b),'sha256':digest(b),'role':name.removesuffix('.csv').removesuffix('.json')})
        bundle={'bundle_version':'q4-r3-'+args.version.replace('_','-'),'producer_question':'q4','input_version':'904d7257b899b9f71d1ac9e0eab7479e459eab52',
          'evaluation_stratum':'conditional_scenario; numerical_benchmark rows explicitly separated','files':files,
          'status':'frozen_for_joint_review','probability_weights':None,'independent_local_validation_events':0,
          'time_origin':'bulk release','initiation_to_release_delay_seconds':None,'limitations':summary['limitations'],
          'human_scientific_adoption':'pending_team_review','file_list_excludes_self':True}
        write_json(dest/'bundle.json',bundle);write_json(R/'exports/propagation_bundle.json',bundle);log['final_bundle_written']=True;log['bundle_version']=bundle['bundle_version']
    if args.early_freeze:
        log['early_partial_bundle']=early_export(ins,runs,metrics,arrivals,numerical,summary,args.version)
        log['early_partial_bundle_written']=True
    write_json(R/'results/comparison_integration_log.json',log)
    print(canonical({'status':summary['status'],'inventory':len(runs),'official_current_pending':len(summary['current_pending_runs']),'actual_regional_attempts':summary['actual_regional_execution_attempted_count'],'arrivals':dict(summary['arrival_status_counts']),'final_bundle_written':log['final_bundle_written'],'source_input_index_sha256':log['source_index_sha256'],'early_partial_bundle':log.get('early_partial_bundle')}))

if __name__=='__main__':main()
