# -*- coding: utf-8 -*-
"""Step 10: data verification + preprocessing.
Outputs: data_processed/chem_raw.csv, chem_imputed.csv, sensory_z.csv, feature_meta.csv, verification report.
"""
import sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np
from scipy.stats import spearmanr, pearsonr

ROOT = r"C:\Users\17601\Desktop\MathorCup\03_A赛道\01_附件"
EXT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\data_processed\external"
DP = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\data_processed"
OUT = r"C:\Users\17601\Desktop\MathorCup\DeepSeek_A\results"
os.makedirs(DP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
lines=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s); lines.append(s)

# ---------- load ----------
d1 = pd.read_csv(os.path.join(ROOT,'1.csv'), encoding='utf-8')
d2 = pd.read_csv(os.path.join(ROOT,'2.csv'), encoding='utf-8', index_col=0)
d4 = pd.read_csv(os.path.join(ROOT,'4.csv'), encoding='utf-8')
d5 = pd.read_csv(os.path.join(ROOT,'5.csv'), encoding='utf-8', index_col=0)
d6 = pd.read_csv(os.path.join(ROOT,'6.csv'), encoding='utf-8', index_col=0)
d7 = pd.read_csv(os.path.join(ROOT,'7.csv'), encoding='utf-8')
x8 = pd.ExcelFile(os.path.join(ROOT,'8.xlsx'))
snames = pd.read_excel(x8, sheet_name='Sensory names')
sthresh = pd.read_excel(x8, sheet_name='Sensory thresholds')
calib = pd.read_excel(x8, sheet_name='Calibrated chemical dataset')

CHEM_COLS = [c for c in d1.columns if c not in ('beer','beer_id','tasting_category_fine')]
SENS_COLS = [c for c in d4.columns if c not in ('beer','beer_id','tasting_category_fine')]
log('chem features:', len(CHEM_COLS), 'sensory dims:', len(SENS_COLS))

# ---------- 1. verify 2.csv = which correlation? ----------
# map full chemical names (2.csv) -> R names via thresholds table
name_map = {str(r['chemical_name']).strip().lower(): str(r['field_name_python']).strip()
            for _, r in sthresh.iterrows() if pd.notna(r['chemical_name']) and pd.notna(r['field_name_python'])}
