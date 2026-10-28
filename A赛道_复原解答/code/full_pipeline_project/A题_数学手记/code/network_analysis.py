"""问题2：相关结构、三个关联视角与有放回重采样稳定性。

运行：python code/network_analysis.py --bootstrap 200
输出的排名是探索性关联，不是因果贡献；不以全样本拟合优度冒充预测精度。
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import scipy.linalg as la
from scipy.stats import rankdata, f as f_dist, t as t_dist
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import adjusted_rand_score
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'A题_数学手记'
METHODS = ['spearman', 'rank_ridge', 'quantile_eta2']


def rank_standardize(a):
    """在当前重采样袋内填中位数；把每列数值换成大小名次并标准化。"""
    a = np.asarray(a, float).copy()
    med = np.nanmedian(a, axis=0)
    med = np.where(np.isfinite(med), med, 0)
    a = np.where(np.isfinite(a), a, med)
    ranks = rankdata(a, axis=0, method='average')
    scale = ranks.std(axis=0, ddof=1)
    z = (ranks - ranks.mean(axis=0)) / np.where(scale > 0, scale, 1)
    return z, ranks


def association_scores(x, y, alpha=100):
    """三个固定规则：单调、控制其他秩变量后的岭系数、低自由度分箱关联。"""
    zx, rx = rank_standardize(x)
    zy, _ = rank_standardize(y)
    n, p = zx.shape
    signed = zx.T @ zy / (n - 1)
    ridge = la.solve(zx.T @ zx + alpha * np.eye(p), zx.T @ zy,
                     assume_a='pos', check_finite=False)
    eta = np.zeros((p, y.shape[1]))
    for j in range(p):
        # 五个等频箱；并列名次留在同一箱，避免把相同观测强行分开。
        bins = np.minimum(((rx[:, j] - 1) * 5 / n).astype(int), 4)
        groups = np.unique(bins)
        between = sum(np.sum(bins == g) * zy[bins == g].mean(axis=0)**2
                      for g in groups)
        raw = between / (n - 1)
        eta[j] = np.maximum(0, 1 - (1 - raw) * (n - 1) / (n - len(groups)))
    values = np.stack([np.abs(signed), np.abs(ridge), eta])
    # 每个方法内部排231个变量；平均名次越小，多个视角越一致。
    ranks = np.stack([rankdata(-s, axis=0, method='average') for s in values])
    borda = ranks.mean(axis=0)
    top = np.argsort(borda, axis=0, kind='stable')[:3]
    method_top = np.stack([np.argsort(r, axis=0, kind='stable')[:3] for r in ranks])
    return values, ranks, borda, top, method_top, signed


def graph_partition(corr, cutoff, seed):
    a = np.abs(corr.to_numpy())
    g = nx.Graph()
    g.add_nodes_from(corr.index)
    for i, j in zip(*np.where(np.triu(a >= cutoff, 1))):
        g.add_edge(corr.index[i], corr.index[j], weight=a[i, j],
                   signed_correlation=float(corr.iloc[i, j]))
    communities = nx.community.louvain_communities(g, weight='weight', seed=seed)
    communities = sorted(communities, key=lambda c: (-len(c), min(c)))
    labels = {v: k + 1 for k, members in enumerate(communities) for v in members}
    modularity = nx.community.modularity(g, communities, weight='weight') if g.number_of_edges() else 0
    return g, communities, labels, modularity


def bh_adjust(pvalues):
    p = np.asarray(pvalues)
    order = np.argsort(p)
    adjusted = np.minimum.accumulate((p[order] * len(p) / np.arange(1, len(p)+1))[::-1])[::-1]
    out = np.empty(len(p)); out[order] = np.minimum(adjusted, 1)
    return out


def threshold_analysis(x, y, reference, varmeta):
    """在核验原生量的变量上，以预给定阈值比较直线与折线；仅作探索。"""
    rows = []
    for _, meta in varmeta.dropna(subset=['threshold_mean']).iterrows():
        v, threshold = meta.var_id, float(meta.threshold_mean)
        if v not in reference.columns or v not in x.columns or threshold <= 0:
            continue
        # 直接用ref_scale原生数值，防止把对数地板误当精确原生测量。
        native = pd.to_numeric(reference[v], errors='coerce')
        mask = native.notna() & np.isfinite(native)
        xx = native[mask].to_numpy() / threshold
        if len(xx) < 30 or np.sum(xx <= 1) < 10 or np.sum(xx > 1) < 10:
            continue
        design0 = np.column_stack([np.ones(len(xx)), xx])
        design1 = np.column_stack([design0, np.maximum(xx-1, 0)])
        if np.linalg.matrix_rank(design1) < 3:
            continue
        yy = y.loc[native.index[mask]].to_numpy()
        b0 = la.lstsq(design0, yy)[0]; b1 = la.lstsq(design1, yy)[0]
        rss0 = np.sum((yy-design0 @ b0)**2, axis=0)
        rss1 = np.sum((yy-design1 @ b1)**2, axis=0)
        stats = np.maximum(rss0-rss1, 0) / np.maximum(rss1/(len(xx)-3), 1e-30)
        p = f_dist.sf(stats, 1, len(xx)-3)
        inverse = la.inv(design1.T @ design1)
        influence = inverse @ design1.T
        leverage = np.sum(design1 * influence.T, axis=1)
        adjusted_residual = (yy-design1 @ b1) / np.maximum(1-leverage[:,None],1e-10)
        hc3_se = np.sqrt(np.sum(influence[-1,:,None]**2 * adjusted_residual**2,axis=0))
        hc3_p = 2*t_dist.sf(np.abs(b1[-1])/np.maximum(hc3_se,1e-30),len(xx)-3)
        for k, target in enumerate(y.columns):
            rows.append({'feature':v, 'target':target, 'n':len(xx),
                'n_below':int(np.sum(xx <= 1)), 'n_above':int(np.sum(xx > 1)),
                'threshold_native':threshold, 'hinge_slope_change':b1[2,k],
                'relative_rss_reduction':(rss0[k]-rss1[k])/max(rss0[k],1e-30),
                'F':stats[k], 'p_normal_homoskedastic_assumption':p[k],
                'p_HC3_approximate':hc3_p[k], 'max_leverage':leverage.max()})
    result = pd.DataFrame(rows)
    if len(result):
        result['q_BH_exploratory'] = bh_adjust(result.p_normal_homoskedastic_assumption)
        result['q_BH_HC3_exploratory'] = bh_adjust(result.p_HC3_approximate)
    return result


def main(bootstrap=200, seed=20261026):
    results = WORK / 'results'; figures = WORK / 'figures'
    results.mkdir(parents=True, exist_ok=True); figures.mkdir(parents=True, exist_ok=True)
    xfull = pd.read_csv(ROOT/'data/D01.csv').set_index('object')
    yfull = pd.read_csv(ROOT/'data/D04.csv').set_index('object').loc[xfull.index]
    x = xfull.filter(regex=r'^V\d{3}$'); y = yfull.filter(regex=r'^Y\d{2}$')
    features, targets = x.columns, y.columns
    d02 = pd.read_csv(ROOT/'data/D02.csv', index_col=0).loc[features, features]
    d06 = pd.read_csv(ROOT/'data/D06.csv', index_col=0)
    native = pd.read_excel(ROOT/'data/D08.xlsx', sheet_name='ref_scale').set_index('object').loc[x.index]
    meta = pd.read_excel(ROOT/'data/D08.xlsx', sheet_name='var_reference')
    global_ref = pd.read_excel(ROOT/'data/D08.xlsx', sheet_name='ref_importance').set_index('var_id')
    spearman = x.corr(method='spearman'); pearson = x.corr(method='pearson')
    cross = x.join(y).corr(method='spearman').loc[d06.index, d06.columns]
    audit = {'D02_spearman_MAE':float(np.nanmean(np.abs(d02-spearman))),
             'D02_pearson_MAE':float(np.nanmean(np.abs(d02-pearson))),
             'D06_recomputed_spearman_MAE':float(np.nanmean(np.abs(d06-cross))),
             'D06_rows':len(d06), 'missing_features':int(x.isna().sum().sum()),
             'bootstrap':bootstrap, 'seed':seed, 'ridge_alpha':100,
             'association_outcome':'D04 continuous values, rank transformed',
             'identification':'association, not causal effect; grades unavailable'}
    with threadpool_limits(limits=1):
        values, ranks, borda, top, method_top, signed = association_scores(x.to_numpy(),y.to_numpy())
        # 去掉类别组均值后的秩相关：区分整体差异与同类内部关联。
        zx, _ = rank_standardize(x.to_numpy()); zy, _ = rank_standardize(y.to_numpy())
        wx, wy = zx.copy(), zy.copy()
        for regime in xfull.regime.unique():
            mask = (xfull.regime==regime).to_numpy()
            wx[mask] -= wx[mask].mean(axis=0); wy[mask] -= wy[mask].mean(axis=0)
        within = (wx.T @ wy) / np.maximum(np.sqrt(np.sum(wx**2,axis=0)[:,None]*np.sum(wy**2,axis=0)[None,:]),1e-30)
        alpha_rows=[]; alpha_bordas={}
        for alpha in [10,1000]:
            _, aranks, ab, at, _, _ = association_scores(x.to_numpy(),y.to_numpy(),alpha=alpha)
            alpha_bordas[alpha]=ab
            for k,target in enumerate(targets):
                a,b=set(top[:,k]),set(at[:,k])
                alpha_rows.append({'target':target,'alpha':alpha,
                    'Top3':';'.join(features[at[:,k]]),'Jaccard_vs_alpha_100':len(a&b)/len(a|b)})
        pd.DataFrame(alpha_rows).to_csv(results/'question2_ridge_alpha_sensitivity.csv',index=False)
        g, communities, labels, modularity = graph_partition(d02, .6, seed)
        labelvector = [labels[v] for v in features]
        sensitivity = []
        for cutoff in [.4,.5,.6,.7,.8]:
            gg, cc, ll, qq = graph_partition(d02, cutoff, seed)
            sensitivity.append({'cutoff':cutoff,'seed':seed,'edges':gg.number_of_edges(),
                'communities':len(cc),'isolates':nx.number_of_isolates(gg),'modularity':qq,
                'ARI_vs_cutoff_0_6':adjusted_rand_score(labelvector,[ll[v] for v in features])})
        for otherseed in range(20):
            gg, cc, ll, qq = graph_partition(d02,.6,otherseed)
            sensitivity.append({'cutoff':.6,'seed':otherseed,'edges':gg.number_of_edges(),
                'communities':len(cc),'isolates':nx.number_of_isolates(gg),'modularity':qq,
                'ARI_vs_cutoff_0_6':adjusted_rand_score(labelvector,[ll[v] for v in features])})
        pd.DataFrame(sensitivity).to_csv(results/'question2_network_sensitivity.csv',index=False)
        freq = np.zeros((len(features),len(targets)))
        mfreq = np.zeros((3,len(features),len(targets)))
        modfreq = np.zeros((len(communities),len(targets)))
        boot_rows = []; graph_boot = []
        rng = np.random.default_rng(seed)
        for b in range(bootstrap):
            ids = rng.integers(0,len(x),len(x))
            xb, yb = x.to_numpy()[ids],y.to_numpy()[ids]
            _, _, _, bt, mt, _ = association_scores(xb,yb)
            for k,target in enumerate(targets):
                freq[bt[:,k],k] += 1
                mods = set(labels[features[j]]-1 for j in bt[:,k])
                for m in mods: modfreq[m,k] += 1
                for method in range(3): mfreq[method,mt[method,:,k],k] += 1
                boot_rows.append({'replicate':b+1,'target':target,
                    **{f'top{j+1}':features[bt[j,k]] for j in range(3)}})
            if b < min(40,bootstrap):
                bcorr = pd.DataFrame(xb,columns=features).corr(method='spearman')
                bg, bc, bl, bq = graph_partition(bcorr,.6,seed)
                ref_edges={tuple(sorted(e)) for e in g.edges}
                b_edges={tuple(sorted(e)) for e in bg.edges}
                graph_boot.append({'replicate':b+1,'edges':bg.number_of_edges(),
                    'communities':len(bc),'modularity':bq,
                    'ARI_vs_full':adjusted_rand_score(labelvector,[bl[v] for v in features]),
                    'edge_Jaccard':len(ref_edges & b_edges)/len(ref_edges | b_edges)})
        freq /= bootstrap; mfreq /= bootstrap; modfreq /= bootstrap
    allrows=[]; selected=[]; method_j=[]
    metai=meta.drop_duplicates('var_id').set_index('var_id')
    for k,target in enumerate(targets):
        jacc=[]
        for a,b in [(0,1),(0,2),(1,2)]:
            sa=set(method_top[a,:,k]); sb=set(method_top[b,:,k])
            jac=len(sa & sb)/len(sa | sb); jacc.append(jac)
            method_j.append({'target':target,'method_a':METHODS[a],'method_b':METHODS[b],
                'Jaccard':jac,'a_top3':';'.join(features[list(method_top[a,:,k])]),
                'b_top3':';'.join(features[list(method_top[b,:,k])])})
        for j,v in enumerate(features):
            row={'target':target,'feature':v,'borda_mean_rank':borda[j,k],
                'spearman_signed_after_median_imputation':signed[j,k],
                'within_regime_rank_correlation':within[j,k],
                'bootstrap_selection_frequency':freq[j,k],
                'bootstrap_MC_standard_error':np.sqrt(freq[j,k]*(1-freq[j,k])/bootstrap),
                'module':labels[v], 'fixed_module_selection_frequency':modfreq[labels[v]-1,k],
                'mean_method_Jaccard':np.mean(jacc)}
            for alpha in [10,1000]: row[f'borda_mean_rank_alpha_{alpha}']=alpha_bordas[alpha][j,k]
            for m,name in enumerate(METHODS):
                row[name+'_score']=values[m,j,k]; row[name+'_rank']=ranks[m,j,k]
                row[name+'_bootstrap_frequency']=mfreq[m,j,k]
            if v in metai.index:
                for name in ['source_group','unit_code','trend','threshold_mean','threshold_median']:
                    row[name]=metai.loc[v,name]
            row['derived_feature']=v in ['V037','V228','V229','V230','V231']
            row['D06_same_data_reference_correlation']=d06.loc[v,target] if v in d06.index else np.nan
            row['global_reference_importance_unknown_procedure']=global_ref.loc[v,'importance'] if v in global_ref.index else np.nan
            allrows.append(row)
            if j in top[:,k]:
                row=row.copy(); row['top_rank']=int(np.where(top[:,k]==j)[0][0]+1)
                selected.append(row)
    allframe=pd.DataFrame(allrows); topframe=pd.DataFrame(selected).sort_values(['target','top_rank'])
    allframe.to_csv(results/'question2_all_feature_scores.csv',index=False)
    topframe.to_csv(results/'question2_top3.csv',index=False)
    pd.DataFrame(boot_rows).to_csv(results/'question2_bootstrap_top3.csv',index=False)
    pd.DataFrame(method_j).to_csv(results/'question2_method_Jaccard.csv',index=False)
    pd.DataFrame(graph_boot).to_csv(results/'question2_network_bootstrap.csv',index=False)
    edges=pd.DataFrame([{'feature_a':a,'feature_b':b,**d} for a,b,d in g.edges(data=True)])
    edges.to_csv(results/'question2_network_edges.csv',index=False)
    nodeframe=pd.DataFrame([{'feature':v,'module':labels[v],'degree':g.degree[v],
        'strength':g.degree(v,weight='weight'), 'source_group':metai.loc[v,'source_group']} for v in features])
    nodeframe.to_csv(results/'question2_network_nodes.csv',index=False)
    modrows=[{'target':t,'module':m+1,'module_size':len(communities[m]),
        'any_top3_bootstrap_frequency':modfreq[m,k]} for m in range(len(communities)) for k,t in enumerate(targets)]
    pd.DataFrame(modrows).to_csv(results/'question2_module_stability.csv',index=False)
    threshold=threshold_analysis(x,y,native,meta)
    threshold.to_csv(results/'question2_threshold_hinge_exploratory.csv',index=False)
    audit.update({'network_cutoff':.6,'edges':g.number_of_edges(),'communities':len(communities),
        'isolates':nx.number_of_isolates(g),'modularity':modularity,
        'top3_frequency_median':float(topframe.bootstrap_selection_frequency.median()),
        'top3_frequency_min':float(topframe.bootstrap_selection_frequency.min()),
        'top3_frequency_ge_0_8':int((topframe.bootstrap_selection_frequency>=.8).sum()),
        'mean_method_Jaccard':float(pd.DataFrame(method_j).Jaccard.mean()),
        'threshold_hinge_tests':len(threshold),
        'threshold_hinge_q_BH_below_0_05':int((threshold.q_BH_exploratory<.05).sum()) if len(threshold) else 0,
        'threshold_hinge_q_BH_HC3_below_0_05':int((threshold.q_BH_HC3_exploratory<.05).sum()) if len(threshold) else 0,
        'top3_overall_within_regime_sign_reversals':int((topframe.spearman_signed_after_median_imputation*topframe.within_regime_rank_correlation<0).sum()),
        'network_bootstrap_ARI_median':float(pd.DataFrame(graph_boot).ARI_vs_full.median()),
        'network_bootstrap_edge_Jaccard_median':float(pd.DataFrame(graph_boot).edge_Jaccard.median())})
    (results/'question2_summary.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')

    # 图一完整展示231×231强度和符号，模块顺序仅用于排版。
    order=sorted(features,key=lambda v:(labels[v],v))
    fig,ax=plt.subplots(figsize=(10,9)); im=ax.imshow(d02.loc[order,order],vmin=-1,vmax=1,cmap='coolwarm')
    boundary=0
    for c in communities[:-1]:
        boundary+=len(c)
        if len(c)>1:
            ax.axhline(boundary-.5,color='black',lw=.4); ax.axvline(boundary-.5,color='black',lw=.4)
    ax.set(title='D02: signed Spearman correlation, ordered by |rho| modules',xlabel='231 variables',ylabel='231 variables')
    ax.set_xticks([]); ax.set_yticks([]); fig.colorbar(im,ax=ax,label='Spearman rho')
    fig.tight_layout(); fig.savefig(figures/'question2_correlation_modules.png',dpi=160); plt.close(fig)
    # 图二直接显示全部50个目标的三个名字与实际重采样频率。
    mat=topframe.pivot(index='target',columns='top_rank',values='bootstrap_selection_frequency').loc[targets].to_numpy()
    names=topframe.pivot(index='target',columns='top_rank',values='feature').loc[targets].to_numpy()
    fig,ax=plt.subplots(figsize=(8,15)); im=ax.imshow(mat,vmin=0,vmax=1,cmap='YlGnBu',aspect='auto')
    for i in range(50):
        for j in range(3): ax.text(j,i,f'{names[i,j]}  {mat[i,j]:.2f}',ha='center',va='center',fontsize=7,color='white' if mat[i,j]>.6 else 'black')
    ax.set_yticks(np.arange(50),targets,fontsize=7); ax.set_xticks([0,1,2],['Top 1','Top 2','Top 3'])
    ax.set_title(f'Borda Top-3, bootstrap inclusion frequency (B={bootstrap})')
    fig.colorbar(im,ax=ax,pad=.03,label='Empirical inclusion frequency'); fig.tight_layout()
    fig.savefig(figures/'question2_top3_stability.png',dpi=160); plt.close(fig)
    # 图三把孤点单列，避免101个孤点把有边的结构挤在图中心。
    components=sorted(nx.connected_components(g),key=lambda c:(-len(c),min(c)))
    large=g.subgraph(components[0]); small=[c for c in components[1:] if len(c)>1]
    isolated=sorted(nx.isolates(g)); counts=topframe.feature.value_counts()
    fig=plt.figure(figsize=(15,11)); grid=fig.add_gridspec(3,4,height_ratios=[1,1,.65])
    ax=fig.add_subplot(grid[:2,:3]); ax.axis('off')
    pos=nx.spring_layout(large,seed=seed,k=.3,weight='weight',iterations=300)
    nx.draw_networkx_edges(large,pos,ax=ax,alpha=.3,width=.6)
    nx.draw_networkx_nodes(large,pos,ax=ax,node_size=[28+3*g.degree[v] for v in large.nodes],
        node_color=[plt.colormaps['tab20']((labels[v]-1)%20) for v in large.nodes],alpha=.9)
    lab={v:v for v in counts.head(20).index if v in large}
    nx.draw_networkx_labels(large,pos,labels=lab,ax=ax,font_size=9)
    ax.set_title('Largest connected component: 99 variables; colors = modules')
    side=fig.add_subplot(grid[:2,3]); side.axis('off')
    side.set_title(f'Other {len(small)} nontrivial components')
    for k,members in enumerate(small):
        sg=g.subgraph(members); sp=nx.circular_layout(sg)
        sp={v:(p[0]*.8,p[1]*.25-k) for v,p in sp.items()}
        nx.draw_networkx_edges(sg,sp,ax=side,width=.7,alpha=.6)
        nx.draw_networkx_nodes(sg,sp,ax=side,node_size=30,
            node_color=[plt.colormaps['tab20']((labels[v]-1)%20) for v in sg])
        nx.draw_networkx_labels(sg,sp,ax=side,font_size=6)
    bottom=fig.add_subplot(grid[2,:]); bottom.axis('off')
    isolines=['  '.join(isolated[i:i+13]) for i in range(0,len(isolated),13)]
    bottom.text(0,.98,f'{len(isolated)} isolated variables at this cutoff (all listed):\n'+'\n'.join(isolines),
        transform=bottom.transAxes,ha='left',va='top',fontsize=9,family='monospace')
    fig.suptitle(f'Covariation strength network: |rho| >= 0.60, {g.number_of_edges()} edges; 19 nontrivial modules + 101 singleton modules',fontsize=12)
    fig.tight_layout(); fig.savefig(figures/'question2_network.png',dpi=160); plt.close(fig)
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--bootstrap',type=int,default=200)
    parser.add_argument('--seed',type=int,default=20261026); args=parser.parse_args()
    if args.bootstrap < 1: raise ValueError('bootstrap must be positive')
    main(args.bootstrap,args.seed)
