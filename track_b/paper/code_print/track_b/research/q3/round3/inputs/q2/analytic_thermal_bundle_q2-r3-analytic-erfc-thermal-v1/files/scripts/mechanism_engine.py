"""Q2R3 plane-slab conditional mechanism engine; SI except kPa and hours.

No event-time fitting; arrays are computational scenarios, not observations.
Time[0] is the specified initial state. Forcing[i] drives [time[i],time[i+1]).
"""
from __future__ import annotations

import numpy as np

MODEL_IDS = {"S": "q2r3_S_v1", "S_T": "q2r3_ST_v1", "S_H": "q2r3_SH_v1", "S_T_H": "q2r3_STH_v1"}
MARGIN_DEFINITION = "(resisting_shear_kPa-driving_shear_kPa)/driving_shear_kPa; positive stable"
G = 9.80665


def stresses(parameters):
    """h is thickness normal to plane, not vertical thickness."""
    theta = np.deg2rad(np.asarray(parameters["theta_deg"], float))
    weight = np.asarray(parameters["density_kg_m3"]) * G * np.asarray(parameters["thickness_normal_m"]) / 1000
    return weight * np.cos(theta), weight * np.sin(theta)


def joint_strength(temperature_c, policy="linear_extension"):
    """Mamot2018 Eq4/5: ice-filled limestone joint, not pure ice.

    Source domain -8<=T<=-.5 degC; effective stress/domain checked by caller.
    linear_extension explicitly retains and flags extrapolation.
    thawed_rock_contact is an uncalibrated challenger above -.5 C.
    """
    t = np.asarray(temperature_c, float)
    c, mu = 53.3 - 73.5 * t, 0.42 - 0.21 * t
    if policy == "thawed_rock_contact":
        c, mu = np.where(t > -0.5, 0., c), np.where(t > -0.5, 0.60, mu)
    elif policy != "linear_extension":
        raise ValueError(policy)
    return c, mu


def resistance(parameters, damage, interface_c, pressure_kpa, policy="linear_extension"):
    sn, drive = stresses(parameters)
    c_joint, mu_joint = joint_strength(interface_c, policy)
    bridge = np.asarray(parameters["bridge_fraction"])
    cohesion = (1-np.asarray(damage)) * (bridge*np.asarray(parameters["bridge_cohesion_kpa"]) + (1-bridge)*c_joint)
    friction = bridge*np.asarray(parameters["rock_mu"]) + (1-bridge)*mu_joint
    eff = sn-np.asarray(pressure_kpa)
    resist = cohesion + np.maximum(eff, 0)*friction
    margin = (resist-drive)/drive
    domain = (np.asarray(interface_c)>=-8) & (np.asarray(interface_c)<=-.5) & (eff>=100) & (eff<=400)
    algebraic_head = (sn-(drive-cohesion)/friction)/(G)  # rho_water=1000: kPa per metre = g
    # With nonnegative effective stress, cohesion > driving cannot be
    # destabilized by pressure alone. Do not export an unreachable root.
    critical_head = np.where(cohesion <= drive, algebraic_head, np.nan)
    root_status = np.where(cohesion > drive, 'no_pressure_only_root',
                           np.where(cohesion == drive, 'contact_limit_critical',
                                    np.where(algebraic_head <= 0, 'dry_already_critical', 'positive_pressure_root')))
    return dict(resistance_kpa=resist, driving_kpa=drive, normal_kpa=sn,
                effective_kpa=eff, failure_margin=margin, strength_domain=domain,
                contact_valid=eff>0, critical_head_m=critical_head,
                cohesion_kpa=cohesion, mu=friction,critical_head_status=root_status)


