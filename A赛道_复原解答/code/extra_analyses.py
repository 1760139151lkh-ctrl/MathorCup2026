# -*- coding: utf-8 -*-
"""补充分析（不属于脱敏版既有结果，由复原工作额外计算，均在原题数据上从零执行）：
1. 问题1：额外随机缺失（10%/30%/50%）下的折外稳健性；
2. 问题1：中位数填补 vs KNN 填补的对比；
3. 问题3：用可解释监督分类器检验生成样本与迁移样本的“风格保真度”；
4. 问题3：生成风格平均画像与真实风格平均画像的关键维度对照。
输出：results/补充_*.csv 与 figures 所需数据。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.impute import KNNImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels as L

sys.stdout.reconfigure(encoding="utf-8")
R = L.SAND_SOL / "results"
OUT = L.RESULTS

meta, X = L.read_orig_chem()
_, Y = L.read_orig_sensory()
X = X.copy()
Y = Y.copy()
folds = pd.read_csv(R / "question1_cv_folds.csv")
assert (folds["object"].values == meta["beer"].values).all()
fold_id = folds["random_outer_fold"].values

def fit_pls(Xtr, Ytr, ncomp=10):
    model = PLSRegression(n_components=ncomp, scale=False)
    model.fit(Xtr, Ytr)
    return model

def run_cv(mask_rate=0.0, imputer="median", seed=0, n_splits=5):
    rng = np.random.default_rng(seed)
    maes, r2s = [], []
    for k in range(1, n_splits + 1):
        te = fold_id == k
        tr = ~te
        Xtr_raw, Xte_raw = X.values[tr].copy(), X.values[te].copy()
        Ytr, Yte = Y.values[tr].copy(), Y.values[te].copy()
        # 额外随机缺失：只在原始非缺失格上挖空
        if mask_rate > 0:
            for arr in (Xtr_raw, Xte_raw):
                obs = ~np.isnan(arr)
                mask = (rng.random(arr.shape) < mask_rate) & obs
                arr[mask] = np.nan
        if imputer == "median":
            med = np.nanmedian(Xtr_raw, axis=0)
            med = np.where(np.isnan(med), 0.0, med)
            Xtr = np.where(np.isnan(Xtr_raw), med, Xtr_raw)
            Xte = np.where(np.isnan(Xte_raw), med, Xte_raw)
        else:
            imp = KNNImputer(n_neighbors=5, weights="distance")
            # KNNImputer 不接受全空列：记录全空列并用 0 占位，插补后再置 0
            allnan = np.all(np.isnan(Xtr_raw), axis=0)
            Xtr_in = Xtr_raw.copy(); Xtr_in[:, allnan] = 0.0
            Xte_in = Xte_raw.copy(); Xte_in[:, allnan] = 0.0
            imp.fit(Xtr_in)
            Xtr = imp.transform(Xtr_in); Xtr[:, allnan] = 0.0
            Xte = imp.transform(Xte_in); Xte[:, allnan] = 0.0
        lo = np.quantile(Xtr, 0.01, axis=0)
        hi = np.quantile(Xtr, 0.99, axis=0)
        Xtr = np.clip(Xtr, lo, hi)
        Xte = np.clip(Xte, lo, hi)
        mu = Xtr.mean(axis=0)
        sd = Xtr.std(axis=0, ddof=0)
        sd[sd == 0] = 1.0
        Xtr = (Xtr - mu) / sd
        Xte = (Xte - mu) / sd
        ymu = Ytr.mean(axis=0)
        ysd = Ytr.std(axis=0, ddof=0)
        ysd[ysd == 0] = 1.0
        model = fit_pls(Xtr, (Ytr - ymu) / ysd)
        pred = model.predict(Xte) * ysd + ymu
        mae = np.mean(np.abs(pred - Yte), axis=0)
        ss_res = np.sum((pred - Yte) ** 2, axis=0)
        ss_tot = np.sum((Yte - Yte.mean(axis=0)) ** 2, axis=0)
        r2 = 1 - ss_res / np.where(ss_tot == 0, np.nan, ss_tot)
        maes.append(mae)
        r2s.append(r2)
    maes = np.vstack(maes).mean(axis=0)
    r2s = np.nanmean(np.vstack(r2s), axis=0)
    return dict(mae_mean=float(maes.mean()), mae_median=float(np.median(maes)),
                r2_mean=float(np.mean(r2s)), r2_median=float(np.median(r2s)),
                n_r2_positive=int((r2s > 0).sum()))

rows = []
for rate in [0.0, 0.1, 0.3, 0.5]:
    res = run_cv(mask_rate=rate, imputer="median", seed=20261026 + int(rate * 100))
    res.update(method="中位数填补(训练折内)", extra_missing_rate=rate)
    rows.append(res)
for rate in [0.0, 0.3]:
    res = run_cv(mask_rate=rate, imputer="knn", seed=20261026 + int(rate * 100))
    res.update(method="KNN填补(k=5,训练折内)", extra_missing_rate=rate)
    rows.append(res)
missing_df = pd.DataFrame(rows)[["method", "extra_missing_rate", "mae_mean", "mae_median",
                                 "r2_mean", "r2_median", "n_r2_positive"]]
missing_df.to_csv(OUT / "补充_Q1_缺失稳健性.csv", index=False, encoding="utf-8-sig")
print(missing_df.round(4).to_string(index=False))

# ============================================================ 风格保真度
def make_classifier(pos_styles):
    y = meta["style"].isin(pos_styles).astype(int).values
    return y

def fit_prep(Xdf):
    """只用训练（真实）数据确定填补、缩尾与标准化参数。"""
    Xv = Xdf.values.astype(float)
    med = np.nanmedian(Xv, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    Xi = np.where(np.isnan(Xv), med, Xv)
    lo = np.quantile(Xi, 0.01, axis=0)
    hi = np.quantile(Xi, 0.99, axis=0)
    Xc = np.clip(Xi, lo, hi)
    mu = Xc.mean(axis=0)
    sd = Xc.std(axis=0, ddof=0)
    sd[sd == 0] = 1.0
    return dict(med=med, lo=lo, hi=hi, mu=mu, sd=sd)

def apply_prep(Xdf, P):
    Xv = Xdf.values.astype(float)
    Xv = np.where(np.isnan(Xv), P["med"], Xv)
    Xv = np.clip(Xv, P["lo"], P["hi"])
    return (Xv - P["mu"]) / P["sd"]

PREP = fit_prep(X)
Xz = apply_prep(X, PREP)
# 训练/评估用 5 折交叉验证 AUC（在原题 250 个真实样本上）
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=20261026)
fidelity_rows = []
models = {}
for style in ["Tripel", "Kriek", "Lambic"]:
    y = make_classifier([style])
    aucs = []
    for tr, te in skf.split(Xz, y):
        clf = LogisticRegression(max_iter=3000, C=0.1, class_weight="balanced")
        clf.fit(Xz[tr], y[tr])
        aucs.append(roc_auc_score(y[te], clf.predict_proba(Xz[te])[:, 1]))
    clf = LogisticRegression(max_iter=3000, C=0.1, class_weight="balanced")
    clf.fit(Xz, y)
    models[style] = clf
    fidelity_rows.append(dict(style=style, cv_auc_mean=float(np.mean(aucs)),
                              cv_auc_std=float(np.std(aucs)), n_positive=int(y.sum())))

# 对生成样本打分
gen = pd.read_csv(OUT / "Q3_生成化合物谱_三类合并.csv")
gen_z = apply_prep(gen[list(X.columns)], PREP)
for style in ["Tripel", "Kriek", "Lambic"]:
    p = models[style].predict_proba(gen_z)[:, 1]
    for true_style in ["Tripel", "Kriek", "Lambic"]:
        sub = gen["style"].values == true_style
        fidelity_rows.append(dict(style=f"生成{true_style}_被判为{style}", cv_auc_mean=float(p[sub].mean()),
                                  cv_auc_std=float(p[sub].std()), n_positive=int(sub.sum())))
fid = pd.DataFrame(fidelity_rows)
fid.to_csv(OUT / "补充_Q3_风格保真度.csv", index=False, encoding="utf-8-sig")
print(fid.round(4).to_string(index=False))

# 迁移前后的 Tripel 概率
before = pd.read_csv(OUT / "Q3_跨风格迁移_PilsLager到Tripel_迁移前.csv")
after = pd.read_csv(OUT / "Q3_跨风格迁移_PilsLager到Tripel_迁移后.csv")
feat = list(X.columns)
before_z = apply_prep(before[feat], PREP)
after_z = apply_prep(after[feat], PREP)
p_before = models["Tripel"].predict_proba(before_z)[:, 1]
p_after = models["Tripel"].predict_proba(after_z)[:, 1]
trans = pd.DataFrame(dict(source_object=before["source_object"],
                          P_Tripel_before=p_before, P_Tripel_after=p_after,
                          delta=p_after - p_before))
trans.to_csv(OUT / "补充_Q3_迁移前后Tripel判别概率.csv", index=False, encoding="utf-8-sig")
print(trans.round(4).to_string(index=False))

# ============================================================ 生成画像 vs 真实画像（关键维度）
portrait = pd.read_csv(OUT / "Q3_三类生成样本平均感官画像.csv")
real = pd.read_csv(OUT / "Q3_真实风格平均感官画像_D04尺度.csv")
key_dims = ["alcohol", "acidity", "lactic", "acetic", "X4vg", "diacetyl", "dms",
            "stale_hops", "t2n", "sweetness", "bitternes", "body", "overall",
            "A_esters_all", "A_hops_all", "A_malt_all", "F_esters_all"]
rows = []
for style in ["Tripel", "Kriek", "Lambic"]:
    for d in key_dims:
        rows.append(dict(style=style, dimension=d,
                         生成均值=float(portrait.loc[portrait["style"] == style, d].iloc[0]),
                         真实风格均值=float(real.loc[real["style"] == style, d].iloc[0])))
pd.DataFrame(rows).to_csv(OUT / "补充_Q3_生成与真实画像关键维度.csv", index=False, encoding="utf-8-sig")
print("补充分析完成")
