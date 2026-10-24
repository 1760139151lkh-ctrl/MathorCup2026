"""Offline deterministic full Q2R3 conditional competition and early exports."""
from __future__ import annotations
import hashlib, json, platform, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from mechanism_engine import MODEL_IDS, MARGIN_DEFINITION, G, simulate, thermal_transfer, stresses, resistance, classify_trajectory

ROOT=Path(__file__).resolve().parents[5]
BASE=ROOT/'track_b/research/q2/round3'
CONFIG=BASE/'config/experiment_v1.json'
INPUT_VERSION={'baseline_commit':'904d7257b899b9f71d1ac9e0eab7479e459eab52','baseline_manifest_sha256':'fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'}

RANGES={
 'theta_deg':(30,60,'linear','conditional structural plane; not NC surface slope'),
 'thickness_normal_m':(10,60,'linear','conditional; NC inventory 6..154 m is background only'),
 'rock_volume_fraction':(.2,.8,'linear','conditional two-solid mixture; not measured'),
 'bridge_fraction':(.0,.25,'linear','conditional load-bearing area fraction'),
 'bridge_cohesion_kpa':(300,3000,'log','conditional rock-bridge effective cohesion, not measured'),
 'rock_mu':(.45,.85,'linear','conditional friction coefficient'),
 'initial_temp_c':(-6,-.8,'linear','conditional initial joint temperature; within lab thermal domain'),
 'diffusivity_m2_s':(.9e-6,2.1e-6,'linear','external_transfer Weber2025 median +/- MAD endpoints; design interval not statistical CI'),
 'interface_depth_m':(.5,20,'log','conditional depth of thermal path, distinct from slab thickness'),
 'station_source_offset_c':(-18,-6,'linear','conditional combined elevation/exposure/surface transfer offset'),
 'storativity':(.002,.08,'log','conditional water-equivalent storage/head ratio'),
 'drainage_hours':(3,240,'log','conditional reservoir time constant; not fixed by external flow lag'),
 'connected_depth_m':(2,40,'log','conditional maximum connected water head'),
 'rain_multiplier':(.25,3,'log','conditional station-to-source and effective infiltration multiplier'),
 'melt_mm_deg_day':(.5,6,'linear','conditional degree-day coefficient; not an energy balance'),
 'damage_rate_h_inv':(1e-7,2e-4,'log','phenomenological design range; not calibrated ice rheology'),
 'damage_exponent':(2,6,'linear','phenomenological stress-ratio power'),
 'initial_damage':(.05,.7,'linear','conditional cohesion loss fraction'),
 'drainage_damage_coupling':(0,3,'linear','conditional damage-enhanced drainage exp(-k*D)')}


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def digest(path,role):
    raw=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':role}


def initialize():
    BASE.mkdir(parents=True,exist_ok=True)
    for d in ['results','figures','exports','config']: (BASE/d).mkdir(exist_ok=True)
    if not CONFIG.exists():
        write_json(CONFIG,dict(experiment_id='q2r3-competing-mechanisms-v1',parameter_version='q2r3-design-v1',
          seed=260826,n_parameter_sets=256,models=list(MODEL_IDS),policies=['linear_extension','thawed_rock_contact'],
          start_utc='2026-06-01T00:00:00Z',end_utc='2026-08-27T00:00:00Z',evaluation_start_utc='2026-08-19T00:00:00Z',
          dt_hours=1.,dz_m=.5,thermal_bottom_m=40.,ranges={k:dict(min=v[0],max=v[1],scale=v[2],source=v[3]) for k,v in RANGES.items()},
          initial_water_storage_m=0,design_is_probability_prior=False,weights=None,independent_events=0,
          information_available_time=None,forecast_input_mode='ideal_weather',evaluation_stratum='conditional_scenario',
          crossing_rule='first sampled nonpositive margin after stable finite initial value; linear interpolation within bracket; initial nonpositive left censored',
          source_mapping='Tsource=Tstation+offset; surface=min(Tsource,0); rain as assumed mm/h times multiplier times linear -1..+1 C liquid partition; melt positive source-air degree day'))
    return json.loads(CONFIG.read_text())