def thermal_transfer(air_c, parameters, dt_hours=1., dz_m=.5, bottom_m=40.):
    """Explicit 1D conduction, surface Dirichlet, bottom no flux.

    Surface min(air + scenario offset, 0) assumes an ice-capped boundary;
    this is not an energy balance or measured source temperature.
    """
    air = np.asarray(air_c, float)
    if not np.all(np.isfinite(air)):
        raise ValueError("missing temperature: cannot silently fill")
    n = len(parameters["initial_temp_c"])
    initial = np.asarray(parameters["initial_temp_c"], float)
    alpha = np.asarray(parameters["diffusivity_m2_s"], float)
    depth = np.asarray(parameters["interface_depth_m"], float)
    z = np.arange(0, bottom_m+dz_m*.5, dz_m)
    if depth.max() >= bottom_m or depth.min() < 0:
        raise ValueError("interface outside thermal domain")
    ratio = alpha*dt_hours*3600/dz_m**2
    substeps = max(1, int(np.ceil(ratio.max()/.45)))
    rr = ratio[:, None]/substeps
    prof = np.repeat(initial[:, None], len(z), axis=1)
    ti = np.empty((len(air), n), float)
    surf = np.minimum(air[:, None]+np.asarray(parameters["station_source_offset_c"])[None, :], 0)
    k = np.floor(depth/dz_m).astype(int); frac = depth/dz_m-k; row=np.arange(n)
    ti[0] = initial
    for i in range(len(air)-1):
        for _ in range(substeps):
            old=prof.copy(); old[:,0]=surf[i]
            prof[:,1:-1]=old[:,1:-1]+rr*(old[:,2:]-2*old[:,1:-1]+old[:,:-2])
            prof[:,-1]=old[:,-1]+2*rr[:,0]*(old[:,-2]-old[:,-1])
            prof[:,0]=surf[i]
        ti[i+1]=prof[row,k]*(1-frac)+prof[row,k+1]*frac
    return ti, surf


def reservoir_step(storage_m, input_m_h, tau_h, capacity_m, dt_h):
    """Exact piecewise constant-input reservoir with continuous overflow.

    Integrate until the capacity is hit, then keep capacity storage while
    I-C/tau overflows. This avoids timestep-dependent drain/overflow splits.
    """
    w,inc,tau,cap=np.broadcast_arrays(np.asarray(storage_m,float),np.asarray(input_m_h,float),np.asarray(tau_h,float),np.asarray(capacity_m,float))
    if np.any(tau<=0) or np.any(cap<0) or dt_h<=0 or np.any(inc<0): raise ValueError('invalid reservoir parameters')
    immediate=np.maximum(w-cap,0);w=np.minimum(w,cap)
    equilibrium=inc*tau
    decay=np.exp(-dt_h/tau)
    provisional=w*decay+equilibrium*(1-decay)
    hits=(equilibrium>cap)&(provisional>=cap)
    fraction=np.divide(equilibrium-cap,equilibrium-w,out=np.ones_like(w),where=(equilibrium-w)>0)
    hit_time=-tau*np.log(np.clip(fraction,1e-300,1.))
    active_time=np.where(hits,dt_h-np.clip(hit_time,0,dt_h),0.)
    storage=np.where(hits,cap,provisional)
    overflow=immediate+np.maximum(inc-cap/tau,0)*active_time
    drainage=np.asarray(storage_m)+inc*dt_h-storage-overflow
    return storage,drainage,overflow


