# -*- coding: utf-8 -*-
"""20_dataset.py —— 数据核验、缺失处理、特征/标签构建
输出：
  data_processed/chem_features.csv      秩-高斯变换后的 231 个化学特征
  data_processed/sensory_z.csv          50 个感官维度的标准化真值（4.csv）
  data_processed/sensory_ordinal.csv    反演得到的 0–6 等级（用于问题 1 目标口径与校准）
  data_processed/feature_meta2.csv      特征元数据（来源类别、是否校准、是否 log10）
  results/20_data_report.json           数据核验统计
  data_processed/rankgauss.pkl          可逆变换器
"""
import sys, os, json, pickle, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

d = load_raw()
chem, sens, calib, th = d['chem'], d['sens'], d['calibrated'], d['thresholds']
C = chem_cols(chem)
S = sens_cols(sens)
log('化学特征', len(C), '感官维度', len(S))

# ---------- 1. 样本对齐校验 ----------
assert (chem['beer'].values == sens['beer'].values).all()
assert (chem['tasting_category_fine'].values == sens['tasting_category_fine'].values).all()
log('样本按 beer 序号 1–250 完全对齐；风格标签一致')

# ---------- 2. 2.csv 相关性类型核验（Spearman vs Pearson）----------
# 2.csv 行名 -> 1.csv 列名映射（来自 8.xlsx Sensory thresholds）
th_map = {}
for _, r in th.iterrows():
    py = str(r['field_name_python']).strip()
    for key in ('chemical_name', 'chemical_name_short'):
        k = str(r[key]).strip().lower()
        if k and k != 'nan':
            th_map[k] = py
extra = {
    'total ester compounds': 'esters_sum', 'total hop aroma compounds': 'aroma_hops_sum',
    'total acids': 'acids_sum', 'total sulfur compounds': 'sulfur_sum',
    'iso-alpha acids': 'bitterness', 'color': 'color.EBC.', 'sulfur dioxide': 'SO2.mg.L.',
    '4-vinylguaiacol': 'X4VG', 'dimethyl sulfide': 'DMS', 'diethyl sulfide': 'DES',
    'carbon disulfide': 'CS2', 'hydrogen sulfide': 'H2S', 'methanethiol': 'MeSH',
    'acetic acid': 'acetic_acid.g.L.', 'ammonia': 'ammonia.mg.L.', 'protein': 'protein.g.L.',
    'sugars': 'GFS', 'ethanol': 'ethanol..v.v.', 'carbon dioxide': 'CO2.PSI.',
    'caloric value': 'kcalperc', 'ph': 'pH', 'lactic acid': 'lactic_acid.mg.L.',
    'betaglucan': 'betaglucan.mg.L.', 'iron': 'iron', 'glycerol': 'glycerol',
    'diacetyl': 'X2.3.butanedione', '3-methylbutanal': 'X3.methylbutanal',
    'isobutyl acetate': 'isobutyl_acetate', 'phenethyl acetate': 'phenethyl_acetate',
    'isopentyl acetate': 'isopentyl_acetate', 'ethyl 3-methylbutyrate': 'ethyl_isovalerate',
    'ethyl 2-methylbutyrate': 'ethyl_2.methyl_butyrate',
    'trans-2-nonenal': 'X.E..2.nonenal', 'e-2-nonenal': 'X.E..2.nonenal',
    '(e)-2-nonenal': 'X.E..2.nonenal',
}
th_map.update({k: v for k, v in extra.items()})

def fix_mojibake(s):
    """修正 Excel/csv 中常见的 UTF-8→Latin-1 乱码（如 'Î²'→'β'）。"""
    s = str(s)
    if 'Ã' in s or 'Î' in s or 'Â' in s:
        try:
            s = s.encode('latin-1').decode('utf-8')
        except Exception:
            pass
    return s


def canon(s):
    s = fix_mojibake(str(s)).strip().lower()
    greek = {'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon',
             'μ': 'mu', 'ω': 'omega'}
    for k, v in greek.items():
        s = s.replace(k, v)
    s = s.replace('−', '-').replace('(', '').replace(')', '')
    s = re.sub(r'[^a-z0-9]+', '', s)
    # 去掉 1.csv 列名中常见的前缀 x（X1.propanol 等）
    if s.startswith('x') and len(s) > 1:
        s = s[1:]
    return s