# manual extra mappings for 2.csv names
extra = {
 'iso-alpha acids':'bitterness','4-vinylguaiacol':'X4VG','dimethyl sulfide':'DMS',
 'diethyl sulfide':'DES','carbon disulfide':'CS2','hydrogen sulfide':'H2S','methanethiol':'MeSH',
 'sulfur dioxide':'SO2.mg.L.','acetic acid':'acetic_acid.g.L.','ammonia':'ammonia.mg.L.',
 'color':'color.EBC.','betaglucan':'betaglucan.mg.L.','lactic acid':'lactic_acid.mg.L.',
 'glycerol':'glycerol','iron':'iron','ph':'pH','protein':'protein.g.L.','sugars':'GFS',
 'ethanol':'ethanol..v.v.','carbon dioxide':'CO2.PSI.','unfermentables':'unfermentables',
 'caloric value':'kcalperc','1-propanol':'X1.propanol','diacetyl':'X2.3.butanedione',
 '3-methylbutanal':'X3.methylbutanal','propylene glycol':'propylene.glycol',
 'n-propyl acetate':'propyl.acetate','n-pentanol':'n.pentanol','2-methyl-1-butanol':'X2.methyl.1.butanol',
 'isopentyl formate':'isopentyl.formate','ethyl isobutyrate':'ethyl.isobutyrate',
 '3-methyl-2-butenal':'X3.methyl.2.butenal','2-methyltetrahydrofuran-3-one':'X2.methyltetrahydrofuran.3.one',
 'ethyl butyrate':'ethyl.butyrate','butyl acetate':'butyl.acetate','methylpyrazine':'methylpyrazine',
 'furfural':'furfural','ethyl lactate':'ethyl.lactate','cis-3-hexenol':'X3Z.hexenol',
 'n-hexanol':'n.hexanol','styrene':'styrene','furfuryl alcohol':'X2.furanmethanol',
 '3-methyl-2-hexanol':'X3.methyl.2.hexanol','3-furanmethanol':'X3.furanmethanol',
 '2-acetylfuran':'X2.acetylfuran','2,6-dimethylpyrazine':'X2.6.dimethyl.pyrazine',
 'amyl acetate':'amyl.acetate','ethyl tiglate':'ethyl.tiglate','benzaldehyde':'benzaldehyde',
 '5-methylfurfural':'X5.methylfurfural','n-heptanol':'n.heptanol','1-octen-3-ol':'X1.octen.3.ol',
 'methionol':'X3.methylthio.propanol','isomaltol':'isomaltol','methyl heptenone':'X6.methyl.5.hepten.2.one',
 '2-pentyl furan':'X2.pentyl.furan','ethyl 3-hexanoate':'ethyl.hex..3E..enoate',
 'alpha-phellandrene':'alpha.phellandrene','dehydroxy-cis-linalool oxide':'dehydroxy.cis.linalool.oxide',
 'hexyl acetate':'hexyl.acetate','isopentyl butanoate':'isopentyl.butanoate',
 '2-ethyl-1-hexanol':'X2.ethyl.1.hexanol','beta-phellandrene':'beta.phellandrene',
 'limonene':'limonene','eucalyptol':'eucalyptol','benzyl alcohol':'benzyl.alcohol',
 'ethyl 2-hexenoate':'ethyl.hex..2E..enoate','phenylacetaldehyde':'phenylacetaldehyde',
 'e-beta-ocimene':'X.E..beta.ocimene','prenyl isobutyrate':'prenyl.isobutyrate',
 'ethyl furoate':'ethyl.furoate','o-cresol':'ortho.cresol','ethyl 5-methylhexanoate':'ethyl.5.methylhexanoate',
 '2-acetylpyrrole':'X2.acetylpyrrole','isoamyl lactate':'isoamyl.lactate','n-octanol':'n.octanol',
 'cis-linalool oxide':'cis.linalool.oxide','meta-cymenene':'meta.cymenene','terpinolene':'terpinolene',
 'linalool':'linalool','2-nonanol':'nonan.2.ol','n-nonanal':'n.nonanal',
 '2-methyl-benzofuran':'X2.methyl.benzofuran','heptyl acetate':'heptyl.acetate',
 '4-methyl-1-pentanol':'X4.methyl.1.pentanol','neo-allo-ocimene':'neo.allo.ocimene',
 'x-methyl-1-octanol':'x.methyl.1.octanol','trans-dihydro-beta-terpineol':'trans.dihydro.beta.terpineol',
 'cis-beta-terpineol':'cis.beta.terpineol','y-methyl-1-octanol':'y.methyl.1.octanol',
 'camphor':'camphor','isobutyl hexanoate':'isobutyl.hexanoate','nerol oxide':'nerol.oxide',
 'e-2-nonenal':'X.E..2.nonenal','cis-dihydro-beta-terpineol':'cis.dihydro.beta.terpineol',
 '4-ethyl-phenol':'X4.ethyl.phenol','isoborneol':'isoborneol','ethyl benzoate':'ethyl.benzoate',
 'n-nonanol':'n.nonanol','terpinen-4-ol':'terpinen.4.ol','diethyl succinate':'diethyl.succinate',
 'vinyl caprylate':'vinyl.caprylate','alpha-terpineol':'X1.alpha.terpineol',
 'ethyl linalool':'ethyl..E..linalool','ethyl nicotinate':'ethyl.nicotinate','citronellol':'citronellol',
 'nerol':'nerol','5-hydroxymethylfurfural':'hydroxy.methyl.furfural','ocimenone':'E.ocimenone',
 'cumin aldehyde':'cumin.aldehyde','ethyl phenylacetate':'ethyl.phenylacetate',
 'isopentyl hexanoate':'isopentyl.hexanoate','geraniol':'geraniol',
 'beta-cyclohomocitral':'beta.cyclohomocitral','e-cinnamaldehyde':'E.cinnamaldehyde',
 'n-decanol':'n.decanol','neryl formate':'neryl.formate','4-ethylguaiacol':'X4.ethyl.guaiacol',
 '2-undecanone':'X2.undecanone','trans-dihydro-alpha-terpinyl acetate':'trans.dihydro.alpha.terpinyl.acetate',
 'terpinen-4-ol acetate':'terpinen.4.ol.acetate','2-undecanol':'X2.undecanol',
 'delta-terpinyl acetate':'delta.terpinyl.acetate','(e,e)-2,4-decadienal':'X.E.E..2.4.decadienal',
 'methyl geranate':'methyl.geranate','car-3-en-2-one':'car.3.en.2.one',
 'dimethoxy-(e)-citral':'dimethoxy..E..citral','2-butyloctanoate':'X2.butyloctanoate',
 '4-methoxysalicylaldehyde':'X4.methoxysalicylaldehyde','ethyl hydrocinnamate':'ethyl.hydrocinnamate',
 'eugenol':'eugenol','gamma-nonalactone':'gamma.nonalactone','methyl para-anisate':'methyl.para.anisate',
 '(e)-beta-damascenone':'X.E..beta.damascenone','ethyl 9-decenoate':'ethyl..9..decenoate',
 'vanillin':'vanillin','geosmin':'geosmin','dodecanal':'dodecanal',
 '4,8-alpha-epoxy-caryophyllane':'X4.8.alpha.epoxy.caryophyllane','e-caryophyllene':'E.caryophyllene',
 '(e)-alpha-ionone':'X.E..alpha.ionone','perillyl acetate':'perillyl.acetate','beta-humulene':'beta.humulene',
 '2-phenyl ethyl butyrate':'X2.phenyl.ethyl.butyrate','(z)-beta-farnesene':'X.Z..beta.farnesene',
 'pentyl octanoate':'pentyl.octanoate','(e)-beta-farnesene':'X.E..beta.farnesene',
 '2-methylbutyl octanoate':'X2.methylbutyl.octanoate','alpha-humulene':'alpha.humulene',
 'neryl propanoate':'neryl.propanoate','9-epi-(e)-caryophyllene':'X9.epi..E..caryophyllene',
 'ethyl (e)-cinnamate':'ethyl..E..cinnamate','linalool isovalerate':'linalool.isovalerate',
 'alpha-terpinyl isobutanoate':'alpha.terpinyl.isobutanoate','n-dodecanol':'n.dodecanol',
 'germacrene d':'germacrene.D','(e)-nerolidol':'Z.nerolidol',
 'acetaldehyde':'acetaldehyde','ethyl 2-methylbutyrate':'ethyl_2.methyl_butyrate',
 'ethyl acetate':'ethyl_acetate','ethyl decanoate':'ethyl_decanoate','ethyl hexanoate':'ethyl_hexanoate',
 'ethyl 3-methylbutyrate':'ethyl_isovalerate','ethyl octanoate':'ethyl_octanoate',
 'ethyl propionate':'ethyl_propionate','isoamyl alcohol':'isoamyl_alcohol','isobutanol':'isobutanol',
 'isobutyl acetate':'isobutyl_acetate','isoamyl acetate':'isopentyl_acetate','octyl acetate':'octyl_acetate',
 'phenethyl acetate':'phenethyl_acetate','phenethyl alcohol':'phenethyl_alcohol',
 '2,3-butanedione':'X2.3.butanedione','2,3-hexanedione':'X2.3.hexanedione',
}
def map_name(n):
    k = str(n).strip()
    kl = k.lower()
    if k in extra: return extra[k]
    if kl in extra: return extra[kl]
    if kl in name_map: return name_map[kl]
    return None

