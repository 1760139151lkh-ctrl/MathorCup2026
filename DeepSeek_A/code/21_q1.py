# -*- coding: utf-8 -*-
"""21_q1.py —— 问题 1：数据缺失条件下的感官评分（化合物 → 约 50 个感官维度 0–6 级）
流程：
  1) 读取秩-高斯变换后的 231 维化学特征与 50 维感官标签；
  2) 以风格分层、重复 5 折交叉验证比较 8 种模型（含缺失率鲁棒性实验）；
  3) 选出最优模型，输出全部 250 个样本的交叉验证外推预测（z 值）与 0–6 等级；
  4) 保存指标、预测表与图件。
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import RidgeCV, MultiTaskLassoCV
from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.impute import KNNImputer
from sklearn.base import clone

plt = setup_cn_font()
t0 = time.time()

chem = pd.read_csv(os.path.join(DP, 'chem_features.csv'), encoding='utf-8-sig')
sens = pd.read_csv(os.path.join(DP, 'sensory_z.csv'), encoding='utf-8-sig')
C = chem_cols(chem)
S = sens_cols(sens)
X = chem[C].values.astype(float)
Y = sens[S].values.astype(float)
styles = chem['tasting_category_fine'].values
n, p = X.shape
q = Y.shape[1]
log('X', X.shape, 'Y', Y.shape)

# 分层标签：稀有风格合并，保证每折该层至少 2 个样本
vc = pd.Series(styles).value_counts()
strat = np.array([s if vc[s] >= 10 else 'Rare' for s in styles])

# ---------------- 模型库 ----------------
def make_models():
    return {
        'Ridge-多输出': RidgeCV(alphas=np.logspace(-2, 3, 12)),
        '多任务Lasso': MultiTaskLassoCV(alphas=np.logspace(-4, 0, 25), cv=3, max_iter=8000),
        'PLS-潜变量': PLSRegression(n_components=15, scale=False),
        '随机森林': RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                       max_features='sqrt', n_jobs=1, random_state=0),
        '极端随机树': ExtraTreesRegressor(n_estimators=400, min_samples_leaf=1,
                                      max_features=0.5, n_jobs=1, random_state=0),
        '梯度提升': MultiOutputRegressor(
            GradientBoostingRegressor(n_estimators=150, learning_rate=0.05, max_depth=2,
                                      subsample=0.8, random_state=0)),
        '多层感知机': MultiOutputRegressor(
            MLPRegressor(hidden_layer_sizes=(64, 32), alpha=0.6, learning_rate_init=5e-3,
                         max_iter=600, early_stopping=True, n_iter_no_change=25,
                         random_state=0)),
        '均值基线': None,
    }

# ---------------- 交叉验证 ----------------
N_REPEATS = 3
N_FOLDS = 5
models = make_models()
oof = {m: np.zeros((n, q, N_REPEATS)) for m in models}
oof_mask = {m: np.zeros((n,), dtype=int) for m in models}

for rep in range(N_REPEATS):
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=100 + rep)
    for fold, (tr, te) in enumerate(skf.split(X, strat)):
        for mname, model in models.items():
            if model is None:
                pred = np.tile(Y[tr].mean(axis=0), (len(te), 1))
            else:
                mdl = clone(model)
                mdl.fit(X[tr], Y[tr])
                pred = np.asarray(mdl.predict(X[te]))
                if pred.ndim == 1:
                    pred = pred[:, None]
            oof[mname][te, :, rep] = pred
        oof_mask['Ridge-多输出'][te] += 1
    log('repeat %d/%d done  %.1fs' % (rep + 1, N_REPEATS, time.time() - t0))

# 汇总指标（每次重复单独算 R²，再取均值±标准差）
cv_rows = []
for mname in models:
    r2_rep = []
    for rep in range(N_REPEATS):
        r2_rep.append(r2_scores(Y, oof[mname][:, :, rep]))
    r2_rep = np.array(r2_rep)
    cv_rows.append({'model': mname,
                    'R2_mean': float(np.nanmean(r2_rep)),
                    'R2_std_across_repeats': float(np.nanmean(np.nanstd(r2_rep, axis=0))),
                    'R2_median_dim': float(np.nanmedian(np.nanmean(r2_rep, axis=0))),
                    'n_dim_R2>0.2': int((np.nanmean(r2_rep, axis=0) > 0.2).sum()),
                    'n_dim_R2>0': int((np.nanmean(r2_rep, axis=0) > 0).sum())})
cv = pd.DataFrame(cv_rows).sort_values('R2_mean', ascending=False)
log('\n' + cv.to_string(index=False))
cv.to_csv(os.path.join(RES, 'Q1_cv_model_comparison.csv'), index=False, encoding='utf-8-sig')

# ---------------- 缺失率鲁棒性实验 ----------------
# 在主模型（极端随机树）与 Ridge 上，对测试折随机遮蔽一定比例特征后 KNN 填补再预测
miss_rates = [0.0, 0.05, 0.10, 0.20, 0.30]
robust_results = []
for mname in ['极端随机树', '梯度提升', 'Ridge-多输出']:
    model = models[mname]
    for rate in miss_rates:
        rng = np.random.default_rng(2026)
        r2_all = []
        for rep in range(2):
            skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=300 + rep)
            pred_all = np.zeros_like(Y)
            for tr, te in skf.split(X, strat):
                Xtr, Xte = X[tr].copy(), X[te].copy()
                if rate > 0:
                    mask = rng.random(Xte.shape) < rate
                    Xte[mask] = np.nan
                    imp = KNNImputer(n_neighbors=5, weights='distance')
                    imp.fit(Xtr)
                    Xte = imp.transform(Xte)
                mdl = clone(model)
                mdl.fit(Xtr, Y[tr])
                pred_all[te] = np.asarray(mdl.predict(Xte))
            r2_all.append(r2_scores(Y, pred_all))
        r2_all = np.array(r2_all)
        robust_results.append({'model': mname, 'missing_rate': rate,
                               'R2_mean': float(np.nanmean(r2_all)),
                               'R2_retention': float(np.nanmean(r2_all) / max(np.nanmean(r2_all[0]), 1e-9))})
        log('缺失鲁棒性 %-14s rate=%.2f  R2=%.4f' % (mname, rate, np.nanmean(r2_all)))
rob = pd.DataFrame(robust_results)
rob.to_csv(os.path.join(RES, 'Q1_missing_robustness.csv'), index=False, encoding='utf-8-sig')

# ---------------- 选最优模型，生成 OOF 预测 ----------------
best_name = cv.iloc[0]['model']
log('\n最优模型：', best_name)
pred_z = oof[best_name].mean(axis=2)          # 多次重复平均的 OOF 预测
pred_z_std = oof[best_name].std(axis=2)

# 逐维度指标
r2_dim = r2_scores(Y, pred_z)
mae_dim = np.mean(np.abs(Y - pred_z), axis=0)
from scipy.stats import spearmanr
rho_dim = np.array([spearmanr(Y[:, j], pred_z[:, j]).statistic for j in range(q)])
dim_metrics = pd.DataFrame({
    'dim': S, 'dim_cn': [SENS_CN[c] for c in S], 'group': [SENS_GROUP[c] for c in S],
    'R2': r2_dim, 'MAE': mae_dim, 'Spearman': rho_dim,
})
dim_metrics.sort_values('R2', ascending=False).to_csv(
    os.path.join(RES, 'Q1_dim_metrics.csv'), index=False, encoding='utf-8-sig')
log('逐维度 R²：均值 %.4f，中位数 %.4f，最大 %.4f (%s)，最小 %.4f (%s)'
    % (np.nanmean(r2_dim), np.nanmedian(r2_dim), np.nanmax(r2_dim),
       S[int(np.nanargmax(r2_dim))], np.nanmin(r2_dim), S[int(np.nanargmin(r2_dim))]))

# ---------------- 0–6 等级转换 ----------------
report = json.load(open(os.path.join(RES, '20_data_report.json'), encoding='utf-8'))
ordinal = report['ordinal_fits']
grade_pred = np.zeros((n, q), dtype=int)
grade_true = np.zeros((n, q), dtype=int)
for j, c in enumerate(S):
    fit = ordinal[c]
    grade_pred[:, j] = np.clip(np.round((pred_z[:, j] - fit['a']) / fit['b']), 0, 6).astype(int)
    grade_true[:, j] = np.clip(np.round((Y[:, j] - fit['a']) / fit['b']), 0, 6).astype(int)

# 等级一致性评价（模拟实验见 25_inversion_validation.py）
grade_acc = float(np.mean(grade_pred == grade_true))
grade_within1 = float(np.mean(np.abs(grade_pred - grade_true) <= 1))
grade_mae = float(np.mean(np.abs(grade_pred - grade_true)))
log('等级预测：完全一致 %.3f，±1 以内 %.3f，MAE %.3f' % (grade_acc, grade_within1, grade_mae))

# 保存预测结果
pred_z_df = sens[['beer', 'tasting_category_fine']].copy()
for j, c in enumerate(S):
    pred_z_df['pred_' + c] = pred_z[:, j]
pred_z_df.to_csv(os.path.join(RES, 'Q1_pred_z.csv'), index=False, encoding='utf-8-sig')

grade_df = sens[['beer', 'tasting_category_fine']].copy()
for j, c in enumerate(S):
    grade_df[c] = grade_pred[:, j]
grade_df.to_csv(os.path.join(RES, 'Q1_pred_grades_0to6.csv'), index=False, encoding='utf-8-sig')

# 长表：样本 × 维度 × 0–6 等级（便于附件提交）
long = grade_df.melt(id_vars=['beer', 'tasting_category_fine'], var_name='dim', value_name='grade_0to6')
long['dim_cn'] = long['dim'].map(SENS_CN)
long['group'] = long['dim'].map(SENS_GROUP)
long.sort_values(['beer', 'group', 'dim']).to_csv(
    os.path.join(RES, 'Q1_pred_grades_long.csv'), index=False, encoding='utf-8-sig')

# 整体指标存档
model_card = {
    'best_model': best_name,
    'cv': cv.to_dict(orient='records'),
    'cv_protocol': '%d 次重复 %d 折（按风格分层）交叉验证' % (N_REPEATS, N_FOLDS),
    'overall_R2': float(np.nanmean(r2_dim)),
    'overall_R2_AF': float(np.nanmean(r2_dim[[S.index(c) for c in A_F_COLS]])),
    'grade_exact_agreement': grade_acc,
    'grade_within1_agreement': grade_within1,
    'grade_MAE': grade_mae,
    'missing_robustness': rob.to_dict(orient='records'),
    'n_samples': n, 'n_features': p, 'n_dims': q,
}
dump_json(model_card, 'Q1_model_card.json')

# ---------------- 图 ----------------
# 1. 模型比较
fig, ax = plt.subplots(figsize=(8.6, 4.2))
cvp = cv.sort_values('R2_mean')
bars = ax.barh(cvp['model'], cvp['R2_mean'],
               xerr=cvp['R2_std_across_repeats'], color='#4C72B0', alpha=.85,
               error_kw=dict(ecolor='#333', lw=1, capsize=3))
ax.axvline(0, color='k', lw=.8)
ax.set_xlabel('交叉验证平均 $R^2$（50 个感官维度）')
ax.set_title('图 1  各回归模型的交叉验证性能比较')
for b, v in zip(bars, cvp['R2_mean']):
    ax.text(v + 0.004, b.get_y() + b.get_height() / 2, f'{v:.3f}', va='center', fontsize=9)
savefig(fig, 'fig_q1_model_comparison.png'); plt.close(fig)

# 2. 逐维度 R²
fig, ax = plt.subplots(figsize=(11, 5))
dm = dim_metrics.sort_values('R2', ascending=False)
colors = {'Aroma': '#4C72B0', 'Flavour': '#DD8452', 'Other': '#55A868'}
ax.bar(range(q), dm['R2'], color=[colors[g] for g in dm['group']])
ax.set_xticks(range(q)); ax.set_xticklabels([SENS_CN[c] for c in dm['dim']], rotation=90, fontsize=7)
ax.set_ylabel('$R^2$'); ax.set_title('图 2  50 个感官维度的预测 $R^2$（%s）' % best_name)
for g in colors:
    ax.bar([0], [0], color=colors[g], label={'Aroma': '香气 Aroma', 'Flavour': '风味 Flavour', 'Other': '其他'}[g])
ax.legend(frameon=False)
savefig(fig, 'fig_q1_dim_r2.png'); plt.close(fig)

# 3. 预测 vs 真值（整体）
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
for ax, c in zip(axes, ['A_hops_all', 'bitternes', 'overall']):
    j = S.index(c)
    ax.scatter(Y[:, j], pred_z[:, j], s=10, alpha=.55, color='#4C72B0')
    lim = [min(Y[:, j].min(), pred_z[:, j].min()), max(Y[:, j].max(), pred_z[:, j].max())]
    ax.plot(lim, lim, 'k--', lw=1)
    ax.set_xlabel('实测 z 值'); ax.set_ylabel('预测 z 值')
    ax.set_title('%s (R²=%.2f)' % (SENS_CN[c], r2_dim[j]))
fig.suptitle('图 3  典型感官维度的交叉验证预测效果', y=1.02)
savefig(fig, 'fig_q1_pred_scatter.png'); plt.close(fig)

# 4. 0–6 等级分布热图（风格 × 维度，取 A/F 维度）
fig, ax = plt.subplots(figsize=(11, 6))
grp = pd.DataFrame(grade_pred, columns=S).assign(style=styles).groupby('style')[A_F_COLS].mean()
grp = grp.loc[[s for s in STYLE_ORDER if s in grp.index]]
im = ax.imshow(grp.values, aspect='auto', cmap='YlOrRd', vmin=0, vmax=4)
ax.set_xticks(range(len(A_F_COLS))); ax.set_xticklabels([SENS_CN[c] for c in A_F_COLS], rotation=90, fontsize=7)
ax.set_yticks(range(len(grp))); ax.set_yticklabels([STYLE_CN[s] for s in grp.index], fontsize=8)
ax.set_title('图 4  不同啤酒风格 30 个香气/风味维度的平均预测等级（0–6）')
plt.colorbar(im, ax=ax, label='平均等级')
savefig(fig, 'fig_q1_style_grade_heatmap.png'); plt.close(fig)

# 5. 缺失率鲁棒性
fig, ax = plt.subplots(figsize=(7, 4.2))
for mname, sub in rob.groupby('model'):
    sub = sub.sort_values('missing_rate')
    ax.plot(sub['missing_rate'] * 100, sub['R2_mean'], marker='o', label=mname)
ax.set_xlabel('测试集特征随机缺失率 (%)'); ax.set_ylabel('平均 $R^2$')
ax.set_title('图 5  不同缺失率下的预测性能（KNN 填补）')
ax.legend(frameon=False, fontsize=8)
savefig(fig, 'fig_q1_missing_robustness.png'); plt.close(fig)

log('问题 1 完成，用时 %.1fs' % (time.time() - t0))
