# -*- coding: utf-8 -*-
"""Step 2: dump 3.xlsx summary sheet and check whether beer_i sheets hold real scores."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np

ROOT = r"C:\Users\17601\Desktop\MathorCup\03_A赛道\01_附件"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
lines=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s); lines.append(s)

p = os.path.join(ROOT,'3.xlsx')
sm = pd.read_excel(p, sheet_name='summary', header=None)
log('summary shape', sm.shape)
log(sm.to_string(max_rows=50, max_cols=60, max_colwidth=40))

# check values in beer sheets
xls = pd.ExcelFile(p)
for sh in xls.sheet_names[:-1]:
    d = pd.read_excel(p, sheet_name=sh, header=None)
    vals = d.stack().dropna()
    num = pd.to_numeric(vals, errors='coerce').dropna()
    uniq = sorted(set(np.round(num.values,4)))
    log(sh, 'nonnull', len(vals), 'numeric uniq', uniq[:20], '...' if len(uniq)>20 else '')
    # text labels in col 4 and 20
    labels = []
    for r in range(d.shape[0]):
        for c in (1,4,17,20):
            v = d.iloc[r,c]
            if isinstance(v,str) and v.strip() and v.strip() not in ('Date','Name:','Aroma','Flavour','Malt','Hops','Esters','Faults','Overall','Comments:'):
                labels.append((r,c,v.strip()))
    log('   labels:', labels)

with open(os.path.join(OUT,'02_3xlsx_summary.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
log('Saved')