def simulate(air_c, precip_mm_h, parameters, mechanism="S_T_H", policy="linear_extension",
             dt_hours=1., dz_m=.5, thermal=None, drainage_feedback=True, damage_enabled=True):
    """Run all parameter rows together; never removes non-failing scenarios.

    Continuing after first criterion crossing is a counterfactual diagnostic,
    not motion/propagation. Independent-event counts are not defined here.
    """
    if mechanism not in MODEL_IDS: raise ValueError(mechanism)
    air, rain = np.asarray(air_c,float), np.asarray(precip_mm_h,float)
    if len(air)!=len(rain) or not np.all(np.isfinite(rain)) or np.any(rain<0):
        raise ValueError("rain inputs must be finite nonnegative conditional rates")
    tstate, surf = thermal if thermal is not None else thermal_transfer(air,parameters,dt_hours,dz_m)
    nt,n=tstate.shape
    has_t=mechanism in ("S_T","S_T_H"); has_h=mechanism in ("S_H","S_T_H")
    ti=tstate if has_t else np.broadcast_to(np.asarray(parameters['initial_temp_c']),tstate.shape)
    damage=np.empty((nt,n)); storage=np.zeros((nt,n)); pressure=np.zeros((nt,n))
    margin=np.empty((nt,n)); domain=np.empty((nt,n),bool); critical=np.empty((nt,n))
    damage[0]=parameters['initial_damage']
    sn,drive=stresses(parameters)
    capacity_head=np.minimum(np.asarray(parameters['connected_depth_m']),.98*sn/G)
    capacity=capacity_head*np.asarray(parameters['storativity'])
    cumulative_input=np.zeros(n); cumulative_drain=np.zeros(n); cumulative_overflow=np.zeros(n)
    budget_error=np.zeros(n)
    for i in range(nt):
        pressure[i]=G*storage[i]/np.asarray(parameters['storativity']) if has_h else 0
        state=resistance(parameters,damage[i],ti[i],pressure[i],policy)
        margin[i]=state['failure_margin'];domain[i]=state['strength_domain'];critical[i]=state['critical_head_m']
        if i==nt-1: break
        # Phenomenological stress-ratio damage; no claimed creep-material calibration.
        ratio=drive/np.maximum(state['resistance_kpa'],1e-6)
        rate=np.asarray(parameters['damage_rate_h_inv'])*np.minimum(ratio,10.)**np.asarray(parameters['damage_exponent']) if damage_enabled else np.zeros(n)
        damage[i+1]=1-(1-damage[i])*np.exp(-rate*dt_hours)
        damage[i+1]=np.minimum(damage[i+1],.999999)
        if has_h:
            source_air=air[i]+np.asarray(parameters['station_source_offset_c'])
            rain_fraction=np.clip((source_air+1)/2,0,1)
            incoming=np.asarray(parameters['rain_multiplier'])*rain[i]/1000*rain_fraction + np.asarray(parameters['melt_mm_deg_day'])*np.maximum(source_air,0)/24000
            # Damage may increase connectivity/drainage; this coupling is a scenario.
            tau=np.asarray(parameters['drainage_hours'])*np.exp(-np.asarray(parameters['drainage_damage_coupling'])*damage[i]) if drainage_feedback else np.asarray(parameters['drainage_hours'])
            storage[i+1],out,over=reservoir_step(storage[i],incoming,tau,capacity,dt_hours)
            cumulative_input+=incoming*dt_hours;cumulative_drain+=out;cumulative_overflow+=over
            budget_error=np.maximum(budget_error,np.abs(storage[i+1]-cumulative_input+cumulative_drain+cumulative_overflow))
    return dict(interface_temp_c=ti,damage=damage,storage_m=storage,pressure_kpa=pressure,
                failure_margin=margin,strength_domain=domain,critical_head_m=critical,
                water_budget_max_abs_m=budget_error,water_input_m=cumulative_input,
                water_drain_m=cumulative_drain,water_overflow_m=cumulative_overflow)


def classify_trajectory(margins, dt_hours=1.):
    """Distinct missing/left-censored/interval-crossing/never-crossed states.

    A missing value before any crossing prevents a no-start claim. A first
    sample <=0 is already unstable, not an observed onset at time zero.
    """
    x=np.asarray(margins,float)
    if x.ndim!=1 or len(x)==0: raise ValueError('one nonempty trajectory required')
    finite=np.isfinite(x)
    if not finite[0]: return dict(onset_status='missing',onset_elapsed_hours=None,crossing_lower_hours=None,crossing_upper_hours=None)
    if x[0]<=0: return dict(onset_status='left_censored_already_unstable',onset_elapsed_hours=None,crossing_lower_hours=None,crossing_upper_hours=0.)
    below=np.flatnonzero(finite&(x<=0))
    if len(below):
        k=int(below[0])
        if not finite[:k+1].all(): return dict(onset_status='missing_before_possible_crossing',onset_elapsed_hours=None,crossing_lower_hours=None,crossing_upper_hours=k*dt_hours)
        f=x[k-1]/(x[k-1]-x[k])
        return dict(onset_status='interval_crossing',onset_elapsed_hours=(k-1+f)*dt_hours,crossing_lower_hours=(k-1)*dt_hours,crossing_upper_hours=k*dt_hours)
    return dict(onset_status='never_crossed' if finite.all() else 'missing',onset_elapsed_hours=None,crossing_lower_hours=None,crossing_upper_hours=None)
