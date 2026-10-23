# -*- coding: utf-8 -*-
"""common.py —— 2026 MathorCup 大数据竞赛 A 赛道（DeepSeek 队）公共模块
功能：路径常量、数据加载、秩-高斯变换、缺失填补、风格标签、0–6 序数反演、绘图风格。
AI 辅助说明：本文件由 DeepSeek-V3.2 (deepseek) 辅助编写，2026-10-23；人工核验并修改。
"""
import os, sys, io, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# ---------------- paths ----------------
BASE = r"C:\Users\17601\Desktop\MathorCup"
ATT = os.path.join(BASE, "03_A赛道", "01_附件")
WORK = os.path.join(BASE, "DeepSeek_A")
DP = os.path.join(WORK, "data_processed")
RES = os.path.join(WORK, "results")
FIG = os.path.join(WORK, "figures")
for d in (DP, RES, FIG):
    os.makedirs(d, exist_ok=True)

META_COLS = ['beer', 'beer_id', 'tasting_category_fine']

# ---------------- sensory dimension metadata ----------------
SENS_CN = {
    'A_malt_all': '麦芽香-总', 'A_malt_grain': '麦芽香-谷物', 'A_malt_bread': '麦芽香-面包',
    'A_malt_cara': '麦芽香-焦糖', 'A_malt_burn': '麦芽香-烟熏',
    'A_hops_all': '酒花香-总', 'A_hops_citrus': '酒花香-柑橘', 'A_hops_tropical': '酒花香-热带水果',
    'A_hops_noble': '酒花香-草本干草', 'A_hops_woody': '酒花香-木质松脂',
    'A_esters_all': '酯香-总', 'A_esters_ethac': '酯香-溶剂指甲油', 'A_esters_isoaa': '酯香-香蕉',
    'A_esters_flower': '酯香-花香', 'A_esters_fruity': '酯香-果香',
    'F_malt_all': '麦芽味-总', 'F_malt_grain': '麦芽味-谷物', 'F_malt_bread': '麦芽味-面包',
    'F_malt_cara': '麦芽味-焦糖', 'F_malt_burn': '麦芽味-烟熏',
    'F_hops_all': '酒花味-总', 'F_hops_citrus': '酒花味-柑橘', 'F_hops_tropical': '酒花味-热带水果',
    'F_hops_noble': '酒花味-草本干草', 'F_hops_woody': '酒花味-木质松脂',
    'F_esters_all': '酯味-总', 'F_esters_ethac': '酯味-溶剂指甲油', 'F_esters_isoaa': '酯味-香蕉',
    'F_esters_flower': '酯味-花香', 'F_esters_fruity': '酯味-果香',
    'acidity': '酸度', 'bitternes': '苦度', 'sweetness': '甜度', 'X4vg': '4-乙烯基愈创木酚',
    'diacetyl': '双乙酰', 'dms': '二甲基硫', 'metallic': '金属味', 'stale_hops': '陈酒花味',
    't2n': '反-2-壬烯醛', 'orange': '橙味', 'coriander': '芫荽', 'clove': '丁香',
    'lactic': '乳酸味', 'acetic': '乙酸味', 'barnyard': '畜棚味', 'alcohol': '酒精感',
    'aftertaste': '后味', 'body': '酒体', 'co2': '碳酸感', 'overall': '总体喜好',
}
SENS_GROUP = {**{k: 'Aroma' for k in SENS_CN if k.startswith('A_')},
              **{k: 'Flavour' for k in SENS_CN if k.startswith('F_')},
              **{k: 'Other' for k in SENS_CN if not (k.startswith('A_') or k.startswith('F_'))}}
A_F_COLS = [c for c in SENS_CN if c.startswith(('A_', 'F_'))]
OTHER_COLS = [c for c in SENS_CN if c not in A_F_COLS]

STYLE_ORDER = ['Blond', 'Tripel', 'Strong ale', 'Hoppy', 'Stout/Porter', 'Wheat', 'Amber',
               'Brown', 'Pils/Lager', 'Lambic', 'Dubbel', 'Kriek', 'Saison', 'Christmas',
               'Low/No alcohol', 'Fruitbeer', 'West Flanders ale', 'Brett/cofermented',
               'Flanders old brown', 'Scotch', 'Brut', 'Faro']
STYLE_CN = {'Blond': '金色', 'Tripel': '三料', 'Strong ale': '烈性艾尔', 'Hoppy': '酒花型',
            'Stout/Porter': '世涛/波特', 'Wheat': '小麦', 'Amber': '琥珀', 'Brown': '棕色',
            'Pils/Lager': '皮尔森/拉格', 'Lambic': '兰比克', 'Dubbel': '双料', 'Kriek': '樱桃',
            'Saison': '赛松', 'Christmas': '圣诞', 'Low/No alcohol': '无/低醇',
            'Fruitbeer': '果啤', 'West Flanders ale': '西佛兰德', 'Brett/cofermented': '布雷特',
            'Flanders old brown': '佛兰德老棕', 'Scotch': '苏格兰', 'Brut': '天然干型', 'Faro': '法罗'}