c2 = list(d2.index)
mapped = {n: map_name(n) for n in c2}
unmapped = [n for n,v in mapped.items() if v is None or v not in CHEM_COLS]
log('2.csv rows:', len(c2), 'unmapped/unmatched:', len(unmapped))
log('unmapped:', unmapped[:20])

# compute spearman & pearson from 1.csv on columns present
pair = [(n, mapped[n]) for n in c2 if mapped[n] in CHEM_COLS]
log('comparable pairs:', len(pair))
X = d1[[p[1] for p in pair]].values.astype(float)
sp = spearmanr(X, nan_policy='omit').correlation
pe = np.corrcoef(np.nan_to_num((X-np.nanmean(X,0))/np.nanstd(X,0), nan=0.0), rowvar=False)
ref = d2.loc[[p[0] for p in pair], [p[0] for p in pair]].values.astype(float)
iu = np.triu_indices(len(pair), 1)
log('2.csv vs Spearman-from-1.csv: r=%.4f, MAD=%.4f' % (
    np.corrcoef(ref[iu], sp[iu])[0,1], np.mean(np.abs(ref[iu]-sp[iu]))))
log('2.csv vs Pearson-from-1.csv: r=%.4f, MAD=%.4f' % (
    np.corrcoef(ref[iu], pe[iu])[0,1], np.mean(np.abs(ref[iu]-pe[iu]))))

