#!/usr/bin/env python3
"""Redraw Q1 paper figures from frozen round-3 outputs; never fit a model.

Run from the repository root:
    track_b/.venv/bin/python track_b/paper/scripts/q1_figures.py
"""
from pathlib import Path
import json
import hashlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[3]
R3 = ROOT / "track_b/research/q1/round3"
OUT = ROOT / "track_b/paper/figures/q1"
QC = "original_qc_view"
MODELS = ["A_marginal_ecdf", "B_shrunk_conditional", "C_other_family_analog"]
FONT_PATHS = [Path.home() / "Library/Fonts/PingFang Regular_0.ttf",
              Path.home() / "Library/Fonts/SimSun.ttf",
              Path("/System/Library/Fonts/Supplemental/Songti.ttc")]
font_path = next(p for p in FONT_PATHS if p.is_file())
font_manager.fontManager.addfont(str(font_path))
plt.rcParams.update({
    "font.family": font_manager.FontProperties(fname=str(font_path)).get_name(),
    "font.size": 8.3, "axes.labelsize": 8.3, "axes.titlesize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.unicode_minus": False, "pdf.fonttype": 42, "ps.fonttype": 42,
    "savefig.dpi": 300, "mathtext.fontset": "dejavusans",
})
OUT.mkdir(parents=True, exist_ok=True)
sources = set()


def read_csv(name):
    p = R3 / "results" / name
    sources.add(p)
    return pd.read_csv(p)


def save(fig, name):
    for ext in ["pdf", "png"]:
        meta = {"CreationDate": None, "ModDate": None, "Creator": "Q1 paper plotting"} if ext == "pdf" else None
        fig.savefig(OUT / f"{name}.{ext}", facecolor="white", bbox_inches="tight", pad_inches=.04, metadata=meta)
    plt.close(fig)


def annotated_heatmap(ax, values, rows, cols, title, cmap="Blues"):
    im = ax.imshow(values, vmin=0, vmax=1, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(cols)), cols)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_title(title, loc="left", pad=7)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for (i, j), val in np.ndenumerate(values):
        ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7.7,
                color="white" if val > .65 else "#162e3b")
    return im


def state_figure():
    p = R3 / "exports/hourly_drivers.parquet"
    sources.add(p)
    hourly = pd.read_parquet(p)
    reference = pd.Timestamp("2026-08-26T02:30:00Z")
    time_ns = pd.to_datetime(hourly.time_utc, utc=True).astype("datetime64[ns, UTC]").astype("int64")
    subset = hourly[(hourly.quality_track == QC) &
                    (time_ns >= reference.value - 168 * 3600 * 10**9) & (time_ns < reference.value)].copy()
    x = (time_ns.loc[subset.index] - reference.value) / (3600 * 10**9)
    y = subset.soil_vwc_0p1m.to_numpy()
    directions = read_csv("factor_directions.csv")
    ids = ["air_temperature_2m", "relative_humidity_2m", "wind_speed_10m",
           "soil_temperature_0p1m", "soil_vwc_0p1m", "soil_heat_flux_0p1m", "shortwave_down"]
    names = ["2 m 气温", "2 m 相对湿度", "10 m 风速", "0.1 m 土温",
             "0.1 m 含水率", "0.1 m 土热通量", "向下短波"]
    d = directions[(directions.quality_track == QC) & (directions.statistic == "median")]
    values = d.pivot(index="driver_id", columns="window_hours", values="background_percentile").loc[ids, [24, 72, 168]].to_numpy()
    fig, (ax, hm) = plt.subplots(1, 2, figsize=(6.65, 2.16),
                                  gridspec_kw={"width_ratios": [1.18, .9], "wspace": .54})
    ax.plot(x, y, color="#17657c", lw=1.25)
    ax.axvspan(-24, 0, color="#edf2f3", zorder=-2)
    ax.scatter([x.iloc[0], x.iloc[-1]], [y[0], y[-1]], s=13, color="#b56b35", zorder=3)
    ax.annotate(f"{y[0]:.4f}", (x.iloc[0], y[0]), xytext=(4, -13),
                textcoords="offset points", fontsize=8, color="#8b4f26")
    ax.annotate(f"{y[-1]:.5f}", (x.iloc[-1], y[-1]), xytext=(-5, 8),
                textcoords="offset points", ha="right", fontsize=8, color="#8b4f26")
    ax.set(xlim=(-170, 1), ylim=(.06, .18), xlabel="距参考时刻 / h",
           ylabel=r"体积含水率 / $\mathrm{m^3\,m^{-3}}$")
    ax.set_xticks([-168, -120, -72, -24, 0])
    ax.grid(axis="y", color="#e2e7ea", lw=.5)
    ax.set_title("(a) 土壤水分的实际变化", loc="left", pad=7)
    im = annotated_heatmap(hm, values, names, ["24 h", "72 h", "168 h"],
                           "(b) 窗口中位数的季节背景位置", "YlGnBu")
    cb = fig.colorbar(im, ax=hm, fraction=.06, pad=.035, ticks=[0, .5, 1])
    cb.ax.set_ylabel("加权背景百分位", fontsize=8)
    save(fig, "q1_state")
    return {"reference_utc": reference.isoformat(), "n_vwc": int(np.isfinite(y).sum()),
            "vwc_first": float(y[0]), "vwc_last": float(y[-1]),
            "representative_driver_ids": ids, "windows_hours": [24, 72, 168],
            "median_percentiles": values.tolist()}


