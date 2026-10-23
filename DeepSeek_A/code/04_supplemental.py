# -*- coding: utf-8 -*-
"""Step 4: inspect Zenodo supplemental workbook; match to competition attachments."""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np

EXT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\data_processed\external"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
lines=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s); lines.append(s)

p = os.path.join(EXT,'Supplemental.xlsx')
xls = pd.ExcelFile(p)
log('sheets:', xls.sheet_names)
for sh in xls.sheet_names:
    d = pd.read_excel(p, sheet_name=sh, header=None, nrows=6)
    log('-'*90)
    log(f'[{sh}]')
    try:
        full = pd.read_excel(p, sheet_name=sh, header=None)
        log('shape:', full.shape)
    except Exception as e:
        log('shape err', e)
    log(d.head(6).to_string(max_cols=14, max_colwidth=28)[:2500])

with open(os.path.join(OUT,'04_supplemental_sheets.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
log('Saved')