def load_forcing(cfg):
    temporal=ROOT/'track_b/data/processed/temporal'
    axis=pd.read_parquet(temporal/'hourly_time_axis.parquet')
    strict=pd.read_parquet(temporal/'hourly_strict_qc0.parquet',columns=['MET__Ta_2m'])
    raw=pd.read_parquet(temporal/'hourly_raw_numeric.parquet',columns=['MET__Precip'])
    choose=(axis.time_utc>=cfg['start_utc'])&(axis.time_utc<=cfg['end_utc'])
    out=pd.DataFrame({'time_utc':axis.loc[choose,'time_utc'].reset_index(drop=True),
       'station_air_temp_c':strict.loc[choose,'MET__Ta_2m'].reset_index(drop=True),
       'precip_assumed_mm_h':raw.loc[choose,'MET__Precip'].reset_index(drop=True).replace(9999.9,np.nan)})
    assert out[['station_air_temp_c','precip_assumed_mm_h']].notna().all().all()
    assert (out.time_utc.diff().dropna()==pd.Timedelta(hours=1)).all()
    assert (out.precip_assumed_mm_h>=0).all()
    out['elapsed_hours']=np.arange(len(out));out['data_role']='scenario';out['forecast_input_mode']='ideal_weather'
    out['temperature_quality']='original_strict_QC0';out['precip_quality']='unknown_QC_and_accumulation; assumed_1h_interval'
    out['available_time']=None
    out.to_csv(BASE/'results/forcing_hourly_v1.csv',index=False)
    write_json(BASE/'results/forcing_support.json',{'rows':len(out),'first_utc':str(out.time_utc.iloc[0]),'last_utc':str(out.time_utc.iloc[-1]),
      'temperature_missing':0,'precip_missing':0,'precip_label_sum_mm_under_hourly_assumption':float(out.precip_assumed_mm_h.sum()),
      'no_interpolation':True,'operational_availability':None,'station_timezone_assumption':'UTC+8 as inherited, local equivalence still unknown',
      'source_space':'Gyirong regional station; source temperature/rain are conditional transfers',
      'used_as':'conditional_scenario ideal_weather retrospective forcing, not validated source observation',
      'excluded_long_gap':'2026-08-27T01:00Z onward not filled or treated as zero'})
    return out


def parameter_design(cfg):
    rng=np.random.default_rng(cfg['seed']);n=cfg['n_parameter_sets']
    u=np.column_stack([(rng.permutation(n)+rng.random(n))/n for _ in RANGES])
    p={}
    for j,(name,(lo,hi,scale,_)) in enumerate(RANGES.items()):
        p[name]=np.exp(np.log(lo)+(np.log(hi)-np.log(lo))*u[:,j]) if scale=='log' else lo+(hi-lo)*u[:,j]
    p['density_kg_m3']=917*(1-p['rock_volume_fraction'])+2700*p['rock_volume_fraction']
    return p


def take(parameters,index): return {k:np.asarray(v)[index] for k,v in parameters.items()}


def scenario_id(i,mechanism,policy): return f'q2r3-p{i:04d}-{mechanism}-'+('linear' if policy=='linear_extension' else 'thaw')


