"""Full2048 analytical conductive challenger with offline paired numerical audit."""
from __future__ import annotations

import hashlib
import io
import json
import math
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from analytic_thermal_engine import (thermal_transfer_analytic, linear_causal_convolution,
                                     finite_step_kernel, reflection_temperature_bound)
from mechanism_engine import MODEL_IDS, MARGIN_DEFINITION, thermal_transfer, simulate, classify_trajectory
from run_experiments import RANGES, parameter_design, scenario_id

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / "track_b/research/q2/round3"
OUT = BASE / "results/analytic_thermal"
ENGINE_SHA = "bb6636d2d3f463c894cdc6bc1df9c7fd0f93f9b7a6f9aa6e8233113630afe14e"
BUNDLE = BASE / "exports/analytic_thermal_bundle.json"
VERSION = "q2-r3-analytic-erfc-thermal-v1"


def digest(path, role):
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), role=role)


def emit(path, raw):
    raw = raw.encode() if isinstance(raw, str) else raw
    assert path.resolve().is_relative_to(BASE)
    if path.exists():
        assert path.read_bytes() == raw, f"immutable analytical output differs: {path}"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def emit_json(path, data):
    emit(path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def emit_csv(path, frame):
    emit(path, frame.to_csv(index=False, lineterminator="\n"))


def bound_bundles():
    records = []
    for name in ["mechanism_bundle.json", "release_bundle.json", "mechanism_bundle_v2.json", "release_bundle_v2.json"]:
        path = BASE / "exports" / name
        obj = json.loads(path.read_text())
        records.append(digest(path, name))
        for item in obj["files"]:
            member = Path(item["path"])
            member = member if member.is_absolute() else ROOT/member
            assert member.stat().st_size == item["bytes"]
            assert hashlib.sha256(member.read_bytes()).hexdigest() == item["sha256"]
    return records


def numerical_benchmarks():
    p = dict(initial_temp_c=np.array([-5., -3.]), station_source_offset_c=np.array([0., 0.]),
             interface_depth_m=np.array([1., 2.]), diffusivity_m2_s=np.array([1e-6, 2e-6]))
    air = np.full(97, -1.)
    temperature, _ = thermal_transfer_analytic(air, p)
    direct_step = np.repeat(p["initial_temp_c"][None, :], len(air), axis=0)
    for k in range(1, len(air)):
        for j in range(2):
            direct_step[k, j] += (-1-p["initial_temp_c"][j])*math.erfc(p["interface_depth_m"][j]/(2*math.sqrt(p["diffusivity_m2_s"][j]*k*3600)))
    step_error = float(np.max(np.abs(temperature-direct_step)))
    assert step_error < 1e-11
    boundary = np.array([-4., -1., -3., -2., -6., 1., 2., -2., -1., -3., -4., 0., -5.])
    arbitrary, b = thermal_transfer_analytic(boundary, p)
    direct = np.repeat(p["initial_temp_c"][None, :], len(boundary), axis=0)
    delta = np.vstack([b[0]-p["initial_temp_c"], np.diff(b, axis=0)])
    for k in range(1, len(boundary)):
        for j in range(2):
            for i in range(k):
                direct[k, j] += delta[i, j]*math.erfc(p["interface_depth_m"][j]/(2*math.sqrt(p["diffusivity_m2_s"][j]*(k-i)*3600)))
    arbitrary_error = float(np.max(np.abs(arbitrary-direct)))
    assert arbitrary_error < 1e-11
    baseline = -4+np.sin(np.arange(97)/7)
    changed = baseline.copy(); changed[30:] += 4
    before, _ = thermal_transfer_analytic(baseline, p)
    after, _ = thermal_transfer_analytic(changed, p)
    causal_error = float(np.max(np.abs(before[:31]-after[:31])))
    assert causal_error < 1e-11
    assert float(np.max(np.abs(before[31:]-after[31:]))) > .01
    # z=0 interface sampling is the left boundary limit at the stored state.
    boundary_p = {**p, "interface_depth_m": np.array([0., 0.])}
    at_surface, bb = thermal_transfer_analytic(boundary, boundary_p)
    surface_error = float(np.max(np.abs(at_surface[1:]-bb[:-1])))
    assert surface_error < 1e-11
    matrix = []
    for bottom, depth, alpha, hours in [(2., 1., 2e-6, 168), (4., 3., 2e-6, 240), (40., 20., 2.1e-6, 2088)]:
        kernel, correction = finite_step_kernel(hours+1, [depth], [alpha], bottom, terms=12)
        kernel24, _ = finite_step_kernel(hours+1, [depth], [alpha], bottom, terms=24)
        assert np.max(np.abs(kernel-kernel24)) < 1e-13
        target = -5+4*kernel[-1, 0]
        previous_error = None
        for dt, dz in [(1., .125), (.25, .03125)]:
            pp = dict(initial_temp_c=np.array([-5.]), station_source_offset_c=np.array([0.]),
                      interface_depth_m=np.array([depth]), diffusivity_m2_s=np.array([alpha]))
            finite, _ = thermal_transfer(np.full(round(hours/dt)+1, -1.), pp, dt, dz, bottom)
            error = float(abs(finite[-1, 0]-target))
            if previous_error is not None:
                assert error < previous_error and error < .001
            previous_error = error
            matrix.append(dict(bottom_m=bottom, interface_depth_m=depth, alpha_m2_s=alpha, duration_hours=hours,
                               fd_dt_hours=dt, fd_dz_m=dz, finite_mirror_final_temperature_c=float(target),
                               fd_final_temperature_c=float(finite[-1, 0]), abs_fd_minus_mirror_c=error,
                               finite_minus_semi_kernel=float(correction[-1, 0]), evaluation_stratum="numerical_benchmark"))
    return dict(benchmark_version="analytic-erfc-engineering-v1", all_passed=True,
                step_erfc_max_abs_error_c=step_error, arbitrary_direct_vs_fft_max_abs_error_c=arbitrary_error,
                future_perturbation_prefix_max_abs_error_c=causal_error, surface_left_limit_max_abs_error_c=surface_error,
                causal_tolerance_c=1e-11, future_change_first_input_index=30, invariant_state_indices_inclusive=[0, 30],
                zero_padding_rule="nfft=next_power_of_two_at_least(2nt-1)",
                finite_mirror_fd_case_matrix=matrix, independent_observed_events=0), pd.DataFrame(matrix)


def main():
    clock = time.perf_counter()
    assert str(ROOT) == "<LOCAL_HOME>/Documents/MathorCup/worktrees/track-b-q2" and Path.cwd().resolve() == ROOT
    engine_path = BASE / "scripts/mechanism_engine.py"
    assert digest(engine_path, "engine")["sha256"] == ENGINE_SHA
    frozen = bound_bundles()
    cfg0 = json.loads((BASE / "config/experiment_v1.json").read_text())
    protocol = dict(experiment_id="q2r3-analytic-thermal-challenger-v1", parameter_points=256,
                    mechanism_groups=cfg0["models"], law_policies=cfg0["policies"], outcomes_expected=2048,
                    fixed_representatives=np.linspace(0, 255, 8, dtype=int).tolist(),
                    boundary="B[i]=min(air[i]+offset,0) on [i,i+1); state0=Tinit; positive source depths0.5..20m",
                    increments="dB0=B0-Tinit; dBj=Bj-Bj-1; K0=0, Kk=erfc(z/(2sqrt(alpha*k*3600)))",
                    convolution="linear causal via rfft/irfft with nfft>=2nt-1, keep firstnt outputs",
                    mechanical_engine_sha256=ENGINE_SHA, state_dt_hours=1.,
                    comparisons=["v2(0.125m) all2048 summaries and onset", "full0.0625m FD all2048 trajectories and onset", "direct analytical/causal and finite-mirror benchmarks"],
                    no_model_or_parameter_tuning_to_event_time=True, design_is_probability_prior=False,
                    independent_observed_events=0,
                    registration_scope="Protocol saved before full256 analytical/FD computation. Implementation-only finite mirror/FD cases were preflighted before this file; they are engineering checks, not independent scientific validation.")
    emit_json(OUT / "protocol.json", protocol)
    benchmark, matrix = numerical_benchmarks()
    emit_json(OUT / "numerical_benchmarks.json", benchmark)
    emit_csv(OUT / "finite_mirror_fd_cases.csv", matrix)
    print("Analytical direct/causal and finite-mirror benchmarks passed", flush=True)
    forcing_path = BASE / "results/refined_v2/forcing_hourly_v2.csv"
    forcing = pd.read_csv(forcing_path, parse_dates=["time_utc"])
    air, rain = forcing.station_air_temp_c.to_numpy(), forcing.precip_assumed_mm_h.to_numpy()
    assert len(air) == 2089 and np.array_equal(forcing.elapsed_hours, np.arange(len(air)))
    p = parameter_design(cfg0)
    assert np.all((p["interface_depth_m"] >= .5) & (p["interface_depth_m"] <= 20))
    assert np.all((p["diffusivity_m2_s"] >= .9e-6) & (p["diffusivity_m2_s"] <= 2.1e-6))
    cfg = {**cfg0, "experiment_id": protocol["experiment_id"], "solver_id": "analytic_halfspace_erfc_linear_causal_fft_v1",
           "thermal_dz_m": None, "thermal_domain": "semi_infinite; finite40m Neumann reflection explicitly bounded",
           "scenario_suffix": "analytic_erfc_v1", "state_dt_hours": 1., "fft_padding_min_samples": 2*len(air)-1,
           "fft_nfft": 1 << (2*len(air)-2).bit_length()}
    cfg.pop("dz_m")
    emit_json(OUT / "config.json", cfg)
    emit_csv(OUT / "forcing_hourly.csv", forcing)
    thermal = thermal_transfer_analytic(air, p)
    bounds, total_variation, reflection = reflection_temperature_bound(air, p, 40.)
    bound_frame = pd.DataFrame(dict(parameter_set_id=[f"q2r3-p{i:04d}" for i in range(256)],
                                    interface_depth_m=p["interface_depth_m"], diffusivity_m2_s=p["diffusivity_m2_s"],
                                    used_boundary_total_variation_c=total_variation,
                                    first_reflection_kernel_upper_bound=reflection,
                                    finite40_minus_halfspace_temperature_abs_bound_c=bounds,
                                    evaluation_stratum="numerical_benchmark"))
    emit_csv(OUT / "reflection_bounds.csv", bound_frame)
    print(f"Analytical all256 thermal complete; max finite40 reflection temperature bound={bounds.max():.6g}C", flush=True)
    print("Computing all256 FD reference dz0.0625m", flush=True)
    fd_thermal = thermal_transfer(air, p, 1., .0625, 40.)
    reps = np.asarray(protocol["fixed_representatives"])
    evaluation = int(np.flatnonzero(forcing.time_utc >= cfg["evaluation_start_utc"])[0])
    v2 = pd.read_csv(BASE / "results/refined_v2/scenario_outcomes.csv")
    v2_by_base = v2.set_index("base_scenario_id")
    existing_fd = pd.read_csv(BASE / "results/refined_v2/full_reference_checks.csv").set_index("base_scenario_id")
    records, parameter_records, tracks, pairs, diagnostic, minima = [], [], [], [], [], {}
    watermax = 0.
    model_ids = {mechanism: f"q2r3_{mechanism}_analytic_v1" for mechanism in cfg["models"]}
    for policy in cfg["policies"]:
        for mechanism in cfg["models"]:
            result = simulate(air, rain, p, mechanism, policy, thermal=thermal)
            fd = simulate(air, rain, p, mechanism, policy, thermal=fd_thermal)
            minima[(mechanism, policy)] = result["failure_margin"][evaluation:].min(axis=0)
            watermax = max(watermax, float(result["water_budget_max_abs_m"].max()))
            for i in range(256):
                base_id = scenario_id(i, mechanism, policy)
                sid = base_id+"__analytic_erfc_v1"
                trajectory = result["failure_margin"][:, i]
                onset = classify_trajectory(trajectory)
                fd_onset = classify_trajectory(fd["failure_margin"][:, i])
                old_fd = existing_fd.loc[base_id]
                assert fd_onset["onset_status"] == old_fd.reference_onset_status
                if fd_onset["onset_elapsed_hours"] is not None:
                    np.testing.assert_allclose(fd_onset["onset_elapsed_hours"], old_fd.reference_onset_elapsed_hours, atol=1e-8, rtol=0)
                late = classify_trajectory(trajectory[evaluation:])
                row = dict(scenario_id=sid, base_scenario_id=base_id, v2_scenario_id=base_id+"__thermal125v2",
                           parameter_set_id=f"q2r3-p{i:04d}", model_id=model_ids[mechanism], mechanism_id=mechanism,
                           law_policy=policy, experiment_id=cfg["experiment_id"], parameter_version=cfg["parameter_version"],
                           geometry_version="conditional_plane_slab_v1", evaluation_stratum="conditional_scenario",
                           data_role="scenario", forecast_input_mode="ideal_weather",
                           min_margin_all=float(trajectory.min()), min_margin_evaluation=float(trajectory[evaluation:].min()),
                           final_margin=float(trajectory[-1]), initial_margin=float(trajectory[0]),
                           final_interface_temp_c=float(result["interface_temp_c"][-1, i]),
                           final_damage=float(result["damage"][-1, i]), peak_pressure_kpa=float(result["pressure_kpa"][:, i].max()),
                           strength_domain_fraction=float(result["strength_domain"][:, i].mean()),
                           evaluation_onset_status=late["onset_status"], **onset)
                row["crossing_time_utc"] = (forcing.time_utc.iloc[0]+pd.Timedelta(hours=onset["onset_elapsed_hours"])).isoformat() if onset["onset_elapsed_hours"] is not None else None
                records.append(row)
                parameter_records.append(dict(scenario_id=sid, base_scenario_id=base_id, parameter_set_id=f"q2r3-p{i:04d}",
                                              model_id=model_ids[mechanism], mechanism_id=mechanism, law_policy=policy,
                                              parameter_version=cfg["parameter_version"], geometry_version="conditional_plane_slab_v1",
                                              design_role="space_filling_not_probability", prior_weight=None,
                                              **{key: float(value[i]) for key, value in p.items()}))
                v2row = v2_by_base.loc[base_id]
                adiff = trajectory-fd["failure_margin"][:, i]
                both_fd = onset["onset_elapsed_hours"] is not None and fd_onset["onset_elapsed_hours"] is not None
                both_v2 = onset["onset_elapsed_hours"] is not None and pd.notna(v2row.onset_elapsed_hours)
                branch_mismatch = (result["interface_temp_c"][:, i] > -.5) != (fd["interface_temp_c"][:, i] > -.5)
                pairs.append(dict(scenario_id=sid, base_scenario_id=base_id, parameter_set_id=f"q2r3-p{i:04d}",
                                  mechanism_id=mechanism, law_policy=policy,
                                  analytic_onset_status=onset["onset_status"], analytic_onset_elapsed_hours=onset["onset_elapsed_hours"],
                                  analytic_crossing_lower_hours=onset["crossing_lower_hours"], analytic_crossing_upper_hours=onset["crossing_upper_hours"],
                                  fd0625_onset_status=fd_onset["onset_status"], fd0625_onset_elapsed_hours=fd_onset["onset_elapsed_hours"],
                                  fd0625_crossing_lower_hours=fd_onset["crossing_lower_hours"], fd0625_crossing_upper_hours=fd_onset["crossing_upper_hours"],
                                  v2_onset_status=v2row.onset_status, v2_onset_elapsed_hours=v2row.onset_elapsed_hours,
                                  abs_analytic_minus_fd_onset_hours=abs(onset["onset_elapsed_hours"]-fd_onset["onset_elapsed_hours"]) if both_fd else None,
                                  signed_analytic_minus_fd_onset_hours=onset["onset_elapsed_hours"]-fd_onset["onset_elapsed_hours"] if both_fd else None,
                                  abs_analytic_minus_v2_onset_hours=abs(onset["onset_elapsed_hours"]-v2row.onset_elapsed_hours) if both_v2 else None,
                                  fd_onset_category_changed=onset["onset_status"] != fd_onset["onset_status"],
                                  v2_onset_category_changed=onset["onset_status"] != v2row.onset_status,
                                  max_abs_margin_analytic_minus_fd=float(np.abs(adiff).max()),
                                  final_margin_delta_analytic_minus_fd=float(adiff[-1]),
                                  evaluation_min_margin_delta_analytic_minus_fd=float(trajectory[evaluation:].min()-fd["failure_margin"][evaluation:, i].min()),
                                  final_margin_delta_analytic_minus_v2=float(trajectory[-1]-v2row.final_margin),
                                  evaluation_min_margin_delta_analytic_minus_v2=float(trajectory[evaluation:].min()-v2row.min_margin_evaluation),
                                  max_abs_interface_temperature_analytic_minus_fd_c=float(np.abs(result["interface_temp_c"][:, i]-fd["interface_temp_c"][:, i]).max()),
                                  thaw_branch_mismatch_hours=int(branch_mismatch.sum()) if policy == "thawed_rock_contact" else 0,
                                  evaluation_stratum="numerical_benchmark"))
            for i in reps:
                base_id = scenario_id(i, mechanism, policy)
                track = pd.DataFrame(dict(scenario_id=base_id+"__analytic_erfc_v1", base_scenario_id=base_id,
                                          model_id=model_ids[mechanism], mechanism_id=mechanism, law_policy=policy,
                                          time_utc=forcing.time_utc, elapsed_hours=forcing.elapsed_hours,
                                          failure_margin=result["failure_margin"][:, i], margin_definition=MARGIN_DEFINITION,
                                          interface_temp_c=result["interface_temp_c"][:, i], damage=result["damage"][:, i],
                                          storage_m=result["storage_m"][:, i], pressure_kpa=result["pressure_kpa"][:, i],
                                          strength_in_lab_domain=result["strength_domain"][:, i], critical_head_m=result["critical_head_m"][:, i],
                                          data_role="scenario", forecast_input_mode="ideal_weather", evaluation_stratum="conditional_scenario",
                                          physical_phase="initiation", parameter_version=cfg["parameter_version"], geometry_version="conditional_plane_slab_v1",
                                          available_time=None, onset_status_whole_run=classify_trajectory(result["failure_margin"][:, i])["onset_status"]))
                track["forcing_cutoff_utc"] = forcing.time_utc.shift(1)
                tracks.append(track)
            if mechanism == "S_T_H":
                for i in [52, 107, 227]:
                    diagnostic.append(pd.DataFrame(dict(parameter_set_id=f"q2r3-p{i:04d}", mechanism_id=mechanism,
                                                        law_policy=policy, time_utc=forcing.time_utc, elapsed_hours=forcing.elapsed_hours,
                                                        analytic_margin=result["failure_margin"][:, i], fd0625_margin=fd["failure_margin"][:, i],
                                                        analytic_temp_c=result["interface_temp_c"][:, i], fd0625_temp_c=fd["interface_temp_c"][:, i])))
            print(f"Analytical+FD paired complete {policy} {mechanism}", flush=True)
    outcomes, parameters, pair_frame = pd.DataFrame(records), pd.DataFrame(parameter_records), pd.DataFrame(pairs)
    assert len(outcomes) == 2048
    emit_csv(OUT / "scenario_outcomes.csv", outcomes); emit_csv(OUT / "parameter_ensemble.csv", parameters)
    emit_csv(OUT / "paired_v2_fd0625.csv", pair_frame)
    emit_csv(OUT / "diagnostic_traces.csv", pd.concat(diagnostic, ignore_index=True))
    memory = io.BytesIO()
    pd.concat(tracks, ignore_index=True).to_parquet(memory, index=False, compression="zstd")
    emit(OUT / "state_trajectories.parquet", memory.getvalue())
    competition = []
    for (mechanism, policy), group in outcomes.groupby(["mechanism_id", "law_policy"], sort=False):
        competition.append(dict(mechanism_id=mechanism, model_id=model_ids[mechanism], law_policy=policy,
                                n_parameter_sets=len(group), interval_crossing_n=int((group.onset_status == "interval_crossing").sum()),
                                left_censored_n=int(group.onset_status.str.startswith("left_censored").sum()),
                                never_crossed_n=int((group.onset_status == "never_crossed").sum()),
                                missing_n=int(group.onset_status.str.contains("missing").sum()),
                                median_min_margin=float(group.min_margin_evaluation.median()),
                                p05_min_margin=float(group.min_margin_evaluation.quantile(.05)), p95_min_margin=float(group.min_margin_evaluation.quantile(.95)),
                                wholly_lab_domain_n=int((group.strength_domain_fraction == 1).sum()),
                                mean_lab_domain_fraction=float(group.strength_domain_fraction.mean()), independent_validation_events=0,
                                design_fraction_is_probability=False, evaluation_stratum="conditional_scenario"))
    emit_csv(OUT / "model_comparison.csv", pd.DataFrame(competition))
    sensitivity = []
    for (mechanism, policy), response in minima.items():
        x = np.column_stack([p[key] if RANGES[key][2] == "linear" else np.log(p[key]) for key in RANGES])
        z = (x-x.mean(0))/x.std(0); y = (response-response.mean())/response.std()
        beta = np.linalg.lstsq(np.column_stack([np.ones(256), z]), y, rcond=None)[0][1:]
        for j, key in enumerate(RANGES):
            sensitivity.append(dict(mechanism_id=mechanism, law_policy=policy, parameter=key,
                                    spearman_rho=float(pd.Series(p[key]).rank().corr(pd.Series(response).rank())),
                                    standardized_linear_coefficient=float(beta[j]), n_joint_design=256,
                                    evaluation_stratum="conditional_scenario", interpretation="space-filling design association, no empirical/causal posterior"))
    emit_csv(OUT / "joint_sensitivity.csv", pd.DataFrame(sensitivity))
    interaction = minima[("S_T_H", "linear_extension")]-minima[("S_T", "linear_extension")]-minima[("S_H", "linear_extension")]+minima[("S", "linear_extension")]
    emit_csv(OUT / "interaction.csv", pd.DataFrame(dict(parameter_set_id=[f"q2r3-p{i:04d}" for i in range(256)], contrast_of_minima_STH_minus_ST_minus_SH_plus_S=interaction)))
    contract = json.loads((BASE / "results/mechanism_contract.json").read_text())
    contract.update(contract_version="q2r3-analytic-erfc-contract-v1", model_ids=model_ids,
                    engine_entry="scripts/analytic_thermal_engine.py: simulate_analytic(air_c,precip_mm_h,parameters,mechanism,policy,dt_hours=1)",
                    thermal_entry="thermal_transfer_analytic(air_c,parameters,dt_hours=1) returns frozen-engine-compatible(temperature,boundary)",
                    scenario_suffix="analytic_erfc_v1", base_scenario_join="base_scenario_id joins v1/v2 and release-geometry-v2; release states unchanged, use this model version onset/censoring when combined",
                    thermal_domain="semi_infinite; finite40m Neumann difference bounded using boundary total variation",
                    time0_surface_convention="positive depth: specified uniform interior initial state; if depth0 requested, states k>=1 use B[k-1] left limit",
                    state_trajectory_scope="8 fixed representatives x4 mechanisms x2 policies; all256 parameters/outcomes retained per group",
                    engine_sha256=ENGINE_SHA, source_available_time=None)
    contract["equations"] = ["T[k]=Tinit+sum_{j=0}^{k-1}dB[j]*erfc(z/(2sqrt(alpha*(k-j)*3600))); B=min(air+offset,0)" if str(item).startswith("dT/dt=") else item for item in contract["equations"]]
    emit_json(OUT / "mechanism_contract.json", contract)

    def maximum(column):
        good = pair_frame[column].dropna()
        if not len(good):
            return None
        row = pair_frame.loc[good.idxmax()]
        return dict(value=float(row[column]), base_scenario_id=row.base_scenario_id, mechanism_id=row.mechanism_id, law_policy=row.law_policy)

    bound_i = int(bounds.argmax())
    parameter_bound = float(math.erfc(60/(2*math.sqrt(2.1e-6*2088*3600))))
    summary = dict(analytic_version=VERSION, evaluation_stratum="conditional_scenario", input_version=json.loads((BASE / "exports/mechanism_bundle.json").read_text())["input_version"],
                   frozen_bundles_before_and_after=frozen, engine_sha256=ENGINE_SHA,
                   benchmark_all_passed=True, full_parameter_sets=256, scenario_outcomes=len(outcomes), representative_state_rows=133696,
                   native_state_dt_hours=1., time_origin_utc=forcing.time_utc.iloc[0].isoformat(),
                   forcing_used_sha256=digest(forcing_path, "forcing")["sha256"],
                   fft_nfft=cfg["fft_nfft"], fft_min_linear_padding=cfg["fft_padding_min_samples"],
                   max_actual_reflection_temperature_bound_c=float(bounds.max()), max_bound_parameter_set_id=f"q2r3-p{bound_i:04d}",
                   max_actual_reflection_kernel_bound=float(reflection.max()),
                   conservative_parameter_box_first_reflection_kernel_bound=parameter_bound,
                   max_boundary_total_variation_c=float(total_variation.max()),
                   box_kernel_times_max_actual_boundary_tv_bound_c=float(parameter_bound*total_variation.max()),
                   finite_bound_scope="max over supplied256 actual parameter+boundary columns, horizon2088h, L40m; box bound uses z20/alpha2.1e-6",
                   analytic_status_counts=outcomes.onset_status.value_counts().to_dict(),
                   finite_analytic_fd_onset_pairs=int(pair_frame.abs_analytic_minus_fd_onset_hours.notna().sum()),
                   finite_analytic_v2_onset_pairs=int(pair_frame.abs_analytic_minus_v2_onset_hours.notna().sum()),
                   fd_onset_category_changes=int(pair_frame.fd_onset_category_changed.sum()),
                   v2_onset_category_changes=int(pair_frame.v2_onset_category_changed.sum()),
                   max_analytic_fd_onset_difference=maximum("abs_analytic_minus_fd_onset_hours"),
                   max_analytic_v2_onset_difference=maximum("abs_analytic_minus_v2_onset_hours"),
                   max_analytic_fd_margin_difference=maximum("max_abs_margin_analytic_minus_fd"),
                   max_analytic_fd_temp_difference=maximum("max_abs_interface_temperature_analytic_minus_fd_c"),
                   thaw_branch_mismatch_hours=int(pair_frame.thaw_branch_mismatch_hours.sum()), max_water_budget_error_m=watermax,
                   probabilities_assigned=False, independent_observed_events=0, scientific_adoption="pending_team_review",
                   runtime_stack=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__))
    emit_json(OUT / "summary.json", summary)
    doc = f"""# 解析热传导竞争路线

本路线完成原256参数×4机制×2强度策略=2048情景和8预定代表×8组×2089小时=133696行状态。原引擎SHA `{ENGINE_SHA}`；只通过`simulate(thermal=...)`替换热传导模块，1h水/损伤状态步长、参数、气象边界、判据和删失规则不变，不进行事件时刻拟合。

## 方程、因果性与边界

半无限一维热传导，初始均匀Tinit，表面B[i]=min(air[i]+offset,0)于[i,i+1)保持。令ΔB0=B0−Tinit，ΔBj=Bj−Bj−1，K0=0，Kk=erfc[z/(2√(αk·3600))]，则T[k]=Tinit+Σ(j<k)ΔB[j]K[k−j]。使用零填充FFT线性卷积，nt=2089，nfft={cfg['fft_nfft']}≥2nt−1={cfg['fft_padding_min_samples']}，禁止循环卷积或未来边界泄漏。实际深度0.5–20m严格大于0；若调用者给z=0，state[k]取边界B[k−1]左极限，state0保留指定初值。公开可调用`thermal_transfer_analytic`和`simulate_analytic`均在`analytic_thermal_engine.py`。

独立工程检查：阶跃对erfc最大温差{benchmark['step_erfc_max_abs_error_c']:.5g}°C；任意预设分段边界直接逐项和对FFT误差{benchmark['arbitrary_direct_vs_fft_max_abs_error_c']:.5g}°C；只改t≥30h的未来输入时，state0..30最大差{benchmark['future_perturbation_prefix_max_abs_error_c']:.5g}°C，均在1e−11°C容差内。镜像有限域解与细FD的矩阵见`finite_mirror_fd_cases.csv`，包括可见反射的小域测试和生产域极端测试；不是本地事件科学验证。

## 40m无通量边界与半无限解的差

Laplace传递比cosh((L−z)q)/cosh(Lq)=[exp(−zq)+exp(−(2L−z)q)]/[1+exp(−2Lq)]，q=√(s/α)。展开几何级数并对阶跃除s，逆变换得到Σ(n≥0)(−1)^n[erfc((2nL+z)/a)+erfc((2(n+1)L−z)/a)]，a=2√(αt)。与半无限核相减后可成对写作Σ(n≥1)(−1)^(n−1)[erfc((2nL−z)/a)−erfc((2nL+z)/a)]。括号非负且随n递减，因此修正位于0与首项之间，并小于erfc((2L−z)/a)。任意分段边界的温差绝对值上界为这一末时核上界乘Σ|ΔB|；包含初始表面跃变，末行未作用的边界不计。

实际256参数/实际边界的最大温差上界 **{float(bounds.max()):.9g}°C**，参数q2r3-p{bound_i:04d}。参数盒z≤20m、α≤2.1e−6m²/s、t≤2088h、L=40m的首反射核上界{parameter_bound:.9g}，乘实际最大边界总变差{float(total_variation.max()):.9g}°C后上界{float(parameter_bound*total_variation.max()):.9g}°C。修正小于浮点舍入，代码仍独立保存反射核修正及界，未将相减得到0误称数学上等于0。这个界只说明两种理想热边界的差，不约束真实源区边界、热通道、相变、热对流或观测误差。

## 全量竞争和数值比较

解析对0.0625m有限差分的有限启动时间对{summary['finite_analytic_fd_onset_pairs']}/2048，类别改变{summary['fd_onset_category_changes']}；对已发布0.125m v2的有限时间对{summary['finite_analytic_v2_onset_pairs']}/2048，类别改变{summary['v2_onset_category_changes']}。最大启动差分别{summary['max_analytic_fd_onset_difference']['value']:.9g}h与{summary['max_analytic_v2_onset_difference']['value']:.9g}h，逐情景及原生小时首越阈区间见`paired_v2_fd0625.csv`。解析对0.0625m全期逐时最大裕度差{summary['max_analytic_fd_margin_difference']['value']:.9g}；thaw挑战分支切换不一致合计{summary['thaw_branch_mismatch_hours']}个情景小时。不要因启动类别相同就声称时刻已收敛。

此解析模块可作为所声明线性热传导方程的数值参考，避免热空间网格误差；水压、损伤和强度反馈仍按1h状态离散，不是整套耦合系统解析解。局部温压、物源/结构面、站源映射与损伤材料仍为条件情景或外部迁移。冰填石灰岩快速剪切实验的温/应力域标志不证明当地材料适用；升温穿越−0.5°C的thaw强度切换仍是未校准挑战假设。没有独立事件、概率先验或实测启动真值，后越阈计算只是反事实诊断。

新scenario_id加`__analytic_erfc_v1`，`base_scenario_id`对应v1/v2及已有释放几何v2；释放体积、厚度、组分、几何不改。与本路线组合时采用本模型版本的onset/censor，不能把旧释放表onset当第二个真值。最终科学采用由队员联合审视。

实际离线复跑命令：

```sh
track_b/.venv/bin/python track_b/research/q2/round3/scripts/run_analytic_thermal.py
```

协议先于全量求解保存在`results/analytic_thermal/protocol.json`；协议明确披露实现前期镜像/FD工程预检，未当独立科学验证。入口`exports/analytic_thermal_bundle.json`逐文件绑定，无自包含；所有旧包原字节保留。
"""
    emit(BASE / "ANALYTIC_THERMAL.md", doc)
    paths = [(OUT/name, name) for name in ["protocol.json", "config.json", "forcing_hourly.csv", "numerical_benchmarks.json", "finite_mirror_fd_cases.csv",
             "reflection_bounds.csv", "scenario_outcomes.csv", "parameter_ensemble.csv", "state_trajectories.parquet", "model_comparison.csv",
             "paired_v2_fd0625.csv", "diagnostic_traces.csv", "joint_sensitivity.csv", "interaction.csv", "mechanism_contract.json", "summary.json"]]
    paths += [(BASE/"scripts/analytic_thermal_engine.py", "callable_analytic_thermal_wrapper"),
              (Path(__file__).resolve(), "analytic_reproduction_script"), (engine_path, "frozen_mechanical_engine"),
              (BASE/"scripts/run_experiments.py", "frozen_parameter_design_source"), (BASE/"ANALYTIC_THERMAL.md", "methods_results_limits")]
    bundle = dict(bundle_version=VERSION, producer_question="q2", input_version=summary["input_version"], evaluation_stratum="conditional_scenario",
                  files=[digest(path, role) for path, role in paths],
                  limitations=["All source models conditional; no local event calibration, probabilities or verified initiation time.",
                               "Analytical solution is for linear half-space thermal conduction with the specified hourly step boundary only.",
                               "Finite40m Neumann replacement bounded by actual boundary total variation; thermal advection, enthalpy/melting and unmeasured boundary physics remain excluded.",
                               "Hourly water/damage/strength coupling retains time-discretization uncertainty; analytic thermal does not solve the whole coupled system exactly.",
                               "Initial instability is left-censored; no-start/missing retained. base_scenario_id maps prior mechanism/release versions without rewriting them.",
                               "Mamot transfer/thaw policy/source geometry remain scientific assumptions requiring team review."])
    assert bound_bundles() == frozen
    emit_json(BUNDLE, bundle)
    print(json.dumps(dict(bundle=digest(BUNDLE, "analytic_thermal"), max_reflection_bound_c=float(bounds.max()),
                          max_fd_time_difference=summary["max_analytic_fd_onset_difference"],
                          max_v2_time_difference=summary["max_analytic_v2_onset_difference"],
                          fd_category_changes=summary["fd_onset_category_changes"], runtime_seconds=time.perf_counter()-clock)), flush=True)


if __name__ == "__main__":
    main()
