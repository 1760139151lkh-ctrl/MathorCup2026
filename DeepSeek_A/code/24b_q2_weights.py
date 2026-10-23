# -*- coding: utf-8 -*-
"""24b_q2_weights.py —— 问题 2 的秩聚合权重方案对比实验（只用于方法选择）"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import networkx as nx
from sklearn.linear_model import MultiTaskLassoCV, MultiTaskLasso
from sklearn.ensemble import ExtraTreesRegressor
from scipy.stats import rankdata

chem = pd.read_csv(os.path.join(DP, 'chem_features.csv'), encoding='utf-8-sig')
sens = pd.read_csv(os.path.join(DP, 'sensory_z.csv'), encoding='utf-8-sig')
meta = pd.read_csv(os.path.join(DP, 'feature_meta2.csv'), encoding='utf-8-sig').set_index('feature')
C_all = chem_cols(chem); S = sens_cols(sens)
EXCLUDE = {'pH', 'color.EBC.', 'protein.g.L.', 'kcalperc', 'CO2.PSI.', 'unfermentables',
           'betaglucan.mg.L.', 'iron', 'GFS', 'aroma_hops_sum', 'esters_sum', 'acids_sum',
           'sulfur_sum'}
CAND = [c for c in C_all if c not in EXCLUDE]
icand = np.array([C_all.index(c) for c in CAND])
X = chem[CAND].values.astype(float); Y = sens[S].values.astype(float)
Rdf = pd.read_csv(os.path.join(DP, 'chem_corr_2csv.csv'), index_col=0)
R = Rdf.values.astype(float)[np.ix_(icand, icand)]
chem_name = {c: str(nm) for c, nm in zip(C_all, Rdf.index)}
origin = meta['origin'].to_dict()

THR = 0.5
G = nx.Graph(); G.add_nodes_from(CAND)
iu = np.triu_indices(len(CAND), 1); mask = np.abs(R[iu]) >= THR
for i, j, w in zip(iu[0][mask], iu[1][mask], R[iu][mask]):
    G.add_edge(CAND[i], CAND[j], weight=float(w))
comms = sorted(nx.community.louvain_communities(G, weight='weight', seed=42), key=len, reverse=True)
strength = dict(G.degree(weight='weight'))
MODULES = [np.array([CAND.index(c) for c in cm]) for cm in comms if len(cm) >= 5]

Xr = np.apply_along_axis(rankdata, 0, X); Yr = np.apply_along_axis(rankdata, 0, Y)
Xr = (Xr - Xr.mean(0)) / Xr.std(0); Yr = (Yr - Yr.mean(0)) / Yr.std(0)
M1 = np.abs(Xr.T @ Yr) / len(X)

mtl = MultiTaskLassoCV(alphas=np.logspace(-4, 0, 25), cv=3, max_iter=8000).fit(X, Y)
alpha_best = float(mtl.alpha_)
M2 = np.abs(MultiTaskLasso(alpha=alpha_best, max_iter=8000).fit(X, Y).coef_.T)

W = np.abs(R) ** 2; np.fill_diagonal(W, 0); W = W / (W.sum(1, keepdims=True) + 1e-12)
seed_pr = np.maximum(M1 - np.quantile(M1, 0.6, axis=0, keepdims=True), 0) ** 2
M4 = np.zeros_like(M1)
for j in range(len(S)):
    s = seed_pr[:, j]; s = s / (s.sum() + 1e-12); p = s.copy()
    for _ in range(40):
        p = 0.75 * (W @ p) + 0.25 * s
    M4[:, j] = p

M3 = np.zeros_like(M1)
for j in range(len(S)):
    et = ExtraTreesRegressor(n_estimators=300, max_features=0.4, random_state=0, n_jobs=1)
    et.fit(X, Y[:, j]); M3[:, j] = et.feature_importances_

# M5
M5 = np.zeros_like(M1)
eig = []
for idx in MODULES:
    Xm = X[:, idx] - X[:, idx].mean(0)
    u, s_, vt = np.linalg.svd(Xm, full_matrices=False)
    eig.append(u[:, 0] * s_[0])
eig = np.array(eig)
er = np.apply_along_axis(rankdata, 1, eig)
er = (er - er.mean(1, keepdims=True)) / (er.std(1, keepdims=True) + 1e-12)
rmod = np.abs(er @ Yr) / len(X)
for j in range(len(S)):
    cutoff = np.quantile(rmod[:, j], 0.75)
    active = np.where(rmod[:, j] >= max(cutoff, 0.15))[0]
    if len(active) == 0:
        active = np.array([int(np.argmax(rmod[:, j]))])
    for a in active:
        idx = MODULES[a]
        cen = np.array([strength.get(CAND[i], 0) for i in idx], float)
        cen = cen / (cen.max() + 1e-12)
        M5[idx, j] = M1[idx, j] * (0.5 + 0.5 * cen)
log('方法矩阵准备完成')

MARK = {
    'bitternes': ['bitterness'], 'A_hops_citrus': ['limonene', 'citronellol', 'geraniol'],
    'A_esters_ethac': ['ethyl_acetate'], 'A_esters_isoaa': ['isopentyl_acetate'],
    'X4vg': ['X4VG'], 'clove': ['X4VG', 'eugenol'], 'dms': ['DMS'], 'diacetyl': ['X2.3.butanedione'],
    'lactic': ['lactic_acid.mg.L.'], 'acetic': ['acetic_acid.g.L.'], 'alcohol': ['ethanol..v.v.'],
    'body': ['glycerol', 'ethanol..v.v.'], 'orange': ['limonene'], 'coriander': ['linalool', 'limonene'],
    'A_hops_all': ['linalool', 'geraniol', 'citronellol', 'X1.alpha.terpineol', 'beta.humulene'],
    'A_esters_fruity': ['ethyl_hexanoate', 'ethyl_octanoate', 'ethyl.butyrate'],
    'A_malt_all': ['furfural', 'X3.methylbutanal', 'methylpyrazine', 'X2.furanmethanol'],
}
SCREEN_K = 25


def screened_agg(weights):
    methods = {'M1': M1, 'M2': M2, 'M3': M3, 'M4': M4, 'M5': M5}
    out = np.zeros_like(M1)
    mask = np.zeros(M1.shape, bool)
    for j in range(M1.shape[1]):
        mask[np.argsort(-M1[:, j])[:SCREEN_K], j] = True
    tot = sum(weights.values())
    for k, w in weights.items():
        m = methods[k]
        for j in range(m.shape[1]):
            vals = m[:, j].copy(); vals[~mask[:, j]] = -1e12
            out[:, j] += w * rankdata(-vals, method='average')
    return out / tot


schemes = {
    'equal': {'M1': 1, 'M2': 1, 'M3': 1, 'M4': 1, 'M5': 1},
    'M1x2': {'M1': 2, 'M2': 1, 'M3': 1, 'M4': 1, 'M5': 1},
    'M1x3': {'M1': 3, 'M2': 1, 'M3': 1, 'M4': 1, 'M5': 1},
    'asso': {'M1': 2, 'M2': 1, 'M3': 0.5, 'M4': 0.5, 'M5': 1},
    'M1M5': {'M1': 2, 'M5': 1},
    'noM3': {'M1': 2, 'M2': 1, 'M4': 1, 'M5': 1},
    'M1only': {'M1': 1},
}
for name, wts in schemes.items():
    agg = screened_agg(wts)
    top3 = np.argsort(agg, axis=0)[:3, :]
    hits = 0; hits10 = 0; tot = 0
    txt = []
    for j, c in enumerate(S):
        if c not in MARK:
            continue
        tot += 1
        order = np.argsort(agg[:, j])
        ranks = [int(np.where(order == CAND.index(m))[0][0]) for m in MARK[c] if m in CAND]
        r = min(ranks)
        hits += r < 3; hits10 += r < 10
        if c in ('bitternes', 'A_hops_all', 'A_hops_citrus', 'A_esters_fruity', 'A_esters_ethac',
                 'X4vg', 'clove', 'dms', 'diacetyl', 'alcohol', 'body', 'A_malt_all'):
            txt.append((c, [chem_name[CAND[t]] for t in top3[:, j]], r))
    log('%-8s  marker@3=%2d/%d  marker@10=%2d/%d' % (name, hits, tot, hits10, tot))
    for c, t, r in txt:
        log('     %-16s %s  (marker rank %d)' % (c, t, r))

# 保存各方法矩阵供主脚本参考
np.savez(os.path.join(DP, 'q2_methods.npz'), M1=M1, M2=M2, M3=M3, M4=M4, M5=M5,
         cand=np.array(CAND), sens=np.array(S))
log('done')
