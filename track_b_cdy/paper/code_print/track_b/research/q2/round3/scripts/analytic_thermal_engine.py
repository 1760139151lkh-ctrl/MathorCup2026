"""Analytical 1D conductive challenger for hourly step boundary conditions.

The mechanical/water/damage equations are the frozen Q2R3 engine.  This module
only supplies the thermal tuple to its public simulate(thermal=...) argument.
No observations, event fitting or probability weights are introduced.
"""
from __future__ import annotations

import math

import numpy as np

from mechanism_engine import simulate


def erfc_array(values):
    """Use the standard-library scalar erfc, avoiding an additional dependency."""
    values = np.asarray(values, float)
    return np.fromiter((math.erfc(float(value)) for value in values.flat),
                       dtype=float, count=values.size).reshape(values.shape)


def step_kernel(nt, depth_m, alpha_m2_s, dt_hours=1.):
    """Semi-infinite Dirichlet step response; K[0]=0 by state0 convention."""
    depth, alpha = np.broadcast_arrays(np.atleast_1d(np.asarray(depth_m, float)),
                                      np.atleast_1d(np.asarray(alpha_m2_s, float)))
    if nt < 1 or dt_hours <= 0 or np.any(depth < 0) or np.any(alpha <= 0):
        raise ValueError("invalid time/depth/diffusivity")
    if not np.all(np.isfinite(depth)) or not np.all(np.isfinite(alpha)):
        raise ValueError("nonfinite thermal parameters")
    kernel = np.zeros((nt, depth.size))
    if nt > 1:
        denominator = 2*np.sqrt(np.arange(1, nt)[:, None] * dt_hours * 3600 * alpha[None, :])
        kernel[1:] = erfc_array(depth[None, :]/denominator)
    return kernel


def finite_step_kernel(nt, depth_m, alpha_m2_s, bottom_m, dt_hours=1., terms=12):
    """Finite0..L Dirichlet/no-flux step response, using a mirror expansion.

    cosh((L-z)q)/cosh(Lq) = sum_n(-1)^n *
        [exp(-(2nL+z)q) + exp(-(2(n+1)L-z)q)], q=sqrt(s/alpha).
    Divide by s for a unit step and invert each exponential to erfc.  The
    complementary paired form below avoids subtracting the main kernel when
    reporting the extremely small production-domain reflection correction.
    """
    depth, alpha = np.broadcast_arrays(np.atleast_1d(np.asarray(depth_m, float)),
                                      np.atleast_1d(np.asarray(alpha_m2_s, float)))
    if bottom_m <= 0 or np.any(depth > bottom_m) or terms < 1:
        raise ValueError("invalid finite thermal domain")
    kernel = step_kernel(nt, depth, alpha, dt_hours)
    correction = np.zeros_like(kernel)
    if nt > 1:
        denominator = 2*np.sqrt(np.arange(1, nt)[:, None] * dt_hours * 3600 * alpha[None, :])
        for n in range(1, terms+1):
            pair = (erfc_array((2*n*bottom_m-depth)[None, :]/denominator)
                    - erfc_array((2*n*bottom_m+depth)[None, :]/denominator))
            correction[1:] += (1 if n % 2 else -1) * pair
    return kernel+correction, correction


def linear_causal_convolution(increments, kernel):
    """Zero-padded FFT linear convolution, truncated to physical state times.

    nfft >= 2*nt-1 prevents circular wrap-around from future increments.  K0=0
    ensures forcing[i] first influences state[i+1], not state[i].
    """
    increments, kernel = np.asarray(increments, float), np.asarray(kernel, float)
    if increments.shape != kernel.shape or increments.ndim != 2:
        raise ValueError("thermal increments/kernel must have equal(nt,n) shape")
    nt = len(increments)
    nfft = 1 << (2*nt-2).bit_length()
    transformed = np.fft.rfft(increments, n=nfft, axis=0) * np.fft.rfft(kernel, n=nfft, axis=0)
    return np.fft.irfft(transformed, n=nfft, axis=0)[:nt], nfft


