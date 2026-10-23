# -*- coding: utf-8 -*-
"""25_q3.py —— 问题 3：风味与"风味指纹"生成
内容：
  1) 构建平滑特征空间（对数变换 + 标准化，可逆），保持与 1.csv 的正逆变换；
  2) 两个风格条件生成模型：条件概率主成分（PPCA）生成器 与 条件变分自编码器（CVAE）；
  3) 用风格分类保真度、MMD 分布距离、感官画像一致性、缺陷化合物合规率、多样性 5 项指标比较模型；
  4) 对 Tripel / Kriek / Lambic 三个风格生成化合物谱与感官画像（风味指纹）；
  5) 跨风格迁移：Pils/Lager → Tripel，并在输出空间做缺陷化合物约束修正，保证缺陷不恶化。
"""
import sys, os, json, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import torch
import torch.nn as nn
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, confusion_matrix
plt = setup_cn_font()
t0 = time.time()
torch.manual_seed(2026); np.random.seed(2026)

chem_raw = pd.read_csv(os.path.join(ATT, '1.csv'), encoding='utf-8')
chem = pd.read_csv(os.path.join(DP, 'chem_features.csv'), encoding='utf-8-sig')
sens = pd.read_csv(os.path.join(DP, 'sensory_z.csv'), encoding='utf-8-sig')
C = chem_cols(chem)
S = sens_cols(sens)
styles = chem['tasting_category_fine'].values
STYLES = sorted(set(styles))
Y = sens[S].values.astype(float)
log('样本 %d，特征 %d，感官维度 %d，风格 %d 种' % (len(chem), len(C), len(S), len(STYLES)))

# ---------------- 1. 平滑对数特征空间 ----------------
# 已知：37 个参数列在 1.csv 中为 log10 值；少数化合物列为原始浓度（与校准数据同量纲）；
# 其余为未校准的对数响应值。统一做法：log10 列直接使用；非负原始列取 log10(x+1e-6)。
log10_cols = set()
raw_cols = set()
fm = pd.read_csv(os.path.join(DP, 'feature_meta2.csv'), encoding='utf-8-sig').set_index('feature')
for c in C:
    vt = fm.loc[c, 'value_type'] if c in fm.index else 'log10_or_unknown'
    if vt == 'raw':
        raw_cols.add(c)
    else:
        log10_cols.add(c)
# 校准核验中未覆盖的列：含负值者必为对数；非负者按对数处理
for c in C:
    v = chem_raw[c].values.astype(float)
    if np.nanmin(v) < 0:
        log10_cols.add(c); raw_cols.discard(c)
log('log10 列 %d，原始浓度列 %d' % (len(log10_cols), len(raw_cols)))

EPS = 1e-6
V = np.zeros((len(chem), len(C)))
for j, c in enumerate(C):
    x = chem_raw[c].values.astype(float)
    if c in raw_cols:
        V[:, j] = np.log10(np.clip(x, 0, None) + EPS)
    else:
        V[:, j] = x
# 缺失处理：按列中位数填补（问题 1 中已证明中位数/KNN 填补差异极小）
n_miss = int(np.isnan(V).sum())
for j in range(V.shape[1]):
    m = np.isnan(V[:, j])
    if m.any():
        V[m, j] = np.nanmedian(V[:, j])
log('对数空间缺失单元格 %d，已按列中位数填补' % n_miss)
MU, SD = V.mean(0), V.std(0) + 1e-9
Z = (V - MU) / SD
log('平滑特征空间：Z 形状 %s，均值 %.3f，标准差 %.3f' % (Z.shape, Z.mean(), Z.std()))


def inv_transform(Zgen):
    """Z 空间 → 1.csv 原始量纲（浓度/响应值）。"""
    Vg = Zgen * SD + MU
    X = np.zeros_like(Vg)
    for j, c in enumerate(C):
        if c in raw_cols:
            X[:, j] = 10 ** np.clip(Vg[:, j], -20, 20) - EPS
        else:
            X[:, j] = np.clip(Vg[:, j], -20, 20)
    return X


