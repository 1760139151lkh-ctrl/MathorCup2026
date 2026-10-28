"""针对实测零原子失真的修复：收缩类别经验边际+共享高斯相关旋钮。

每列取值来自训练数据的离散广义逆；零和负值不会被插值跨过。
相关矩阵控制组合关系；规定的边际概率不依赖潜在类均值或原方差。
"""
from __future__ import annotations

import numpy as np
from scipy.special import ndtr, ndtri
from sklearn.covariance import LedoitWolf

from generation import ConditionalGaussian


class ShrunkEmpiricalCopula:
    def __init__(self, tau=5.0):
        self.tau=tau

    def fit(self,x,groups):
        a=np.asarray(x,dtype=float)
        self.groups=np.asarray(groups)
        self.n_features_=a.shape[1]
        self.classes=np.unique(self.groups)
        self.counts={c:int(np.sum(self.groups==c)) for c in self.classes}
        # 几何接口只供统一留出距离与迁移相容性描述，不用于新采样的类均值位移。
        self.geometry=ConditionalGaussian().fit(x,groups)
        self.imputer=self.geometry.imputer
        self.global_values=[np.sort(a[np.isfinite(a[:,j]),j]) for j in range(self.n_features_)]
        self.margins={}
        self.marginal_counts={}
        for c in self.classes:
            self.margins[c]=[]
            self.marginal_counts[c]=[]
            for j,global_values in enumerate(self.global_values):
                local=np.sort(a[(self.groups==c)&np.isfinite(a[:,j]),j])
                # 这一列的NA没有贡献CDF证据，收缩权重按该列实际观测数。
                local_weight=len(local)/(len(local)+self.tau) if len(local) else 0.
                self.marginal_counts[c].append(len(local))
                values=np.concatenate([local,global_values])
                weights=np.concatenate([np.full(len(local),local_weight/max(len(local),1)),
                                        np.full(len(global_values),(1-local_weight)/len(global_values))])
                order=np.argsort(values,kind="stable")
                values,weights=values[order],weights[order]
                cumulative=np.cumsum(weights)
                cumulative[-1]=1.
                self.margins[c].append((values,weights,cumulative))
        # 离散变量用质量块中点排名估计依赖；这是一种近似，不是连续copula定理。
        scores=np.zeros_like(a)
        for c in self.classes:
            rows=np.flatnonzero(self.groups==c)
            for j,(values,weights,cumulative) in enumerate(self.margins[c]):
                observed=np.isfinite(a[rows,j])
                raw=a[rows[observed],j]
                left=np.searchsorted(values,raw,side="left")
                right=np.searchsorted(values,raw,side="right")
                before=np.where(left>0,cumulative[np.maximum(left-1,0)],0.)
                through=np.where(right>0,cumulative[np.maximum(right-1,0)],0.)
                mid=.5*(before+through)
                scores[rows[observed],j]=ndtri(np.clip(mid,1e-6,1-1e-6))
        estimator=LedoitWolf().fit(scores)
        covariance=estimator.covariance_
        sd=np.sqrt(np.maximum(np.diag(covariance),1e-12))
        self.correlation=covariance/np.outer(sd,sd)
        np.fill_diagonal(self.correlation,1.)
        values,vectors=np.linalg.eigh(self.correlation)
        self.factor=vectors*np.sqrt(np.maximum(values,1e-10))
        self.shrinkage=float(estimator.shrinkage_)
        return self

    def transform(self,x):
        return self.geometry.transform(x)

    def mean(self,group):
        return self.geometry.mean(group)

    def sample(self,group,n,rng):
        # diag(R)=1使每列Z为标准正态，Phi(Z)才是Uniform；不叠加class shift。
        z=rng.normal(size=(n,self.n_features_))@self.factor.T
        uniforms=ndtr(z)
        result=np.empty_like(uniforms)
        for j,(values,weights,cumulative) in enumerate(self.margins[group]):
            indexes=np.searchsorted(cumulative,uniforms[:,j],side="left")
            result[:,j]=values[np.minimum(indexes,len(values)-1)]
        return result

    def nll(self,x,groups):
        # 该模型是有原子的联合分布，不能继续冒充全局rank Gaussian密度。
        return np.full(len(x),np.nan)

    def atom_probability(self,group,column_index,value=0.):
        values,weights,_=self.margins[group][column_index]
        return float(weights[values==value].sum())
