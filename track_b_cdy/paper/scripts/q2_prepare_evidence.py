"""Map the Q2 paper's claims to frozen results; performs no model integration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "track_b/paper"
R3 = ROOT / "track_b/research/q2/round3"


def load(rel):
    return json.loads((R3 / rel).read_text())


def binding(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def source(*paths):
    return [binding(R3 / p) for p in paths]


def main():
    evidence = PAPER / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    config = load("config/experiment_v1.json")
    summary = load("results/analytic_thermal/summary.json")
    comparison = pd.read_csv(R3 / "results/analytic_thermal/model_comparison.csv")
    sensitivity = pd.read_csv(R3 / "results/analytic_thermal/joint_sensitivity.csv")
    response = pd.read_csv(R3 / "results/thermal_response_times.csv")
    critical = pd.read_csv(R3 / "results/critical_relations.csv")
    identifiability = pd.read_csv(R3 / "results/identifiability.csv")
    observations = pd.read_csv(R3 / "lab_strength/audit/results/observations.csv")
    lab_run = load("lab_strength/model/results/run_summary.json")
    lab_decision = load("lab_strength/model/results/decision_summary.json")
    lab_fits = pd.read_csv(R3 / "lab_strength/model/results/fits.csv")
    claims = []

    def add(cid, statement, value, unit, files, anchor, scope, model_id=None, scenario_id=None):
        claims.append({"claim_id": cid, "statement": statement, "value": value, "unit": unit,
                       "source_files": files, "model_id": model_id, "scenario_id": scenario_id,
                       "scope": scope, "paper_anchor": anchor})

    add("q2-C01", "平面板法向/驱动应力、体积组成密度与法向厚度定义",
        {"sigma_n": "rho*g*h*cos(theta)/1000", "tau_g": "rho*g*h*sin(theta)/1000", "rho": "2700*r+917*(1-r)", "g": 9.80665, "h_direction": "normal_to_failure_plane"},
        {"stress": "kPa", "density": "kg/m^3", "h": "m", "g": "m/s^2"},
        source("scripts/mechanism_engine.py", "scripts/run_experiments.py"), "q2:eq-stress", "prescribed plane-slab scenario mechanics")
    add("q2-C02", "损伤仅乘面积混合黏聚项，摩擦采用非负有效应力；正裕度稳定",
        {"C": "(1-D)*(fb*cb+(1-fb)*cj(T))", "mu_e": "fb*mu_b+(1-fb)*mu_j(T)",
         "R": "C+max(sigma_n-u,0)*mu_e", "M": "(R-tau_g)/tau_g"},
        {"C_R": "kPa", "mu_e_M_D": "dimensionless"}, source("scripts/mechanism_engine.py"), "q2:eq-resistance", "common mechanical state relation")
    add("q2-C03", "Mamot冰填石灰岩快速剪切关系及两强度策略",
        {"c_j_intercept_kpa": 53.3, "c_j_T_slope_kpa_per_c": -73.5, "mu_j_intercept": .42, "mu_j_T_slope_per_c": -.21,
         "source_temperature_c": [-8, -.5], "source_nominal_normal_stress_kpa": [100, 400], "mean_strain_rate_s_inv": .0048,
         "strain_rate_plus_minus_s_inv": .0014, "thaw_challenger_above_c": -.5, "thaw_c_kpa": 0, "thaw_mu": .60},
        "mixed; see field suffixes", source("scripts/mechanism_engine.py", "sources/strength/mamot2018_article.pdf", "lab_strength/literature/literature_facts.json"),
        "q2:eq-strength", "external brittle limestone law with domain flags; warm contact is a prescribed challenger")
    add("q2-C04", "19维条件域、256共同参数点、4机制和2政策构成2048情景",
        {"parameter_ranges": config["ranges"], "parameter_count": len(config["ranges"]), "parameter_sets": 256, "mechanisms": 4, "policies": 2,
         "scenario_outcomes": summary["scenario_outcomes"], "seed": config["seed"], "probability_prior": False, "weights": None},
        "ranges per parameter; counts", source("config/experiment_v1.json", "results/analytic_thermal/config.json", "results/analytic_thermal/summary.json"),
        "q2:tab-parameters", "space-filling computational design; no event-probability weights")
    add("q2-C05", "共同边界2089小时状态与条件降水口径",
        {"start_utc": config["start_utc"], "end_utc": config["end_utc"], "hourly_states": 2089,
         "state_dt_hours": summary["native_state_dt_hours"], "initial_W_m": 0, "temperature_qc": "QC0",
         "precipitation_role": "conditional assumed mm/h; QC and integration interval unresolved", "available_time": None},
        "UTC, h, m", source("config/experiment_v1.json", "results/analytic_thermal/forcing_hourly.csv", "EXPERIMENT_PROTOCOL.md"),
        "q2:sec-structure", "retrospective ideal-weather scenario forcing; not operational availability acceptance")
    add("q2-C06", "半无限常系数导热的erfc边界增量因果叠加作为线性热数值参考",
        {"surface_B": "min(T_air+offset,0)", "initial_temperature": "uniform_T0", "kernel": "erfc(z/(2*sqrt(alpha*lag_seconds)))",
         "delta_B0": "B0-T0", "causal_j_lt_k": True, "K0": 0, "nfft": summary["fft_nfft"], "minimum_linear_padding": summary["fft_min_linear_padding"]},
        {"T_B": "degC", "alpha": "m^2/s", "z": "m", "lag": "s"}, source("scripts/analytic_thermal_engine.py", "results/analytic_thermal/protocol.json"),
        "q2:eq-thermal", "constant-property linear conduction with prescribed boundary; water/damage remain hourly")
    selected_response = response.loc[(response.diffusivity_m2_s == 1.5e-6) & (response.hours == 72) & response.depth_m.isin([2, 5])]
    assert len(selected_response) == 2
    add("q2-C07", "72小时纯导热的2m和5m阶跃幅度响应",
        selected_response[["diffusivity_m2_s", "depth_m", "hours", "step_response_fraction"]].to_dict(orient="records"),
        "dimensionless interface/surface amplitude ratio", source("results/thermal_response_times.csv", "scripts/analyze_robustness.py"),
        "q2:eq-thermal", "ideal conductive step benchmark, not observed local temperature")
    add("q2-C08", "雨融水经储排水到孔压，损伤促进排水，采用每小时连续溢流分段解析水库",
        {"gamma_w_kpa_per_m": 9.80665, "rho_w_kg_m3": 1000, "I": "mR*P*clip((Ts+1)/2,0,1)/1000+km*max(Ts,0)/24000",
         "u_kpa": "gamma_w*W/Sy", "tau_d_hours": "tau0*exp(-kappa*D_i)", "capacity_m": "Sy*min(Hconn,.98*sigma_n/gamma_w)",
         "damage_update": "Dnext=min(.999999,1-(1-D)*exp(-A*min(tau_g/max(R,1e-6),10)^n*dt_h))",
         "state_dt_hours": 1, "max_water_budget_error_m": summary["max_water_budget_error_m"]},
        "m/h, m, kPa, h; see field suffixes", source("scripts/mechanism_engine.py", "results/analytic_thermal/summary.json"),
        "q2:eq-states", "conditional water-equivalent reservoir and phenomenological cohesion loss, not calibrated creep")
    example = critical.loc[(critical.parameter_set_id == "q2r3-p0036") & critical.temperature_c.isin([-6, -3, -1])]
    example_records = json.loads(example[["parameter_set_id", "temperature_c", "critical_head_m", "root_status", "allowed_head_capacity_m", "root_reachable_before_capacity"]].to_json(orient="records"))
    add("q2-C09", "条件临界水头公式、容量判定和固定p0036温度示例",
        {"Hc": "[sigma_n-(tau_g-C)/mu_e]/gamma_w", "conditions": "C<=tau_g and mu_e>0; capacity criterion separately applied",
         "examples": example_records}, "m, degC", source("results/critical_relations.csv", "scripts/mechanism_engine.py"),
        "q2:eq-critical", "fixed initial-damage algebraic states, not measured trigger thresholds", scenario_id="q2r3-p0036")
    linear = comparison.loc[comparison.law_policy == "linear_extension"]
    add("q2-C10", "最终解析热线性分支四机制计数与评估期最小裕度中位数",
        linear[["mechanism_id", "model_id", "n_parameter_sets", "interval_crossing_n", "left_censored_n", "never_crossed_n", "median_min_margin", "p05_min_margin", "p95_min_margin"]].to_dict(orient="records"),
        "counts; dimensionless margin", source("results/analytic_thermal/model_comparison.csv", "results/analytic_thermal/scenario_outcomes.csv"),
        "q2:tab-mechanisms", "onset counts over whole June1–Aug27 horizon; margin minimum over Aug19–27; no probability interpretation",
        model_id=linear.model_id.tolist())
    add("q2-C11", "全2048解析结果分类和暖端接触ST分支变化",
        {"status_counts": summary["analytic_status_counts"], "thaw_ST": comparison.loc[(comparison.mechanism_id == "S_T") & (comparison.law_policy == "thawed_rock_contact"), ["interval_crossing_n", "left_censored_n", "never_crossed_n"]].iloc[0].to_dict(),
         "independent_local_events": summary["independent_observed_events"], "probabilities_assigned": False},
        "counts", source("results/analytic_thermal/model_comparison.csv", "results/analytic_thermal/summary.json"),
        "q2:sec-results", "computational scenarios, censored and no-crossing retained")
    sens = sensitivity.loc[(sensitivity.mechanism_id == "S_T_H") & (sensitivity.law_policy == "linear_extension")].copy()
    sens["abs_rho"] = sens.spearman_rho.abs()
    add("q2-C12", "解析STH线性分支最小裕度联合关联前五因素及方向",
        sens.sort_values("abs_rho", ascending=False).head(5)[["parameter", "spearman_rho", "n_joint_design"]].to_dict(orient="records"),
        "Spearman rho, dimensionless", source("results/analytic_thermal/joint_sensitivity.csv"), "q2:fig-critical",
        "association conditional on prescribed19-dimensional parameter ranges; not empirical causal ranking", model_id="q2r3_S_T_H_analytic_v1")
    add("q2-C13", "解析热对细/原FD参考的完整有限启动配对及不连续暖端误差",
        {"finite_pairs": summary["finite_analytic_fd_onset_pairs"], "fd00625_max_hours": summary["max_analytic_fd_onset_difference"],
         "fd0125_max_hours": summary["max_analytic_v2_onset_difference"], "max_margin_difference": summary["max_analytic_fd_margin_difference"],
         "finite40_vs_halfspace_max_temperature_bound_c": summary["max_actual_reflection_temperature_bound_c"],
         "category_changes_vs_fd00625": summary["fd_onset_category_changes"], "state_dt_hours": 1},
        "h; dimensionless margin", source("results/analytic_thermal/summary.json", "results/analytic_thermal/paired_v2_fd0625.csv"),
        "q2:sec-results", "thermal numerical comparison; does not establish full coupled physical-time accuracy")
    add("q2-C14", "四未知量的局部可辨识性秩随温压损伤信息增加",
        identifiability[["design_id", "n_observations", "n_unknown_parameters", "rank", "condition_status"]].to_dict(orient="records"),
        "rank", source("results/identifiability.csv", "results/identifiability_details.json"), "q2:sec-results",
        "numerical Jacobian benchmark at known geometry and ideal measurements; not local inversion", model_id="q2r3_STH_v1")
    add("q2-C15", "完整141实验、14派生温层、800名义组20次的实际温应力域",
        {"tests": len(observations), "derived_temperature_summaries": 14, "high_class": lab_decision["high_class"],
         "subset_membership": "nominal stress/temperature groups", "regression_predictors": "measured values at failure", "physical_specimen_UID": None},
        "counts, kPa, degC", source("lab_strength/audit/results/observations.csv", "lab_strength/audit/results/coefficient_strata.csv", "lab_strength/audit/results/schema.json"),
        "q2:sec-laboratory", "external repeated lab tests and author-derived summaries kept separate")
    add("q2-C16", "外部实验的四候选、四域两权重32拟合与576完整留组折",
        {"fits": lab_run["new_fits"], "folds": lab_run["holdout_fits"], "warm_common_tests": lab_run["domains"]["warm_all"],
         "bootstrap_attempts": lab_run["bootstrap_attempts"], "bootstrap_usable": lab_run["bootstrap_usable"], "unknown_physical_UID": True},
        "counts", source("lab_strength/model/results/run_summary.json", "lab_strength/model/results/run_config.json"), "q2:sec-laboratory",
        "external constitutive competition only; no replacement of local engine or independent local events")
    add("q2-C17", "暖域各本构候选训练、整温层/应力层和仅800组留出RMSE",
        {"grouped_row_ols": lab_decision["warm_grouped_metrics_row_ols"], "only_800_holdout": lab_decision["warm_800_class_holdout_row_ols"],
         "training_fits": lab_fits.loc[(lab_fits.domain == "warm_all") & (lab_fits.weight == "row_ols"), ["model", "parameter_count", "n", "rmse_kpa"]].to_dict(orient="records"),
         "macro_RMSE_definition": "sqrt(mean(fold_RMSE^2))"}, "kPa", source("lab_strength/model/results/fits.csv", "lab_strength/model/results/holdout_summary.csv", "lab_strength/model/results/holdout_folds.csv"),
        "q2:fig-lab", "83 external warm-domain tests; full class holdout; published Eq6 same-table score descriptive")
    add("q2-C18", "作者共同暖域的低/全应力线选择不同温层；低复杂度只作为外部挑战",
        {"selected_warm_low_c": [-4, -2, -.5], "selected_warm_all_c": [-4, -2, -1, -.5], "all_common_warm_c": [-4, -3, -2, -1, -.5],
         "local_engine_replaced": False, "local_events_added": 0}, "nominal degC; boolean",
        source("lab_strength/literature/figure6_temperature_screen.csv", "lab_strength/literature/literature_facts.json", "lab_strength/REPORT.md"),
        "q2:sec-laboratory", "source selection confounding distinguished from stress coverage; no automatic field transfer")
    add("q2-C19", "在固定实验设计坐标处的条件均值与两种重复相关性假设百分位范围",
        [row for row in lab_decision["conditional_mean_intervals_at_registered_lab_coordinate"] if row["model"] == "mc_linear"],
        "kPa at T=-2 degC and nominal sigma=800kPa", source("lab_strength/model/results/decision_summary.json", "lab_strength/model/results/bootstrap_coefficient_draws.npz"),
        "q2:sec-laboratory", "fixed lab design coordinate; bootstrap conditional mean sensitivity, not individual-event probability", model_id="mc_linear")
    for item in claims:
        if item["claim_id"] == "q2-C17":
            item["additional_paper_anchors"] = ["q2:tab-lab"]
        elif item["claim_id"] == "q2-C08":
            item["additional_paper_anchors"] = ["q2:eq-inflow"]

    figure_sources_path = PAPER / "figures/q2/q2_figure_sources.json"
    if figure_sources_path.exists():
        for filename, anchor, label in (
            ("q2_mechanism_comparison.pdf", "q2:fig-mechanisms", "共同参数机制比较图"),
            ("q2_critical_head_sensitivity.pdf", "q2:fig-critical", "临界水头与联合敏感性图"),
            ("q2_lab_grouped_validation.pdf", "q2:fig-lab", "外部本构分组评价图"),
        ):
            add("q2-F" + str(len([c for c in claims if c["claim_id"].startswith("q2-F")]) + 1).zfill(2), label,
                {"figure_file": f"track_b/paper/figures/q2/{filename}", "selection_rules": "See bound figure_sources metadata"},
                "see plot axes", [binding(PAPER / "figures/q2" / filename), binding(figure_sources_path), binding(PAPER / "scripts/q2_make_figures.py")],
                anchor, "paper-only redraw from frozen source tables; no model recalculation")
    (evidence / "q2_claims.json").write_text(json.dumps(claims, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

    code = [
        (R3 / "scripts/mechanism_engine.py", "共同力学、损伤及储排水推进"),
        (R3 / "scripts/analytic_thermal_engine.py", "因果erfc热核与解析热接口"),
        (R3 / "scripts/run_experiments.py", "共同19维参数设计与情景记录"),
        (R3 / "scripts/run_analytic_thermal.py", "全2048解析热竞争与参考配对后处理"),
        (R3 / "scripts/analyze_identifiability.py", "局部雅可比与参数补偿基准"),
        (R3 / "lab_strength/model/competition.py", "完整外部实验本构拟合、分组留出与条件不确定性"),
        (PAPER / "scripts/q2_make_figures.py", "本章节三幅矢量图重绘"),
    ]
    files = [{**binding(path), "role": role} for path, role in code]
    payload = {"question": "q2", "paper_baseline_commit": "eecf07db7873b3c2c63275fa0b419867d8bdd3b2", "files": files,
               "execution_in_paper_phase": "Only paper plotting and verification; historical model programs listed for adopted method provenance, not rerun",
               "runtime": {"python": "3.12.14", "numpy": "2.5.4", "pandas": "2.3.3", "matplotlib": "3.11.2"},
               "third_party_solver": None}
    (evidence / "q2_code_files.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"claims": len(claims), "adopted_program_files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
