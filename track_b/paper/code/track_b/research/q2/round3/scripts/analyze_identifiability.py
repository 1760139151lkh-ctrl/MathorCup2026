"""Prospective local identifiability benchmark, registered here before calculation.

Design: use mechanism_engine.resistance at one fixed, in-domain engineering state.
Four unknowns are normalized by explicitly chosen parameter scales. Differentiate
the prescribed observation operators by central finite differences, standardize
by prescribed measurement noise, and compare SVD/rank for five nested designs.
There are no measured observations, fitted event times or independent events.
Repeated margin measurements mean hypothetical independent instrument repeats
at an unchanged state; their information gain is conditional on that assumption.

Only outputs results/identifiability.csv and identifiability_details.json.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
ENGINE = HERE / "mechanism_engine.py"
BASELINE = "904d7257b899b9f71d1ac9e0eab7479e459eab52"

PARAMETERS = ["bridge_cohesion_kpa", "initial_damage", "head_m", "interface_temperature_c"]
UNITS = ["kPa", "1", "m", "degC"]
CENTER = np.array([800.0, 0.30, 5.0, -2.5])
SCALES = np.array([500.0, 0.20, 5.0, 1.0])
NOISE = {"failure_margin": 0.05, "interface_temperature_c": 0.10,
         "pressure_kpa": 5.0, "damage": 0.05}
FIXED = {"theta_deg": 55.0, "density_kg_m3": 2400.0,
         "thickness_normal_m": 20.0, "bridge_fraction": 0.20,
         "rock_mu": 0.60}
DESIGNS = [
    ("margin_single", ["failure_margin"]),
    ("margin_24_fixed_condition_repeats", ["failure_margin"] * 24),
    ("margin_plus_temperature", ["failure_margin", "interface_temperature_c"]),
    ("margin_plus_temperature_pressure", ["failure_margin", "interface_temperature_c", "pressure_kpa"]),
    ("margin_plus_temperature_pressure_damage", ["failure_margin", "interface_temperature_c", "pressure_kpa", "damage"]),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_engine():
    spec = importlib.util.spec_from_file_location("q2_identifiability_engine", ENGINE)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


def main():
    engine_hash = digest(ENGINE)
    engine = load_engine()

    def physical_state(x):
        p = {**FIXED, "bridge_cohesion_kpa": float(x[0])}
        state = engine.resistance(p, float(x[1]), float(x[3]), engine.G * float(x[2]))
        return {k: (bool(v) if np.asarray(v).dtype == bool else
                    str(v) if np.asarray(v).dtype.kind in "US" else float(v))
                for k, v in state.items()}

    def observe(x, names):
        state = physical_state(x)
        values = {"failure_margin": state["failure_margin"],
                  "interface_temperature_c": float(x[3]),
                  "pressure_kpa": float(engine.G * x[2]), "damage": float(x[1])}
        return np.array([values[name] for name in names])

    def jacobian(names, step):
        jac = np.empty((len(names), len(PARAMETERS)))
        noise = np.array([NOISE[name] for name in names])
        for j in range(len(PARAMETERS)):
            delta = np.zeros(len(PARAMETERS)); delta[j] = step * SCALES[j]
            jac[:, j] = (observe(CENTER + delta, names) - observe(CENTER - delta, names)) / (2 * step * noise)
        return jac

    base = physical_state(CENTER)
    assert base["strength_domain"] and base["contact_valid"]
    fb, damage, t = FIXED["bridge_fraction"], CENTER[1], CENTER[3]
    cj, muj = engine.joint_strength(t)
    unscaled_cohesion = fb * CENTER[0] + (1 - fb) * float(cj)
    analytic_margin = np.array([
        (1 - damage) * fb,
        -unscaled_cohesion,
        -engine.G * base["mu"],
        (1 - damage) * (1 - fb) * -73.5 + base["effective_kpa"] * (1 - fb) * -0.21,
    ]) / base["driving_kpa"] * SCALES / NOISE["failure_margin"]

    expected_ranks = [1, 1, 2, 3, 4]
    results, rows = [], []
    checks = []
    for (design_id, names), expected in zip(DESIGNS, expected_ranks):
        jac = jacobian(names, 1e-4)
        u, singular, vt = np.linalg.svd(jac, full_matrices=True)
        tol = 1e-10 * singular[0]
        rank = int((singular > tol).sum())
        singular_full = np.zeros(len(PARAMETERS)); singular_full[:len(singular)] = singular
        nonzero = singular[singular > tol]
        condition = float(nonzero[0] / nonzero[-1]) if rank == len(PARAMETERS) else None
        subspace_condition = float(nonzero[0] / nonzero[-1])
        perturbations = []
        for step in [1e-3, 1e-5]:
            other = jacobian(names, step)
            other_sv = np.linalg.svd(other, compute_uv=False)
            other_rank = int((other_sv > other_sv[0] * 1e-10).sum())
            perturbations.append({"normalized_step": step, "rank": other_rank,
                                  "max_abs_jacobian_difference": float(np.max(np.abs(other - jac)))})
            assert other_rank == expected
        assert rank == expected
        error = float(np.max(np.abs(jac[0] - analytic_margin)))
        assert error < 1e-7
        check = {"design_id": design_id, "expected_rank": expected, "actual_rank": rank,
                 "analytic_margin_jacobian_max_abs_error": error,
                 "finite_difference_step_checks": perturbations}
        checks.append(check)
        record = {"design_id": design_id, "observation_names": names,
                  "observation_center_values": observe(CENTER, names).tolist(),
                  "standardized_jacobian": jac.tolist(),
                  "singular_values_returned_by_svd": singular.tolist(),
                  "parameter_space_singular_values_padded": singular_full.tolist(),
                  "rank": rank, "rank_relative_tolerance": 1e-10,
                  "nullity": len(PARAMETERS) - rank,
                  "nullspace_directions_normalized_parameters": vt[rank:].tolist(),
                  "condition_full_parameter_space": condition,
                  "condition_status": "finite" if condition is not None else "infinite_rank_deficient",
                  "condition_identified_subspace": subspace_condition,
                  "evaluation_stratum": "numerical_benchmark", "independent_events": 0}
        results.append(record)
        meanings = {
            1: "one local mechanical resistance combination only; three-dimensional parameter nullspace",
            2: "interface temperature separately constrained; cohesion-damage-head remain compensating",
            3: "temperature and pressure constrained; surviving product (1-D)*(fb*cb+(1-fb)*cj)",
            4: "four parameters locally distinguishable only given ideal direct damage, known geometry/fb/rock_mu and correct law",
        }
        rows.append({"experiment_id": "q2r3_local_identifiability_v1", "design_id": design_id,
                     "model_id": engine.MODEL_IDS["S_T_H"], "mechanism_id": "S_T_H",
                     "evaluation_stratum": "numerical_benchmark", "independent_events": 0,
                     "data_role": "scenario", "n_observations": len(names),
                     "n_unknown_parameters": len(PARAMETERS), "rank": rank,
                     "nullity": len(PARAMETERS)-rank,
                     "singular_values_noise_and_parameter_scaled": json.dumps(singular_full.tolist()),
                     "condition_full_parameter_space": "" if condition is None else condition,
                     "condition_status": record["condition_status"],
                     "condition_identified_subspace": subspace_condition,
                     "normalization": "d(y/noise)/d((parameter-center)/scale); all scales and noise prescribed",
                     "identifiable_combination": meanings[rank],
                     "most_valuable_added_measurements": "independent interface temperature and hydraulic head; calibrated damage/bridge constraint needed to separate cohesion-damage product",
                     "limitations": "local Jacobian only; fixed known geometry and fractions; no local observations or likelihood calibration; unchanged repeats add precision only under independent noise",
                     "engine_sha256": engine_hash})

    # Exact compensation pairs for this engine's fixed-state algebra. All remain
    # in-domain and retain the same original driving stress and failure margin.
    cases = [("specified_center", CENTER.copy())]
    x = CENTER.copy(); x[1] = 0.50
    x[0] = (base["cohesion_kpa"] / (1-x[1]) - (1-fb)*float(cj)) / fb
    cases.append(("higher_bridge_cohesion_with_more_damage", x))
    x = CENTER.copy(); x[2] = 8.0
    required_cohesion = base["cohesion_kpa"] + engine.G * (x[2]-CENTER[2]) * base["mu"]
    x[0] = (required_cohesion/(1-x[1]) - (1-fb)*float(cj)) / fb
    cases.append(("higher_bridge_cohesion_with_more_head", x))
    x = CENTER.copy(); x[3] = -2.0
    cj_new, mu_new = engine.joint_strength(x[3])
    mu_mixed_new = fb*FIXED["rock_mu"] + (1-fb)*float(mu_new)
    required_cohesion = base["resistance_kpa"] - base["effective_kpa"] * mu_mixed_new
    x[0] = (required_cohesion/(1-x[1]) - (1-fb)*float(cj_new)) / fb
    cases.append(("higher_bridge_cohesion_with_warmer_joint", x))
    pairs = []
    for label, x in cases:
        state = physical_state(x)
        assert state["strength_domain"] and state["contact_valid"]
        difference = state["failure_margin"] - base["failure_margin"]
        assert abs(difference) < 1e-12
        pairs.append({"case_id": label, "parameters": dict(zip(PARAMETERS, map(float,x))),
                      "state": state, "margin_difference_from_center": difference,
                      "evaluation_stratum": "numerical_benchmark", "independent_events": 0})

    details = {"experiment_id": "q2r3_local_identifiability_v1", "baseline_commit": BASELINE,
               "evaluation_stratum": "numerical_benchmark", "independent_events": 0,
               "data_role": "scenario", "event_id": None,
               "time_utc": None, "time_note": "fixed-state hypothetical experimental design, not an event observation",
               "input_version": {"engine_path": str(ENGINE.relative_to(ROUND.parents[3])), "engine_sha256": engine_hash,
                                 "script_sha256": digest(Path(__file__))},
               "parameter_order": PARAMETERS, "parameter_units": UNITS,
               "parameter_center": CENTER.tolist(), "parameter_scales": SCALES.tolist(),
               "fixed_known_parameters": FIXED, "prescribed_noise_standard_deviations": NOISE,
               "noise_status": "arbitrary prospective design values, independent Gaussian measurement standardization only; no noisy data generated or fitted",
               "finite_difference": {"method": "central", "normalized_step": 1e-4, "check_steps": [1e-3,1e-5]},
               "observation_definitions": {"failure_margin": engine.MARGIN_DEFINITION,
                   "interface_temperature_c": "hypothetical direct interface temperature",
                   "pressure_kpa": "hypothetical direct pressure, u=g*head with water density1000kg/m3",
                   "damage": "ideal direct model-state damage; actual damage proxy would require separate calibration"},
               "center_state": base, "designs": results, "exact_compensation_cases": pairs,
               "structural_analysis": {"surviving_combination_given_T_and_u": "C_eff=(1-D)*(fb*cb+(1-fb)*cj(T))",
                   "cohesion_damage_null_relation": "dcb=[fb*cb+(1-fb)*cj(T)]/[fb*(1-D)]*dD",
                   "cohesion_pressure_null_relation_at_fixed_D_and_T": "dcb=mu_mixed/[fb*(1-D)]*du",
                   "repeated_unchanged_conditions": "24 identical Jacobian rows retain rank1; singular value increases sqrt(24) only with independent noise and no shared model discrepancy",
                   "full_rank_scope": "local conditional identifiability of four unknowns only; not global uniqueness or practical field identifiability; allowing unknown fb/geometry/constitutive coefficients changes the result"},
               "validation": {"rank_expected_vector": expected_ranks, "all_rank_checks_passed": True,
                   "analytic_margin_jacobian": analytic_margin.tolist(), "finite_difference_checks": checks,
                   "same_margin_max_abs_error": max(abs(p["margin_difference_from_center"]) for p in pairs),
                   "all_compensation_cases_in_joint_domain": True},
               "limits": ["No local measured data, inverse fit, independent validation, event-time estimate or coverage claim",
                          "All parameter centers/scales/noise and measurement designs are prescribed numerical-benchmark choices",
                          "Rank depends on stated normalization/tolerance and local differentiability away from contact/domain transitions",
                          "Mamot brittle shear law transferred conditionally; not locally calibrated; added direct damage is idealized",
                          "Parameter compensation shows non-uniqueness, not likelihood or posterior probability"]}
    assert digest(ENGINE) == engine_hash, "engine changed during benchmark; rerun against stable version"
    with (ROUND/"results/identifiability.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (ROUND/"results/identifiability_details.json").write_text(json.dumps(details,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"rank_vector":[r["rank"] for r in results],
                      "full_design_condition_number":results[-1]["condition_full_parameter_space"],
                      "compensation_max_abs_margin_error":details["validation"]["same_margin_max_abs_error"],
                      "center_strength_domain":base["strength_domain"],"independent_events":0}))


if __name__ == "__main__":
    main()
