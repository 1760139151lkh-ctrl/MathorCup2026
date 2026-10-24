"""Independent engineering checks for Q2R3, never an event validation.

Uses analytical values constructed independently of model outputs.  No network,
calibration, event label, inferred local material property, or probability prior.
Only its own JSON report is written; run with the original locked environment.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PACKET = HERE.parent
ENGINE_PATH = HERE / "mechanism_engine.py"
REPORT_PATH = PACKET / "results/independent_physics_review.json"
EXPECTED_ROOT = Path("/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parameters(**overrides):
    values = dict(theta_deg=30., density_kg_m3=2000., thickness_normal_m=10.,
                  bridge_fraction=.2, bridge_cohesion_kpa=200., rock_mu=.6,
                  initial_damage=.15, initial_temp_c=-3.,
                  diffusivity_m2_s=1.e-6, interface_depth_m=2.,
                  station_source_offset_c=0., connected_depth_m=10.,
                  storativity=.1, rain_multiplier=.5, melt_mm_deg_day=3.,
                  drainage_hours=12., drainage_damage_coupling=1.,
                  damage_rate_h_inv=.0002, damage_exponent=2.)
    values.update(overrides)
    return {k: np.atleast_1d(np.asarray(v, dtype=float)) for k, v in values.items()}


def close(actual, expected, atol=1e-11, rtol=1e-11):
    np.testing.assert_allclose(actual, expected, atol=atol, rtol=rtol)


def check_slab_stresses():
    p = parameters(theta_deg=[0., 30., 60.], density_kg_m3=[2000.] * 3,
                   thickness_normal_m=[10.] * 3)
    normal, driving = ENGINE.stresses(p)
    # 196.133 kPa is the weight per unit slab-plane area, h normal to plane.
    close(normal, [196.133, 196.133 * math.sqrt(3) / 2, 98.0665])
    close(driving, [0., 98.0665, 196.133 * math.sqrt(3) / 2])
    return {"normal_kpa": normal.tolist(), "driving_kpa": driving.tolist()}


def check_strength_formula():
    c, mu = ENGINE.joint_strength(np.array([-8., -2., -.5]))
    close(c, [641.3, 200.3, 90.05])
    close(mu, [2.10, .84, .525])
    cc, mm = ENGINE.joint_strength(np.array([-.5, -.49, 0.]), "thawed_rock_contact")
    close(cc, [90.05, 0., 0.]); close(mm, [.525, .60, .60])
    try:
        ENGINE.joint_strength(-2., "unregistered_policy")
    except ValueError:
        pass
    else:
        raise AssertionError("unregistered strength policy accepted")
    return {"temperatures_c": [-8, -2, -.5], "cohesion_kpa": c.tolist(),
            "friction_coefficient": mu.tolist(),
            "meaning": "formula transcription only; no local transfer validation"}


def check_force_balance():
    p = parameters(bridge_fraction=.3, bridge_cohesion_kpa=200., rock_mu=.6)
    d, temp, pressure = .1, -2., 40.
    result = ENGINE.resistance(p, [d], [temp], [pressure])
    normal = 2000 * 9.80665 * 10 * math.cos(math.pi / 6) / 1000
    driving = 2000 * 9.80665 * 10 * .5 / 1000
    cohesion = .9 * (.3 * 200 + .7 * 200.3)
    mu = .3 * .6 + .7 * .84
    resisting = cohesion + (normal - pressure) * mu
    close(result["resistance_kpa"], [resisting])
    close(result["failure_margin"], [(resisting - driving) / driving])
    # Above contact loss, the effective-normal friction term is zero.
    lifted = ENGINE.resistance(p, [d], [temp], [normal + 10])
    close(lifted["resistance_kpa"], [cohesion])
    assert not bool(lifted["contact_valid"][0])
    return {"normal_kpa": normal, "driving_kpa": driving,
            "cohesion_kpa": cohesion, "resistance_kpa": resisting}


def check_domain_and_monotonicity():
    # Choose a thickness giving exactly 200 kPa total normal stress.
    thickness = 200000 / (2000 * 9.80665 * math.cos(math.pi / 6))
    p = parameters(thickness_normal_m=thickness, bridge_fraction=0.)
    # Boundary equality is included; numerical tolerance is not hidden by this test.
    normal = float(ENGINE.stresses(p)[0][0])
    status = []
    for t, effective, expected in [(-8., 100., True), (-.5, 150., True),
                                    (-8.01, 150., False), (-.49, 150., False),
                                    (-2., 99., False), (-2., 401., False)]:
        r = ENGINE.resistance(p, [.5], [t], [normal - effective])
        assert bool(r["strength_domain"][0]) == expected
        status.append(dict(temperature_c=t, effective_kpa=effective, in_domain=expected))
    temperatures = [-8., -5., -2., -.5]
    rr = [float(ENGINE.resistance(p, [.3], [t], [10.])["failure_margin"][0]) for t in temperatures]
    assert np.all(np.diff(rr) < 0), "warming should lower transferred strength in this domain"
    pressure_margins = [float(ENGINE.resistance(p, [.3], [-2.], [u])["failure_margin"][0])
                        for u in [0., 50., 100., normal, normal + 50]]
    assert np.all(np.diff(pressure_margins) <= 0)
    close(pressure_margins[-2], pressure_margins[-1])
    return {"domain_cases": status, "warming_margins": rr,
            "pressure_margins": pressure_margins}


def check_pressure_roots():
    thickness = 200000 / (2000 * 9.80665 * math.cos(math.pi / 6))
    p = parameters(thickness_normal_m=thickness, bridge_fraction=0.)
    root = ENGINE.resistance(p, [.8], [-2.], [0.])
    head = float(root["critical_head_m"][0])
    assert root["critical_head_status"][0] == "positive_pressure_root"
    critical = ENGINE.resistance(p, [.8], [-2.], [head * 9.80665])
    close(critical["failure_margin"], [0.], atol=2e-15)
    assert ENGINE.resistance(p, [.8], [-2.], [(head - .1) * 9.80665])["failure_margin"][0] > 0
    assert ENGINE.resistance(p, [.8], [-2.], [(head + .1) * 9.80665])["failure_margin"][0] < 0
    unreachable = ENGINE.resistance(p, [0.], [-2.], [0.])
    assert np.isnan(unreachable["critical_head_m"][0])
    assert unreachable["critical_head_status"][0] == "no_pressure_only_root"
    assert ENGINE.resistance(p, [0.], [-2.], [500.])["failure_margin"][0] > 0
    dry = ENGINE.resistance(parameters(theta_deg=60., thickness_normal_m=100., bridge_fraction=0.),
                            [.99], [-.5], [0.])
    assert dry["failure_margin"][0] < 0
    assert dry["critical_head_status"][0] == "dry_already_critical"
    # Exactly cohesion==driving is critical at complete effective-contact loss,
    # even though pressure cannot push it into a strictly negative margin.
    driving = float(ENGINE.stresses(p)[1][0])
    boundaryp = parameters(thickness_normal_m=thickness, bridge_fraction=1.,
                           bridge_cohesion_kpa=driving)
    boundary = ENGINE.resistance(boundaryp, [0.], [-2.], [200.])
    assert boundary["critical_head_status"][0] == "contact_limit_critical"
    close(boundary["failure_margin"], [0.], atol=2e-15)
    close(boundary["critical_head_m"], [200. / 9.80665])
    return {"reachable_head_m": head, "margin_at_root": float(critical["failure_margin"][0]),
            "unreachable_head_is_null": True, "dry_root_status": str(dry["critical_head_status"][0]),
            "cohesion_equals_drive_status": str(boundary["critical_head_status"][0])}


def check_censor_and_interpolation():
    cases = [([0., .1], "left_censored_already_unstable", None),
             ([-1., .1], "left_censored_already_unstable", None),
             ([1., .5, -.5], "interval_crossing", 3.),
             ([1., 0.], "interval_crossing", 2.),
             ([1., .5, .01], "never_crossed", None),
             ([float("nan"), -1.], "missing", None),
             ([1., float("nan"), -1.], "missing_before_possible_crossing", None),
             ([1., float("nan"), 1.], "missing", None),
             ([1., -1., float("nan")], "interval_crossing", 1.)]
    outputs = []
    for trajectory, expected_status, expected_onset in cases:
        result = ENGINE.classify_trajectory(trajectory, dt_hours=2.)
        assert result["onset_status"] == expected_status, result
        if expected_onset is None:
            assert result["onset_elapsed_hours"] is None
        else:
            close(result["onset_elapsed_hours"], expected_onset)
        outputs.append({"input": [x if math.isfinite(x) else None for x in trajectory], **result})
    return {"native_step_hours": 2., "cases": outputs,
            "rule": "first nonpositive margin, linear interpolation inside adjacent finite bracket; no persistence requirement"}


def check_thermal_constant():
    p = parameters(initial_temp_c=-3., interface_depth_m=7.)
    ti, surface = ENGINE.thermal_transfer(np.full(97, -3.), p, .5, .25)
    close(ti, -3.); close(surface, -3.)
    try:
        ENGINE.thermal_transfer([0., float("nan")], p)
    except ValueError:
        pass
    else:
        raise AssertionError("missing air temperature silently accepted")
    return {"max_error_c": float(np.max(np.abs(ti + 3.)))}


def check_thermal_step_convergence():
    p = parameters(initial_temp_c=-5., interface_depth_m=2., diffusivity_m2_s=1e-6)
    duration_h = 72.
    exact = -5. + 4. * math.erfc(2. / (2. * math.sqrt(1e-6 * duration_h * 3600)))
    runs = []
    for dt, dz in [(2., 1.), (1., .5), (.5, .25), (.25, .125)]:
        ti, _ = ENGINE.thermal_transfer(np.full(int(duration_h / dt) + 1, -1.), p, dt, dz, 20.)
        error = abs(float(ti[-1, 0]) - exact)
        runs.append(dict(dt_hours=dt, dz_m=dz, final_interface_c=float(ti[-1, 0]), abs_error_c=error))
        assert np.all(ti >= -5. - 1e-12) and np.all(ti <= -1. + 1e-12)
    errors = [r["abs_error_c"] for r in runs]
    assert np.all(np.diff(errors) < 0)
    assert errors[-1] < .002
    return {"analytic": "T_i+(T_s-T_i)erfc(z/(2sqrt(alpha*t)))", "exact_final_c": exact,
            "runs": runs, "boundary_qualification": "20 m bottom versus 1.02 m diffusion scale; semi-infinite approximation"}


def check_thermal_internal_substeps():
    # Nominal alpha*dt/dz^2=5.76 would be unstable without subcycling.
    p = parameters(initial_temp_c=-5., interface_depth_m=.5, diffusivity_m2_s=2e-6)
    ti, surf = ENGINE.thermal_transfer(np.full(25, 10.), p, 5., .25, 20.)
    assert np.all(np.isfinite(ti))
    assert np.all(ti >= -5. - 1e-12) and np.all(ti <= 1e-12)
    close(surf, 0.)
    assert np.all(np.diff(ti[:, 0]) >= -1e-12)
    return {"nominal_diffusion_number": 5.76,
            "max_internal_diffusion_number_declared": .45,
            "min_temp_c": float(ti.min()), "max_temp_c": float(ti.max())}


def check_reservoir_analytic():
    w0, incoming, tau, dt = .02, .01, 12., 7.3
    stored, drained, overflow = ENGINE.reservoir_step(w0, incoming, tau, 10., dt)
    exact = incoming * tau + (w0 - incoming * tau) * math.exp(-dt / tau)
    close(stored, exact); close(overflow, 0.)
    close(w0 + incoming * dt, stored + drained + overflow)
    decay, out, over = ENGINE.reservoir_step(w0, 0., tau, 10., dt)
    close(decay, w0 * math.exp(-dt / tau)); close(w0, decay + out + over)
    return {"uncapped_exact_storage_m": exact, "absolute_error_m": float(abs(stored - exact)),
            "mass_balance_error_m": float(abs(w0 + incoming * dt - stored - drained - overflow))}


def check_capped_reservoir_analytic():
    incoming, tau, capacity, final_h = .1, 2., .05, 20.
    hit = -tau * math.log(1 - capacity / (incoming * tau))
    exact_drain = incoming * hit - capacity + capacity / tau * (final_h - hit)
    exact_over = incoming * final_h - capacity - exact_drain
    runs = []
    for dt in [20., 5., 1., .5, .25, .125, .0625, .03125, .015625]:
        storage, drainage, overflow, max_closure = 0., 0., 0., 0.
        for i in range(round(final_h / dt)):
            storage, out, over = ENGINE.reservoir_step(storage, incoming, tau, capacity, dt)
            drainage += float(out); overflow += float(over)
            max_closure = max(max_closure, abs((i + 1) * incoming * dt - storage - drainage - overflow))
            assert -1e-15 <= storage <= capacity + 1e-15
        runs.append(dict(dt_hours=dt, drain_abs_error_m=abs(drainage - exact_drain),
                         overflow_abs_error_m=abs(overflow - exact_over),
                         max_budget_abs_m=float(max_closure)))
    assert max(r["max_budget_abs_m"] for r in runs) < 1e-12
    assert max(r["drain_abs_error_m"] for r in runs) < 1e-12
    assert max(r["overflow_abs_error_m"] for r in runs) < 1e-12
    # Capacity initially full with high input, including pre-existing surplus;
    # a recession from capacity; and zero capacity.  These exercise all branches
    # together so vectorized hit masks cannot silently mix the flow partitions.
    initial = np.array([.05, .10, .05, .02])
    inputs = np.array([.1, .1, 0., .1])
    capacities = np.array([.05, .05, .05, 0.])
    storage, drained, overflow = ENGINE.reservoir_step(initial, inputs, 2., capacities, 4.)
    recession = .05 * math.exp(-2.)
    close(storage, [.05, .05, recession, 0.])
    close(drained, [.10, .10, .05 - recession, 0.])
    close(overflow, [.30, .35, 0., .42])
    close(initial + inputs * 4., storage + drained + overflow)
    return {"continuous_capacity_analytic_hit_hours": hit, "continuous_exact_drain_m": exact_drain,
            "continuous_exact_overflow_m": exact_over, "runs": runs,
            "vector_boundary_cases": ["initially_at_capacity", "initial_surplus", "recession_from_capacity", "zero_capacity"],
            "qualification": "continuous overflow piecewise analytical solution agrees to floating-point precision for constant interval inputs and parameters"}


def check_simulation_units_and_ablation():
    p = parameters(initial_temp_c=-3., damage_rate_h_inv=0., connected_depth_m=30.)
    air, rain = np.full(25, 1.), np.full(25, 2.)
    h = ENGINE.simulate(air, rain, p, "S_H", damage_enabled=False, drainage_feedback=False)
    # 0.5*2 mm/hour rainfall plus 3 mm/degree/day melt at 1 degree C.
    input_per_hour = .5 * 2 / 1000 + 3 / 24000
    close(h["water_input_m"], [24 * input_per_hour])
    close(h["storage_m"][-1], [input_per_hour * 12 * (1 - math.exp(-24 / 12))])
    close(h["pressure_kpa"], 9.80665 * h["storage_m"] / .1)
    assert float(h["water_budget_max_abs_m"][0]) < 1e-12
    structural = ENGINE.simulate(air, rain, p, "S", damage_enabled=False)
    close(structural["failure_margin"], np.broadcast_to(structural["failure_margin"][0],
                                                       structural["failure_margin"].shape))
    close(structural["interface_temp_c"], -3.); close(structural["pressure_kpa"], 0.)
    dryp = parameters(melt_mm_deg_day=0., damage_rate_h_inv=0.)
    t = ENGINE.simulate(air, np.zeros(25), dryp, "S_T", damage_enabled=False)
    th = ENGINE.simulate(air, np.zeros(25), dryp, "S_T_H", damage_enabled=False)
    close(t["failure_margin"], th["failure_margin"])
    try:
        ENGINE.simulate(air, np.full(25, np.nan), p)
    except ValueError:
        pass
    else:
        raise AssertionError("missing rain silently became zero")
    return {"rain_plus_melt_input_m_per_hour": input_per_hour,
            "integrated_input_m": float(h["water_input_m"][0]),
            "max_budget_error_m": float(h["water_budget_max_abs_m"][0]),
            "dry_TH_equals_T": True, "damage_disabled_S_constant": True}


def check_damage_update():
    p = parameters(damage_rate_h_inv=.001, damage_exponent=2.)
    pre = ENGINE.resistance(p, [.15], [-3.], [0.])
    ratio = float(pre["driving_kpa"][0] / pre["resistance_kpa"][0])
    exact_first = 1 - .85 * math.exp(-.001 * min(ratio, 10.) ** 2 * 2)
    run = ENGINE.simulate(np.full(37, -3.), np.zeros(37), p, "S", dt_hours=2.)
    close(run["damage"][1], [exact_first])
    assert np.all(np.diff(run["damage"][:, 0]) >= 0)
    assert np.all(run["damage"] < 1)
    assert np.all(np.diff(run["failure_margin"][:, 0]) <= 0)
    return {"first_step_expected_damage": exact_first, "final_damage": float(run["damage"][-1, 0]),
            "qualification": "phenomenological accumulation occurs even at stable positive margin; no observation-calibrated creep law"}


def check_shared_time_step():
    p = parameters(melt_mm_deg_day=0., damage_rate_h_inv=0.)
    results = []
    for dt in [2., 1., .5, .25]:
        n = round(24 / dt) + 1
        out = ENGINE.simulate(np.full(n, 2.), np.full(n, 2.), p, "S_H", dt_hours=dt,
                              damage_enabled=False, drainage_feedback=False)
        results.append(float(out["failure_margin"][-1, 0]))
        close(out["water_input_m"], [.024])
    close(results, results[0])
    return {"dt_hours": [2., 1., .5, .25], "same_elapsed_24h_final_margin": results,
            "meaning": "constant forcing/no damage/no capacity contact analytic time-step consistency"}


CHECKS = [check_slab_stresses, check_strength_formula, check_force_balance,
          check_domain_and_monotonicity, check_pressure_roots, check_censor_and_interpolation,
          check_thermal_constant, check_thermal_step_convergence, check_thermal_internal_substeps,
          check_reservoir_analytic, check_capped_reservoir_analytic,
          check_simulation_units_and_ablation, check_damage_update, check_shared_time_step]


def main():
    if ROOT != EXPECTED_ROOT or Path.cwd().resolve() != ROOT:
        raise SystemExit("run only from assigned Q2 worktree")
    before = sha256(ENGINE_PATH)
    global ENGINE
    spec = importlib.util.spec_from_file_location("q2r3_independently_reviewed_engine", ENGINE_PATH)
    ENGINE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ENGINE)
    records = []
    for function in CHECKS:
        try:
            details = function()
            records.append(dict(check=function.__name__, status="passed", details=details))
        except Exception as exc:
            records.append(dict(check=function.__name__, status="failed", error=f"{type(exc).__name__}: {exc}"))
    after = sha256(ENGINE_PATH)
    failed = sum(r["status"] == "failed" for r in records)
    report = dict(review_version="q2r3-independent-physics-v2",
                  evaluation_stratum="numerical_benchmark",
                  generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  engine_path=ENGINE_PATH.relative_to(ROOT).as_posix(),
                  engine_sha256=before, engine_unchanged_during_review=before == after,
                  reviewer_role="independent_AI_subagent_engineering_review",
                  independent_observed_events=0, scientific_adoption="pending_team_review",
                  passed=len(records)-failed, failed=failed,
                  overall_status="passed" if not failed and before == after else "failed",
                  limitations=["Analytical/numerical properties of implemented conditional equations only.",
                               "No source geometry, thermal state, pressure, material, damage or onset calibrated or validated.",
                               "Strength transfer domain does not establish local material applicability.",
                               "Parameter scenarios are not probability samples."],
                  checks=records,
                  reproduction_command="track_b/.venv/bin/python track_b/research/q2/round3/scripts/validate_engine.py")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["overall_status", "passed", "failed", "engine_sha256"]}))
    if failed or before != after:
        for record in records:
            if record["status"] == "failed":
                print(f"{record['check']}: {record['error']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
