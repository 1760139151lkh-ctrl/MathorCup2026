# -*- coding: utf-8 -*-
"""26_redraw_figures.py —— 用已保存的结果重绘问题 1 相关图（去掉图内编号标题，统一由论文图题标注）"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
plt = setup_cn_font()

q1cv = pd.read_csv(os.path.join(RES, 'Q1_cv_model_comparison.csv'))
dim = pd.read_csv(os.path.join(RES, 'Q1_dim_metrics.csv'))
sens = pd.read_csv(os.path.join(DP, 'sensory_z.csv'), encoding='utf-8-sig')
pred = pd.read_csv(os.path.join(RES, 'Q1_pred_z.csv'), encoding='utf-8-sig')
grades = pd.read_csv(os.path.join(RES, 'Q1_pred_grades_0to6.csv'), encoding='utf-8-sig')
rob = pd.read_csv(os.path.join(RES, 'Q1_missing_robustness.csv'))
sim = pd.read_csv(os.path.join(RES, 'Q1_inversion_simulation.csv'))
rep = json.load(open(os.path.join(RES, '20_data_report.json'), encoding='utf-8'))
S = [c for c in sens.columns if c not in ('beer', 'beer_id', 'tasting_category_fine')]
styles = sens['tasting_category_fine'].values
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

# 1) 模型比较
fig, ax = plt.subplots(figsize=(8.6, 4.2))
cvp = q1cv.sort_values('R2_mean')
bars = ax.barh(cvp['model'], cvp['R2_mean'], xerr=cvp['R2_std_across_repeats'],
               color='#4C72B0', alpha=.85, error_kw=dict(ecolor='#333', lw=1, capsize=3))
ax.axvline(0, color='k', lw=.8)
ax.set_xlabel('交叉验证平均 $R^2$（50 个感官维度）')
for b, v in zip(bars, cvp['R2_mean']):
    ax.text(v + 0.004 if v >= 0 else v - 0.004, b.get_y() + b.get_height() / 2,
            f'{v:.3f}', va='center', ha='left' if v >= 0 else 'right', fontsize=9)
savefig(fig, 'fig_q1_model_comparison.png'); plt.close(fig)

# 2) 逐维度 R²
fig, ax = plt.subplots(figsize=(11, 5))
dm = dim.sort_values('R2', ascending=False)
colors = {'Aroma': '#4C72B0', 'Flavour': '#DD8452', 'Other': '#55A868'}
ax.bar(range(len(dm)), dm['R2'], color=[colors[g] for g in dm['group']])
ax.set_xticks(range(len(dm)))
ax.set_xticklabels(dm['dim_cn'], rotation=90, fontsize=7)
ax.set_ylabel('$R^2$')
for g in colors:
    ax.bar([0], [0], color=colors[g],
           label={'Aroma': '香气 Aroma', 'Flavour': '风味 Flavour', 'Other': '其他'}[g])
ax.legend(frameon=False)
savefig(fig, 'fig_q1_dim_r2.png'); plt.close(fig)

# 3) 预测散点
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
CN = {'A_hops_all': '酒花香-总', 'bitternes': '苦度', 'overall': '总体喜好'}
Y = sens[S].values
P = pred[['pred_' + c for c in S]].values
for ax, c in zip(axes, ['A_hops_all', 'bitternes', 'overall']):
    j = S.index(c)
    ax.scatter(Y[:, j], P[:, j], s=10, alpha=.55, color='#4C72B0')
    lim = [min(Y[:, j].min(), P[:, j].min()), max(Y[:, j].max(), P[:, j].max())]
    ax.plot(lim, lim, 'k--', lw=1)
    ax.set_xlabel('实测 z 值'); ax.set_ylabel('预测 z 值')
    ax.set_title('%s (R²=%.2f)' % (CN[c], dim.set_index('dim').loc[c, 'R2']))
savefig(fig, 'fig_q1_pred_scatter.png'); plt.close(fig)

# 4) 风格 × 维度等级热图
AF = [c for c in S if c.startswith(('A_', 'F_'))]
CN50 = dict(zip(dim['dim'], dim['dim_cn']))
grp = grades.set_index(pd.Index(styles, name='style'))[AF].groupby('style').mean()
grp = grp.loc[[s for s in STYLE_ORDER if s in grp.index]]
fig, ax = plt.subplots(figsize=(11.5, 6.2))
im = ax.imshow(grp.values, aspect='auto', cmap='YlOrRd', vmin=0, vmax=4)
ax.set_xticks(range(len(AF))); ax.set_xticklabels([CN50[c] for c in AF], rotation=90, fontsize=7)
ax.set_yticks(range(len(grp))); ax.set_yticklabels([STYLE_CN[s] for s in grp.index], fontsize=8)
plt.colorbar(im, ax=ax, label='平均等级')
savefig(fig, 'fig_q1_style_grade_heatmap.png'); plt.close(fig)

# 5) 等级分布
fig, ax = plt.subplots(figsize=(11.5, 4.2))
G = grades[S].values.astype(int)
mat = np.array([np.bincount(G[:, j], minlength=7) / len(G) for j in range(len(S))]).T
im = ax.imshow(mat, aspect='auto', cmap='Blues', origin='lower')
ax.set_yticks(range(7)); ax.set_yticklabels(['0 未见', '1', '2', '3', '4', '5', '6 极强'])
ax.set_xticks(range(len(S))); ax.set_xticklabels([CN50[c] for c in S], rotation=90, fontsize=6)
plt.colorbar(im, ax=ax, label='样本占比')
savefig(fig, 'fig_q1_grade_distribution.png'); plt.close(fig)

# 6) 缺失鲁棒性
fig, ax = plt.subplots(figsize=(7, 4.2))
for mname, sub in rob.groupby('model'):
    sub = sub.sort_values('missing_rate')
    ax.plot(sub['missing_rate'] * 100, sub['R2_mean'], marker='o', label=mname)
ax.set_xlabel('测试集特征随机缺失率 (%)'); ax.set_ylabel('平均 $R^2$')
ax.legend(frameon=False, fontsize=8)
savefig(fig, 'fig_q1_missing_robustness.png'); plt.close(fig)

# 7) 反演仿真验证
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
ax = axes[0]
for key, sub in sim.groupby('n_taster'):
    ax.scatter(sub['exact'], sub['within1'], s=22, label='品评员 %d 人' % key)
ax.set_xlabel('等级完全一致率'); ax.set_ylabel('±1 级以内一致率')
ax.set_title('(a) 仿真实验的等级恢复精度'); ax.legend(frameon=False, fontsize=8)
ax = axes[1]
fits = rep['ordinal_fits']
nlev = [int(np.sum(np.array(f['w']) > 0.02)) for f in fits.values()]
bvals = [f['b'] for f in fits.values()]
ax.scatter(nlev, bvals, s=24, color='#4C72B0')
ax.set_xlabel('有效等级数（权重>0.02）'); ax.set_ylabel('等级步长 b')
ax.set_title('(b) 50 个感官维度的反演参数')
savefig(fig, 'fig_q1_inversion_validation.png'); plt.close(fig)
print('Q1 figures redrawn')