# ---------- 缺陷化合物定义（浓度来自 1.csv 与校准数据的关系）----------
DEFECT = [  # (化合物, 变换类型, 阈值, 单位)
    ('DMS', 'log10', 17.25, 'ug/L'),
    ('X4VG', 'log10', 0.206333, 'mg/L'),
    ('X2.3.butanedione', 'raw', 0.29925, 'mg/L'),
    ('X.E..2.nonenal', 'raw', 0.35, 'ug/L'),
]
IDX = {c: C.index(c) for c in C}


def defect_concentration(Zgen):
    """返回各缺陷化合物的浓度矩阵 (n × 4)。"""
    Vg = Zgen * SD + MU
    out = np.zeros((Zgen.shape[0], len(DEFECT)))
    for k, (c, typ, thr, unit) in enumerate(DEFECT):
        v = Vg[:, IDX[c]]
        out[:, k] = 10 ** np.clip(v, -20, 20) if typ == 'log10' else 10 ** np.clip(v, -20, 20) - EPS
    return out


def defect_index(Zgen, sensory_pred):
    """缺陷指数：前 4 项为浓度/阈值，第 5 项为预测的 stale_hops 感官 z 值映射。"""
    D = defect_concentration(Zgen)
    thr = np.array([d[2] for d in DEFECT])
    idx = D / thr
    stale = sensory_pred[:, S.index('stale_hops')]
    idx = np.column_stack([idx, np.maximum(stale, 0)])    # 感官缺陷指数
    return idx


# ---------- 感官预测器（用于风格画像与缺陷约束） ----------
sens_model = ExtraTreesRegressor(n_estimators=400, max_features=0.4, min_samples_leaf=1,
                                 random_state=0, n_jobs=1).fit(Z, Y)
log('感官预测器（ExtraTrees）拟合完成')


def correct_defects(Zcand, D_cap_local, iters=None, lr=None):
    """缺陷约束投影：把 4 个缺陷化合物的浓度直接截断到"允许上限"，精确且无迭代误差。

    D_cap_local: (n, 5) 的缺陷指数上限（前 4 列为化学缺陷，第 5 列为感官缺陷，不修正）。
    """
    Zc = Zcand.copy()
    Vc = Zc * SD + MU
    for k, (c, typ, thr, unit) in enumerate(DEFECT):
        j = IDX[c]
        v = Vc[:, j]
        conc = 10 ** np.clip(v, -20, 20) - (EPS if typ != 'log10' else 0.0)
        conc = np.clip(conc, 1e-12, None)
        conc_cap = np.maximum(D_cap_local[:, k] * thr, 1e-12)
        conc_new = np.minimum(conc, conc_cap)
        v_new = np.log10(conc_new + (EPS if typ != 'log10' else 0.0))
        Vc[:, j] = v_new
    return (Vc - MU) / SD


# ---------------- 2A. 条件 PPCA 生成器 ----------------
K_FACT = 20
pca = PCA(n_components=K_FACT, random_state=0).fit(Z)
F = pca.transform(Z)                                  # 250 × K
resid = Z - pca.inverse_transform(F)
resid_std = resid.std(0)
style_mean_F = {s: F[styles == s].mean(0) for s in STYLES}
n_style = pd.Series(styles).value_counts().to_dict()
KAPPA = 5.0


class PPCA_Generator:
    name = '条件 PPCA（概率主成分）'

    def fit(self):
        self.muF_global = F.mean(0)
        self.muF = {s: (n_style[s] * style_mean_F[s] + KAPPA * self.muF_global) /
                       (n_style[s] + KAPPA) for s in STYLES}
        self.scaleF = F.std(0)
        return self

    def sample(self, style, n, rng):
        mu = self.muF[style]
        f = mu[None, :] + rng.normal(0, 1, (n, K_FACT)) * self.scaleF[None, :]
        X = pca.inverse_transform(f)
        X = X + rng.normal(0, 1, (n, len(C))) * resid_std[None, :]
        return X


