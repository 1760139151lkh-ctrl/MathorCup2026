"""Refined complete-state run, applicability audit and pointwise interaction."""
import json
import numpy as np
import pandas as pd
from mechanism_engine import simulate,thermal_transfer,classify_trajectory
from run_experiments import BASE,CONFIG,parameter_design,take


def run():
    cfg=json.loads(CONFIG.read_text());p=parameter_design(cfg);tracks=pd.read_parquet(BASE/'results/state_trajectories.parquet')
    outcomes=pd.read_csv(BASE/'results/scenario_outcomes.csv')
    audit=outcomes[['scenario_id','mechanism_id','law_policy','strength_domain_fraction']].copy()
    audit['numeric_domain_definition']='T in [-8,-0.5] C and effective normal stress100..400kPa only'
    audit['local_joint_material_validation']='unknown';audit['local_joint_strain_rate_s_inv']=None
    audit['rate_transfer_status']='unknown; phenomenological damage_rate_h_inv is not shear strain rate'
    audit['effective_stress_substitution']='conditional uncalibrated extension'
    audit['local_strength_validation']='not_validated';audit['evaluation_stratum']='conditional_scenario'
    audit.to_csv(BASE/'results/applicability_audit.csv',index=False)
    linear=tracks[tracks.law_policy=='linear_extension'].copy();linear['parameter_set_id']=linear.scenario_id.str.extract('(q2r3-p[0-9]+)')
    wide=linear.pivot(index=['parameter_set_id','time_utc','elapsed_hours'],columns='mechanism_id',values='failure_margin')
    wide['pointwise_interaction']=wide.S_T_H-wide.S_T-wide.S_H+wide.S
    wide[['pointwise_interaction']].reset_index().to_parquet(BASE/'results/interaction_timepoint.parquet',index=False)
    forcing=pd.read_csv(BASE/'results/forcing_hourly_v1.csv');air=forcing.station_air_temp_c.to_numpy();rain=forcing.precip_assumed_mm_h.to_numpy()
    indices=np.linspace(0,cfg['n_parameter_sets']-1,8,dtype=int);ps=take(p,indices)
    finer_air=np.r_[np.repeat(air[:-1],2),air[-1]];finer_rain=np.r_[np.repeat(rain[:-1],2),rain[-1]]
    heat=thermal_transfer(finer_air,ps,.5,.25)
    rows=[]
    for mechanism in cfg['models']:
      refined=simulate(finer_air,finer_rain,ps,mechanism,dt_hours=.5,dz_m=.25,thermal=heat)
      for j,i in enumerate(indices):
        coarse=linear[(linear.parameter_set_id==f'q2r3-p{i:04d}')&(linear.mechanism_id==mechanism)].sort_values('time_utc')
        ref=refined['failure_margin'][::2,j];c=coarse.failure_margin.to_numpy();a=classify_trajectory(c);b=classify_trajectory(ref)
        rows.append(dict(parameter_set_id=f'q2r3-p{i:04d}',mechanism_id=mechanism,coarse_dt_h=1,coarse_dz_m=.5,refined_dt_h=.5,refined_dz_m=.25,
          max_abs_margin_difference=float(np.abs(ref-c).max()),final_margin_difference=float(ref[-1]-c[-1]),
          max_abs_temperature_difference_c=float(np.abs(refined['interface_temp_c'][::2,j]-coarse.interface_temp_c.to_numpy()).max()),
          max_abs_pressure_difference_kpa=float(np.abs(refined['pressure_kpa'][::2,j]-coarse.pressure_kpa.to_numpy()).max()),
          coarse_status=a['onset_status'],refined_status=b['onset_status'],status_agrees=a['onset_status']==b['onset_status'],
          evaluation_stratum='numerical_benchmark',independent_events=0))
      print('Refined numerical comparison',mechanism,flush=True)
    pd.DataFrame(rows).to_csv(BASE/'results/convergence.csv',index=False)
    print(json.dumps({'convergence_rows':len(rows),'max_margin_difference':max(r['max_abs_margin_difference'] for r in rows),'status_agreement':sum(r['status_agrees'] for r in rows)}))


if __name__=='__main__':run()
