#!/usr/bin/env python3
"""Consume the actual Q2 erfc bundle; keep prior FD deliveries immutable."""
from __future__ import annotations
import hashlib
import json
import sys
import types
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
R=HERE.parents[2]
ROOT=R.parents[3]
FD_SOURCE=R/'scripts/mechanistic_replay.py'
BUNDLE=R/'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1/bundle.json'
BUNDLE_HASH='05e8b885198a3011e316472f562ba92480788cb04c6ab9bebfb3e04dbd3660ca'
FD_INDEX=R/'results/mechanistic_replay/delivery_index.json'
FD_INDEX_HASH='404bba4b1a429d16ac154fd73549fe2e69aff05fd5be6bc54c89a0030e69a4a7'
REGISTRATION=HERE/'ANALYTIC_REPLAY.md'
EXPERIMENT='q3r3-full-mechanistic-weather-replay-analytic-erfc-v1'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

# Execute the prior consumer read-only, without __pycache__ or CLI execution.
fd=types.ModuleType('frozen_fd_replay_helpers')
fd.__file__=str(FD_SOURCE)
exec(compile(FD_SOURCE.read_text(),str(FD_SOURCE),'exec'),fd.__dict__)
assert fd.ROOT==ROOT and fd.R==R
original_history=fd.continuous_history
original_forecast=fd.forecast

def load_inputs(mechanisms=None):
    assert mechanisms is None,'Registered study retains all four mechanisms'
    assert ROOT==Path('<LOCAL_HOME>/Documents/MathorCup/worktrees/track-b-q3')
    assert sha(BUNDLE)==BUNDLE_HASH and sha(FD_INDEX)==FD_INDEX_HASH
    assert REGISTRATION.exists()
    index=json.loads(FD_INDEX.read_text())
    # Validate every immutable prior-delivery entry, not only its index hash.
    for item in index['files']:
        path=ROOT/item['path']
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],str(path)
    bundle=json.loads(BUNDLE.read_text());files={}
    for item in bundle['files']:
        path=ROOT/item['path']
        assert path.is_relative_to(R/'inputs') and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
        assert item['role'] not in files
        files[item['role']]=path
    assert len(files)==21
    aliases={'scripts/mechanism_engine.py':'frozen_mechanical_engine',
      'config/experiment_v1.json':'config.json','results/parameter_ensemble.csv':'parameter_ensemble.csv',
      'results/forcing_hourly_v1.csv':'forcing_hourly.csv','results/scenario_outcomes.csv':'scenario_outcomes.csv',
      'results/state_trajectories.parquet':'state_trajectories.parquet'}
    for canonical,actual in aliases.items():files[canonical]=files[actual]
    mechanical=types.ModuleType('q2_erfc_frozen_mechanical')
    exec(compile(files['frozen_mechanical_engine'].read_text(),str(files['frozen_mechanical_engine']),'exec'),mechanical.__dict__)
    analytic=types.ModuleType('q2_delivered_analytic_thermal')
    previous=sys.modules.get('mechanism_engine')
    sys.modules['mechanism_engine']=mechanical
    try:exec(compile(files['callable_analytic_thermal_wrapper'].read_text(),str(files['callable_analytic_thermal_wrapper']),'exec'),analytic.__dict__)
    finally:
        if previous is None:sys.modules.pop('mechanism_engine',None)
        else:sys.modules['mechanism_engine']=previous
    mechanical.analytic=analytic
    ensemble=pd.read_csv(files['parameter_ensemble.csv'])
    forcing=pd.read_csv(files['forcing_hourly.csv'])
    config=json.loads(files['config.json'].read_text())
    assert len(ensemble)==2048 and ensemble.scenario_id.is_unique and ensemble.base_scenario_id.notna().all()
    assert set(ensemble.mechanism_id)=={'S','S_T','S_H','S_T_H'}
    assert len(forcing)==2089
    clock=[fd.dt(x) for x in forcing.time_utc]
    assert all(y-x==timedelta(hours=1) for x,y in zip(clock[:-1],clock[1:]))
    air=forcing.station_air_temp_c.to_numpy(float);rain=forcing.precip_assumed_mm_h.to_numpy(float)
    assert np.isfinite(air).all() and np.isfinite(rain).all() and (rain>=0).all()
    sources=HERE/'execution_source';sources.mkdir(parents=True,exist_ok=True)
    for path,label,suffix in [(Path(__file__),'analytic_replay','.py.txt'),(FD_SOURCE,'frozen_fd_helpers','.py.txt'),
                              (REGISTRATION,'registered_protocol','.md')]:
        snapshot=sources/(label+'_'+sha(path)+suffix)
        if snapshot.exists():assert snapshot.read_bytes()==path.read_bytes()
        else:snapshot.write_bytes(path.read_bytes())
        files['consumer:'+label]=snapshot
    for path in [BUNDLE,FD_INDEX,R/'inputs/weather/gfs_hourly_summary.csv',
                 R/'results/mechanistic_replay/v2/predictions.csv.gz']:
        files['consumer:'+str(path.relative_to(R))]=path
    return mechanical,bundle,files,ensemble,forcing,config,clock,air,rain

