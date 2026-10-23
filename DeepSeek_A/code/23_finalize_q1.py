# -*- coding: utf-8 -*-
"""23_finalize_q1.py —— 问题 1 收尾：
  1) 用最终版反演参数重算 0–6 等级与一致性指标；
  2) 生成 3.xlsx 官方评分表格式的预测结果（12 款啤酒 × 50 个维度，含 summary 汇总表）；
  3) 重绘风格×维度等级热图。
"""
import sys, os, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import openpyxl
plt = setup_cn_font()

sens = pd.read_csv(os.path.join(DP, 'sensory_z.csv'), encoding='utf-8-sig')
pred = pd.read_csv(os.path.join(RES, 'Q1_pred_z.csv'), encoding='utf-8-sig')
S = sens_cols(sens)
Y = sens[S].values.astype(float)
P = pred[['pred_' + c for c in S]].values.astype(float)
report = json.load(open(os.path.join(RES, '20_data_report.json'), encoding='utf-8'))
fits = report['ordinal_fits']

gp = np.zeros_like(Y, dtype=int)
gt = np.zeros_like(Y, dtype=int)
cont = np.zeros_like(Y)
for j, c in enumerate(S):
    f = fits[c]
    gp[:, j] = np.clip(np.round((P[:, j] - f['a']) / f['b']), 0, 6).astype(int)
    gt[:, j] = np.clip(np.round((Y[:, j] - f['a']) / f['b']), 0, 6).astype(int)
    cont[:, j] = (P[:, j] - f['a']) / f['b']

metrics = {
    'grade_exact_agreement': float(np.mean(gp == gt)),
    'grade_within1_agreement': float(np.mean(np.abs(gp - gt) <= 1)),
    'grade_MAE': float(np.mean(np.abs(gp - gt))),
    'grade_spearman': float(np.mean([np.corrcoef(gp[:, j], P[:, j])[0, 1] for j in range(len(S))])),
    'distribution': {c: np.bincount(gp[:, j], minlength=7).tolist() for j, c in enumerate(S)},
}
log('等级一致性：完全一致 %.3f  ±1 以内 %.3f  MAE %.3f'
    % (metrics['grade_exact_agreement'], metrics['grade_within1_agreement'], metrics['grade_MAE']))

# 更新 model_card
card = json.load(open(os.path.join(RES, 'Q1_model_card.json'), encoding='utf-8'))
card.update(metrics)
dump_json(card, 'Q1_model_card.json')

# 保存等级预测
gdf = sens[['beer', 'tasting_category_fine']].copy()
for j, c in enumerate(S):
    gdf[c] = gp[:, j]
gdf.to_csv(os.path.join(RES, 'Q1_pred_grades_0to6.csv'), index=False, encoding='utf-8-sig')
long = gdf.melt(id_vars=['beer', 'tasting_category_fine'], var_name='dim', value_name='grade_0to6')
long['dim_cn'] = long['dim'].map(SENS_CN)
long['group'] = long['dim'].map(SENS_GROUP)
long.sort_values(['beer', 'group', 'dim']).to_csv(
    os.path.join(RES, 'Q1_pred_grades_long.csv'), index=False, encoding='utf-8-sig')
# 连续等级（未取整）
cdf = sens[['beer', 'tasting_category_fine']].copy()
for j, c in enumerate(S):
    cdf[c] = cont[:, j]
cdf.to_csv(os.path.join(RES, 'Q1_pred_grades_continuous.csv'), index=False, encoding='utf-8-sig')