# ---------------- 2B. 条件 VAE 生成器 ----------------
class CVAE(nn.Module):
    def __init__(self, d, n_style, latent=16, hidden=128, emb=8):
        super().__init__()
        self.emb = nn.Embedding(n_style, emb)
        self.enc = nn.Sequential(nn.Linear(d + emb, hidden), nn.GELU(),
                                 nn.Linear(hidden, hidden), nn.GELU())
        self.mu = nn.Linear(hidden, latent); self.logvar = nn.Linear(hidden, latent)
        self.dec = nn.Sequential(nn.Linear(latent + emb, hidden), nn.GELU(),
                                 nn.Linear(hidden, hidden), nn.GELU(),
                                 nn.Linear(hidden, d))
        self.latent = latent

    def forward(self, x, sidx):
        e = self.emb(sidx)
        h = self.enc(torch.cat([x, e], dim=1))
        mu, logvar = self.mu(h), torch.clamp(self.logvar(h), -6, 4)
        z = mu + torch.randn_like(mu) * torch.exp(0.5 * logvar)
        xr = self.dec(torch.cat([z, e], dim=1))
        return xr, mu, logvar

    def decode(self, z, sidx):
        return self.dec(torch.cat([z, self.emb(sidx)], dim=1))


class CVAE_Generator:
    name = '条件变分自编码器（CVAE）'

    def __init__(self):
        self.s2i = {s: i for i, s in enumerate(STYLES)}

    def fit(self, epochs=1500, beta=0.5):
        d = Z.shape[1]
        self.net = CVAE(d, len(STYLES))
        opt = torch.optim.Adam(self.net.parameters(), lr=1e-3, weight_decay=1e-5)
        Xt = torch.tensor(Z, dtype=torch.float32)
        st = torch.tensor([self.s2i[s] for s in styles], dtype=torch.long)
        n = len(Z)
        for ep in range(epochs):
            perm = torch.randperm(n)
            tot = 0.0
            for i in range(0, n, 32):
                b = perm[i:i + 32]
                xr, mu, logvar = self.net(Xt[b], st[b])
                rec = ((xr - Xt[b]) ** 2).mean()
                kl = (-0.5 * (1 + logvar - mu ** 2 - logvar.exp()).sum(1)).mean() / d
                loss = rec + beta * kl
                opt.zero_grad(); loss.backward(); opt.step()
                tot += float(loss) * len(b)
            if (ep + 1) % 300 == 0:
                log('  CVAE epoch %4d loss=%.4f' % (ep + 1, tot / n))
        self.net.eval()
        # 潜在空间的风格均值与尺度（用于条件采样与迁移）
        with torch.no_grad():
            e = self.net.emb(st)
            h = self.net.enc(torch.cat([Xt, e], dim=1))
            mu_all = self.net.mu(h)
            self.muZ, self.sigmaZ = {}, {}
            for s in STYLES:
                m = (st == self.s2i[s]).numpy()
                ms = mu_all[m]
                self.muZ[s] = ms.mean(0).numpy()
                n_s = int(m.sum())
                var = ((ms - ms.mean(0)) ** 2).sum(0) / (n_s + KAPPA) + KAPPA / (n_s + KAPPA)
                self.sigmaZ[s] = np.sqrt(var).numpy()
        return self

    def sample(self, style, n, rng):
        with torch.no_grad():
            z = self.muZ[style][None, :] + rng.normal(0, 1, (n, self.net.latent)) * \
                self.sigmaZ[style][None, :]
            z = torch.tensor(z, dtype=torch.float32)
            sidx = torch.full((n,), self.s2i[style], dtype=torch.long)
            return self.net.decode(z, sidx).numpy()

    def encode_mu(self, Zsub, style):
        with torch.no_grad():
            Xt = torch.tensor(Zsub, dtype=torch.float32)
            sidx = torch.full((len(Zsub),), self.s2i[style], dtype=torch.long)
            e = self.net.emb(sidx)
            h = self.net.enc(torch.cat([Xt, e], dim=1))
            return self.net.mu(h).numpy()

    def decode(self, f, style):
        with torch.no_grad():
            z = torch.tensor(np.atleast_2d(f), dtype=torch.float32)
            sidx = torch.full((z.shape[0],), self.s2i[style], dtype=torch.long)
            return self.net.decode(z, sidx).numpy()