def thermal_transfer_analytic(air_c, parameters, dt_hours=1.):
    """Return (interface temperature, imposed surface temperature) at states.

    Boundary B[i]=min(air[i]+offset,0) drives [i,i+1).  Initial interior state
    is uniform Tinit.  dB0=B0-Tinit and dBj=Bj-Bj-1 for j>=1.  Neither the last
    boundary value nor any future perturbation can drive an earlier state.
    Production depths are strictly positive (0.5..20m); if z=0 is requested,
    state[k] uses the left boundary limit B[k-1], with state[0]=Tinit.
    """
    air = np.asarray(air_c, float)
    if air.ndim != 1 or len(air) < 1 or not np.isfinite(air).all():
        raise ValueError("finite nonempty one-dimensional air boundary required")
    initial = np.atleast_1d(np.asarray(parameters["initial_temp_c"], float))
    offset = np.atleast_1d(np.asarray(parameters["station_source_offset_c"], float))
    depth = np.atleast_1d(np.asarray(parameters["interface_depth_m"], float))
    alpha = np.atleast_1d(np.asarray(parameters["diffusivity_m2_s"], float))
    if not all(value.shape == initial.shape for value in [offset, depth, alpha]):
        raise ValueError("thermal parameter arrays must have one shared row shape")
    if not np.isfinite(initial).all() or not np.isfinite(offset).all():
        raise ValueError("nonfinite initial temperature or source offset")
    boundary = np.minimum(air[:, None]+offset[None, :], 0.)
    increments = np.empty_like(boundary)
    increments[0] = boundary[0]-initial
    increments[1:] = np.diff(boundary, axis=0)
    kernel = step_kernel(len(air), depth, alpha, dt_hours)
    response, _ = linear_causal_convolution(increments, kernel)
    temperature = initial[None, :]+response
    # At t0 no interval has elapsed. Restore the exact declared initial state;
    # all other pre-perturbation checks retain actual FFT round-off.
    temperature[0] = initial
    return temperature, boundary


def simulate_analytic(air_c, precip_mm_h, parameters, mechanism="S_T_H",
                      policy="linear_extension", dt_hours=1.,
                      drainage_feedback=True, damage_enabled=True):
    """Public Q3 wrapper: same frozen mechanical engine and criterion/censoring."""
    thermal = thermal_transfer_analytic(air_c, parameters, dt_hours)
    return simulate(air_c, precip_mm_h, parameters, mechanism=mechanism, policy=policy,
                    dt_hours=dt_hours, thermal=thermal,
                    drainage_feedback=drainage_feedback, damage_enabled=damage_enabled)


def reflection_temperature_bound(air_c, parameters, bottom_m=40., dt_hours=1.):
    """Conservative finite-Neumann versus half-space error, per parameter row.

    Mirror correction is an alternating series of positive decreasing erfc
    differences, hence 0 <= Kfinite-Ksemi <= erfc((2L-z)/(2sqrt(alpha*t))).
    Bound the convolution by this horizon maximum times sum(abs(dB)).  This
    remains a temperature-discretization bound, not a physical/model error.
    """
    air = np.asarray(air_c, float)
    initial = np.atleast_1d(np.asarray(parameters["initial_temp_c"], float))
    offset = np.atleast_1d(np.asarray(parameters["station_source_offset_c"], float))
    depth = np.atleast_1d(np.asarray(parameters["interface_depth_m"], float))
    alpha = np.atleast_1d(np.asarray(parameters["diffusivity_m2_s"], float))
    if bottom_m <= 0 or np.any(depth < 0) or np.any(depth > bottom_m) or dt_hours <= 0:
        raise ValueError("depth outside finite reflection-bound domain")
    boundary = np.minimum(air[:, None]+offset[None, :], 0.)
    increments = np.empty_like(boundary)
    increments[0] = boundary[0]-initial
    increments[1:] = np.diff(boundary, axis=0)
    # Last boundary is unused at the last output state (K0=0).
    total_variation = np.abs(increments[:-1]).sum(axis=0)
    horizon = (len(air)-1)*dt_hours*3600
    first_reflection = erfc_array((2*bottom_m-depth)/(2*np.sqrt(alpha*horizon))) if horizon > 0 else np.zeros_like(depth)
    return total_variation*first_reflection, total_variation, first_reflection