# ---------------- data loading ----------------
def load_raw():
    """读取附件 1/2/4/5/6/7/8，返回 dict。原始文件不做任何修改。"""
    d = {}
    d['chem'] = pd.read_csv(os.path.join(ATT, '1.csv'), encoding='utf-8')
    d['chem_corr'] = pd.read_csv(os.path.join(ATT, '2.csv'), encoding='utf-8', index_col=0)
    d['sens'] = pd.read_csv(os.path.join(ATT, '4.csv'), encoding='utf-8')
    d['sens_corr'] = pd.read_csv(os.path.join(ATT, '5.csv'), encoding='utf-8', index_col=0)
    d['cross_corr'] = pd.read_csv(os.path.join(ATT, '6.csv'), encoding='utf-8', index_col=0)
    d['reviews'] = pd.read_csv(os.path.join(ATT, '7.csv'), encoding='utf-8')
    x8 = pd.ExcelFile(os.path.join(ATT, '8.xlsx'))
    d['sens_names'] = pd.read_excel(x8, sheet_name='Sensory names')
    d['thresholds'] = pd.read_excel(x8, sheet_name='Sensory thresholds')
    d['calibrated'] = pd.read_excel(x8, sheet_name='Calibrated chemical dataset')
    d['gbm_imp'] = pd.read_excel(x8, sheet_name='GBM importance MDI')
    d['prices'] = pd.read_excel(x8, sheet_name='Beer Prices')
    return d


def chem_cols(df):
    return [c for c in df.columns if c not in META_COLS]


def sens_cols(df):
    return [c for c in df.columns if c not in META_COLS]


# ---------------- transforms ----------------
class RankGauss:
    """秩-高斯（分位数-正态）变换，单调、对异常值稳健，并支持逆变换。

    对每个特征：rank -> 分位 u=(rank-0.5)/n -> z=Phi^{-1}(u)
    逆变换：给定 z -> u -> 在原特征经验分布上线性插值
    """

    def __init__(self):
        self.fitted = False

    def fit(self, X):
        from scipy.stats import norm
        X = np.asarray(X, dtype=float)
        self.n, self.p = X.shape
        self.sorted = np.sort(X, axis=0)
        self.z_sorted = norm.ppf((np.arange(self.n) + 0.5) / self.n)
        self.fitted = True
        return self

    def transform(self, X):
        from scipy.stats import norm
        X = np.asarray(X, dtype=float)
        out = np.empty_like(X)
        for j in range(self.p):
            # 用搜索插入位置得到秩，再插值到正态分位
            idx = np.searchsorted(self.sorted[:, j], X[:, j], side='left')
            idx = np.clip(idx, 0, self.n - 1)
            out[:, j] = self.z_sorted[idx]
        return out

    def fit_transform(self, X):
        self.fit(X)
        return self.transform(X)

    def inverse(self, Z):
        from scipy.stats import norm
        Z = np.asarray(Z, dtype=float)
        out = np.empty_like(Z)
        u = norm.cdf(Z)
        for j in range(self.p):
            out[:, j] = np.interp(u[:, j], (np.arange(self.n) + 0.5) / self.n, self.sorted[:, j])
        return out


def knn_impute(X, k=5):
    """KNN 缺失填补（基于特征间距离），返回填补后的矩阵。"""
    from sklearn.impute import KNNImputer
    if not np.isnan(X).any():
        return X.copy()
    imp = KNNImputer(n_neighbors=k, weights='distance')
    return imp.fit_transform(X)


def winsorize(X, lo=0.5, hi=99.5):
    """按分位数缩尾，抑制真实异常值对线性模型的影响。"""
    X = np.asarray(X, dtype=float).copy()
    a = np.nanpercentile(X, lo, axis=0)
    b = np.nanpercentile(X, hi, axis=0)
    return np.clip(X, a, b)