# ---------- 填充 3.xlsx 评分表 ----------
# (pandas 行号, Aroma 列=16, Flavour 列=32) -> 维度名
ROW_MAP = [
    (6, 'A_malt_all', 'F_malt_all'), (9, 'A_malt_grain', 'F_malt_grain'),
    (11, 'A_malt_bread', 'F_malt_bread'), (13, 'A_malt_cara', 'F_malt_cara'),
    (15, 'A_malt_burn', 'F_malt_burn'), (19, 'A_hops_all', 'F_hops_all'),
    (22, 'A_hops_citrus', 'F_hops_citrus'), (24, 'A_hops_tropical', 'F_hops_tropical'),
    (26, 'A_hops_noble', 'F_hops_noble'), (28, 'A_hops_woody', 'F_hops_woody'),
    (32, 'A_esters_all', 'F_esters_all'), (35, 'A_esters_ethac', 'F_esters_ethac'),
    (37, 'A_esters_isoaa', 'F_esters_isoaa'), (39, 'A_esters_flower', 'F_esters_flower'),
    (41, 'A_esters_fruity', 'F_esters_fruity'),
    (49, 'body', 'alcohol'), (53, 'bitternes', 'sweetness'), (57, 'co2', 'acidity'),
    (61, 'aftertaste', None), (67, 'dms', 't2n'), (71, 'metallic', 'diacetyl'),
    (75, 'X4vg', 'stale_hops'), (81, 'orange', 'lactic'), (85, 'coriander', 'acetic'),
    (89, 'clove', 'barnyard'), (93, 'overall', None),
]
src = os.path.join(ATT, '3.xlsx')
dst = os.path.join(RES, 'Q1_评分表_3xlsx格式.xlsx')
shutil.copyfile(src, dst)
wb = openpyxl.load_workbook(dst)
beer_index = {int(b): i for i, b in enumerate(sens['beer'].values)}
for k in range(1, 13):
    ws = wb['beer_%d' % k]
    i = beer_index[k]
    for r, adim, fdim in ROW_MAP:
        if adim is not None:
            ws.cell(row=r + 1, column=17, value=int(gp[i, S.index(adim)]))
        if fdim is not None:
            ws.cell(row=r + 1, column=33, value=int(gp[i, S.index(fdim)]))
# summary
ws = wb['summary']
hdr = [c.value for c in ws[1]]
name_map = {h: h for h in hdr}
typo = {'A_ester_fruity': 'A_esters_fruity', 'F_ester_fruity': 'F_esters_fruity'}
for k in range(1, 13):
    i = beer_index[k]
    for jc, h in enumerate(hdr, start=1):
        if h is None:
            continue
        src_name = typo.get(h, h)
        if src_name in S:
            ws.cell(row=k + 1, column=jc, value=int(gp[i, S.index(src_name)]))
wb.save(dst)
log('已生成评分表：', dst)

# 12 款啤酒的宽表
sub = gdf[gdf['beer'] <= 12].copy()
sub.to_csv(os.path.join(RES, 'Q1_评分表_12款啤酒.csv'), index=False, encoding='utf-8-sig')

# ---------- 重绘等级分布热图 ----------
AF = A_F_COLS
grp = pd.DataFrame(gp, columns=S).assign(style=sens['tasting_category_fine'].values) \
        .groupby('style')[AF].mean()
grp = grp.loc[[s for s in STYLE_ORDER if s in grp.index]]
fig, ax = plt.subplots(figsize=(11.5, 6.2))
im = ax.imshow(grp.values, aspect='auto', cmap='YlOrRd', vmin=0, vmax=4)
ax.set_xticks(range(len(AF))); ax.set_xticklabels([SENS_CN[c] for c in AF], rotation=90, fontsize=7)
ax.set_yticks(range(len(grp))); ax.set_yticklabels([STYLE_CN[s] for s in grp.index], fontsize=8)
ax.set_title('不同啤酒风格 30 个香气/风味维度的平均预测等级（0–6）')
plt.colorbar(im, ax=ax, label='平均等级')
savefig(fig, 'fig_q1_style_grade_heatmap.png'); plt.close(fig)

# 等级分布总览
fig, ax = plt.subplots(figsize=(11.5, 4.2))
mat = np.array([np.bincount(gp[:, j], minlength=7) / len(gp) for j in range(len(S))]).T
im = ax.imshow(mat, aspect='auto', cmap='Blues', origin='lower')
ax.set_yticks(range(7)); ax.set_yticklabels(['0 未见', '1', '2', '3', '4', '5', '6 极强'])
ax.set_xticks(range(len(S))); ax.set_xticklabels([SENS_CN[c] for c in S], rotation=90, fontsize=6)
ax.set_title('50 个感官维度预测等级的样本占比（0–6）')
plt.colorbar(im, ax=ax, label='样本占比')
savefig(fig, 'fig_q1_grade_distribution.png'); plt.close(fig)
log('问题 1 收尾完成')
