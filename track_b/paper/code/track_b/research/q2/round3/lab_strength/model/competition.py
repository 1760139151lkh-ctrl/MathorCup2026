"""Fixed, interpretable lab constitutive competition; no local-event inputs.

All domains/held-out groups use nominal experimental classes. Continuous
predictors are the measured temperature and area-corrected normal stress.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
OUT = HERE / "results"
DATA = LAB / "audit/results/observations.csv"
T = "temperature_at_failure_c"
S = "normal_stress_at_failure_kpa"
TC = "temperature_target_c"
SC = "normal_stress_target_kpa"
Y = "peak_shear_kpa"
MODELS = (
    "mc_linear", "mc_temperature_quadratic", "mc_stress_quadratic",
    "mc_stress_hinge_400",
)
DOMAINS = ("low_full", "low_eq6_temperature", "warm_low", "warm_all")
WEIGHTS = ("row_ols", "cell_equal")
BOOTSTRAPS = 1000
SEED = 26082418


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(name, rows):
    pd.DataFrame(rows).to_csv(OUT / name, index=False, float_format="%.15g", lineterminator="\n")


def data_domains(df):
    low = df[SC] <= 400
    warm = df[TC].between(-4, -.5)
    return {
        "low_full": df.loc[low].copy(),
        "low_eq6_temperature": df.loc[low & df[TC].between(-8, -.5)].copy(),
        "warm_low": df.loc[low & warm].copy(),
        "warm_all": df.loc[warm].copy(),
    }


def features(model, temperature, stress):
    t, s = np.broadcast_arrays(np.asarray(temperature, float) / 5, np.asarray(stress, float) / 400)
    columns = [np.ones_like(t), t, s, t * s]
    if model == "mc_temperature_quadratic":
        columns += [t**2, t**2 * s]
    elif model == "mc_stress_quadratic":
        columns += [s**2, t * s**2]
    elif model == "mc_stress_hinge_400":
        hinge = np.maximum(s - 1, 0)
        columns += [hinge, t * hinge]
    elif model != "mc_linear":
        raise ValueError(model)
    return np.stack(columns, axis=-1)


def weights(df, policy):
    if policy == "row_ols":
        return np.ones(len(df))
    if policy != "cell_equal":
        raise ValueError(policy)
    n = df.groupby([TC, SC])[Y].transform("size").to_numpy(float)
    w = 1 / n
    return w / w.mean()


def solve(x, y, w):
    good = w > 0
    xw = x[good] * np.sqrt(w[good, None])
    yw = y[good] * np.sqrt(w[good])
    beta, _, rank, singular = np.linalg.lstsq(xw, yw, rcond=1e-12)
    condition = float(singular[0] / singular[-1]) if rank == x.shape[1] else None
    return beta, int(rank), condition


def fit(df, model, policy="row_ols"):
    x, y = features(model, df[T], df[S]), df[Y].to_numpy(float)
    w = weights(df, policy)
    beta, rank, condition = solve(x, y, w)
    result = {"beta": beta, "rank": rank, "condition": condition, "p": x.shape[1], "n": len(y)}
    if rank < x.shape[1]:
        return result
    residual = y - x @ beta
    bread = np.linalg.inv(x.T @ (w[:, None] * x))
    leverage = np.sum((x @ bread) * x, axis=1) * w
    # HC3: working independent-test calculation, not a material/event CI.
    adjusted = w * residual / np.maximum(1 - leverage, 1e-12)
    score = x * adjusted[:, None]
    hc3 = bread @ (score.T @ score) @ bread
    labels = df["specimen_label"].to_numpy()
    unique = np.unique(labels)
    blocks = np.array([(x[labels == label] * (w[labels == label] * residual[labels == label])[:, None]).sum(axis=0) for label in unique])
    factor = len(unique) / (len(unique) - 1) * (len(y) - 1) / (len(y) - x.shape[1])
    cr1 = factor * bread @ (blocks.T @ blocks) @ bread
    result.update({
        "residual": residual, "bread": bread, "hc3": hc3, "label_cr1": cr1,
        "max_training_leverage": float(leverage.max()), "clusters": len(unique),
    })
    return result


def metrics(df, predicted):
    residual = np.asarray(predicted) - df[Y].to_numpy(float)
    error = df[[TC, SC]].copy()
    error["squared"] = residual**2
    error["absolute"] = np.abs(residual)
    error["bias"] = residual
    cells = error.groupby([TC, SC])[["squared", "absolute", "bias"]].mean()
    return {
        "n": len(df), "rmse_kpa": float(np.sqrt(np.mean(residual**2))),
        "mae_kpa": float(np.mean(np.abs(residual))), "bias_kpa": float(np.mean(residual)),
        "cell_macro_rmse_kpa": float(np.sqrt(cells["squared"].mean())),
        "cell_macro_mae_kpa": float(cells["absolute"].mean()),
        "max_absolute_error_kpa": float(np.max(np.abs(residual))),
    }


def physical_diagnostics(df, model, beta):
    ts = np.linspace(df[TC].min(), df[TC].max(), 81)
    ss = np.linspace(df[SC].min(), df[SC].max(), 81)
    tt, sn = np.meshgrid(ts, ss, indexing="ij")
    tau = features(model, tt, sn) @ beta
    dt = (features(model, tt + 1e-4, sn) @ beta - features(model, tt - 1e-4, sn) @ beta) / 2e-4
    ds = (features(model, tt, sn + .001) @ beta - features(model, tt, sn - .001) @ beta) / .002
    # c(T) is a zero-stress extrapolated intercept, not an observed measurement.
    cohesion = features(model, ts, np.zeros_like(ts)) @ beta
    return {
        "diagnostic_grid": "81x81 nominal rectangular domain; not additional observations",
        "negative_strength_grid_points": int((tau < -1e-8).sum()),
        "negative_cohesion_intercept_points": int((cohesion < -1e-8).sum()),
        "warming_strength_increase_grid_points": int((dt > 1e-8).sum()),
        "negative_stress_derivative_grid_points": int((ds < -1e-8).sum()),
        "min_predicted_strength_kpa": float(tau.min()),
        "min_cohesion_intercept_kpa": float(cohesion.min()),
        "min_d_tau_d_sigma": float(ds.min()), "max_d_tau_d_T_kpa_per_c": float(dt.max()),
    }


def bootstrap(df, model, scheme, rng):
    x, y = features(model, df[T], df[S]), df[Y].to_numpy(float)
    labels = df["specimen_label"].to_numpy()
    distinct = np.unique(labels)
    cells = list(df.groupby([TC, SC], sort=True).indices.values())
    draws, failed = [], 0
    for _ in range(BOOTSTRAPS):
        if scheme == "within_cell_independent_tests":
            indices = np.concatenate([rng.choice(i, len(i), replace=True) for i in cells])
            xb, yb = x[indices], y[indices]
            beta, rank, _ = solve(xb, yb, np.ones(len(indices)))
        elif scheme == "specimen_label_blocks_assumed":
            chosen = Counter(rng.choice(distinct, len(distinct), replace=True))
            w = np.array([chosen.get(label, 0) for label in labels], dtype=float)
            beta, rank, _ = solve(x, y, w)
        else:
            raise ValueError(scheme)
        if rank < x.shape[1] or not np.isfinite(beta).all():
            failed += 1
        else:
            draws.append(beta)
    return np.asarray(draws), failed


def run():
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA)
    assert len(df) == 141 and df["observation_id"].is_unique
    assert np.isfinite(df[[T, S, TC, SC, Y]].to_numpy(float)).all()
    sets = data_domains(df)
    assert {key: len(value) for key, value in sets.items()} == {
        "low_full": 121, "low_eq6_temperature": 107, "warm_low": 63, "warm_all": 83,
    }
    config = {
        "models": list(MODELS), "fixed_reference": "author_eq6",
        "basis": "t=T_degC/5, s=sigma_kPa/400; tau_kPa",
        "models_and_terms": {
            "mc_linear": ["1", "t", "s", "t*s"],
            "mc_temperature_quadratic": ["1", "t", "s", "t*s", "t^2", "t^2*s"],
            "mc_stress_quadratic": ["1", "t", "s", "t*s", "s^2", "t*s^2"],
            "mc_stress_hinge_400": ["1", "t", "s", "t*s", "max(s-1,0)", "t*max(s-1,0)"],
        },
        "subset_and_holdout_groups": "nominal experimental classes; measured continuous predictors",
        "design": "four predeclared domains, two weights, complete temperature/stress/specimen-label holdouts",
        "fit": "weighted least squares, rcond1e-12; no penalty/model selection/clipping",
        "bootstrap_repetitions": BOOTSTRAPS, "seed": SEED,
        "bootstrap": ["within_cell_independent_tests", "specimen_label_blocks_assumed"],
        "fixed_reference_cv": "Not included in CV rankings: original article reused these data",
        "independent_local_events": 0,
        "protocol_sha256": sha(LAB / "PROTOCOL.md"),
        "protocol_amendment_sha256": sha(LAB / "PROTOCOL_AMENDMENT.md"),
        "data_sha256": sha(DATA), "code_sha256": sha(__file__),
        "environment": {"python": platform.python_version(), "executable": sys.executable, "numpy": np.__version__, "pandas": pd.__version__},
    }
    # This writes the frozen recipe before any fits in this run.
    save_json(OUT / "run_config.json", config)
    fits, residual_rows, coefficient_rows, covariance_rows, domain_rows = [], [], [], [], []
    cv_predictions, folds, cv_aggregate, boot_summary, boot_curves, draw_store = [], [], [], [], [], {}
    rng = np.random.default_rng(SEED)
    for domain, sub in sets.items():
        sub = sub.reset_index(drop=True)
        domain_rows.append({
            "domain": domain, "n": len(sub), "temperature_classes": sorted(sub[TC].unique().tolist()),
            "stress_classes": sorted(sub[SC].unique().tolist()), "specimen_labels": sorted(sub["specimen_label"].unique().tolist()),
            "measured_temperature_min_c": float(sub[T].min()), "measured_temperature_max_c": float(sub[T].max()),
            "measured_normal_stress_min_kpa": float(sub[S].min()), "measured_normal_stress_max_kpa": float(sub[S].max()),
            "actual_outside_original_eq6_strict_continuous_domain": int((~sub[T].between(-8, -.5) | ~sub[S].between(100, 400)).sum()),
            "actual_outside_eq6_with_explicit_temperature_tolerance_0p1c": int((~sub[T].between(-8.1, -.4) | ~sub[S].between(100, 400)).sum()),
            "single_test_cells": int((sub.groupby([TC, SC]).size() == 1).sum()),
            "test_cells": int(sub.groupby([TC, SC]).ngroups),
        })
        author_pred = 53.3 - 73.5 * sub[T].to_numpy() + sub[S].to_numpy() * (.42 - .21 * sub[T].to_numpy())
        fits.append({"domain": domain, "model": "author_eq6", "weight": "fixed_published_reference", "parameter_count": 0,
                     "role": "retrospective_published_reference_not_independent_validation", **metrics(sub, author_pred)})
        for idx, (_, row) in enumerate(sub.iterrows()):
            residual_rows.append({"domain": domain, "model": "author_eq6", "weight": "fixed_published_reference", "observation_id": row.observation_id,
                                  TC: row[TC], SC: row[SC], T: row[T], S: row[S], "observed_kpa": row[Y], "predicted_kpa": author_pred[idx], "residual_pred_minus_observed_kpa": author_pred[idx] - row[Y]})
        for model in MODELS:
            for policy in WEIGHTS:
                fitted = fit(sub, model, policy)
                assert fitted["rank"] == fitted["p"], (domain, model, policy)
                beta = fitted["beta"]
                pred = features(model, sub[T], sub[S]) @ beta
                fits.append({"domain": domain, "model": model, "weight": policy, "parameter_count": fitted["p"], "rank": fitted["rank"],
                             "condition_number_scaled_design": fitted["condition"], "max_training_leverage": fitted["max_training_leverage"],
                             "role": "external_lab_calibration", **metrics(sub, pred), **physical_diagnostics(sub, model, beta)})
                for k, value in enumerate(beta):
                    coefficient_rows.append({"domain": domain, "model": model, "weight": policy, "term": config["models_and_terms"][model][k], "coefficient_kpa": value,
                                             "hc3_independence_se_kpa": np.sqrt(max(0, fitted["hc3"][k, k])),
                                             "assumed_label_cluster_cr1_se_kpa": np.sqrt(max(0, fitted["label_cr1"][k, k])), "label_clusters": fitted["clusters"]})
                for covariance_name in ("hc3", "label_cr1"):
                    covariance_rows.append({"domain": domain, "model": model, "weight": policy, "method": covariance_name,
                                            "matrix_kpa_squared": fitted[covariance_name].tolist(), "conditional_assumptions": "See PROTOCOL_AMENDMENT.md; labels not verified physical UIDs"})
                for idx, (_, row) in enumerate(sub.iterrows()):
                    residual_rows.append({"domain": domain, "model": model, "weight": policy, "observation_id": row.observation_id,
                                          TC: row[TC], SC: row[SC], T: row[T], S: row[S], "observed_kpa": row[Y], "predicted_kpa": pred[idx], "residual_pred_minus_observed_kpa": pred[idx] - row[Y]})
                for group_column, scheme in ((TC, "temperature"), (SC, "normal_stress"), ("specimen_label", "specimen_label_assumed")):
                    scheme_rows = []
                    for group in sorted(sub[group_column].unique()):
                        test_mask = sub[group_column] == group
                        train, test = sub.loc[~test_mask], sub.loc[test_mask]
                        trained = fit(train, model, policy)
                        identity = {"domain": domain, "model": model, "weight": policy, "holdout_scheme": scheme, "heldout_group": str(group)}
                        fold = {
                            **identity, "training_n": len(train), "test_n": len(test), "rank": trained["rank"], "parameter_count": trained["p"],
                            "condition_number_scaled_design": trained["condition"],
                            "train_stress_classes": json.dumps(sorted(train[SC].unique().tolist())),
                            "train_temperature_classes": json.dumps(sorted(train[TC].unique().tolist())),
                            "train_measured_sigma_min_kpa": train[S].min(), "train_measured_sigma_max_kpa": train[S].max(),
                            "train_measured_T_min_c": train[T].min(), "train_measured_T_max_c": train[T].max(),
                            "test_ids_sha256": hashlib.sha256("\n".join(test.observation_id).encode()).hexdigest(),
                            "status": "full_rank" if trained["rank"] == trained["p"] else "rank_deficient_no_prediction",
                            "high_stress_design_support_absent": bool(train[SC].max() <= 400 and test[SC].max() > 400),
                            "test_group_is_nominal_edge": bool(group_column != "specimen_label" and group in (sub[group_column].min(), sub[group_column].max())),
                        }
                        if trained["rank"] != trained["p"]:
                            folds.append(fold)
                            continue
                        xt = features(model, test[T], test[S])
                        predicted = xt @ trained["beta"]
                        leverage = np.sum((xt @ trained["bread"]) * xt, axis=1)
                        se = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", xt, trained["label_cr1"], xt), 0))
                        fold.update({**metrics(test, predicted), "max_test_design_leverage": float(leverage.max()),
                                     "max_conditional_mean_label_cr1_se_kpa": float(se.max()),
                                     "max_training_leverage": trained["max_training_leverage"]})
                        folds.append(fold)
                        for idx, (_, row) in enumerate(test.iterrows()):
                            item = {
                                **identity, "observation_id": row.observation_id, "specimen_label": row.specimen_label,
                                TC: row[TC], SC: row[SC], T: row[T], S: row[S], "observed_kpa": row[Y],
                                "predicted_kpa": predicted[idx], "residual_pred_minus_observed_kpa": predicted[idx] - row[Y],
                                "design_leverage": leverage[idx], "assumed_label_cr1_conditional_mean_se_kpa": se[idx],
                                "outside_training_measured_sigma_range": bool(row[S] < train[S].min() or row[S] > train[S].max()),
                                "outside_training_measured_temperature_range": bool(row[T] < train[T].min() or row[T] > train[T].max()),
                            }
                            scheme_rows.append(item)
                            cv_predictions.append(item)
                    group_folds = [r for r in folds if all(r.get(k) == v for k, v in {"domain": domain, "model": model, "weight": policy, "holdout_scheme": scheme}.items())]
                    if scheme_rows:
                        pframe = pd.DataFrame(scheme_rows)
                        pseudo = pframe.rename(columns={"observed_kpa": Y})
                        usable_folds = [r for r in group_folds if r["status"] == "full_rank"]
                        cv_aggregate.append({
                            "domain": domain, "model": model, "weight": policy, "holdout_scheme": scheme,
                            **metrics(pseudo, pframe.predicted_kpa), "folds": len(group_folds), "usable_folds": len(usable_folds),
                            "missing_prediction_count": len(sub) - len(pframe),
                            "group_macro_rmse_kpa": float(np.sqrt(np.mean([r["rmse_kpa"]**2 for r in usable_folds]))),
                            "group_macro_mae_kpa": float(np.mean([r["mae_kpa"] for r in usable_folds])),
                        })
            # Bootstrap primary row-OLS fits only; weighted fit is a separate sensitivity.
            ts = np.linspace(sub[TC].min(), sub[TC].max(), 81)
            stresses = sorted(sub[SC].unique())
            grid_t, grid_s = np.meshgrid(ts, stresses, indexing="ij")
            gridx = features(model, grid_t.ravel(), grid_s.ravel())
            primary = fit(sub, model, "row_ols")
            for scheme in ("within_cell_independent_tests", "specimen_label_blocks_assumed"):
                draws, failed = bootstrap(sub, model, scheme, rng)
                assert len(draws) > 0
                key = domain + "__" + model + "__" + scheme
                draw_store[key] = draws
                q = np.quantile(draws, [.025, .5, .975], axis=0)
                boot_summary.append({"domain": domain, "model": model, "scheme": scheme, "attempted_draws": BOOTSTRAPS,
                                     "usable_draws": len(draws), "rank_deficient_or_nonfinite_draws": failed,
                                     "actual_label_count": sub.specimen_label.nunique(), "physical_UID_known": False,
                                     "coefficient_percentiles_2p5_50_97p5_kpa": q.tolist(),
                                     "interpretation": "conditional percentile sensitivity; not guaranteed 95% coverage or local event probability"})
                predictions = draws @ gridx.T
                curves = np.quantile(predictions, [.025, .5, .975], axis=0)
                hc3_se = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", gridx, primary["hc3"], gridx), 0))
                cr1_se = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", gridx, primary["label_cr1"], gridx), 0))
                primary_pred = gridx @ primary["beta"]
                hc3_q = student_t.ppf(.975, len(sub) - primary["p"])
                cr1_q = student_t.ppf(.975, primary["clusters"] - 1)
                for i in range(len(gridx)):
                    boot_curves.append({"domain": domain, "model": model, "scheme": scheme, "temperature_c": grid_t.ravel()[i], "normal_stress_kpa": grid_s.ravel()[i],
                                        "primary_mean_kpa": primary_pred[i], "percentile_2p5_mean_kpa": curves[0, i], "percentile_50_mean_kpa": curves[1, i], "percentile_97p5_mean_kpa": curves[2, i],
                                        "hc3_independence_mean_low_kpa": primary_pred[i] - hc3_q * hc3_se[i], "hc3_independence_mean_high_kpa": primary_pred[i] + hc3_q * hc3_se[i],
                                        "assumed_label_cr1_mean_low_kpa": primary_pred[i] - cr1_q * cr1_se[i], "assumed_label_cr1_mean_high_kpa": primary_pred[i] + cr1_q * cr1_se[i]})
    write_csv("fits.csv", fits)
    write_csv("coefficients.csv", coefficient_rows)
    write_csv("calibration_residuals.csv", residual_rows)
    write_csv("holdout_folds.csv", folds)
    write_csv("holdout_predictions.csv", cv_predictions)
    write_csv("holdout_summary.csv", cv_aggregate)
    write_csv("uncertainty_curves.csv", boot_curves)
    save_json(OUT / "covariances.json", covariance_rows)
    save_json(OUT / "domains.json", domain_rows)
    save_json(OUT / "bootstrap_summary.json", boot_summary)
    np.savez_compressed(OUT / "bootstrap_coefficient_draws.npz", **draw_store)
    audit = {
        "complete": True, "domains": {k: len(v) for k, v in sets.items()},
        "new_fits": len([r for r in fits if r["model"] != "author_eq6"]),
        "fixed_author_references": 4, "holdout_fits": len(folds),
        "holdout_predictions": len(cv_predictions), "bootstrap_attempts": BOOTSTRAPS * len(boot_summary),
        "bootstrap_usable": int(sum(r["usable_draws"] for r in boot_summary)),
        "bootstrap_failed_rank_or_nonfinite": int(sum(r["rank_deficient_or_nonfinite_draws"] for r in boot_summary)),
        "models_not_automatically_selected": True, "local_models_modified": False, "independent_local_events": 0,
        "elapsed_seconds": time.monotonic() - started,
        "scope": "External laboratory experiments; grouping and covariance sensitivity do not establish local applicability",
    }
    save_json(OUT / "run_summary.json", audit)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    run()
