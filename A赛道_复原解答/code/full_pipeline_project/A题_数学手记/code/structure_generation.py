"""问题3的结构修复：先生成226个基础量，再计算五个候选派生量。

V001--V036使用D08参照原生值，保留零、负值和真正的缺失；其余
基础列保留D01观察刻度。五个关系是数据支持的候选，不是官方定义。
运行：python code/structure_generation.py --project 原题目录
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial.distance import cdist, pdist
from sklearn.model_selection import StratifiedShuffleSplit

from generation import ConditionalGaussian, distribution_distances
from derived_relations import (
    candidate_derived_from_native, fit_positive_floors, native_to_recorded, CANDIDATE_COEFFICIENTS,
)

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [f"V{i:03d}" for i in range(1, 232)]
DERIVED = ["V037", "V228", "V229", "V230", "V231"]
BASE = [v for v in FEATURES if v not in DERIVED]
CRITICAL = {"V004": 17.25, "V039": .29925, "V021": .206333333, "V109": .35}
ATOM_FIELDS = ("V002", "V004", "V021", "V026", "V036")
SEED = 20261026


def load_native_inputs(project):
    """跨表按object对齐。参照缺失保留NA，不能用10**log下限伪造原生量。"""
    raw = pd.read_csv(Path(project)/"data"/"D01.csv")
    reference = pd.read_excel(Path(project)/"data"/"D08.xlsx", sheet_name="ref_scale")
    reference = reference.set_index("object").reindex(raw.object)
    reference.index = raw.index
    native = raw[FEATURES].copy()
    for i in range(1, 37):
        native[f"V{i:03d}"] = reference[f"V{i:03d}"]
    for var in ("V039", "V109"):
        native[var] = native[var].fillna(reference[var])
    return raw, native[BASE]


def expand_native(basis):
    """基础量保持不动；派生量只能由同一组基础量计算。"""
    full = basis[BASE].copy()
    derived = candidate_derived_from_native(full)
    for var in DERIVED:
        full[var] = derived[var]
    return full[FEATURES]


def valid_native(basis):
    derived = candidate_derived_from_native(basis).to_numpy()
    return np.isfinite(np.asarray(basis)).all(axis=1) & np.isfinite(derived).all(axis=1) & (derived > 0).all(axis=1)


def sample_valid(model, group, n, rng):
    """拒绝非正派生和；绝不把错误的和取绝对值或截成epsilon来输出。"""
    accepted, attempts, rejected, proposed, valid_count = [], 0, 0, 0, 0
    proposal_zero_counts = {v: 0 for v in ATOM_FIELDS}
    valid_zero_counts = {v: 0 for v in ATOM_FIELDS}
    remaining = n
    while remaining and attempts < 60:
        batch = pd.DataFrame(model.sample(group, max(2*remaining, 50), rng), columns=BASE)
        good = valid_native(batch)
        proposed += len(batch)
        valid_count += int(good.sum())
        for var in ATOM_FIELDS:
            proposal_zero_counts[var] += int((batch[var] == 0).sum())
            valid_zero_counts[var] += int((batch.loc[good, var] == 0).sum())
        rejected += int((~good).sum())
        kept = batch.loc[good].iloc[:remaining]
        accepted.append(kept)
        remaining -= len(kept)
        attempts += 1
    if remaining:
        raise RuntimeError(f"{group}有效派生关系重采样仍缺{remaining}个样本")
    retained = pd.concat(accepted, ignore_index=True)
    diagnostic = {"regime": group, "batches": attempts, "rejected_invalid_candidates": rejected,
                  "proposed_count": proposed, "valid_proposal_count": valid_count, "kept_count": len(retained),
                  "rejection_rate": rejected/proposed,
                  "proposal_zero_rate_before_rejection": {v: proposal_zero_counts[v]/proposed for v in ATOM_FIELDS},
                  "valid_pool_zero_rate_before_truncation": {v: valid_zero_counts[v]/valid_count for v in ATOM_FIELDS},
                  "retained_zero_rate": {v: float((retained[v] == 0).mean()) for v in ATOM_FIELDS},
                  "theoretical_zero_probability_before_rejection": {
                      v: model.atom_probability(group, BASE.index(v), 0.) if hasattr(model, "atom_probability") else None
                      for v in ATOM_FIELDS}}
    return retained, diagnostic


def evaluate_structure_generators(basis, groups, repeats=5, method_names=None):
    """留出比较只在基础量的训练排名空间衡量，重采样后再比较。"""
    rows = []
    splitter = StratifiedShuffleSplit(n_splits=repeats, test_size=.3, random_state=SEED)
    for split, (tr, te) in enumerate(splitter.split(basis, groups)):
        train, holdout = basis.iloc[tr], basis.iloc[te]
        train_groups, holdout_groups = groups[tr], groups[te]
        candidates = [("global_lw", {"conditional": False}),
                      ("conditional_lw", {"conditional": True}),
                      ("conditional_posterior_predictive", {"conditional": True, "posterior_predictive": True}),
                      ("empirical_marginal_copula", {})]
        for name, settings in candidates:
            if method_names is not None and name not in method_names:
                continue
            if name == "empirical_marginal_copula":
                from empirical_copula import ShrunkEmpiricalCopula
                model = ShrunkEmpiricalCopula(**settings).fit(train, train_groups)
            else:
                model = ConditionalGaussian(**settings).fit(train, train_groups)
            ztrain, zhold = model.transform(train), model.transform(holdout)
            bandwidth = max(float(np.median(pdist(ztrain))), 1e-8)
            # 阶梯经验边际含离散原子，旧Gaussian连续排名密度不适用。
            losses = np.full(len(holdout), np.nan) if name == "empirical_marginal_copula" else model.nll(holdout, holdout_groups)
            for group in np.unique(groups):
                real_train = ztrain[train_groups == group]
                real_hold = zhold[holdout_groups == group]
                reference_e, reference_m = distribution_distances(real_train, real_hold, bandwidth)
                rng = np.random.default_rng(SEED+100*split)
                energies, mmds, rejected = [], [], 0
                for _ in range(10):
                    generated, diagnostic = sample_valid(model, group, len(real_train), rng)
                    e, m = distribution_distances(model.transform(generated), real_hold, bandwidth)
                    energies.append(e)
                    mmds.append(m)
                    rejected += diagnostic["rejected_invalid_candidates"]
                rows.append({"split": split, "method": name, "regime": group,
                             "n_train": len(real_train), "n_holdout": len(real_hold),
                             "energy_v": float(np.mean(energies)), "mmd2_v": float(np.mean(mmds)),
                             "gaussian_rank_space_nll": float(losses[holdout_groups == group].mean()),
                             "real_train_vs_holdout_energy_v": reference_e,
                             "real_train_vs_holdout_mmd2_v": reference_m,
                             "invalid_candidates_rejected": rejected,
                             "evaluation_space": "226_native_mixed_base_training_rank_space"})
    return pd.DataFrame(rows)


def tagged(frame, identifiers, kind="generated_id", regime=None):
    result = frame.reset_index(drop=True).copy()
    if regime is not None:
        result.insert(0, "regime", np.asarray(regime))
    result.insert(0, kind, np.asarray(identifiers))
    return result


def relation_diagnostics(native, recorded, stage):
    reconstructed = candidate_derived_from_native(native)
    rows = []
    for var in DERIVED:
        recovered = np.power(10., recorded[var].to_numpy())
        expected = reconstructed[var].to_numpy()
        error = np.abs(recovered-expected)
        rows.append({"stage": stage, "feature": var,
                     "max_absolute_residual": float(error.max()),
                     "max_relative_residual": float(np.max(error/np.maximum(np.abs(expected), 1e-12))),
                     "meaning": "implemented_candidate_formula_consistency; not_official_definition_proof"})
    return pd.DataFrame(rows)


def state_diagnostics(real, generated, real_groups, generated_groups, sampling=None):
    rows = []
    sampling_by_group = {q["regime"]: q for q in sampling or []}
    for group in ("R20", "R12", "R13"):
        for var in ATOM_FIELDS:
            for label, frame, groups in (("real_reference", real, real_groups),
                                         ("generated", generated, generated_groups)):
                q = frame.loc[np.asarray(groups) == group, var]
                observed = q.dropna()
                diagnostic = sampling_by_group.get(group, {}) if label == "generated" else {}
                rows.append({"regime": group, "feature": var, "sample": label,
                             "n_rows": len(q), "n_observed": len(observed),
                             "missing_rate": float(q.isna().mean()),
                             "zero_rate_among_observed": float((observed == 0).mean()),
                             "negative_rate_among_observed": float((observed < 0).mean()),
                             "positive_rate_among_observed": float((observed > 0).mean()),
                             "theoretical_zero_probability_before_rejection": diagnostic.get("theoretical_zero_probability_before_rejection", {}).get(var, np.nan),
                             "proposal_zero_rate_before_rejection": diagnostic.get("proposal_zero_rate_before_rejection", {}).get(var, np.nan),
                             "valid_pool_zero_rate_before_truncation": diagnostic.get("valid_pool_zero_rate_before_truncation", {}).get(var, np.nan),
                             "proposal_count": diagnostic.get("proposed_count", np.nan),
                             "valid_proposal_count": diagnostic.get("valid_proposal_count", np.nan),
                             "kept_count": diagnostic.get("kept_count", np.nan),
                             "rejection_rate": diagnostic.get("rejection_rate", np.nan)})
    return pd.DataFrame(rows)


def aggregate_range_diagnostics(real_basis, generated_basis, real_groups, generated_groups):
    """结构相等是构造结果；范围和超出率另行描述分布是否仍像参照。"""
    real_derived = candidate_derived_from_native(real_basis)
    generated_derived = candidate_derived_from_native(generated_basis)
    rows = []
    for group in ("R20", "R12", "R13"):
        for var in DERIVED:
            real = real_derived.loc[np.asarray(real_groups) == group, var].dropna()
            generated = generated_derived.loc[np.asarray(generated_groups) == group, var]
            low, high = float(real.min()), float(real.max())
            rows.append({"regime": group, "feature": var,
                         "n_real_complete_formula_inputs": len(real), "n_generated": len(generated),
                         "real_candidate_aggregate_min": low, "real_candidate_aggregate_max": high,
                         "generated_candidate_aggregate_min": float(generated.min()),
                         "generated_candidate_aggregate_max": float(generated.max()),
                         "generated_fraction_below_real_range": float((generated < low).mean()),
                         "generated_fraction_above_real_range": float((generated > high).mean()),
                         "meaning": "descriptive_class_range; no_population_support_certificate"})
    return pd.DataFrame(rows)


def working_k_table(canonical_profiles, original_profiles, after_profiles, objects, prediction):
    """仅展示统一人为单调映射下的K；不是已识别的原始0--6等级。"""
    return pd.DataFrame({"source_object": np.asarray(objects),
                         "canonical_source_working_K": prediction.working_grades(canonical_profiles)["Y38"].to_numpy(),
                         "original_D01_source_working_K": prediction.working_grades(original_profiles)["Y38"].to_numpy(),
                         "after_working_K": prediction.working_grades(after_profiles)["Y38"].to_numpy(),
                         "true_K": "unidentified",
                         "mapping_scope": "same_monotone_working_mapping; no_original_grade_or_grade2_safety_identification"})


def write_representatives(raw, basis, generated_basis, generated_native, generated_recorded,
                          identifiers, generated_groups, model, profiles, prediction, out, max_per_class=3):
    """只筛现有池：五个候选聚合均处于类内观察范围，再选邻近同类的代表。

    这是明确依赖观察数据的兼容性筛选，改变输出分布；不能继承未筛生成器
    的留出距离，也不把真实样本min/max冒充总体支持边界。
    """
    groups = np.asarray(generated_groups)
    real_groups = raw.regime.to_numpy()
    real_derived = candidate_derived_from_native(basis)
    candidate_derived = candidate_derived_from_native(generated_basis)
    zreal, zgenerated = model.transform(basis), model.transform(generated_basis)
    flags, summaries, chosen_positions = [], [], []
    for group in ("R20", "R12", "R13"):
        positions = np.flatnonzero(groups == group)
        real_positions = np.flatnonzero(real_groups == group)
        center = zreal[real_positions].mean(axis=0)
        distances = cdist(zgenerated[positions], zreal[real_positions])
        nearest = distances.min(axis=1)
        nearest_object = raw.object.to_numpy()[real_positions[distances.argmin(axis=1)]]
        center_distance = np.linalg.norm(zgenerated[positions]-center, axis=1)
        local_rows = []
        available = True
        for local, position in enumerate(positions):
            row = {"generated_id": identifiers[position], "regime": group,
                   "pool_position": int(position), "nearest_real_class_object": nearest_object[local],
                   "nearest_real_class_rank_distance": float(nearest[local]),
                   "class_center_rank_distance": float(center_distance[local])}
            passed = True
            for var in DERIVED:
                observed = real_derived.loc[real_groups == group, var].dropna()
                low, high = float(observed.min()), float(observed.max())
                value = float(candidate_derived.iloc[position][var])
                valid_range = bool(len(observed) and np.isfinite(low) and np.isfinite(high))
                available &= valid_range
                inside = bool(valid_range and np.isfinite(value) and low <= value <= high)
                row[f"{var}_candidate_native"] = value
                row[f"{var}_real_observed_min"] = low
                row[f"{var}_real_observed_max"] = high
                row[f"{var}_range_pass"] = inside
                passed &= inside
            row["all_five_ranges_pass"] = passed
            row["selected_rank_within_class"] = np.nan
            local_rows.append(row)
        eligible = [r for r in local_rows if r["all_five_ranges_pass"]]
        eligible.sort(key=lambda r: (r["nearest_real_class_rank_distance"], r["class_center_rank_distance"], r["generated_id"]))
        selected = eligible[:max_per_class]
        for rank, row in enumerate(selected, 1):
            row["selected_rank_within_class"] = rank
            chosen_positions.append(row["pool_position"])
        flags.extend(local_rows)
        summaries.append({"regime": group, "existing_pool_count": len(positions),
                          "all_five_ranges_pass_count": len(eligible), "selected_count": len(selected),
                          "selection_rule": "five_class_observed_candidate_aggregate_ranges; then_nearest_same_class_rank_distance_then_center_distance",
                          "empty_reason": "" if selected else ("no_pool_candidate_passed_all_five_ranges" if available else "missing_class_reference_range"),
                          "interpretation": "compatibility_screened_representatives; not_unbiased_generator_samples_or_population_support_certificate",
                          "heldout_metric_scope": "existing_heldout_metrics_apply_to_unscreened_generator_only"})
    pd.DataFrame(flags).to_csv(out/"question3_structure_representative_selection.csv", index=False)
    summary = pd.DataFrame(summaries)
    summary.to_csv(out/"question3_structure_representative_summary.csv", index=False)
    ids = np.asarray(identifiers)[chosen_positions]
    regimes = groups[chosen_positions]
    tagged(generated_recorded.iloc[chosen_positions], ids, regime=regimes).to_csv(
        out/"question3_structure_representatives_D01_scale.csv", index=False)
    tagged(generated_native.iloc[chosen_positions], ids, regime=regimes).to_csv(
        out/"question3_structure_representatives_native_mixed.csv", index=False)
    selected_profiles = profiles.iloc[chosen_positions].reset_index(drop=True)
    tagged(selected_profiles, ids, regime=regimes).to_csv(
        out/"question3_structure_representatives_profiles_D04_scale.csv", index=False)
    selected_working = prediction.working_grades(selected_profiles) if len(chosen_positions) else pd.DataFrame(columns=prediction.TARGETS)
    tagged(selected_working, ids, regime=regimes).to_csv(
        out/"question3_structure_representatives_WORKING_GRADES_NOT_IDENTIFIED.csv", index=False)
    return summary


def select_saved_representatives(project=None):
    """定向复用既有池，不重新采样、留出评估或迁移。"""
    project = Path(project) if project else ROOT.parent
    out = ROOT/"results"
    raw, basis = load_native_inputs(project)
    native = pd.read_csv(out/"question3_structure_generated_full231_native.csv")
    recorded = pd.read_csv(out/"question3_structure_generated_full231_D01_scale.csv")
    profiles = pd.read_csv(out/"question3_structure_generated_profiles_D04_scale.csv")
    from empirical_copula import ShrunkEmpiricalCopula
    import prediction
    model = ShrunkEmpiricalCopula().fit(basis, raw.regime.to_numpy())
    summary = write_representatives(raw, basis, native[BASE], native[FEATURES], recorded[FEATURES],
                                    native.generated_id.to_numpy(), native.regime.to_numpy(), model,
                                    profiles[prediction.TARGETS], prediction, out)
    note_path = out/"question3_structure_summary.json"
    if note_path.exists():
        note = json.loads(note_path.read_text(encoding="utf-8"))
        note["compatibility_screened_representative_counts"] = summary.set_index("regime").selected_count.to_dict()
        note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def transfer_structure(model, basis, groups, objects, floors, prediction, original_source_recorded=None,
                       observed_source_y38=None, numerical_margin=1e-6, record_unresolved=False):
    """原生基础量平移，再在同一空间约束C1--C4和重算后的Y38预测。

    优化器探索到派生量无效的点时只返回惩罚，不给这种点制造对数或评分。
    最后再检查实际输出；只有重表达源同时满足原始源评分上界时才可退源。
    若重表达源已不可行且未找到其他可行点，就明确报错，不把失败算合格迁移。
    """
    filled = pd.DataFrame(model.imputer.transform(np.asarray(basis)), columns=BASE, index=basis.index)
    source = filled.loc[groups == "R15"].reset_index(drop=True)
    source_objects = np.asarray(objects)[groups == "R15"]
    source_full = expand_native(source)
    if not valid_native(source).all():
        raise ValueError("R15源样本在候选公式下有非正派生量，不能构造已知可行源点")
    source_recorded = native_to_recorded(source_full, floors)
    source_scores = prediction.predict_continuous(source_recorded)["Y38"].to_numpy()
    original_scores = source_scores.copy() if original_source_recorded is None else prediction.predict_continuous(original_source_recorded)["Y38"].to_numpy()
    observed_scores = None
    if observed_source_y38 is not None:
        observed_scores = observed_source_y38.reindex(source_objects).to_numpy(dtype=float)
        if not np.isfinite(observed_scores).all():
            raise ValueError("观测源守卫缺少按object对齐的有限D04.Y38源观测")
    shift = filled.loc[groups == "R20"].mean()-filled.loc[groups == "R15"].mean()
    proposal = source.add(shift, axis=1)
    scales = np.nanquantile(filled, .9, axis=0)-np.nanquantile(filled, .1, axis=0)
    scales = np.where(scales > 1e-8, scales, 1.)
    lower, upper = filled.min().to_numpy(), filled.max().to_numpy()
    critical_indexes = [BASE.index(v) for v in CRITICAL]
    derived_scale = np.maximum(np.nanmedian(np.abs(candidate_derived_from_native(filled)), axis=0), 1e-6)
    positive_epsilon = 1e-10*derived_scale
    bundle=prediction.load_final_model()
    score_pre=bundle.estimator.regressor_.named_steps["preprocess"]
    derived_parents={v for coefficients in CANDIDATE_COEFFICIENTS.values() for v in coefficients}
    phase_free=[v for v in BASE if v not in CRITICAL and v not in derived_parents
                and v not in [f"V{k:03d}" for k in range(1,37)]]
    moved, diagnostics, comparisons, solver_points, initial_points = [], [], [], [], []
    proposal_recorded_parts = []

    for i, (src, candidate, obj) in enumerate(zip(source.to_numpy(), proposal.to_numpy(), source_objects)):
        src_score = float(source_scores[i])
        original_score = float(original_scores[i])
        observed_score = np.nan if observed_scores is None else float(observed_scores[i])
        score_cap = min(src_score, original_score) if observed_scores is None else min(src_score,original_score,observed_score)
        optimization_cap = score_cap if observed_scores is None else score_cap-numerical_margin
        score_tolerance=1e-8 if observed_scores is None else 0.
        lo, hi = np.minimum(lower, src), np.maximum(upper, src)
        hi[critical_indexes] = np.minimum(hi[critical_indexes], src[critical_indexes])
        initial = np.minimum(np.maximum(candidate, lo), hi)
        initial_frame = pd.DataFrame([initial], columns=BASE)
        if not valid_native(initial_frame)[0]:
            initial = src.copy()
        phase1_applied=False
        phase1_lambda=0.
        phase1_anchor_score=np.nan
        initial_score=float(prediction.predict_continuous(native_to_recorded(expand_native(pd.DataFrame([initial],columns=BASE)),floors))["Y38"].iloc[0])
        if observed_scores is not None and initial_score>optimization_cap:
            phase1_applied=True
            # 只动原观察尺度、非C、非任何派生父量的坐标，保持五派生和四C。
            # 朝线性评分系数下降方向到low/high，得到可行性锚点，绝不直接作为成品。
            anchor=src.copy()
            for feature in phase_free:
                j,k=BASE.index(feature),FEATURES.index(feature)
                chosen=score_pre.low_[k] if bundle.linear_coef_[37,k]>=0 else score_pre.high_[k]
                anchor[j]=np.clip(chosen,lo[j],hi[j])
            anchor_recorded=native_to_recorded(expand_native(pd.DataFrame([anchor],columns=BASE)),floors)
            phase1_anchor_score=float(prediction.predict_continuous(anchor_recorded)["Y38"].iloc[0])
            if phase1_anchor_score<=optimization_cap:
                left,right=0.,1.
                for _ in range(45):
                    middle=.5*(left+right)
                    point=src+middle*(anchor-src)
                    recorded=native_to_recorded(expand_native(pd.DataFrame([point],columns=BASE)),floors)
                    value=float(prediction.predict_continuous(recorded)["Y38"].iloc[0])
                    if value<=optimization_cap:
                        right=middle
                    else:
                        left=middle
                phase1_lambda=right
                initial=src+right*(anchor-src)
                initial_score=float(prediction.predict_continuous(native_to_recorded(expand_native(pd.DataFrame([initial],columns=BASE)),floors))["Y38"].iloc[0])
        origin = initial.copy()
        initial_points.append(initial.copy())

        def unpack(u):
            return origin+np.asarray(u)*scales

        def objective(u):
            d = (unpack(u)-candidate)/scales
            return .5*float(d@d)

        def objective_jac(u):
            return (unpack(u)-candidate)/scales

        def constraints_batch(points):
            frame = pd.DataFrame(np.atleast_2d(points), columns=BASE)
            derived = candidate_derived_from_native(frame).to_numpy()
            positive = (derived-positive_epsilon)/derived_scale
            good = np.isfinite(derived).all(axis=1) & (derived > 0).all(axis=1)
            # 无定义点的负惩罚不会进入输出，也不调用log(max(sum,epsilon))。
            score_margin = -1000.-np.maximum(-positive, 0).sum(axis=1)
            if good.any():
                rendered = native_to_recorded(expand_native(frame.loc[good]), floors)
                score_margin[good] = optimization_cap-prediction.predict_continuous(rendered)["Y38"].to_numpy()
            return np.column_stack([score_margin, positive])

        def constraint_fun(u):
            return constraints_batch(unpack(u))[0]

        def constraint_jac(u):
            # 227行一次送入现有评分器，避免逐列创建、加载、评分226次。
            h = 1e-6
            shifted = np.tile(np.asarray(u), (len(BASE)+1, 1))
            shifted[1:] += h*np.eye(len(BASE))
            values = constraints_batch(origin+shifted*scales)
            return ((values[1:]-values[0])/h).T

        attempt = minimize(objective, np.zeros(len(BASE)), jac=objective_jac,
                           method="SLSQP", bounds=list(zip((lo-origin)/scales, (hi-origin)/scales)),
                           constraints={"type": "ineq", "fun": constraint_fun, "jac": constraint_jac},
                           options={"maxiter": 120, "ftol": 1e-9})
        result = unpack(attempt.x)
        # 数值求解容差不能冒充精确上界：修正四个基础坐标后，重算所有派生量与评分。
        result[critical_indexes] = np.minimum(result[critical_indexes], src[critical_indexes])
        solver_points.append(result.copy())
        frame = pd.DataFrame([result], columns=BASE)
        positive_ok = bool(valid_native(frame)[0])
        critical_ok = bool(np.all(result[critical_indexes] <= src[critical_indexes]+1e-9))
        score = np.nan
        if positive_ok:
            score = float(prediction.predict_continuous(native_to_recorded(expand_native(frame), floors))["Y38"].iloc[0])
        fallback = not (positive_ok and critical_ok and np.isfinite(score) and score <= score_cap+score_tolerance)
        unresolved=False
        fallback_to_feasible_initial=False
        if fallback:
            if observed_scores is not None and initial_score<=score_cap:
                result,score=initial.copy(),initial_score
                fallback_to_feasible_initial=True
            else:
                if src_score>score_cap+score_tolerance:
                    if not record_unresolved:
                        raise RuntimeError(f"object {obj}: 候选未满足约束，重表达源也超过源预测/观测上界，无法作为可行回退")
                    unresolved=True
                result, score = src.copy(), src_score
        before_distance = np.linalg.norm(model.transform(pd.DataFrame([src], columns=BASE))[0]-model.mean("R20"))
        solver_distance = np.linalg.norm(model.transform(pd.DataFrame([result], columns=BASE))[0]-model.mean("R20"))
        path_applied, path_alpha = False, 1.
        final_candidate_origin="slsqp_candidate" if not fallback else ("verified_feasible_initial_fallback" if fallback_to_feasible_initial else "source_fallback")
        if solver_distance >= before_distance-1e-10 and not fallback:
            path_applied = True
            alphas = np.linspace(0., 1., 101)
            path = src+alphas[:, None]*(result-src)
            path[:, critical_indexes] = np.minimum(path[:, critical_indexes], src[critical_indexes])
            path_frame = pd.DataFrame(path, columns=BASE)
            valid = valid_native(path_frame)
            path_scores = np.full(len(path), np.inf)
            if valid.any():
                path_recorded = native_to_recorded(expand_native(path_frame.loc[valid]), floors)
                path_scores[valid] = prediction.predict_continuous(path_recorded)["Y38"].to_numpy()
            path_cap=score_cap+score_tolerance if observed_scores is None else optimization_cap+1e-10
            feasible = valid & (path_scores <= path_cap)
            distances = np.linalg.norm(model.transform(path_frame)-model.mean("R20"), axis=1)
            distances[~feasible] = np.inf
            selected = int(np.argmin(distances))
            if np.isfinite(distances[selected]):
                result, score = path[selected].copy(), float(path_scores[selected])
                path_alpha = float(alphas[selected])
                final_candidate_origin="source_to_slsqp_feasible_path"
        # 初值本身也是已实际验证的候选；局部目标变好不保证rank类别距离变好。
        # 观测守卫下只在初值确实满足三重cap时，才允许按相容性选回它。
        initial_distance=np.linalg.norm(model.transform(pd.DataFrame([initial],columns=BASE))[0]-model.mean("R20"))
        current_distance=np.linalg.norm(model.transform(pd.DataFrame([result],columns=BASE))[0]-model.mean("R20"))
        if observed_scores is not None and initial_score<=score_cap and initial_distance<current_distance:
            result,score=initial.copy(),initial_score
            final_candidate_origin="verified_near_phase1_initial"
            path_alpha=np.nan
            unresolved=False
        source_unchanged = bool(np.linalg.norm((result-src)/scales) <= 1e-12)
        completion_status=("unresolved_no_feasible_candidate_found" if unresolved else
                           ("source_retained_no_transfer" if source_unchanged else "feasible_moved_candidate"))
        moved.append(result)
        candidate_frame = pd.DataFrame([candidate], columns=BASE)
        candidate_valid = bool(valid_native(candidate_frame)[0])
        candidate_score = np.nan
        if candidate_valid:
            candidate_recorded = native_to_recorded(expand_native(candidate_frame), floors)
            proposal_recorded_parts.append(candidate_recorded)
            candidate_score = float(prediction.predict_continuous(candidate_recorded)["Y38"].iloc[0])
        else:
            proposal_recorded_parts.append(pd.DataFrame(np.nan, index=[0], columns=FEATURES))
        for var, threshold in CRITICAL.items():
            j = BASE.index(var)
            comparisons.append({"source_object": obj, "criterion": var, "threshold": threshold,
                                "source_native": src[j], "proposal_native": candidate[j], "after_native": result[j],
                                "source_ratio": src[j]/threshold, "after_ratio": result[j]/threshold,
                                "nonworsening": bool(result[j] <= src[j]+1e-9),
                                "completion_status":completion_status,
                                "scope": "native_candidate_coordinate; candidate_derived_relations"})
        comparisons.append({"source_object": obj, "criterion": "Y38_model_continuous", "threshold": np.nan,
                            "source_native": src_score, "proposal_native": candidate_score, "after_native": score,
                            "source_ratio": np.nan, "after_ratio": np.nan,
                            "nonworsening": bool(score <= src_score+score_tolerance),
                            "original_source_prediction": original_score, "constraint_score_cap": score_cap,
                            "original_source_nonworsening": bool(score <= original_score+score_tolerance),
                            "observed_source_y38":observed_score,"optimization_cap":optimization_cap,
                            "numerical_margin":0. if observed_scores is None else numerical_margin,
                            "observed_source_nonworsening":np.nan if observed_scores is None else bool(score<=observed_score),
                            "all_score_caps_pass":bool(score<=score_cap+score_tolerance),
                            "completion_status":completion_status,
                            "scope": "fitted_D04_scale_prediction_only; min_original_reexpressed_and_observed_source_cap; true_K_grade_unidentified" if observed_scores is not None else "fitted_D04_scale_prediction_only; min_original_and_reexpressed_source_cap; true_K_grade_unidentified"})
        after_distance = np.linalg.norm(model.transform(pd.DataFrame([result], columns=BASE))[0]-model.mean("R20"))
        diagnostics.append({"source_object": obj, "optimizer_success": bool(attempt.success),
                            "optimizer_message": str(attempt.message), "iterations": int(attempt.nit),
                            "fallback_to_source": bool((fallback and not fallback_to_feasible_initial) or source_unchanged),
                            "fallback_to_feasible_initial":fallback_to_feasible_initial,
                            "constraint_failure_fallback": fallback, "source_unchanged": source_unchanged,
                            "completion_status":completion_status,"unresolved":unresolved,
                            "observed_source_y38":observed_score,"mathematical_score_cap":score_cap,
                            "optimization_cap":optimization_cap,
                            "numerical_margin":0. if observed_scores is None else numerical_margin,
                            "all_score_caps_pass":bool(score<=score_cap+score_tolerance),
                            "phase1_applied":phase1_applied,"phase1_anchor_prediction":phase1_anchor_score,
                            "phase1_selected_lambda":phase1_lambda,"phase1_initial_prediction":initial_score,
                            "phase1_initial_distance_to_R20_mean":float(initial_distance),
                            "final_candidate_origin":final_candidate_origin,
                            "proposal_positive_derived": candidate_valid,
                            "slsqp_distance_to_R20_mean": float(solver_distance),
                            "path_search_applied": path_applied, "selected_path_alpha": path_alpha,
                            "optimization_scope": "local_SLSQP_plus_finite_path_search; not_global_projection_optimum",
                            "after_min_derived_value": float(candidate_derived_from_native(pd.DataFrame([result], columns=BASE)).min(axis=1).iloc[0]),
                            "distance_to_R20_mean_before": float(before_distance),
                            "distance_to_R20_mean_after": float(after_distance),
                            "standardized_displacement": float(np.linalg.norm((result-src)/scales))})
    return {"source": source, "proposal": proposal,
            "after": pd.DataFrame(moved, columns=BASE), "source_objects": source_objects,
            "slsqp_base": pd.DataFrame(solver_points, columns=BASE),
            "feasible_initial_base":pd.DataFrame(initial_points,columns=BASE),
            "proposal_recorded": pd.concat(proposal_recorded_parts, ignore_index=True),
            "comparison": pd.DataFrame(comparisons), "optimization": pd.DataFrame(diagnostics)}


def refine_guard_with_exact_subspace(guard,model,basis,floors,prediction):
    """固定44列，精确求182维box+半空间投影，再比较真实可行候选的类相容性。

    精确性仅针对该仿射子问题；全226维的类相容性选择没有全局最优保证。
    """
    bundle=prediction.load_final_model()
    pre=bundle.estimator.regressor_.named_steps["preprocess"]
    parents={v for coefficients in CANDIDATE_COEFFICIENTS.values() for v in coefficients}
    free=[v for v in BASE if v not in CRITICAL and v not in parents
          and v not in [f"V{k:03d}" for k in range(1,37)]]
    indexes=np.array([BASE.index(v) for v in free])
    recorded_indexes=np.array([FEATURES.index(v) for v in free])
    beta=bundle.linear_coef_[37,recorded_indexes]/pre.scale_[recorded_indexes]
    filled=model.imputer.transform(np.asarray(basis))
    scales=np.nanquantile(filled,.9,axis=0)-np.nanquantile(filled,.1,axis=0)
    scales=np.where(scales>1e-8,scales,1.)
    global_low,global_high=np.min(filled,axis=0),np.max(filled,axis=0)
    critical_indexes=[BASE.index(v) for v in CRITICAL]
    selected_points,qp_points,polished_qp_points,certificates,selections,curves=[],[],[],[],[],[]
    comparison=guard["comparison"].copy()
    optimization=guard["optimization"].copy()

    for i,obj in enumerate(guard["source_objects"]):
        source=guard["source"].iloc[i].to_numpy().copy()
        proposal=guard["proposal"].iloc[i].to_numpy()
        score_row=comparison.loc[(comparison.source_object==obj)&(comparison.criterion=="Y38_model_continuous")].iloc[0]
        cap=float(score_row.constraint_score_cap)
        target=float(score_row.optimization_cap)
        box_low,box_high=np.minimum(global_low,source),np.maximum(global_high,source)
        low=np.maximum(box_low[indexes],pre.low_[recorded_indexes])
        high=np.minimum(box_high[indexes],pre.high_[recorded_indexes])
        p=proposal[indexes]
        variance=scales[indexes]**2
        initial_free=np.clip(p,low,high)
        reference=source.copy();reference[indexes]=initial_free
        reference_score=float(prediction.predict_continuous(native_to_recorded(expand_native(pd.DataFrame([reference],columns=BASE)),floors))["Y38"].iloc[0])
        affine_constant=reference_score-float(beta@initial_free)
        rhs=target-affine_constant

        def free_point(multiplier):
            return np.clip(p-multiplier*variance*beta,low,high)

        multiplier=0.;bracket_found=True
        if float(beta@initial_free)>rhs:
            left,right=0.,1.
            for _ in range(80):
                if float(beta@free_point(right))<=rhs:
                    break
                right*=2.
            else:
                bracket_found=False
            if bracket_found:
                for _ in range(75):
                    middle=.5*(left+right)
                    if float(beta@free_point(middle))<=rhs:
                        right=middle
                    else:
                        left=middle
                multiplier=right
        qp=source.copy()
        qp[indexes]=free_point(multiplier)
        if int(obj)==124:
            grid=np.unique(np.r_[np.linspace(0.,max(1.,1.5*multiplier),61),multiplier])
            free_values=np.stack([free_point(value) for value in grid])
            curve_points=np.tile(source,(len(grid),1));curve_points[:,indexes]=free_values
            curve_scores=prediction.predict_continuous(native_to_recorded(expand_native(pd.DataFrame(curve_points,columns=BASE)),floors))["Y38"].to_numpy()
            for value,point,score in zip(grid,free_values,curve_scores):
                objective=.5*float(np.sum(((point-p)/scales[indexes])**2))
                curves.append({"source_object":obj,"multiplier":value,
                               "actual_prediction":score,"affine_prediction":affine_constant+float(beta@point),
                               "free_weighted_objective":objective,"free_weighted_distance":np.sqrt(2*objective),
                               "touching_bound_count":int(((point==low)|(point==high)).sum()),
                               "mathematical_cap":cap,"optimization_cap":target,
                               "selected_qp_multiplier":multiplier,"is_selected_multiplier":bool(value==multiplier)})

        def plateau_polish(point):
            polished=point.copy()
            for j,k in zip(indexes,recorded_indexes):
                if pre.low_[k]==pre.high_[k]:
                    polished[j]=np.clip(proposal[j],box_low[j],box_high[j])
                elif point[j]>=pre.high_[k]:
                    polished[j]=np.clip(proposal[j],max(box_low[j],pre.high_[k]),box_high[j])
                elif point[j]<=pre.low_[k]:
                    polished[j]=np.clip(proposal[j],box_low[j],min(box_high[j],pre.low_[k]))
            return polished

        old_origin=str(optimization.iloc[i].get("final_candidate_origin","previous_verified_selection"))
        candidates=[(old_origin,guard["after"].iloc[i].to_numpy()),
                    ("verified_near_phase1_initial",guard["feasible_initial_base"].iloc[i].to_numpy()),
                    ("exact_182d_box_halfspace_projection",qp)]
        candidates+=[(name+"_plateau_polish",plateau_polish(point)) for name,point in candidates.copy()]
        candidate_frame=pd.DataFrame([point for _,point in candidates],columns=BASE)
        native_valid=valid_native(candidate_frame)
        scores=np.full(len(candidates),np.inf)
        if native_valid.any():
            scores[native_valid]=prediction.predict_continuous(native_to_recorded(expand_native(candidate_frame.loc[native_valid]),floors))["Y38"].to_numpy()
        c_pass=np.all(candidate_frame.to_numpy()[:,critical_indexes]<=source[critical_indexes],axis=1)
        feasible=native_valid&c_pass&(scores<=cap)
        distances=np.linalg.norm(model.transform(candidate_frame)-model.mean("R20"),axis=1)
        distances[~feasible]=np.inf
        chosen=int(np.argmin(distances))
        if not np.isfinite(distances[chosen]):
            selected=guard["after"].iloc[i].to_numpy().copy()
            origin=old_origin
        else:
            selected=candidates[chosen][1].copy()
            origin=candidates[chosen][0]
        selected_points.append(selected)
        qp_points.append(qp)
        polished_qp_points.append(plateau_polish(qp))
        qp_score=float(scores[2])
        affine_prediction=affine_constant+float(beta@qp[indexes])
        endpoint=source.copy()
        endpoint[indexes]=np.where(beta>=0,low,high)
        endpoint_score=float(prediction.predict_continuous(native_to_recorded(expand_native(pd.DataFrame([endpoint],columns=BASE)),floors))["Y38"].iloc[0])
        certificates.append({"source_object":obj,"free_coordinate_count":len(indexes),
                             "fixed_coordinate_count":len(BASE)-len(indexes),"qp_bracket_found":bracket_found,
                             "qp_multiplier":multiplier,"mathematical_cap":cap,"optimization_cap":target,
                             "qp_actual_prediction":qp_score,"qp_affine_prediction":affine_prediction,
                             "actual_minus_affine_prediction":qp_score-affine_prediction,
                             "qp_linear_halfspace_margin":rhs-float(beta@qp[indexes]),
                             "qp_free_objective":.5*float(np.sum(((qp[indexes]-p)/scales[indexes])**2)),
                             "qp_full_target_objective":.5*float(np.sum(((qp-proposal)/scales)**2)),
                             "endpoint_actual_prediction":endpoint_score,"endpoint_cap_margin":cap-endpoint_score,
                             "endpoint_C_max_absolute_change":float(np.max(np.abs(endpoint[critical_indexes]-source[critical_indexes]))),
                             "endpoint_derived_max_absolute_change":float(np.max(np.abs(candidate_derived_from_native(pd.DataFrame([endpoint],columns=BASE)).to_numpy()-candidate_derived_from_native(pd.DataFrame([source],columns=BASE)).to_numpy()))),
                             "proof_scope":"exact_box_halfspace_projection_only_in_fixed_182d_affine_subspace"})
        for j,(name,point) in enumerate(candidates):
            selections.append({"source_object":obj,"candidate_origin":name,"selected":j==chosen,
                               "prediction_Y38":scores[j],"strict_cap_pass":bool(scores[j]<=cap),
                               "C_pass":bool(c_pass[j]),"derived_valid":bool(native_valid[j]),
                               "rank_distance_to_R20_center":float(distances[j]),
                               "weighted_target_objective":.5*float(np.sum(((point-proposal)/scales)**2)),
                               "standardized_displacement_from_source":float(np.linalg.norm((point-source)/scales)),
                               "score_difference_from_unpolished":0. if j<3 else float(scores[j]-scores[j-3])})
        optimization.loc[i,"final_candidate_origin"]=origin
        optimization.loc[i,"optimization_scope"]="selection_over_local_SLSQP_verified_initial_exact_182d_QP_and_same_input_fibres; not_global_226d_optimum"
        optimization.loc[i,"exact_qp_rank_distance"]=float(distances[2])
        optimization.loc[i,"distance_to_R20_mean_after"]=float(np.linalg.norm(model.transform(pd.DataFrame([selected],columns=BASE))[0]-model.mean("R20")))
        optimization.loc[i,"standardized_displacement"]=float(np.linalg.norm((selected-source)/scales))
        optimization.loc[i,"source_unchanged"]=bool(np.linalg.norm((selected-source)/scales)<=1e-12)
        optimization.loc[i,"completion_status"]="feasible_moved_candidate" if np.isfinite(distances[chosen]) else "unresolved_no_feasible_candidate_found"
        optimization.loc[i,"unresolved"]=not np.isfinite(distances[chosen])
        if origin!=old_origin:
            optimization.loc[i,"selected_path_alpha"]=np.nan
        after_score=float(scores[chosen])
        comparison.loc[(comparison.source_object==obj)&(comparison.criterion=="Y38_model_continuous"),"after_native"]=after_score
    guard["after"]=pd.DataFrame(selected_points,columns=BASE)
    guard["exact_qp_base"]=pd.DataFrame(qp_points,columns=BASE)
    guard["plateau_polished_qp_base"]=pd.DataFrame(polished_qp_points,columns=BASE)
    guard["qp_certificate"]=pd.DataFrame(certificates)
    guard["candidate_selection"]=pd.DataFrame(selections)
    guard["qp_curves"]=pd.DataFrame(curves)
    guard["optimization"],guard["comparison"]=optimization,comparison
    return guard


def write_qp_platform_profiles(guard,prediction,floors,out,prefix):
    """平台等输入修复另存，不把clip箱外点冒充原182维凸问题的最优解。"""
    profiles=[]
    for name in ("exact_qp_base","plateau_polished_qp_base"):
        recorded=native_to_recorded(expand_native(guard[name]),floors)
        profile=prediction.predict_continuous(recorded)
        profiles.append(profile)
        tagged(profile,guard["source_objects"],"source_object").to_csv(out/f"{prefix}{name}_profiles_D04_scale.csv",index=False)
    bundle=prediction.load_final_model()
    pre=bundle.estimator.regressor_.named_steps["preprocess"]
    parents={v for coefficients in CANDIDATE_COEFFICIENTS.values() for v in coefficients}
    free=[v for v in BASE if v not in CRITICAL and v not in parents
          and v not in [f"V{k:03d}" for k in range(1,37)]]
    rows=[]
    selection=guard["candidate_selection"]
    for i,obj in enumerate(guard["source_objects"]):
        before=selection.loc[(selection.source_object==obj)&(selection.candidate_origin=="exact_182d_box_halfspace_projection")].iloc[0]
        after=selection.loc[(selection.source_object==obj)&(selection.candidate_origin=="exact_182d_box_halfspace_projection_plateau_polish")].iloc[0]
        outside=[]
        excess=[]
        for name in ("exact_qp_base","plateau_polished_qp_base"):
            point=guard[name].iloc[i]
            outside.append(sum(bool(point[v]<pre.low_[FEATURES.index(v)] or point[v]>pre.high_[FEATURES.index(v)]) for v in free))
            excess.append(max(max(float(pre.low_[FEATURES.index(v)]-point[v]),float(point[v]-pre.high_[FEATURES.index(v)]),0.) for v in free))
        rows.append({"source_object":obj,"max50_absolute_prediction_difference":float(np.max(np.abs(profiles[0].iloc[i].to_numpy()-profiles[1].iloc[i].to_numpy()))),
                     "Y38_before":profiles[0].Y38.iloc[i],"Y38_after":profiles[1].Y38.iloc[i],
                     "weighted_target_objective_before":before.weighted_target_objective,
                     "weighted_target_objective_after":after.weighted_target_objective,
                     "rank_distance_before":before.rank_distance_to_R20_center,
                     "rank_distance_after":after.rank_distance_to_R20_center,
                     "outside_score_clip_box_before":outside[0],"outside_score_clip_box_after":outside[1],
                     "max_clip_box_excess_before":excess[0],"max_clip_box_excess_after":excess[1],
                     "scope":"same_clipped_input; score_equivalence_only; polished_point_not_original_clip_box_QP_solution"})
    result=pd.DataFrame(rows)
    result.to_csv(out/f"{prefix}QP_platform_profile_comparison.csv",index=False)
    return result


def run_observed_source_guard(project=None,model=None,raw=None,basis=None,floors=None,numerical_margin=1e-6,reuse_solver=False):
    """单独增加观测源守卫，复用现有模型结构，不重做生成池或留出比较。

    约束的是迁移后的模型预测，不是未知的真实迁移评分，更不是K原始等级。
    """
    project=Path(project) if project else ROOT.parent
    out=ROOT/"results"
    out.mkdir(exist_ok=True)
    if raw is None or basis is None:
        raw,basis=load_native_inputs(project)
    groups,objects=raw.regime.to_numpy(),raw.object.to_numpy()
    if model is None:
        from empirical_copula import ShrunkEmpiricalCopula
        model=ShrunkEmpiricalCopula().fit(basis,groups)
    if floors is None:
        reference=pd.read_excel(project/"data"/"D08.xlsx",sheet_name="ref_scale").set_index("object").reindex(raw.object)
        floors=fit_positive_floors(reference[[f"V{i:03d}" for i in range(1,38)]])
    observed=pd.read_csv(project/"data"/"D04.csv").set_index("object")
    import prediction
    original_source=raw.loc[groups=="R15",FEATURES].reset_index(drop=True)
    prefix="question3_observed_source_guard_"
    if reuse_solver:
        # 明确复用同一输入下已保存的局部求解点；不适用于原始输入或cap变化。
        guard={"source_objects":raw.loc[groups=="R15","object"].to_numpy()}
        for stage in ("source","proposal","after"):
            guard[stage]=pd.read_csv(out/f"{prefix}{stage}_native_mixed.csv")[BASE]
        for stage in ("feasible_initial_base","slsqp_base"):
            guard[stage]=pd.read_csv(out/f"{prefix}{stage}226_native_mixed.csv")[BASE]
        guard["proposal_recorded"]=pd.read_csv(out/f"{prefix}proposal_D01_scale.csv")[FEATURES]
        guard["comparison"]=pd.read_csv(out/f"{prefix}critical_comparison.csv")
        guard["optimization"]=pd.read_csv(out/f"{prefix}optimization.csv")
    else:
        guard=transfer_structure(model,basis,groups,objects,floors,prediction,original_source,
                                 observed_source_y38=observed.Y38,numerical_margin=numerical_margin,
                                 record_unresolved=True)
    guard=refine_guard_with_exact_subspace(guard,model,basis,floors,prediction)
    source_objects=guard["source_objects"]
    for name in ("feasible_initial_base","slsqp_base","exact_qp_base","plateau_polished_qp_base"):
        tagged(guard[name],source_objects,"source_object").to_csv(out/f"{prefix}{name}226_native_mixed.csv",index=False)
    guard["qp_certificate"].to_csv(out/f"{prefix}exact_qp_certificate.csv",index=False)
    guard["candidate_selection"].to_csv(out/f"{prefix}feasible_candidate_selection.csv",index=False)
    guard["qp_curves"].to_csv(out/f"{prefix}exact_qp_curve_object124.csv",index=False)
    make_exact_qp_curve_figure(guard["qp_curves"],ROOT/"figures"/f"{prefix}exact_qp_curve_object124.png")
    write_qp_platform_profiles(guard,prediction,floors,out,prefix)
    for stage in ("source","proposal","after"):
        native=expand_native(guard[stage])
        recorded=guard["proposal_recorded"] if stage=="proposal" else native_to_recorded(native,floors)
        tagged(native,source_objects,"source_object").to_csv(out/f"{prefix}{stage}_native_mixed.csv",index=False)
        tagged(recorded,source_objects,"source_object").to_csv(out/f"{prefix}{stage}_D01_scale.csv",index=False)
    # 用实际交付CSV重新评分；数值余量只处理舍入，不作为统计置信边界。
    saved_source=pd.read_csv(out/f"{prefix}source_native_mixed.csv").set_index("source_object")
    saved_after=pd.read_csv(out/f"{prefix}after_native_mixed.csv").set_index("source_object")
    saved_recorded=pd.read_csv(out/f"{prefix}after_D01_scale.csv")
    actual_profiles=prediction.predict_continuous(saved_recorded[FEATURES])
    tagged(actual_profiles,source_objects,"source_object").to_csv(out/f"{prefix}after_profiles_D04_scale.csv",index=False)
    actual_y38=pd.Series(actual_profiles.Y38.to_numpy(),index=source_objects)
    comparison=guard["comparison"].copy()
    for row in comparison.index:
        obj,criterion=comparison.at[row,"source_object"],comparison.at[row,"criterion"]
        comparison.at[row,"csv_reread_verified"]=True
        if criterion in CRITICAL:
            before,after=saved_source.at[obj,criterion],saved_after.at[obj,criterion]
            comparison.at[row,"source_native"],comparison.at[row,"after_native"]=before,after
            comparison.at[row,"source_ratio"]=before/CRITICAL[criterion]
            comparison.at[row,"after_ratio"]=after/CRITICAL[criterion]
            comparison.at[row,"nonworsening"]=bool(after<=before)
        else:
            value=float(actual_y38.at[obj])
            comparison.at[row,"after_native"]=value
            comparison.at[row,"nonworsening"]=bool(value<=comparison.at[row,"source_native"])
            comparison.at[row,"original_source_nonworsening"]=bool(value<=comparison.at[row,"original_source_prediction"])
            comparison.at[row,"observed_source_nonworsening"]=bool(value<=comparison.at[row,"observed_source_y38"])
            comparison.at[row,"all_score_caps_pass"]=bool(value<=comparison.at[row,"constraint_score_cap"])
            comparison.at[row,"strict_saved_score_margin"]=comparison.at[row,"constraint_score_cap"]-value
    comparison.to_csv(out/f"{prefix}critical_comparison.csv",index=False)
    optimization=guard["optimization"].copy()
    failed=set(comparison.loc[comparison.nonworsening==False,"source_object"])
    score_rows=comparison.loc[comparison.criterion=="Y38_model_continuous"].copy()
    failed|=set(score_rows.loc[score_rows.all_score_caps_pass==False,"source_object"])
    optimization.loc[optimization.source_object.isin(failed),"unresolved"]=True
    optimization.loc[optimization.source_object.isin(failed),"completion_status"]="unresolved_saved_csv_constraint"
    optimization.to_csv(out/f"{prefix}optimization.csv",index=False)
    residual=relation_diagnostics(saved_after,pd.read_csv(out/f"{prefix}after_D01_scale.csv").set_index("source_object"),"observed_guard_after")
    residual["evaluation_point"]="read_saved_csv"
    residual.to_csv(out/f"{prefix}candidate_relation_residuals.csv",index=False)
    original_profiles=prediction.predict_continuous(original_source)
    source_profiles=prediction.predict_continuous(native_to_recorded(expand_native(guard["source"]),floors))
    for name,profiles in (("original_source",original_profiles),("reexpressed_source",source_profiles)):
        tagged(profiles,source_objects,"source_object").to_csv(out/f"{prefix}{name}_profiles_D04_scale.csv",index=False)
    k=working_k_table(source_profiles,original_profiles,actual_profiles,source_objects,prediction)
    observed_profiles=observed.reindex(source_objects)[prediction.TARGETS].reset_index(drop=True)
    k["observed_source_WORKING_K"]=prediction.working_grades(observed_profiles).Y38.to_numpy()
    k["observed_working_nonworsening"]=k.after_working_K<=k.observed_source_WORKING_K
    k.to_csv(out/f"{prefix}K_WORKING_ONLY.csv",index=False)
    baseline_path=out/"question3_structure_transfer_after_profiles_D04_scale.csv"
    baseline=pd.read_csv(baseline_path).set_index("source_object").Y38 if baseline_path.exists() else pd.Series(dtype=float)
    branch_comparison=pd.DataFrame({"source_object":source_objects,
                                    "observed_source_Y38":observed.reindex(source_objects).Y38.to_numpy(),
                                    "model_only_branch_after_prediction":baseline.reindex(source_objects).to_numpy(),
                                    "observed_guard_after_prediction":actual_y38.reindex(source_objects).to_numpy(),
                                    "mathematical_cap":score_rows.constraint_score_cap.to_numpy()})
    branch_comparison["model_only_minus_observed"]=branch_comparison.model_only_branch_after_prediction-branch_comparison.observed_source_Y38
    branch_comparison["guard_minus_observed"]=branch_comparison.observed_guard_after_prediction-branch_comparison.observed_source_Y38
    branch_comparison["strict_observed_order_pass"]=branch_comparison.observed_guard_after_prediction<=branch_comparison.observed_source_Y38
    branch_comparison.to_csv(out/f"{prefix}versus_model_only_branch.csv",index=False)
    note={"cap_definition":"min(original_D01_source_prediction,reexpressed_source_prediction,observed_D04_source_Y38)",
          "numerical_inner_margin":numerical_margin,"margin_meaning":"floating_point_only; not_statistical_safety_bound",
          "final_order_rule":"saved_CSV_reprediction<=mathematical_cap; no_positive_tolerance",
          "source_count":len(source_objects),"critical_coordinate_pass_count":int(comparison.loc[comparison.criterion.isin(CRITICAL),"nonworsening"].sum()),
          "strict_all_score_caps_pass_count":int(score_rows.all_score_caps_pass.sum()),
          "strict_observed_source_pass_count":int(branch_comparison.strict_observed_order_pass.sum()),
          "unresolved_count":int(optimization.unresolved.sum()),
          "source_unchanged_count":int(optimization.source_unchanged.sum()),
          "optimizer_success_count":int(optimization.optimizer_success.sum()),
          "verified_initial_selected_count":int((optimization.final_candidate_origin=="verified_near_phase1_initial").sum()),
          "exact_qp_selected_count":int(optimization.final_candidate_origin.str.startswith("exact_182d_box_halfspace_projection").sum()),
          "plateau_polished_selected_count":int(optimization.final_candidate_origin.str.endswith("_plateau_polish").sum()),
          "max_exact_qp_prediction_affine_error":float(guard["qp_certificate"].actual_minus_affine_prediction.abs().max()),
          "exact_qp_scope":"182_free_coordinate_box_and_affine_halfspace; not_global_226d_optimum",
          "feasible_initial_fallback_count":int(optimization.fallback_to_feasible_initial.sum()),
          "distance_to_R20_center_improved_count":int((optimization.distance_to_R20_mean_after<optimization.distance_to_R20_mean_before).sum()),
          "old_branch_exceeding_observed_source_count":int((branch_comparison.model_only_minus_observed>0).sum()),
          "max_guard_minus_observed":float(branch_comparison.guard_minus_observed.max()),
          "min_strict_saved_cap_margin":float(score_rows.strict_saved_score_margin.min()),
          "true_migrated_score_and_original_K":"unobserved_or_unidentified; no_real_safety_certificate"}
    (out/f"{prefix}summary.json").write_text(json.dumps(note,ensure_ascii=False,indent=2),encoding="utf-8")
    structure_note_path=out/"question3_structure_summary.json"
    if structure_note_path.exists():
        structure_note=json.loads(structure_note_path.read_text(encoding="utf-8"))
        structure_note["observed_source_guard"]=note
        structure_note_path.write_text(json.dumps(structure_note,ensure_ascii=False,indent=2),encoding="utf-8")
    make_observed_guard_figure(branch_comparison,optimization,ROOT/"figures"/f"{prefix}comparison.png")
    print(json.dumps(note,ensure_ascii=False,indent=2))
    return note


def make_exact_qp_curve_figure(curve,path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if curve.empty:
        return
    curve=curve.sort_values("multiplier")
    multiplier=float(curve.selected_qp_multiplier.iloc[0])
    fig,axes=plt.subplots(1,2,figsize=(12,4.6))
    axes[0].plot(curve.multiplier,curve.actual_prediction,label="Actual model prediction")
    axes[0].axhline(curve.optimization_cap.iloc[0],color="tab:orange",linestyle="--",label="mathematical cap - 1e-6")
    axes[0].axvline(multiplier,color="tab:red",linestyle=":",label=f"selected multiplier {multiplier:.4f}")
    axes[0].set(xlabel="Lagrange multiplier",ylabel="Y38 prediction",title="Object 124: monotone score along the exact-QP family")
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    axes[1].plot(curve.multiplier,curve.free_weighted_distance,color="tab:green")
    axes[1].axvline(multiplier,color="tab:red",linestyle=":")
    axes[1].set(xlabel="Lagrange multiplier",ylabel="Weighted distance to proposal (182 free coordinates)",title="The score constraint requires a larger adjustment")
    axes[1].grid(alpha=.2)
    fig.tight_layout();fig.savefig(path,dpi=160);plt.close(fig)


def make_observed_guard_figure(comparison,optimization,path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True)
    x=np.arange(len(comparison))
    axes[0].plot(x,comparison.observed_source_Y38,"o-",label="Observed source Y38")
    axes[0].plot(x,comparison.model_only_branch_after_prediction,"o--",label="Previous model-only branch")
    axes[0].plot(x,comparison.observed_guard_after_prediction,"o-",label="Observed-source guard prediction")
    axes[0].set(ylabel="Y38 (D04 continuous scale)",title="New guard compares AFTER predictions with OBSERVED source scores")
    axes[0].legend();axes[0].grid(alpha=.2)
    axes[1].plot(x,optimization.distance_to_R20_mean_before,"o-",label="Source R15")
    axes[1].plot(x,optimization.distance_to_R20_mean_after,"o-",label="Guarded candidate")
    axes[1].set(xlabel="source object",ylabel="Rank-space distance to R20 center")
    axes[1].set_xticks(x,comparison.source_object.astype(str));axes[1].legend();axes[1].grid(alpha=.2)
    fig.text(.5,.005,"Prediction guard only; migrated true scores and original 0-6 K grades are not observed",ha="center",fontsize=10)
    fig.tight_layout(rect=(0,.025,1,1));fig.savefig(path,dpi=160);plt.close(fig)


def make_figures(evaluation, profiles, profile_groups, optimization, folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    folder.mkdir(exist_ok=True)
    methods = [m for m in ("global_lw", "conditional_lw", "conditional_posterior_predictive", "empirical_marginal_copula")
               if m in evaluation.method.unique()]
    short = {"global_lw": "global LW", "conditional_lw": "conditional LW",
             "conditional_posterior_predictive": "conditional + predictive spread",
             "empirical_marginal_copula": "shrunk empirical margins"}
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, metric, title in zip(axes, ("energy_v", "gaussian_rank_space_nll"),
                                 ("Held-out energy distance (V)", "Held-out Gaussian rank-space NLL")):
        metric_methods = [m for m in methods if evaluation.loc[evaluation.method == m, metric].notna().any()]
        values = [evaluation.loc[evaluation.method == m].groupby("split")[metric].mean().to_numpy()
                  for m in metric_methods]
        ax.boxplot(values, tick_labels=[short[m] for m in metric_methods], showmeans=True)
        ax.tick_params(axis="x", rotation=15)
        ax.set_title(title if metric != "gaussian_rank_space_nll" else
                     title+"\nEmpirical margins: NLL not applicable (discrete atoms)", fontsize=11)
        ax.grid(axis="y", alpha=.2)
    fig.suptitle("226 base coordinates: native mixed representation; repeated splits are dependent")
    fig.tight_layout()
    fig.savefig(folder/"question3_structure_heldout_models.png", dpi=170)
    plt.close(fig)
    frame = profiles.copy()
    frame.insert(0, "regime", np.asarray(profile_groups))
    means = frame.groupby("regime").mean().reindex(["R20", "R12", "R13"])
    vmax = max(float(np.max(np.abs(means))), 1e-8)
    fig, axes = plt.subplots(2, 1, figsize=(15, 5.6))
    for i, ax in enumerate(axes):
        part = means.iloc[:, 25*i:25*(i+1)]
        im = ax.imshow(part, aspect="auto", cmap="coolwarm", vmin=-vmax, vmax=vmax)
        ax.set_xticks(np.arange(25), part.columns, rotation=45, ha="right")
        ax.set_yticks(np.arange(3), part.index)
        ax.set_title(f"Y{25*i+1:02d}--Y{25*(i+1):02d}: generated class mean predicted profile")
    fig.suptitle("Model predictions on D04 continuous scale; original 0--6 grades are unidentified")
    fig.subplots_adjust(left=.06, right=.88, bottom=.13, top=.86, hspace=.8)
    color_axis = fig.add_axes([.91, .20, .015, .57])
    fig.colorbar(im, cax=color_axis, label="predicted continuous score")
    fig.savefig(folder/"question3_structure_generated_profiles.png", dpi=170)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    positions = np.arange(len(optimization))
    ax.plot(positions, optimization.distance_to_R20_mean_before, "o-", label="source R15")
    ax.plot(positions, optimization.distance_to_R20_mean_after, "o-", label="constrained structural candidate")
    ax.set_xticks(positions, optimization.source_object.astype(str))
    ax.set(xlabel="source object", ylabel="rank-space distance to R20 mean",
           title="Structural transfer: native-coordinate proposal and exact output checks")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(folder/"question3_structure_transfer_distances.png", dpi=170)
    plt.close(fig)


def run_structure(project=None, repeats=5, reuse_heldout=False):
    project = Path(project) if project else ROOT.parent
    out = ROOT/"results"
    out.mkdir(exist_ok=True)
    raw, basis = load_native_inputs(project)
    groups, objects = raw.regime.to_numpy(), raw.object.to_numpy()
    heldout_path = out/"question3_structure_heldout_metrics.csv"
    if reuse_heldout and heldout_path.exists():
        evaluation = pd.read_csv(heldout_path)
        if evaluation.split.nunique() != repeats:
            evaluation = evaluate_structure_generators(basis, groups, repeats)
        else:
            expected = {"global_lw", "conditional_lw", "conditional_posterior_predictive", "empirical_marginal_copula"}
            missing = expected-set(evaluation.method)
            if missing:
                added = evaluate_structure_generators(basis, groups, repeats, method_names=missing)
                evaluation = pd.concat([evaluation, added], ignore_index=True)
    else:
        evaluation = evaluate_structure_generators(basis, groups, repeats)
    evaluation.to_csv(out/"question3_structure_heldout_metrics.csv", index=False)
    summary = evaluation.groupby("method")[["energy_v", "mmd2_v", "gaussian_rank_space_nll"]].mean()
    summary.to_csv(out/"question3_structure_heldout_summary.csv")
    from empirical_copula import ShrunkEmpiricalCopula
    model = ShrunkEmpiricalCopula().fit(basis, groups)
    marginal_counts=[]
    for group in model.classes:
        for j,feature in enumerate(BASE):
            observed=model.marginal_counts[group][j]
            weight=observed/(observed+model.tau) if observed else 0.
            marginal_counts.append({"regime":group,"feature":feature,
                                    "class_rows":model.counts[group],"effective_observed_count":observed,
                                    "global_observed_count":len(model.global_values[j]),
                                    "class_cdf_weight":weight,"global_cdf_weight":1-weight})
    pd.DataFrame(marginal_counts).to_csv(out/"question3_structure_marginal_effective_counts.csv",index=False)
    filled = pd.DataFrame(model.imputer.transform(np.asarray(basis)), columns=BASE)
    # 编码下限来自真实标度参照，不能把插补产生的数再当成独立校准依据。
    reference = pd.read_excel(project/"data"/"D08.xlsx", sheet_name="ref_scale").set_index("object").reindex(raw.object)
    floors = fit_positive_floors(reference[[f"V{i:03d}" for i in range(1, 38)]])
    pd.DataFrame({"feature": list(floors), "positive_floor": list(floors.values())}).to_csv(
        out/"question3_structure_recording_floors.csv", index=False)
    rng = np.random.default_rng(SEED)
    generated_parts, generated_groups, identifiers, sampling = [], [], [], []
    for group in ("R20", "R12", "R13"):
        a, diagnostic = sample_valid(model, group, 100, rng)
        generated_parts.append(a)
        generated_groups.extend([group]*100)
        identifiers.extend([f"{group}_s{i+1:03d}" for i in range(100)])
        sampling.append(diagnostic)
    generated_basis = pd.concat(generated_parts, ignore_index=True)
    generated_native = expand_native(generated_basis)
    generated_recorded = native_to_recorded(generated_native, floors)
    for name, frame in (("base226_native", generated_basis), ("full231_native", generated_native),
                        ("full231_D01_scale", generated_recorded)):
        tagged(frame, identifiers, regime=generated_groups).to_csv(out/f"question3_structure_generated_{name}.csv", index=False)
    state_diagnostics(basis, generated_basis, groups, generated_groups, sampling).to_csv(
        out/"question3_structure_zero_negative_rates.csv", index=False)
    aggregate_range_diagnostics(basis, generated_basis, groups, generated_groups).to_csv(
        out/"question3_structure_derived_ranges.csv", index=False)
    import prediction
    continuous = prediction.predict_continuous(generated_recorded)
    working = prediction.working_grades(continuous)
    tagged(continuous, identifiers, regime=generated_groups).to_csv(out/"question3_structure_generated_profiles_D04_scale.csv", index=False)
    tagged(working, identifiers, regime=generated_groups).to_csv(out/"question3_structure_generated_profiles_WORKING_GRADES_NOT_IDENTIFIED.csv", index=False)
    representatives = write_representatives(raw, basis, generated_basis, generated_native, generated_recorded,
                                            identifiers, generated_groups, model, continuous, prediction, out)
    nearest = cdist(model.transform(generated_basis), model.transform(basis))
    pd.DataFrame({"generated_id": identifiers, "regime": generated_groups,
                  "nearest_training_object": objects[nearest.argmin(axis=1)],
                  "nearest_training_distance": nearest.min(axis=1)}).to_csv(out/"question3_structure_novelty.csv", index=False)
    original_source = raw.loc[groups == "R15", FEATURES].reset_index(drop=True)
    transfer = transfer_structure(model, basis, groups, objects, floors, prediction, original_source)
    tagged(transfer["slsqp_base"], transfer["source_objects"], "source_object").to_csv(
        out/"question3_structure_transfer_slsqp_base226_native.csv", index=False)
    original_source_profiles = prediction.predict_continuous(original_source)
    tagged(original_source_profiles, transfer["source_objects"], "source_object").to_csv(
        out/"question3_structure_transfer_original_D01_source_profiles.csv", index=False)
    transfer_profiles = {}
    for stage in ("source", "proposal", "after"):
        full = expand_native(transfer[stage])
        recorded = transfer["proposal_recorded"] if stage == "proposal" else native_to_recorded(full, floors)
        tagged(full, transfer["source_objects"], "source_object").to_csv(out/f"question3_structure_transfer_{stage}_native.csv", index=False)
        tagged(recorded, transfer["source_objects"], "source_object").to_csv(out/f"question3_structure_transfer_{stage}_D01_scale.csv", index=False)
        if stage != "proposal":
            profiles = prediction.predict_continuous(recorded)
            transfer_profiles[stage] = profiles
            tagged(profiles, transfer["source_objects"], "source_object").to_csv(out/f"question3_structure_transfer_{stage}_profiles_D04_scale.csv", index=False)
    working_k_table(transfer_profiles["source"], original_source_profiles, transfer_profiles["after"],
                    transfer["source_objects"], prediction).to_csv(out/"question3_structure_transfer_K_WORKING_ONLY.csv", index=False)
    # 对实际保存并重读的CSV复核，包含十进制序列化的舍入误差。
    relation_rows=[]
    for stage,native_name,recorded_name in (
        ("generated","question3_structure_generated_full231_native.csv","question3_structure_generated_full231_D01_scale.csv"),
        ("transfer_source","question3_structure_transfer_source_native.csv","question3_structure_transfer_source_D01_scale.csv"),
        ("transfer_after","question3_structure_transfer_after_native.csv","question3_structure_transfer_after_D01_scale.csv")):
        check=relation_diagnostics(pd.read_csv(out/native_name),pd.read_csv(out/recorded_name),stage)
        check["evaluation_point"]="read_saved_csv"
        relation_rows.append(check)
    pd.concat(relation_rows, ignore_index=True).to_csv(out/"question3_structure_candidate_relation_residuals.csv", index=False)
    transfer["comparison"].to_csv(out/"question3_structure_transfer_critical_comparison.csv", index=False)
    transfer["optimization"].to_csv(out/"question3_structure_transfer_optimization.csv", index=False)
    raw.loc[groups == "R15", ["object"]+FEATURES].to_csv(out/"question3_structure_transfer_original_D01_source.csv", index=False)
    observed_guard_note=run_observed_source_guard(project,model,raw,basis,floors)
    note = {"representation": "226_base_columns; V001-V036_ref_native; other_D01_observed_scale",
            "final_generator": "class_and_global_shrunk_step_empirical_marginals_with_shared_copula",
            "marginal_shrinkage_weight": "per_feature_nonmissing_n_jc/(n_jc+5)",
            "full231_native_filename_scope": "native_mixed: V001-V036_and_five_derived_native; remaining_columns_D01_observed_scale",
            "native_reference_missing": {v: int(basis[v].isna().sum()) for v in BASE[:36] if basis[v].isna().any()},
            "missing_handling": "CDFs_use_observed_cells; rank_geometry_and_transfer_use_training_medians; no_inverse_log_floor_fabrication",
            "derived_status": "five_data_supported_candidate_formulas; not_official_definitions",
            "generated_per_class": 100, "sampling": sampling, "seed": SEED,
            "heldout_repeats": repeats,
            "heldout_means": summary.astype(object).where(pd.notna(summary), None).to_dict(orient="index"),
            "transfer_fallback_count": int(transfer["optimization"].fallback_to_source.sum()),
            "transfer_path_search_count": int(transfer["optimization"].path_search_applied.sum()),
            "transfer_source_unchanged_count": int(transfer["optimization"].source_unchanged.sum()),
            "compatibility_screened_representative_counts": representatives.set_index("regime").selected_count.to_dict(),
            "true_K_status": "unidentified; only_fitted_continuous_prediction_constrained",
            "observed_source_guard":observed_guard_note,
            "source_baseline": "source_native_reexpressed_with_candidate_formulas_and_training_floors; original_D01_saved_separately"}
    (out/"question3_structure_summary.json").write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    make_figures(evaluation, continuous, generated_groups, transfer["optimization"], ROOT/"figures")
    print(json.dumps(note, ensure_ascii=False, indent=2))
    return note


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--reuse-heldout", action="store_true", help="仅重算生成迁移与图，复用已有留出表")
    parser.add_argument("--observed-guard-only",action="store_true",help="只新增观测源守卫迁移，不重跑生成池或留出比较")
    parser.add_argument("--guard-reuse-solver",action="store_true",help="同输入下复用已保存守卫求解候选，只作精确子空间投影和可行候选选择")
    args = parser.parse_args()
    if args.observed_guard_only:
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=2):
            run_observed_source_guard(args.project,reuse_solver=args.guard_reuse_solver)
    else:
        run_structure(args.project, args.repeats, args.reuse_heldout)
