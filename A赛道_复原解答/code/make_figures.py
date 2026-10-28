# -*- coding: utf-8 -*-
"""生成论文用图（啤酒语义）。所有数值来自：
- 原题 1.csv/4.csv/8.xlsx（图1、图2、图13 等）
- A题_数学手记 的脱敏版结果经标签复原（图3–图12）
- 补充分析（图13）
输出：A赛道_复原解答/figures/*.png 与 _figure_manifest.json
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels as L

sys.stdout.reconfigure(encoding="utf-8")
OUT = L.RESULTS
FIG = L.FIGURES
FIG.mkdir(parents=True, exist_ok=True)
R = L.SAND_SOL / "results"

mpl.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans SC"],
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.5,
    "figure.dpi": 110,
    "savefig.dpi": 240,
    "savefig.bbox": "tight",
})
MANIFEST = []

def save(fig, name, caption):
    p = FIG / name
    fig.savefig(p)
    plt.close(fig)
    MANIFEST.append({"file": name, "caption": caption})
    print("[fig]", name)

# 颜色
C = dict(blue="#3B6EA8", orange="#D9822B", green="#4C9F70", red="#C0504D",
         purple="#7E6ABA", gray="#8A8A8A", light="#E8EDF3", dark="#2F3E4E",
         teal="#4FA3A5", gold="#C9A227")
BLOCK_COLORS = {"香气(Aroma)": C["blue"], "风味(Flavour)": C["orange"],
                "口感/缺陷/总体": C["green"]}
ORIGIN_COLORS = {"Hops": C["green"], "Yeast": C["orange"], "Malt": C["gold"],
                 "Spices": C["red"], "Wild flora": C["purple"], "Others": C["gray"],
                 "Internal standard solution": "#BBBBBB", "": "#DDDDDD"}

meta, X = L.read_orig_chem()
_, Y = L.read_orig_sensory()
style_counts = meta["style"].value_counts()

# ============================================================ 图1 数据概况
fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.5), gridspec_kw={"width_ratios": [1.15, 1, 1]})
ax = axes[0]
sc = style_counts.sort_values()
ax.barh(range(len(sc)), sc.values, color=C["blue"], alpha=0.85)
ax.set_yticks(range(len(sc)))
ax.set_yticklabels(sc.index, fontsize=7.5)
ax.set_xlabel("样本数")
ax.set_title("(a) 22 个啤酒风格的样本数")
ax.grid(axis="x", alpha=0.25)

ax = axes[1]
miss = X.isna().sum()
miss = miss[miss > 0].sort_values()
ax.barh(range(len(miss)), miss.values, color=C["orange"])
ax.set_yticks(range(len(miss)))
ax.set_yticklabels([L.FEATURE_INFO[L.V2ID[c]]["pretty"] for c in miss.index], fontsize=7.5)
ax.set_xlabel("缺失单元数")
ax.set_title(f"(b) 231 个特征中仅 9 列存在缺失（共 {int(miss.sum())} 格）")
ax.grid(axis="x", alpha=0.25)

ax = axes[2]
sel_dims = ["acidity", "bitternes", "alcohol", "stale_hops", "overall", "dms"]
vals = [Y[d].values for d in sel_dims]
bp = ax.boxplot(vals, widths=0.55, patch_artist=True, showfliers=False)
for patch, col in zip(bp["boxes"], [C["blue"], C["teal"], C["green"], C["red"], C["purple"], C["gold"]]):
    patch.set_facecolor(col); patch.set_alpha(0.55)
ax.axhline(0, color=C["gray"], lw=0.8, ls="--")
ax.set_xticks(range(1, len(sel_dims) + 1))
ax.set_xticklabels(["酸度", "苦度", "酒精感", "陈酒花", "总体", "DMS"], fontsize=8)
ax.set_ylabel("4.csv 连续评分（z 化）")
ax.set_title("(c) 感官标签是标准化连续值")

fig.suptitle("数据概况：样本、缺失与标签性质", fontsize=12, y=1.02)
save(fig, "fig01_数据概况.png",
     "图 1 数据概况。(a) 22 个风格的样本数；(b) 231 个特征中的缺失分布（73 格）；"
     "(c) 4.csv 感官目标为标准化后的连续值（含负值），并非原始 0–6 分。")

# ============================================================ 图2 标度核验
import openpyxl
wb = openpyxl.load_workbook(L.ORIG / "8.xlsx", data_only=True)
ws = wb["Calibrated chemical dataset"]
rows = list(ws.iter_rows(values_only=True))
cal = pd.DataFrame(rows[1:], columns=rows[0])
cal = cal[[c for c in cal.columns if c is not None]]
cal["beer"] = cal["beer"].astype(int)
cal_idx = cal.set_index("beer")
beers = meta["beer"].values

def native_of(col):
    return pd.to_numeric(pd.Series(cal_idx.loc[beers, col].values), errors="coerce")

fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.6))
for ax, col, title, unit in [
    (axes[0], "pH", "(a) pH 记录值 = log10(原生值)", ""),
    (axes[1], "ethanol..v.v.", "(b) 乙醇记录值 = log10(%v/v)", "% v/v"),
]:
    x = X[col].values.astype(float)
    y = native_of(col).values.astype(float)
    ok = np.isfinite(x) & np.isfinite(y) & (y > 0)
    ax.scatter(y[ok], x[ok], s=11, color=C["blue"], alpha=0.65, label="1.csv 记录值")
    yy = np.linspace(max(y[ok].min(), 1e-4), y[ok].max(), 50)
    ax.plot(yy, np.log10(yy), color=C["red"], lw=1.6, label="log10 理论线")
    ax.plot(yy, np.log(yy), color=C["gray"], lw=1.2, ls="--", label="ln 理论线")
    ax.set_xlabel(f"8.xlsx 校准原生值（{unit}）" if unit else "8.xlsx 校准原生值")
    ax.set_ylabel("1.csv 记录值")
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=7.5)
    ax.grid(alpha=0.25)

ax = axes[2]
x4 = pd.to_numeric(pd.Series(native_of("X4VG")), errors="coerce")
rec4 = X["X4VG"].values
ax.scatter(x4.fillna(0).values, rec4, s=14, color=C["orange"], alpha=0.7)
n_zero = int((x4.fillna(0) == 0).sum())
ax.axhline(np.log10(0.0194031667 / 2), color=C["red"], lw=1.4, ls="--",
           label=f"非正原生值的下限 log10(m/2)≈{np.log10(0.0097015833):.4f}")
ax.set_xlabel("8.xlsx 校准原生 4-VG 浓度（mg/L）")
ax.set_ylabel("1.csv 记录值")
ax.set_title(f"(c) 4-VG：{n_zero} 个原生 0 被压成同一有限下限")
ax.legend(loc="lower right", fontsize=7)
ax.grid(alpha=0.25)
fig.suptitle("对数底数与零点处理核验", fontsize=12, y=1.02)
save(fig, "fig02_标度核验.png",
     "图 2 标度核验。(a)(b) 37 个参数列与 8.xlsx 原生校准值满足 10^记录值=原生值，"
     "对 ln 假设明显不符；(c) 原生浓度为 0 的 4-VG 被替换为“最小正值的一半”后取对数，"
     "因此 10^记录值不等于原生 0。")

# ============================================================ 图3 问题1 逐维度 R²
q1 = pd.read_csv(OUT / "Q1_逐维度交叉验证指标.csv")
sel_rand = q1[(q1["model"] == "selected") & (q1["protocol"] == "nested_random_5x3")].copy()
sel_reg = q1[(q1["model"] == "selected") & (q1["protocol"] == "nested_regime_holdout_5x3")].copy()
order = sel_rand.sort_values("r2", ascending=False).copy()
order["block"] = order["target"].map(lambda y: L.TARGET_INFO[y]["block"] if y in L.TARGET_INFO else "口感/缺陷/总体")
fig, ax = plt.subplots(figsize=(11.2, 4.0))
xpos = np.arange(len(order))
ax.bar(xpos - 0.2, order["r2"].values, width=0.4, color=[BLOCK_COLORS[b] for b in order["block"]],
       label="随机 5 折（主结果）")
ax.bar(xpos + 0.2, sel_reg.set_index("target").loc[order["target"], "r2"].values,
       width=0.4, color="white", edgecolor=C["gray"], hatch="////", label="整风格留组 5 折")
ax.axhline(0, color="black", lw=0.8)
ax.set_xticks(xpos)
ax.set_xticklabels(order["target_name"], rotation=90, fontsize=7.2)
ax.set_ylabel("折外 $R^2$")
ax.set_title("图 3  50 个感官维度的折外预测表现（PLS 主模型）")
from matplotlib.patches import Patch
handles = [Patch(color=BLOCK_COLORS[k], label=k) for k in BLOCK_COLORS]
handles.append(Patch(facecolor="white", edgecolor=C["gray"], hatch="////", label="整风格留组"))
ax.legend(handles=handles, ncol=4, loc="upper right", fontsize=8)
ax.grid(axis="y", alpha=0.25)
ax.set_ylim(-0.18, 0.78)
save(fig, "fig03_Q1逐维度R2.png",
     "图 3 50 个感官维度的折外 R²（随机 5 折为主结果，整风格留组为泛化压力测试）。"
     "酸度、酒精感、乳酸、苦度、酒体等可直接由化学量解释的维度表现最好；"
     "酯香花香、陈酒花味等依赖微量阈值效应的维度最差。")

# ============================================================ 图4 问题1 预测散点
oof = pd.read_csv(OUT / "Q1_连续评分预测_折外_D04尺度.csv")
fig, axes = plt.subplots(1, 4, figsize=(11.4, 3.1))
for ax, d, title in zip(axes, ["acidity", "bitternes", "alcohol", "stale_hops"],
                        ["酸度", "苦度", "酒精感", "陈酒花味"]):
    r2 = float(sel_rand.loc[sel_rand["target"] == L.Y2ID[d], "r2"].iloc[0])
    ax.scatter(Y[d].values, oof[d].values, s=8, alpha=0.55, color=C["blue"])
    lim = [min(Y[d].min(), oof[d].min()) - 0.1, max(Y[d].max(), oof[d].max()) + 0.1]
    ax.plot(lim, lim, color=C["red"], lw=1.1, ls="--")
    ax.set_xlabel("观测值")
    ax.set_ylabel("折外预测")
    ax.set_title(f"{title}（$R^2$={r2:.3f}）")
    ax.grid(alpha=0.2)
fig.suptitle("问题 1 折外预测与观测的一致性（虚线上方为高估）", fontsize=12, y=1.03)
save(fig, "fig04_Q1预测散点.png",
     "图 4 四个代表性感官维度的折外预测散点。酸度与酒精感接近对角线；"
     "陈酒花味的预测值域被明显压缩，说明该缺陷维度难以由现有化学测量稳定预测。")

# ============================================================ 图5 共形区间
conf = pd.read_csv(OUT / "Q1_共形区间指标.csv")
fig, axes = plt.subplots(1, 2, figsize=(11.2, 3.4), gridspec_kw={"width_ratios": [1.4, 1]})
ax = axes[0]
order_c = conf.sort_values("test_coverage")
ax.bar(range(len(order_c)), order_c["test_coverage"] * 100, color=C["teal"], alpha=0.85)
ax.axhline(90, color=C["red"], lw=1.2, ls="--", label="名义 90%")
ax.set_xticks(range(len(order_c)))
ax.set_xticklabels(order_c["target_name"], rotation=90, fontsize=7)
ax.set_ylabel("测试集覆盖率（%）")
ax.set_title("(a) 逐维度边际覆盖率（平均 90.1%）")
ax.legend()
ax.grid(axis="y", alpha=0.25)
ax = axes[1]
ax.hist(conf["interval_width"], bins=18, color=C["blue"], alpha=0.85)
ax.set_xlabel("90% 区间平均宽度（D04 单位）")
ax.set_ylabel("维度数")
ax.set_title("(b) 区间宽度分布（平均 1.54）")
ax.grid(axis="y", alpha=0.25)
fig.suptitle("问题 1 的逐维度共形区间：平均覆盖 90.1%，但 50 维同时覆盖仅 10%", fontsize=12, y=1.03)
save(fig, "fig05_Q1共形区间.png",
     "图 5 问题 1 共形预测区间。(a) 逐维度边际覆盖率平均 90.1%（各维度 64%–98%）；"
     "(b) 区间宽度分布。(c) 联合盒子在 50 个测试样本上的覆盖为 84%（42/50）。")

# ============================================================ 图6 评分协议敏感性
kdist = pd.read_csv(OUT / "Q1_陈酒花味Y38等级分布_协议A与B.csv")
fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.4), gridspec_kw={"width_ratios": [1, 1.25]})
ax = axes[0]
for i, (ds, proto, label, color) in enumerate([
        ("fitted", "A", "协议A（均值±标准差）", C["blue"]),
        ("fitted", "B", "协议B（训练分位切点）", C["orange"])]):
    sub = kdist[(kdist["dataset"] == ds) & (kdist["protocol"] == proto)].sort_values("grade")
    ax.bar(sub["grade"] + (i - 0.5) * 0.38, sub["count"], width=0.36, color=color, label=label)
ax.set_xlabel("陈酒花味（Y38）的 0–6 工作等级")
ax.set_ylabel("对象数（共 250）")
ax.set_title("(a) 同一连续预测，两种分级协议")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.25)

ax = axes[1]
sens = pd.DataFrame({"斜率 a": [0.5, 1.0, 1.5, 2.0],
                     "全部等级改变比例": [29.336, 0.0, 25.752, 46.264],
                     "Y38 达到等级2 的比例改变": [0.4, 0.0, 1.2, 6.4]})
ax.bar(sens["斜率 a"] - 0.11, sens["全部等级改变比例"], width=0.22, color=C["purple"],
       label="50 维全部等级改变")
ax.bar(sens["斜率 a"] + 0.11, sens["Y38 达到等级2 的比例改变"], width=0.22, color=C["red"],
       label="Y38 临界状态改变")
ax.set_xlabel("工作等级协议 A 的斜率 a（a=1 为基准）")
ax.set_ylabel("相对 a=1 的改变比例（%）")
ax.set_title("(b) 等级刻度选择的敏感性")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.25)
fig.suptitle("0–6 等级依赖分级协议：连续预测本身不变，等级口径变化显著", fontsize=12, y=1.03)
save(fig, "fig06_Q1评分协议.png",
     "图 6 评分协议的敏感性。(a) 同一批连续预测在协议 A 与协议 B 下得到不同的陈酒花味等级分布；"
     "(b) 协议 A 的斜率从 1 变为 0.5/1.5/2 时，全部等级改变 29.3%–46.3%，"
     "但“是否达到等级 2”的判定改变较小（0.4%–6.4%）。")

# ============================================================ 图7 共变网络
import networkx as nx
nodes = pd.read_csv(OUT / "Q2_网络节点与模块.csv")
edges = pd.read_csv(OUT / "Q2_网络边.csv")
G = nx.Graph()
for _, r in nodes.iterrows():
    G.add_node(r["feature"], compound=r["compound"], module=int(r["module"]),
               strength=float(r["strength"]), degree=int(r["degree"]), origin=r["origin"])
for _, r in edges.iterrows():
    G.add_edge(r["feature_a"], r["feature_b"], weight=float(r["weight"]),
               rho=float(r["signed_correlation"]))
comps = sorted(nx.connected_components(G), key=len, reverse=True)
core = comps[0]
H = G.subgraph(core).copy()
pos = nx.spring_layout(H, seed=20261026, k=0.5, iterations=400)
fig = plt.figure(figsize=(11.2, 4.6))
ax = fig.add_subplot(1, 2, 1)
node_colors = [ORIGIN_COLORS.get(H.nodes[n]["origin"], C["gray"]) for n in H.nodes]
max_strength = max(H.nodes[n]["strength"] for n in H.nodes)
node_sizes = [22 + 95 * (H.nodes[n]["strength"] / max_strength) for n in H.nodes]
nx.draw_networkx_edges(H, pos, ax=ax, alpha=0.22, edge_color=C["gray"], width=0.7)
nx.draw_networkx_nodes(H, pos, ax=ax, node_color=node_colors, node_size=node_sizes,
                       edgecolors="white", linewidths=0.6)
group_names = {"Hops": "酒花萜类", "Yeast": "酵母酯/醇", "Malt": "麦芽/呋喃"}
for origin, cn_name in group_names.items():
    members = [n for n in H.nodes if H.nodes[n]["origin"] == origin]
    if len(members) < 3:
        continue
    cx = np.mean([pos[n][0] for n in members]); cy = np.mean([pos[n][1] for n in members])
    ax.annotate(cn_name, xy=(cx, cy), xytext=(cx, cy + 0.16), fontsize=9.5, ha="center",
                color=C["dark"], fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=ORIGIN_COLORS[origin], alpha=0.85))
ax.set_title(f"(a) 最大连通分量（{len(core)} 个化合物、{H.number_of_edges()} 条边）\n节点颜色=化合物来源，节点大小=连接强度")
ax.axis("off")
from matplotlib.lines import Line2D
handles = [Line2D([0], [0], marker="o", color="w", markerfacecolor=col, markersize=8, label=k)
           for k, col in ORIGIN_COLORS.items() if k in set(nodes["origin"])]
ax.legend(handles=handles, loc="lower left", fontsize=7, framealpha=0.85)

ax2 = fig.add_subplot(1, 2, 2)
mods = pd.read_csv(OUT / "Q2_共变模块构成.csv")
mods = mods[mods["size"] >= 3].head(10)
origin_order = ["Hops", "Yeast", "Malt", "Spices", "Wild flora", "Others"]
bottom = np.zeros(len(mods))
for origin in origin_order:
    vals = []
    for _, r in mods.iterrows():
        d = dict(kv.split(":") for kv in str(r["origins"]).split(";") if ":" in kv)
        vals.append(float(d.get(origin, 0)))
    if sum(vals) == 0:
        continue
    ax2.barh(range(len(mods)), vals, left=bottom, color=ORIGIN_COLORS[origin], label=origin, height=0.62)
    bottom += np.array(vals)
ax2.set_yticks(range(len(mods)))
ax2.set_yticklabels([f"模块{int(r['module'])}（{int(r['size'])}）" for _, r in mods.iterrows()], fontsize=8)
ax2.invert_yaxis()
ax2.set_xlabel("模块内化合物数（按来源分组）")
ax2.set_title("(b) 主要共变模块的来源构成")
ax2.legend(fontsize=7, ncol=2, loc="lower right")
ax2.grid(axis="x", alpha=0.25)
fig.suptitle(f"图 7  化学特征共变网络：{len(nodes)} 个节点、{len(edges)} 条边（|ρ|≥0.6），模块度 Q=0.745", fontsize=12, y=1.03)
save(fig, "fig07_Q2共变网络.png",
     "图 7 共变网络与模块。(a) 最大连通分量按来源着色：酒花萜类、酵母酯/醇、麦芽来源化合物"
     "各自聚成模块；(b) 主要模块的来源构成，大型模块以酒花萜类和酵母代谢物为主。")

# ============================================================ 图8 Top-3 稳定性
top3 = pd.read_csv(OUT / "Q2_Top3关键化合物_汇总.csv")
dims20 = ["A_malt_all", "A_malt_bread", "A_hops_all", "A_hops_citrus", "A_hops_tropical",
          "A_esters_all", "A_esters_isoaa", "A_esters_flower", "F_malt_all", "F_hops_all",
          "F_esters_all", "F_esters_ethanol", "acidity", "bitternes", "sweetness",
          "X4vg", "diacetyl", "dms", "stale_hops", "t2n", "alcohol", "body"]
dims20 = [d for d in dims20 if d in set(top3["target"])]
if len(dims20) < 20:
    dims20 = (list(top3.sort_values("target")["target"])[:10] +
              list(top3.sort_values("target")["target"])[-10:])

def draw_top3(sub, fname, figsize, fs_name, fs_val):
    mat = np.full((len(sub), 3), np.nan)
    labels_mat = [[""] * 3 for _ in range(len(sub))]
    for i, (_, r) in enumerate(sub.iterrows()):
        for k in range(3):
            mat[i, k] = r[f"top{k+1}_freq"]
            name = str(r[f"top{k+1}_compound"])
            labels_mat[i][k] = name if len(name) <= 20 else name[:18] + "…"
    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(mat, aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["第 1 名", "第 2 名", "第 3 名"], fontsize=fs_name)
    ax.set_yticks(range(len(sub)))
    ax.set_yticklabels([f"{r['target_name']}" for _, r in sub.iterrows()], fontsize=fs_name)
    for i in range(len(sub)):
        for k in range(3):
            v = mat[i, k]
            ax.text(k, i, f"{labels_mat[i][k]}\n{v:.2f}", ha="center", va="center",
                    fontsize=fs_val, color="white" if v > 0.55 else "black")
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("bootstrap 入选频率", fontsize=fs_name)
    save(fig, fname, "")

sub20 = top3[top3["target"].isin(dims20)].copy()
sub20["order"] = sub20["target"].map({t: i for i, t in enumerate(dims20)})
sub20 = sub20.sort_values("order")
draw_top3(sub20, "fig08_Q2_top3.png", (9.6, 5.8), 8.2, 6.6)
draw_top3(top3.sort_values("target"), "fig08b_Q2_top3_full.png", (9.6, 10.0), 7.6, 5.8)
MANIFEST[-1]["caption"] = "图 B-1  50 个感官维度的 Top-3 关键化合物与 bootstrap 入选频率（完整版）"

# ============================================================ 图9 问题3 生成模型比较
held = pd.read_csv(OUT / "Q3_生成模型留出比较_结构路线.csv")
name_map = {"global_lw": "全局高斯 copula", "conditional_lw": "条件高斯 copula",
            "conditional_posterior_predictive": "条件高斯+方差修正",
            "empirical_marginal_copula": "类条件经验边际 copula（最终）"}
held["方法"] = held["method"].map(name_map)
fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.4))
metrics = [("energy_v", "能量距离（越低越好）", C["blue"]),
           ("mmd2_v", "MMD²（越低越好）", C["orange"]),
           ("gaussian_rank_space_nll", "秩空间高斯 NLL（越低越好）", C["green"])]
for ax, (col, title, color) in zip(axes, metrics):
    d = held.dropna(subset=[col]).sort_values(col)
    ax.barh(range(len(d)), d[col], color=color, alpha=0.85)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels(d["方法"], fontsize=8)
    ax.invert_yaxis()
    ax.set_title(title, fontsize=10)
    ax.grid(axis="x", alpha=0.25)
    for i, v in enumerate(d[col]):
        ax.text(v, i, f" {v:.3f}", va="center", fontsize=7.5)
fig.suptitle("问题 3 生成模型的留出比较（5 次按风格分层 70%/30% 划分）", fontsize=12, y=1.03)
save(fig, "fig09_Q3模型比较.png",
     "图 9 生成模型留出比较。类条件经验边际 copula 在能量距离与 MMD 上最好；"
     "含离散原子的分布无法直接计算连续高斯 NLL，故 NLL 栏留空。")

# ============================================================ 图10 生成画像 vs 真实画像
port = pd.read_csv(OUT / "Q3_三类生成样本平均感官画像.csv")
real = pd.read_csv(OUT / "Q3_真实风格平均感官画像_D04尺度.csv")
dims10 = ["alcohol", "body", "overall", "A_esters_all", "A_hops_all", "A_malt_all",
          "bitternes", "sweetness", "acidity", "lactic", "acetic", "X4vg",
          "diacetyl", "dms", "stale_hops", "t2n"]
disp10 = [L.TARGET_INFO[L.Y2ID[d]]["display"] for d in dims10]
M = np.zeros((len(dims10), 6))
for j, sty in enumerate(["Tripel", "Kriek", "Lambic"]):
    M[:, j * 2] = port.loc[port["style"] == sty, dims10].values[0]
    M[:, j * 2 + 1] = real.loc[real["style"] == sty, dims10].values[0]
fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.2), gridspec_kw={"width_ratios": [1.35, 1]})
ax = axes[0]
im = ax.imshow(M, aspect="auto", cmap="RdBu_r", norm=TwoSlopeNorm(vcenter=0, vmin=-2, vmax=2))
ax.set_xticks(range(6))
ax.set_xticklabels(["生成\nTripel", "真实\nTripel", "生成\nKriek", "真实\nKriek",
                    "生成\nLambic", "真实\nLambic"], fontsize=8)
ax.set_yticks(range(len(dims10)))
ax.set_yticklabels(disp10, fontsize=8)
for i in range(M.shape[0]):
    for j in range(6):
        ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=6.4,
                color="white" if abs(M[i, j]) > 1.2 else "black")
fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="D04 单位（风格均值）")
ax.set_title("(a) 三个风格的关键感官维度：生成 vs 真实")

ax = axes[1]
all_gen = port.set_index("style")
cols_y = list(Y.columns)
for sty, col, marker in [("Tripel", C["blue"], "o"), ("Kriek", C["orange"], "s"), ("Lambic", C["green"], "^")]:
    xg = real.loc[real["style"] == sty, cols_y].values[0]
    yg = all_gen.loc[sty, cols_y].values
    r = np.corrcoef(xg, yg)[0, 1]
    ax.scatter(xg, yg, s=22, color=col, marker=marker, alpha=0.8, label=f"{sty}（r={r:.2f}）")
lim = [-2.2, 2.4]
ax.plot(lim, lim, color=C["gray"], ls="--", lw=1)
ax.set_xlim(*lim); ax.set_ylim(*lim)
ax.set_xlabel("真实风格平均评分（D04）")
ax.set_ylabel("生成样本平均评分（D04）")
ax.set_title("(b) 50 个维度的生成—真实对应")
ax.legend(fontsize=8, loc="upper left")
ax.grid(alpha=0.25)
fig.suptitle("生成样本的感官画像与真实风格画像对比", fontsize=12, y=1.03)
save(fig, "fig10_Q3感官画像.png",
     "图 10 生成样本的感官画像。(a) 16 个关键维度的风格均值：Tripel 呈现高酒精、高酯香、低酸；"
     "Kriek/Lambic 呈现高酸、高乳酸/乙酸、低苦；生成值与真实风格均值总体同向但幅度更保守。"
     "(b) 50 维散点，三个风格的生成—真实相关系数分别为 0.88、0.96、0.97。")

# ============================================================ 图11 跨风格迁移
crit = pd.read_csv(OUT / "Q3_迁移_缺陷化合物对照.csv")
crit4 = crit[crit["criterion"].isin(["V004", "V039", "V021", "V109"])].copy()
crit4["name"] = crit4["criterion"].map({"V004": "DMS", "V039": "双乙酰",
                                        "V021": "4-VG", "V109": "反-2-壬烯醛"})
kcomp = pd.read_csv(OUT / "Q3_迁移_陈酒花味Y38安全对照.csv")
guard = kcomp[kcomp["branch"] == "observed_guard_original_D01_model_source"]
prob = pd.read_csv(OUT / "补充_Q3_迁移前后Tripel判别概率.csv")

fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.7), gridspec_kw={"width_ratios": [1.1, 1, 1], "wspace": 0.34})
ax = axes[0]
piv = crit4.pivot(index="source_object", columns="name", values="after_ratio")
piv = piv[["DMS", "双乙酰", "4-VG", "反-2-壬烯醛"]]
from matplotlib.colors import LogNorm
im = ax.imshow(np.maximum(piv.values, 1e-3), aspect="auto", cmap="YlOrRd",
               norm=LogNorm(vmin=1e-3, vmax=3))
ax.set_xticks(range(4)); ax.set_xticklabels(piv.columns, fontsize=8)
ax.set_yticks(range(len(piv))); ax.set_yticklabels(piv.index, fontsize=7)
for i in range(piv.shape[0]):
    for j in range(4):
        v = piv.values[i, j]
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.8,
                color="white" if v > 0.5 else "black")
cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.10)
cb.set_label("阈值倍数", fontsize=8)
ax.set_title("(a) 四项缺陷化合物的阈值倍数\n（迁移后=迁移前，未恶化）", fontsize=10)

ax = axes[1]
i_ord = np.arange(len(guard))
ax.axhline(0, color=C["gray"], lw=0.8, ls=":")
ax.bar(i_ord, guard["continuous_delta_after_minus_before"], color=C["teal"], alpha=0.85)
ax.set_xticks(i_ord)
ax.set_xticklabels(guard["source_object"], rotation=90, fontsize=7)
ax.set_xlabel("源对象（Pils/Lager）")
ax.set_ylabel("迁移后−迁移前")
ax.set_title("(b) 陈酒花味 Y38 连续预测变化（全部 ≤ 0）", fontsize=10)
ax.grid(axis="y", alpha=0.25)

ax = axes[2]
xpos = np.arange(len(prob))
ax.bar(xpos - 0.2, prob["P_Tripel_before"], width=0.4, color=C["gray"], label="迁移前")
ax.bar(xpos + 0.2, prob["P_Tripel_after"], width=0.4, color=C["blue"], label="迁移后")
ax.set_xticks(xpos)
ax.set_xticklabels(prob["source_object"], rotation=90, fontsize=7)
ax.set_xlabel("源对象（Pils/Lager）")
ax.set_ylabel("判别为 Tripel 的概率")
ax.set_title("(c) 监督分类器的风格判定", fontsize=10)
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.25)
fig.suptitle("跨风格迁移（Pils/Lager → Tripel）：缺陷约束、感官安全与风格判定", fontsize=12, y=1.03)
save(fig, "fig11_Q3迁移.png",
     "图 11 跨风格迁移。(a) 四项缺陷化合物的原生值相对阈值倍数：迁移后保持源对象的数值，"
     "未出现恶化（红=超过阈值）；(b) 陈酒花味 Y38 连续预测逐对象下降；"
     "(c) 独立监督分类器判为 Tripel 的概率由平均 2.4% 升至 39.1%，10/11 个对象上升。")

# ============================================================ 图12 零原子修复
zr = pd.read_csv(R / "question3_structure_zero_negative_rates.csv")
zr["feature_en"] = zr["feature"].map(lambda v: L.FEATURE_INFO[v]["pretty"])
sel_z = zr[zr["feature"].isin(["V002", "V021", "V026", "V036"])].copy()
fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.6), gridspec_kw={"width_ratios": [1.05, 1]})
ax = axes[0]
feat_colors = {"V002": C["blue"], "V021": C["orange"], "V026": C["green"], "V036": C["red"]}
pts = []
for feat, col in feat_colors.items():
    for sty in ["R20", "R12", "R13"]:
        rr = sel_z[(sel_z["regime"] == sty) & (sel_z["feature"] == feat) & (sel_z["sample"] == "real_reference")]
        gg = sel_z[(sel_z["regime"] == sty) & (sel_z["feature"] == feat) & (sel_z["sample"] == "generated")]
        if len(rr) and len(gg):
            pts.append((float(rr["zero_rate_among_observed"].iloc[0]),
                        float(gg["zero_rate_among_observed"].iloc[0]), feat, sty, col))
for x, y, feat, sty, col in pts:
    ax.scatter(x, y, s=42, color=col, alpha=0.85,
               label=L.FEATURE_INFO[feat]["pretty"] if sty == "R20" else None)
ax.plot([0, 1], [0, 1], color=C["gray"], ls="--", lw=1, label="生成=真实")
ax.set_xlabel("真实类内零值比例")
ax.set_ylabel("生成样本零值比例")
ax.set_title("(a) 四个含零原子特征的零率：生成 vs 真实")
ax.legend(fontsize=7.5)
ax.grid(alpha=0.25)

ax = axes[1]
gen4 = pd.read_csv(OUT / "Q3_生成化合物谱_三类合并.csv")
v21 = gen4["X4VG"].values
ax.hist(v21, bins=np.linspace(v21.min(), -1.7, 40), color=C["purple"], alpha=0.8)
ax.axvline(-2.013157381, color=C["red"], lw=1.4, ls="--",
           label="非正原生值的对数下限 −2.0132")
ax.set_xlabel("4-VG 的 1.csv 记录值")
ax.set_ylabel("样本数")
ax.set_title("(b) 4-VG 的零原子：生成值集中在有限下限")
ax.legend(fontsize=7.5)
ax.grid(axis="y", alpha=0.25)
fig.suptitle("生成模型对“零/负值原子”的修复", fontsize=12, y=1.03)
save(fig, "fig12_Q3零原子.png",
     "图 12 零原子修复。直接用总体分位数时生成样本的零比例严重失真；"
     "改用类条件收缩经验分布后，生成样本的零值与真实类内零值接近，"
     "4-VG 等非正原生值仍集中在记录尺度下限 −2.0132。")

# ============================================================ 图13 缺失稳健性
miss = pd.read_csv(OUT / "补充_Q1_缺失稳健性.csv")
med = miss[miss["method"].str.startswith("中位数")]
fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.4))
ax = axes[0]
ax.plot(med["extra_missing_rate"] * 100, med["mae_mean"], marker="o", color=C["blue"], lw=1.6)
for rate, v in zip(med["extra_missing_rate"] * 100, med["mae_mean"]):
    ax.annotate(f"{v:.3f}", (rate, v), textcoords="offset points", xytext=(0, 7), fontsize=8, ha="center")
ax.set_xlabel("额外随机缺失比例（%）")
ax.set_ylabel("50 维平均 MAE")
ax.set_title("(a) 额外缺失下的折外误差")
ax.grid(alpha=0.25)
ax = axes[1]
ax.plot(med["extra_missing_rate"] * 100, med["r2_mean"], marker="s", color=C["orange"], lw=1.6)
for rate, v in zip(med["extra_missing_rate"] * 100, med["r2_mean"]):
    ax.annotate(f"{v:.3f}", (rate, v), textcoords="offset points", xytext=(0, 7), fontsize=8, ha="center")
ax.set_xlabel("额外随机缺失比例（%）")
ax.set_ylabel("50 维平均 $R^2$")
ax.set_title("(b) 额外缺失下的平均解释力")
ax.grid(alpha=0.25)
fig.suptitle("问题 1 对额外随机缺失的稳健性（PLS 主模型，同一 5 折划分）", fontsize=12, y=1.03)
save(fig, "fig13_Q1缺失稳健性.png",
     "图 13 额外随机缺失稳健性。在原始 73 个缺失单元格之外再随机挖空 10%/30%/50% 的观测值，"
     "平均 MAE 由 0.353 升至 0.356/0.364/0.377，平均 R² 由 0.180 降至 0.165/0.135/0.077，"
     "说明方法对缺失是渐进而非崩溃式退化。")

# ============================================================ 写入 manifest
(FIG / "_figure_manifest.json").write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
print("figures:", len(MANIFEST))
