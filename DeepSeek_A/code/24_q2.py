# -*- coding: utf-8 -*-
"""24_q2.py —— 问题 2：化合物–风味分析
（共表达图 + 每个感官维度 Top-3 关键化合物 + 稳定性与化学合理性）

关键设定：
 * 候选特征限定为"化合物"：剔除 pH、色度、蛋白、热量、CO2、不可发酵糖、β-葡聚糖、
   铁、总糖及 4 个衍生加和列等非化合物/派生变量（共 13 个），保留异α-酸、乙醇、
   甘油、SO2、氨、乳酸、乙酸等真实化合物，最终 218 个候选化合物。
 * 四种重要性度量：M1 单变量 Spearman、M2 多任务 Lasso 稀疏系数、
   M3 逐维度极端随机树重要性、M4 共表达图个性化 PageRank 传播；Borda 秩聚合。
 * 稳定性：B=100 次 bootstrap 重采样下 Top-3 入选频率 + 4 种方法 Top-3 的 Jaccard。
 * 化学合理性：标志化合物命中率、来源一致性、阈值型非线性检验、Top-3 单独预测 R²。
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import networkx as nx
from sklearn.linear_model import MultiTaskLassoCV, MultiTaskLasso, RidgeCV
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import KFold
from scipy.stats import rankdata, hypergeom, mannwhitneyu
plt = setup_cn_font()
t0 = time.time()

chem = pd.read_csv(os.path.join(DP, 'chem_features.csv'), encoding='utf-8-sig')
sens = pd.read_csv(os.path.join(DP, 'sensory_z.csv'), encoding='utf-8-sig')
meta = pd.read_csv(os.path.join(DP, 'feature_meta2.csv'), encoding='utf-8-sig').set_index('feature')
C_all = chem_cols(chem)
S = sens_cols(sens)

# ---- 化合物候选集 ----
EXCLUDE = {'pH', 'color.EBC.', 'protein.g.L.', 'kcalperc', 'CO2.PSI.', 'unfermentables',
           'betaglucan.mg.L.', 'iron', 'GFS', 'aroma_hops_sum', 'esters_sum', 'acids_sum',
           'sulfur_sum'}
CAND = [c for c in C_all if c not in EXCLUDE]
icand = np.array([C_all.index(c) for c in CAND])
log('全部特征 %d，剔除非化合物/派生变量 %d，候选化合物 %d'
    % (len(C_all), len(C_all) - len(CAND), len(CAND)))

X = chem[CAND].values.astype(float)
Y = sens[S].values.astype(float)
Rdf = pd.read_csv(os.path.join(DP, 'chem_corr_2csv.csv'), index_col=0)
R_all = Rdf.values.astype(float)
R = R_all[np.ix_(icand, icand)]
assert R.shape == (len(CAND), len(CAND))

# 化学名称与来源
corr2 = Rdf
name_all = [str(nm) for nm in corr2.index]
chem_name = {c: name_all[i] for c, i in zip(C_all, range(len(C_all)))}
origin = meta['origin'].to_dict()
unit = meta['unit'].to_dict()

# ---------------- 1. 共表达图与社区 ----------------
THR = 0.5
G = nx.Graph(); G.add_nodes_from(CAND)
iu = np.triu_indices(len(CAND), 1)
mask = np.abs(R[iu]) >= THR
for i, j, w in zip(iu[0][mask], iu[1][mask], R[iu][mask]):
    G.add_edge(CAND[i], CAND[j], weight=float(w))
comms = sorted(nx.community.louvain_communities(G, weight='weight', seed=42), key=len, reverse=True)
node_comm = {nd: k for k, cm in enumerate(comms) for nd in cm}
mod = nx.community.modularity(G, comms, weight='weight')
deg = dict(G.degree()); strength = dict(G.degree(weight='weight'))
_bc = nx.betweenness_centrality(G, weight=None)
log('共表达图：节点 %d，边 %d，密度 %.4f，平均度 %.1f，社区 %d，模块度 %.3f，正相关边 %.1f%%'
    % (G.number_of_nodes(), G.number_of_edges(), nx.density(G), np.mean(list(deg.values())),
       len(comms), mod, 100 * (R[iu][mask] > 0).mean()))

origin_arr = np.array([origin.get(c, 'Others') for c in CAND])
comm_rows = []
for k, cm in enumerate(comms):
    cm = list(cm)
    row = {'community': k, 'size': len(cm),
           'top_compounds': '; '.join(sorted(cm, key=lambda x: -strength[x])[:6])}
    for o in ['Hops', 'Yeast', 'Malt', 'Spices', 'Wild flora', 'Others']:
        n_o = int((origin_arr == o).sum()); k_o = int(sum(origin.get(c, 'Others') == o for c in cm))
        if k_o > 0 and len(cm) < len(CAND):
            row['enrich_p_' + o] = float(hypergeom.sf(k_o - 1, len(CAND), n_o, len(cm)))
    comm_rows.append(row)
comm_df = pd.DataFrame(comm_rows)
comm_df.to_csv(os.path.join(RES, 'Q2_communities.csv'), index=False, encoding='utf-8-sig')
log('主要社区（按规模）：')
log(comm_df[['community', 'size', 'top_compounds']].head(12).to_string(index=False))

nodes = pd.DataFrame({'compound': CAND})
nodes['name'] = nodes['compound'].map(chem_name)
nodes['origin'] = nodes['compound'].map(lambda c: origin.get(c, 'Others'))
nodes['community'] = nodes['compound'].map(node_comm)
nodes['degree'] = nodes['compound'].map(deg)
nodes['strength'] = nodes['compound'].map(strength)
nodes['betweenness'] = nodes['compound'].map(_bc)
nodes = nodes.sort_values('strength', ascending=False)
nodes.to_csv(os.path.join(RES, 'Q2_graph_nodes.csv'), index=False, encoding='utf-8-sig')

# ---------------- 2. 四种方法 ----------------
Wgraph = np.abs(R) ** 2
np.fill_diagonal(Wgraph, 0.0)
Wgraph = Wgraph / (Wgraph.sum(axis=1, keepdims=True) + 1e-12)


def spearman_scores(Xb, Yb):
    Xr = np.apply_along_axis(rankdata, 0, Xb); Yr = np.apply_along_axis(rankdata, 0, Yb)
    Xr = (Xr - Xr.mean(0)) / (Xr.std(0) + 1e-12); Yr = (Yr - Yr.mean(0)) / (Yr.std(0) + 1e-12)
    return np.abs(Xr.T @ Yr) / Xb.shape[0]


def pagerank_scores(seed_mat, alpha=0.75, n_iter=40):
    out = np.zeros_like(seed_mat)
    for j in range(seed_mat.shape[1]):
        s = seed_mat[:, j]
        if s.sum() <= 0:
            continue
        s = s / s.sum()
        p = s.copy()
        for _ in range(n_iter):
            p = alpha * (Wgraph @ p) + (1 - alpha) * s
        out[:, j] = p
    return out


def all_methods(Xb, Yb):
    m1 = spearman_scores(Xb, Yb)
    m2 = np.abs(MultiTaskLasso(alpha=alpha_best, max_iter=8000).fit(Xb, Yb).coef_.T)
    seeds = np.maximum(m1 - np.quantile(m1, 0.6, axis=0, keepdims=True), 0) ** 2
    m4 = pagerank_scores(seeds)
    m5 = module_eigengene_scores(Xb, Yb, m1)
    return {'M1-Spearman': m1, 'M2-MultiTaskLasso': m2, 'M4-GraphPageRank': m4,
            'M5-ModuleEigengene': m5}


# M5：WGCNA 式"模块-性状"关联 + 模块内枢纽排序
MODULES = [np.array([CAND.index(c) for c in cm]) for cm in comms if len(cm) >= 5]
log('参与模块分析的共表达模块数：%d' % len(MODULES))


def module_eigengene_scores(Xb, Yb, m1):
    n = Xb.shape[0]
    out = np.zeros((len(CAND), Yb.shape[1]))
    # 各模块第一主成分（模块特征基因）
    eig = []
    for idx in MODULES:
        Xm = Xb[:, idx]
        Xm = Xm - Xm.mean(0)
        try:
            u, s, vt = np.linalg.svd(Xm, full_matrices=False)
            e = u[:, 0] * s[0]
        except np.linalg.LinAlgError:
            e = Xm[:, 0]
        eig.append(e)
    eig = np.array(eig)                              # n_module × n
    # 模块与性状的 Spearman 相关
    er = np.apply_along_axis(rankdata, 1, eig)
    yr = np.apply_along_axis(rankdata, 0, Yb)
    er = (er - er.mean(1, keepdims=True)) / (er.std(1, keepdims=True) + 1e-12)
    yr = (yr - yr.mean(0)) / (yr.std(0) + 1e-12)
    rmod = np.abs(er @ yr) / n                        # n_module × n_dim
    for j in range(Yb.shape[1]):
        rj = rmod[:, j]
        if len(rj) == 0:
            continue
        cutoff = np.quantile(rj, 0.75)               # 取关联最强的前 25% 模块
        active = np.where(rj >= max(cutoff, 0.15))[0]
        if len(active) == 0:
            active = np.array([int(np.argmax(rj))])
        for a in active:
            idx = MODULES[a]
            centrality = np.array([strength.get(CAND[i], 0) for i in idx], dtype=float)
            centrality = centrality / (centrality.max() + 1e-12)
            out[idx, j] = m1[idx, j] * (0.5 + 0.5 * centrality)
    return out


SCREEN_K = 25


def screen_mask(m1):
    """单变量相关初筛：每个维度保留 |ρ| 最强的 SCREEN_K 个化合物。"""
    mask = np.zeros_like(m1, dtype=bool)
    for j in range(m1.shape[1]):
        mask[np.argsort(-m1[:, j])[:SCREEN_K], j] = True
    return mask


METHOD_W = {'M1-Spearman': 2.0, 'M2-MultiTaskLasso': 1.0, 'M3-ExtraTrees': 1.0,
            'M4-GraphPageRank': 1.0, 'M5-ModuleEigengene': 1.0}


def aggregate(methods):
    """先单变量初筛，再对初筛内化合物做加权 Borda 秩聚合（数值越小越重要）。

    权重：单变量关联（M1）为 2，其余四种方法各为 1，以突出与感官维度最直接的
    关联证据，同时保留多方法共识的稳健性。
    """
    m1 = methods['M1-Spearman']
    mask = screen_mask(m1)
    n_comp = m1.shape[0]
    out = np.zeros((n_comp, m1.shape[1]))
    for k, m in methods.items():
        w = METHOD_W.get(k, 1.0)
        for j in range(m.shape[1]):
            vals = m[:, j].copy()
            vals[~mask[:, j]] = -1e12
            out[:, j] += w * rankdata(-vals, method='average')
    return out / sum(METHOD_W.get(k, 1.0) for k in methods)


mtl = MultiTaskLassoCV(alphas=np.logspace(-4, 0, 25), cv=3, max_iter=8000).fit(X, Y)
alpha_best = float(mtl.alpha_)
log('多任务 Lasso 最优 alpha = %.4f' % alpha_best)

full = all_methods(X, Y)
imp3 = np.zeros((len(CAND), len(S)))
for j in range(len(S)):
    et = ExtraTreesRegressor(n_estimators=300, max_features=0.4, min_samples_leaf=1,
                             random_state=0, n_jobs=1).fit(X, Y[:, j])
    imp3[:, j] = et.feature_importances_
full['M3-ExtraTrees'] = imp3
agg = aggregate({k: full[k] for k in ['M1-Spearman', 'M2-MultiTaskLasso', 'M3-ExtraTrees', 'M4-GraphPageRank', 'M5-ModuleEigengene']})
top3 = np.argsort(agg, axis=0)[:3, :]
log('全样本方法计算完成 %.1fs' % (time.time() - t0))

# ---------------- 3. Bootstrap 稳定性 ----------------
B = 100
rng = np.random.default_rng(2026)
freq = np.zeros((len(CAND), len(S)))
top3_boot = np.zeros((B, 3, len(S)), dtype=int)
for b in range(B):
    idx = rng.integers(0, len(X), len(X))
    ab = aggregate(all_methods(X[idx], Y[idx]))
    tb = np.argsort(ab, axis=0)[:3, :]
    top3_boot[b] = tb
    for r in range(3):
        for j in range(len(S)):
            freq[tb[r, j], j] += 1
freq /= B
log('bootstrap 完成 %.1fs' % (time.time() - t0))

method_names = ['M1-Spearman', 'M2-MultiTaskLasso', 'M3-ExtraTrees', 'M4-GraphPageRank', 'M5-ModuleEigengene']
method_top3 = {mn: np.argsort(-full[mn], axis=0)[:3, :] for mn in method_names}
jac_rows = []
for j in range(len(S)):
    sets = [set(method_top3[mn][:, j].tolist()) for mn in method_names]
    js = [len(sets[a] & sets[b]) / len(sets[a] | sets[b])
          for a in range(len(sets)) for b in range(a + 1, len(sets))]
    final_set = set(top3[:, j].tolist())
    jac_rows.append({'dim': S[j], 'dim_cn': SENS_CN[S[j]],
                     'Jaccard_methods_mean': float(np.mean(js)),
                     'Jaccard_final_vs_methods': float(np.mean(
                         [len(final_set & s) / len(final_set | s) for s in sets])),
                     'top3_bootstrap_freq_mean': float(np.mean([freq[c, j] for c in top3[:, j]]))})
jac_df = pd.DataFrame(jac_rows)
jac_df.to_csv(os.path.join(RES, 'Q2_stability_jaccard.csv'), index=False, encoding='utf-8-sig')
log('方法间 Jaccard 均值 %.3f；Top-3 bootstrap 入选频率均值 %.3f；最终 Top-3 平均频率 %.3f'
    % (jac_df['Jaccard_methods_mean'].mean(), jac_df['top3_bootstrap_freq_mean'].mean(),
       jac_df['Jaccard_final_vs_methods'].mean()))

# ---------------- 4. 化学合理性 ----------------
MARKERS = {
    'dms': ['DMS', 'DES', 'H2S', 'MeSH'],
    'diacetyl': ['X2.3.butanedione', 'X2.3.hexanedione'],
    'X4vg': ['X4VG', 'eugenol', 'X4.ethyl.guaiacol'],
    't2n': ['X.E..2.nonenal', 'X.E..2.4.decadienal', 'n.nonanal'],
    'lactic': ['lactic_acid.mg.L.', 'acetic_acid.g.L.'],
    'acetic': ['acetic_acid.g.L.', 'lactic_acid.mg.L.'],
    'barnyard': ['X4.ethyl.phenol', 'X4.ethyl.guaiacol', 'X4VG', 'E.nerolidol'],
    'metallic': ['iron', 'bitterness'],
    'bitternes': ['bitterness'],
    'sweetness': ['GFS', 'glycerol', 'kcalperc'],
    'acidity': ['lactic_acid.mg.L.', 'acetic_acid.g.L.', 'pH'],
    'alcohol': ['ethanol..v.v.', 'glycerol', 'isoamyl_alcohol', 'isobutanol'],
    'body': ['glycerol', 'ethanol..v.v.', 'protein.g.L.'],
    'co2': ['CO2.PSI.'],
    'orange': ['limonene', 'octyl_acetate', 'n.octanol', 'myrcene'],
    'coriander': ['linalool', 'geraniol', 'X1.alpha.terpineol', 'camphor', 'limonene'],
    'clove': ['X4VG', 'eugenol', 'X4.ethyl.guaiacol'],
    'A_malt_all': ['X3.methylbutanal', 'furfural', 'X2.furanmethanol', 'methylpyrazine',
                   'X5.methylfurfural', 'X2.6.dimethyl.pyrazine', 'X2.acetylpyrrole',
                   'X2.acetylfuran', 'isomaltol', 'vanillin', 'X2.ethyl.3.methylpyrazine'],
    'A_hops_all': ['linalool', 'geraniol', 'citronellol', 'X1.alpha.terpineol', 'beta.humulene',
                   'E.caryophyllene', 'limonene', 'terpinolene', 'alpha.humulene',
                   'humulene.epoxide.II', 'caryophyllene.oxide', 'methyl.geranate',
                   'beta.phellandrene', 'alpha.phellandrene'],
    'A_hops_citrus': ['limonene', 'citronellol', 'geraniol', 'X1.alpha.terpineol',
                      'methyl.geranate', 'beta.phellandrene'],
    'A_hops_tropical': ['ethyl.butyrate', 'ethyl.hex..3E..enoate', 'isopentyl.butanoate',
                        'ethyl.hexanoate', 'ethyl.octanoate', 'linalool'],
    'A_hops_noble': ['X3Z.hexenol', 'beta.humulene', 'X.E..beta.farnesene',
                     'X1.alpha.terpineol', 'humulene.epoxide.II', 'alpha.humulene'],
    'A_hops_woody': ['E.caryophyllene', 'beta.humulene', 'alpha.humulene', 'eugenol',
                     'caryophyllene.oxide', 'gamma.eudesmol', 'caryophyllene.alcohol'],
    'A_esters_isoaa': ['isopentyl_acetate'],
    'A_esters_ethac': ['ethyl_acetate'],
    'A_esters_flower': ['phenethyl_acetate', 'phenethyl_alcohol', 'linalool', 'geraniol',
                        'X.E..beta.damascenone'],
    'A_esters_fruity': ['ethyl_hexanoate', 'ethyl_octanoate', 'ethyl.butyrate', 'ethyl_decanoate',
                        'ethyl.isobutyrate', 'ethyl.propionate'],
}
MARKERS['A_esters_banana'] = MARKERS['A_esters_isoaa']
for base in ['malt_grain', 'malt_bread', 'malt_cara', 'malt_burn']:
    MARKERS['A_' + base] = MARKERS['A_malt_all']
for base in ['hops_citrus', 'hops_tropical', 'hops_noble', 'hops_woody']:
    MARKERS['F_' + base] = MARKERS['A_' + base]
MARKERS['A_esters_all'] = MARKERS['A_esters_fruity'] + MARKERS['A_esters_isoaa']
MARKERS['F_esters_all'] = MARKERS['A_esters_all']
for base in ['malt_grain', 'malt_bread', 'malt_cara', 'malt_burn']:
    MARKERS['F_' + base] = MARKERS['A_' + base]
for base in ['esters_isoaa', 'esters_ethac', 'esters_flower', 'esters_fruity']:
    MARKERS['F_' + base] = MARKERS['A_' + base]

EXPECTED_ORIGIN = {}
for c in S:
    if c.startswith(('A_malt', 'F_malt')):
        EXPECTED_ORIGIN[c] = {'Malt', 'Others'}
    elif c.startswith(('A_hops', 'F_hops')):
        EXPECTED_ORIGIN[c] = {'Hops', 'Others'}
    elif c.startswith(('A_esters', 'F_esters')):
        EXPECTED_ORIGIN[c] = {'Yeast', 'Others'}
    elif c in ('lactic', 'acetic', 'barnyard'):
        EXPECTED_ORIGIN[c] = {'Wild flora', 'Yeast', 'Others'}
    elif c in ('X4vg', 'clove', 'coriander', 'orange'):
        EXPECTED_ORIGIN[c] = {'Wild flora', 'Spices', 'Yeast', 'Hops', 'Others'}
    elif c in ('dms', 't2n', 'stale_hops'):
        EXPECTED_ORIGIN[c] = {'Malt', 'Hops', 'Others'}
    elif c == 'diacetyl':
        EXPECTED_ORIGIN[c] = {'Yeast', 'Others'}
    else:
        EXPECTED_ORIGIN[c] = None

top3_idx_all = [top3[:, j].tolist() for j in range(len(S))]
rows = []
for j, c in enumerate(S):
    t3 = top3[:, j]
    markers = MARKERS.get(c, [])
    rank_of_marker = min([int(np.where(np.argsort(agg[:, j]) == CAND.index(m))[0][0])
                          for m in markers if m in CAND] or [999])
    origin_set = {origin.get(CAND[t], 'Others') for t in t3}
    origin_ok = (EXPECTED_ORIGIN.get(c) is not None) and bool(origin_set & EXPECTED_ORIGIN[c])
    row = {'dim': c, 'dim_cn': SENS_CN[c], 'group': SENS_GROUP[c],
           'marker_best_rank': rank_of_marker,
           'marker_hit_top3': bool(rank_of_marker < 3),
           'marker_hit_top10': bool(rank_of_marker < 10),
           'origin_consistent': bool(origin_ok),
           'top3_bootstrap_freq_mean': float(np.mean([freq[t, j] for t in t3])),
           'Jaccard_methods_mean': float(jac_df.loc[j, 'Jaccard_methods_mean'])}
    for r in range(3):
        t = t3[r]
        row[f'Top{r+1}_compound'] = CAND[t]
        row[f'Top{r+1}_name'] = chem_name.get(CAND[t], CAND[t])
        row[f'Top{r+1}_origin'] = origin.get(CAND[t], 'Others')
        row[f'Top{r+1}_rho'] = float(full['M1-Spearman'][t, j])
        row[f'Top{r+1}_lasso'] = float(full['M2-MultiTaskLasso'][t, j])
        row[f'Top{r+1}_ETimp'] = float(imp3[t, j])
        row[f'Top{r+1}_pagerank'] = float(full['M4-GraphPageRank'][t, j])
        row[f'Top{r+1}_bootfreq'] = float(freq[t, j])
        row[f'Top{r+1}_community'] = int(node_comm.get(CAND[t], -1))
    rows.append(row)
top3_df = pd.DataFrame(rows)
# 附加：单变量关联最强（M1 第 1 名）化合物，便于对照说明
m1_top1 = np.argsort(-full['M1-Spearman'], axis=0)[0, :]
top3_df['M1_top1_compound'] = [CAND[i] for i in m1_top1]
top3_df['M1_top1_name'] = [chem_name.get(CAND[i], CAND[i]) for i in m1_top1]
top3_df['M1_top1_rho'] = [float(full['M1-Spearman'][m1_top1[j], j]) for j in range(len(S))]

# 阈值型非线性：对含已知阈值的化合物，比较"超阈值"前后的感官差异（Mann-Whitney U）
THR_DEF = {'DMS': ('dms', 17.25, 1), 'X2.3.butanedione': ('diacetyl', 0.29925, 0),
           'X4VG': ('X4vg', 0.206333, 0), 'X.E..2.nonenal': ('t2n', None, 0),
           'lactic_acid.mg.L.': ('lactic', 416.6667, 0), 'acetic_acid.g.L.': ('acetic', 0.14025, 0)}
thr_rows = []
for comp, (dim, thr, is_log) in THR_DEF.items():
    if comp not in CAND or dim not in S:
        continue
    vals = chem[comp].values.astype(float)
    conc = 10 ** vals if is_log else vals
    if thr is None:      # 无公开阈值，用 90% 分位作为参照
        thr = float(np.nanpercentile(conc, 90))
    med_hi = float(np.nanmedian(Y[conc > thr, S.index(dim)]))
    med_lo = float(np.nanmedian(Y[conc <= thr, S.index(dim)]))
    try:
        p = float(mannwhitneyu(Y[conc > thr, S.index(dim)], Y[conc <= thr, S.index(dim)],
                               alternative='greater').pvalue)
    except Exception:
        p = np.nan
    thr_rows.append({'compound': comp, 'name': chem_name.get(comp, comp), 'dim': dim,
                     'threshold': thr, 'n_above': int((conc > thr).sum()),
                     'median_sensory_above': med_hi, 'median_sensory_below': med_lo,
                     'p_value_one_sided': p})
thr_df = pd.DataFrame(thr_rows)
thr_df.to_csv(os.path.join(RES, 'Q2_threshold_nonlinearity.csv'), index=False, encoding='utf-8-sig')
log('阈值非线性检验：\n' + thr_df.to_string(index=False))

# Top-3 单独预测能力（5 折 RidgeCV）
kf = KFold(n_splits=5, shuffle=True, random_state=0)
r2_top3, r2_full = [], []
for j in range(len(S)):
    cols = top3[:, j]; pred3 = np.zeros(len(X)); predf = np.zeros(len(X))
    for tr, te in kf.split(X):
        pred3[te] = RidgeCV(alphas=np.logspace(-2, 3, 10)).fit(
            X[tr][:, cols], Y[tr, j]).predict(X[te][:, cols])
        predf[te] = RidgeCV(alphas=np.logspace(-2, 3, 10)).fit(
            X[tr], Y[tr, j]).predict(X[te])
    r2_top3.append(float(r2_scores(Y[:, j:j + 1], pred3[:, None])[0]))
    r2_full.append(float(r2_scores(Y[:, j:j + 1], predf[:, None])[0]))
top3_df['R2_top3_only'] = r2_top3
top3_df['R2_all_features'] = r2_full
top3_df.to_csv(os.path.join(RES, 'Q2_top3_table.csv'), index=False, encoding='utf-8-sig')

log('Top-3 单独预测 R² 均值 %.3f；全化合物 Ridge R² 均值 %.3f；信息保留率 %.1f%%'
    % (np.mean(r2_top3), np.mean(r2_full), 100 * np.mean(r2_top3) / np.mean(r2_full)))
log('标志化合物 Top-3 命中 %d/%d（%.1f%%），Top-10 命中 %d/%d（%.1f%%）'
    % (top3_df['marker_hit_top3'].sum(), len(S), 100 * top3_df['marker_hit_top3'].mean(),
       top3_df['marker_hit_top10'].sum(), len(S), 100 * top3_df['marker_hit_top10'].mean()))
log('来源一致性 %d/%d（%.1f%%）'
    % (top3_df['origin_consistent'].sum(), len(S), 100 * top3_df['origin_consistent'].mean()))

# 保存
pd.DataFrame(agg, index=CAND, columns=S).to_csv(
    os.path.join(RES, 'Q2_importance_aggregate.csv'), encoding='utf-8-sig')
pd.DataFrame(freq, index=CAND, columns=S).to_csv(
    os.path.join(RES, 'Q2_bootstrap_freq.csv'), encoding='utf-8-sig')
pd.DataFrame(top3_boot.reshape(B, -1)).to_csv(os.path.join(RES, 'Q2_bootstrap_top3.csv'), index=False)
summary = {
    'n_candidates': len(CAND),
    'graph': {'n_nodes': G.number_of_nodes(), 'n_edges': G.number_of_edges(),
              'density': float(nx.density(G)), 'threshold': THR,
              'n_communities': len(comms), 'modularity': float(mod),
              'mean_degree': float(np.mean(list(deg.values())))},
    'stability': {'bootstrap_B': B,
                  'mean_top3_frequency': float(jac_df['top3_bootstrap_freq_mean'].mean()),
                  'mean_final_top3_frequency': float(jac_df['Jaccard_final_vs_methods'].mean()),
                  'mean_jaccard_methods': float(jac_df['Jaccard_methods_mean'].mean())},
    'rationality': {'marker_hit_top3': float(top3_df['marker_hit_top3'].mean()),
                    'marker_hit_top10': float(top3_df['marker_hit_top10'].mean()),
                    'origin_consistent': float(top3_df['origin_consistent'].mean()),
                    'R2_top3_only_mean': float(np.mean(r2_top3)),
                    'R2_all_features_mean': float(np.mean(r2_full))},
    'alpha_lasso': alpha_best,
}
dump_json(summary, 'Q2_summary.json')

# ---------------- 5. 图 ----------------
fig, ax = plt.subplots(figsize=(10, 8.5))
Gs = nx.Graph(); Gs.add_nodes_from(CAND)
for i, j in zip(*np.where(np.triu(np.abs(R) >= 0.7, 1))):
    Gs.add_edge(CAND[i], CAND[j])
pos = nx.spring_layout(Gs, k=0.35, seed=7, weight=None, iterations=120)
comm_colors = plt.cm.tab20(np.linspace(0, 1, max(len(comms), 2)))
nx.draw_networkx_edges(Gs, pos, alpha=0.15, width=0.6, edge_color='#888', ax=ax)
nx.draw_networkx_nodes(Gs, pos, node_color=[comm_colors[node_comm.get(nd, 0) % 20] for nd in Gs],
                       node_size=[16 + 3.0 * np.sqrt(deg.get(nd, 1)) for nd in Gs],
                       linewidths=0.3, edgecolors='white', ax=ax)
hubs = nodes.head(12)['compound'].tolist()
nx.draw_networkx_labels(Gs, pos, labels={h: h.replace('.', ' ')[:14] for h in hubs},
                        font_size=7, ax=ax)
ax.set_title('')
ax.axis('off')
savefig(fig, 'fig_q2_network.png'); plt.close(fig)

fig, ax = plt.subplots(figsize=(9.5, 4.4))
topc = comm_df.sort_values('size', ascending=False).head(10)
bottoms = np.zeros(len(topc))
origin_colors = {'Hops': '#55A868', 'Yeast': '#C44E52', 'Malt': '#4C72B0',
                 'Spices': '#8172B2', 'Wild flora': '#CCB974', 'Others': '#999999'}
for o in ['Hops', 'Yeast', 'Malt', 'Spices', 'Wild flora', 'Others']:
    vals = [sum(origin.get(c, 'Others') == o for c in comms[k]) for k in topc['community']]
    ax.bar([f'C{k}({n})' for k, n in zip(topc['community'], topc['size'])], vals,
           bottom=bottoms, color=origin_colors[o], label=o)
    bottoms += np.array(vals, dtype=float)
ax.set_ylabel('化合物数')
ax.legend(frameon=False, fontsize=8, ncol=3)
plt.xticks(rotation=30, fontsize=8)
savefig(fig, 'fig_q2_community_composition.png'); plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))
ax = axes[0]
order = np.argsort(-top3_df['top3_bootstrap_freq_mean'].values)
ax.bar(range(len(S)), top3_df['top3_bootstrap_freq_mean'].values[order], color='#4C72B0')
ax.axhline(top3_df['top3_bootstrap_freq_mean'].mean(), color='r', ls='--', lw=1)
ax.set_xticks(range(len(S)))
ax.set_xticklabels([SENS_CN[S[i]] for i in order], rotation=90, fontsize=6)
ax.set_ylabel('Top-3 平均 bootstrap 入选频率'); ax.set_ylim(0, 1)
ax.set_title('(a) Top-3 稳定性')
ax = axes[1]
ax.hist(jac_df['Jaccard_methods_mean'], bins=14, color='#DD8452', alpha=.85)
ax.axvline(jac_df['Jaccard_methods_mean'].mean(), color='k', ls='--',
           label='均值 %.2f' % jac_df['Jaccard_methods_mean'].mean())
ax.set_xlabel('方法间 Top-3 的 Jaccard 系数'); ax.set_ylabel('维度数')
ax.set_title('(b) 不同建模方法的一致性'); ax.legend(frameon=False)
savefig(fig, 'fig_q2_stability.png'); plt.close(fig)

sel = ['A_hops_all', 'A_esters_all', 'A_malt_all', 'bitternes', 'dms', 'diacetyl',
       'X4vg', 'lactic', 'clove', 'overall']
sel_idx = [S.index(c) for c in sel]
comps = sorted({int(t) for j in sel_idx for t in top3[:, j]})
fig, ax = plt.subplots(figsize=(9, max(4, 0.32 * len(comps))))
mat = np.array([[agg[t, j] for j in sel_idx] for t in comps])
im = ax.imshow(mat, aspect='auto', cmap='viridis_r')
ax.set_xticks(range(len(sel))); ax.set_xticklabels([SENS_CN[c] for c in sel], rotation=60, fontsize=8)
ax.set_yticks(range(len(comps)))
ax.set_yticklabels([chem_name.get(CAND[t], CAND[t])[:24] for t in comps], fontsize=7)
ax.set_title('')
plt.colorbar(im, ax=ax, label='聚合秩')
savefig(fig, 'fig_q2_top3_heatmap.png'); plt.close(fig)

log('问题 2 完成，用时 %.1fs' % (time.time() - t0))