rng = np.random.default_rng(2026)
models = [PPCA_Generator().fit(), CVAE_Generator().fit()]
log('两个生成模型训练完成  %.1fs' % (time.time() - t0))


# ---------------- 3. 生成质量评价 ----------------
def style_classifier_eval():
    """真实数据上训练风格分类器（5 折交叉验证），用于评价生成样本的风格保真度。"""
    clf = ExtraTreesClassifier(n_estimators=400, max_features=0.4, random_state=0, n_jobs=1)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    strat = np.array([s if pd.Series(styles).value_counts()[s] >= 10 else 'Rare' for s in styles])
    acc = []
    for tr, te in skf.split(Z, strat):
        clf.fit(Z[tr], styles[tr])
        acc.append(accuracy_score(styles[te], clf.predict(Z[te])))
    clf.fit(Z, styles)
    return clf, float(np.mean(acc))


clf_style, real_acc = style_classifier_eval()
log('真实数据风格分类器 5 折准确率 %.3f' % real_acc)


def mmd_rbf(A, B, gamma=None):
    from sklearn.metrics.pairwise import rbf_kernel
    if gamma is None:
        gamma = 1.0 / A.shape[1]
    Kaa = rbf_kernel(A, A, gamma).mean()
    Kbb = rbf_kernel(B, B, gamma).mean()
    Kab = rbf_kernel(A, B, gamma).mean()
    return float(np.sqrt(max(Kaa + Kbb - 2 * Kab, 0)))


GEN_N = 200
TARGET_STYLES = ['Tripel', 'Kriek', 'Lambic']
# 真实数据的缺陷违规率（作为参照）
real_viol = {}
for s in TARGET_STYLES:
    Ds = defect_index(Z[styles == s], Y[styles == s])
    real_viol[s] = float(np.mean((Ds > 1).any(axis=1)))
    log('真实 %-8s 缺陷超阈值样本比例 = %.3f' % (s, real_viol[s]))
# 生成时的缺陷上限：不超过该风格真实样本的 75% 分位（且不小于 0.5 倍阈值）
D_cap_style = {s: np.maximum(np.percentile(defect_index(Z[styles == s], Y[styles == s]),
                                           75, axis=0), 0.5) for s in TARGET_STYLES}

eval_rows, gen_store = [], {}
for m in models:
    for s in TARGET_STYLES:
        Zg = m.sample(s, GEN_N, np.random.default_rng(2026))
        # 生成谱的缺陷防护（保持与真实风格同量级的缺陷水平）
        Zg = correct_defects(Zg, np.tile(D_cap_style[s], (GEN_N, 1)))
        pred = clf_style.predict(Zg)
        fidelity = float(np.mean(pred == s))
        sens_g = sens_model.predict(Zg).mean(0)
        sens_real = Y[styles == s].mean(0)
        sens_corr = float(np.corrcoef(sens_g, sens_real)[0, 1])
        rep = np.random.default_rng(1).choice(np.where(styles == s)[0],
                                              min(30, int((styles == s).sum())), replace=False)
        mmd = mmd_rbf(Zg, Z[rep])
        dg = defect_index(Zg, sens_model.predict(Zg))
        viol = float(np.mean((dg > np.maximum(np.percentile(
            defect_index(Z[styles == s], Y[styles == s]), 75, axis=0), 1.0)).any(axis=1)))
        # 多样性：5 维主成分空间中的平均两两欧氏距离
        pca5 = PCA(n_components=5, random_state=0).fit(Z)
        P = pca5.transform(Zg)[:100]
        div = float(np.mean(np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2)))
        eval_rows.append({'model': m.name, 'style': s, 'style_fidelity': fidelity,
                          'sensory_corr': sens_corr, 'MMD': mmd,
                          'defect_exceed_rate': viol, 'real_defect_exceed_rate': real_viol[s],
                          'diversity': div})
        gen_store[(m.name, s)] = Zg
