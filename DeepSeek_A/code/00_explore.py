# -*- coding: utf-8 -*-
"""Step 0: inspect all attachment files (shapes, columns, missingness, dtypes)."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np

ROOT = r"C:\Users\17601\Desktop\MathorCup\03_A赛道\01_附件"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
os.makedirs(OUT, exist_ok=True)

lines = []
def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    lines.append(s)

def read_csv_smart(path):
    for enc in ('utf-8', 'utf-8-sig', 'gbk', 'latin-1'):
        try:
            return pd.read_csv(path, encoding=enc), enc
        except Exception as e:
            last = e
    raise last

for f in ['1.csv', '2.csv', '4.csv', '5.csv', '6.csv', '7.csv']:
    p = os.path.join(ROOT, f)
    df, enc = read_csv_smart(p)
    log('=' * 100)
    log(f, 'shape=', df.shape, 'encoding=', enc)
    log('columns[:25] =', list(df.columns[:25]))
    log('dtypes summary:', df.dtypes.value_counts().to_dict())
    log('missing cells =', int(df.isna().sum().sum()), '/', df.size)
    with pd.option_context('display.max_columns', 12):
        log('head(3):')
        log(df.head(3).to_string()[:2500])

for f in ['3.xlsx', '8.xlsx']:
    p = os.path.join(ROOT, f)
    xls = pd.ExcelFile(p)
    log('=' * 100)
    log(f, 'sheets =', xls.sheet_names)
    for sh in xls.sheet_names:
        d = pd.read_excel(p, sheet_name=sh, header=None)
        log('-' * 80)
        log(f'[{f}] sheet {sh}: shape={d.shape}')
        with pd.option_context('display.max_columns', 12):
            log(d.head(15).to_string()[:4000])

with open(os.path.join(OUT, '00_explore.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines))
log('\nSaved ->', os.path.join(OUT, '00_explore.txt'))
