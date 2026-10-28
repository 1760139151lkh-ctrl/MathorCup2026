# -*- coding: utf-8 -*-
"""把脱敏版（多通道测量数据）的解答结果复原为 A 题（啤酒）语义的交付结果。

输入：同级“多通道测量数据_研究题目/A题_数学手记/results/”，或本目录内置 full_pipeline_project 运行后的结果；
输出：A赛道_复原解答/results/ 下的 CSV/XLSX 与 _ledger.json
说明：只做标签翻译、列顺序整理和汇总统计；数值本身与脱敏版结果逐元素一致。
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels as L

sys.stdout.reconfigure(encoding="utf-8")
R = L.SAND_SOL / "results"
OUT = L.RESULTS
OUT.mkdir(parents=True, exist_ok=True)

LEDGER = {}

# ============================================================ 通用
def rename_features(df):
    """把 V001–V231 列名换成原题 1.csv 的列名。"""
    df = df.copy()
    ren = {v: L.V2NAME[v] for v in L.V2NAME if v in df.columns}
    return df.rename(columns=ren)

def rename_targets(df):
    df = df.copy()
    ren = {y: L.Y2NAME[y] for y in L.Y2NAME if y in df.columns}
    return df.rename(columns=ren)

def disp(y):
    if y in L.TARGET_INFO:
        return L.TARGET_INFO[y]["display"]
    return "总体(overall)" if y == "overall" else str(y)

def rename_styles(df, col="regime"):
    df = df.copy()
    if col in df.columns:
        df[col] = df[col].map(L.R2STYLE).fillna(df[col])
    return df

def out(df, name, **kw):
    p = OUT / name
    df.to_csv(p, index=False, encoding="utf-8-sig", **kw)
    print(f"[saved] {name}  {df.shape}")
    return p

# ============================================================ 0. 化合物与感官参照表
feat_rows = []
for v in L.V2NAME:
    i = L.FEATURE_INFO[v]
    feat_rows.append(dict(var_id=v, column_1csv=i["original"], compound=i["pretty"],
                          origin=i["origin"], calibrated=i["calibrated"], unit=i["unit"],
                          threshold_mean=i["threshold_mean"], threshold_median=i["threshold_median"],
                          aging=i["aging"], off_flavor=i["off_flavor"]))
feat_ref = pd.DataFrame(feat_rows)
out(feat_ref, "参照表_化合物231.csv")

tgt_rows = []
for y in L.Y2NAME:
    t = L.TARGET_INFO[y]
    tgt_rows.append(dict(target_id=y, column_4csv=t["original"], name=t["display"],
                         clean_name=t["clean"], block=t["block"], category=t["category"]))
tgt_ref = pd.DataFrame(tgt_rows)
out(tgt_ref, "参照表_感官维度50.csv")

style_ref = pd.DataFrame([dict(regime_id=k, style=v) for k, v in L.R2STYLE.items()])
out(style_ref, "参照表_风格22.csv")

# 评分卡模板项目 → 单元格/目标列（供 make_scorecard.py 独立运行；不含任何敏感内容）
tpl_ref = L.TEMPLATE_MAP.copy()
out(tpl_ref, "参照表_模板项目.csv")

# ============================================================ 1. 数据核验结果
audit = json.loads((R / "data_audit_summary.json").read_text(encoding="utf-8"))
LEDGER["data_audit"] = {
    "n_samples": audit["shape"]["D01"][0],
    "n_features": 231,
    "n_targets": 50,
    "n_styles": 22,
    "missing_cells_D01": audit["D01_missing_cells"],
    "missing_rows_D01": audit["D01_missing_rows"],
    "missing_cols_D01": audit["D01_missing_columns"],
    "missing_cells_D07": audit["D07_missing_cells"],
    "D03_cards": audit["D03_cards"],
    "D03_nonblank_checkmarks": audit["D03_nonblank_checkmarks"],
    "scale_log10_count": audit["scale_best_counts"]["log10"],
    "scale_identity_count": audit["scale_best_counts"]["identity"],
    "identity_conflicts_gt_1e-7": audit["identity_reference_discrepancies_gt_1e_7"],
    "D01_D04_object_id_equal_count": audit["D01_D04_object_id_equal_count"],
    "D06_rows": 44,
    "correlation_types": {
        "D02_spearman_MAE": 1.6021924986637158e-16,
        "D02_pearson_MAE": 0.08730394533051206,
        "D05_spearman_MAE": 1.595e-16,
        "D05_pearson_MAE": 0.0513316,
        "D06_spearman_MAE": 1.5063071812105482e-16,
        "D06_pearson_MAE": 0.0579355,
    },
    "ref_attribution": audit["attribution_hypothetical_additive_scalar"],
    "critical_scale": audit["critical_scale"],
}
# 简单可核验的标度例子（原题 8.xlsx 校准表）：pH / 乙醇 / 色度 / 苦度
scale_examples = []
for v in ["V030", "V034", "V025", "V032", "V004", "V021"]:
    sc = next((x for x in audit["critical_scale"] if x["var_id"] == v), None)
    if sc is None:
        sc = next((x for x in pd.read_csv(R / "data_audit_scale_candidates.csv").to_dict("records")
                   if x["var_id"] == v), None)
    i = L.FEATURE_INFO[v]
    scale_examples.append(dict(var_id=v, compound=i["pretty"], unit=i["unit"],
                               best_transform=sc["best_transform"] if sc else "",
                               log10_error=sc["error_log10"] if sc else np.nan,
                               ln_error=sc["error_ln"] if sc else np.nan,
                               nonpositive_native_count=sc.get("native_nonpositive_count", np.nan),
                               replacement_floor_native=sc.get("replacement_floor_native", np.nan)))
out(pd.DataFrame(scale_examples), "核验_标度示例.csv")

derived = pd.read_csv(R / "data_audit_derived_consistency.csv")
derived_map = {"V037": "kcalperc", "V228": "esters_sum", "V229": "aroma_hops_sum",
               "V230": "acids_sum", "V231": "sulfur_sum"}
derived["column_1csv"] = derived["target"].map(derived_map)
out(derived, "核验_派生量关系误差.csv")
LEDGER["derived"] = {
    "names": derived_map,
    "consistency": derived[["target", "source", "n_valid_pairs", "recorded_MAE",
                            "recorded_max_abs_error"]].to_dict("records"),
    "formulas_power10": {
        "V037": "10^V037 = 0.4*u(V031) + 0.4*u(V033) + 0.4*u(V036) + 5.523*u(V034) + 0.0003*u(V027)",
        "V228": "10^V228 = (1/23)*u(V006) + (200/207)*u(V007) + (40/9)*u(V008) + 10*u(V009) + (4/3)*u(V010) + (1/10)*u(V011) + (5/3)*u(V016) + (100/129)*u(V019)",
        "V229": "10^V229 = (2000/9)*u(V095) + (2/3)*u(V118) + (2000/49)*u(V121) + (1000/23)*u(V128) + (100/23)*u(V155) + (8/5)*u(V164)",
        "V230": "10^V230 = (200/29)*u(V023) + (1/400)*u(V027)",
        "V231": "10^V231 = (1/50)*u(V002) + (5/6)*u(V003) + (1/19)*u(V004) + (2/7)*u(V012) + (1/11)*u(V022)",
    },
}

# ============================================================ 2. 问题1
# 连续预测（全拟合 / 折外）
cont_fit = pd.read_csv(R / "question1_continuous_fitted.csv")
cont_oof = pd.read_csv(R / "question1_continuous_oof.csv")
meta_cols = [c for c in cont_fit.columns if not c.startswith("Y")]
legacy_meta = {"object": "beer", "object_id": "beer_id", "regime": "style"}
def prep_frame(df):
    df = df.copy()
    df = df.rename(columns=legacy_meta)
    df["style"] = df["style"].map(L.R2STYLE).fillna(df["style"])
    return df
cont_fit = rename_targets(prep_frame(cont_fit))
cont_oof = rename_targets(prep_frame(cont_oof))
out(cont_fit, "Q1_连续评分预测_全拟合_D04尺度.csv")
out(cont_oof, "Q1_连续评分预测_折外_D04尺度.csv")

# 0–6 工作等级（协议A/B，全拟合与折外）
for tag, f in [("A_全拟合", "question1_protocol_A_fitted_grades.csv"),
               ("A_折外", "question1_protocol_A_oof_grades.csv"),
               ("B_全拟合", "question1_protocol_B_fitted_grades.csv"),
               ("B_折外", "question1_protocol_B_oof_grades.csv")]:
    g = rename_targets(prep_frame(pd.read_csv(R / f)))
    out(g, f"Q1_0-6分级_协议{tag}.csv")

# 协议一致性与 K 分布
agree = pd.read_csv(R / "question1_protocol_agreement.csv")
agree["target_name"] = agree["target"].map(disp)
out(agree, "Q1_协议A与B差异_逐维度.csv")
for ds in ["fitted", "oof"]:
    sub = agree[(agree["dataset"] == ds) & (agree["target"] != "overall")]
    LEDGER.setdefault("q1_protocol", {})[ds] = {
        "exact_agreement_rate": float((sub["exact_agreement_rate"] * sub["n_scores"]).sum() / sub["n_scores"].sum()),
        "mean_abs_grade_diff": float(sub["mean_absolute_grade_difference"].mean()),
        "mean_B_minus_A": float(sub["mean_B_minus_A"].mean()),
        "max_abs_diff": int(sub["maximum_absolute_grade_difference"].max()),
    }
kdist = pd.read_csv(R / "question1_protocol_K_distribution.csv")
kdist["target"] = "stale_hops"
out(kdist, "Q1_陈酒花味Y38等级分布_协议A与B.csv")
LEDGER["q1_K_distribution"] = kdist.to_dict("records")

# 每维度指标（选定流程，随机5折嵌套验证）
metrics = pd.read_csv(R / "question1_metrics.csv")
metrics["target_name"] = metrics["target"].map(disp)
out(metrics, "Q1_逐维度交叉验证指标.csv")
agg = (metrics.groupby(["model", "protocol"])
       .agg(mae=("mae", "mean"), rmse=("rmse", "mean"), r2=("r2", "mean"),
            r2_positive=("r2", lambda s: int((s > 0).sum())),
            mae_improvement=("mae_improvement_over_mean", "mean"), n=("target", "size"))
       .reset_index())
out(agg, "Q1_模型比较汇总.csv")
LEDGER["q1_metrics"] = json.loads(agg.round(6).to_json(orient="records"))

# 选定模型逐维度（随机5折）最好 / 最差
sel = metrics[(metrics["model"] == "selected") &
              (metrics["protocol"] == "nested_random_5x3")].copy()
sel = sel.sort_values("r2", ascending=False)
LEDGER["q1_best"] = sel.head(10)[["target", "target_name", "mae", "r2"]].round(4).to_dict("records")
LEDGER["q1_worst"] = sel.tail(8)[["target", "target_name", "mae", "r2"]].round(4).to_dict("records")
out(sel, "Q1_选定模型_逐维度指标_随机5折.csv")

# conformal
conf = pd.read_csv(R / "question1_conformal_metrics.csv")
conf["target_name"] = conf["target"].map(disp)
out(conf, "Q1_共形区间指标.csv")
q1s = json.loads((R / "question1_summary.json").read_text(encoding="utf-8"))
LEDGER["q1_summary"] = q1s
LEDGER["q1_conformal"] = {
    "mean_marginal_coverage": q1s["conformal"]["mean_marginal_coverage"],
    "mean_interval_width": float(conf["interval_width"].mean()),
    "coverage_min": float(conf["test_coverage"].min()),
    "coverage_max": float(conf["test_coverage"].max()),
    "joint_box_coverage": q1s["conformal"]["joint_box_test_coverage"],
    "joint_box_covered": q1s["conformal"]["joint_box_covered"],
    "joint_box_n": q1s["conformal"]["joint_box_test_n"],
    "all50_covered_rate": q1s["conformal"]["all50_covered_by_marginal_intervals"],
}

# 等级可识别性
gi = json.loads((R / "question1_grade_identification_summary.json").read_text(encoding="utf-8"))
gidf = pd.read_csv(R / "question1_grade_identification_summary.csv")
gidf["target_name"] = gidf["target"].map(disp)
out(gidf, "Q1_等级可识别性_逐维度.csv")
LEDGER["q1_identifiability"] = gi

# ============================================================ 3. 问题2
top3 = pd.read_csv(R / "question2_top3.csv")
top3["compound"] = top3["feature"].map(lambda v: L.FEATURE_INFO[v]["pretty"])
top3["origin"] = top3["feature"].map(lambda v: L.FEATURE_INFO[v]["origin"])
top3["target_name"] = top3["target"].map(disp)
top3["style_signal"] = top3["within_regime_rank_correlation"]
out(top3, "Q2_Top3关键化合物_明细.csv")
wide_rows = []
for y, g in top3.groupby("target", sort=False):
    g = g.sort_values("top_rank")
    row = dict(target=y, target_name=L.TARGET_INFO[y]["display"])
    for k, (_, r) in enumerate(g.iterrows(), start=1):
        row[f"top{k}_compound"] = r["compound"]
        row[f"top{k}_column"] = r["feature"]
        row[f"top{k}_freq"] = r["bootstrap_selection_frequency"]
        row[f"top{k}_module"] = r["module"]
    row["module_any_rep_freq"] = g["fixed_module_selection_frequency"].iloc[0]
    row["mean_method_Jaccard"] = g["mean_method_Jaccard"].iloc[0]
    wide_rows.append(row)
top3_wide = pd.DataFrame(wide_rows)
out(top3_wide, "Q2_Top3关键化合物_汇总.csv")
LEDGER["q2_top3_examples"] = top3_wide[top3_wide["target"].isin(
    ["Y01", "Y06", "Y07", "Y11", "Y31", "Y32", "Y34", "Y35", "Y36", "Y38", "Y39", "Y46", "Y50"]
)].round(4).to_dict("records")

nodes = pd.read_csv(R / "question2_network_nodes.csv")
nodes["compound"] = nodes["feature"].map(lambda v: L.FEATURE_INFO[v]["pretty"])
nodes["origin"] = nodes["feature"].map(lambda v: L.FEATURE_INFO[v]["origin"])
out(nodes, "Q2_网络节点与模块.csv")
edges = pd.read_csv(R / "question2_network_edges.csv")
edges["compound_a"] = edges["feature_a"].map(lambda v: L.FEATURE_INFO[v]["pretty"])
edges["compound_b"] = edges["feature_b"].map(lambda v: L.FEATURE_INFO[v]["pretty"])
out(edges, "Q2_网络边.csv")

# 模块构成摘要：每个非单点模块列出规模/来源构成/代表化合物
mod_rows = []
for m, g in nodes.groupby("module"):
    if len(g) < 2:
        continue
    g = g.sort_values("strength", ascending=False)
    origin_counts = g["origin"].value_counts().to_dict()
    mod_rows.append(dict(module=int(m), size=len(g), edges_degree_sum=int(g["degree"].sum()),
                         origins=";".join(f"{k}:{v}" for k, v in origin_counts.items()),
                         top_compounds="; ".join(g["compound"].head(8)),
                         top_features=";".join(g["feature"].head(8))))
mods = pd.DataFrame(mod_rows).sort_values("size", ascending=False)
out(mods, "Q2_共变模块构成.csv")
LEDGER["q2_network"] = {
    "n_nodes": int(len(nodes)),
    "n_edges": int(len(edges)),
    "weighted_degree_sum": float(nodes["degree"].sum()),
    "n_modules_incl_isolates": int(nodes["module"].nunique()),
    "n_isolates": int((nodes["degree"] == 0).sum()),
    "n_nontrivial_modules": int((nodes.groupby("module").size() >= 2).sum()),
    "largest_module": int(nodes.groupby("module").size().max()),
    "module_summary": mods.head(8).to_dict("records"),
}
q2s = json.loads((R / "question2_summary.json").read_text(encoding="utf-8"))
LEDGER["q2_summary"] = q2s
LEDGER["q2_network"].update({k: q2s[k] for k in
                             ["edges", "communities", "isolates", "modularity",
                              "network_bootstrap_ARI_median", "network_bootstrap_edge_Jaccard_median",
                              "top3_frequency_median", "top3_frequency_min", "top3_frequency_ge_0_8",
                              "mean_method_Jaccard", "threshold_hinge_tests",
                              "threshold_hinge_q_BH_below_0_05", "threshold_hinge_q_BH_HC3_below_0_05",
                              "top3_overall_within_regime_sign_reversals"]})

# 阈值 hinge 汇总
hinge = pd.read_csv(R / "question2_threshold_hinge_exploratory.csv")
hinge["compound"] = hinge["feature"].map(lambda v: L.FEATURE_INFO[v]["pretty"])
hinge["target_name"] = hinge["target"].map(disp)
hinge["origin"] = hinge["feature"].map(lambda v: L.FEATURE_INFO[v]["origin"])
out(hinge, "Q2_阈值折线检验_全部1050组.csv")
top_hinge = hinge.sort_values("p_HC3_approximate").head(20)
out(top_hinge, "Q2_阈值折线检验_最显著20组.csv")
LEDGER["q2_hinge_top"] = top_hinge[["feature", "compound", "target", "target_name",
                                    "threshold_native", "hinge_slope_change",
                                    "p_HC3_approximate", "q_BH_HC3_exploratory"]].round(6).to_dict("records")

# ============================================================ 4. 问题3
# 生成化合物谱（1.csv 记录尺度）与感官画像
gen = pd.read_csv(R / "question3_structure_generated_full231_D01_scale.csv")
gen_styles = {"R20": "Tripel", "R12": "Kriek", "R13": "Lambic"}
gen["style"] = gen["regime"].map(gen_styles)
gen = rename_features(gen)
for sty in ["Tripel", "Kriek", "Lambic"]:
    sub = gen[gen["style"] == sty].drop(columns=["regime"])
    out(sub, f"Q3_生成化合物谱_{sty}.csv")
feature_cols = [i["original"] for i in L.FEATURE_INFO.values()]
gen_all = gen[["generated_id", "style"] + [c for c in gen.columns if c in feature_cols]]
out(gen_all, "Q3_生成化合物谱_三类合并.csv")

prof = pd.read_csv(R / "question3_structure_generated_profiles_D04_scale.csv")
prof["style"] = prof["regime"].map(gen_styles)
prof = rename_targets(prof).drop(columns=["regime"])
out(prof, "Q3_生成感官画像_D04尺度.csv")
portrait = prof.groupby("style")[[c for c in prof.columns if c in L.Y2NAME.values()]].mean()
portrait.index.name = "style"
out(portrait.reset_index(), "Q3_三类生成样本平均感官画像.csv")

# 真实风格的平均感官画像（D04），用于对照
_, sens = L.read_orig_sensory()
meta1, _ = L.read_orig_chem()
real_prof = sens.copy()
real_prof.columns = [L.Y2ID[c] if c in L.Y2ID else c for c in real_prof.columns]
real_prof = real_prof.rename(columns=L.Y2NAME)
real_prof.insert(0, "style", meta1["style"].values)
real_means = real_prof.groupby("style").mean()
out(real_means.reset_index(), "Q3_真实风格平均感官画像_D04尺度.csv")
corr_rows = []
for sty in ["Tripel", "Kriek", "Lambic"]:
    a = portrait.loc[sty].values
    b = real_means.loc[sty, portrait.columns].values
    corr_rows.append(dict(style=sty, pearson_r=float(np.corrcoef(a, b)[0, 1]),
                          spearman_r=float(pd.Series(a).corr(pd.Series(b), method="spearman")),
                          mean_abs_diff=float(np.mean(np.abs(a - b)))))
out(pd.DataFrame(corr_rows), "Q3_生成画像与真实风格画像一致性.csv")
LEDGER["q3_portrait_corr"] = corr_rows
LEDGER["q3_portrait_means"] = {sty: portrait.loc[sty].round(4).to_dict() for sty in portrait.index}

# 0–6 工作等级（生成画像，协议A）；直接由画像按协议 A 参数生成更一致
q1_grades_fit = pd.read_csv(OUT / "Q1_0-6分级_协议A_全拟合.csv")
prof_long = prof.melt(id_vars=["generated_id", "style"], var_name="column_4csv", value_name="z")
# 用全拟合 D04 的训练均值/标准差做协议 A
_, sens2 = L.read_orig_sensory()
mu = sens2.mean()
sd = sens2.std(ddof=0)
prof_long["grade_A"] = np.clip(np.floor(3 + (prof_long["z"] - prof_long["column_4csv"].map(mu)) /
                                        prof_long["column_4csv"].map(sd) + 0.5), 0, 6).astype(int)
grades_wide = prof_long.pivot_table(index=["generated_id", "style"], columns="column_4csv",
                                    values="grade_A").reset_index()
out(grades_wide, "Q3_生成感官画像_0-6工作等级_协议A.csv")
LEDGER["q3_K_generated"] = {
    "A_ge2": int((grades_wide["stale_hops"] >= 2).sum()),
    "n": int(len(grades_wide)),
    "by_style_A_ge2": grades_wide.groupby("style")["stale_hops"].apply(lambda s: int((s >= 2).sum())).to_dict(),
}
# 协议 B 的生成 K 分布来自脱敏结果（直接用）
kb = pd.read_csv(R / "question3_structure_generated_profiles_PROTOCOL_B.csv")
kb["style"] = kb["regime"].map(gen_styles)
out(kb, "Q3_生成画像_协议B_K分布.csv")

# 生成质量比较
held = pd.read_csv(R / "question3_structure_heldout_summary.csv")
out(held, "Q3_生成模型留出比较_结构路线.csv")
gen_sum = json.loads((R / "question3_structure_summary.json").read_text(encoding="utf-8"))
LEDGER["q3_generation"] = gen_sum
LEDGER["q3_heldout"] = held.to_dict("records")

# 代表样本（9 个）
rep_sum = pd.read_csv(R / "question3_structure_representative_summary.csv")
rep_sel = pd.read_csv(R / "question3_structure_representative_selection.csv")
rep_sel["style"] = rep_sel["regime"].map(gen_styles)
sel_ids = rep_sel[rep_sel["selected_rank_within_class"].notna()][
    ["generated_id", "regime", "style", "selected_rank_within_class",
     "nearest_real_class_rank_distance", "class_center_rank_distance"]]
out(rep_sum, "Q3_代表样本筛选汇总.csv")
out(sel_ids, "Q3_代表样本清单.csv")
rep_d01 = pd.read_csv(R / "question3_structure_representatives_D01_scale.csv")
rep_d01["style"] = rep_d01["regime"].map(gen_styles)
rep_d01 = rename_features(rep_d01)
out(rep_d01, "Q3_代表样本化合物谱_D01尺度.csv")
rep_prof = pd.read_csv(R / "question3_structure_representatives_profiles_D04_scale.csv")
rep_prof["style"] = rep_prof["regime"].map(gen_styles)
rep_prof = rename_targets(rep_prof)
out(rep_prof, "Q3_代表样本感官画像.csv")
rep_protoB = pd.read_csv(R / "question3_structure_representatives_profiles_PROTOCOL_B.csv")
out(rep_protoB, "Q3_代表样本协议B等级.csv")
LEDGER["q3_representatives"] = sel_ids.to_dict("records")

# 迁移（观测源守卫分支）：before/after 向量 + 缺陷对照 + 感官安全
trans_after = rename_features(pd.read_csv(R / "question3_observed_source_guard_after_D01_scale.csv"))
trans_after["style_target"] = "Tripel"
out(trans_after, "Q3_跨风格迁移_PilsLager到Tripel_迁移后.csv")
trans_source = rename_features(pd.read_csv(R / "question3_observed_source_guard_source_D01_scale.csv"))
out(trans_source, "Q3_跨风格迁移_PilsLager到Tripel_迁移前.csv")
trans_prof = pd.read_csv(R / "question3_observed_source_guard_after_profiles_D04_scale.csv")
out(trans_prof, "Q3_跨风格迁移_迁移后感官画像.csv")
trans_prof_before = pd.read_csv(R / "question3_observed_source_guard_original_source_profiles_D04_scale.csv")
out(trans_prof_before, "Q3_跨风格迁移_迁移前感官画像.csv")

crit = pd.read_csv(R / "question3_observed_source_guard_critical_comparison.csv")
def crit_name(v):
    if v in L.FEATURE_INFO:
        return L.FEATURE_INFO[v]["pretty"]
    return "陈酒花味（Y38 连续预测）" if "Y38" in str(v) else str(v)
crit["compound"] = crit["criterion"].map(crit_name)
crit["criterion_name"] = crit["criterion"].map({"V004": "DMS", "V039": "双乙酰",
                                                "V021": "4-VG", "V109": "反-2-壬烯醛"})
out(crit, "Q3_迁移_缺陷化合物对照.csv")
crit_wide = crit.pivot_table(index="source_object", columns="criterion",
                             values=["source_native", "after_native", "threshold", "nonworsening"])
out(crit_wide.reset_index(), "Q3_迁移_缺陷化合物对照_宽表.csv")
LEDGER["q3_transfer_critical"] = crit[crit["criterion"].isin(["V004", "V039", "V021", "V109"])][
    ["source_object", "criterion", "criterion_name", "threshold", "source_native", "after_native",
     "source_ratio", "after_ratio", "nonworsening"]].round(6).to_dict("records")

kcomp = pd.read_csv(R / "question3_protocol_K_comparison.csv")
kcomp["style_before"] = kcomp["baseline_kind"]
out(kcomp, "Q3_迁移_陈酒花味Y38安全对照.csv")
ksum = pd.read_csv(R / "question3_protocol_K_summary.csv")
out(ksum, "Q3_迁移_安全判据汇总.csv")
LEDGER["q3_transfer_K"] = ksum.round(6).to_dict("records")
LEDGER["q3_transfer_summary"] = gen_sum["observed_source_guard"]

feas = pd.read_csv(R / "question3_feasibility_bounds.csv")
feas["compound"] = feas["feature"].map(lambda v: L.FEATURE_INFO[v]["pretty"])
out(feas, "Q3_迁移可行性下界_W1.csv")
LEDGER["q3_feasibility"] = feas.to_dict("records")

# 迁移目标距离
try:
    dist = pd.read_csv(R / "question3_observed_source_guard_summary.json", encoding="utf-8")
except Exception:
    dist = None
LEDGER["q3_observed_guard"] = json.loads(
    (R / "question3_observed_source_guard_summary.json").read_text(encoding="utf-8"))

# ============================================================ 5. 汇总 ledger
(OUT / "_ledger.json").write_text(json.dumps(LEDGER, ensure_ascii=False, indent=2,
                                             default=lambda o: float(o) if isinstance(o, (np.floating,)) else str(o)),
                                  encoding="utf-8")
print("\n[done] _ledger.json")