ev = pd.DataFrame(eval_rows)
ev.to_csv(os.path.join(RES, 'Q3_model_comparison.csv'), index=False, encoding='utf-8-sig')
log('生成模型比较：\n' + ev.to_string(index=False))

# 综合评分（归一化后加权）
score = {}
for name, sub in ev.groupby('model'):
    fid = sub['style_fidelity'].mean()
    sen = sub['sensory_corr'].mean()
    mmd = sub['MMD'].mean()
    vio = sub['defect_exceed_rate'].mean()
    mmd_score = 1 - (mmd - ev['MMD'].min()) / (ev['MMD'].max() - ev['MMD'].min() + 1e-9)
    score[name] = 0.35 * fid + 0.30 * sen + 0.20 * mmd_score + 0.15 * (1 - vio)
for k, v in score.items():
    log('  综合得分 %-30s %.4f' % (k, v))
best_name = max(score, key=score.get)
best = [m for m in models if m.name == best_name][0]
log('全局综合最优生成模型：', best_name)

# 逐风格模型选择：每个风格选用该风格综合指标更优的生成器
model_by_name = {m.name: m for m in models}
final_model, final_gen = {}, {}
for s in TARGET_STYLES:
    sub = ev[ev['style'] == s].copy()
    mmd_min, mmd_max = sub['MMD'].min(), sub['MMD'].max() + 1e-9
    sub['per_style_score'] = (0.35 * sub['style_fidelity'] + 0.30 * sub['sensory_corr'] +
                              0.20 * (1 - (sub['MMD'] - mmd_min) / (mmd_max - mmd_min)) +
                              0.15 * (1 - sub['defect_exceed_rate']))
    pick = sub.sort_values('per_style_score', ascending=False).iloc[0]
    final_model[s] = model_by_name[pick['model']]
    Zg = final_model[s].sample(s, GEN_N, np.random.default_rng(2026))
    Zg = correct_defects(Zg, np.tile(D_cap_style[s], (GEN_N, 1)))
    final_gen[s] = Zg
    log('风格 %-8s 选用模型：%s（风格保真 %.2f，感官相关 %.2f，MMD %.3f）'
        % (s, pick['model'], pick['style_fidelity'], pick['sensory_corr'], pick['MMD'],))

# ---------------- 4. 三风格生成与感官画像（风味指纹）----------------
portrait_rows, fingerprint = [], {}
for s in TARGET_STYLES:
    Zg = final_gen[s]
    Xg = inv_transform(Zg)
    sens_g = sens_model.predict(Zg)
    grade_mean = np.zeros(len(S))
    for j, c in enumerate(S):
        fitp = json.load(open(os.path.join(RES, '20_data_report.json'), encoding='utf-8'))['ordinal_fits'][c]
        grade_mean[j] = np.clip(np.round((sens_g.mean(0)[j] - fitp['a']) / fitp['b']), 0, 6)
    # 保存生成谱
    df = pd.DataFrame(Xg, columns=C)
    df.insert(0, 'beer', ['gen_%s_%03d' % (s, i) for i in range(len(df))])
    df.insert(1, 'style', s)
    df.to_csv(os.path.join(RES, 'Q3_generated_%s.csv' % s), index=False, encoding='utf-8-sig')
    # 感官画像
    portrait_rows.append({'style': s, **{c: float(sens_g.mean(0)[j]) for j, c in enumerate(S)},
                          **{'grade_' + c: float(grade_mean[j]) for j, c in enumerate(S)}})
    # 风味指纹：与全局均值差异最大的化合物
    global_mean = Z.mean(0)
    diff = Zg.mean(0) - global_mean
    top_up = np.argsort(-diff)[:10]
    top_dn = np.argsort(diff)[:10]
    fingerprint[s] = {
        'up': [{'compound': C[i], 'delta_z': float(diff[i])} for i in top_up],
        'down': [{'compound': C[i], 'delta_z': float(diff[i])} for i in top_dn],
        'sensory_mean': {c: float(sens_g.mean(0)[j]) for j, c in enumerate(S)},
    }