def stability_figure():
    rec = read_csv("recommended_factors.csv")
    rec = rec[rec.quality_track == QC].sort_values("recommended_rank")
    ids, names = rec.family_id.tolist(), rec.family_name.tolist()
    draws = read_csv("ranking_stability.csv")
    d = draws[(draws.quality_track == QC) & (draws.kind == "hierarchical_bootstrap")]
    freq = d.groupby(["family_id", "model_id"]).top5_frequency.mean().unstack().loc[ids, MODELS]
    valid = {model: sorted(d[d.model_id == model].n_valid.unique().astype(int).tolist()) for model in MODELS}
    assert valid == {MODELS[0]: [89], MODELS[1]: [44], MODELS[2]: [89]}, valid
    s = read_csv("sensitivity_metrics.csv")
    s = s[s.quality_track == QC]
    groups = [
        ("参考时刻 ±1 h", (s.variant == "primary") & (s.shift_hours != 0)),
        ("过程块 3 / 14 d", s.variant.isin(["process_3", "process_14"])),
        ("季节范围 ±15 d", s.variant == "season_15"),
        ("支持率 50% / 90%", s.variant.isin(["support_0.5", "support_0.9"])),
        ("收缩系数 0.1 / 0.9", s.variant.isin(["shrinkage_0.1", "shrinkage_0.9"])),
        ("每年类比数 1 / 3", s.variant.isin(["analogs_1", "analogs_3"])),
    ]
    sensitivity = np.array([s[mask].groupby("model_id").top5_jaccard.mean().reindex(MODELS).to_numpy()
                            for _, mask in groups])
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.65, 2.25),
                                  gridspec_kw={"width_ratios": [.94, .94], "wspace": .77})
    im = annotated_heatmap(ax, freq.to_numpy(), names, ["A (89)", "B (44)", "C (89)"],
                           "(a) 三窗平均 TOP5 入选频率")
    cb = fig.colorbar(im, ax=ax, fraction=.06, pad=.035, ticks=[0, .5, 1])
    im2 = annotated_heatmap(bx, sensitivity, [label for label, _ in groups], ["A", "B", "C"],
                            "(b) 预设变动下的集合一致性", "YlGnBu")
    cb2 = fig.colorbar(im2, ax=bx, fraction=.06, pad=.035, ticks=[0, .5, 1])
    save(fig, "q1_stability")
    return {"family_ids": ids, "models": MODELS, "frequency_mean_over_three_windows": freq.to_numpy().tolist(),
            "valid_bootstrap_draws_per_window": valid, "requested_draws_per_window": 100,
            "sensitivity_categories": [label for label, _ in groups],
            "jaccard_mean_over_three_windows_and_listed_variants": sensitivity.tolist()}


if __name__ == "__main__":
    payload = {"state": state_figure(), "stability": stability_figure(),
               "font": str(font_path), "fit_performed": False}
    payload["source_files"] = [{"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                               for p in sorted(sources)]
    (OUT / "q1_figure_values.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print("Wrote q1_state.{pdf,png}, q1_stability.{pdf,png}, q1_figure_values.json")
