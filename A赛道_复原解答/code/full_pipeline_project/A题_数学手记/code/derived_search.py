"""有限的纯数学候选识别：只用训练对象选择公式，再报告未参与选择对象的误差。"""
from pathlib import Path
import csv
from decimal import Decimal
import numpy as np
import pandas as pd
from sklearn.linear_model import OrthogonalMatchingPursuit
from derived_relations import CANDIDATE_COEFFICIENTS, candidate_derived_from_native

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'A题_数学手记' / 'results'
DERIVED = ['V037','V228','V229','V230','V231']


def main():
    data = pd.read_csv(ROOT/'data'/'D01.csv').set_index('object')
    reference = pd.read_excel(ROOT/'data'/'D08.xlsx',sheet_name='ref_scale').set_index('object')
    base = [c for c in data.columns if c.startswith('V') and c not in DERIVED]
    x = data[base].copy()
    # 两种已知尺度分别成为候选，不把未核验的变量猜成对数。
    for i in range(1,37):
        v=f'V{i:03d}'
        x[f'native_{v}'] = reference[v]
    rng=np.random.default_rng(20261026)
    order=rng.permutation(len(data))
    tr,va=order[:165],order[165:]
    median=x.iloc[tr].median()
    array=x.fillna(median).to_numpy()
    mean=array[tr].mean(axis=0)
    sd=array[tr].std(axis=0)
    sd[sd<1e-12]=1
    z=(array-mean)/sd
    names=x.columns.to_list()
    response, response_names=[],[]
    for target in DERIVED:
        for transform in ['recorded','power10']:
            response.append(data[target].to_numpy() if transform=='recorded' else 10.**data[target].to_numpy())
            response_names.append((target,transform))
    response=np.array(response).T
    records=[]
    # 稀疏拟合最多六项，防止用接近样本数的自由度插值。
    for j,(target,transform) in enumerate(response_names):
        y=response[:,j]
        ti=tr[np.isfinite(y[tr])]
        vi=va[np.isfinite(y[va])]
        for k in [1,2,3,4,6]:
            model=OrthogonalMatchingPursuit(n_nonzero_coefs=k).fit(z[ti],y[ti])
            ptr,pva=model.predict(z[ti]),model.predict(z[vi])
            denominator=max(np.std(y[ti]),1e-12)
            coefs=model.coef_/sd
            intercept=float(model.intercept_-np.sum(coefs*mean))
            active=np.flatnonzero(coefs)
            formula=f'{intercept:.12g}' + ''.join(f' {coefs[q]:+.12g}*{names[q]}' for q in active)
            records.append({'target':target,'target_scale':transform,'family':'sparse_linear','terms':k,
                            'formula':formula,'n_train':len(ti),'n_holdout':len(vi),
                            'train_RMSE':float(np.sqrt(np.mean((ptr-y[ti])**2))),
                            'holdout_RMSE':float(np.sqrt(np.mean((pva-y[vi])**2))),
                            'holdout_nRMSE_train_sd':float(np.sqrt(np.mean((pva-y[vi])**2))/denominator),
                            'holdout_max_abs_error':float(np.max(np.abs(pva-y[vi])))})
    # 成对和/差/积/比，每个候选仅拟合一个斜率和截距；按训练残差选前3再看留出。
    # 循环按第二个变量分块，避免生成庞大的永久中间文件。
    best={j:[] for j in range(len(response_names))}
    for b in range(len(names)):
        if b==0:
            continue
        a=array[:,:b]
        bb=array[:,b:b+1]
        ops={'sum':a+bb,'difference':a-bb,'product':a*bb}
        safe_b=np.where(np.abs(bb)>1e-12,bb,np.nan)
        safe_a=np.where(np.abs(a)>1e-12,a,np.nan)
        ops['ratio']=a/safe_b
        ops['reverse_ratio']=bb/safe_a
        for op,f in ops.items():
            for j in range(len(response_names)):
                yy=response[:,j]
                ti=tr[np.isfinite(yy[tr])]
                ft=f[ti]
                finite=np.isfinite(ft).all(axis=0)
                if not finite.any():
                    continue
                q=np.flatnonzero(finite)
                ft=ft[:,q]
                fc=ft-ft.mean(axis=0)
                yc=yy[ti]-yy[ti].mean()
                variance=np.sum(fc*fc,axis=0)
                slope=np.divide(fc.T@yc,variance,out=np.zeros_like(variance),where=variance>1e-20)
                intercept=yy[ti].mean()-slope*ft.mean(axis=0)
                rmse=np.sqrt(np.mean((ft*slope+intercept-yy[ti,None])**2,axis=0))
                for ii in np.argsort(rmse)[:3]:
                    candidate=(float(rmse[ii]),int(q[ii]),b,op,float(slope[ii]),float(intercept[ii]))
                    best[j].append(candidate)
                best[j]=sorted(best[j],key=lambda row:row[0])[:3]
    for j,candidates in best.items():
        target,transform=response_names[j]
        yy=response[:,j]
        ti=tr[np.isfinite(yy[tr])]
        vi=va[np.isfinite(yy[va])]
        for training_error,a,b,op,slope,intercept in candidates:
            aa,bb=array[vi,a],array[vi,b]
            ff={'sum':lambda:aa+bb,'difference':lambda:aa-bb,'product':lambda:aa*bb,
                'ratio':lambda:aa/bb,'reverse_ratio':lambda:bb/aa}[op]()
            pred=intercept+slope*ff
            finite=np.isfinite(pred)
            error=pred[finite]-yy[vi][finite]
            denominator=max(np.std(yy[ti]),1e-12)
            records.append({'target':target,'target_scale':transform,'family':'pair_formula','terms':2,
                            'formula':f'{intercept:.12g} {slope:+.12g}*{op}({names[a]},{names[b]})',
                            'n_train':len(ti),'n_holdout':int(finite.sum()),'train_RMSE':training_error,
                            'holdout_RMSE':float(np.sqrt(np.mean(error**2))),
                            'holdout_nRMSE_train_sd':float(np.sqrt(np.mean(error**2))/denominator),
                            'holdout_max_abs_error':float(np.max(np.abs(error)))})
    result=pd.DataFrame(records)
    result.to_csv(OUT/'data_audit_derived_candidates.csv',index=False,encoding='utf-8-sig')
    result.groupby(['target','target_scale']).apply(lambda g:g.sort_values('train_RMSE').head(1),include_groups=False).to_csv(
        OUT/'data_audit_derived_train_selected.csv',encoding='utf-8-sig')
    split=pd.DataFrame({'object':data.index,'partition':['train' if i in set(tr) else 'holdout' for i in range(len(data))]})
    split.to_csv(OUT/'data_audit_derived_partition.csv',index=False,encoding='utf-8-sig')
    # 第一轮发现V228/V229的幂尺度有近似加性结构，再有限扩展候选原生参照。
    # 仍仅按同一165个训练对象拟合；最多16个非零系数，远少于训练样本数。
    refined=x.copy()
    for v in reference:
        if v.startswith('V') and v not in DERIVED:
            refined[f'native_{v}']=reference[v]
    aa=refined.fillna(refined.iloc[tr].median()).to_numpy()
    mm,ss=aa[tr].mean(axis=0),aa[tr].std(axis=0)
    ss[ss<1e-12]=1
    zz=(aa-mm)/ss
    refinement=[]
    for target in ['V228','V229']:
        yy=10.**data[target].to_numpy()
        ti=tr[np.isfinite(yy[tr])]
        vi=va[np.isfinite(yy[va])]
        for k in [6,8,10,12,16]:
            model=OrthogonalMatchingPursuit(n_nonzero_coefs=k).fit(zz[ti],yy[ti])
            coefs=model.coef_/ss
            intercept=float(model.intercept_-np.sum(coefs*mm))
            active=np.flatnonzero(coefs)
            formula=f'{intercept:.12g}' + ''.join(f' {coefs[q]:+.12g}*{refined.columns[q]}' for q in active)
            error=model.predict(zz[vi])-yy[vi]
            refinement.append({'target':target,'terms':k,'formula':formula,'n_train':len(ti),'n_holdout':len(vi),
                               'train_RMSE':float(np.sqrt(np.mean((model.predict(zz[ti])-yy[ti])**2))),
                               'holdout_RMSE':float(np.sqrt(np.mean(error**2))),
                               'holdout_nRMSE_train_sd':float(np.sqrt(np.mean(error**2))/np.std(yy[ti])),
                               'holdout_max_abs_error':float(np.max(np.abs(error)))})
    pd.DataFrame(refinement).to_csv(OUT/'data_audit_derived_refinement.csv',index=False,encoding='utf-8-sig')
    # 简洁系数是探索后的候选：以下全对象误差用于代数一致性，不能叫新的独立泛化评估。
    raw_frame=data.copy()
    for i in range(1,38):
        v=f'V{i:03d}'
        raw_frame[v]=reference[v]
    aggregate=candidate_derived_from_native(raw_frame)
    consistency=[]
    details=[]
    for target in DERIVED:
        observed=data[target]
        predicted=np.log10(aggregate[target])
        good=observed.notna() & predicted.notna()
        error=predicted[good]-observed[good]
        consistency.append({'target':target,'source':'ref_first37_D01_others','n_valid_pairs':int(good.sum()),
                            'recorded_MAE':float(error.abs().mean()),'recorded_max_abs_error':float(error.abs().max()),
                            'scope':'exploratory algebraic consistency, not independent generalization'})
        details.extend(pd.DataFrame({'object':data.index[good],'target':target,'recorded_observed':observed[good],
                                     'recorded_candidate':predicted[good],'difference':error}).to_dict('records'))
    # V229六源的参照版本另算，避免与D01不同精度、不同单元格的版本混同。
    coefficients=CANDIDATE_COEFFICIENTS['V229']
    qref=reference[list(coefficients)].mul(pd.Series(coefficients),axis=1).sum(axis=1,min_count=len(coefficients))
    eref=np.log10(qref)-data['V229']
    consistency.append({'target':'V229','source':'ref_scale_six_components','n_valid_pairs':int(eref.notna().sum()),
                        'recorded_MAE':float(eref.abs().mean()),'recorded_max_abs_error':float(eref.abs().max()),
                        'scope':'exploratory algebraic consistency, not independent generalization'})
    pd.DataFrame(consistency).to_csv(OUT/'data_audit_derived_consistency.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(details).to_csv(OUT/'data_audit_derived_consistency_by_object.csv',index=False,encoding='utf-8-sig')
    precision=[]
    with open(ROOT/'data'/'D01.csv',encoding='utf-8-sig',newline='') as handle:
        for row in csv.DictReader(handle):
            if not row['V229']:
                continue
            recorded=float(row['V229'])
            qsum=sum(weight*float(row[var]) for var,weight in coefficients.items())
            delta_q=sum(abs(weight)*0.5*10.**Decimal(row[var]).as_tuple().exponent for var,weight in coefficients.items())
            delta_y=0.5*10.**Decimal(row['V229']).as_tuple().exponent
            candidate=np.log10(qsum)
            q_lower,q_upper=qsum-delta_q,qsum+delta_q
            log_lower,log_upper=np.log10(q_lower),np.log10(q_upper)
            target_lower,target_upper=recorded-delta_y,recorded+delta_y
            allowed=max(candidate-log_lower,log_upper-candidate)+delta_y
            precision.append({'object':int(row['object']),'recorded_observed':recorded,'recorded_candidate':candidate,
                              'log_abs_difference':abs(candidate-recorded),'aggregate_delta_from_decimal_precision':delta_q,
                              'candidate_log_lower':log_lower,'candidate_log_upper':log_upper,
                              'observed_log_lower':target_lower,'observed_log_upper':target_upper,
                              'rounding_intervals_intersect':bool(max(log_lower,target_lower)<=min(log_upper,target_upper)),
                              'difference_divided_by_allowed':abs(candidate-recorded)/allowed})
    precision=pd.DataFrame(precision)
    precision.to_csv(OUT/'data_audit_V229_decimal_precision.csv',index=False,encoding='utf-8-sig')
    print(result.sort_values(['target','target_scale','train_RMSE']).groupby(['target','target_scale']).head(1).to_string(index=False))
    print(pd.DataFrame(refinement).to_string(index=False))
    print(pd.DataFrame(consistency).to_string(index=False))
    print('V229 rounding interval overlap:',int(precision.rounding_intervals_intersect.sum()),'/',len(precision),
          'max discrepancy / allowed:',precision.difference_divided_by_allowed.max())


if __name__=='__main__':
    main()
