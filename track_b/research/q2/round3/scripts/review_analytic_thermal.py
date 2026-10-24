#!/usr/bin/env python3
"""Independent, read-only analytic thermal solver review.

Uses scalar math.erfc direct summation as reference, never the engine kernel.
This report provides numerical verification, not independent event validation.
"""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT=Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2')
BASE=ROOT/'track_b/research/q2/round3'
OUT=BASE/'results/analytic_thermal_independent_review.json'


def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def direct_halfspace(air, initial, offset, depth, diffusivity, dt_hours=1.):
    """Scalar loops with Python erfc; output shape scenario,time."""
    initial=np.atleast_1d(initial).astype(float)
    offset=np.atleast_1d(offset).astype(float)
    depth=np.atleast_1d(depth).astype(float)
    diffusivity=np.atleast_1d(diffusivity).astype(float)
    initial,offset,depth,diffusivity=np.broadcast_arrays(initial,offset,depth,diffusivity)
    air=np.asarray(air,float)
    n=len(air); result=np.empty((len(initial),n))
    for j in range(len(initial)):
        boundary=np.minimum(air+offset[j],0.)
        increments=np.empty(n); increments[0]=boundary[0]-initial[j];increments[1:]=np.diff(boundary)
        for k in range(n):
            result[j,k]=initial[j]+math.fsum(float(increments[i])*math.erfc(float(depth[j])/(2*math.sqrt(float(diffusivity[j])*(k-i)*dt_hours*3600.))) for i in range(k))
    return result

def image_kernel(z,t,alpha,L=40.,terms=64):
    """Independent D(0)/N(L) step kernel via scalar image terms."""
    if t<=0: return 0.
    a=2*math.sqrt(alpha*t)
    return math.fsum((-1.)**n*(math.erfc((2*n*L+z)/a)+math.erfc((2*(n+1)*L-z)/a)) for n in range(terms))

def direct_finite(air,initial,offset,depth,alpha,dt_hours=1.,L=40.):
    b=np.minimum(np.asarray(air,float)+offset,0.)
    db=np.r_[b[0]-initial,np.diff(b)]
    return np.asarray([initial+math.fsum(float(db[i])*image_kernel(depth,(k-i)*dt_hours*3600,alpha,L) for i in range(k)) for k in range(len(b))])


