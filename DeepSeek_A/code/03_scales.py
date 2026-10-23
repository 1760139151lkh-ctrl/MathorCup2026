# -*- coding: utf-8 -*-
"""Step 3: recover 0-6 scale from 4.csv; inspect 7.csv structure; dump 8.xlsx key sheets."""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np

ROOT = r"C:\Users\17601\Desktop\MathorCup\03_A赛道\01_附件"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
lines=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s); lines.append(s)
np.set_printoptions(precision=4, suppress=True)

d4 = pd.read_csv(os.path.join(ROOT,'4.csv'), encoding='utf-8')
sensory_cols = [c for c in d4.columns if c not in ('beer','beer_id','tasting_category_fine')]
log('n sensory cols', len(sensory_cols))
log('unique value analysis per column:')
for c in sensory_cols:
    v = np.sort(d4[c].dropna().unique())
    diffs = np.diff(v)
    log(f'  {c:16s} n_uniq={len(v):4d} min={v[0]:8.4f} max={v[-1]:8.4f} '
        f'diff_med={np.median(diffs) if len(diffs) else 0:.6f} diff_uniq={len(np.unique(np.round(diffs,6)))}')

log('='*90)
d7 = pd.read_csv(os.path.join(ROOT,'7.csv'), encoding='utf-8')
log('7.csv columns:', list(d7.columns))
log('7.csv describe (first 8 cols):')
log(d7.iloc[:, :8].describe().to_string())
# unique values of a few 7.csv cols
for c in d7.columns[3:8]:
    v = np.sort(d7[c].dropna().unique())
    log(f'  {c}: n_uniq={len(v)} first={v[:8]} last={v[-3:]}')

log('='*90)
p8 = os.path.join(ROOT,'8.xlsx')
x8 = pd.ExcelFile(p8)
sn = pd.read_excel(p8, sheet_name='Sensory names')
log('Sensory names full:')
log(sn.to_string(max_rows=120, max_cols=10))
st = pd.read_excel(p8, sheet_name='Sensory thresholds')
log('='*90)
log('Sensory thresholds shape', st.shape)
log(st.to_string(max_rows=300, max_cols=12))
gi = pd.read_excel(p8, sheet_name='GBM importance MDI')
log('='*90); log('GBM importance MDI shape', gi.shape)
log(gi.sort_values(gi.columns[0], ascending=False).head(30).to_string())

with open(os.path.join(OUT,'03_scales.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
log('Saved')
