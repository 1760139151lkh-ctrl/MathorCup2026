"""Standalone scientific figures; original XLSX and earlier bundles read-only."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from competition import DATA, LAB, MODELS, OUT, SC, S, TC, T, Y, features

FIG = LAB / "figures"
COLORS = {"mc_linear": "#24699c", "mc_temperature_quadratic": "#aa6222", "mc_stress_quadratic": "#8d4f85", "mc_stress_hinge_400": "#3c8070"}
NAMES = {"mc_linear": "MC linear T", "mc_temperature_quadratic": "MC quadratic T", "mc_stress_quadratic": "Quadratic stress", "mc_stress_hinge_400": "Stress hinge 400"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 11, "figure.titlesize": 14,
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 160})


def save(fig, name):
    # Explicit title/footer reservation: a post-hoc constrained-layout rect can
    # otherwise leave subplot titles at the canvas top under the suptitle.
    fig.set_layout_engine(None)
    fig.tight_layout(rect=(.005, .10, .995, .91), h_pad=2.0, w_pad=1.8)
    fig.savefig(FIG / (name + ".png"), facecolor="white")
    fig.savefig(FIG / (name + ".pdf"), facecolor="white")
    plt.close(fig)


def design(df):
    counts = pd.crosstab(df[TC], df[SC]).sort_index()
    fig, axes = plt.subplots(1, 2, figsize=(11.7, 5.1), layout="constrained")
    values = counts.to_numpy()
    axes[0].imshow(values, cmap="Blues", vmin=0, vmax=6, aspect="auto")
    for i in range(len(counts)):
        for j in range(len(counts.columns)):
            axes[0].text(j, i, str(values[i, j]), ha="center", va="center", color="white" if values[i, j] > 3 else "#18242b")
    axes[0].set(xticks=np.arange(len(counts.columns)), xticklabels=[str(int(x)) for x in counts.columns],
                yticks=np.arange(len(counts)), yticklabels=[f"{x:g}" for x in counts.index], xlabel="Nominal normal stress (kPa)", ylabel="Nominal temperature (°C)", title="141 reported tests; cells contain repeat counts")
    for stress, group in df.groupby(SC):
        axes[1].scatter(group[T], group[S], s=30, alpha=.8, label=f"{stress:g} kPa class")
    axes[1].axhline(400, c="#555", lw=.8, ls="--")
    axes[1].axvline(-.5, c="#555", lw=.8, ls=":")
    axes[1].set(xlabel="Measured temperature at failure (°C)", ylabel="Measured normal stress at failure (kPa)", title="Measured predictors differ from class labels")
    axes[1].legend(loc="upper left", frameon=False, fontsize=9)
    fig.suptitle("External rock–ice laboratory design and actual support")
    fig.get_layout_engine().set(rect=(0, .07, 1, 1))
    fig.text(.5, .015, "All tests retained. Repeated specimen labels have unknown global physical identity; 800 kPa class exists only in the warm domain.", ha="center", fontsize=9)
    save(fig, "01_design_support")


def author():
    table = pd.read_csv(LAB / "audit/results/coefficient_strata.csv")
    stage1 = pd.read_csv(Path(__file__).parent / "author_results/stage1_temperature_regressions.csv")
    stage2 = pd.read_csv(Path(__file__).parent / "author_results/source_stage2_weight_sensitivity.csv")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    masks = {"nominal_100_400": {-8., -5., -4., -2., -.5}, "nominal_100_800": {-4., -2., -1., -.5}}
    for j, block in enumerate(masks):
        sub = table.loc[table.nominal_stress_group == block]
        raw = stage1.loc[(stage1.block == block) & (stage1.method == "individual_tests_ols")]
        for i, (response, column, error) in enumerate((("cohesion", "cohesion_kpa", "cohesion_error_kpa"), ("mu", "friction_coefficient_mu", "friction_coefficient_error"))):
            ax = axes[i, j]
            selected = sub.temperature_target_c.isin(masks[block])
            ax.errorbar(sub.friction_temperature_mean_c, sub[column], yerr=sub[error], xerr=sub.friction_temperature_error_c,
                        fmt="none", ecolor="#aaa", lw=.8, capsize=2)
            ax.scatter(sub.loc[selected, "friction_temperature_mean_c"], sub.loc[selected, column], c="#24699c", s=35, label="Source selected layers")
            ax.scatter(sub.loc[~selected, "friction_temperature_mean_c"], sub.loc[~selected, column], facecolors="none", edgecolors="#777", s=35, label="Source unselected layers")
            ax.scatter(raw.temperature_measured_mean_c, raw["intercept" if response == "cohesion" else "slope"], marker="x", c="#b66327", s=35, label="Raw-test OLS reconstruction")
            selected_fit = stage2.loc[(stage2.block == block) & (stage2.selection == "published_significant_layers") & (stage2.response == response)
                                     & (stage2.method == "inverse_response_error_squared_wls") & (stage2.temperature_axis == "source_measured_mean")].iloc[0]
            t = np.linspace(sub.loc[selected, "friction_temperature_mean_c"].min(), sub.loc[selected, "friction_temperature_mean_c"].max(), 150)
            ax.plot(t, selected_fit.intercept + selected_fit.slope * t, c="#24699c", lw=1.5, label="Two-stage WLS reconstruction")
            ax.set(xlabel="Measured mean temperature (°C)", ylabel="Cohesion intercept (kPa)" if i == 0 else "Friction coefficient μ",
                   title=("100–400" if j == 0 else "100–800 warm") + " nominal kPa")
    axes[0, 0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle("Author reconstruction: source summaries and full raw experiments")
    fig.get_layout_engine().set(rect=(0, .06, 1, 1))
    fig.text(.5, .012, "Error bars reproduce untyped source '_error' columns; they are not local prediction intervals. −0.5°C summaries do not exactly reproduce.", ha="center", fontsize=9)
    save(fig, "02_author_reconstruction")


def competition():
    summary = pd.read_csv(OUT / "holdout_summary.csv")
    folds = pd.read_csv(OUT / "holdout_folds.csv")
    fig, axes = plt.subplots(1, 4, figsize=(14.5, 4.9), layout="constrained")
    schemes = ("temperature", "normal_stress", "specimen_label_assumed")
    for i, scheme in enumerate(schemes):
        ax = axes[i]
        for j, model in enumerate(MODELS):
            rows = summary.loc[(summary.domain == "warm_all") & (summary.model == model) & (summary.holdout_scheme == scheme)]
            a = rows.loc[rows.weight == "row_ols"].iloc[0].group_macro_rmse_kpa
            b = rows.loc[rows.weight == "cell_equal"].iloc[0].group_macro_rmse_kpa
            ax.bar(j, a, width=.65, color=COLORS[model], alpha=.85)
            ax.scatter(j, b, marker="D", facecolors="white", edgecolors="#222", s=24, zorder=3)
            ax.text(j, a + 15, f"{a:.0f}", ha="center", fontsize=8)
        ax.set(xticks=range(4), xticklabels=["MC\nlinear T", "MC\nquad T", "Quad\nstress", "Hinge\n400"], ylabel="Group-macro RMSE (kPa)",
               title={"temperature": "Leave temperature\nclass out", "normal_stress": "Leave normal-stress\nclass out", "specimen_label_assumed": "Leave specimen\nlabel out"}[scheme])
        ax.set_ylim(0, max(axes[i].get_ylim()[1] * 1.10, 280))
    for j, model in enumerate(MODELS):
        rows = folds.loc[(folds.domain == "warm_all") & (folds.model == model) & (folds.holdout_scheme == "normal_stress") & (folds.heldout_group.astype(str) == "800.0")]
        a = rows.loc[rows.weight == "row_ols"].iloc[0].rmse_kpa
        b = rows.loc[rows.weight == "cell_equal"].iloc[0].rmse_kpa
        axes[3].bar(j, a, width=.65, color=COLORS[model], alpha=.85)
        axes[3].scatter(j, b, marker="D", facecolors="white", edgecolors="#222", s=24, zorder=3)
        axes[3].text(j, a + 22, f"{a:.0f}", ha="center", fontsize=8)
    axes[3].set(xticks=range(4), xticklabels=["MC\nlinear T", "MC\nquad T", "Quad\nstress", "Hinge\n400"], ylabel="Held-out-test RMSE (kPa)", title="Only 800 kPa class\nheld out")
    axes[3].set_ylim(0, axes[3].get_ylim()[1] * 1.10)
    fig.suptitle("Warm-domain grouped validation; all repetitions leave together")
    fig.get_layout_engine().set(rect=(0, .10, 1, 1))
    fig.text(.5, .035, "Bars: row OLS. White diamonds: cell-equal weighting. Published Eq6 is excluded from CV because these data developed it.", ha="center", fontsize=9)
    fig.text(.5, .005, "800-class holdout tests extrapolation from lower stress classes. These are laboratory generalization diagnostics, not local-event validation.", ha="center", fontsize=9)
    save(fig, "03_grouped_validation")


def stress_curves(df):
    coefficients = pd.read_csv(OUT / "coefficients.csv")
    fig, axes = plt.subplots(2, 2, figsize=(11.7, 7.8), layout="constrained")
    stress = np.linspace(80, 860, 181)
    for ax, temp in zip(axes.ravel(), (-4., -2., -1., -.5)):
        sub = df.loc[df[TC] == temp]
        ax.scatter(sub[S], sub[Y], c="#343b43", s=22, alpha=.8, label="All raw tests in class")
        for model in MODELS:
            beta = coefficients.loc[(coefficients.domain == "warm_all") & (coefficients.model == model) & (coefficients.weight == "row_ols"), "coefficient_kpa"].to_numpy()
            ax.plot(stress, features(model, np.full_like(stress, temp), stress) @ beta, c=COLORS[model], lw=1.5, label=NAMES[model])
        ref = 53.3 - 73.5 * temp + stress * (.42 - .21 * temp)
        ax.plot(stress, ref, c="#777", ls="--", lw=1.2, label="Fixed Eq6 reference")
        ax.axvspan(400, 860, facecolor="#ddd", alpha=.17)
        ax.set(title=f"Nominal T = {temp:g}°C", xlabel="Measured normal stress (kPa)", ylabel="Peak shear stress (kPa)")
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Competing warm-domain stress relations calibrated to 83 tests")
    fig.get_layout_engine().set(rect=(0, .075, 1, 1))
    fig.text(.5, .018, "Curves evaluate nominal T; dots retain measured T deviations. Grey region exceeds Eq6 nominal stress domain. Curves do not prove a mechanism.", ha="center", fontsize=9)
    save(fig, "04_stress_relations")


def uncertainty(df):
    curves = pd.read_csv(OUT / "uncertainty_curves.csv")
    fig, axes = plt.subplots(2, 2, figsize=(11.7, 7.8), layout="constrained")
    observed = df.loc[df[SC] == 800]
    for ax, model in zip(axes.ravel(), MODELS):
        sub = curves.loc[(curves.domain == "warm_all") & (curves.model == model) & (curves.normal_stress_kpa == 800)]
        clustered = sub.loc[sub.scheme == "specimen_label_blocks_assumed"]
        independent = sub.loc[sub.scheme == "within_cell_independent_tests"]
        ax.fill_between(clustered.temperature_c, clustered.percentile_2p5_mean_kpa, clustered.percentile_97p5_mean_kpa,
                        color=COLORS[model], alpha=.22, label="Assumed label-block percentile range")
        ax.plot(independent.temperature_c, independent.percentile_2p5_mean_kpa, c="#999", lw=1, ls=":", label="Independent-test range")
        ax.plot(independent.temperature_c, independent.percentile_97p5_mean_kpa, c="#999", lw=1, ls=":")
        ax.plot(clustered.temperature_c, clustered.primary_mean_kpa, c=COLORS[model], lw=1.5, label="Fitted conditional mean at 800 kPa")
        ax.scatter(observed[T], observed[Y], c="#333", s=20, alpha=.7, label="800-class tests (actual σ varies)")
        ax.set(title=NAMES[model], xlabel="Temperature (°C)", ylabel="Peak shear stress (kPa)")
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Conditional mean uncertainty and correlation sensitivity")
    fig.get_layout_engine().set(rect=(0, .08, 1, 1))
    fig.text(.5, .025, "Bands are 2.5/97.5 percentiles of 1000 conditional bootstrap fits. Eight labels are not verified physical specimen UIDs.", ha="center", fontsize=9)
    fig.text(.5, .005, "Mean bands exclude individual-test scatter and field-transfer error; they do not imply 95% event coverage or local probability.", ha="center", fontsize=9)
    save(fig, "05_conditional_uncertainty")


def run():
    FIG.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA)
    design(df)
    author()
    competition()
    stress_curves(df)
    uncertainty(df)
    print(json.dumps({"png_figures": 5, "pdf_figures": 5, "directory": str(FIG)}))


if __name__ == "__main__":
    run()