def main():
    if Path.cwd().resolve()!=ROOT:
        raise RuntimeError('explicit execution root required')
    sys.dont_write_bytecode=True
    engine_path=BASE/'scripts/analytic_thermal_engine.py'
    runner_path=BASE/'scripts/run_analytic_thermal.py'
    engine_hash=digest(engine_path)
    sys.path.insert(0,str(BASE/'scripts'))
    spec=importlib.util.spec_from_file_location('q2_independently_reviewed_analytic_engine',engine_path)
    engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    checks=[];advisories=[]
    def check(name,condition,**evidence):
        checks.append({'check':name,'passed':bool(condition),**evidence})
        if not condition: raise AssertionError(name)
    def p(initial=-3.,offset=-8.,depth=2.,alpha=1.3e-6):
        return {'initial_temp_c':np.atleast_1d(initial).astype(float),'station_source_offset_c':np.atleast_1d(offset).astype(float),'interface_depth_m':np.atleast_1d(depth).astype(float),'diffusivity_m2_s':np.atleast_1d(alpha).astype(float)}
    rng=np.random.default_rng(112398)
    nt=137;air=8+9*np.sin(np.arange(nt)*.17)+rng.normal(0,3,nt)
    pp=p([-6.,-.8,-3.,-4.],[-18.,-6.,-12.,-9.],[.5,2.,8.,20.],[9e-7,2.1e-6,1.7e-6,1.2e-6])
    T,B=engine.thermal_transfer_analytic(air,pp)
    direct=direct_halfspace(air,pp['initial_temp_c'],pp['station_source_offset_c'],pp['interface_depth_m'],pp['diffusivity_m2_s']).T
    err=float(np.max(np.abs(T-direct)))
    check('multirow_fft_vs_independent_scalar_erfc_direct_loop',err<2e-12,max_abs_error_c=err,nt=nt,n_parameter_rows=4,reference='math.erfc + math.fsum scalar i<k loops; no engine kernel')
    check('temperature_and_boundary_shape_time_by_parameter',T.shape==(nt,4) and B.shape==(nt,4),temperature_shape=list(T.shape),boundary_shape=list(B.shape))
    check('hourly_left_hold_boundary_cap_preserved',np.array_equal(B,np.minimum(air[:,None]+pp['station_source_offset_c'][None,:],0.)))
    check('initial_state_exact_not_step_boundary',np.array_equal(T[0],pp['initial_temp_c']))
    for name,initial,bound in [('warm_step',-5.,-1.),('negative_cooling',-1.,-5.)]:
        params=p(initial=initial,offset=-10.,depth=1.7,alpha=1.8e-6)
        aa=np.full(97,bound+10.)
        out,_=engine.thermal_transfer_analytic(aa,params)
        ref=np.array([initial]+[initial+(bound-initial)*math.erfc(1.7/(2*math.sqrt(1.8e-6*k*3600.))) for k in range(1,97)])
        error=float(np.max(np.abs(out[:,0]-ref)))
        monotone=np.all(np.diff(out[:,0])>=-1e-12) if bound>initial else np.all(np.diff(out[:,0])<=1e-12)
        check(name+'_closed_form_and_monotonicity',error<2e-12 and monotone,max_abs_error_c=error,initial_c=initial,boundary_c=bound)
    iso_params=p(initial=-3.,offset=-10.,depth=3.,alpha=9e-7)
    iso,_=engine.thermal_transfer_analytic(np.full(25,7.),iso_params)
    check('isothermal_equilibrium_exact',np.array_equal(iso,np.full((25,1),-3.)))
    for dt in [.5,1.,3.]:
        out,_=engine.thermal_transfer_analytic(air,pp,dt_hours=dt)
        ref=direct_halfspace(air,pp['initial_temp_c'],pp['station_source_offset_c'],pp['interface_depth_m'],pp['diffusivity_m2_s'],dt).T
        e=float(np.max(np.abs(out-ref)))
        check('hours_to_seconds_units_'+str(dt),e<2e-12,max_abs_error_c=e,dt_hours=dt,seconds_per_hour=3600)
    # A future boundary increment first affects state[m+1]; state[m] is included in the unchanged past.
    split=63;future=air.copy();future[split:]+=7.
    altered,_=engine.thermal_transfer_analytic(future,pp)
    past_error=float(np.max(np.abs(altered[:split+1]-T[:split+1])))
    future_effect=float(np.max(np.abs(altered[split+1:]-T[split+1:])))
    check('future_only_forcing_has_no_past_effect_to_fft_roundoff',past_error<2e-12 and future_effect>1e-4,past_max_abs_error_c=past_error,future_max_effect_c=future_effect,first_changed_forcing_index=split,first_permitted_changed_state_index=split+1)
    last=air.copy();last[-1]-=8.
    last_T,_=engine.thermal_transfer_analytic(last,pp)
    last_error=float(np.max(np.abs(last_T-T)))
    check('final_boundary_has_no_returned_state_effect',last_error<2e-12,max_abs_error_c=last_error)
    increments=np.zeros((23,2));increments[1,0]=3.;increments[8,0]=-2.;increments[-1,1]=1000.
    kernel=engine.step_kernel(23,[.5,2.],[9e-7,2.1e-6])
    conv,nfft=engine.linear_causal_convolution(increments,kernel)
    scalar=np.stack([np.convolve(increments[:,j],kernel[:,j],mode='full')[:23] for j in range(2)],axis=1)
    check('explicit_zero_padding_and_no_circular_wrap',nfft>=45 and np.max(np.abs(conv-scalar))<2e-12 and np.max(np.abs(conv[:,1]))<2e-12,nfft=int(nfft),required_at_least=45,max_abs_error_c=float(np.max(np.abs(conv-scalar))))
    check('kernel_zero_lag_exact',np.array_equal(kernel[0],np.zeros(2)))
    z0_params=p(initial=-2.,offset=-6.,depth=0.)
    z0_air=np.array([8.,-10.,9.,0.,2.])
    z0,zb=engine.thermal_transfer_analytic(z0_air,z0_params)
    check('surface_depth_zero_is_documented_left_limit',np.max(np.abs(z0[:,0]-np.r_[-2.,zb[:-1,0]]))<2e-12,meaning='state0=Tinit; state[k>0]=B[k-1]. Not the right-continuous B[k] at the forcing jump.')
    single,single_B=engine.thermal_transfer_analytic([11.],p())
    check('single_state_zero_elapsed_time',single.shape==(1,1) and single[0,0]==-3.)
    check('discrete_maximum_principle_in_production_parameter_range',all(T[:,j].min()>=min(pp['initial_temp_c'][j],B[:,j].min())-2e-12 and T[:,j].max()<=max(pp['initial_temp_c'][j],B[:,j].max())+2e-12 for j in range(4)))
    invalid=[('empty_air',lambda:engine.thermal_transfer_analytic([],p())),('nan_air',lambda:engine.thermal_transfer_analytic([float('nan')],p())),('negative_alpha',lambda:engine.step_kernel(2,[1.],[-1e-6])),('negative_depth',lambda:engine.step_kernel(2,[-1.],[1e-6])),('zero_dt',lambda:engine.step_kernel(2,[1.],[1e-6],dt_hours=0)),('mismatched_parameter_row_shapes',lambda:engine.thermal_transfer_analytic([0.,1.],p(initial=[-2.,-3.],offset=[-8.],depth=[1.,2.],alpha=[1e-6,2e-6]))),('finite_depth_below_bottom',lambda:engine.finite_step_kernel(2,[41.],[1e-6],40.))]
    for name,func in invalid:
        rejected=False
        try:func()
        except (ValueError,TypeError):rejected=True
        check('reject_'+name,rejected)
    # These observable-reflection benchmarks differ from the physics agent's L2/L4 cases.
    for L,z,alpha,n in [(3.,2.3,2.1e-6,337),(7.,5.8,1.3e-6,481)]:
        finite,corr=engine.finite_step_kernel(n,[z],[alpha],L,terms=24)
        ref=np.array([image_kernel(z,k*3600,alpha,L,terms=96) for k in range(n)])
        error=float(np.max(np.abs(finite[:,0]-ref)))
        # Independently derive finite D/N step response from sine eigenfunctions.
        spectral=[]
        for k in [1,24,n-1]:
            t=k*3600.;terms=[]
            for m in range(2000):
                odd=2*m+1;lam=odd*math.pi/(2*L)
                terms.append(4/(odd*math.pi)*math.sin(lam*z)*math.exp(-alpha*lam*lam*t))
            spectral.append((k,1-math.fsum(terms)))
        spectral_error=max(abs(float(finite[k,0])-value) for k,value in spectral)
        check('finite_DN_image_kernel_independent_L'+str(L),error<2e-12 and spectral_error<2e-12,max_abs_image_error=error,max_abs_eigenfunction_error=spectral_error,domain={'L_m':L,'z_m':z,'alpha_m2_s':alpha,'nt':n,'dt_hours':1.},benchmark_evidence_tier='numerical_benchmark_not_local_event')
        check('finite_kernel_reflection_nonnegative_L'+str(L),np.min(corr)>=-1e-14 and finite.min()>=-1e-14 and finite.max()<=1+1e-14,max_correction=float(corr.max()))
    L=3.;alpha=2.1e-6;n=337
    surface,_=engine.finite_step_kernel(n,[0.],[alpha],L,terms=24)
    check('finite_Dirichlet_boundary_equals_unit_step',np.array_equal(surface[0],np.zeros(1)) and np.max(np.abs(surface[1:,0]-1))<2e-12)
    h=1e-4;bottom,_=engine.finite_step_kernel(n,[L,L-h,L-2*h],[alpha]*3,L,terms=24)
    derivative=(3*bottom[:,0]-4*bottom[:,1]+bottom[:,2])/(2*h)
    check('finite_bottom_Neumann_independent_one_sided_derivative',np.max(np.abs(derivative))<2e-7,max_abs_derivative_per_m=float(np.max(np.abs(derivative))),h_m=h)
    # Read the actual published forcing/parameter design, not a hand-picked constant boundary.
    import pandas as pd
    forcing_path=BASE/'results/refined_v2/forcing_hourly_v2.csv'
    params_path=BASE/'results/refined_v2/parameter_ensemble.csv'
    forcing=pd.read_csv(forcing_path);param=pd.read_csv(params_path).drop_duplicates('parameter_set_id')
    actual_air=forcing.station_air_temp_c.to_numpy(float)
    actual={name:param[name].to_numpy(float) for name in pp}
    elapsed=forcing.elapsed_hours.to_numpy(float)
    check('actual_inputs_hourly_2088h_and_declared_thermal_domain',len(actual_air)==2089 and np.array_equal(elapsed,np.arange(2089)) and actual['interface_depth_m'].min()>=.5 and actual['interface_depth_m'].max()<=20. and actual['diffusivity_m2_s'].max()<=2.1e-6,nt=len(actual_air),horizon_hours=float(elapsed[-1]),parameter_rows=len(param))
    engine_bound,engine_tv,engine_kmax=engine.reflection_temperature_bound(actual_air,actual,bottom_m=40.,dt_hours=1.)
    actual_bounds=[];actual_tvs=[]
    horizon=2088*3600.
    for j in range(len(param)):
        b=np.minimum(actual_air+actual['station_source_offset_c'][j],0.)
        db=np.r_[b[0]-actual['initial_temp_c'][j],np.diff(b)]
        tv=math.fsum(abs(float(v)) for v in db[:-1])
        first=math.erfc((80-actual['interface_depth_m'][j])/(2*math.sqrt(actual['diffusivity_m2_s'][j]*horizon)))
        actual_tvs.append(tv);actual_bounds.append(tv*first)
    actual_bounds=np.array(actual_bounds);actual_tvs=np.array(actual_tvs)
    relative=float(np.max(np.abs(engine_bound-actual_bounds)/np.maximum(np.abs(actual_bounds),1e-300)))
    check('finite_reflection_bound_actual_forcing_total_variation',relative<2e-12,max_relative_error=relative,max_actual_bound_c=float(actual_bounds.max()),max_actual_effective_total_variation_c=float(actual_tvs.max()),unused_last_increment_excluded=True)
    domain_erfc=math.erfc(60/(2*math.sqrt(2.1e-6*horizon)))
    full_tv_max=max(math.fsum(abs(float(v)) for v in np.r_[np.minimum(actual_air+actual['station_source_offset_c'][j],0.)[0]-actual['initial_temp_c'][j],np.diff(np.minimum(actual_air+actual['station_source_offset_c'][j],0.))]) for j in range(len(param)))
    uniform_bound=domain_erfc*full_tv_max
    check('uniform_60m_minimum_reflection_distance_bound',np.all(actual_bounds<=uniform_bound) and domain_erfc<1.3e-26,domain_kernel_upper_bound=domain_erfc,max_full_boundary_total_variation_c=full_tv_max,temperature_uniform_upper_bound_c=uniform_bound,derivation='Kfinite-Ksemi=sum_m>=1(-1)^(m-1)[erfc((2mL-z)/a)-erfc((2mL+z)/a)]. Positive decreasing brackets imply 0<=difference<=first bracket<=erfc((2L-z)/a). Multiply its horizon supremum by sum(abs(dB)); 2L-z>=60m.')
    # Review the production runner and already-published numeric audit files without running it.
    runner_text=runner_path.read_text()
    runner_ast=ast.parse(runner_text)
    assigned_engine_hash=next(node.value.value for node in runner_ast.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ENGINE_SHA' for t in node.targets))
    mechanical_path=BASE/'scripts/mechanism_engine.py'
    check('runner_binds_the_unchanged_mechanical_engine',assigned_engine_hash==digest(mechanical_path),sha256=assigned_engine_hash)
    current_results=[]
    analytic_results=BASE/'results/analytic_thermal'
    for filename in ['protocol.json','config.json','reflection_bounds.csv','forcing_hourly.csv']:
        fp=analytic_results/filename
        if fp.exists(): current_results.append({'path':str(fp.relative_to(ROOT)),'sha256':digest(fp),'reading_scope':'All rows/fields used by independent audit below.'})
    config=json.loads((analytic_results/'config.json').read_text())
    check('published_runner_fft_config_hourly_and_linear_padding',config['state_dt_hours']==1. and config['fft_nfft']>=4177 and config['fft_padding_min_samples']==4177,state_dt_hours=config['state_dt_hours'],nfft=config['fft_nfft'],minimum_padding=config['fft_padding_min_samples'])
    protocol=json.loads((analytic_results/'protocol.json').read_text())
    check('published_protocol_preserves_all_four_groups_no_independent_events',protocol['parameter_points']==256 and protocol['outcomes_expected']==2048 and set(protocol['mechanism_groups'])=={'S','S_T','S_H','S_T_H'} and protocol['independent_observed_events']==0)
    published_bounds=pd.read_csv(analytic_results/'reflection_bounds.csv')
    bound_error=float(np.max(np.abs(published_bounds.finite40_minus_halfspace_temperature_abs_bound_c.to_numpy()-actual_bounds)/np.maximum(np.abs(actual_bounds),1e-300)))
    check('published_reflection_csv_matches_independent_actual_forcing_bound',len(published_bounds)==len(param) and bound_error<2e-12,max_relative_error=bound_error)
    published_forcing=pd.read_csv(analytic_results/'forcing_hourly.csv')
    check('published_forcing_copy_preserves_hourly_inputs',published_forcing.shape==forcing.shape and np.array_equal(published_forcing.station_air_temp_c,forcing.station_air_temp_c) and np.array_equal(published_forcing.elapsed_hours,forcing.elapsed_hours))
    # Verify the public callable's delegation with independently computed temperatures.
    short_air=actual_air[:49]
    full_params={key:param[key].to_numpy(float)[:4] for key in list(config['ranges'])+['density_kg_m3']}
    direct_temperature=direct_halfspace(short_air,full_params['initial_temp_c'],full_params['station_source_offset_c'],full_params['interface_depth_m'],full_params['diffusivity_m2_s']).T
    direct_boundary=np.minimum(short_air[:,None]+full_params['station_source_offset_c'][None,:],0.)
    short_rain=forcing.precip_assumed_mm_h.to_numpy(float)[:49]
    for mechanism in ['S','S_T','S_H','S_T_H']:
        wrapped=engine.simulate_analytic(short_air,short_rain,full_params,mechanism=mechanism)
        delegated=engine.simulate(short_air,short_rain,full_params,mechanism=mechanism,thermal=(direct_temperature,direct_boundary))
        e=max(float(np.max(np.abs(wrapped[key]-delegated[key]))) for key in ['failure_margin','damage','storage_m','pressure_kpa','interface_temp_c'])
        check('public_wrapper_direct_temperature_delegation_'+mechanism,e<2e-12,max_abs_numeric_output_difference=e,scope='49 hourly states x4 real design rows; same frozen mechanics, independently summed thermal input; not an independent mechanical model or observed event')
    # A nan time step is outside production's fixed finite 1h contract; report input-hardening gap.
    try:
        bad=engine.step_kernel(2,[1.],[1e-6],dt_hours=float('nan'))
        if not np.isfinite(bad).all():advisories.append('step_kernel does not reject NaN dt_hours. Production contract fixes dt_hours=1 finite; optional input-hardening follow-up, no observed production numerical effect.')
    except ValueError:pass
    check('reviewed_engine_bytes_unchanged_during_review',digest(engine_path)==engine_hash,sha256=engine_hash)
    runner_hash=digest(runner_path) if runner_path.exists() else None
    record={'review_version':'q2r3-analytic-thermal-independent-v1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'reviewer':'independent_SAR_agent_numeric_review','outcome':'pass_with_nonblocking_input_hardening_advisory' if advisories else 'pass','files_reviewed':[{'path':str(engine_path.relative_to(ROOT)),'sha256':engine_hash,'reading_scope':'Entire analytic engine, independently tested thermal operators and reflection bound; simulate wrapper delegation inspected and tested in four groups.'},{'path':str(runner_path.relative_to(ROOT)),'sha256':runner_hash,'reading_scope':'Entire runner source read: protocol, input binding, causal thermal override, unchanged mechanical loops, scenario ID/version suffixes, reference pairing and bundle construction. No full2048 mechanical experiment rerun by this review.'},{'path':str(forcing_path.relative_to(ROOT)),'sha256':digest(forcing_path),'reading_scope':'All2089 station-air forcing values and elapsed-hours used for actual B total variation.'},{'path':str(params_path.relative_to(ROOT)),'sha256':digest(params_path),'reading_scope':'All rows parsed; unique parameter_set_id thermal design used for bounds.'}]+current_results, 'checks':checks,'advisories':advisories,'mathematical_scope':{'PDE':'dT/dt=alpha*d2T/dz2, homogeneous initial interior Tinit, Dirichlet B at z0, half-space bounded at infinity; finite challenger Dirichlet0/NeumannL.','boundary_hold':'B_i=min(air_i+offset,0), held on[i,i+1)hours. DeltaB0=B0-Tinit; later differences.','discrete_response':'T_k=Tinit+sum_i<k DeltaB_i erfc[z/(2sqrt(alpha*(k-i)*3600))], K0=0.','z0_convention':'state[k>0]=B[k-1] left boundary limit; state0=Tinit. Actual production depths0.5..20m.','time_units':'One hour=3600seconds; horizon2088h; diffusivity m2/s; depth m; temperatures and increments degreeC.','finite_reflection_scope':'Production L40,z<=20,alpha<=2.1e-6,horizon<=2088h; bound is only mathematical truncation error, not heat-physics or station-to-interface model error.'},'independent_events':0,'data_role':'numerical_benchmark_and_conditional_scenario_review','scientific_causal_validation':False,'actual_command':'track_b/.venv/bin/python track_b/research/q2/round3/scripts/review_analytic_thermal.py','writes':[str(OUT.relative_to(ROOT))]}
    OUT.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'outcome':record['outcome'],'checks':len(checks),'engine_sha256':engine_hash,'runner_sha256':runner_hash,'max_actual_reflection_bound_c':float(actual_bounds.max()),'uniform_domain_reflection_bound_c':uniform_bound,'advisories':advisories},indent=2))

if __name__=='__main__': main()