# ---------- 2. verify 5.csv (sensory corr) ----------
S = d4[SENS_COLS].values.astype(float)
sp5 = spearmanr(S).correlation
ref5 = d5.values.astype(float)
# detect ordering: d5 index/cols are long names; map via Sensory names CleanName_PanelFeedback
log('5.csv shape', d5.shape, 'sensory', len(SENS_COLS))
# 5.csv first 30 names vs Sensory names order: assume same order as columns of 4.csv? compare sizes
# reorder using names if possible
sn_map = {str(r['CleanName_PanelFeedback']).strip(): r['R_name'] for _,r in snames.iterrows()}
log('5.csv labels sample:', list(d5.columns[:3]), '...')
# Try direct: 5.csv is 50x50 with same order as sensory columns
log('5.csv vs Spearman(4.csv): r=%.4f MAD=%.4f' % (
    np.corrcoef(ref5[iu[:0]], ref5.ravel())[0,1] if False else np.corrcoef(ref5.ravel(), sp5.ravel())[0,1],
    np.mean(np.abs(ref5 - sp5))))

# ---------- 3. log base check using calibrated dataset ----------
log('='*90)
log('Calibrated dataset columns:', list(calib.columns)[:80])
calib = calib.set_index('beer') if 'beer' in calib.columns else calib
# align by beer
d1b = d1.set_index('beer')
common = [c for c in calib.columns if c in CHEM_COLS]
log('calibrated cols matching 1.csv:', len(common), common[:20])
if common:
    A = calib[common].values.astype(float)
    B = d1b.loc[calib.index, common].values.astype(float)
    for c in common[:60]:
        a = calib[c].values.astype(float); b = d1b.loc[calib.index, c].values.astype(float)
        mask = np.isfinite(a) & np.isfinite(b) & (a>0)
        if mask.sum() > 20:
            r10 = np.corrcoef(np.log10(a[mask]), b[mask])[0,1]
            rln = np.corrcoef(np.log(a[mask]), b[mask])[0,1]
            log(f'  {c:28s} n={mask.sum():3d} r(log10)={r10:+.4f} r(ln)={rln:+.4f} slope_ln={np.polyfit(b[mask],np.log(a[mask]),1)[0]:.3f}')

# ---------- 4. raw vs log columns ----------
log('='*90)
rows=[]
for c in CHEM_COLS:
    v = d1[c].values.astype(float)
    rows.append(dict(col=c, n_missing=int(np.isnan(v).sum()), min=np.nanmin(v), max=np.nanmax(v),
                     mean=np.nanmean(v), std=np.nanstd(v), n_neg=int((v<0).sum())))
meta = pd.DataFrame(rows)
meta['type'] = np.where(meta['min']<0, 'log', 'raw_or_nonneg')
log(meta.groupby('type').size().to_string())
log('nonneg columns (possible raw-physical):')
log(meta[meta['type']=='raw_or_nonneg'].sort_values('max', ascending=False).head(60).to_string())
log('missing cells:', int(meta['n_missing'].sum()))
log(meta[meta['n_missing']>0].to_string())

meta.to_csv(os.path.join(DP,'feature_meta.csv'), index=False, encoding='utf-8-sig')
d1.to_csv(os.path.join(DP,'chem_raw.csv'), index=False, encoding='utf-8-sig')
d4.to_csv(os.path.join(DP,'sensory_z.csv'), index=False, encoding='utf-8-sig')
d2.to_csv(os.path.join(DP,'chem_corr_2csv.csv'), encoding='utf-8-sig')
d5.to_csv(os.path.join(DP,'sensory_corr_5csv.csv'), encoding='utf-8-sig')
d6.to_csv(os.path.join(DP,'cross_corr_6csv.csv'), encoding='utf-8-sig')
d7.to_csv(os.path.join(DP,'reviews_7csv.csv'), index=False, encoding='utf-8-sig')
snames.to_csv(os.path.join(DP,'sensory_names.csv'), index=False, encoding='utf-8-sig')
sthresh.to_csv(os.path.join(DP,'sensory_thresholds.csv'), index=False, encoding='utf-8-sig')
calib.to_csv(os.path.join(DP,'calibrated_chem.csv'), encoding='utf-8-sig')

with open(os.path.join(OUT,'10_verify.txt'),'w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
log('Saved verification report')