def run():
    t0=time.perf_counter();cfg=initialize();forcing=load_forcing(cfg);p=parameter_design(cfg)
    n=cfg['n_parameter_sets'];nt=len(forcing);air=forcing.station_air_temp_c.to_numpy();rain=forcing.precip_assumed_mm_h.to_numpy()
    thermal=thermal_transfer(air,p,1.,cfg['dz_m'])
    print('Thermal state complete',flush=True)
    # Representatives fixed by design index before seeing any result.
    reps=np.linspace(0,n-1,8,dtype=int);ev=int(np.flatnonzero(forcing.time_utc>=cfg['evaluation_start_utc'])[0])
    rows=[];tracks=[];params=[];ablation=[];crit=[];releases=[];summary_arrays={};watermax=0
    for policy in cfg['policies']:
      for mech in cfg['models']:
        result=simulate(air,rain,p,mech,policy,thermal=thermal)
        print(f'Completed {policy} {mech}',flush=True)
        summary_arrays[(mech,policy)]=np.min(result['failure_margin'][ev:],axis=0)
        watermax=max(watermax,float(result['water_budget_max_abs_m'].max()))
        for i in range(n):
          sid=scenario_id(i,mech,policy)
          onset=classify_trajectory(result['failure_margin'][:,i]);late=classify_trajectory(result['failure_margin'][ev:,i])
          record=dict(scenario_id=sid,parameter_set_id=f'q2r3-p{i:04d}',model_id=MODEL_IDS[mech],mechanism_id=mech,law_policy=policy,
            experiment_id=cfg['experiment_id'],parameter_version=cfg['parameter_version'],geometry_version='conditional_plane_slab_v1',
            evaluation_stratum='conditional_scenario',data_role='scenario',forecast_input_mode='ideal_weather',
            min_margin_all=float(result['failure_margin'][:,i].min()),min_margin_evaluation=float(result['failure_margin'][ev:,i].min()),
            final_margin=float(result['failure_margin'][-1,i]),initial_margin=float(result['failure_margin'][0,i]),
            final_interface_temp_c=float(result['interface_temp_c'][-1,i]),final_damage=float(result['damage'][-1,i]),
            peak_pressure_kpa=float(result['pressure_kpa'][:,i].max()),strength_domain_fraction=float(result['strength_domain'][:,i].mean()),
            evaluation_onset_status=late['onset_status'],**onset)
          record['crossing_time_utc']=str(forcing.time_utc.iloc[0]+pd.Timedelta(hours=onset['onset_elapsed_hours'])) if onset['onset_elapsed_hours'] is not None else None
          rows.append(record)
          params.append(dict(scenario_id=sid,parameter_set_id=f'q2r3-p{i:04d}',mechanism_id=mech,model_id=MODEL_IDS[mech],law_policy=policy,
            parameter_version=cfg['parameter_version'],geometry_version='conditional_plane_slab_v1',design_role='space_filling_not_probability',prior_weight=None,
            **{k:float(v[i]) for k,v in p.items()}))
        for i in reps:
          sid=scenario_id(i,mech,policy)
          status=classify_trajectory(result['failure_margin'][:,i])['onset_status']
          track=pd.DataFrame({'scenario_id':sid,'model_id':MODEL_IDS[mech],'mechanism_id':mech,'law_policy':policy,
           'time_utc':forcing.time_utc,'elapsed_hours':forcing.elapsed_hours,'failure_margin':result['failure_margin'][:,i],
           'margin_definition':MARGIN_DEFINITION,'interface_temp_c':result['interface_temp_c'][:,i],'damage':result['damage'][:,i],
           'storage_m':result['storage_m'][:,i],'pressure_kpa':result['pressure_kpa'][:,i],
           'strength_in_lab_domain':result['strength_domain'][:,i],'critical_head_m':result['critical_head_m'][:,i],
           'data_role':'scenario','forecast_input_mode':'ideal_weather','evaluation_stratum':'conditional_scenario',
           'parameter_version':cfg['parameter_version'],'geometry_version':'conditional_plane_slab_v1','physical_phase':'initiation',
           'available_time':None,'onset_status_whole_run':status})
          # Last forcing contributing to each state, not a claim of real-time availability.
          track['forcing_cutoff_utc']=forcing.time_utc.shift(1)
          tracks.append(track)
          if policy=='linear_extension':
            plan_area=float([10000,40000,100000][list(reps).index(i)%3]);h=float(p['thickness_normal_m'][i]);theta=float(p['theta_deg'][i]);rho=float(p['density_kg_m3'][i]);rf=float(p['rock_volume_fraction'][i])
            releases.append(dict(scenario_id=sid,model_id=MODEL_IDS[mech],mechanism_id=mech,geometry_version='conditional_area_requires_q4_polygon_v1',
              parameter_version=cfg['parameter_version'],source_polygon_or_release_raster=None,release_thickness_or_volume='see normal/vertical thickness and conditional plan-area volume columns',
              plan_area_m2=plan_area,release_thickness_normal_m=h,release_thickness_vertical_m=h/np.cos(np.deg2rad(theta)),
              release_volume_m3=plan_area*h/np.cos(np.deg2rad(theta)),phase_fraction_basis='volume',phase_fractions=json.dumps({'rock':rf,'ice':1-rf,'free_water':0}),
              density=rho,density_unit='kg m-3',initial_velocity=json.dumps({'x':0,'y':0,'z':0,'unit':'m s-1','crs':'EPSG:32645; zero vector direction immaterial'}),
              onset_status=status,evaluation_stratum='conditional_scenario',
              provenance_and_assumptions='area/plane/thickness/composition/zero velocity explicitly specified scenarios, not measured release; V=plan_area*h_normal/cos(theta); source polygon pending Q4; simulated onset is separate from travel time'))
        if policy=='linear_extension' and mech=='S_T_H':
          for label,kwargs in [('no_damage',dict(damage_enabled=False)),('no_drainage_damage_feedback',dict(drainage_feedback=False))]:
            alt=simulate(air,rain,p,mech,policy,thermal=thermal,**kwargs)
            for i in range(n):ablation.append(dict(parameter_set_id=f'q2r3-p{i:04d}',ablation=label,base_min_margin=float(result['failure_margin'][ev:,i].min()),
              alternative_min_margin=float(alt['failure_margin'][ev:,i].min()),paired_difference=float((alt['failure_margin'][ev:,i]-result['failure_margin'][ev:,i]).min()),evaluation_stratum='conditional_scenario'))
          dry=simulate(air,np.zeros_like(rain),p,mech,policy,thermal=thermal)
          for i in range(n):ablation.append(dict(parameter_set_id=f'q2r3-p{i:04d}',ablation='zero_rain_scenario_melt_retained',base_min_margin=float(result['failure_margin'][ev:,i].min()),
             alternative_min_margin=float(dry['failure_margin'][ev:,i].min()),paired_difference=float(dry['failure_margin'][ev:,i].min()-result['failure_margin'][ev:,i].min()),evaluation_stratum='conditional_scenario'))
          for i in reps:
            for temp in [-6.,-3.,-1.,-.5,0.]:
              pi=take(p,[i]);state=resistance(pi,np.array([p['initial_damage'][i]]),np.array([temp]),np.array([0.]))
              head=state['critical_head_m'][0];cap=min(p['connected_depth_m'][i],.98*state['normal_kpa'][0]/G)
              crit.append(dict(parameter_set_id=f'q2r3-p{i:04d}',temperature_c=temp,normal_kpa=state['normal_kpa'][0],driving_kpa=state['driving_kpa'][0],
                initial_damage=p['initial_damage'][i],critical_head_m=float(head) if np.isfinite(head) else None,
                root_status=str(state['critical_head_status'][0]),allowed_head_capacity_m=cap,
                root_reachable_before_capacity=bool(np.isfinite(head) and 0<head<=cap),lab_temperature_domain=-8<=temp<=-.5,
                evaluation_stratum='conditional_scenario'))
    outcomes=pd.DataFrame(rows);outcomes.to_csv(BASE/'results/scenario_outcomes.csv',index=False)
    pd.DataFrame(params).to_csv(BASE/'results/parameter_ensemble.csv',index=False)
    pd.concat(tracks,ignore_index=True).to_parquet(BASE/'results/state_trajectories.parquet',index=False,compression='zstd')
    pd.DataFrame(releases).to_csv(BASE/'results/release_states.csv',index=False)
    pd.DataFrame(ablation).to_csv(BASE/'results/ablation.csv',index=False)
    pd.DataFrame(crit).to_csv(BASE/'results/critical_relations.csv',index=False)
    comparison=[]
    for (mech,policy),group in outcomes.groupby(['mechanism_id','law_policy'],sort=False):
      comparison.append(dict(mechanism_id=mech,model_id=MODEL_IDS[mech],law_policy=policy,n_parameter_sets=len(group),
       interval_crossing_n=int((group.onset_status=='interval_crossing').sum()),left_censored_n=int(group.onset_status.str.startswith('left_censored').sum()),
       never_crossed_n=int((group.onset_status=='never_crossed').sum()),missing_n=int(group.onset_status.str.contains('missing').sum()),
       median_min_margin=float(group.min_margin_evaluation.median()),p05_min_margin=float(group.min_margin_evaluation.quantile(.05)),p95_min_margin=float(group.min_margin_evaluation.quantile(.95)),
       wholly_lab_domain_n=int((group.strength_domain_fraction==1).sum()),mean_lab_domain_fraction=float(group.strength_domain_fraction.mean()),
       independent_local_training_events=0,independent_local_validation_events=0,evaluation_stratum='conditional_scenario',design_fraction_is_probability=False))
    pd.DataFrame(comparison).to_csv(BASE/'results/model_comparison.csv',index=False)
    sensitivity=[]
    for (mech,policy),response in summary_arrays.items():
      # Joint design sensitivity, not confidence or causal parameter importance.
      x=np.column_stack([p[k] if RANGES[k][2]=='linear' else np.log(p[k]) for k in RANGES])
      z=(x-x.mean(0))/x.std(0);y=(response-response.mean())/response.std()
      beta=np.linalg.lstsq(np.column_stack([np.ones(n),z]),y,rcond=None)[0][1:]
      for j,k in enumerate(RANGES):
        sensitivity.append(dict(mechanism_id=mech,law_policy=policy,parameter=k,spearman_rho=float(pd.Series(p[k]).rank().corr(pd.Series(response).rank())),standardized_linear_coefficient=float(beta[j]),
           outcome='minimum margin Aug19..Aug27',n_joint_design=n,evaluation_stratum='conditional_scenario',interpretation='design-dependent association; no causal/empirical posterior interpretation'))
    pd.DataFrame(sensitivity).to_csv(BASE/'results/sensitivity.csv',index=False)
    # Pointwise extrema interaction does not commute: report both paired minima
    # contrast and representative trajectory contrasts separately.
    inter=summary_arrays[('S_T_H','linear_extension')]-summary_arrays[('S_T','linear_extension')]-summary_arrays[('S_H','linear_extension')]+summary_arrays[('S','linear_extension')]
    pd.DataFrame({'parameter_set_id':[f'q2r3-p{i:04d}' for i in range(n)],'contrast_of_minima_STH_minus_ST_minus_SH_plus_S':inter,
      'evaluation_stratum':'conditional_scenario'}).to_csv(BASE/'results/interaction.csv',index=False)
    write_json(BASE/'results/run_metadata.json',dict(runtime_seconds=time.perf_counter()-t0,python=platform.python_version(),numpy=np.__version__,
      parameter_sets=n,models=4,law_policies=2,scenario_outcomes=len(rows),representative_state_rows=len(reps)*8*nt,
      time_origin_utc=str(forcing.time_utc.iloc[0]),time_step_hours=1,nt=nt,information_cutoff='forcing_cutoff_utc per state; real available_time unknown',
      max_water_budget_error_m=watermax,input_version=INPUT_VERSION,probability_prior=False,independent_validation_events=0))
    contract=dict(contract_version='q2r3-mechanism-contract-v1',input_version=INPUT_VERSION,model_ids=MODEL_IDS,
       parameter_version=cfg['parameter_version'],evaluation_stratum='conditional_scenario',data_role='scenario',forecast_input_mode='ideal_weather',
       time_origin_utc=cfg['start_utc'],time_step_hours=1,forcing_interval='forcing[i] drives [time[i],time[i+1]); state[0] specified initial condition',
       real_available_time=None,margin_definition=MARGIN_DEFINITION,positive_is_stable=True,
       onset_status_values=['left_censored_already_unstable','interval_crossing','never_crossed','missing','missing_before_possible_crossing'],
       onset_rule=cfg['crossing_rule'],no_probability_prior=True,grid_weights=None,
       engine_entry='scripts/mechanism_engine.py: simulate(air_c,precip_mm_h,parameters,mechanism,policy,dt_hours,dz_m)',
       state_columns={'interface_temp_c':'degC','damage':'dimensionless cohesion-loss fraction','storage_m':'water-equivalent m','pressure_kpa':'kPa','failure_margin':'dimensionless'},
       equations=['sigma_n=rho*g*h_normal*cos(theta)/1000 kPa; tau=rho*g*h_normal*sin(theta)/1000 kPa',
        'R=(1-D)*(fb*cb+(1-fb)*cj(T))+max(sigma_n-u,0)*(fb*mub+(1-fb)*muj(T))',
        'cj=53.3-73.5*T kPa; muj=.42-.21*T; external_transfer ice-filled limestone fast-shear law',
        'dT/dt=alpha*Tzz; Tsurface=min(Tstation+offset,0); no-flux at40m',
        'dW/dt=I-W/tau_d; head=W/Sy; u=g*head kPa; capacity=min(connected_depth,.98*sigma_n/g)',
        'Dnext=1-(1-D)*exp(-A*min(tau/max(R,1e-6),10)^n*dt); cap D .999999',
        'tau_d=drainage_hours*exp(-drainage_damage_coupling*D)'],
       applicability={'Mamot2018':{'temperature_c':[-8,-.5],'effective_normal_kpa':[100,400],
         'material':'ice-filled limestone joint','strain_rate_s_inv':'mean (4.8+/-1.4)e-3; not slow creep'},
         'conditional_extensions':['effective-stress substitution','area mixing','damage law','temperature/rain transfer','melt proxy','thaw branch mu=.6']},
       refutation=['deep joint temperature unchanged contradicts rapid conductive weakning at that depth','measured head below conditional critical relation challenges pressure trigger','geometry/material mismatch rejects assigned slab/strength transfer'],
       limitations=['not event-calibrated; independent events=0','linear_extension outside lab range explicitly flagged','thaw branch uncalibrated','post-crossing continuation diagnostic only','representatives are 8 fixed design indices; all 2048 outcomes retain no-start and censoring'])
    write_json(BASE/'results/mechanism_contract.json',contract)
    export_v1()
    print(json.dumps({'outcomes':len(rows),'representative_state_rows':len(reps)*8*nt,'runtime_seconds':time.perf_counter()-t0,'water_budget_max_abs_m':watermax}))