portrait = pd.DataFrame(portrait_rows)
portrait.to_csv(os.path.join(RES, 'Q3_sensory_portrait.csv'), index=False, encoding='utf-8-sig')
log('三风格感官画像（关键维度 z 值）：')
key_dims = ['alcohol', 'body', 'bitternes', 'sweetness', 'acidity', 'lactic', 'acetic',
            'A_esters_all', 'A_hops_all', 'A_malt_all', 'dms', 'diacetyl', 'X4vg', 't2n', 'stale_hops']
log(portrait[['style'] + key_dims].round(2).to_string(index=False))

# ---------------- 5. 跨风格迁移：Pils/Lager → Tripel ----------------
SRC = 'Pils/Lager'
TGT = 'Tripel'
src_idx = np.where(styles == SRC)[0]
tgt_idx = np.where(styles == TGT)[0]
log('源风格 %s：%d 个样本；目标风格 %s：%d 个样本' % (SRC, len(src_idx), TGT, len(tgt_idx)))

# 缺陷上限 = min(源样本自身, 目标风格 75% 分位) ，确保"不恶化"
D_src = defect_index(Z[src_idx], Y[src_idx])
D_tgt = defect_index(Z[tgt_idx], Y[tgt_idx])
D_cap = np.minimum(np.percentile(D_tgt, 75, axis=0)[None, :],
                   np.maximum(D_src, 1e-3))


def transfer(m, Zsrc, D_cap_local):
    """潜在空间风格平移 + 缺陷约束修正。"""
    if isinstance(m, PPCA_Generator):
        f_src = pca.transform(Zsrc)
        mu_src = m.muF[SRC]; mu_tgt = m.muF[TGT]
        f_new = f_src + (mu_tgt - mu_src)[None, :]
        Znew = pca.inverse_transform(f_new)
    else:
        z_src = m.encode_mu(Zsrc, SRC)
        z_tgt_mean = m.muZ[TGT]
        z_src_mean = m.muZ[SRC]
        z_new = z_src + (z_tgt_mean - z_src_mean)[None, :]
        Znew = m.decode(z_new, TGT)
    return correct_defects(Znew, D_cap_local)


Z_trans = transfer(best, Z[src_idx], D_cap)
X_trans = inv_transform(Z_trans)
D_trans = defect_index(Z_trans, sens_model.predict(Z_trans))
sens_src = sens_model.predict(Z[src_idx])
sens_trans = sens_model.predict(Z_trans)
sens_tgt_mean = Y[tgt_idx].mean(0)

# 风格概率与感官相似度
def style_probs(Zmat):
    return clf_style.predict_proba(Zmat)


def tgt_prob(prob, clf, style):
    classes = list(clf.classes_)
    if style not in classes:
        return np.zeros(len(prob))
    return prob[:, classes.index(style)]


prob_src = style_probs(Z[src_idx])
prob_trans = style_probs(Z_trans)
p_tgt_src = tgt_prob(prob_src, clf_style, TGT)
p_tgt_trans = tgt_prob(prob_trans, clf_style, TGT)
cos_src = np.array([np.corrcoef(sens_src[i], sens_tgt_mean)[0, 1] for i in range(len(src_idx))])
cos_trans = np.array([np.corrcoef(sens_trans[i], sens_tgt_mean)[0, 1] for i in range(len(src_idx))])
# 缺陷改善情况
viol_src = (D_src > 1).sum(1)
viol_trans = (D_trans > 1).sum(1)

rows = []
for i, bi in enumerate(src_idx):
    rows.append({'source_beer': int(chem['beer'].values[bi]),
                 'src_style': SRC,
                 'P_Tripel_before': float(p_tgt_src[i]),
                 'P_Tripel_after': float(p_tgt_trans[i]),
                 'sensory_corr_to_Tripel_before': float(cos_src[i]),
                 'sensory_corr_to_Tripel_after': float(cos_trans[i]),
                 'defect_flags_before': int(viol_src[i]),
                 'defect_flags_after': int(viol_trans[i]),
                 **{'idx_before_' + d[0]: float(D_src[i, k]) for k, d in enumerate(DEFECT)},
                 **{'idx_after_' + d[0]: float(D_trans[i, k]) for k, d in enumerate(DEFECT)},
                 'idx_stale_before': float(D_src[i, 4]), 'idx_stale_after': float(D_trans[i, 4])})