canon_map = {}
for _, r in th.iterrows():
    py = str(r['field_name_python']).strip()
    for key in ('chemical_name', 'chemical_name_short', 'field_name_R', 'field_name_python'):
        k = canon(r[key])
        if k and k != 'nan':
            canon_map.setdefault(k, py)
    canon_map.setdefault(canon(py), py)
# 1.csv 列名自身也纳入规范化映射（如 X.E..beta.ocimene -> ebetaocimene）
for c in C:
    canon_map.setdefault(canon(c), c)

def map2to1(n):
    key = str(n).strip().lower()
    if key in th_map:
        return th_map[key]
    c = canon(n)
    if c in canon_map:
        return canon_map[c]
    # 模糊匹配兜底
    from difflib import get_close_matches
    cand = get_close_matches(c, list(canon_map.keys()), n=1, cutoff=0.88)
    if cand:
        return canon_map[cand[0]]
    return None

corr2 = d['chem_corr']
# 经核验：2.csv 的行/列顺序与 1.csv 的 231 个化学特征列顺序完全一致（逐位置对应）
pairs = list(zip(corr2.index, C))
assert len(pairs) == len(corr2) == len(C)
# 名称一致性抽查（规范化后前 3 个字符可判别）
name_ok = sum(1 for a, b in pairs if map2to1(a) == b)
log('2.csv 与 1.csv 位置一一对应；名称规范化后可确认 %d/%d 对，其余按位置对应'
    % (name_ok, len(pairs)))
Xp = chem[C].values.astype(float)
med = np.nanmedian(Xp, axis=0)
Xp = np.where(np.isnan(Xp), med[None, :], Xp)
sp = spearman_matrix(Xp, Xp)
ref = corr2.values.astype(float)
iu = np.triu_indices(len(pairs), 1)
r_spear = float(np.corrcoef(ref[iu], sp[iu])[0, 1])
mad_spear = float(np.mean(np.abs(ref[iu] - sp[iu])))
# pearson 对照
Xz = (Xp - np.nanmean(Xp, 0)) / (np.nanstd(Xp, 0) + 1e-12)
pe = np.corrcoef(np.nan_to_num(Xz), rowvar=False)
r_pear = float(np.corrcoef(ref[iu], pe[iu])[0, 1])
mad_pear = float(np.mean(np.abs(ref[iu] - pe[iu])))
log('2.csv ≈ Spearman: r=%.6f MAD=%.6f ; 2.csv vs Pearson: r=%.4f MAD=%.4f'
    % (r_spear, mad_spear, r_pear, mad_pear))

# ---------- 3. 变换底数核验：1.csv 与 8.xlsx 校准浓度 ----------
cal = calib.set_index('beer')
num_cols = [c for c in cal.columns if pd.api.types.is_numeric_dtype(cal[c]) and c in C]
logb = {}
for c in num_cols:
    a = cal[c].astype(float)
    b = chem.set_index('beer').loc[cal.index, c].astype(float)
    m = np.isfinite(a) & np.isfinite(b) & (a > 0)
    if m.sum() < 20:
        continue
    rlog10 = np.corrcoef(np.log10(a[m]), b[m])[0, 1]
    rdir = np.corrcoef(a[m], b[m])[0, 1]
    if rlog10 > 0.999:
        logb[c] = 'log10'
    elif rdir > 0.99:
        logb[c] = 'raw'
    else:
        logb[c] = 'other'
cnt = pd.Series(logb).value_counts().to_dict()
log('校准核验：1.csv 为 log10(浓度) 的参数 %d 个，与校准浓度同量纲 %d 个，其它 %d 个'
    % (cnt.get('log10', 0), cnt.get('raw', 0), cnt.get('other', 0)))

# ---------- 4. 特征元数据 ----------
origin = {}
unit = {}
calflag = {}
for c in C:
    origin[c] = 'Others'
for _, r in th.iterrows():
    py = str(r['field_name_python']).strip()
    if py in C:
        origin[py] = str(r['origin_paper']) if pd.notna(r['origin_paper']) else 'Others'
        unit[py] = str(r['unit']) if pd.notna(r['unit']) else ''
        calflag[py] = str(r['calibrated']) if pd.notna(r['calibrated']) else ''
meta = pd.DataFrame({'feature': C})
meta['origin'] = meta['feature'].map(origin).fillna('Others')
meta['unit'] = meta['feature'].map(unit).fillna('')
meta['calibrated'] = meta['feature'].map(calflag).fillna('')
meta['value_type'] = meta['feature'].map(lambda c: logb.get(c, 'log10_or_uncalibrated'))
meta.loc[meta['value_type'] == 'log10_or_uncalibrated', 'value_type'] = 'log10_or_unknown'
# 衍生加和列
for c in ['esters_sum', 'aroma_hops_sum', 'acids_sum', 'sulfur_sum']:
    if c in C:
        meta.loc[meta['feature'] == c, ['origin', 'value_type']] = ['Derived', 'sum']
