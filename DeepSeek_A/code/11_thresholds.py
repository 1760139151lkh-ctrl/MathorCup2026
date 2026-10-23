# -*- coding: utf-8 -*-
"""Step 11: full inspection of Sensory thresholds / names tables; robust 2.csv<->1.csv mapping."""
import sys, io, os, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np

ROOT = r"C:\Users\17601\Desktop\MathorCup\03_A赛道\01_附件"
DP = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\data_processed"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
lines=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s); lines.append(s)

sth = pd.read_excel(os.path.join(ROOT,'8.xlsx'), sheet_name='Sensory thresholds')
sn = pd.read_excel(os.path.join(ROOT,'8.xlsx'), sheet_name='Sensory names')
log('thresholds cols:', list(sth.columns))
log('non-null counts:', sth.notna().sum().to_dict())
log('calibrated values:', sth['calibrated'].value_counts(dropna=False).to_dict())
log('origin_paper values:', sth['origin_paper'].value_counts(dropna=False).to_dict())
log('off_flavors values:', sth['off_flavors'].value_counts(dropna=False).to_dict())
log('unit values:', sth['unit'].value_counts(dropna=False).to_dict())
log('aging values:', sth['aging'].value_counts(dropna=False).to_dict())
log('rows with threshold_mean notna:', int(sth['threshold_mean'].notna().sum()))
log('\n=== rows where off_flavors notna ===')
sub = sth[sth['off_flavors'].notna() | sth['aging'].notna()]
log(sub[['field_name_python','chemical_name','origin_paper','unit','aging','off_flavors','threshold_mean','threshold_median']].to_string(max_rows=300))
log('\n=== rows with thresholds ===')
log(sth[sth['threshold_mean'].notna()][['field_name_python','chemical_name','origin_paper','unit','threshold_mean','threshold_median']].to_string(max_rows=300))
log('\n=== full thresholds table ===')
log(sth[['field_name_python','chemical_name','chemical_name_short','calibrated','origin_paper','unit','aging','off_flavors','threshold_mean','threshold_median']].to_string(max_rows=300))
log('\n=== Sensory names full ===')
log(sn.to_string(max_rows=120))

sth.to_csv(os.path.join(DP,'sensory_thresholds.csv'), index=False, encoding='utf-8-sig')
sn.to_csv(os.path.join(DP,'sensory_names.csv'), index=False, encoding='utf-8-sig')
with open(os.path.join(OUT,'11_thresholds.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
log('Saved')
