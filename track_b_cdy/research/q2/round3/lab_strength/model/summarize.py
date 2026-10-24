"""Compact, machine-readable report numbers from completed lab-only results."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from competition import DATA, LAB, MODELS, OUT, SC, S, TC, T, features, save_json, sha


def main():
    df = pd.read_csv(DATA)
    coefficients = pd.read_csv(OUT / "coefficients.csv")
    fits = pd.read_csv(OUT / "fits.csv")
    cv = pd.read_csv(OUT / "holdout_summary.csv")
    folds = pd.read_csv(OUT / "holdout_folds.csv")
    draws = np.load(OUT / "bootstrap_coefficient_draws.npz", allow_pickle=False)
    key = {"domain": "warm_all", "weight": "row_ols"}
    intervals = []
    for model in MODELS:
        beta = coefficients.loc[(coefficients.domain == key["domain"]) & (coefficients.weight == key["weight"]) & (coefficients.model == model), "coefficient_kpa"].to_numpy()
        x = features(model, -2, 800)
        for scheme in ("within_cell_independent_tests", "specimen_label_blocks_assumed"):
            b = draws[f"warm_all__{model}__{scheme}"]
            intervals.append({"model": model, "scheme": scheme, "temperature_c": -2, "normal_stress_kpa": 800,
                              "role": "fixed_nominal_lab_design_coordinate_not_local_event_target",
                              "mean_kpa": float(x @ beta), "mean_percentiles_2p5_50_97p5_kpa": np.quantile(b @ x, [.025, .5, .975]).tolist(),
                              "usable_draws": len(b), "not_individual_prediction_interval_or_event_probability": True})
    low = coefficients.loc[(coefficients.domain == "warm_low") & (coefficients.model == "mc_linear") & (coefficients.weight == "row_ols"), "coefficient_kpa"].to_numpy()
    full = coefficients.loc[(coefficients.domain == "warm_all") & (coefficients.model == "mc_linear") & (coefficients.weight == "row_ols"), "coefficient_kpa"].to_numpy()
    high = df.loc[df[SC] == 800]
    warm_table = cv.loc[(cv.domain == "warm_all") & (cv.weight == "row_ols")]
    # Convert normalized basis into the physical-unit linear MC coefficients.
    def physical(b):
        return {"c_intercept_kpa": float(b[0]), "c_T_slope_kpa_per_c": float(b[1] / 5),
                "mu_intercept": float(b[2] / 400), "mu_T_slope_per_c": float(b[3] / 2000)}
    result = {
        "scope": "External raw-laboratory evidence only; no local-model updates or probability inference",
        "independent_local_events": 0,
        "high_class": {"nominal_kpa": 800, "tests": len(high), "measured_normal_stress_min_kpa": float(high[S].min()),
                       "measured_normal_stress_max_kpa": float(high[S].max()), "measured_temperature_min_c": float(high[T].min()),
                       "measured_temperature_max_c": float(high[T].max()),
                       "nominal_temperature_classes_c": sorted(high[TC].unique().tolist()),
                       "failure_type_counts": high.failure_type_description.value_counts().to_dict()},
        "warm_linear_coefficients": {"warm_low": physical(low), "warm_all": physical(full)},
        "warm_grouped_metrics_row_ols": warm_table.to_dict(orient="records"),
        "warm_800_class_holdout_row_ols": folds.loc[(folds.domain == "warm_all") & (folds.weight == "row_ols") & (folds.holdout_scheme == "normal_stress") & (folds.heldout_group.astype(str) == "800.0")].to_dict(orient="records"),
        "conditional_mean_intervals_at_registered_lab_coordinate": intervals,
        "rank_deficient_folds": folds.loc[folds.status != "full_rank", ["domain", "model", "weight", "holdout_scheme", "heldout_group", "rank", "parameter_count"]].to_dict(orient="records"),
        "fixed_author_reference_role": "Retrospective same-table score; never ranked as independent CV",
        "source_result_bindings": [{"path": str(p.relative_to(LAB)), "sha256": sha(p)} for p in [DATA, OUT / "fits.csv", OUT / "coefficients.csv", OUT / "holdout_summary.csv", OUT / "holdout_folds.csv", OUT / "bootstrap_coefficient_draws.npz"]],
    }
    # CSV deserialization contains NaN only in nonselected fixed-reference
    # columns. Selected rows above are finite. Reject silently invalid JSON.
    save_json(OUT / "decision_summary.json", result)
    print(json.dumps({"conditional_mean_examples": intervals}, ensure_ascii=False))


if __name__ == "__main__":
    main()