class AnalyticPhysics(fd.Physics):
    """Q2 mechanical state plus complete causal thermal boundary history."""
    def __init__(self,q,ensemble,config):
        self.q=q;self.f=ensemble;self.n=len(ensemble)
        self.names=list(config['ranges'])+['density_kg_m3']
        self.p={k:ensemble[k].to_numpy(float) for k in self.names}
        bases=ensemble.drop_duplicates('parameter_set_id').sort_values('parameter_set_id')
        self.baseids=list(bases.parameter_set_id);self.nb=len(bases)
        self.bp={k:bases[k].to_numpy(float) for k in self.names}
        self.baseindex=np.array([self.baseids.index(x) for x in ensemble.parameter_set_id])
        assert self.nb==256 and all(np.array_equal(self.p[k],self.bp[k][self.baseindex]) for k in self.names)
        self.has_t=ensemble.mechanism_id.isin(['S_T','S_T_H']).to_numpy()
        self.has_h=ensemble.mechanism_id.isin(['S_H','S_T_H']).to_numpy()
        self.policies={k:np.flatnonzero(ensemble.law_policy.eq(k)) for k in ['linear_extension','thawed_rock_contact']}
        self.policy_params={k:{a:v[idx] for a,v in self.p.items()} for k,idx in self.policies.items()}
        self.sn,self.drive=q.stresses(self.p)
        self.capacity=np.minimum(self.p['connected_depth_m'],.98*self.sn/q.G)*self.p['storativity']
        self.dt=config['dt_hours'];assert self.dt==1.
        self.bottom=config['thermal_bottom_m'];self.dz=None;self.z=[];self.substeps=None
        self.water_budget_max=0.;self.past_cache={};self.direct_checks=[]
        self.context=None;self.context_air=None;self.cursor=0
        self.kernel=None;self.history_temperature=None;self.history_air=None;self.history_boundary=None
        self.history_increments=None;self.reference_indices=set()
        self.future_causality_error=None

    def set_context(self,temperature,air):
        assert temperature.shape==(len(air)+1,self.nb) or temperature.shape==(len(air),self.nb)
        self.context=temperature;self.context_air=air;self.cursor=0

    def initial(self):
        assert self.context is not None and self.cursor==0
        return self.context[0].copy(),self.p['initial_damage'].copy(),np.zeros(self.n)

    def interface_base(self,profile):return profile

    def thermal_step(self,profile,air):
        assert self.cursor<len(self.context)-1
        assert air==self.context_air[self.cursor],'temperature interval alignment mismatch'
        assert np.max(abs(profile-self.context[self.cursor]))<1e-10
        self.cursor+=1
        return self.context[self.cursor].copy()

    def establish_history(self,air,issues):
        self.history_air=air.copy()
        self.history_temperature,self.history_boundary=self.q.analytic.thermal_transfer_analytic(air,self.bp,self.dt)
        self.history_increments=np.empty_like(self.history_boundary)
        self.history_increments[0]=self.history_boundary[0]-self.bp['initial_temp_c']
        self.history_increments[1:]=np.diff(self.history_boundary,axis=0)
        max_states=max(len(air),max(issues)+73)
        self.kernel=self.q.analytic.step_kernel(max_states,self.bp['interface_depth_m'],self.bp['diffusivity_m2_s'],self.dt)
        self.reference_indices={issues[0],issues[len(issues)//2],issues[-1]}
        self.set_context(self.history_temperature,air)
        # Use the actual complete provider to check FFT future perturbation.
        change=max(1,len(air)-73)
        altered=air.copy();altered[change:]-=10.
        changed,_=self.q.analytic.thermal_transfer_analytic(altered,self.bp,self.dt)
        self.future_causality_error=float(np.max(abs(changed[:change+1]-self.history_temperature[:change+1])))

    def future_temperature(self,j,aa):
        length=len(aa)
        if not length:return self.history_temperature[j:j+1].copy()
        assert j>0
        # Past-only convolution includes increments strictly before issue.
        # The remaining long memory is advanced for all 72 possible hours.
        if j not in self.past_cache:
            nt=j+73;increments=np.zeros((nt,self.nb))
            increments[:j]=self.history_increments[:j]
            response,nfft=self.q.analytic.linear_causal_convolution(increments,self.kernel[:nt])
            assert nfft>=2*nt-1
            self.past_cache[j]=response[j:j+73].copy()
        boundary=np.minimum(aa[:,None]+self.bp['station_source_offset_c'][None,:],0.)
        future_increments=np.zeros((length+1,self.nb))
        future_increments[0]=boundary[0]-self.history_boundary[j-1]
        future_increments[1:length]=np.diff(boundary,axis=0)
        future_response,nfft=self.q.analytic.linear_causal_convolution(future_increments,self.kernel[:length+1])
        assert nfft>=2*(length+1)-1
        temperature=self.bp['initial_temp_c'][None,:]+self.past_cache[j][:length+1]+future_response
        # K0=0. Preserve exactly the common historical state at issue.
        issue_error=float(np.max(abs(temperature[0]-self.history_temperature[j])))
        assert issue_error<1e-10
        temperature[0]=self.history_temperature[j]
        if j in self.reference_indices:
            # Last endpoint does not drive any returned state. This repeated
            # endpoint is an API shape placeholder, not an imputed interval.
            direct_air=np.r_[self.history_air[:j],aa,aa[-1]]
            direct,_=self.q.analytic.thermal_transfer_analytic(direct_air,self.bp,self.dt)
            error=float(np.max(abs(temperature-direct[j:])))
            self.direct_checks.append(dict(history_intervals=j,future_intervals=length,
              direct_provider_maximum_absolute_error_c=error,issue_state_roundoff_c=issue_error,
              concatenated_boundary_sha256=hashlib.sha256(direct_air.tobytes()).hexdigest()))
            assert error<1e-10
        return temperature

def continuous_history(engine,clock,air,rain,issues):
    indices=[clock.index(x) for x in issues]
    engine.establish_history(air,indices)
    history=original_history(engine,clock,air,rain,issues)
    return history

def forecast(engine,history,j,aa,pp):
    engine.set_context(engine.future_temperature(j,aa),aa)
    return original_forecast(engine,history,j,aa,pp)

def version_comparison(pred,bundle_version):
    old=R/'results/mechanistic_replay/v2/predictions.csv.gz'
    prior=pd.read_csv(old)
    keys=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','mechanism_id','law_policy','probability_prior','horizon_hours']
    values=['model_id','probability_start_within_horizon','conditional_lower_hours','conditional_median_hours','conditional_upper_hours',
      'already_started_prior_mass','at_risk_prior_mass','event_prior_mass','unresolved_future_prior_mass']
    assert not prior.duplicated(keys).any() and not pred.duplicated(keys).any()
    assert set(prior.mechanism_id)==set(pred.mechanism_id)
    pair=prior[keys+values].merge(pred[keys+values],on=keys,how='outer',suffixes=('_v2','_analytic'),validate='one_to_one',indicator=True)
    for name in values[1:]:pair[name+'_difference_analytic_minus_v2']=pair[name+'_analytic']-pair[name+'_v2']
    pair['comparison_scope']='same 2048 physical/mechanism/policy rows; linear thermal numerical provider sensitivity; no forecast skill ranking'
    pair['fragile_prior_changes_with_initial_margin']=pair.probability_prior.eq(fd.PRIORS[2])
    fd.csv_out(HERE/'paired_v2_analytic_weather_predictions.csv.gz',pair.to_dict('records'))
    x=pair.probability_start_within_horizon_difference_analytic_minus_v2.dropna()
    t=pair.conditional_median_hours_difference_analytic_minus_v2.dropna()
    grouped=[]
    for key,g in pair.groupby(['mechanism_id','law_policy','probability_prior'],dropna=False):
        p=g.probability_start_within_horizon_difference_analytic_minus_v2.dropna()
        m=g.conditional_median_hours_difference_analytic_minus_v2.dropna()
        grouped.append(dict(mechanism_id=key[0],law_policy=key[1],probability_prior=key[2],matched_rows=len(g),
          identified_probability_pairs=len(p),maximum_absolute_probability_difference=float(p.abs().max()) if len(p) else None,
          changed_probability_rows_above_1e_12=int((p.abs()>1e-12).sum()),conditional_median_pairs=len(m),
          maximum_absolute_conditional_median_difference_hours=float(m.abs().max()) if len(m) else None))
    fd.csv_out(HERE/'paired_v2_analytic_summary.csv',grouped)
    return dict(status='matched_same_full_2048_universe',old_input_path=str(old.relative_to(ROOT)),old_input_sha256=sha(old),
      new_bundle_version=bundle_version,matched_rows=int(pair['_merge'].eq('both').sum()),unmatched_rows=int(pair['_merge'].ne('both').sum()),
      identified_probability_pairs=len(x),maximum_absolute_probability_difference=float(x.abs().max()) if len(x) else None,
      changed_probability_rows_above_1e_12=int((x.abs()>1e-12).sum()),conditional_median_pairs=len(t),
      maximum_absolute_conditional_median_difference_hours=float(t.abs().max()) if len(t) else None,
      interpretation='same issue/mechanism/law/space/latency/prior/horizon; model IDs versioned and paired by mechanism; no empirical accuracy or coverage claim')

engine_holder=[]
class CapturedPhysics(AnalyticPhysics):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);engine_holder.append(self)

def main():
    assert not (HERE/'summary.json').exists(),'completed outputs are immutable; choose a new version directory rather than overwrite'
    fd.BUNDLE=BUNDLE;fd.OUT=HERE;fd.EXPERIMENT=EXPERIMENT
    fd.load_inputs=load_inputs;fd.Physics=CapturedPhysics
    fd.continuous_history=continuous_history;fd.forecast=forecast;fd.version_comparison=version_comparison
    # Source provenance of audit records points to this actual wrapper; the
    # read-only helper source is independently snapshotted and hash-bound.
    fd.__file__=str(Path(__file__))
    fd.run()
    engine=engine_holder[0]
    analytic_checks={'causal_decomposition_matches_actual_provider':bool(engine.direct_checks and all(x['direct_provider_maximum_absolute_error_c']<1e-10 for x in engine.direct_checks)),
      'future_boundary_perturbation_has_no_past_effect_beyond_roundoff':engine.future_causality_error<1e-10,
      'prior_FD_delivery_index_and_every_bound_file_unchanged':sha(FD_INDEX)==FD_INDEX_HASH}
    for item in json.loads(FD_INDEX.read_text())['files']:
        path=ROOT/item['path']
        analytic_checks['prior_FD_delivery_index_and_every_bound_file_unchanged'] &= path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
    record=dict(checks=analytic_checks,passed=all(analytic_checks.values()),direct_provider_comparisons=engine.direct_checks,
      future_perturbation_maximum_preperturbation_temperature_error_c=engine.future_causality_error,
      method='actual delivered erfc kernel and padded linear convolution; past-only plus future-jump decomposition; water/damage warm state retained',
      thermal_memory='full boundary increments from 2026-06-01; interface temperature alone is not a Markov restart state',
      thermal_dt_hours=engine.dt,independent_observed_events=0)
    fd.dump(HERE/'analytic_causality_validation.json',record)
    assert record['passed'],record
    for name in ['summary.json','validation.json']:
        result=json.loads((HERE/name).read_text())
        result['checks'].update(analytic_checks);result['passed']=all(result['checks'].values())
        result['analytic_causality_validation']=record
        if name=='summary.json':
            result['thermal_provider']=dict(solver_id='analytic_halfspace_erfc_linear_causal_fft_v1',spatial_grid=None,
              state_dt_hours=engine.dt,history_memory='full causal boundary increments',finite_bottom_comparator_m=engine.bottom,
              scope='linear constant diffusivity half-space with hourly step boundary; mechanical/water/damage still hourly discrete')
            result.pop('thermal_discretization',None)
            result['paired_thermal_provider_comparison']=result.pop('paired_grid_version_comparison')
            result['limitations'].extend(['Analytic thermal is a numerical reference only for the registered linear half-space model, not an exact coupled system or measured source state',
              'Prior FD differences are retained; the Q2 historical fine-FD comparison is not a bound or confidence interval for future forecasts'])
            result['actual_command']='track_b/.venv/bin/python '+str(Path(__file__).relative_to(ROOT))
        fd.dump(HERE/name,result)
    fd.event_support_diagnostics(HERE)
    fd.audit_exports(HERE)
    summary=json.loads((HERE/'summary.json').read_text())
    support=json.loads((HERE/'event_support_summary.json').read_text())
    summary['event_support_diagnostics']=support
    fd.dump(HERE/'summary.json',summary)
    output_files=[p for p in HERE.rglob('*') if p.is_file() and p.name not in ['delivery_index.json','run.stdout.log']]
    index=dict(experiment_id=EXPERIMENT,generated_at_utc=fd.stamp(datetime.now(timezone.utc)),
      upstream_bundle_sha256=BUNDLE_HASH,prior_FD_delivery_index_sha256=FD_INDEX_HASH,
      files=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(output_files)])
    fd.dump(HERE/'delivery_index.json',index)
    print(json.dumps(dict(status='completed',summary_sha256=sha(HERE/'summary.json'),predictions_sha256=sha(HERE/'predictions.csv.gz'),
      delivery_index_sha256=sha(HERE/'delivery_index.json'),event_support_summary=support),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
