"""公开、单调、可重算的两套0--6评分协议；不重训连续预测器。

从本题根目录运行：python A题_数学手记/code/scoring_protocols.py
A按训练目标均值/标准差定尺；B按训练目标的六个分位点定尺。
OOF对象的协议参数仅由该对象所在折之外的D04目标估计。
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[1] / "results"
FIGURES = Path(__file__).resolve().parents[1] / "figures"
TARGETS = [f"Y{i:02d}" for i in range(1, 51)]
QUANTILES = np.arange(1, 7, dtype=float) / 7.


def _score_array(scores):
    if isinstance(scores, pd.DataFrame):
        absent = set(TARGETS) - set(scores.columns)
        if absent:
            raise ValueError(f"评分矩阵缺少目标列：{sorted(absent)}")
        array = scores[TARGETS].to_numpy(dtype=float)
    else:
        array = np.asarray(scores, dtype=float)
    if array.ndim != 2 or array.shape[1] != len(TARGETS):
        raise ValueError("评分矩阵必须为n×50")
    if not np.isfinite(array).all():
        raise ValueError("公开协议要求有限评分；缺失目标应先明确处理，不能静默分箱")
    return array


def fit_protocols(Y_train):
    """只拟合刻度，返回与预测器无关的参数字典。

    B使用numpy的linear分位定义；重复值可能产生重复切点，协议允许这件事。
    A在训练标准差为0的目标上没有定义，因此明确报错，不暗中补一把尺子。
    """
    y = _score_array(Y_train)
    if not len(y):
        raise ValueError("协议参数至少需要一个训练对象")
    mu, sd = y.mean(axis=0), y.std(axis=0, ddof=0)
    if np.any(sd <= 0.):
        names = [TARGETS[j] for j in np.flatnonzero(sd <= 0.)]
        raise ValueError(f"协议A的训练标准差为0，需另行声明常量目标规则：{names}")
    return {"targets": TARGETS.copy(), "n_train": len(y),
            "A": {"mu": mu, "sd": sd, "sd_ddof": 0},
            "B": {"cutpoints": np.quantile(y, QUANTILES, axis=0, method="linear").T,
                  "quantile_levels": QUANTILES.copy(), "quantile_method": "linear",
                  "search_side": "right", "duplicate_cutpoints_allowed": True}}


def apply_protocol(scores, parameters, protocol="A"):
    """返回50列整数DataFrame，保留传入DataFrame的行索引，不携带元数据列。

    searchsorted(right)把恰等于切点的值放到切点右侧；重复切点可能跳过等级。
    这个边界约定使B在重复值下仍是确定、非降的函数，不保证七箱均有对象。
    """
    z = _score_array(scores)
    protocol = protocol.upper()
    if protocol == "A":
        p = parameters["A"]
        raw = 3. + (z - np.asarray(p["mu"])) / np.asarray(p["sd"])
        values = np.clip(np.floor(raw + .5), 0, 6).astype(int)
    elif protocol == "B":
        cuts = np.asarray(parameters["B"]["cutpoints"], dtype=float)
        if cuts.shape != (50, 6):
            raise ValueError("协议B切点必须是50×6")
        values = np.column_stack([np.searchsorted(cuts[j], z[:, j], side="right") for j in range(50)])
    else:
        raise ValueError("protocol只允许A或B")
    index = scores.index if isinstance(scores, pd.DataFrame) else None
    return pd.DataFrame(values, columns=TARGETS, index=index)


def _parameter_rows(parameters, scope, fold):
    rows = []
    for j, target in enumerate(TARGETS):
        cuts = np.asarray(parameters["B"]["cutpoints"])[j]
        row = {"scope": scope, "random_outer_fold": fold, "training_n": parameters["n_train"],
               "target": target, "A_mu": float(parameters["A"]["mu"][j]),
               "A_sd_ddof0": float(parameters["A"]["sd"][j]),
               "B_quantile_method": "linear", "B_search_side": "right",
               "B_distinct_cutpoint_count": len(np.unique(cuts)),
               "B_duplicate_cutpoints": len(np.unique(cuts)) < 6,
               "B_all_7_bins_occupied_not_guaranteed": True}
        row.update({f"B_cutpoint_{r+1}_q{r+1}_over_7": float(cuts[r]) for r in range(6)})
        rows.append(row)
    return rows


def _agreement_rows(a, b, dataset):
    difference = b.to_numpy() - a.to_numpy()
    rows = []
    for j, target in enumerate(TARGETS):
        d = difference[:, j]
        rows.append({"dataset": dataset, "target": target, "n_scores": len(d),
                     "exact_agreement_rate": float(np.mean(d == 0)),
                     "mean_absolute_grade_difference": float(np.mean(np.abs(d))),
                     "mean_B_minus_A": float(d.mean()),
                     "fraction_B_greater_A": float(np.mean(d > 0)),
                     "fraction_B_less_A": float(np.mean(d < 0)),
                     "maximum_absolute_grade_difference": int(np.abs(d).max())})
    flat = difference.ravel()
    rows.append({"dataset": dataset, "target": "overall", "n_scores": len(flat),
                 "exact_agreement_rate": float(np.mean(flat == 0)),
                 "mean_absolute_grade_difference": float(np.mean(np.abs(flat))),
                 "mean_B_minus_A": float(flat.mean()),
                 "fraction_B_greater_A": float(np.mean(flat > 0)),
                 "fraction_B_less_A": float(np.mean(flat < 0)),
                 "maximum_absolute_grade_difference": int(np.abs(flat).max())})
    return rows


def _k_distribution_rows(grades, dataset, protocol):
    k = grades.Y38.to_numpy()
    return [{"dataset": dataset, "protocol": protocol, "grade": grade,
             "count": int(np.sum(k == grade)), "frequency": float(np.mean(k == grade)),
             "n_objects": len(k), "K_ge2_count": int(np.sum(k >= 2)),
             "K_ge2_rate": float(np.mean(k >= 2))} for grade in range(7)]


def _read_profiles(name):
    path = RESULTS / name
    if not path.exists():
        return None
    profiles = pd.read_csv(path)
    _score_array(profiles)
    if "source_object" not in profiles.columns or profiles.source_object.duplicated().any():
        raise ValueError(f"迁移画像缺少唯一source_object：{name}")
    return profiles.set_index("source_object", drop=False)


def _comparison_rows(before, after, parameters, branch, baseline_kind, before_file, after_file):
    if set(before.index) != set(after.index):
        raise ValueError(f"前后对象集合不一致：{branch}")
    after = after.reindex(before.index)
    a_before = apply_protocol(before, parameters, "A").Y38.to_numpy()
    a_after = apply_protocol(after, parameters, "A").Y38.to_numpy()
    b_before = apply_protocol(before, parameters, "B").Y38.to_numpy()
    b_after = apply_protocol(after, parameters, "B").Y38.to_numpy()
    pre, post = before.Y38.to_numpy(), after.Y38.to_numpy()
    return pd.DataFrame({"branch": branch, "source_object": before.index.to_numpy(),
                         "baseline_kind": baseline_kind, "before_file": before_file,
                         "after_file": after_file, "protocol_parameters": "same_fullfit_D04_for_before_and_after",
                         "before_Y38_D04": pre, "after_Y38_D04": post,
                         "continuous_delta_after_minus_before": post-pre,
                         "continuous_nonincrease_exact": post <= pre,
                         "A_before": a_before, "A_after": a_after,
                         "A_delta_after_minus_before": a_after-a_before,
                         "A_nonincrease": a_after <= a_before,
                         "B_before": b_before, "B_after": b_after,
                         "B_delta_after_minus_before": b_after-b_before,
                         "B_nonincrease": b_after <= b_before,
                         "both_protocols_nonincrease": (a_after <= a_before) & (b_after <= b_before),
                         "all_criteria_pass": (post <= pre) & (a_after <= a_before) & (b_after <= b_before)})


def build_transfer_comparisons(parameters, observed):
    comparisons = []
    pairs = [
        ("joint231_model_source", "question3_transfer_before_profiles_D04_scale.csv", "question3_transfer_after_profiles_D04_scale.csv"),
        ("structure_original_D01_model_source", "question3_structure_transfer_original_D01_source_profiles.csv", "question3_structure_transfer_after_profiles_D04_scale.csv"),
        ("structure_reexpressed_model_source", "question3_structure_transfer_source_profiles_D04_scale.csv", "question3_structure_transfer_after_profiles_D04_scale.csv"),
        ("observed_guard_original_D01_model_source", "question3_observed_source_guard_original_source_profiles_D04_scale.csv", "question3_observed_source_guard_after_profiles_D04_scale.csv"),
        ("observed_guard_reexpressed_model_source", "question3_observed_source_guard_reexpressed_source_profiles_D04_scale.csv", "question3_observed_source_guard_after_profiles_D04_scale.csv"),
    ]
    for branch, before_name, after_name in pairs:
        before, after = _read_profiles(before_name), _read_profiles(after_name)
        if before is not None and after is not None:
            comparisons.append(_comparison_rows(before, after, parameters, branch, "model_prediction", before_name, after_name))
    # 观测D04基线与模型迁移前预测是两种不同比较，必须分别列出。
    observed_pairs = [
        ("joint231_observed_D04_source", "question3_transfer_after_profiles_D04_scale.csv"),
        ("structure_observed_D04_source", "question3_structure_transfer_after_profiles_D04_scale.csv"),
        ("observed_source_guard", "question3_observed_source_guard_after_profiles_D04_scale.csv"),
    ]
    for branch, after_name in observed_pairs:
        after = _read_profiles(after_name)
        if after is None:
            continue
        before = observed.reindex(after.index).copy()
        if before[TARGETS].isna().any().any():
            raise ValueError(f"无法按object找到观测评分：{branch}")
        before["source_object"] = before.index
        comparisons.append(_comparison_rows(before, after, parameters, branch, "observed_D04", "data/D04.csv aligned by object", after_name))
    if comparisons:
        out = pd.concat(comparisons, ignore_index=True)
        out.to_csv(RESULTS / "question3_protocol_K_comparison.csv", index=False)
        summary = out.groupby(["branch", "baseline_kind"], as_index=False).agg(
            n_objects=("source_object", "size"),
            continuous_nonincrease_exact_count=("continuous_nonincrease_exact", "sum"),
            A_nonincrease_count=("A_nonincrease", "sum"), B_nonincrease_count=("B_nonincrease", "sum"),
            both_protocols_nonincrease_count=("both_protocols_nonincrease", "sum"),
            all_criteria_pass_count=("all_criteria_pass", "sum"),
            maximum_continuous_delta=("continuous_delta_after_minus_before", "max"))
        summary.to_csv(RESULTS / "question3_protocol_K_summary.csv", index=False)
        return summary
    return pd.DataFrame()


def draw_protocol_figure(observed, parameters, distribution):
    """只画已经确定的协议与已有OOF等级，没有拟合新的预测器。"""
    FIGURES.mkdir(parents=True, exist_ok=True)
    j = TARGETS.index("Y38")
    actual = observed.Y38.to_numpy()
    span = float(np.ptp(actual))
    grid = np.linspace(float(actual.min()-.04*span), float(actual.max()+.04*span), 2000)
    a = np.clip(np.floor(3. + (grid-parameters["A"]["mu"][j])/parameters["A"]["sd"][j]+.5),0,6)
    b = np.searchsorted(parameters["B"]["cutpoints"][j], grid, side="right")
    fig, axes = plt.subplots(1,2,figsize=(12,4.4),dpi=150)
    axes[0].step(grid,a,where="post",label="Protocol A: mean / SD",color="#2074b5",lw=1.8)
    axes[0].step(grid,b,where="post",label="Protocol B: training quantiles",color="#e38123",lw=1.8,linestyle="--")
    axes[0].plot(actual,np.full(len(actual),-.18),"|",color="#666666",alpha=.35,label="Observed D04 positions")
    axes[0].set(xlabel="Continuous Y38 in D04 space",ylabel="Declared protocol grade",title="Same full-data parameters",ylim=(-.4,6.35),yticks=range(7))
    axes[0].legend(fontsize=8,loc="lower right")
    levels=np.arange(7)
    for protocol,offset,color in (("A",-.18,"#2074b5"),("B",.18,"#e38123")):
        counts=distribution[(distribution.dataset=="oof")&(distribution.protocol==protocol)].set_index("grade").reindex(levels)["count"].to_numpy()
        axes[1].bar(levels+offset,counts,width=.36,color=color,label=f"Protocol {protocol}")
    axes[1].set(xlabel="Declared protocol grade",ylabel="Number of objects",title="Out-of-fold Y38 grades (250 objects)",xticks=levels)
    axes[1].legend(fontsize=9)
    fig.suptitle("Two declared protocols, not original-grade truth",fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGURES/"question1_protocol_AB_Y38.png")
    plt.close(fig)


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    observed = pd.read_csv(ROOT / "data/D04.csv").set_index("object", drop=False)
    if observed.index.duplicated().any():
        raise ValueError("D04的object必须唯一")
    full_parameters = fit_protocols(observed[TARGETS])
    parameter_rows = _parameter_rows(full_parameters, "fullfit", 0)
    fitted = pd.read_csv(RESULTS / "question1_continuous_fitted.csv")
    oof = pd.read_csv(RESULTS / "question1_continuous_oof.csv")
    folds = pd.read_csv(RESULTS / "question1_cv_folds.csv").set_index("object")
    agreement, k_distribution = [], []
    for dataset, scores in (("fitted", fitted), ("oof", oof)):
        if scores.object.duplicated().any() or set(scores.object) != set(observed.index):
            raise ValueError(f"评分矩阵的object与D04不一致：{dataset}")
        metadata = scores[[c for c in scores.columns if c not in TARGETS]].copy()
        if dataset == "fitted":
            grades = {protocol: apply_protocol(scores, full_parameters, protocol) for protocol in ("A", "B")}
        else:
            fold_for_row = folds.reindex(scores.object).random_outer_fold.to_numpy()
            fold_for_observed = folds.reindex(observed.index).random_outer_fold.to_numpy()
            if pd.isna(fold_for_row).any() or pd.isna(fold_for_observed).any():
                raise ValueError("折外协议缺少已有random_outer_fold")
            grades = {protocol: pd.DataFrame(index=scores.index, columns=TARGETS, dtype=int) for protocol in ("A", "B")}
            for fold in np.unique(fold_for_row):
                train_y = observed.loc[fold_for_observed != fold, TARGETS]
                parameters = fit_protocols(train_y)
                parameter_rows.extend(_parameter_rows(parameters, "oof", int(fold)))
                positions = np.flatnonzero(fold_for_row == fold)
                for protocol in ("A", "B"):
                    grades[protocol].iloc[positions] = apply_protocol(scores.iloc[positions], parameters, protocol).to_numpy()
            grades = {protocol: value.astype(int) for protocol, value in grades.items()}
        for protocol in ("A", "B"):
            pd.concat([metadata, grades[protocol]], axis=1).to_csv(RESULTS / f"question1_protocol_{protocol}_{dataset}_grades.csv", index=False)
            k_distribution.extend(_k_distribution_rows(grades[protocol], dataset, protocol))
        difference = grades["B"] - grades["A"]
        pd.concat([metadata, difference], axis=1).to_csv(RESULTS / f"question1_protocol_difference_{dataset}_B_minus_A.csv", index=False)
        agreement.extend(_agreement_rows(grades["A"], grades["B"], dataset))
    pd.DataFrame(parameter_rows).to_csv(RESULTS / "question1_protocol_cutpoints.csv", index=False)
    agreement = pd.DataFrame(agreement)
    agreement["comparison_kind"] = "protocol_A_vs_protocol_B"
    agreement.to_csv(RESULTS / "question1_protocol_agreement.csv", index=False)
    distribution = pd.DataFrame(k_distribution)
    distribution.to_csv(RESULTS / "question1_protocol_K_distribution.csv", index=False)
    generated_distribution=[]
    for source_name, output_name, dataset in [
        ("question3_structure_generated_profiles_D04_scale.csv", "question3_structure_generated_profiles_PROTOCOL_B.csv", "structure_generated300"),
        ("question3_structure_representatives_profiles_D04_scale.csv", "question3_structure_representatives_profiles_PROTOCOL_B.csv", "structure_representatives9"),
    ]:
        source_path = RESULTS / source_name
        if source_path.exists():
            continuous = pd.read_csv(source_path)
            meta = continuous[[c for c in continuous.columns if c not in TARGETS]]
            grades = apply_protocol(continuous, full_parameters, "B")
            pd.concat([meta, grades], axis=1).to_csv(RESULTS / output_name, index=False)
            for protocol in ("A","B"):
                protocol_grades=apply_protocol(continuous,full_parameters,protocol)
                overall_rows=_k_distribution_rows(protocol_grades,dataset,protocol)
                for row in overall_rows:
                    row.update({"grouping":"overall","regime":"__all__"})
                generated_distribution.extend(overall_rows)
                condition_column=next((c for c in ("regime","condition_regime") if c in continuous.columns),None)
                if condition_column is not None:
                    for regime in sorted(continuous[condition_column].dropna().unique()):
                        selected=continuous[condition_column] == regime
                        class_rows=_k_distribution_rows(protocol_grades.loc[selected],dataset,protocol)
                        for row in class_rows:
                            row.update({"grouping":"class","regime":regime})
                        generated_distribution.extend(class_rows)
    if generated_distribution:
        pd.DataFrame(generated_distribution).to_csv(RESULTS/"question3_protocol_K_distribution.csv",index=False)
    draw_protocol_figure(observed,full_parameters,distribution)
    transfer_summary = build_transfer_comparisons(full_parameters, observed)
    print("Two declared protocols; neither is claimed to recover original absolute grades.")
    print(agreement[agreement.target == "overall"].to_string(index=False))
    print(distribution.groupby(["dataset", "protocol"])[["K_ge2_count", "K_ge2_rate"]].first().to_string())
    print(transfer_summary.to_string(index=False))


if __name__ == "__main__":
    main()