trans_df = pd.DataFrame(rows)
trans_df.to_csv(os.path.join(RES, 'Q3_transfer_results.csv'), index=False, encoding='utf-8-sig')
log('跨风格迁移（%s → %s）汇总：' % (SRC, TGT))
log('  风格判别概率 Tripel：迁移前 %.3f → 迁移后 %.3f'
    % (p_tgt_src.mean(), p_tgt_trans.mean()))
log('  与 Tripel 真实感官画像相关：迁移前 %.3f → 迁移后 %.3f'
    % (cos_src.mean(), cos_trans.mean()))
log('  缺陷指标超阈值个数：迁移前 %.2f → 迁移后 %.2f（缺陷修正后）'
    % (viol_src.mean(), viol_trans.mean()))
log('  缺陷指数均值（DMS/4VG/Diacetyl/t2n/stale）：')
log('    迁移前 ' + np.round(D_src.mean(0), 3).tolist().__str__())
log('    迁移后 ' + np.round(D_trans.mean(0), 3).tolist().__str__())
log('  缺陷不恶化样本比例：%.3f'
    % float(np.mean((D_trans[:, :4] <= D_src[:, :4] + 1e-6).all(axis=1))))

# 保存迁移结果
df = pd.DataFrame(X_trans, columns=C)
df.insert(0, 'source_beer', [int(chem['beer'].values[i]) for i in src_idx])
df.to_csv(os.path.join(RES, 'Q3_transfer_Pils_to_Tripel.csv'), index=False, encoding='utf-8-sig')

# ---------------- 6. 图 ----------------
pca2 = PCA(n_components=2, random_state=0).fit(Z)
fig, ax = plt.subplots(figsize=(8.4, 6))
for s in STYLES:
    m = styles == s
    ax.scatter(pca2.transform(Z[m])[:, 0], pca2.transform(Z[m])[:, 1], s=22, alpha=.75,
               label=STYLE_CN.get(s, s) if s in ('Tripel', 'Kriek', 'Lambic', 'Pils/Lager') else None,
               color={'Tripel': '#4C72B0', 'Kriek': '#C44E52', 'Lambic': '#DD8452',
                      'Pils/Lager': '#55A868'}.get(s, '#cccccc'))
for s in TARGET_STYLES:
    Zg = final_gen[s]
    ax.scatter(pca2.transform(Zg)[:, 0], pca2.transform(Zg)[:, 1], s=26, marker='*',
               color={'Tripel': '#4C72B0', 'Kriek': '#C44E52', 'Lambic': '#DD8452'}[s],
               edgecolor='k', linewidths=.3, label='生成-%s' % STYLE_CN.get(s, s))
ax.set_xlabel('PC1'); ax.set_ylabel('PC2')
ax.legend(frameon=False, fontsize=8, ncol=2)
savefig(fig, 'fig_q3_pca_generated.png'); plt.close(fig)

# 雷达图：三风格感官画像
radar_dims = ['alcohol', 'body', 'bitternes', 'sweetness', 'acidity', 'lactic', 'acetic',
              'A_esters_all', 'A_hops_all', 'A_malt_all', 'dms', 'diacetyl']
labels = [SENS_CN[c] for c in radar_dims]
ang = np.linspace(0, 2 * np.pi, len(radar_dims), endpoint=False).tolist()
ang += ang[:1]
fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), subplot_kw=dict(polar=True))
port = portrait.set_index('style')
for ax, s in zip(axes, TARGET_STYLES):
    v = [float(port.loc[s, c]) for c in radar_dims] + [float(port.loc[s, radar_dims[0]])]
    ax.plot(ang, v, lw=2, color='#C44E52', label='生成')
    yr = [float(Y[styles == s].mean(0)[S.index(c)]) for c in radar_dims]
    ax.plot(ang, yr + [yr[0]], lw=2, ls='--', color='#4C72B0', label='真实均值')
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(labels, fontsize=7)
    ax.set_title('生成-%s / 真实-%s' % (STYLE_CN.get(s, s), STYLE_CN.get(s, s)), fontsize=10)
    ax.legend(frameon=False, fontsize=7, loc='upper right', bbox_to_anchor=(1.15, 1.1))
