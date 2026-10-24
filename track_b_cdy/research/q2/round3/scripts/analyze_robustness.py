"""Post-v1 explicitly declared mapping/coefficient/response sensitivity."""
from pathlib import Path
import itertools,json,math
import numpy as np
import pandas as pd
from mechanism_engine import simulate,thermal_transfer,resistance,stresses,classify_trajectory,G
from run_experiments import BASE,CONFIG,parameter_design,take


def run():
    cfg=json.loads(CONFIG.read_text());p=parameter_design(cfg)
    forcing=pd.read_csv(BASE/'results/forcing_hourly_v1.csv');air=forcing.station_air_temp_c.to_numpy();rain=forcing.precip_assumed_mm_h.to_numpy()
    base=pd.read_csv(BASE/'results/scenario_outcomes.csv');sub=base[(base.mechanism_id=='S_T_H')&(base.law_policy=='linear_extension')].reset_index(drop=True)
    ev=int(np.flatnonzero(pd.to_datetime(forcing.time_utc,utc=True)>=cfg['evaluation_start_utc'])[0]);rows=[]
    for shift in [-3,3]:
        changed={k:v.copy() for k,v in p.items()};changed['station_source_offset_c']+=shift
        alt=simulate(air,rain,changed,'S_T_H')
        for i in range(cfg['n_parameter_sets']):
            onset=classify_trajectory(alt['failure_margin'][:,i])
            rows.append(dict(parameter_set_id=f'q2r3-p{i:04d}',station_source_offset_shift_c=shift,
              base_min_margin=float(sub.min_margin_evaluation.iloc[i]),shifted_min_margin=float(alt['failure_margin'][ev:,i].min()),
              base_onset_status=sub.onset_status.iloc[i],shifted_onset_status=onset['onset_status'],
              evaluation_stratum='conditional_scenario',probability_interpretation=False))
        print('Mapping sensitivity',shift,'complete',flush=True)
    pd.DataFrame(rows).to_csv(BASE/'results/mapping_sensitivity.csv',index=False)
    tracks=pd.read_parquet(BASE/'results/state_trajectories.parquet');tracks=tracks[tracks.law_policy=='linear_extension']
    coefficient=[]
    for (sid,mech),frame in tracks.groupby(['scenario_id','mechanism_id'],sort=False):
        index=int(sid.split('-p')[1].split('-')[0]);pi=take(p,[index]);sn,_=stresses(pi)
        t=frame.interface_temp_c.to_numpy();d=frame.damage.to_numpy();u=frame.pressure_kpa.to_numpy();fb=pi['bridge_fraction'][0]
        _,drive=stresses(pi);mask=pd.to_datetime(frame.time_utc,utc=True)>=cfg['evaluation_start_utc']
        for signs in itertools.product([-1,1],repeat=4):
            dc0,dcT,dmu0,dmuT=np.array(signs)*np.array([20.6,8.8,.15,.06])
            # coefficient convention c=c0+cT*T where baseline cT=-73.5.
            delta=(1-d)*(1-fb)*(dc0+dcT*t)+np.maximum(sn[0]-u,0)*(1-fb)*(dmu0+dmuT*t)
            shifted=frame.failure_margin.to_numpy()+delta/drive[0]
            coefficient.append(dict(scenario_id=sid,mechanism_id=mech,corner=''.join('p' if s>0 else 'm' for s in signs),
              dc0_kpa=dc0,dcT_kpa_per_c=dcT,dmu0=dmu0,dmuT_per_c=dmuT,
              base_min_margin=float(frame.loc[mask,'failure_margin'].min()),frozen_state_min_margin=float(shifted[mask].min()),
              evaluation_stratum='conditional_scenario',role='frozen_state_constitutive_sensitivity_not_dynamic_rerun',is_confidence_interval=False))
    pd.DataFrame(coefficient).to_csv(BASE/'results/strength_coefficient_sensitivity.csv',index=False)
    response=[]
    for alpha,depth,hours in itertools.product([.9e-6,1.5e-6,2.1e-6],[.5,2,5,10,20],[24,72,168]):
        response.append(dict(diffusivity_m2_s=alpha,depth_m=depth,hours=hours,
          step_response_fraction=math.erfc(depth/(2*math.sqrt(alpha*hours*3600))),diffusion_scale_hours=depth**2/alpha/3600,
          evaluation_stratum='numerical_benchmark',interpretation='half-space constant-property conductive step; not local boundary prediction'))
    pd.DataFrame(response).to_csv(BASE/'results/thermal_response_times.csv',index=False)
    # v1 ablation paired minimum contrasts recomputed from exported minima;
    # keep originally written pointwise minimum-difference column distinct.
    ab=pd.read_csv(BASE/'results/ablation.csv');ab['difference_of_minima']=ab.alternative_min_margin-ab.base_min_margin
    ab.to_csv(BASE/'results/ablation_summary.csv',index=False)
    print(json.dumps({'mapping_rows':len(rows),'coefficient_corners':len(coefficient),'response_rows':len(response)}))


if __name__=='__main__':run()
