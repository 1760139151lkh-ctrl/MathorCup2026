#!/usr/bin/env python3
"""Independent lineage/branch audit of completed analytic and FD exports."""
from pathlib import Path
import hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent
R=HERE.parents[2];ROOT=R.parents[3]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,x):path.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def read_bundle(name):
    path=R/'inputs/q2'/name/'bundle.json';b=json.loads(path.read_text())
    return path,b,{x['role']:ROOT/x['path'] for x in b['files']}

def main():
    oldp,oldb,old=read_bundle('mechanism_bundle_v2_q2-r3-mechanism-thermal-refinement-v2')
    newp,newb,new=read_bundle('analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1')
    a=pd.read_csv(old['parameter_ensemble.csv']).set_index('base_scenario_id').sort_index()
    b=pd.read_csv(new['parameter_ensemble.csv']).set_index('base_scenario_id').sort_index()
    assert a.index.equals(b.index) and a.index.is_unique
    config=json.loads(new['config.json'].read_text());physical=list(config['ranges'])+['density_kg_m3']
    physical_diff={k:float(np.max(abs(a[k].to_numpy(float)-b[k].to_numpy(float)))) for k in physical}
    exact_metadata={k:a[k].equals(b[k]) for k in ['parameter_set_id','mechanism_id','law_policy','geometry_version','parameter_version']}
    oldforcing=next(path for key,path in old.items() if key in ['forcing_hourly_v2.csv','results/forcing_hourly_v1.csv'])
    fa=pd.read_csv(oldforcing);fb=pd.read_csv(new['forcing_hourly.csv'])
    forcing_same=fa.equals(fb)
    common=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','forecast_reference_time',
      'base_scenario_id','parameter_set_id','mechanism_id','law_policy','followup_hours','history_status','forecast_status']
    fields=['final_margin','crossing_point_hours_after_issue','initial_margin_at_issue','future_interface_temperature_change_c','max_observed_pressure_kpa']
    pa=pq.ParquetFile(R/'results/mechanistic_replay/v2/parameter_first_passages.parquet')
    pb=pq.ParquetFile(HERE/'parameter_first_passages.parquet')
    assert pa.metadata.num_rows==pb.metadata.num_rows==1536000
    counts=defaultdict(lambda:dict(rows=0,changed_crossing_status=0,changed_point_nullness=0,maximum_point_time_difference_hours=0.,
      maximum_initial_margin_difference=0.,maximum_final_margin_difference=0.,maximum_thermal_change_difference_c=0.,maximum_pressure_difference_kpa=0.))
    weather_effects=[]
    keys_match=True;total=0
    ideal_for_issue={}
    # Earlier metadata cleanup regrouped FD v2 Parquet into 65536-row blocks;
    # storage row groups are not scientific track boundaries. Stream both in
    # the registered 2048-row physical-design blocks instead.
    xa=pa.iter_batches(batch_size=2048,columns=common+fields)
    ya=pb.iter_batches(batch_size=2048,columns=common+fields)
    for i,(xb,yb) in enumerate(zip(xa,ya)):
        x=xb.to_pandas();y=yb.to_pandas()
        total+=len(y)
        compare_keys=[k for k in common if k not in ['forecast_status']]
        keys_match &= x[compare_keys].equals(y[compare_keys])
        if not keys_match:raise AssertionError('Version rows must pair on physical/scenario/weather keys')
        for mech,idx in y.groupby('mechanism_id').groups.items():
            ix=np.asarray(idx);g=counts[mech];g['rows']+=len(ix)
            g['changed_crossing_status']+=int(np.sum(x.forecast_status.iloc[ix].to_numpy()!=y.forecast_status.iloc[ix].to_numpy()))
            xp=x.crossing_point_hours_after_issue.iloc[ix].to_numpy(float);yp=y.crossing_point_hours_after_issue.iloc[ix].to_numpy(float)
            g['changed_point_nullness']+=int(np.sum(np.isfinite(xp)!=np.isfinite(yp)))
            good=np.isfinite(xp)&np.isfinite(yp)
            if good.any():g['maximum_point_time_difference_hours']=max(g['maximum_point_time_difference_hours'],float(np.max(abs(xp[good]-yp[good]))))
            for field,label in [('initial_margin_at_issue','maximum_initial_margin_difference'),('final_margin','maximum_final_margin_difference'),
              ('future_interface_temperature_change_c','maximum_thermal_change_difference_c'),('max_observed_pressure_kpa','maximum_pressure_difference_kpa')]:
                g[label]=max(g[label],float(np.max(abs(x[field].iloc[ix].to_numpy(float)-y[field].iloc[ix].to_numpy(float)))))
        mode=y.forecast_input_mode.iloc[0];issue=y.issue_time.iloc[0]
        if mode=='ideal_weather':ideal_for_issue={issue:y}
        if mode=='assumed_latency' and issue in ideal_for_issue:
            oracle=ideal_for_issue[issue]
            # State endpoints are comparable only at the same followup time.
            if y.followup_hours.iloc[0]==oracle.followup_hours.iloc[0] and y.followup_hours.iloc[0]>0:
                for mech,idx in y.groupby('mechanism_id').groups.items():
                    ix=np.asarray(idx)
                    weather_effects.append(dict(issue_time=issue,space_object=y.space_object.iloc[0],assumed_latency_hours=float(y.assumed_latency_hours.iloc[0]),
                      mechanism_id=mech,followup_hours=int(y.followup_hours.iloc[0]),rows=len(ix),
                      maximum_final_margin_weather_vs_ideal_difference=float(np.max(abs(y.final_margin.iloc[ix].to_numpy(float)-oracle.final_margin.iloc[ix].to_numpy(float)))),
                      maximum_interface_temperature_weather_vs_ideal_difference_c=float(np.max(abs(y.future_interface_temperature_change_c.iloc[ix].to_numpy(float)-oracle.future_interface_temperature_change_c.iloc[ix].to_numpy(float)))),
                      maximum_pressure_weather_vs_ideal_difference_kpa=float(np.max(abs(y.max_observed_pressure_kpa.iloc[ix].to_numpy(float)-oracle.max_observed_pressure_kpa.iloc[ix].to_numpy(float))))))
    rows=[dict(mechanism_id=k,**v) for k,v in sorted(counts.items())]
    pd.DataFrame(rows).to_csv(HERE/'paired_v2_analytic_parameter_summary.csv',index=False)
    pd.DataFrame(weather_effects).to_csv(HERE/'equal_followup_weather_state_contrasts.csv',index=False)
    checks=dict(full_2048_same_physical_parameter_values=all(x==0 for x in physical_diff.values()),
      full_2048_same_base_id_and_metadata=all(exact_metadata.values()),same_history_forcing_values=forcing_same,
      all_1536000_rows_exact_weather_base_scenario_pairing=keys_match and total==1536000,
      nonthermal_S_and_SH_branches_unchanged=all(counts[k]['maximum_final_margin_difference']==0 and counts[k]['maximum_initial_margin_difference']==0 and
        counts[k]['maximum_pressure_difference_kpa']==0 and counts[k]['maximum_point_time_difference_hours']==0 and
        counts[k]['changed_crossing_status']==0 and counts[k]['changed_point_nullness']==0 for k in ['S','S_H']))
    result=dict(checks=checks,passed=all(checks.values()),parameter_rows=2048,paired_forecast_rows=total,
      physical_parameter_maximum_absolute_differences=physical_diff,metadata_identity=exact_metadata,
      input_bundles=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in [oldp,newp]],
      forecast_parameter_comparison=rows,equal_followup_weather_state_contrast_rows=len(weather_effects),
      interpretation='Thermal-provider sensitivity under identical physical designs and source forcing. GFS vs ideal endpoint contrasts require equal followup. Nonzero state changes can coexist with unchanged rare discrete first-cross events; no empirical weather-skill claim.',
      audit_source_sha256=sha(Path(__file__)))
    dump(HERE/'lineage_and_parameter_validation.json',result)
    assert result['passed'],result
    summary=json.loads((HERE/'summary.json').read_text());summary['lineage_and_parameter_validation']=result
    summary['checks'].update(checks);summary['passed']=all(summary['checks'].values());dump(HERE/'summary.json',summary)
    validation=json.loads((HERE/'validation.json').read_text());validation['checks'].update(checks)
    validation['lineage_and_parameter_validation']=result;validation['passed']=all(validation['checks'].values());dump(HERE/'validation.json',validation)
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
