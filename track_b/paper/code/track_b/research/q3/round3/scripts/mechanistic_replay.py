#!/usr/bin/env python3
"""Warm-restart the delivered Q2 physics under per-issue actual GFS scenarios.

No local truth or historical public-availability claim. See the preregistration.
Only existing NumPy/pandas/pyarrow are used; no networking or installations.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, types, warnings
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

warnings.filterwarnings('ignore',message="The 'generic' unit for NumPy timedelta is deprecated",category=DeprecationWarning)
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]
OUT=R/'results/mechanistic_replay'
BUNDLE=R/'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1/bundle.json'
EXPERIMENT='q3r3-full-mechanistic-weather-replay-v1'
PRIORS=['uniform_design_assumption','equal_mechanism_then_design_assumption','fragile_issue_initial_margin_assumption']
HORIZONS=[24,48,72]
START=datetime(2026,8,23,tzinfo=timezone.utc);END=datetime(2026,8,26,2,tzinfo=timezone.utc)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp(t):return t.isoformat().replace('+00:00','Z')
def dt(s):return datetime.fromisoformat(str(s).replace('Z','+00:00'))
def num(s):return float(s) if s not in ['',None] else np.nan
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):x=x.item()
    if isinstance(x,float) and not np.isfinite(x):return None
    return x
def dump(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(obj),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def csv_read(p):return list(csv.DictReader(p.open()))
def csv_out(p,rows):
    frame=pd.DataFrame(rows)
    if p.suffix=='.gz':frame.to_csv(p,index=False,compression={'method':'gzip','mtime':0})
    else:frame.to_csv(p,index=False)

def load_inputs(mechanisms=None):
    assert ROOT==Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3')
    assert (R/'MECHANISTIC_REPLAY.md').exists(),'preregister before computing'
    b=json.loads(BUNDLE.read_text());files={}
    for item in b['files']:
        p=ROOT/item['path']
        assert p.is_relative_to(R/'inputs') and p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
        files[item['role']]=p
    aliases={
      'scripts/mechanism_engine.py':['frozen_local_mechanism_engine'],
      'config/experiment_v1.json':['config.json'],
      'results/parameter_ensemble.csv':['parameter_ensemble.csv'],
      'results/forcing_hourly_v1.csv':['forcing_hourly_v2.csv'],
      'results/scenario_outcomes.csv':['scenario_outcomes.csv'],
      'results/state_trajectories.parquet':['state_trajectories.parquet']}
    for canonical,alternatives in aliases.items():
        if canonical not in files:
            available=[files[k] for k in alternatives if k in files]
            assert len(available)==1,f'No unambiguous delivered role for {canonical}'
            files[canonical]=available[0]
    # Execute read-only source without generating __pycache__ in delivered input.
    module=types.ModuleType('q2_delivered_physics')
    exec(compile(files['scripts/mechanism_engine.py'].read_text(),str(files['scripts/mechanism_engine.py']),'exec'),module.__dict__)
    ensemble=pd.read_csv(files['results/parameter_ensemble.csv'])
    forcing=pd.read_csv(files['results/forcing_hourly_v1.csv'])
    config=json.loads(files['config/experiment_v1.json'].read_text())
    assert len(ensemble)==2048 and ensemble.scenario_id.is_unique
    if 'base_scenario_id' not in ensemble:ensemble['base_scenario_id']=ensemble.scenario_id
    if mechanisms:
        ensemble=ensemble[ensemble.mechanism_id.isin(mechanisms)].reset_index(drop=True)
        assert len(ensemble)>0 and set(ensemble.mechanism_id)==set(mechanisms)
    assert len(forcing)==2089
    clock=[dt(x) for x in forcing.time_utc]
    assert all((y-x)==timedelta(hours=1) for x,y in zip(clock[:-1],clock[1:]))
    air=forcing.station_air_temp_c.to_numpy(float);rain=forcing.precip_assumed_mm_h.to_numpy(float)
    assert np.isfinite(air).all() and np.isfinite(rain).all() and (rain>=0).all()
    # Preserve exact executed code and the preregistration used by this output
    # version. Later documentation additions cannot rewrite that input history.
    sources=OUT/'execution_source';sources.mkdir(parents=True,exist_ok=True)
    raw=Path(__file__).read_bytes()
    code_snapshot=sources/f'mechanistic_replay_{hashlib.sha256(raw).hexdigest()}.py.txt'
    if code_snapshot.exists():assert code_snapshot.read_bytes()==raw
    else:code_snapshot.write_bytes(raw)
    registration=sources/f"registered_protocol_{sha(R/'MECHANISTIC_REPLAY.md')}.md"
    if not registration.exists():registration.write_bytes((R/'MECHANISTIC_REPLAY.md').read_bytes())
    for p in [R/'inputs/weather/gfs_hourly_summary.csv',registration,code_snapshot,BUNDLE]:
        files['consumer:'+str(p.relative_to(R))]=p
    return module,b,files,ensemble,forcing,config,clock,air,rain

class Physics:
    """Exact Q2 update equations with complete restart state, not a new model."""
    def __init__(self,q,ensemble,config):
        self.q=q;self.f=ensemble;self.n=len(ensemble)
        self.names=list(config['ranges'])+['density_kg_m3']
        self.p={k:ensemble[k].to_numpy(float) for k in self.names}
        bases=ensemble.drop_duplicates('parameter_set_id').sort_values('parameter_set_id')
        self.baseids=list(bases.parameter_set_id);self.nb=len(bases)
        self.bp={k:bases[k].to_numpy(float) for k in self.names}
        self.baseindex=np.array([self.baseids.index(x) for x in ensemble.parameter_set_id])
        # Physical parameters must agree for every mechanism/policy clone.
        assert self.nb==256 and all(np.array_equal(self.p[k],self.bp[k][self.baseindex]) for k in self.names)
        self.has_t=ensemble.mechanism_id.isin(['S_T','S_T_H']).to_numpy()
        self.has_h=ensemble.mechanism_id.isin(['S_H','S_T_H']).to_numpy()
        self.policies={k:np.flatnonzero(ensemble.law_policy.eq(k)) for k in ['linear_extension','thawed_rock_contact']}
        self.policy_params={k:{a:v[idx] for a,v in self.p.items()} for k,idx in self.policies.items()}
        self.sn,self.drive=q.stresses(self.p)
        self.capacity=np.minimum(self.p['connected_depth_m'],.98*self.sn/q.G)*self.p['storativity']
        self.dz=config['dz_m'];self.bottom=config['thermal_bottom_m'];self.dt=config['dt_hours']
        assert self.dt==1.
        self.z=np.arange(0,self.bottom+self.dz*.5,self.dz)
        ratio=self.bp['diffusivity_m2_s']*self.dt*3600/self.dz**2
        self.substeps=max(1,int(np.ceil(ratio.max()/.45)));self.rr=ratio[:,None]/self.substeps
        self.k=np.floor(self.bp['interface_depth_m']/self.dz).astype(int)
        self.frac=self.bp['interface_depth_m']/self.dz-self.k;self.row=np.arange(self.nb)
        assert self.bp['interface_depth_m'].max()<self.bottom
        self.water_budget_max=0.

    def initial(self):
        return np.repeat(self.bp['initial_temp_c'][:,None],len(self.z),axis=1),self.p['initial_damage'].copy(),np.zeros(self.n)

    def thermal_step(self,profile,air):
        profile=profile.copy()
        surf=np.minimum(air+self.bp['station_source_offset_c'],0.)
        for _ in range(self.substeps):
            old=profile.copy();old[:,0]=surf
            profile[:,1:-1]=old[:,1:-1]+self.rr*(old[:,2:]-2*old[:,1:-1]+old[:,:-2])
            profile[:,-1]=old[:,-1]+2*self.rr[:,0]*(old[:,-2]-old[:,-1])
            profile[:,0]=surf
        return profile

    def interface_base(self,profile):
        return profile[self.row,self.k]*(1-self.frac)+profile[self.row,self.k+1]*self.frac

    def observe(self,profile,damage,storage):
        ib=self.interface_base(profile)
        ti=np.where(self.has_t,ib[self.baseindex],self.p['initial_temp_c'])
        pressure=np.where(self.has_h,self.q.G*storage/self.p['storativity'],0.)
        margin=np.empty(self.n);resist=np.empty(self.n);domain=np.empty(self.n,bool)
        for policy,idx in self.policies.items():
            out=self.q.resistance(self.policy_params[policy],damage[idx],ti[idx],pressure[idx],policy)
            margin[idx]=out['failure_margin'];resist[idx]=out['resistance_kpa'];domain[idx]=out['strength_domain']
        return margin,resist,domain,ti,pressure

    def advance(self,profile,damage,storage,air,rain,resist):
        assert np.isfinite(air) and np.isfinite(rain) and rain>=0
        ratio=self.drive/np.maximum(resist,1e-6)
        rate=self.p['damage_rate_h_inv']*np.minimum(ratio,10.)**self.p['damage_exponent']
        damage_next=np.minimum(1-(1-damage)*np.exp(-rate*self.dt),.999999)
        source_air=air+self.p['station_source_offset_c']
        rain_fraction=np.clip((source_air+1)/2,0,1)
        incoming=self.p['rain_multiplier']*rain/1000*rain_fraction+self.p['melt_mm_deg_day']*np.maximum(source_air,0)/24000
        incoming=np.where(self.has_h,incoming,0.)
        tau=self.p['drainage_hours']*np.exp(-self.p['drainage_damage_coupling']*damage)
        storage_next,drain,over=self.q.reservoir_step(storage,incoming,tau,self.capacity,self.dt)
        self.water_budget_max=max(self.water_budget_max,float(np.max(np.abs(storage+incoming*self.dt-storage_next-drain-over))))
        return self.thermal_step(profile,air),damage_next,storage_next

def continuous_history(engine,clock,air,rain,issues):
    nt=len(clock);n=engine.n
    margins=np.empty((nt,n));damage_hist=np.empty((nt,n));storage_hist=np.empty((nt,n));ibase=np.empty((nt,engine.nb))
    first=np.full(n,np.nan);left=np.zeros(n,bool);minmargin=np.full(n,np.inf);peakp=np.zeros(n)
    prof,dmg,store=engine.initial();snapshots={}
    ix={x:i for i,x in enumerate(clock)};issue_idx=[ix[x] for x in issues]
    wanted=set(issue_idx+[min(i+72,nt-1) for i in issue_idx])
    initial_m=None;previous=None
    for j in range(nt):
        margin,resist,domain,ti,pressure=engine.observe(prof,dmg,store)
        margins[j]=margin;damage_hist[j]=dmg;storage_hist[j]=store;ibase[j]=engine.interface_base(prof)
        minmargin=np.minimum(minmargin,margin);peakp=np.maximum(peakp,pressure)
        if j==0:
            initial_m=margin.copy();left=margin<=0;first[left]=0
        else:
            hit=np.isnan(first)&(margin<=0)
            first[hit]=(j-1)+previous[hit]/(previous[hit]-margin[hit])
        if j in wanted:snapshots[j]=prof.copy()
        if j<nt-1:prof,dmg,store=engine.advance(prof,dmg,store,air[j],rain[j],resist)
        previous=margin
    return dict(margin=margins,damage=damage_hist,storage=storage_hist,interface_base=ibase,profiles=snapshots,
      first_elapsed=first,left=left,initial_margin=initial_m,min_margin=minmargin,peak_pressure=peakp,issue_indices=issue_idx,clock_index=ix)

def history_validation(history,engine,ensemble,files):
    q2=pd.read_csv(files['results/scenario_outcomes.csv']).set_index('scenario_id').loc[ensemble.scenario_id]
    expected_status=np.where(history['left'],'left_censored_already_unstable',np.where(np.isfinite(history['first_elapsed']),'interval_crossing','never_crossed'))
    diffs={
      'final_margin':float(np.max(abs(history['margin'][-1]-q2.final_margin.to_numpy(float)))),
      'minimum_margin':float(np.max(abs(history['min_margin']-q2.min_margin_all.to_numpy(float)))),
      'final_damage':float(np.max(abs(history['damage'][-1]-q2.final_damage.to_numpy(float)))),
      'peak_pressure':float(np.max(abs(history['peak_pressure']-q2.peak_pressure_kpa.to_numpy(float))))}
    finalti=np.where(engine.has_t,history['interface_base'][-1,engine.baseindex],engine.p['initial_temp_c'])
    diffs['final_interface_temperature']=float(np.max(abs(finalti-q2.final_interface_temp_c.to_numpy(float))))
    target=q2.onset_elapsed_hours.to_numpy(float);mask=np.isfinite(target)
    diffs['onset_elapsed_hours']=float(np.max(abs(history['first_elapsed'][mask]-target[mask]))) if mask.any() else 0.
    statuses_match=np.array_equal(expected_status,q2.onset_status.to_numpy())
    representative=pd.read_parquet(files['results/state_trajectories.parquet'])
    representative=representative[representative.scenario_id.isin(ensemble.scenario_id)].copy()
    lookup={s:i for i,s in enumerate(ensemble.scenario_id)}
    columns={'failure_margin':'margin','damage':'damage','storage_m':'storage'}
    repdiff={}
    ti=pd.to_datetime(representative.time_utc,utc=True)
    origin=pd.Timestamp('2026-06-01T00:00Z')
    rows=np.rint((ti-origin).dt.total_seconds().to_numpy()/3600).astype(int)
    cols=np.array([lookup[s] for s in representative.scenario_id])
    for raw,key in columns.items():
        if raw in representative:repdiff[raw]=float(np.max(abs(history[key][rows,cols]-representative[raw].to_numpy(float))))
    if 'interface_temp_c' in representative:
        a=np.where(engine.has_t[cols],history['interface_base'][rows,engine.baseindex[cols]],engine.p['initial_temp_c'][cols])
        repdiff['interface_temp_c']=float(np.max(abs(a-representative.interface_temp_c.to_numpy(float))))
    if 'pressure_kpa' in representative:
        a=np.where(engine.has_h[cols],engine.q.G*history['storage'][rows,cols]/engine.p['storativity'][cols],0)
        repdiff['pressure_kpa']=float(np.max(abs(a-representative.pressure_kpa.to_numpy(float))))
    result=dict(full_design_rows=len(q2),status_match=statuses_match,maximum_absolute_differences=diffs,
      representative_rows=len(representative),representative_scenarios=int(representative.scenario_id.nunique()),representative_maximum_absolute_differences=repdiff,
      passed=statuses_match and all(v<1e-8 for v in [*diffs.values(),*repdiff.values()]))
    if not result['passed']:raise AssertionError(result)
    return result

def weather_lookup():
    rows=csv_read(R/'inputs/weather/gfs_hourly_summary.csv');lookup={};refs={}
    for row in rows:
        space=row['space_object'];ref=dt(row['forecast_reference_time']);valid=dt(row['valid_time'])
        lookup[(space,ref,valid)]=row;refs.setdefault(space,set()).add(ref)
    return lookup,{k:sorted(v) for k,v in refs.items()}

def get_forcing(mode,space,latency,issue,j,air,rain,clock,weather,refs):
    if mode=='historically_available':return np.array([]),np.array([]),None,'rejected_historical_first_availability_unknown'
    if mode=='ideal_weather':
        length=min(72,len(clock)-1-j)
        return air[j:j+length],rain[j:j+length],None,'complete_72h' if length==72 else 'right_censored_at_original_forcing_end'
    eligible=[r for r in refs[space] if r+timedelta(hours=latency)<=issue]
    if not eligible:return np.array([]),np.array([]),None,'rejected_no_eligible_acquired_initialization'
    ref=max(eligible);aa=[];pp=[];reason='complete_72h'
    for s in range(72):
        start=issue+timedelta(hours=s);end=start+timedelta(hours=1)
        trow=weather.get((space,ref,start));prow=weather.get((space,ref,end))
        if trow is None or prow is None:
            reason='right_censored_at_GFS_forecast_tail';break
        av=num(trow['temperature_2m_C']);pv=num(prow['precipitation_increment_mm'])
        valid_boundary=bool(prow['precipitation_interval_start'] and prow['precipitation_interval_end'] and
            dt(prow['precipitation_interval_start'])==start and dt(prow['precipitation_interval_end'])==end)
        if not (np.isfinite(av) and np.isfinite(pv) and pv>=0 and valid_boundary):
            reason='missing_or_invalid_future_forcing_interval';break
        aa.append(av);pp.append(pv)
    return np.array(aa),np.array(pp),ref,reason

def forecast(engine,history,j,aa,pp):
    length=len(aa);prof=history['profiles'][j].copy();dmg=history['damage'][j].copy();storage=history['storage'][j].copy()
    margins=np.empty((length+1,engine.n));domain=np.empty((length+1,engine.n),bool)
    pressure_max=np.zeros(engine.n);ti_start=None
    for k in range(length+1):
        margin,resist,flag,ti,pressure=engine.observe(prof,dmg,storage)
        margins[k]=margin;domain[k]=flag;pressure_max=np.maximum(pressure_max,pressure)
        if k==0:ti_start=ti.copy()
        if k<length:prof,dmg,storage=engine.advance(prof,dmg,storage,aa[k],pp[k],resist)
    past=np.isfinite(history['first_elapsed'])&(history['first_elapsed']<=j)
    known_at_risk=~past
    point=np.full(engine.n,np.nan);lower=np.full(engine.n,np.nan);upper=np.full(engine.n,np.nan)
    found=(margins<=0).any(axis=0)&known_at_risk
    hit=np.argmax(margins<=0,axis=0)
    for k in np.unique(hit[found]):
        assert k>0,'at-risk scenario cannot start forecast already unstable'
        ix=found&(hit==k);lower[ix]=k-1;upper[ix]=k
        point[ix]=(k-1)+margins[k-1,ix]/(margins[k-1,ix]-margins[k,ix])
    return dict(margin=margins,domain_fraction=domain.mean(axis=0),point=point,lower=lower,upper=upper,
      past=past,at_risk=known_at_risk,followup=length,final_margin=margins[-1],max_pressure=pressure_max,
      thermal_change=ti-ti_start,profile_final=prof,damage_final=dmg,storage_final=storage)

def assumed_weights(frame,initial_margin,scheme):
    if scheme==PRIORS[0]:w=np.ones(len(frame))
    elif scheme==PRIORS[1]:
        counts=frame.groupby('mechanism_id',dropna=False).mechanism_id.transform('size').to_numpy(float);w=1/counts
    elif scheme==PRIORS[2]:w=np.exp(-np.clip(initial_margin,0,10))
    else:raise ValueError(scheme)
    assert np.isfinite(w).all() and (w>0).all()
    return w/w.sum()

def distribution(frame,result,initial_margin,indices,H,scheme):
    part=frame.iloc[indices];w=assumed_weights(part,initial_margin[indices],scheme)
    risk=result['at_risk'][indices];point=result['point'][indices];length=result['followup']
    event=risk&np.isfinite(point)&(point<=H)
    no=risk&((np.isfinite(point)&(point>H)) | (~np.isfinite(point)&(length>=H)))
    unknown=risk&~(event|no)
    rm=float(w[risk].sum());em=float(w[event].sum());nm=float(w[no].sum());um=float(w[unknown].sum())
    lower=em/rm if rm>0 else None;upper=(em+um)/rm if rm>0 else None
    p=lower if rm>0 and um<1e-12 else None
    qs=[None,None,None]
    if p is not None and p>0:
        vals=point[event];ww=w[event];order=np.argsort(vals);vals=vals[order];ww=ww[order];cw=np.cumsum(ww)/ww.sum()
        qs=[float(vals[min(int(np.searchsorted(cw,q,side='left')),len(vals)-1)]) for q in [.025,.5,.975]]
    return dict(probability_start_within_horizon=p,probability_no_start_within_horizon=1-p if p is not None else None,
        probability_start_lower=lower,probability_start_upper=upper,probability_no_start_lower=1-upper if upper is not None else None,
        probability_no_start_upper=1-lower if lower is not None else None,
        conditional_lower_hours=qs[0],conditional_median_hours=qs[1],conditional_upper_hours=qs[2],conditional_interval_level=.95,
        conditional_interval_interpretation='assumed_prior; given_start_within_horizon_and_retrospective_at_risk',
        already_started_prior_mass=float(w[~risk].sum()),at_risk_prior_mass=rm,event_prior_mass=em,no_start_prior_mass=nm,
        unresolved_future_prior_mass=um,scenario_count=len(indices),at_risk_scenarios=int(risk.sum()),
        observed_event_scenarios=int(event.sum()),known_no_start_scenarios=int(no.sum()),right_censored_or_unknown_scenarios=int(unknown.sum()),
        probability_prior=scheme,prior_is_analyst_assumption=True,design_is_probability_prior=False,
        strength_domain_fraction=float(result['domain_fraction'][indices].mean()))

PARQUET_FIELDS=[
 ('issue_time',pa.string()),('forecast_input_mode',pa.string()),('space_object',pa.string()),('assumed_latency_hours',pa.float64()),
 ('forecast_reference_time',pa.string()),('assumed_available_time',pa.string()),('available_time',pa.string()),
 ('scenario_id',pa.string()),('base_scenario_id',pa.string()),('parameter_set_id',pa.string()),('model_id',pa.string()),('mechanism_id',pa.string()),
 ('law_policy',pa.string()),('geometry_version',pa.string()),('parameter_version',pa.string()),
 ('history_status',pa.string()),('forecast_status',pa.string()),('known_at_risk_under_conditional_history',pa.bool_()),
 ('initial_margin_at_issue',pa.float64()),('historical_first_cross_elapsed_hours',pa.float64()),
 ('crossing_lower_hours_after_issue',pa.float64()),('crossing_upper_hours_after_issue',pa.float64()),('crossing_point_hours_after_issue',pa.float64()),
 ('followup_hours',pa.int32()),('forcing_status',pa.string()),('final_margin',pa.float64()),
 ('future_interface_temperature_change_c',pa.float64()),('max_observed_pressure_kpa',pa.float64()),
 ('strength_domain_fraction_observed',pa.float64()),('evaluation_stratum',pa.string())]

def write_parameter_run(writer,frame,result,initial_margin,history,common):
    n=len(frame);length=result['followup'];past=result['past'];point=result['point']
    status=np.full(n,'no_cross_within_complete_72h',dtype=object)
    if length<72:status[:]='right_censored_or_unknown_future'
    if common['forcing_status'].startswith('rejected'):status[:]=common['forcing_status']
    status[np.isfinite(point)]='point_first_crossing_between_samples'
    status[past]='already_started_by_retrospective_history'
    hist_status=np.where(history['left'],'initial_history_left_censored',np.where(past,'first_crossed_before_or_at_issue','no_prior_cross_in_conditional_history'))
    data={k:frame[k].tolist() for k in ['scenario_id','base_scenario_id','parameter_set_id','model_id','mechanism_id','law_policy','geometry_version','parameter_version']}
    for k in ['issue_time','forecast_input_mode','space_object','assumed_latency_hours','forecast_reference_time','assumed_available_time','available_time','forcing_status']:
        data[k]=[common[k]]*n
    data.update(history_status=hist_status,forecast_status=status,known_at_risk_under_conditional_history=result['at_risk'],
      initial_margin_at_issue=initial_margin,historical_first_cross_elapsed_hours=np.where(past&~history['left'],history['first_elapsed'],np.nan),
      crossing_lower_hours_after_issue=result['lower'],crossing_upper_hours_after_issue=result['upper'],crossing_point_hours_after_issue=point,
      followup_hours=np.full(n,length),final_margin=result['final_margin'],future_interface_temperature_change_c=result['thermal_change'],
      max_observed_pressure_kpa=result['max_pressure'],strength_domain_fraction_observed=result['domain_fraction'],evaluation_stratum=['conditional_scenario']*n)
    table=pa.Table.from_arrays([pa.array(data[k],type=t,from_pandas=True) for k,t in PARQUET_FIELDS],schema=pa.schema(PARQUET_FIELDS))
    writer.write_table(table)
    return Counter(status)

def redact_history_metadata(directory):
    """Remove future oracle times from an earlier audit export, not predictions.

    The original forecast uses only first_elapsed<=issue; this corrects a
    metadata column which otherwise disclosed full-forcing future audit times.
    """
    directory=directory.resolve();assert directory.is_relative_to(R/'results/mechanistic_replay')
    summary=json.loads((directory/'summary.json').read_text())
    origin=pd.Timestamp(summary.get('history_time_origin_utc','2026-06-01T00:00:00Z'))
    outcome_inputs=[ROOT/x['path'] for x in summary['inputs'] if Path(x['path']).name=='scenario_outcomes.csv']
    assert len(outcome_inputs)==1
    left_ids={x['scenario_id'] for x in csv_read(outcome_inputs[0]) if x['onset_status']=='left_censored_already_unstable'}
    records=[]
    for name in ['parameter_first_passages.parquet','history_states_at_issue.parquet']:
        path=directory/name;original_sha=sha(path);reader=pq.ParquetFile(path)
        column='historical_first_cross_elapsed_hours'
        tmp=directory/(name+'.causal.tmp');count=0;left_count=0
        with pq.ParquetWriter(tmp,reader.schema_arrow,compression='zstd',use_dictionary=True) as writer:
            for batch in reader.iter_batches(batch_size=65536):
                table=pa.Table.from_batches([batch]);values=table[column].to_numpy(zero_copy_only=False)
                issue=pd.to_datetime(table['issue_time'].to_pylist(),utc=True)
                elapsed=np.asarray((issue-origin).total_seconds()/3600)
                bad=np.isfinite(values)&(values>elapsed+1e-12);count+=int(bad.sum())
                is_left=np.isin(np.array(table['scenario_id'].to_pylist()),list(left_ids))
                left_bad=is_left&np.isfinite(values);left_count+=int(left_bad.sum())
                values=values.copy();values[bad|is_left]=np.nan
                idx=table.schema.get_field_index(column)
                table=table.set_column(idx,table.schema.field(idx),pa.array(values,type=pa.float64(),from_pandas=True))
                writer.write_table(table)
        tmp.replace(path)
        records.append(dict(path=str(path.relative_to(ROOT)),future_oracle_values_redacted=count,
            left_censored_pseudo_point_values_redacted=left_count,
            original_sha256=original_sha,sha256=sha(path),bytes=path.stat().st_size))
    source=directory/'execution_source'/f'metadata_redaction_{sha(Path(__file__))}.py.txt'
    if not source.exists():source.write_bytes(Path(__file__).read_bytes())
    rec=dict(method='null any first-cross audit time later than issue or left-censored initial pseudo-point; forecast math and ensemble predictions unchanged',
        physics_predictions_changed=False,files=records,source_path=str(source.relative_to(ROOT)),source_sha256=sha(source))
    summary['history_metadata_redaction']=rec;summary['checks']['history_metadata_export_contains_no_future_oracle_onset']=True
    summary['inputs'].append(dict(path=str(source.relative_to(ROOT)),bytes=source.stat().st_size,sha256=sha(source)))
    summary['passed']=all(summary['checks'].values());dump(directory/'summary.json',summary)
    validation=json.loads((directory/'validation.json').read_text())
    validation['checks']['history_metadata_export_contains_no_future_oracle_onset']=True
    validation['history_metadata_redaction']=rec;validation['passed']=all(validation['checks'].values());dump(directory/'validation.json',validation)
    dump(directory/'causal_metadata_redaction.json',rec);print(json.dumps(rec),flush=True)

def event_support_diagnostics(directory):
    """Count physical-design and time-point support, not repeated scenarios."""
    directory=directory.resolve();assert directory.is_relative_to(R/'results/mechanistic_replay')
    file=directory/'parameter_first_passages.parquet'
    columns=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','scenario_id','parameter_set_id',
        'model_id','mechanism_id','law_policy','initial_margin_at_issue','crossing_point_hours_after_issue']
    events={};resolved_rows=0
    def runkey(x):
        value=x['assumed_latency_hours'];lat=float(value) if value not in ['',None] and pd.notna(value) else None
        return x['issue_time'],x['forecast_input_mode'],x['space_object'],lat
    for batch in pq.ParquetFile(file).iter_batches(batch_size=65536,columns=columns):
        table=pa.Table.from_batches([batch]);point=table['crossing_point_hours_after_issue'].to_numpy(zero_copy_only=False)
        mask=np.isfinite(point)&(point>0)
        if mask.any():
            for item in table.filter(pa.array(mask)).to_pylist():events.setdefault(runkey(item),[]).append(item);resolved_rows+=1
    def ess(items,key,fragile=False):
        weights={}
        for item in items:
            value=np.exp(-np.clip(item['initial_margin_at_issue'],0,10)) if fragile else 1.
            ident=item['parameter_set_id'] if key=='design' else round(item['crossing_point_hours_after_issue'],9)
            weights[ident]=weights.get(ident,0.)+float(value)
        w=np.array(list(weights.values()))
        return float(w.sum()**2/np.square(w).sum()) if len(w) else None
    rows=[];support_all=set();count_checks=[]
    with gzip.open(directory/'predictions.csv.gz','rt') as source:
      for item in csv.DictReader(source):
        if item['probability_prior']!=PRIORS[0]:continue
        H=int(item['horizon_hours']);hit=events.get(runkey(item),[])
        if item['model_id']!='mechanism_policy_mixture':
            hit=[x for x in hit if x['model_id']==item['model_id'] and x['law_policy']==item['law_policy']]
        hit=[x for x in hit if x['crossing_point_hours_after_issue']<=H]
        identifiers=sorted({x['parameter_set_id'] for x in hit});support_all.update(identifiers)
        times={round(x['crossing_point_hours_after_issue'],9) for x in hit}
        count_checks.append(len(hit)==int(item['observed_event_scenarios']))
        if len(identifiers)==1:status='degenerate_discrete_support_not_empirical_uncertainty'
        elif len(identifiers)==0:status='no_resolved_event_support'
        else:status='finite_design_support_not_empirical_uncertainty'
        lo=num(item['conditional_lower_hours']);hi=num(item['conditional_upper_hours'])
        rows.append({k:item[k] for k in ['issue_time','forecast_input_mode','space_object','assumed_latency_hours','model_id','mechanism_id','law_policy','horizon_hours']}|
          dict(event_scenario_rows=len(hit),distinct_parameter_set_ids=len(identifiers),support_parameter_ids=';'.join(identifiers),
            distinct_probability_time_support_points=len(times),effective_design_support_uniform=ess(hit,'design'),
            effective_design_support_equal_mechanism=ess(hit,'design'),effective_design_support_fragile=ess(hit,'design',True),
            effective_time_support_uniform=ess(hit,'time'),effective_time_support_fragile=ess(hit,'time',True),
            unresolved_future_prior_mass=num(item['unresolved_future_prior_mass']),
            conditional_interval_computed=bool(item['conditional_median_hours']),
            conditional_interval_width_hours=hi-lo if np.isfinite(hi) and np.isfinite(lo) else None,
            support_status=status,independent_observed_event_count=0))
    assert all(count_checks),'Event support does not match generated forecast event counts'
    output=directory/'event_support_diagnostics.csv';csv_out(output,rows)
    counter=Counter(x['support_status'] for x in rows)
    complete=[x for x in rows if x['conditional_interval_computed']]
    summary=dict(diagnostic_rows=len(rows),resolved_parameter_event_rows_read=resolved_rows,
      distinct_support_parameter_ids=sorted(support_all),status_counts=dict(counter),
      nominal_conditional_interval_rows_uniform_prior=len(complete),
      nominal_intervals_with_one_physical_design=sum(x['distinct_parameter_set_ids']==1 for x in complete),
      maximum_conditional_interval_width_hours=max((x['conditional_interval_width_hours'] for x in complete),default=None),
      event_counts_match_prediction_rows=all(count_checks),independent_observed_events=0,
      explanation='ESS aggregates duplicated law/model scenario weights by physical parameter_set_id or time point. One design/point is discrete degeneracy, not precise empirical uncertainty; equal-mechanism equals uniform here only because delivered design is balanced.',
      inputs=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size) for p in [file,directory/'predictions.csv.gz']],
      output=dict(path=str(output.relative_to(ROOT)),sha256=sha(output),bytes=output.stat().st_size))
    dump(directory/'event_support_summary.json',summary)
    print(json.dumps(summary),flush=True)

def audit_exports(directory):
    directory=directory.resolve();assert directory.is_relative_to(R/'results/mechanistic_replay')
    summary=json.loads((directory/'summary.json').read_text());origin=pd.Timestamp(summary.get('history_time_origin_utc','2026-06-01T00:00:00Z'))
    totals=Counter()
    cols=['issue_time','historical_first_cross_elapsed_hours','history_status','known_at_risk_under_conditional_history',
          'initial_margin_at_issue','crossing_point_hours_after_issue','followup_hours']
    p=directory/'parameter_first_passages.parquet'
    for batch in pq.ParquetFile(p).iter_batches(batch_size=65536,columns=cols):
        x=pa.Table.from_batches([batch]);t=pd.to_datetime(x['issue_time'].to_pylist(),utc=True)
        elapsed=np.asarray((t-origin).total_seconds()/3600);past=x['historical_first_cross_elapsed_hours'].to_numpy(zero_copy_only=False)
        point=x['crossing_point_hours_after_issue'].to_numpy(zero_copy_only=False)
        left=np.array(x['history_status'].to_pylist())=='initial_history_left_censored'
        risk=x['known_at_risk_under_conditional_history'].to_numpy(zero_copy_only=False)
        margin=x['initial_margin_at_issue'].to_numpy(zero_copy_only=False);follow=x['followup_hours'].to_numpy(zero_copy_only=False)
        totals['rows']+=len(x);totals['future_history_time_violations']+=int(np.sum(np.isfinite(past)&(past>elapsed+1e-12)))
        totals['left_censored_exact_pseudo_time_violations']+=int(np.sum(left&np.isfinite(past)))
        totals['already_started_future_point_violations']+=int(np.sum(~risk&np.isfinite(point)))
        totals['at_risk_nonpositive_initial_margin']+=int(np.sum(risk&(margin<=0)))
        totals['crossing_outside_followup']+=int(np.sum(np.isfinite(point)&((point<=0)|(point>follow))))
    retained=all((ROOT/x['path']).stat().st_size==x['bytes'] and sha(ROOT/x['path'])==x['sha256'] for x in summary['inputs'])
    checks={'exported_parameter_rows_complete':totals['rows']==summary['parameter_prediction_rows'],
        'no_future_history_oracle_time_exported':totals['future_history_time_violations']==0,
        'no_precise_historical_time_assigned_to_initial_left_censor':totals['left_censored_exact_pseudo_time_violations']==0,
        'past_started_scenarios_have_no_future_first_cross':totals['already_started_future_point_violations']==0,
        'at_risk_initial_state_stable':totals['at_risk_nonpositive_initial_margin']==0,
        'future_crossing_inside_actual_followup':totals['crossing_outside_followup']==0,
        'recorded_runtime_input_hashes_retained':retained}
    result=dict(checks=checks,passed=all(checks.values()),counts=dict(totals),
        file_path=str(p.relative_to(ROOT)),file_sha256=sha(p),independent_observed_events=0,
        executed_source_sha256=sha(Path(__file__)))
    dump(directory/'postprocess_audit.json',result)
    if not result['passed']:raise AssertionError(result)
    print(json.dumps(result),flush=True)

def version_comparison(pred,bundle_version):
    old_path=R/'results/mechanistic_replay/predictions.csv.gz'
    if OUT==old_path.parent or not old_path.exists():return None
    prior=pd.read_csv(old_path)
    old_universe=set(prior.loc[prior.model_id.ne('mechanism_policy_mixture'),'mechanism_id'])
    new_universe=set(pred.loc[pred.model_id.ne('mechanism_policy_mixture'),'mechanism_id'])
    if old_universe!=new_universe:
        return dict(status='not_comparable_different_mechanism_universes',old_universe=sorted(old_universe),new_universe=sorted(new_universe))
    keys=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','mechanism_id','law_policy','probability_prior','horizon_hours']
    values=['model_id','probability_start_within_horizon','conditional_lower_hours','conditional_median_hours','conditional_upper_hours',
            'already_started_prior_mass','at_risk_prior_mass','event_prior_mass','unresolved_future_prior_mass']
    assert not prior.duplicated(keys).any() and not pred.duplicated(keys).any()
    pair=prior[keys+values].merge(pred[keys+values],on=keys,how='outer',suffixes=('_v1','_v2'),validate='one_to_one',indicator=True)
    for value in ['probability_start_within_horizon','conditional_median_hours','at_risk_prior_mass','already_started_prior_mass']:
        pair[value+'_difference_v2_minus_v1']=pair[value+'_v2']-pair[value+'_v1']
    pair['comparison_scope']='same physical design universe; numerical-grid sensitivity, not forecast skill'
    pair['fragile_prior_changes_with_initial_margin']=pair.probability_prior.eq(PRIORS[2])
    pair.to_csv(OUT/'paired_v1_v2_weather_predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    x=pair.probability_start_within_horizon_difference_v2_minus_v1.dropna()
    t=pair.conditional_median_hours_difference_v2_minus_v1.dropna()
    return dict(status='matched_same_universe',old_input_path=str(old_path.relative_to(ROOT)),old_input_sha256=sha(old_path),
       old_model_universe=sorted(old_universe),new_model_universe=sorted(new_universe),new_bundle_version=bundle_version,
       matched_rows=int(pair['_merge'].eq('both').sum()),unmatched_rows=int(pair['_merge'].ne('both').sum()),
       identified_probability_pairs=len(x),maximum_absolute_probability_difference=float(x.abs().max()) if len(x) else None,
       conditional_median_pairs=len(t),maximum_absolute_conditional_median_difference_hours=float(t.abs().max()) if len(t) else None,
       interpretation='same issue/mechanism/law/space/latency/prior/horizon; risk-set changes and fragile-prior reweighting are retained, no winner ranking')

def run(bundle=None,output=None,mechanisms=None,experiment=None):
    global BUNDLE,OUT,EXPERIMENT
    if bundle is not None:BUNDLE=bundle.resolve()
    if output is not None:OUT=output.resolve()
    if experiment is not None:EXPERIMENT=experiment
    assert BUNDLE.is_relative_to(R/'inputs') and OUT.is_relative_to(R/'results/mechanistic_replay')
    started=datetime.now(timezone.utc);q,b,files,frame,forcing,config,clock,air,rain=load_inputs(mechanisms)
    OUT.mkdir(parents=True,exist_ok=True);engine=Physics(q,frame,config)
    issues=[START+timedelta(hours=i) for i in range(int((END-START).total_seconds()/3600)+1)]
    print(f'continuous Q2 history: {len(clock)} hours, {len(frame)} design rows, {engine.nb} full thermal profiles',flush=True)
    history=continuous_history(engine,clock,air,rain,issues)
    hv=history_validation(history,engine,frame,files);dump(OUT/'history_equivalence.json',hv)
    print(f'history full2048 and representative validation passed: {hv}',flush=True)
    weather,refs=weather_lookup()
    groups=[('mechanism_policy_mixture','all_delivered_mechanisms','mixture_of_both_law_policies',np.arange(len(frame)))]
    groups.extend((str(m),str(mech),str(policy),np.flatnonzero((frame.model_id.eq(m)&frame.law_policy.eq(policy)).to_numpy()))
        for (m,mech,policy),_ in frame.groupby(['model_id','mechanism_id','law_policy'],sort=True))
    predictions=[];ranges=[];runlog=[];statuses=Counter();restart_errors=[];s_invariance=[];future_boundaries=[]
    schema=pa.schema(PARQUET_FIELDS)
    writer=pq.ParquetWriter(OUT/'parameter_first_passages.parquet',schema,compression='zstd',use_dictionary=True)
    history_rows=[];n_runs=0;unique_physics_runs=0;reused_physics_runs=0
    try:
      for issue,j in zip(issues,history['issue_indices']):
        initial=history['margin'][j]
        deterministic_inputs_cache={}
        for n,s in enumerate(frame.scenario_id):
            history_rows.append(dict(issue_time=stamp(issue),scenario_id=s,base_scenario_id=frame.base_scenario_id.iloc[n],model_id=frame.model_id.iloc[n],mechanism_id=frame.mechanism_id.iloc[n],
                law_policy=frame.law_policy.iloc[n],failure_margin=initial[n],damage=history['damage'][j,n],storage_m=history['storage'][j,n],
                interface_temp_c=(history['interface_base'][j,engine.baseindex[n]] if engine.has_t[n] else engine.p['initial_temp_c'][n]),
                historical_first_cross_elapsed_hours=history['first_elapsed'][n] if history['first_elapsed'][n]<=j and not history['left'][n] else np.nan,
                historically_available=False,evaluation_stratum='conditional_scenario'))
        modes=[('historically_available','not_eligible',None),('ideal_weather','Q2_regional_station_forcing',None)]
        modes.extend(('assumed_latency',space,lat) for space in sorted(refs) for lat in [0,3,6,9])
        for mode,space,latency in modes:
            aa,pp,ref,forcing_status=get_forcing(mode,space,latency,issue,j,air,rain,clock,weather,refs)
            # Different latency assumptions often select exactly the same
            # initialization. Reuse that identical deterministic computation,
            # retaining every requested metadata/weight/censoring result row.
            cache_key=(aa.tobytes(),pp.tobytes())
            reused=cache_key in deterministic_inputs_cache
            if reused:
                result=deterministic_inputs_cache[cache_key];reused_physics_runs+=1
            else:
                result=forecast(engine,history,j,aa,pp);deterministic_inputs_cache[cache_key]=result;unique_physics_runs+=1
            if mode=='ideal_weather':
                length=result['followup'];full=history['margin'][j:j+length+1]
                error=float(np.max(abs(result['margin']-full)))
                error=max(error,float(np.max(abs(result['profile_final']-history['profiles'][j+length]))),
                    float(np.max(abs(result['damage_final']-history['damage'][j+length]))),float(np.max(abs(result['storage_final']-history['storage'][j+length]))))
                restart_errors.append(error)
            if mode=='assumed_latency':
                s_idx=np.flatnonzero(frame.mechanism_id.eq('S').to_numpy());length=min(result['followup'],len(clock)-1-j)
                if len(s_idx):s_invariance.append(float(np.max(abs(result['margin'][:length+1,s_idx]-history['margin'][j:j+length+1,s_idx]))))
                if ref is not None:future_boundaries.append(ref+timedelta(hours=latency)<=issue)
            common=dict(issue_time=stamp(issue),information_cutoff_utc=stamp(issue),forecast_input_mode=mode,space_object=space,
                event_id='B20260826_Chhochen',physical_phase='first_mechanical_initiation_at_source',
                assumed_latency_hours=latency,forecast_reference_time=stamp(ref) if ref else None,
                assumed_available_time=stamp(ref+timedelta(hours=latency)) if ref else None,available_time=None,
                forcing_status=forcing_status,followup_hours=result['followup'],historically_operationally_certified=False,
                identical_deterministic_input_computation_reused=reused,
                evaluation_stratum='conditional_scenario',data_role='scenario',history_state_role='retrospective_Q2_forcing_state_unknown_real_availability',
                future_state_role='per_issue_GFS_recomputed_Q2_physics' if mode=='assumed_latency' else 'retrospective_Q2_forcing_oracle' if mode=='ideal_weather' else 'rejected_unknown_historical_availability',
                experiment_id=EXPERIMENT,input_bundle_version=b['bundle_version'],input_bundle_sha256=sha(BUNDLE),
                input_weather_sha256=sha(R/'inputs/weather/gfs_hourly_summary.csv'),input_version=f"stage4-r3-v1; {b['bundle_version']}; weather-q3-v1")
            statuses.update(write_parameter_run(writer,frame,result,initial,history,common))
            runlog.append(dict(common,design_rows=len(frame),at_risk_rows=int(result['at_risk'].sum()),forecast_crossing_rows=int(np.isfinite(result['point']).sum())))
            for model,mechanism,policy,indices in groups:
              for H in HORIZONS:
                point=result['point'][indices];risk=result['at_risk'][indices];event=risk&np.isfinite(point)&(point<=H)
                unresolved=risk&~np.isfinite(point)&(result['followup']<H)
                rr=dict(common,model_id=model,mechanism_id=mechanism,law_policy=policy,horizon_hours=H,scenario_count=len(indices),
                    at_risk_scenario_count=int(risk.sum()),already_started_scenario_count=int((~risk).sum()),
                    point_crossing_count=int(event.sum()),right_censored_or_unknown_count=int(unresolved.sum()),
                    earliest_resolved_point_hours=float(np.min(point[event])) if event.any() else None,
                    latest_resolved_point_hours=float(np.max(point[event])) if event.any() else None,
                    range_definition='resolved_point_subset_only; unknown/right-censored masses separately retained',
                    role='parameter_design_range_no_probability')
                ranges.append(rr)
                for prior in PRIORS:
                    distribution_row=distribution(frame,result,initial,indices,H,prior)
                    predictions.append(dict(common,**distribution_row,engine='A_weather_coupled',model_id=model,mechanism_id=mechanism,law_policy=policy,
                        scenario_id='delivered_design_ensemble',geometry_version=str(frame.geometry_version.iloc[indices[0]]),parameter_version=str(frame.parameter_version.iloc[indices[0]]),
                        horizon_hours=H,truth_time_utc=None,empirical_coverage=None,independent_observed_events=0))
            n_runs+=1
        if len(runlog)%100==0:print(f'completed {len(runlog)} per-issue weather/rejection tracks',flush=True)
    finally:writer.close()
    csv_out(OUT/'predictions.csv.gz',predictions);csv_out(OUT/'scenario_ranges.csv.gz',ranges);csv_out(OUT/'run_log.csv',runlog)
    pd.DataFrame(history_rows).to_parquet(OUT/'history_states_at_issue.parquet',index=False,compression='zstd')
    pred=pd.DataFrame(predictions)
    aggregate=pred.groupby(['forecast_input_mode','space_object','assumed_latency_hours','model_id','law_policy','probability_prior','horizon_hours'],dropna=False).agg(
       issues=('issue_time','size'),identified_probabilities=('probability_start_within_horizon','count'),
       minimum_probability=('probability_start_within_horizon','min'),mean_probability=('probability_start_within_horizon','mean'),
       maximum_probability=('probability_start_within_horizon','max'),conditional_interval_count=('conditional_median_hours','count'),
       minimum_followup_hours=('followup_hours','min'),maximum_followup_hours=('followup_hours','max'),
       mean_strength_domain_fraction=('strength_domain_fraction','mean')).reset_index()
    aggregate.to_csv(OUT/'model_weather_comparison.csv',index=False)
    pred[pred.model_id.eq('mechanism_policy_mixture')].to_csv(OUT/'prior_sensitivity.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    keys=['issue_time','model_id','mechanism_id','law_policy','probability_prior','horizon_hours']
    ideal=pred[pred.forecast_input_mode.eq('ideal_weather')][keys+['probability_start_within_horizon','conditional_median_hours']]
    comp=pred[pred.forecast_input_mode.eq('assumed_latency')].merge(ideal,on=keys,suffixes=('','_ideal'),how='left')
    comp['probability_difference_vs_ideal']=comp.probability_start_within_horizon-comp.probability_start_within_horizon_ideal
    comp['conditional_median_difference_hours_vs_ideal']=comp.conditional_median_hours-comp.conditional_median_hours_ideal
    comp.to_csv(OUT/'matched_weather_contrasts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    paired_versions=version_comparison(pred,b['bundle_version'])
    if paired_versions is not None:dump(OUT/'version_comparison.json',paired_versions)
    finite=pred.dropna(subset=['probability_start_within_horizon'])
    prior_keys=['issue_time','forecast_input_mode','space_object','assumed_latency_hours','model_id','law_policy','horizon_hours']
    a=pred[pred.probability_prior.eq(PRIORS[0])].set_index(prior_keys).probability_start_within_horizon
    c=pred[pred.probability_prior.eq(PRIORS[1])].set_index(prior_keys).probability_start_within_horizon
    equality=bool(np.allclose(a.to_numpy(float),c.to_numpy(float),equal_nan=True))
    monotone=True
    for _,g in pred.groupby(['issue_time','forecast_input_mode','space_object','assumed_latency_hours','model_id','law_policy','probability_prior'],dropna=False):
        g=g.sort_values('horizon_hours')
        for column in ['probability_start_lower','probability_start_upper']:
            x=g[column].dropna().to_numpy(float)
            monotone=monotone and bool(np.all(np.diff(x)>=-1e-12))
    checks={
      'all_input_bundle_hashes_verified':True,'full_Q2_history_matches_delivered_outcomes_and_representatives':hv['passed'],
      'all_75_ideal_full_state_restarts_match_continuous_history':max(restart_errors)<1e-8,
      'structural_only_weather_invariance_when_included':max(s_invariance,default=0.)<1e-8,
      'water_budget_closure':engine.water_budget_max<1e-10,
      'assumed_forecast_reference_available_before_issue':all(future_boundaries),
      'probability_normalized_when_identified':bool(np.allclose(finite.probability_start_within_horizon+finite.probability_no_start_within_horizon,1)),
      'probability_bounds_valid':bool(((pred.probability_start_lower.dropna()>=-1e-12)&(pred.probability_start_lower.dropna()<=1+1e-12)).all() and
          ((pred.probability_start_upper.dropna()>=-1e-12)&(pred.probability_start_upper.dropna()<=1+1e-12)).all()),
      'probability_lower_not_above_upper':bool((pred.probability_start_lower<=pred.probability_start_upper+1e-12).all()),
      'prior_mass_preserved':bool(np.allclose(pred.already_started_prior_mass+pred.event_prior_mass+pred.no_start_prior_mass+pred.unresolved_future_prior_mass,1)),
      'balanced_uniform_and_equal_mechanism_priors_agree':equality,'horizon_probability_bounds_monotone':monotone,
      'historical_unknown_track_rejected':bool(pred.loc[pred.forecast_input_mode.eq('historically_available'),'probability_start_within_horizon'].isna().all()),
      'no_false_local_truth_or_empirical_coverage':bool(pred.truth_time_utc.isna().all() and pred.empirical_coverage.isna().all() and not pred.historically_operationally_certified.any()),
      'unknown_future_not_reported_as_exact_probability':bool(pred.loc[pred.unresolved_future_prior_mass>1e-12,'probability_start_within_horizon'].isna().all())}
    summary=dict(experiment_id=EXPERIMENT,started_at_utc=stamp(started),completed_at_utc=stamp(datetime.now(timezone.utc)),
      issue_count=len(issues),parameter_design_rows=len(frame),distinct_physical_designs=engine.nb,weather_tracks_per_issue=10,
      history_time_origin_utc=stamp(clock[0]),
      bundle_version=b['bundle_version'],included_mechanisms=sorted(frame.mechanism_id.unique()),
      thermal_discretization=dict(dz_m=engine.dz,bottom_m=engine.bottom,grid_points=len(engine.z),substeps_per_hour=engine.substeps),
      per_issue_track_runs=n_runs,parameter_prediction_rows=n_runs*len(frame),ensemble_prediction_rows=len(pred),scenario_range_rows=len(ranges),
      unique_full_ensemble_physics_computations=unique_physics_runs,reused_identical_input_tracks=reused_physics_runs,
      forecast_status_counts=dict(statuses),forecast_forcing_track_counts=dict(Counter(x['forcing_status'] for x in runlog)),
      historical_initial_left_censored=int(history['left'].sum()),historical_total_first_cross_or_left=int(np.isfinite(history['first_elapsed']).sum()),
      maximum_restart_absolute_error=max(restart_errors),maximum_S_weather_invariance_error=max(s_invariance,default=0.),
      S_weather_invariance_actually_checked=bool(s_invariance),maximum_step_water_budget_error_m=engine.water_budget_max,
      identified_probability_rows=len(finite),nonzero_identified_probability_rows=int((finite.probability_start_within_horizon>0).sum()),
      maximum_identified_probability=float(finite.probability_start_within_horizon.max()),
      conditional_interval_rows=int(pred.conditional_median_hours.notna().sum()),independent_local_observed_validation_events=0,empirical_coverage=None,
      paired_grid_version_comparison=paired_versions,
      inputs=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in dict.fromkeys(files.values())],
      checks=checks,passed=all(checks.values()),limitations=[
        'All source states and forecasts are conditional Q2 scenarios; local first mechanical initiation truth remains unknown',
        'Retrospective regional-station history has unknown real availability and assumed hourly precipitation intervals',
        'Direct GFS-to-regional-station driver replacement retains uncalibrated source offsets and multipliers; no local bias correction',
        'No verified historical first public weather availability; latency assumptions are not business release facts',
        'Three priors are analyst sensitivity assumptions, not probabilities implied by the space-filling design',
        'Q2 rock/ice strength transfer, thermal boundary, damage and reservoir limitations retained',
        'Exact consumer/Q2 numerical agreement is distinct from heat-equation grid convergence and scientific model adoption',
        'Conditional 95 percent quantiles describe assumed scenario distributions; empirical coverage denominator is zero',
        'Short followup and missing future forcing remain unresolved, never imputed as no start'])
    dump(OUT/'summary.json',summary);dump(OUT/'validation.json',dict(checks=checks,passed=all(checks.values()),history_validation=hv,
        maximum_restart_absolute_error=max(restart_errors),maximum_water_budget_error_m=engine.water_budget_max,independent_observed_events=0))
    if not all(checks.values()):raise AssertionError(checks)
    print(json.dumps(clean(summary),ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle');parser.add_argument('--output-dir');parser.add_argument('--mechanisms');parser.add_argument('--experiment-id');parser.add_argument('--redact-history-metadata');parser.add_argument('--support-diagnostics');parser.add_argument('--audit-exports')
    args=parser.parse_args()
    if args.audit_exports:audit_exports(ROOT/args.audit_exports)
    elif args.support_diagnostics:event_support_diagnostics(ROOT/args.support_diagnostics)
    elif args.redact_history_metadata:redact_history_metadata(ROOT/args.redact_history_metadata)
    else:run(ROOT/args.bundle if args.bundle else None,ROOT/args.output_dir if args.output_dir else None,
        args.mechanisms.split(',') if args.mechanisms else None,args.experiment_id)