# ---------------- ordinal 0-6 inversion ----------------
def fit_ordinal_inversion(y, K=7, n_grid=10, n_iter=120, seed=0):
    """将标准化感官值 y 反演为 0–6 等级。

    模型：y_i ~ sum_k w_k N(a + b*k, sigma^2)，k=0..6
    理论依据：原论文按品评员逐人 z 化后取均值，y 与真实 0–6 评分的共识值近似线性；
    等价假设"0–6 等级"为等距潜变量，各等级间存在品评员个体差异造成的正态噪声。
    两阶段网格搜索 + EM 估计，兼顾精度与速度。
    返回 dict(a, b, sigma, w, ll, grade, prob)。
    """
    from scipy.stats import norm
    y = np.asarray(y, dtype=float)
    y = y[np.isfinite(y)]
    ymin, ymax = np.min(y), np.max(y)
    rng = ymax - ymin
    ks = np.arange(K, dtype=float)

    def em(a, b, sigma, n_it):
        mu = a + b * ks
        w = np.ones(K) / K
        ll_old = -np.inf
        for _ in range(n_it):
            logp = np.log(w + 1e-12)[None, :] + norm.logpdf(y[:, None], mu[None, :], sigma)
            m = logp.max(axis=1, keepdims=True)
            resp = np.exp(logp - m)
            s = resp.sum(axis=1, keepdims=True)
            ll = float((np.log(s) + m).sum())
            sw = resp / s
            w = sw.mean(axis=0)
            N = sw.sum()
            Sk = (sw * ks[None, :]).sum()
            Skk = (sw * ks[None, :] ** 2).sum()
            Sy = (sw * y[:, None]).sum()
            Syk = (sw * y[:, None] * ks[None, :]).sum()
            det = N * Skk - Sk * Sk
            a_new = (Sy * Skk - Sk * Syk) / det
            b_new = (N * Syk - Sk * Sy) / det
            if b_new <= 1e-6:
                b_new = 1e-6
            mu_new = a_new + b_new * ks
            var = (sw * (y[:, None] - mu_new[None, :]) ** 2).sum() / max(N, 1e-12)
            sigma = max(np.sqrt(var), 0.02 * rng)
            a, b = a_new, b_new
            if abs(ll - ll_old) < 1e-8:
                break
            ll_old = ll
        return dict(a=a, b=b, sigma=sigma, w=w.copy(), ll=ll)

    # 阶段一：粗网格（少量迭代）
    best = None
    for a0 in np.linspace(ymin - 0.1 * rng, ymin + 0.7 * rng, n_grid):
        for b0 in np.linspace(0.12 * rng, 0.85 * rng, n_grid):
            r = em(a0, b0, 0.3 * b0 + 1e-9, 25)
            if best is None or r['ll'] > best['ll']:
                best = r
    # 阶段二：在最优解附近细化
    a_c, b_c = best['a'], best['b']
    span = rng / 25
    for a0 in np.linspace(a_c - 4 * span, a_c + 4 * span, 7):
        for b0 in np.linspace(max(0.05 * rng, b_c - 4 * span), b_c + 4 * span, 7):
            r = em(a0, b0, best['sigma'], n_iter)
            if r['ll'] > best['ll']:
                best = r

    a, b, sigma, w = best['a'], best['b'], best['sigma'], best['w']
    mu = a + b * ks
    x = (y - a) / b
    grade = np.clip(np.round(x), 0, 6).astype(int)
    logp = np.log(w + 1e-12)[None, :] + norm.logpdf(y[:, None], mu[None, :], sigma)
    logp -= logp.max(axis=1, keepdims=True)
    prob = np.exp(logp)
    prob /= prob.sum(axis=1, keepdims=True)
    best.update(mu=mu, x=x, grade=grade, prob=prob)
    return best


def predict_grades(z_pred, fit):
    """用已拟合的反演参数把连续值转换为 0–6 等级。"""
    x = (np.asarray(z_pred) - fit['a']) / fit['b']
    return np.clip(np.round(x), 0, 6).astype(int)


# ---------------- metrics ----------------
def r2_scores(Y_true, Y_pred):
    """逐列 R^2（不依赖 sklearn 的多输出细节）。"""
    Y_true = np.asarray(Y_true); Y_pred = np.asarray(Y_pred)
    ss_res = ((Y_true - Y_pred) ** 2).sum(axis=0)
    ss_tot = ((Y_true - Y_true.mean(axis=0)) ** 2).sum(axis=0)
    return 1 - ss_res / np.maximum(ss_tot, 1e-12)


def spearman_matrix(A, B):
    """A,B: n×p, n×q -> p×q Spearman 相关矩阵。"""
    from scipy.stats import rankdata
    Ar = np.apply_along_axis(rankdata, 0, A)
    Br = np.apply_along_axis(rankdata, 0, B)
    Ar = (Ar - Ar.mean(0)) / (Ar.std(0) + 1e-12)
    Br = (Br - Br.mean(0)) / (Br.std(0) + 1e-12)
    return (Ar.T @ Br) / A.shape[0]


# ---------------- plotting ----------------
def setup_cn_font():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.dpi'] = 120
    plt.rcParams['savefig.dpi'] = 220
    plt.rcParams['savefig.bbox'] = 'tight'
    plt.rcParams['axes.grid'] = True
    plt.rcParams['grid.alpha'] = 0.25
    plt.rcParams['font.size'] = 10
    return plt


def savefig(fig, name, tight=True):
    path = os.path.join(FIG, name)
    fig.savefig(path, dpi=220, bbox_inches='tight')
    return path


def dump_json(obj, name):
    def conv(o):
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.floating,)): return float(o)
        if isinstance(o, np.ndarray): return o.tolist()
        return str(o)
    with open(os.path.join(RES, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=conv)


def log(*a):
    print(*a, flush=True)
