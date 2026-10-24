#!/usr/bin/env python3
"""Audit frozen applicability exports; no physical simulation or reweighting."""
from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent
R=HERE.parents[2];ROOT=R.parents[3]
ANALYTIC=R/'results/mechanistic_replay/analytic_erfc'
BUNDLE=R/'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1/bundle.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    bundle=json.loads(BUNDLE.read_text());files={x['role']:ROOT/x['path'] for x in bundle['files']}
    inputs=[BUNDLE,ANALYTIC/'delivery_index.json',ANALYTIC/'parameter_first_passages.parquet',
      files['parameter_ensemble.csv'],files['scenario_outcomes.csv'],files['frozen_mechanical_engine'],
      files['mechanism_contract.json'],files['analytic_reproduction_script'],
      R/'scripts/mechanistic_replay.py',ANALYTIC/'replay.py']
    before={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in inputs}
    index=json.loads((ANALYTIC/'delivery_index.json').read_text())
    assert all((ROOT/x['path']).stat().st_size==x['bytes'] and sha(ROOT/x['path'])==x['sha256'] for x in index['files'])
    ensemble=pd.read_csv(files['parameter_ensemble.csv'])
    p=ensemble[ensemble.parameter_set_id.eq('q2r3-p0149')];assert len(p)==8
    a=p.iloc[0];g=9.80665
    # Independent scalar formula/units check, without invoking model code.
    normal=float(a.density_kg_m3*g*a.thickness_normal_m*np.cos(np.deg2rad(a.theta_deg))/1000)
    driving=float(a.density_kg_m3*g*a.thickness_normal_m*np.sin(np.deg2rad(a.theta_deg))/1000)
    capacity_pressure=float(g*min(a.connected_depth_m,.98*normal/g))
    columns=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','scenario_id','parameter_set_id',
      'mechanism_id','law_policy','followup_hours','forecast_status','crossing_point_hours_after_issue',
      'strength_domain_fraction_observed','max_observed_pressure_kpa','known_at_risk_under_conditional_history']
    crossings=[];design=[];total=0
    for batch in pq.ParquetFile(ANALYTIC/'parameter_first_passages.parquet').iter_batches(batch_size=65536,columns=columns):
        x=batch.to_pandas();total+=len(x)
        crossings.append(x[x.crossing_point_hours_after_issue.notna()])
        design.append(x[x.parameter_set_id.eq('q2r3-p0149')])
    c=pd.concat(crossings,ignore_index=True);d=pd.concat(design,ignore_index=True)
    grouped=c.groupby(['mechanism_id','law_policy','forecast_input_mode']).agg(rows=('scenario_id','size'),
      minimum_domain_fraction=('strength_domain_fraction_observed','min'),maximum_domain_fraction=('strength_domain_fraction_observed','max'),
      maximum_pressure_kpa=('max_observed_pressure_kpa','max')).reset_index().to_dict('records')
    per_design=d.groupby(['mechanism_id','law_policy']).agg(rows=('scenario_id','size'),
      minimum_domain_fraction=('strength_domain_fraction_observed','min'),maximum_domain_fraction=('strength_domain_fraction_observed','max'),
      maximum_pressure_kpa=('max_observed_pressure_kpa','max')).reset_index().to_dict('records')
    q=pd.read_csv(files['scenario_outcomes.csv']);q=q[q.parameter_set_id.eq('q2r3-p0149')]
    q=q[['scenario_id','mechanism_id','law_policy','strength_domain_fraction','onset_status','onset_elapsed_hours','peak_pressure_kpa']]
    physical={k:float(a[k]) for k in ['theta_deg','thickness_normal_m','density_kg_m3','rock_volume_fraction',
      'initial_temp_c','connected_depth_m','interface_depth_m','bridge_fraction','damage_rate_h_inv','initial_damage']}
    unchanged=all(p.stat().st_size==before[str(p.relative_to(ROOT))]['bytes'] and sha(p)==before[str(p.relative_to(ROOT))]['sha256'] for p in inputs)
    checks=dict(frozen_analytic_index_valid=True,input_bytes_unchanged=unchanged,
      all_342_crossing_rows_present=len(c)==342,all_crossing_domain_fractions_exact_zero=bool(c.strength_domain_fraction_observed.eq(0).all()),
      crossing_domain_fractions_nonmissing=bool(c.strength_domain_fraction_observed.notna().all()),
      only_p0149_S_supplies_crossing_rows=set(c.parameter_set_id)=={'q2r3-p0149'} and set(c.mechanism_id)=={'S'},
      all_crossing_pressures_exact_zero=bool(c.max_observed_pressure_kpa.eq(0).all()),
      every_p0149_branch_never_reaches_registered_stress_domain_even_at_capacity=normal-capacity_pressure>400)
    result=dict(review_id='q3r3-analytic-applicability-readonly-v1',generated_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
      review_scope='Read frozen exports/source and independent scalar stress/units arithmetic only; no simulate/thermal/forecast/weight functions executed',
      inputs=[dict(path=k,**v) for k,v in before.items()],review_source_sha256=sha(Path(__file__)),
      source_locations=dict(normal_stress='mechanism_engine.py:15-20',applicability_mask='mechanism_engine.py:38-47',
        Q2_full_history_fraction='run_analytic_thermal.py:208',Q3_forecast_fraction='mechanistic_replay.py:245-266',
        Q3_ensemble_fraction='mechanistic_replay.py:300',density_mixture='run_experiments.py:91'),
      total_parameter_rows=total,crossing_rows=len(c),crossing_issue_count=int(c.issue_time.nunique()),
      first_crossing_issue_utc=str(c.issue_time.min()),last_crossing_issue_utc=str(c.issue_time.max()),
      crossing_law_counts={str(k):int(v) for k,v in c.law_policy.value_counts().items()},
      crossing_weather_mode_counts={str(k):int(v) for k,v in c.forecast_input_mode.value_counts().items()},
      crossing_domain_fraction_unique=[float(x) for x in sorted(c.strength_domain_fraction_observed.unique())],
      crossing_breakdown=grouped,p0149_physical_parameters=physical,
      scalar_formula_check=dict(density_mixture_917_2700_kg_m3=float(917*(1-a.rock_volume_fraction)+2700*a.rock_volume_fraction),
        normal_stress_kpa=normal,driving_shear_kpa=driving,initial_temperature_in_registered_domain=bool(-8<=a.initial_temp_c<=-.5),
        water_capacity_pressure_upper_bound_kpa=capacity_pressure,effective_stress_lower_bound_all_p0149_mechanisms_kpa=normal-capacity_pressure,
        stress_domain_upper_kpa=400.,domain_failure_reason='stress_outside; constant S temperature is within interval'),
      p0149_all_weather_trajectories=per_design,p0149_Q2_full_history_outcomes=q.to_dict('records'),
      registered_applicability=json.loads(files['mechanism_contract.json'].read_text())['applicability'],
      field_semantics=dict(
        Q2_strength_domain_fraction='Mean Boolean over all 2089 Jun1-Aug27 source-state samples, not only Aug19 evaluation window; includes post-cross counterfactual continuation',
        Q3_strength_domain_fraction_observed='Mean Boolean over L+1 issue..issue+L sampled states, where L is actual followup 0..72; includes issue, endpoint, and any post-cross continuation',
        sample_domain='-8 <= model interface temperature <= -0.5 C AND 100 <= sigma_n - model pore_pressure <= 400 kPa; effective stress not clipped for this check',
        mechanics='S/S_H freeze interface temperature at initial value; S/S_T force pore pressure=0; S_T/S_T_H use analytic temperature; H branches use scenario reservoir pressure',
        policies='Same applicability mask for both laws; thawed_rock_contact above -0.5 C remains outside the Mamot mask; at p0149-S both laws are algebraically identical',
        interpretation='Not a crossing-time flag, publication availability, experimental validation score, or probability; partial fraction does not identify which samples were in-domain'),
      checks=checks,passed=all(checks.values()),independent_observed_validation_events=0)
    assert result['passed'],result
    output=HERE/'applicability_review.json';assert not output.exists(),'Review versions are append-only'
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],crossing_rows=len(c),output=str(output.relative_to(ROOT)),sha256=sha(output)),ensure_ascii=False))

if __name__=='__main__':main()