savefig(fig, 'fig_q3_radar_portrait.png'); plt.close(fig)

# 缺陷指数对比
fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
ax = axes[0]
x = np.arange(5); w = 0.26
for k, s in enumerate(TARGET_STYLES):
    Zg = final_gen[s]
    dg = defect_index(Zg, sens_model.predict(Zg)).mean(0)
    ax.bar(x + (k - 1) * w, dg, width=w, label='生成-' + STYLE_CN.get(s, s))
dr = defect_index(Z[styles == TGT], Y[styles == TGT]).mean(0)
ax.bar(x + 1.5 * w, dr, width=w, label='真实-Tripel')
ax.axhline(1, color='k', ls='--', lw=1)
ax.set_xticks(x); ax.set_xticklabels(['DMS', '4VG', '双乙酰', '反-2-壬烯醛', '陈酒花味'], fontsize=8)
ax.set_ylabel('缺陷指数（浓度/阈值）'); ax.set_title('(a) 生成样本的缺陷指数')
ax.legend(frameon=False, fontsize=7)
ax = axes[1]
idx_names = ['DMS', '4VG', '双乙酰', '反-2-壬烯醛', '陈酒花味']
x = np.arange(5); w = 0.35
ax.bar(x - w / 2, D_src.mean(0), width=w, label='迁移前（Pils/Lager）')
ax.bar(x + w / 2, D_trans.mean(0), width=w, label='迁移后（→Tripel）')
ax.axhline(1, color='k', ls='--', lw=1)
ax.set_xticks(x); ax.set_xticklabels(idx_names, fontsize=8)
ax.set_title('(b) 跨风格迁移前后的缺陷指数')
ax.legend(frameon=False, fontsize=8)
savefig(fig, 'fig_q3_defect_control.png'); plt.close(fig)

# 迁移：风格概率与感官相似度
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
ax = axes[0]
ax.scatter(p_tgt_src, p_tgt_trans, s=40, color='#4C72B0')
ax.plot([0, 1], [0, 1], 'k--', lw=1)
ax.set_xlabel('迁移前被判为 Tripel 的概率'); ax.set_ylabel('迁移后概率')
ax.set_title('(a) 风格判别概率变化')
ax = axes[1]
ax.scatter(cos_src, cos_trans, s=40, color='#DD8452')
ax.plot([0, 1], [0, 1], 'k--', lw=1)
ax.set_xlabel('迁移前感官画像与 Tripel 相关'); ax.set_ylabel('迁移后相关')
ax.set_title('(b) 感官画像向 Tripel 靠拢')
savefig(fig, 'fig_q3_transfer.png'); plt.close(fig)

# 保存摘要
summary = {
    'best_model': best_name, 'model_scores': score,
    'real_style_classifier_acc': real_acc,
    'evaluation': ev.to_dict(orient='records'),
    'generated_styles': TARGET_STYLES, 'generated_per_style': GEN_N,
    'defect_definition': [{'compound': d[0], 'transform': d[1], 'threshold': d[2],
                           'unit': d[3]} for d in DEFECT],
    'transfer': {'source': SRC, 'target': TGT, 'n_source': len(src_idx),
                 'P_Tripel_before': float(p_tgt_src.mean()),
                 'P_Tripel_after': float(p_tgt_trans.mean()),
                 'sensory_corr_before': float(cos_src.mean()),
                 'sensory_corr_after': float(cos_trans.mean()),
                 'defect_flags_before': float(viol_src.mean()),
                 'defect_flags_after': float(viol_trans.mean()),
                 'non_worsen_rate': float(np.mean((D_trans[:, :4] <= D_src[:, :4] + 1e-6).all(axis=1)))},
    'fingerprint': fingerprint,
}
dump_json(summary, 'Q3_summary.json')
log('问题 3 完成，用时 %.1fs' % (time.time() - t0))


