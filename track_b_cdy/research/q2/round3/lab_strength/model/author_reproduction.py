"""Reconstruct two-stage published relations without double-counting summaries."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import linregress, t as student_t

from competition import DATA, LAB, SC, S, TC, T, Y, save_json, sha

OUT = Path(__file__).resolve().parent / "author_results"
SUMMARY = LAB / "audit/results/coefficient_strata.csv"


def linear(x, y, w=None):
    x, y = np.asarray(x, float), np.asarray(y, float)
    w = np.ones(len(x)) if w is None else np.asarray(w, float)
    design = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(design * np.sqrt(w[:, None]), y * np.sqrt(w), rcond=1e-12)[0]
    residual = y - design @ beta
    sigma2 = float(np.sum(w * residual**2) / (len(x) - 2))
    covariance = sigma2 * np.linalg.inv(design.T @ (w[:, None] * design))
    se = np.sqrt(np.diag(covariance))
    total = np.sum(w * (y - np.average(y, weights=w))**2)
    p = float(2 * student_t.sf(abs(beta[1] / se[1]), len(x) - 2))
    return {
        "intercept": float(beta[0]), "slope": float(beta[1]), "intercept_se": float(se[0]), "slope_se": float(se[1]),
        "slope_p_two_sided": p, "r_squared_weighted": float(1 - np.sum(w * residual**2) / total),
        "n_points": len(x), "df_residual": len(x) - 2,
    }


def csv(name, rows):
    pd.DataFrame(rows).to_csv(OUT / name, index=False, float_format="%.15g", lineterminator="\n")


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    df, summaries = pd.read_csv(DATA), pd.read_csv(SUMMARY)
    stage1, compare, stage2, pipeline = [], [], [], []
    # Predictor/response arithmetic means in text: examine rather than assume
    # whether the original first-stage fit used tests or condition means.
    for block, upper in (("nominal_100_400", 400), ("nominal_100_800", 800)):
        sub = df.loc[df[SC] <= upper]
        if upper == 800:
            sub = sub.loc[sub[TC].between(-4, -.5)]
        for temp, group in sub.groupby(TC, sort=True):
            cell = group.groupby(SC)[[S, Y]].mean()
            variance = group.groupby(SC)[S].var(ddof=1)
            for method in ("individual_tests_ols", "stress_cell_means_ols", "stress_cell_means_inverse_sigma_variance_wls"):
                if method == "individual_tests_ols":
                    result = linear(group[S], group[Y])
                elif method == "stress_cell_means_ols":
                    result = linear(cell[S], cell[Y])
                else:
                    if variance.isna().any() or (variance <= 0).any():
                        # A one-test condition has no empirical within-condition
                        # variance. Do not silently substitute zero/infinite W.
                        stage1.append({"block": block, "temperature_target_c": temp, "method": method,
                                       "status": "unavailable_singleton_or_zero_sigma_variance", "n_tests": len(group)})
                        continue
                    result = linear(cell[S], cell[Y], 1 / variance.to_numpy())
                row = {"block": block, "temperature_target_c": temp, "method": method, "status": "computed", "n_tests": len(group),
                       "temperature_measured_mean_c": group[T].mean(), "temperature_measured_sd_c": group[T].std(ddof=1), **result}
                stage1.append(row)
                published = summaries.loc[(summaries.nominal_stress_group == block) & (summaries.temperature_target_c == temp)].iloc[0]
                compare.append({"block": block, "temperature_target_c": temp, "method": method,
                                "raw_cohesion_kpa": result["intercept"], "source_cohesion_kpa": published.cohesion_kpa,
                                "cohesion_difference_kpa": result["intercept"] - published.cohesion_kpa,
                                "raw_mu": result["slope"], "source_mu": published.friction_coefficient_mu,
                                "mu_difference": result["slope"] - published.friction_coefficient_mu,
                                "raw_mu_se": result["slope_se"], "source_mu_error_untyped": published.friction_coefficient_error,
                                "raw_c_se_kpa": result["intercept_se"], "source_c_error_untyped_kpa": published.cohesion_error_kpa,
                                "raw_temperature_mean_c": group[T].mean(), "source_temperature_mean_c": published.friction_temperature_mean_c,
                                "raw_temperature_sd_c": group[T].std(ddof=1), "source_temperature_error_untyped_c": published.friction_temperature_error_c})
    first = pd.DataFrame(stage1)
    # Published figure screen is fixed from source. A separately calculated raw
    # slope screen is reported for each plausible first-stage method.
    fixed_masks = {"nominal_100_400": {-8., -5., -4., -2., -.5}, "nominal_100_800": {-4., -2., -1., -.5}}
    for block, table in summaries.groupby("nominal_stress_group", sort=True):
        selections = {"published_significant_layers": table.temperature_target_c.isin(fixed_masks[block]),
                      "all_layers_no_p_screen": np.ones(len(table), bool)}
        if block == "nominal_100_400":
            selections["warm_published_significant_layers"] = table.temperature_target_c.isin({-4., -2., -.5})
            selections["warm_all_layers_no_p_screen"] = table.temperature_target_c.between(-4, -.5)
        else:
            selections["warm_common_selected_layers"] = table.temperature_target_c.isin({-4., -2., -.5})
        for selection, mask in selections.items():
            selected = table.loc[mask]
            for response, response_column, error_column, tcol, terr in (
                ("cohesion", "cohesion_kpa", "cohesion_error_kpa", "cohesion_temperature_mean_c", "cohesion_temperature_error_c"),
                ("mu", "friction_coefficient_mu", "friction_coefficient_error", "friction_temperature_mean_c", "friction_temperature_error_c"),
            ):
                for method in ("ols", "inverse_response_error_squared_wls", "inverse_temperature_error_squared_wls"):
                    if method == "ols":
                        w = None
                    elif method == "inverse_response_error_squared_wls":
                        w = 1 / selected[error_column].to_numpy(float)**2
                    else:
                        w = 1 / selected[terr].to_numpy(float)**2
                    # A bounded source-axis audit, not a new constitutive
                    # candidate or a local-event-tuned modeling choice.
                    for temperature_axis in ("source_measured_mean", "nominal_class_axis_sensitivity"):
                        x = selected[tcol] if temperature_axis == "source_measured_mean" else selected.temperature_target_c
                        result = linear(x, selected[response_column], w)
                        stage2.append({"block": block, "selection": selection, "response": response, "method": method,
                                       "temperature_axis": temperature_axis, "temperature_layers": json.dumps(selected.temperature_target_c.tolist()),
                                       "source": "author_derived_workbook_summary_not_new_tests", **result})
        # Full two-stage recalculation, rather than treating source summaries as
        # independent observations added to the specimen table.
        for method in first.method.unique():
            rows = first.loc[(first.block == block) & (first.method == method) & (first.status == "computed")]
            for selection in ("published_significant_layers", "recomputed_stage1_p_le_0p05", "all_layers_no_p_screen"):
                if selection == "published_significant_layers":
                    selected = rows.loc[rows.temperature_target_c.isin(fixed_masks[block])]
                elif selection == "recomputed_stage1_p_le_0p05":
                    selected = rows.loc[rows.slope_p_two_sided <= .05]
                else:
                    selected = rows
                if len(selected) < 3:
                    pipeline.append({"block": block, "stage1_method": method, "selection": selection, "status": "fewer_than_three_temperature_layers", "n_layers": len(selected)})
                    continue
                for response, column, error in (("cohesion", "intercept", "intercept_se"), ("mu", "slope", "slope_se")):
                    for stage2_method in ("ols", "inverse_response_error_squared_wls", "inverse_temperature_error_squared_wls"):
                        if stage2_method == "ols":
                            w = None
                        elif stage2_method == "inverse_response_error_squared_wls":
                            w = 1 / selected[error].to_numpy()**2
                        else:
                            w = 1 / selected.temperature_measured_sd_c.to_numpy()**2
                        result = linear(selected.temperature_measured_mean_c, selected[column], w)
                        pipeline.append({"block": block, "stage1_method": method, "selection": selection, "stage2_method": stage2_method,
                                         "response": response, "status": "computed", "temperature_layers": json.dumps(selected.temperature_target_c.tolist()), **result})
    csv("stage1_temperature_regressions.csv", stage1)
    csv("raw_to_source_summary.csv", compare)
    csv("source_stage2_weight_sensitivity.csv", stage2)
    csv("raw_two_stage_pipeline.csv", pipeline)
    save_json(OUT / "protocol.json", {
        "input_observations_sha256": sha(DATA), "input_author_derived_summary_sha256": sha(SUMMARY), "code_sha256": sha(__file__),
        "first_stage_candidates": ["individual_tests_ols", "stress_cell_means_ols", "stress_cell_means_inverse_sigma_variance_wls"],
        "author_screen_by_source_figure": {key: sorted(value) for key, value in fixed_masks.items()},
        "stage2_variance_ambiguity_preserved": True, "no_singleton_variance_filled": True,
        "axis_sensitivity": "Both stored measured temperature means and nominal class coordinates are reported for source reconciliation only; fixed competition uses measured predictors",
        "fit_role": "external_source_reproduction_not_independent_validation", "independent_local_events": 0,
        "source_fig7_values": {
            "low_eq6_c_intercept_slope": [53.3, -73.5], "low_eq6_mu_intercept_slope": [.42, -.21],
            "warm_low_c_intercept_slope": [49.4, -83.5], "warm_low_mu_intercept_slope": [.28, -.38],
            "warm_all_c_intercept_slope": [104.5, -143.8], "warm_all_mu_intercept_slope": [.19, -.10],
        },
        "table2_internal_consistency": "Warm low-stress total/end-point reduction columns match Eq4/5 endpoints, per-degree slopes and R2/p match green warm fit; do not merge into one relation",
    })
    summary = {"stage1_records_including_unavailable": len(stage1), "source_comparisons": len(compare), "stage2_fits": len(stage2), "raw_pipeline_records": len(pipeline)}
    save_json(OUT / "run_summary.json", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    run()