meta.to_csv(os.path.join(DP, 'feature_meta2.csv'), index=False, encoding='utf-8-sig')

# ---------- 5. 缺失分析 + KNN 填补 ----------
Xraw = chem[C].values.astype(float)
miss = np.isnan(Xraw)
miss_cols = pd.Series(miss.sum(0), index=C)
miss_rows = pd.Series(miss.sum(1), index=chem['beer'].values)
log('缺失单元格总数 %d，涉及 %d 个特征；缺失样本数 %d'
    % (int(miss.sum()), int((miss_cols > 0).sum()), int((miss_rows > 0).sum())))
log('缺失最多的特征：\n' + miss_cols[miss_cols > 0].sort_values(ascending=False).to_string())

Ximp = knn_impute(Xraw, k=5)
Xw = winsorize(Ximp, 0.5, 99.5)
rg = RankGauss().fit(Xw)
Xz = rg.transform(Xw)
with open(os.path.join(DP, 'rankgauss.pkl'), 'wb') as f:
    pickle.dump(rg, f)
log('秩-高斯变换后特征：形状 %s，均值 %.3f，标准差 %.3f'
    % (Xz.shape, float(np.nanmean(Xz)), float(np.nanstd(Xz))))

chem_feat = chem[['beer', 'tasting_category_fine']].copy()
for j, c in enumerate(C):
    chem_feat[c] = Xz[:, j]
chem_feat.to_csv(os.path.join(DP, 'chem_features.csv'), index=False, encoding='utf-8-sig')

# ---------- 6. 感官标签：连续 z 值 + 0–6 序数反演 ----------
Y = sens[S].values.astype(float)
ordinal = {}
grade_mat = np.zeros((len(sens), len(S)), dtype=int)
cont = np.zeros_like(Y)
for j, c in enumerate(S):
    fit = fit_ordinal_inversion(Y[:, j])
    ordinal[c] = {k: (float(v) if np.isscalar(v) else np.asarray(v).tolist())
                  for k, v in fit.items() if k in ('a', 'b', 'sigma', 'll', 'w', 'mu')}
    grade_mat[:, j] = fit['grade']
    cont[:, j] = fit['x']
    log('  %-16s a=%7.4f b=%6.4f sigma=%5.4f 等级分布=%s'
        % (c, fit['a'], fit['b'], fit['sigma'],
           np.bincount(fit['grade'], minlength=7).tolist()))

ord_df = sens[['beer', 'tasting_category_fine']].copy()
ord_df = pd.concat([ord_df, pd.DataFrame(grade_mat, columns=S)], axis=1)
ord_df.to_csv(os.path.join(DP, 'sensory_ordinal.csv'), index=False, encoding='utf-8-sig')

cont_df = sens[['beer', 'tasting_category_fine']].copy()
cont_df = pd.concat([cont_df, pd.DataFrame(cont, columns=S)], axis=1)
cont_df.to_csv(os.path.join(DP, 'sensory_ordinal_continuous.csv'), index=False, encoding='utf-8-sig')

sens.to_csv(os.path.join(DP, 'sensory_z.csv'), index=False, encoding='utf-8-sig')

# ---------- 7. 报告 ----------
report = {
    'n_samples': int(len(sens)), 'n_chem_features': len(C), 'n_sensory_dims': len(S),
    'sensory_dims_AF': len(A_F_COLS), 'sensory_dims_other': len(OTHER_COLS),
    'missing_cells': int(miss.sum()), 'missing_features': int((miss_cols > 0).sum()),
    'corr2_spearman_r': r_spear, 'corr2_spearman_mad': mad_spear,
    'corr2_pearson_r': r_pear, 'corr2_pearson_mad': mad_pear,
    'n_matched_2csv': len(pairs),
    'log10_verified_features': cnt.get('log10', 0),
    'raw_verified_features': cnt.get('raw', 0),
    'other_verified_features': cnt.get('other', 0),
    'styles': chem['tasting_category_fine'].value_counts().to_dict(),
    'ordinal_fits': ordinal,
}
dump_json(report, '20_data_report.json')
log('数据构建完成，报告已保存')
