"""问题3：小样本类别条件生成与有约束的候选迁移。

输出均保留D01的混合观测刻度。这是未强制五个已识别候选派生关系的联合基线；
结构修复见structure_generation.py。原始等级不能由本脚本补造。
运行：python code/generation.py（在A题_数学手记目录），或传 --project 原题目录。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial.distance import cdist, pdist
from sklearn.covariance import LedoitWolf
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.preprocessing import QuantileTransformer

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [f"V{i:03d}" for i in range(1, 232)]
CRITICAL = {"V004": 17.25, "V039": 0.29925, "V021": 0.206333333, "V109": 0.35}
DERIVED = ["V037", "V228", "V229", "V230", "V231"]
SEED = 20261026


class ConditionalGaussian:
    """先把各坐标变成近似正态，再共享类别内的相关结构。

    类别样本越少，均值越向总体均值缩回；不是凭空训练22套大协方差。
    每一次留出评估均重新fit本类，因此验证样本不会进入分位数或插补值。
    """
    def __init__(self, covariance="lw", rank=5, tau=5.0, conditional=True, posterior_predictive=False):
        self.covariance = covariance
        self.rank = rank
        self.tau = tau
        self.conditional = conditional
        self.posterior_predictive=posterior_predictive

    def fit(self, x, groups):
        self.imputer = SimpleImputer(strategy="median")
        a = self.imputer.fit_transform(np.asarray(x))
        self.n_features_=a.shape[1]
        self.quantiles = QuantileTransformer(
            n_quantiles=min(len(a), 100), output_distribution="normal",
            random_state=SEED, subsample=None)
        z = self.quantiles.fit_transform(a)
        self.groups = np.asarray(groups)
        self.counts={group:int(np.sum(self.groups==group)) for group in np.unique(self.groups)}
        self.global_mean = z.mean(axis=0)
        self.means = {}
        residual = z.copy()
        for group in np.unique(self.groups):
            loc = self.groups == group
            sample_mean = z[loc].mean(axis=0)
            weight = loc.sum() / (loc.sum() + self.tau)
            self.means[group] = weight * sample_mean + (1-weight) * self.global_mean
            residual[loc] -= sample_mean
        if not self.conditional:
            residual = z - self.global_mean
        # 共享协方差牺牲类别特有的相关性，换取小样本下可估计的参数量。
        if self.covariance == "lw":
            estimator = LedoitWolf(assume_centered=True).fit(residual)
            self.cov = estimator.covariance_
            self.shrinkage = float(estimator.shrinkage_)
        else:
            sample_cov = residual.T @ residual / len(residual)
            values, vectors = np.linalg.eigh(sample_cov)
            order = np.argsort(values)[::-1]
            values, vectors = values[order], vectors[:, order]
            q = min(self.rank, len(values)-1, len(z)-2)
            sigma2 = max(float(values[q:].mean()), 1e-4)
            w = vectors[:, :q] * np.sqrt(np.maximum(values[:q] - sigma2, 0))
            self.cov = w @ w.T + sigma2 * np.eye(len(values))
            self.shrinkage = None
        if self.posterior_predictive and self.conditional:
            # 类均值吃掉C个自由度。此处为模型内修正，不声称恢复LW的iid最优定理。
            self.cov*=len(z)/max(len(z)-len(self.counts),1)
        values, vectors = np.linalg.eigh(self.cov)
        self.factor = vectors * np.sqrt(np.maximum(values, 1e-8))
        self.precision = np.linalg.inv(self.cov + 1e-8*np.eye(self.cov.shape[0]))
        self.logdet = np.linalg.slogdet(self.cov)[1]
        return self

    def transform(self, x):
        return self.quantiles.transform(self.imputer.transform(np.asarray(x)))

    def mean(self, group):
        return self.means[group] if self.conditional else self.global_mean

    def sample(self, group, n, rng):
        variance_factor=1.+1./(self.counts[group]+self.tau) if self.posterior_predictive and self.conditional else 1.
        z = self.mean(group) + np.sqrt(variance_factor)*rng.normal(size=(n, self.n_features_)) @ self.factor.T
        return self.quantiles.inverse_transform(z)

    def nll(self, x, groups):
        z = self.transform(x)
        d = np.stack([row-self.mean(group) for row, group in zip(z, groups)])
        factors=np.array([1.+1./(self.counts[group]+self.tau) for group in groups]) if self.posterior_predictive and self.conditional else np.ones(len(z))
        return .5 * (self.n_features_*np.log(2*np.pi) + self.logdet+self.n_features_*np.log(factors)
                      + np.einsum("ij,jk,ik->i", d, self.precision, d)/factors)


def distribution_distances(a, b, bandwidth):
    """V统计量可用于只有一个留出样本的小类；它有有限样本偏差，不作显著性证明。"""
    aa, bb, ab = cdist(a, a), cdist(b, b), cdist(a, b)
    energy = 2*ab.mean() - aa.mean() - bb.mean()
    scale = 2*bandwidth**2
    mmd_v = np.exp(-aa**2/scale).mean() + np.exp(-bb**2/scale).mean() \
            - 2*np.exp(-ab**2/scale).mean()
    return float(energy), float(mmd_v)


def evaluate_generators(x, groups, repeats=5):
    """预先列出的比较；不能把重复切分的离散程度当成独立实验的置信区间。"""
    rows = []
    splits = StratifiedShuffleSplit(n_splits=repeats, test_size=.30, random_state=SEED)
    candidates = [("global_lw", {"conditional": False}),
                  ("conditional_lw", {}),
                  ("conditional_ppca5", {"covariance": "ppca", "rank": 5}),
                  ("conditional_ppca10", {"covariance": "ppca", "rank": 10})]
    for split, (tr, te) in enumerate(splits.split(x, groups)):
        train_x, hold_x = x.iloc[tr], x.iloc[te]
        train_g, hold_g = groups[tr], groups[te]
        for name, settings in candidates:
            model = ConditionalGaussian(**settings).fit(train_x, train_g)
            ztr, zte = model.transform(train_x), model.transform(hold_x)
            # 核宽只看训练特征，不看留出组的差异。
            bandwidth = float(np.median(pdist(ztr)))
            losses = model.nll(hold_x, hold_g)
            for group in np.unique(groups):
                train_real, real = ztr[train_g == group], zte[hold_g == group]
                rng = np.random.default_rng(SEED + split)
                ed, md = [], []
                # 生成参照数与该类真实训练参照数相同，避免样本量偏差不对称。
                for _ in range(10):
                    gen = model.transform(model.sample(group, len(train_real), rng))
                    e, m = distribution_distances(gen, real, bandwidth)
                    ed.append(e)
                    md.append(m)
                ref_e, ref_m = distribution_distances(train_real, real, bandwidth)
                rows.append({"split": split, "method": name, "regime": group,
                             "n_train": len(train_real), "n_holdout": len(real),
                             "gaussian_rank_space_nll": losses[hold_g == group].mean(),
                             "energy_v": np.mean(ed), "mmd2_v": np.mean(md),
                             "real_train_vs_holdout_energy_v": ref_e,
                             "real_train_vs_holdout_mmd2_v": ref_m})
    return pd.DataFrame(rows)


def native_critical(x, reference=None, objects=None):
    """C1/C3正数可逆；旧对象的零下限用ref_scale恢复，新候选下限选零。

    后一种只是一个可行原生值，不能宣称从log下限唯一反演出了零。
    """
    result = x[list(CRITICAL)].copy()
    for feature in ("V004", "V021"):
        result[feature] = np.power(10.0, result[feature])
    if reference is not None and objects is not None:
        ref = reference.set_index("object")
        for feature in CRITICAL:
            values = ref.reindex(np.asarray(objects))[feature].to_numpy()
            use = np.isfinite(values)
            if feature not in ("V004", "V021"):
                use &= x[feature].isna().to_numpy()
            result[feature] = np.where(use, values, result[feature])
    return result


def tail_compatibility(x, groups, reference, objects):
    native = native_critical(x, reference, objects)
    rows = []
    for feature in CRITICAL:
        source = native.loc[groups == "R15", feature].dropna().to_numpy()
        target = native.loc[groups == "R20", feature].dropna().to_numpy()
        grid = np.unique(np.concatenate([source, target]))
        for threshold in grid:
            source_tail, target_tail = np.mean(source > threshold), np.mean(target > threshold)
            rows.append({"feature": feature, "native_threshold": threshold,
                         "R15_tail": source_tail, "R20_tail": target_tail,
                         "target_minus_source_tail": target_tail-source_tail})
    return pd.DataFrame(rows)


def feasibility_bounds(tail):
    """根代理推导的一维经验下界，不是总体置信下界，也非联合充分条件。

    不增约束使F_Q>=F_source；而F_source-F_target=target_tail-source_tail。
    一维W1是CDF间面积，因此把正尾差乘以相邻断点间距求和即可。
    """
    rows=[]
    for feature,threshold in CRITICAL.items():
        a=tail.loc[tail.feature==feature].sort_values("native_threshold")
        t=a.native_threshold.to_numpy()
        diff=a.target_minus_source_tail.to_numpy()
        area=float(np.sum(np.maximum(diff[:-1],0)*np.diff(t)))
        rows.append({"feature":feature,"critical_threshold_native":threshold,"native_W1_lower_bound":area,
                     "W1_bound_divided_by_critical_threshold":area/threshold,
                     "max_positive_tail_gap":max(float(diff.max()),0.),
                     "scope":"empirical_1D_distributions; not_population_CI_or_joint_sufficiency"})
    return pd.DataFrame(rows)


def predict_profiles(x, prediction):
    scores = prediction.predict_continuous(pd.DataFrame(x, columns=FEATURES))
    grades = prediction.working_grades(scores)
    return scores.reset_index(drop=True), grades.reset_index(drop=True)


def transfer_candidates(model, x, groups, objects, prediction, reference):
    """最接近目标候选的受限点：坐标约束+实际评分器约束；逐个结果再核查。

    评分器可能含截尾，故优化直接调用评分器。优化失败时源向量是已知可行点。
    """
    source_frame = x.loc[groups == "R15"].copy()
    source_objects = objects[groups == "R15"]
    source_frame.index = source_objects
    ref_by_object = reference.set_index("object")
    supplements = []
    # 只补原D01缺失的原生临界字段；D08与已观测D01不一致时保留D01。
    for feature in ("V039", "V109"):
        for obj in source_objects:
            if pd.isna(source_frame.at[obj, feature]):
                value = ref_by_object.at[obj, feature]
                if pd.notna(value):
                    source_frame.at[obj, feature] = value
                    supplements.append({"object":obj,"feature":feature,"source":"D08.ref_scale_for_missing_D01_only","value":value})
    source = model.imputer.transform(np.asarray(source_frame))
    zsource = model.transform(source_frame)
    proposal_z = zsource - model.mean("R15") + model.mean("R20")
    proposal = model.quantiles.inverse_transform(proposal_z)
    scales = np.nanquantile(x.to_numpy(), .9, axis=0)-np.nanquantile(x.to_numpy(), .1, axis=0)
    scales = np.where(scales > 1e-8, scales, 1.)
    cidx = [FEATURES.index(f) for f in CRITICAL]
    lower = np.nanmin(x, axis=0)
    upper = np.nanmax(x, axis=0)
    score_bundle=prediction.load_final_model()
    score_pre=score_bundle.estimator.regressor_.named_steps["preprocess"]
    score_slope=score_bundle.linear_coef_[37]/score_pre.scale_
    results, comparisons, optimisation = [], [], []
    for row_index, (src, candidate, obj) in enumerate(zip(source, proposal, source_objects)):
        before_native = native_critical(pd.DataFrame([src], columns=FEATURES), reference, [obj]).iloc[0]
        critical_caps=src[cidx].copy()
        # CSV保留位数会使10**D01比ref原生值略大；以原生上界回推约束，
        # 避免“观测刻度相等”掩盖原生量纲的微小上升。
        for j,feature in enumerate(CRITICAL):
            if feature in ("V004","V021") and before_native[feature]>0:
                cap=np.nextafter(np.log10(before_native[feature]),-np.inf)
                critical_caps[j]=min(critical_caps[j],cap)
        source_score = float(prediction.predict_continuous(pd.DataFrame([src], columns=FEATURES))["Y38"].iloc[0])
        capped = candidate.copy()
        capped[cidx] = np.minimum(capped[cidx], critical_caps)
        upper_row = upper.copy()
        upper_row[cidx] = np.minimum(upper_row[cidx], critical_caps)
        # 在按实际坐标变动尺度归一化的空间优化，避免大数值列支配距离。
        origin = capped.copy()
        def unpack(u):
            return origin + u * scales
        def objective(u):
            displacement=(unpack(u)-candidate)/scales
            return .5*float(displacement @ displacement)
        def objective_gradient(u):
            return (unpack(u)-candidate)/scales
        def score_constraint(u):
            a = pd.DataFrame([unpack(u)], columns=FEATURES)
            return source_score-float(prediction.predict_continuous(a)["Y38"].iloc[0])
        def score_gradient(u):
            a=unpack(u)
            active=(a>score_pre.low_) & (a<score_pre.high_)
            return -score_slope*active*scales
        lower_row=np.minimum(lower,src)
        lower_row[cidx]=np.minimum(lower_row[cidx],critical_caps)
        upper_row=np.maximum(upper_row,lower_row)
        bounds = list(zip((lower_row-origin)/scales, (upper_row-origin)/scales))
        attempt = minimize(objective, np.zeros(len(FEATURES)), jac=objective_gradient, method="SLSQP",
                           bounds=bounds, constraints={"type": "ineq", "fun": score_constraint,"jac":score_gradient},
                           options={"maxiter": 120, "ftol": 1e-9})
        translated = unpack(attempt.x)
        translated[cidx] = np.minimum(translated[cidx], critical_caps)
        after_score = float(prediction.predict_continuous(pd.DataFrame([translated], columns=FEATURES))["Y38"].iloc[0])
        score_ok = after_score <= source_score+1e-8
        critical_ok = bool(np.all(translated[cidx] <= src[cidx]+1e-10))
        fallback = not (score_ok and critical_ok and np.isfinite(translated).all())
        if fallback:
            translated = src.copy()
            after_score = source_score
        results.append(translated)
        after_native = native_critical(pd.DataFrame([translated], columns=FEATURES)).iloc[0]
        proposal_native=native_critical(pd.DataFrame([candidate],columns=FEATURES)).iloc[0]
        proposal_score=float(prediction.predict_continuous(pd.DataFrame([candidate],columns=FEATURES))["Y38"].iloc[0])
        if fallback:
            after_native=before_native.copy()
        # 同一log下限既可能来自零，也可能来自被替代负值。临界C1/C3旧样本
        # 为零且迁移观测值未升时，选择原生零作为候选，实现约束但标明歧义。
        for feature in ("V004", "V021"):
            idx = FEATURES.index(feature)
            if before_native[feature] == 0 and translated[idx] <= src[idx]+1e-10:
                after_native[feature] = 0.
            if before_native[feature] == 0 and candidate[idx] <= src[idx]+1e-10:
                proposal_native[feature] = 0.
        for feature, threshold in CRITICAL.items():
            comparisons.append({"object": obj, "criterion": feature,
                                "before_native": before_native[feature],
                                "proposal_native_before_projection":proposal_native[feature],
                                "after_native_candidate": after_native[feature],
                                "threshold": threshold,
                                "before_ratio": before_native[feature]/threshold,
                                "after_ratio": after_native[feature]/threshold,
                                "nonworsening": after_native[feature] <= before_native[feature]+1e-8,
                                "guarantee_scope": "candidate_native_assignment; censored_floor_not_unique"})
        comparisons.append({"object": obj, "criterion": "Y38_model_continuous",
                            "before_native": source_score, "after_native_candidate": after_score,
                            "proposal_native_before_projection":proposal_score,
                            "threshold": np.nan, "before_ratio": np.nan, "after_ratio": np.nan,
                            "nonworsening": after_score <= source_score+1e-8,
                            "guarantee_scope": "model_prediction_only; true_K_grade_unidentified"})
        optimisation.append({"object": obj, "optimizer_success": bool(attempt.success),
                             "optimizer_message": str(attempt.message), "fallback_to_source": fallback,
                             "standardized_displacement": np.linalg.norm((translated-src)/scales),
                             "distance_to_R20_mean_before": np.linalg.norm(zsource[row_index]-model.mean("R20")),
                             "distance_to_R20_mean_after": np.linalg.norm(model.transform(pd.DataFrame([translated],columns=FEATURES))[0]-model.mean("R20"))})
    return np.asarray(results), pd.DataFrame(comparisons), pd.DataFrame(optimisation), source, pd.DataFrame(supplements)


def main(project=None, repeats=5, reuse_heldout=False):
    project = Path(project) if project else ROOT.parent
    out, figures = ROOT/"results", ROOT/"figures"
    out.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    raw = pd.read_csv(project/"data"/"D01.csv")
    x, groups, objects = raw[FEATURES], raw.regime.to_numpy(), raw.object.to_numpy()
    reference = pd.read_excel(project/"data"/"D08.xlsx", sheet_name="ref_scale")
    cache=out/"question3_heldout_generator_metrics.csv"
    evaluation = pd.read_csv(cache) if reuse_heldout and cache.exists() else evaluate_generators(x, groups, repeats)
    evaluation.to_csv(out/"question3_heldout_generator_metrics.csv", index=False)
    summary = evaluation.groupby("method")[["gaussian_rank_space_nll","energy_v","mmd2_v"]].mean()
    summary.to_csv(out/"question3_heldout_generator_summary.csv")
    model = ConditionalGaussian().fit(x, groups)
    rng = np.random.default_rng(SEED)
    generated = []
    for group in ("R20", "R12", "R13"):
        a = pd.DataFrame(model.sample(group, 100, rng), columns=FEATURES)
        a.insert(0, "regime", group)
        a.insert(0, "generated_id", [f"{group}_g{i+1:03d}" for i in range(len(a))])
        generated.append(a)
    generated = pd.concat(generated, ignore_index=True)
    generated.to_csv(out/"question3_generated_features_D01_scale.csv", index=False)
    # 距离不为零说明没有逐行照搬；并不证明生成值真实。
    zgenerated, zreal = model.transform(generated[FEATURES]), model.transform(x)
    nearest = cdist(zgenerated, zreal)
    pd.DataFrame({"generated_id":generated.generated_id,"regime":generated.regime,
                  "nearest_training_object":objects[nearest.argmin(axis=1)],
                  "nearest_training_distance":nearest.min(axis=1)}).to_csv(out/"question3_novelty_diagnostic.csv",index=False)
    tail = tail_compatibility(x, groups, reference, objects)
    tail.to_csv(out/"question3_tail_compatibility.csv",index=False)
    feasibility_bounds(tail).to_csv(out/"question3_feasibility_bounds.csv",index=False)
    import prediction
    continuous, grades = predict_profiles(generated[FEATURES], prediction)
    continuous.insert(0, "regime",generated.regime)
    continuous.insert(0, "generated_id",generated.generated_id)
    continuous.to_csv(out/"question3_generated_profiles_D04_scale.csv",index=False)
    grades.insert(0,"regime",generated.regime)
    grades.insert(0,"generated_id",generated.generated_id)
    grades.to_csv(out/"question3_generated_profiles_WORKING_GRADES_NOT_IDENTIFIED.csv",index=False)
    moved, comparison, opt, restored_source, supplements = transfer_candidates(model,x,groups,objects,prediction,reference)
    moved_frame=pd.DataFrame(moved,columns=FEATURES)
    moved_frame.insert(0,"source_object",objects[groups=="R15"])
    moved_frame.to_csv(out/"question3_R15_to_R20_candidates.csv",index=False)
    comparison.to_csv(out/"question3_transfer_critical_comparison.csv",index=False)
    opt.to_csv(out/"question3_transfer_optimization.csv",index=False)
    restored=pd.DataFrame(restored_source,columns=FEATURES)
    restored.insert(0,"source_object",objects[groups=="R15"])
    restored.to_csv(out/"question3_transfer_source_inputs.csv",index=False)
    supplements.to_csv(out/"question3_source_critical_supplements.csv",index=False)
    before_s,before_g=predict_profiles(restored_source,prediction)
    after_s,after_g=predict_profiles(moved,prediction)
    before_s.insert(0,"source_object",objects[groups=="R15"])
    after_s.insert(0,"source_object",objects[groups=="R15"])
    before_s.to_csv(out/"question3_transfer_before_profiles_D04_scale.csv",index=False)
    after_s.to_csv(out/"question3_transfer_after_profiles_D04_scale.csv",index=False)
    k=pd.DataFrame({"object":objects[groups=="R15"],"before_working_K":before_g.Y38,
                    "after_working_K":after_g.Y38,"true_K_nonworsening":"unidentified",
                    "working_grade_formula":"clip(round(3+(prediction-location)/scale),0,6)"})
    k.to_csv(out/"question3_transfer_K_WORKING_ONLY.csv",index=False)
    note={"generator":"conditional Gaussian copula; shared LedoitWolf residual covariance",
          "class_mean_pseudocount":5,"pooled_covariance_shrinkage":model.shrinkage,
          "generated_per_class":100,"seed":SEED,"evaluation_repeats":repeats,
          "derived_feature_status":"baseline_joint_coordinates; five_candidate_relations_not_enforced_here; see_structure_outputs",
          "true_grade_status":"unidentified; working grades are an explicit convention",
          "transfer_scope":"C1-C4 candidate native assignment and fitted continuous Y38 only",
          "tail_max_target_minus_source":tail.groupby("feature").target_minus_source_tail.max().to_dict(),
          "heldout_mean_distances":summary.to_dict(orient="index"),
          "fallback_count":int(opt.fallback_to_source.sum())}
    (out/"question3_summary.json").write_text(json.dumps(note,ensure_ascii=False,indent=2),encoding="utf-8")
    make_figures(evaluation,tail,opt,figures)
    print(json.dumps(note,ensure_ascii=False,indent=2))


def make_figures(evaluation,tail,opt,folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    order=["global_lw","conditional_lw","conditional_ppca5","conditional_ppca10"]
    for ax,metric,title in zip(axes,["energy_v","gaussian_rank_space_nll"],["Held-out energy distance (V)","Held-out Gaussian score in rank space"]):
        values=[evaluation.loc[evaluation.method==m].groupby("split")[metric].mean().to_numpy() for m in order]
        ax.boxplot(values,tick_labels=order,showmeans=True)
        ax.tick_params(axis="x",rotation=20)
        ax.set_title(title)
        ax.grid(axis="y",alpha=.2)
    fig.tight_layout(); fig.savefig(folder/"question3_heldout_models.png",dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,8))
    for ax,feature in zip(axes.flat,CRITICAL):
        a=tail.loc[tail.feature==feature]
        ax.step(a.native_threshold,a.R15_tail,where="post",label="R15 source")
        ax.step(a.native_threshold,a.R20_tail,where="post",label="R20 target")
        ax.set_xscale("symlog",linthresh=.01)
        ax.set(title=feature,xlabel="native threshold t",ylabel="fraction above t")
        ax.legend();ax.grid(alpha=.2)
    fig.suptitle("Pointwise non-increase requires target tail <= source tail")
    fig.tight_layout();fig.savefig(folder/"question3_critical_tail_curves.png",dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5))
    positions=np.arange(len(opt))
    ax.plot(positions,opt.distance_to_R20_mean_before,"o-",label="before")
    ax.plot(positions,opt.distance_to_R20_mean_after,"o-",label="constrained candidate")
    ax.set_xticks(positions,opt.object.astype(str));ax.set(xlabel="source object (R15)",ylabel="rank-space distance to R20 mean")
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(folder/"question3_transfer_distances.png",dpi=160);plt.close(fig)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--repeats",type=int,default=5)
    parser.add_argument("--reuse-heldout",action="store_true",help="仅重算最终生成和迁移，复用已有留出比较")
    args=parser.parse_args()
    main(args.project,args.repeats,args.reuse_heldout)
