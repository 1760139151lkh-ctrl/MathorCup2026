"""Independent thermal-space refinement of the immutable Q2R3 v1 experiment.

Offline, same design/forcing/equations/hourly state axis. Never rewrites v1 or
release v2. Run from assigned worktree; every published v2 byte is compared on
recomputation. Runtime is printed, not embedded in deterministic artifacts.
"""
from __future__ import annotations

import hashlib
import io
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from mechanism_engine import MARGIN_DEFINITION, MODEL_IDS, classify_trajectory, simulate, thermal_transfer
from run_experiments import RANGES, parameter_design, scenario_id, take

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / "track_b/research/q2/round3"
OUT = BASE / "results/refined_v2"
ENGINE = BASE / "scripts/mechanism_engine.py"
ENGINE_SHA = "bb6636d2d3f463c894cdc6bc1df9c7fd0f93f9b7a6f9aa6e8233113630afe14e"
BUNDLE = BASE / "exports/mechanism_bundle_v2.json"
VERSION = "q2-r3-mechanism-thermal-refinement-v2"


def digest(path, role):
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), role=role)


def emit(path, raw):
    if not path.resolve().is_relative_to(BASE):
        raise ValueError("write outside assigned packet")
    raw = raw.encode() if isinstance(raw, str) else raw
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"immutable v2 differs; create another version: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def emit_json(path, value):
    emit(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def emit_csv(path, frame):
    emit(path, frame.to_csv(index=False, lineterminator="\n"))


def emit_parquet(path, frame):
    memory = io.BytesIO()
    frame.to_parquet(memory, index=False, compression="zstd")
    emit(path, memory.getvalue())


def parameter_inputs(cfg):
    p = parameter_design(cfg)
    parent = pd.read_csv(BASE / "results/parameter_ensemble.csv")
    target = parent[(parent.mechanism_id == "S") & (parent.law_policy == "linear_extension")]
    target = target.sort_values("parameter_set_id")
    assert len(target) == 256
    for name, values in p.items():
        np.testing.assert_allclose(values, target[name].to_numpy(), atol=1e-12, rtol=1e-12)
    return p


def compare_representatives(air, rain, p, reps, coarse, fine, coarse_dz, fine_dz):
    records = []
    subset = take(p, reps)
    for policy in ["linear_extension", "thawed_rock_contact"]:
        for mechanism in MODEL_IDS:
            result = simulate(air, rain, subset, mechanism, policy, thermal=(coarse[0][:, reps], coarse[1][:, reps]))
            reference = simulate(air, rain, subset, mechanism, policy, thermal=fine)
            for j, i in enumerate(reps):
                a, b = result["failure_margin"][:, j], reference["failure_margin"][:, j]
                status_a = classify_trajectory(a)
                status_b = classify_trajectory(b)
                same_branch = ((result["interface_temp_c"][:, j] > -.5)
                               == (reference["interface_temp_c"][:, j] > -.5))
                records.append(dict(parameter_set_id=f"q2r3-p{i:04d}", mechanism_id=mechanism, law_policy=policy,
                                    main_dz_m=coarse_dz, reference_dz_m=fine_dz, dt_hours=1.,
                                    max_abs_margin_difference=float(np.abs(a-b).max()),
                                    final_abs_margin_difference=float(abs(a[-1]-b[-1])),
                                    max_abs_interface_temp_difference_c=float(np.abs(result["interface_temp_c"][:, j]
                                                                                  - reference["interface_temp_c"][:, j]).max()),
                                    strength_branch_mismatch_hours=int((~same_branch).sum()) if policy == "thawed_rock_contact" else 0,
                                    max_margin_difference_on_same_strength_branch=float(np.abs(a[same_branch]-b[same_branch]).max()) if same_branch.any() else None,
                                    main_onset_status=status_a["onset_status"], reference_onset_status=status_b["onset_status"],
                                    onset_category_same=status_a["onset_status"] == status_b["onset_status"],
                                    main_onset_elapsed_hours=status_a["onset_elapsed_hours"],
                                    reference_onset_elapsed_hours=status_b["onset_elapsed_hours"],
                                    evaluation_stratum="numerical_benchmark"))
    return pd.DataFrame(records)


def summarize_checks(frame):
    linear = frame[frame.law_policy == "linear_extension"]
    thaw = frame[frame.law_policy == "thawed_rock_contact"]
    return dict(n_comparisons=len(frame), main_dz_m=float(frame.main_dz_m.iloc[0]),
                reference_dz_m=float(frame.reference_dz_m.iloc[0]),
                max_abs_margin_difference=float(frame.max_abs_margin_difference.max()),
                max_final_abs_margin_difference=float(frame.final_abs_margin_difference.max()),
                max_abs_interface_temp_difference_c=float(frame.max_abs_interface_temp_difference_c.max()),
                linear_max_abs_margin_difference=float(linear.max_abs_margin_difference.max()),
                thaw_max_abs_margin_difference=float(thaw.max_abs_margin_difference.max()),
                strength_branch_mismatch_hours=int(frame.strength_branch_mismatch_hours.sum()),
                categories_equal_n=int(frame.onset_category_same.sum()),
                all_categories_equal=bool(frame.onset_category_same.all()),
                target_margin_difference=.02,
                target_met_all_cases=bool((frame.max_abs_margin_difference <= .02).all()),
                target_met_linear_cases=bool((linear.max_abs_margin_difference <= .02).all()))


def run():
    begin = time.perf_counter()
    if Path.cwd().resolve() != ROOT or str(ROOT) != "/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2":
        raise SystemExit("use only the assigned Q2 worktree")
    assert hashlib.sha256(ENGINE.read_bytes()).hexdigest() == ENGINE_SHA
    v1_bundle_path = BASE / "exports/mechanism_bundle.json"
    v1_bundle = json.loads(v1_bundle_path.read_text())
    v1_bound = []
    for item in v1_bundle["files"]:
        path = ROOT / item["path"]
        assert digest(path, item["role"])["sha256"] == item["sha256"]
        assert path.stat().st_size == item["bytes"]
        v1_bound.append(digest(path, item["role"]))
    release_v2_path = BASE / "exports/release_bundle_v2.json"
    release_v2_before = digest(release_v2_path, "release_geometry_v2") if release_v2_path.exists() else None
    cfg0 = json.loads((BASE / "config/experiment_v1.json").read_text())
    protocol = dict(protocol_version="q2r3-refinement-v2-preregistered",
                    same_parameters_and_seed=True, same_hourly_forcing_and_state_grid=True,
                    frozen_engine_sha256=ENGINE_SHA, first_main_dz_m=.125, first_reference_dz_m=.0625,
                    conditional_finer_main_dz_m=.0625, conditional_finer_reference_dz_m=.03125,
                    selection_rule="If any of 8 fixed representatives x4 mechanisms x2 policies has max margin difference >0.02, use 0.0625 m as main and test it against 0.03125 m; report remaining errors without relaxing 0.02 target.",
                    changing_scope="thermal spatial grid only; not hourly state step, damage, water, strength branches, parameters or forcing",
                    representatives=np.linspace(0, 255, 8, dtype=int).tolist(), independent_events=0,
                    probabilities_assigned=False)
    emit_json(OUT / "refinement_protocol.json", protocol)
    forcing_path = BASE / "results/forcing_hourly_v1.csv"
    forcing = pd.read_csv(forcing_path, parse_dates=["time_utc"])
    assert len(forcing) == 2089
    assert (forcing.time_utc.diff().dropna() == pd.Timedelta(hours=1)).all()
    assert np.array_equal(forcing.elapsed_hours.to_numpy(), np.arange(len(forcing)))
    air, rain = forcing.station_air_temp_c.to_numpy(), forcing.precip_assumed_mm_h.to_numpy()
    p = parameter_inputs(cfg0)
    reps = np.asarray(protocol["representatives"])
    emit_csv(OUT / "forcing_hourly_v2.csv", forcing)
    print("Computing main thermal dz=0.125m, all 256 parameter rows", flush=True)
    thermal125 = thermal_transfer(air, p, 1., .125, cfg0["thermal_bottom_m"])
    print("Computing reference thermal dz=0.0625m, 8 fixed rows", flush=True)
    reference0625 = thermal_transfer(air, take(p, reps), 1., .0625, cfg0["thermal_bottom_m"])
    first_checks = compare_representatives(air, rain, p, reps, thermal125, reference0625, .125, .0625)
    emit_csv(OUT / "refinement_125_vs_0625.csv", first_checks)
    initial_summary = summarize_checks(first_checks)
    print(json.dumps({"initial_refinement": initial_summary}), flush=True)
    if initial_summary["target_met_all_cases"]:
        main_dz, final_reference_dz, thermal = .125, .0625, thermal125
        final_checks = first_checks
        label = "thermal125v2"
    else:
        print("0.02 margin target unmet: computing full main dz=0.0625m and reference dz=0.03125m", flush=True)
        thermal = thermal_transfer(air, p, 1., .0625, cfg0["thermal_bottom_m"])
        reference03125 = thermal_transfer(air, take(p, reps), 1., .03125, cfg0["thermal_bottom_m"])
        final_checks = compare_representatives(air, rain, p, reps, thermal, reference03125, .0625, .03125)
        emit_csv(OUT / "refinement_0625_vs_03125.csv", final_checks)
        main_dz, final_reference_dz, label = .0625, .03125, "thermal0625v2"
    final_summary = summarize_checks(final_checks)
    print(json.dumps({"final_refinement": final_summary}), flush=True)
    model_ids = {mechanism: f"{model_id[:-2]}v2_{label}" for mechanism, model_id in MODEL_IDS.items()}
    cfg = {**cfg0, "experiment_id": "q2r3-competing-mechanisms-thermal-v2",
           "dz_m": main_dz, "refinement_reference_dz_m": final_reference_dz,
           "refinement_scope": protocol["changing_scope"], "baseline_experiment_id": cfg0["experiment_id"],
           "model_ids": model_ids, "scenario_suffix": label}
    emit_json(OUT / "config.json", cfg)
    evaluation_index = int(np.flatnonzero(forcing.time_utc >= cfg["evaluation_start_utc"])[0])
    records, parameter_records, tracks, minima, watermax = [], [], [], {}, 0.
    for policy in cfg["policies"]:
        for mechanism in cfg["models"]:
            result = simulate(air, rain, p, mechanism, policy, thermal=thermal)
            print(f"Refined complete: {policy} {mechanism}", flush=True)
            minima[(mechanism, policy)] = result["failure_margin"][evaluation_index:].min(axis=0)
            watermax = max(watermax, float(result["water_budget_max_abs_m"].max()))
            for i in range(cfg["n_parameter_sets"]):
                base_id = scenario_id(i, mechanism, policy)
                sid = f"{base_id}__{label}"
                trajectory = result["failure_margin"][:, i]
                onset = classify_trajectory(trajectory)
                late = classify_trajectory(trajectory[evaluation_index:])
                records.append(dict(scenario_id=sid, base_scenario_id=base_id, parameter_set_id=f"q2r3-p{i:04d}",
                                    model_id=model_ids[mechanism], mechanism_id=mechanism, law_policy=policy,
                                    experiment_id=cfg["experiment_id"], parameter_version=cfg["parameter_version"],
                                    geometry_version="conditional_plane_slab_v1", evaluation_stratum="conditional_scenario",
                                    data_role="scenario", forecast_input_mode="ideal_weather",
                                    min_margin_all=float(trajectory.min()), min_margin_evaluation=float(trajectory[evaluation_index:].min()),
                                    final_margin=float(trajectory[-1]), initial_margin=float(trajectory[0]),
                                    final_interface_temp_c=float(result["interface_temp_c"][-1, i]),
                                    final_damage=float(result["damage"][-1, i]), peak_pressure_kpa=float(result["pressure_kpa"][:, i].max()),
                                    strength_domain_fraction=float(result["strength_domain"][:, i].mean()),
                                    evaluation_onset_status=late["onset_status"], **onset))
                records[-1]["crossing_time_utc"] = (forcing.time_utc.iloc[0] + pd.Timedelta(hours=onset["onset_elapsed_hours"])).isoformat() if onset["onset_elapsed_hours"] is not None else None
                parameter_records.append(dict(scenario_id=sid, base_scenario_id=base_id,
                                              parameter_set_id=f"q2r3-p{i:04d}", mechanism_id=mechanism,
                                              model_id=model_ids[mechanism], law_policy=policy,
                                              parameter_version=cfg["parameter_version"], geometry_version="conditional_plane_slab_v1",
                                              design_role="space_filling_not_probability", prior_weight=None,
                                              **{key: float(values[i]) for key, values in p.items()}))
            for i in reps:
                base_id = scenario_id(i, mechanism, policy)
                status = classify_trajectory(result["failure_margin"][:, i])["onset_status"]
                track = pd.DataFrame(dict(scenario_id=f"{base_id}__{label}", base_scenario_id=base_id,
                                          model_id=model_ids[mechanism], mechanism_id=mechanism, law_policy=policy,
                                          time_utc=forcing.time_utc, elapsed_hours=forcing.elapsed_hours,
                                          failure_margin=result["failure_margin"][:, i], margin_definition=MARGIN_DEFINITION,
                                          interface_temp_c=result["interface_temp_c"][:, i], damage=result["damage"][:, i],
                                          storage_m=result["storage_m"][:, i], pressure_kpa=result["pressure_kpa"][:, i],
                                          strength_in_lab_domain=result["strength_domain"][:, i],
                                          critical_head_m=result["critical_head_m"][:, i], data_role="scenario",
                                          forecast_input_mode="ideal_weather", evaluation_stratum="conditional_scenario",
                                          parameter_version=cfg["parameter_version"], geometry_version="conditional_plane_slab_v1",
                                          physical_phase="initiation", available_time=None, onset_status_whole_run=status))
                track["forcing_cutoff_utc"] = forcing.time_utc.shift(1)
                tracks.append(track)
    outcomes, parameters = pd.DataFrame(records), pd.DataFrame(parameter_records)
    emit_csv(OUT / "scenario_outcomes.csv", outcomes)
    emit_csv(OUT / "parameter_ensemble.csv", parameters)
    emit_parquet(OUT / "state_trajectories.parquet", pd.concat(tracks, ignore_index=True))
    comparison = []
    for (mechanism, policy), group in outcomes.groupby(["mechanism_id", "law_policy"], sort=False):
        comparison.append(dict(mechanism_id=mechanism, model_id=model_ids[mechanism], law_policy=policy,
                               n_parameter_sets=len(group), interval_crossing_n=int((group.onset_status == "interval_crossing").sum()),
                               left_censored_n=int(group.onset_status.str.startswith("left_censored").sum()),
                               never_crossed_n=int((group.onset_status == "never_crossed").sum()),
                               missing_n=int(group.onset_status.str.contains("missing").sum()),
                               median_min_margin=float(group.min_margin_evaluation.median()),
                               p05_min_margin=float(group.min_margin_evaluation.quantile(.05)),
                               p95_min_margin=float(group.min_margin_evaluation.quantile(.95)),
                               wholly_lab_domain_n=int((group.strength_domain_fraction == 1).sum()),
                               mean_lab_domain_fraction=float(group.strength_domain_fraction.mean()),
                               independent_local_training_events=0, independent_local_validation_events=0,
                               evaluation_stratum="conditional_scenario", design_fraction_is_probability=False))
    emit_csv(OUT / "model_comparison.csv", pd.DataFrame(comparison))
    parent_outcomes = pd.read_csv(BASE / "results/scenario_outcomes.csv")
    paired = outcomes.merge(parent_outcomes, left_on="base_scenario_id", right_on="scenario_id", suffixes=("_v2", "_v1"), validate="one_to_one")
    deltas = paired[["scenario_id_v2", "base_scenario_id", "parameter_set_id_v2", "mechanism_id_v2", "law_policy_v2"]].copy()
    for metric in ["initial_margin", "min_margin_all", "min_margin_evaluation", "final_margin", "final_interface_temp_c", "final_damage", "peak_pressure_kpa", "strength_domain_fraction"]:
        deltas[f"{metric}_v1"] = paired[f"{metric}_v1"]
        deltas[f"{metric}_v2"] = paired[f"{metric}_v2"]
        deltas[f"{metric}_delta_v2_minus_v1"] = paired[f"{metric}_v2"] - paired[f"{metric}_v1"]
    deltas["onset_status_v1"], deltas["onset_status_v2"] = paired.onset_status_v1, paired.onset_status_v2
    deltas["onset_category_changed"] = paired.onset_status_v1 != paired.onset_status_v2
    deltas["onset_elapsed_hours_v1"], deltas["onset_elapsed_hours_v2"] = paired.onset_elapsed_hours_v1, paired.onset_elapsed_hours_v2
    deltas["onset_elapsed_hours_delta"] = paired.onset_elapsed_hours_v2 - paired.onset_elapsed_hours_v1
    deltas["evaluation_stratum"] = "numerical_benchmark"
    emit_csv(OUT / "paired_v1_v2.csv", deltas)
    sensitivities = []
    for (mechanism, policy), response in minima.items():
        x = np.column_stack([p[key] if RANGES[key][2] == "linear" else np.log(p[key]) for key in RANGES])
        z = (x-x.mean(0))/x.std(0)
        y = (response-response.mean())/response.std()
        beta = np.linalg.lstsq(np.column_stack([np.ones(len(response)), z]), y, rcond=None)[0][1:]
        for j, key in enumerate(RANGES):
            sensitivities.append(dict(mechanism_id=mechanism, law_policy=policy, parameter=key,
                                      spearman_rho=float(pd.Series(p[key]).rank().corr(pd.Series(response).rank())),
                                      standardized_linear_coefficient=float(beta[j]),
                                      outcome="minimum margin Aug19..Aug27", n_joint_design=len(response),
                                      evaluation_stratum="conditional_scenario", interpretation="design-dependent association, no posterior/causal importance"))
    emit_csv(OUT / "joint_sensitivity.csv", pd.DataFrame(sensitivities))
    interaction = minima[("S_T_H", "linear_extension")] - minima[("S_T", "linear_extension")] - minima[("S_H", "linear_extension")] + minima[("S", "linear_extension")]
    emit_csv(OUT / "interaction.csv", pd.DataFrame(dict(parameter_set_id=[f"q2r3-p{i:04d}" for i in range(256)],
                                                        contrast_of_minima_STH_minus_ST_minus_SH_plus_S=interaction,
                                                        evaluation_stratum="conditional_scenario")))
    contract = json.loads((BASE / "results/mechanism_contract.json").read_text())
    contract.update(contract_version="q2r3-mechanism-contract-v2", model_ids=model_ids,
                    thermal_grid_m=main_dz, thermal_reference_grid_m=final_reference_dz,
                    parent_contract_version="q2r3-mechanism-contract-v1", scenario_suffix=label,
                    base_scenario_join="base_scenario_id matches v1 mechanism and release-geometry-v2 base_scenario_id; release geometry unchanged. Use v2 onset states when combining with v2, not old release table onset as a second truth.",
                    state_trajectory_scope="8 preselected parameter indices x4 mechanisms x2 policies; outcomes and parameter grid contain all 2048 scenarios",
                    engine_sha256=ENGINE_SHA)
    emit_json(OUT / "mechanism_contract.json", contract)
    summary = dict(bundle_version=VERSION, input_version=v1_bundle["input_version"], evaluation_stratum="numerical_benchmark",
                   engine_sha256=ENGINE_SHA, v1_bundle_sha256=digest(v1_bundle_path, "v1")["sha256"],
                   v1_files=v1_bound, release_geometry_v2_reference=release_v2_before,
                   first_refinement=initial_summary, final_refinement=final_summary,
                   chosen_main_dz_m=main_dz, chosen_reference_dz_m=final_reference_dz,
                   full_parameter_sets=256, scenario_outcomes=len(outcomes), representative_state_rows=len(reps)*8*len(forcing),
                   time_origin_utc=forcing.time_utc.iloc[0].isoformat(), state_dt_hours=1.,
                   information_cutoff="forcing[i] drives interval i..i+1; state0 specified initial state; real available_time remains unknown",
                   v1_v2_category_changed_n=int(deltas.onset_category_changed.sum()),
                   v1_v2_max_abs_final_margin_delta=float(deltas.final_margin_delta_v2_minus_v1.abs().max()),
                   v1_v2_max_abs_evaluation_min_margin_delta=float(deltas.min_margin_evaluation_delta_v2_minus_v1.abs().max()),
                   v1_v2_max_abs_onset_hours_delta=float(deltas.onset_elapsed_hours_delta.abs().max()) if deltas.onset_elapsed_hours_delta.notna().any() else None,
                   max_water_budget_error_m=watermax, independent_events=0, probabilities_assigned=False,
                   runtime_stack=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__),
                   scientific_adoption="pending_team_review")
    emit_json(OUT / "refinement_summary.json", summary)
    note = f"""# Q2 热空间网格细化 v2

本轮发现v1的0.5 m网格对浅层界面存在可见离散误差，故独立发布v2。保留v1、几何release v2及冻结引擎原字节；引擎SHA256 `{ENGINE_SHA}`。方程、256个同一LHS参数点、两强度策略、4机制、小时输入与状态时间轴均不变，只细化热传导空间网格。试验规则先写入`results/refined_v2/refinement_protocol.json`再计算，没有拟合事件启动时刻。

## 实际计算和精度

先全256点计算dz=0.125 m，并将8个预定代表（0/36/72/109/145/182/218/255）与dz=0.0625 m比较，4机制×2强度策略共64组。最大逐时裕度差{initial_summary['max_abs_margin_difference']:.9g}，最大温度差{initial_summary['max_abs_interface_temp_difference_c']:.9g}°C；类别一致{initial_summary['categories_equal_n']}/64。预定0.02裕度目标通过：{initial_summary['target_met_all_cases']}。

最终主网格 **{main_dz:g} m**，参考网格{final_reference_dz:g} m；状态步长均1 h，热显式内部按CFL≤0.45子步。最终64组最大逐时裕度差{final_summary['max_abs_margin_difference']:.9g}、末时裕度差{final_summary['max_final_abs_margin_difference']:.9g}、界面温差{final_summary['max_abs_interface_temp_difference_c']:.9g}°C；类别一致{final_summary['categories_equal_n']}/64。连续线性强度分支最大逐时裕度差{final_summary['linear_max_abs_margin_difference']:.9g}，thaw挑战分支{final_summary['thaw_max_abs_margin_difference']:.9g}，thaw分支是否跨过−0.5°C的网格不一致样本合计{final_summary['strength_branch_mismatch_hours']}小时。0.02目标全案例通过：{final_summary['target_met_all_cases']}，线性分支通过：{final_summary['target_met_linear_cases']}。真实差异全部保留；类别一致不等于轨迹已经精确，离散thaw切换尤其不能以放松阈值掩盖。

用最终主网格完成4机制×2策略×256=**2048情景**；全部结果保留不启动、初始已越界和缺测类别。状态长表含预定8代表×8组×2089小时={len(reps)*8*len(forcing)}行。全256输出不是独立事件或概率先验。对v1全2048配对后类别改变{summary['v1_v2_category_changed_n']}组；最大末时裕度变化{summary['v1_v2_max_abs_final_margin_delta']:.9g}、评估窗最小裕度变化{summary['v1_v2_max_abs_evaluation_min_margin_delta']:.9g}。具体逐情景差异、首次越阈时差和域变化见`paired_v1_v2.csv`。水预算最大误差{watermax:.9g} m。

## 使用与限制

建议后续Q3数值接口优先使用本v2细网格包；若最终0.02目标存在未通过项，应按`refinement_summary.json`和逐组检查保留精度限制。当前检验隔离空间细化，不能替代小时状态步长/损伤耦合误差、材料强度转移误差或局部观测验证。

新情景ID添加`__{label}`，model_id为v2；`base_scenario_id`逐条对应v1和现有几何release v2中的基础ID。释放体积、组分和几何不重写；结合细热机制结果时，以v2状态/删失判定作为该数值版本结果，几何表旧onset_status不能当独立真值。源区启动和下游传播仍分开。

本v2重算模型竞争、联合敏感性及T/H交互；v1的其他诊断仍标注原网格，不能自动宣称全部已经细网格验证。站源映射、雨时段/QC、真实可用时间、结构面、热水初值与损伤材料性质继续未知或情景化。无本地独立验证事件，Mamot域标志只描述数值条件，最终科学采用待队员审视。

离线实际命令：

```sh
track_b/.venv/bin/python track_b/research/q2/round3/scripts/run_refined_v2.py
```

输出版本已存在时，复算必须与已发布字节相同；不覆盖旧版本。
"""
    emit(BASE / "NUMERICAL_REFINEMENT.md", note)
    paths = [(OUT / name, name) for name in ["refinement_protocol.json", "config.json", "forcing_hourly_v2.csv", "parameter_ensemble.csv",
              "state_trajectories.parquet", "scenario_outcomes.csv", "model_comparison.csv", "mechanism_contract.json",
              "paired_v1_v2.csv", "joint_sensitivity.csv", "interaction.csv", "refinement_125_vs_0625.csv", "refinement_summary.json"]]
    if (OUT / "refinement_0625_vs_03125.csv").exists():
        paths.append((OUT / "refinement_0625_vs_03125.csv", "refinement_0625_vs_03125.csv"))
    paths += [(ENGINE, "frozen_local_mechanism_engine"), (BASE / "scripts/run_experiments.py", "parent_parameter_design_source"),
              (Path(__file__).resolve(), "refined_v2_reproduction_script"), (BASE / "NUMERICAL_REFINEMENT.md", "numerical_refinement_methods_limits")]
    bundle = dict(bundle_version=VERSION, producer_question="q2", input_version=v1_bundle["input_version"],
                  evaluation_stratum="conditional_scenario", files=[digest(path, role) for path, role in paths],
                  numerical_grid=dict(thermal_dz_m=main_dz, state_dt_hours=1., reference_dz_m=final_reference_dz),
                  limitations=v1_bundle["limitations"] + ["Only thermal spatial grid refined; hourly coupled-state discretization remains separate.",
                                                          "Full parameter/outcome grid has2048 rows; native hourly trajectories cover8 fixed representatives.",
                                                          "Thaw branch is discontinuous at-0.5C; all measured convergence errors retained.",
                                                          "Use base_scenario_id to join existing release geometry v2; do not replace measured onset truth with model crossing."])
    assert hashlib.sha256(ENGINE.read_bytes()).hexdigest() == ENGINE_SHA
    for item in v1_bound:
        assert digest(ROOT / item["path"], item["role"]) == item
    if release_v2_before is not None:
        assert digest(release_v2_path, "release_geometry_v2") == release_v2_before
    emit_json(BUNDLE, bundle)
    print(json.dumps(dict(bundle=digest(BUNDLE, "mechanism_v2"), refinement=final_summary,
                          category_changes_vs_v1=summary["v1_v2_category_changed_n"], runtime_seconds=time.perf_counter()-begin)), flush=True)


if __name__ == "__main__":
    run()
