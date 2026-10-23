# -*- coding: utf-8 -*-
"""Step 1: deep-dive into 3.xlsx score cards, 8.xlsx, 4/7 csv value ranges, sample alignment."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np

ROOT = r"C:\Users\17601\Desktop\MathorCup\03_A赛道\01_附件"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
lines=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s); lines.append(s)

# ---- 3.xlsx full dump of beer_1 and summary ----
p3 = os.path.join(ROOT,'3.xlsx')
for sh in ['beer_1','beer_2','summary']:
    d = pd.read_excel(p3, sheet_name=sh, header=None)
    log('='*90); log('3.xlsx', sh, d.shape)
    log(d.to_string(max_rows=200, max_cols=40))

# ---- non-null stats per sheet ----
xls = pd.ExcelFile(p3)
log('='*90); log('3.xlsx sheets:', xls.sheet_names)
for sh in xls.sheet_names:
    d = pd.read_excel(p3, sheet_name=sh, header=None)
    log(sh, 'shape', d.shape, 'non-null', int(d.notna().sum().sum()))

# ---- 8.xlsx ----
p8 = os.path.join(ROOT,'8.xlsx')
x8 = pd.ExcelFile(p8)
log('='*90); log('8.xlsx sheets:', x8.sheet_names)
for sh in x8.sheet_names:
    d = pd.read_excel(p8, sheet_name=sh, header=None)
    log('-'*80); log('8.xlsx', sh, d.shape)
    log(d.head(30).to_string(max_cols=20)[:6000])

# ---- 4.csv stats ----
d4 = pd.read_csv(os.path.join(ROOT,'4.csv'), encoding='utf-8')
log('='*90); log('4.csv', d4.shape)
log('columns:', list(d4.columns))
log(d4.describe().T.to_string()[:8000])
log('unique beer_id count', d4['beer_id'].nunique(), 'beer values sample', d4['beer'].head(10).tolist())
log('tasting categories:', d4['tasting_category_fine'].value_counts().to_string())

# ---- 7.csv stats ----
d7 = pd.read_csv(os.path.join(ROOT,'7.csv'), encoding='utf-8')
log('='*90); log('7.csv', d7.shape)
log('missing per col (top):')
log(d7.isna().sum().sort_values(ascending=False).head(15).to_string())
log(d7.describe().T.head(10).to_string())

# ---- 1.csv ----
d1 = pd.read_csv(os.path.join(ROOT,'1.csv'), encoding='utf-8')
log('='*90); log('1.csv', d1.shape)
log('missing per col:', d1.isna().sum()[lambda s: s>0].to_string())
log('beer_id dtype', d1['beer_id'].dtype, 'sample', d1['beer_id'].head().tolist())
log('categories 1.csv:', d1['tasting_category_fine'].value_counts().to_string())
log('beer strings:', d1['beer'].head(10).tolist())

# alignment 1.csv vs 4.csv vs 7.csv
for nm, d in [('1', d1), ('4', d4), ('7', d7)]:
    log(nm, 'beer_id set size', d['beer_id'].nunique(), 'first ids', d['beer_id'].head(5).tolist())
log('1&4 same beer_id order?', (d1['beer_id'].values == d4['beer_id'].values).all() if len(d1)==len(d4) else 'len differ')
log('1&7 same beer_id order?', (d1['beer_id'].values == d7['beer_id'].values).all() if len(d1)==len(d7) else 'len differ')

with open(os.path.join(OUT,'01_deep_explore.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
log('\nSaved ->', os.path.join(OUT,'01_deep_explore.txt'))