def export_v1():
    common=['EXPERIMENT_PROTOCOL.md','config/experiment_v1.json','scripts/mechanism_engine.py','results/mechanism_contract.json','results/parameter_ensemble.csv','results/forcing_hourly_v1.csv']
    limitations=['All source mechanism and release states conditional scenarios, not local measurements or calibrated event probability.',
      'No probability weights. First-row unstable left-censored, never-crossed and missing retained.','Real weather availability unknown; ideal_weather retrospective forcing.',
      'Mamot strength transferred beyond original material/stress/rate/temperature domain where marked.','Initiation is separate from propagation arrival. Human scientific adoption pending.']
    for name,paths in [('mechanism',common+['results/state_trajectories.parquet','results/scenario_outcomes.csv']),
                       ('release',['results/release_states.csv','results/parameter_ensemble.csv','results/mechanism_contract.json','config/experiment_v1.json'])]:
        target=BASE/f'exports/{name}_bundle.json'
        bundle=dict(bundle_version=f'q2-r3-{name}-v1',producer_question='q2',input_version=INPUT_VERSION,evaluation_stratum='conditional_scenario',
          files=[digest(BASE/p,p) for p in paths],limitations=limitations)
        # Never mutate a published bundle or any byte-bound v1 file on rerun.
        if target.exists():
            assert json.loads(target.read_text())==bundle,'published bundle changed; create v2 instead'
        else: write_json(target,bundle)


if __name__=='__main__': run()
