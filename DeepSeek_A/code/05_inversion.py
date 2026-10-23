# -*- coding: utf-8 -*-
"""Step 5: verify 4.csv == Supplementary File S4 (z-score averaged per taster),
   test 7-component equally-spaced Gaussian mixture inversion to 0-6 ordinal scale."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np

ROOT = r"C:\Users\17601\Desktop\MathorCup\03_A赛道\01_附件"
EXT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\data_processed\external"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
lines=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s); lines.append(s)

d4 = pd.read_csv(os.path.join(ROOT,'4.csv'), encoding='utf-8')
s4 = pd.read_excel(os.path.join(EXT,'Supplemental.xlsx'), sheet_name='Supplementary File S4')
log('4.csv shape', d4.shape, 'S4 shape', s4.shape)
log('columns equal?', list(d4.columns) == list(s4.columns))
cols = [c for c in d4.columns if c not in ('beer','beer_id','tasting_category_fine')]
diff = np.nanmax(np.abs(d4[cols].values - s4[cols].values))
log('max abs diff 4.csv vs S4:', diff)
log('row-wise mean of sensory values: describe')
log(pd.Series(d4[cols].mean(axis=1)).describe().to_string())
log('col-wise mean std: mean=%.6f  std=%.6f' % (d4[cols].mean().mean(), d4[cols].mean().std()))

# Check 1.csv vs S1, 7.csv vs S7
d1 = pd.read_csv(os.path.join(ROOT,'1.csv'), encoding='utf-8')
s1 = pd.read_excel(os.path.join(EXT,'Supplemental.xlsx'), sheet_name='Supplementary File S1')
log('='*90)
log('1.csv vs S1: shapes', d1.shape, s1.shape)
log('1.csv cols == S1 cols?', list(d1.columns)==list(s1.columns))
numc = [c for c in d1.columns if c not in ('beer','beer_id','tasting_category_fine')]
log('max abs diff:', np.nanmax(np.abs(d1[numc].values - s1[numc].values)))

# ---- mixture inversion experiment on selected attributes ----
from scipy.optimize import minimize_scalar
from scipy.stats import norm

def fit_mixture(y, K=7, n_iter=200, seed=0):
    """Constrained GMM: means a + b*k, common sigma; weights free. EM by grid over (a,b)."""
    y = y[~np.isnan(y)]
    ymin, ymax = y.min(), y.max()
    rng = (ymax - ymin)
    best = None
    # coarse-to-fine grid search over a (score0 center) and b (step)
    for a in np.linspace(ymin - 0.2*rng, ymin + 0.8*rng, 60):
        for b in np.linspace(0.15*rng, 0.9*rng, 60):
            mu = a + b*np.arange(K)
            sigma = 0.35*b + 1e-9
            ll = 0.0
            # init weights from assignment
            w = np.ones(K)/K
            for it in range(30):
                # E
                logp = np.log(w+1e-12)[None,:] + norm.logpdf(y[:,None], mu[None,:], sigma)
                m = logp.max(axis=1, keepdims=True)
                resp = np.exp(logp-m); resp /= resp.sum(axis=1, keepdims=True)
                ll = (np.log(np.exp(logp-m).sum(axis=1)) + m.ravel()).sum()
                # M (weights only; a,b,sigma fixed via grid)
                w = resp.mean(axis=0)
            if best is None or ll > best[0]:
                best = (ll, a, b, sigma, w.copy())
    return best

log('='*90)
log('Mixture inversion test (coarse grid, K=7):')
for c in ['A_malt_all','A_hops_all','bitternes','sweetness','dms','diacetyl','clove','overall']:
    y = d4[c].values
    ll, a, b, sigma, w = fit_mixture(y, K=7)
    xhat = np.clip(np.round((y-a)/b), 0, 6)
    log(f'{c:14s} a={a:7.4f} b={b:7.4f} sigma={sigma:6.4f} ll={ll:9.2f} '
        f'xhat_dist={np.bincount(xhat.astype(int), minlength=7).tolist()}')
    log('   weights:', np.round(w,3).tolist())

with open(os.path.join(OUT,'05_inversion.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
log('Saved')
