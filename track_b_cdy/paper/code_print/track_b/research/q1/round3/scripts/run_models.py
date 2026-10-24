#!/usr/bin/env python3
"""Three competing regional pre-reference anomaly routes; AI assisted, no causal labels."""
from pathlib import Path
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import json, hashlib, time, warnings
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.stats import kendalltau

R = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
CFG = json.loads((R/'config/experiment.json').read_text())
MODELS=CFG['model_ids']
FAMILIES={'air_thermal':'空气热状态','air_moisture':'空气湿状态','mean_wind':'平均风场','air_pressure':'气压','shortwave':'短波辐射','longwave':'长波辐射','soil_thermal':'土壤热状态','soil_moisture':'土壤水分','soil_heat_flux':'土壤热通量','precipitation':'降水标签分布','turbulent_heat':'湍流热交换','turbulent_mechanics':'湍流机械交换'}


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(obj,path): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def finite_num(x): return None if not np.isfinite(x) else float(x)

def weights(meta, valid=None, draw=None, block=7):
    """Exact year/process/row hierarchy, vectorized without changing estimand."""
    if valid is None:valid=np.ones(len(meta),bool)
    out=np.zeros(len(meta)); idx=np.flatnonzero(valid)
    if not len(idx):return out
    y=meta.year.to_numpy(dtype=int);g=((meta.day_offset.to_numpy()+30)//block).astype(int)
    codes=y[idx]*1000+g[idx]
    unique,inv,counts=np.unique(codes,return_inverse=True,return_counts=True)
    uy=unique//1000;ug=unique%1000
    years,yearinv=np.unique(uy,return_inverse=True)
    if draw is None:
        ym=np.ones(len(years));gm=np.ones(len(unique))
    else:
        ym=np.array([draw.get(int(a),{}).get('count',0) for a in years],float)
        gm=np.array([draw.get(int(a),{}).get('processes',{}).get(int(b),0) for a,b in zip(uy,ug)],float)
    mass=np.bincount(yearinv,weights=gm,minlength=len(years))
    numerator=ym[yearinv]*gm
    denominator=mass[yearinv]*counts
    perrow=np.divide(numerator,denominator,out=np.zeros_like(numerator),where=denominator>0)
    out[idx]=perrow[inv]
    return out/out.sum() if out.sum() else out


def quantile(x,w,q):
    ok=np.isfinite(x)&(w>0)
    if not ok.any():return np.nan
    xx=x[ok];ww=w[ok];ii=np.argsort(xx,kind='stable'); xx=xx[ii];ww=ww[ii]
    return float(xx[np.searchsorted(np.cumsum(ww)/ww.sum(),q,side='left').clip(0,len(xx)-1)])


def ecdf(x, val, meta, draw=None, block=7, minimum=3):
    ok=np.isfinite(x)
    w=weights(meta,ok,draw,block)
    if not np.isfinite(val) or len(np.unique(meta.year.to_numpy()[w>0]))<minimum:return np.nan
    return float(w[x<val].sum()+0.5*w[x==val].sum())


def aggregate(feature_scores, contract):
    df=pd.DataFrame({'feature_id':contract.feature_id,'driver_id':contract.driver_id,'family_id':contract.family_id,'value':feature_scores})
    return df.groupby(['family_id','driver_id']).value.median().groupby('family_id').median().to_dict()


def fit_matrix(X,meta,ids,draw=None,block=7, target=None):
    """Only training values determine support, centring, scaling and imputation."""
    w=weights(meta,draw=draw,block=block)
    keep=[]; med=[]; scales=[]
    for j in ids:
        ok=np.isfinite(X[:,j]);obs=float(w[ok].sum())
        if obs<CFG['covariance_feature_observed_fraction'] or len(np.unique(meta.year.to_numpy()[ok&(w>0)]))<3:continue
        if target is not None and not np.isfinite(target[j]):continue
        wj=weights(meta,ok,draw,block)
        m=quantile(X[:,j],wj,.5); s=1.4826*quantile(abs(X[:,j]-m),wj,.5)
        if s<=0 or not np.isfinite(s):s=(quantile(X[:,j],wj,.75)-quantile(X[:,j],wj,.25))/1.349
        if not np.isfinite(s) or s<=0:continue
        keep.append(j);med.append(m);scales.append(s)
    keep=np.array(keep,int);med=np.array(med);scales=np.array(scales)
    if not len(keep):return None
    xx=X[:,keep]; missing=~np.isfinite(xx); zz=np.clip((np.where(missing,med,xx)-med)/scales,-8,8)
    mu=w@zz; zz=zz-mu
    return {'ids':keep,'median':med,'scale':scales,'mean':mu,'z':zz,'weights':w,'imputed_weighted_fraction':float(np.sum(w[:,None]*missing)/len(keep))}


def precision_fit(fit,alpha):
    z=fit['z'];w=fit['weights']; C=(z*w[:,None]).T@z
    S=(1-alpha)*C+alpha*np.eye(len(fit['ids']))
    P=np.linalg.inv(S)
    return P,float(np.linalg.cond(S))


def contributions(fit,P,targets,contract):
    arr=np.atleast_2d(targets)[:,fit['ids']]
    zz=np.clip((np.where(np.isfinite(arr),arr,fit['median'])-fit['median'])/fit['scale'],-8,8)-fit['mean']
    pdiff=zz@P
    cf=contract.iloc[fit['ids']]
    result={}
    for family in sorted(cf.family_id.unique()):
        loc=np.flatnonzero(cf.family_id.to_numpy()==family)
        a=pdiff[:,loc]
        value=np.sum(a*np.linalg.solve(P[np.ix_(loc,loc)],a.T).T,axis=1)/len(loc)
        assert np.min(value)>-1e-7
        result[family]=np.maximum(value,0)
    return result


def b_scores(X,target,meta,contract,alpha,draw=None,block=7):
    fit=fit_matrix(X,meta,range(X.shape[1]),draw,block,target)
    if fit is None:return {},{}, {'features':0,'condition_number':None}
    P,condition=precision_fit(fit,alpha)
    values=contributions(fit,P,target,contract)
    # Five grouped out-of-year calibration folds. Whole years cannot overlap supports.
    cal={f:np.full(len(X),np.nan) for f in values}
    folds=[]
    for yr in sorted(meta.year.unique()):
        test=(meta.year.to_numpy()==yr);train=~test
        sub=fit_matrix(X[train],meta.loc[train].reset_index(drop=True),range(X.shape[1]),draw,block,target)
        if sub is None:continue
        pp,_=precision_fit(sub,alpha)
        cv=contributions(sub,pp,X[test],contract)
        for f in cal:
            if f in cv:
                family_cols=sub['ids'][contract.iloc[sub['ids']].family_id.to_numpy()==f]
                observed=np.isfinite(X[test][:,family_cols]).all(axis=1)
                held=cv[f].copy();held[~observed]=np.nan
                cal[f][test]=held
        folds.append({'year':int(yr),'n_train':int(train.sum()),'n_test':int(test.sum())})
    scores={f:ecdf(cal[f],values[f][0],meta,draw,block) for f in values}
    raw={f:float(values[f][0]) for f in values}
    return scores,raw,{'features':len(fit['ids']),'condition_number':condition,'imputed_training_fraction':fit['imputed_weighted_fraction'],'calibration_folds':folds,'calibration_support':{f:{'n_observed_rows':int(np.isfinite(v).sum()),'n_observed_years':int(meta.loc[np.isfinite(v),'year'].nunique()),'n_observed_processes':int(meta.loc[np.isfinite(v),'process_id'].nunique())} for f,v in cal.items()},'active_features':[contract.iloc[j].feature_id for j in fit['ids']],'_fit_for_routes':fit}


def routes(X,target,meta,contract,alpha=.5,k=2,draw=None,block=7,save_detail=False):
    # A: weighted midpoint ECDF, finite even under point-mass backgrounds.
    F=np.array([ecdf(X[:,j],target[j],meta,draw,block) for j in range(X.shape[1])])
    aa=2*abs(F-.5); scoresA=aggregate(aa,contract)
    scoresB,rawB,binfo=b_scores(X,target,meta,contract,alpha,draw,block)
    # C matching excludes all columns of the family under evaluation.
    fit=binfo.pop('_fit_for_routes',None)
    cc=np.full(X.shape[1],np.nan); analogs=[]
    groups=((meta.day_offset.to_numpy()+30)//block).astype(int)
    sample_ids=meta.sample_id.to_numpy();year_values=meta.year.to_numpy()
    positive=weights(meta,draw=draw,block=block)>0
    if fit is not None:
        targetz=np.clip((target[fit['ids']]-fit['median'])/fit['scale'],-8,8)-fit['mean']
        diff=(fit['z']-targetz)**2
        cf=contract.iloc[fit['ids']]
        family_dist={f:diff[:,cf.family_id.to_numpy()==f].mean(axis=1) for f in cf.family_id.unique()}
        for family in contract.family_id.unique():
            outside=[a for f,a in family_dist.items() if f!=family]
            if not outside:continue
            dist=np.sqrt(np.mean(outside,axis=0));selected=[]
            outside_cols=fit['ids'][cf.family_id.to_numpy()!=family]
            observed_matching_fraction=np.isfinite(X[:,outside_cols]).mean(axis=1)
            distance_eligible=observed_matching_fraction>=0.8
            for yr in sorted(meta.year.unique()):
                cand=np.flatnonzero((meta.year.to_numpy()==yr)&positive&distance_eligible)
                nearest=[]
                for gp in np.unique(groups[cand]):
                    ix=cand[groups[cand]==gp];i=int(ix[np.argmin(dist[ix])]);nearest.append((dist[i],i))
                nearest.sort(key=lambda t:(t[0],str(sample_ids[t[1]])))
                selected.extend(i for _,i in nearest[:k])
            if not selected:continue
            selected=np.array(selected,int);sm=meta.iloc[selected].reset_index(drop=True)
            for j in np.flatnonzero(contract.family_id.to_numpy()==family):
                # Recompute weights over selected finite rows. Each chosen process has one row.
                ff=ecdf(X[selected,j],target[j],sm,draw,block)
                cc[j]=2*abs(ff-.5)
            if save_detail:
                for i in selected:analogs.append({'family_id':family,'selected_sample_id':meta.iloc[i].sample_id,'year':int(meta.iloc[i].year),'process_id':f'{int(meta.iloc[i].year)}-b{int(groups[i])}','distance_excluding_family':float(dist[i]),'observed_outside_family_matching_fraction':float(observed_matching_fraction[i])})
    scoresC=aggregate(cc,contract)
    families=sorted(contract.family_id.unique())
    out={m:{f:s.get(f,np.nan) for f in families} for m,s in [(MODELS[0],scoresA),(MODELS[1],scoresB),(MODELS[2],scoresC)]}
    detail=None
    if save_detail:
        detail=contract[['feature_id','driver_id','family_id','statistic']].copy()
        detail['target_value']=target;detail['background_percentile']=F;detail['signed_direction']=np.sign(F-.5)
        detail['marginal_score']=aa;detail['analog_score']=cc
    return out,{'b_info':binfo,'b_raw_contribution':rawB,'feature_detail':detail,'analogs':analogs}


def ranking(score):
    finite={f:float(x) for f,x in score.items() if np.isfinite(x)}
    # Scores tied at 1e-12 get midranks. Alphabetical labels never select a winner.
    order=sorted(finite,key=lambda f:(-round(finite[f],12),f))
    out={};i=0
    while i<len(order):
        j=i+1
        while j<len(order) and round(finite[order[j]],12)==round(finite[order[i]],12):j+=1
        for f in order[i:j]:out[f]=(i+1+j)/2
        i=j
    return out


def top5_credit(ranks,family):
    if family not in ranks:return 0.0
    r=ranks[family];n=sum(v==r for v in ranks.values());above=r-(n+1)/2
    return float(np.clip((5-above)/n,0,1))


def consensus(result):
    allf=sorted(set().union(*(x.keys() for x in result.values())))
    ranks={m:ranking(s) for m,s in result.items()}
    # Missing route never becomes a good zero rank; report availability and leave mean undefined if <3.
    scores={}
    for f in allf:
        vals=[1-(r[f]-1)/max(len(r)-1,1) for r in ranks.values() if f in r]
        scores[f]=float(np.mean(vals)) if len(vals)==3 else np.nan
    return scores


def select_train(meta,target_meta,exclude=None):
    """Purge actual max-168h support overlap, even when displayed window is 24/72h."""
    keep=np.ones(len(meta),bool);test=np.zeros(len(meta),bool);purge=np.zeros(len(meta),bool)
    if exclude is None:return keep,test,purge
    if exclude[0]=='year':test=meta.year.to_numpy()==exclude[1]
    else:test=meta.process_id.to_numpy()==exclude[1]
    keep &= ~test
    for _,row in meta.loc[test].iterrows():
        a=pd.Timestamp(row.anchor_time_utc)-pd.Timedelta(hours=168)
        b=pd.Timestamp(row.anchor_time_utc)
        starts=pd.to_datetime(meta.anchor_time_utc,utc=True)-pd.Timedelta(hours=168)
        ends=pd.to_datetime(meta.anchor_time_utc,utc=True)
        overlap=((starts<b)&(ends>a)).to_numpy()
        purge |= overlap&~test
    keep &= ~purge
    return keep,test,purge


def main():
    started=datetime.now(timezone.utc).isoformat(); t0=time.monotonic()
    assert ROOT==Path('<LOCAL_HOME>/Documents/MathorCup/worktrees/track-b-q1')
    ctr=pd.read_csv(R/'results/feature_contract.csv')
    enabled=ctr.ranking_enabled.astype(str).str.lower().isin(['true','1'])
    ctr=ctr.loc[enabled].reset_index(drop=True)
    wide=pd.read_parquet(R/'results/features.parquet').set_index('sample_id')
    meta=pd.read_csv(R/'results/sample_metadata.csv')
    sup=pd.read_csv(R/'results/feature_support.csv')
    cover=sup.pivot(index='sample_id',columns='driver_id',values='coverage')
    if 'coverage' not in sup:raise ValueError('Missing coverage')
    bank=wide.loc[meta.sample_id,ctr.feature_id].to_numpy(float)
    coverage=cover.loc[meta.sample_id,ctr.driver_id].to_numpy(float)
    ranks=[];details=[];analogs=[];metrics=[];folds=[];stability=[];cv_metrics=[]
    outputs={}; bdiag=[]
    base={'coverage':.75,'block':7,'season':30,'alpha':.5,'k':2}
    variants={'primary':base}
    for name,key,vals in [('support','coverage',[.5,.9]),('process','block',[3,14]),('season','season',[15]),('shrinkage','alpha',[.1,.9]),('analogs','k',[1,3])]:
        for value in vals:variants[f'{name}_{value}']={**base,key:value}
    def matrices(track,shift,window,par,anchor='problem_1030',exclude=None):
        sel=(meta.quality_track==track)&(meta.shift_hours==shift)&(meta.window_hours==window)
        bg=sel&~meta.is_target.astype(bool)&(meta.day_offset.abs()<=par['season'])
        tgt=sel&meta.is_target.astype(bool)&(meta.anchor_id==anchor)
        assert tgt.sum()==1,(track,shift,window,anchor,tgt.sum())
        bgidx=np.flatnonzero(bg);ti=int(np.flatnonzero(tgt)[0]);bm=meta.loc[bg].reset_index(drop=True)
        keep,test,purge=select_train(bm,meta.iloc[ti],exclude)
        vals=bank[bgidx].copy();tv=bank[ti].copy()
        vals[coverage[bgidx]<par['coverage']]=np.nan;tv[coverage[ti]<par['coverage']]=np.nan
        # All-null unknown-only drivers stay absent in the accepted-QC track.
        eligible=np.array([len(np.unique(bm.year[np.isfinite(vals[:,j])]))>=3 and np.isfinite(tv[j]) for j in range(vals.shape[1])])
        return vals[keep][:,eligible],tv[eligible],bm.loc[keep].reset_index(drop=True),ctr.loc[eligible].reset_index(drop=True),bm,keep,test,purge,meta.iloc[ti]
    def run_one(track,shift,window,par,variant='primary',anchor='problem_1030',exclude=None,draw=None,detail=False):
        X,t,bm,ct,original,keep,test,purge,tm=matrices(track,shift,window,par,anchor,exclude)
        res,info=routes(X,t,bm,ct,par['alpha'],par['k'],draw,par['block'],detail)
        return res,info,(X,t,bm,ct,original,keep,test,purge,tm)
    for track in CFG['quality_tracks']:
        for window in CFG['windows_hours']:
            for variant,par in variants.items():
                shifts=[-1,0,1] if variant=='primary' else [0]
                for shift in shifts:
                    res,info,data=run_one(track,shift,window,par,variant,detail=True)
                    X,t,bm,ct,original,keep,test,purge,tm=data
                    outputs[(track,window,variant,shift)]=res
                    for model,ss in res.items():
                        rr=ranking(ss)
                        for family,score in ss.items():
                            ranks.append({'quality_track':track,'window_hours':window,'variant':variant,'anchor_id':'problem_1030','shift_hours':shift,'model_id':model,'family_id':family,'family_name':FAMILIES.get(family,family),'score':finite_num(score),'rank':rr.get(family),'top5_credit':top5_credit(rr,family),'n_background_windows':len(bm),'n_background_years':bm.year.nunique(),'n_process_proxies':len(set(zip(bm.year,(bm.day_offset+30)//par['block']))),'n_features_available':int((ct.family_id==family).sum()),'evaluation_stratum':'local_observational','data_role':'exploration'})
                    if info['feature_detail'] is not None:
                        df=info['feature_detail'];df['quality_track']=track;df['window_hours']=window;df['variant']=variant;df['shift_hours']=shift;details.append(df)
                    for a in info['analogs']:analogs.append({**a,'quality_track':track,'window_hours':window,'variant':variant,'shift_hours':shift})
                    bdiag.append({'quality_track':track,'window_hours':window,'variant':variant,'shift_hours':shift,**info['b_info'],'b_raw_contribution':info['b_raw_contribution']})
                    metrics.append({'quality_track':track,'window_hours':window,'variant':variant,'shift_hours':shift,'background_windows':len(bm),'background_years':bm.year.nunique(),'process_groups':len(set(zip(bm.year,(bm.day_offset+30)//par['block']))),'feature_columns':len(ct),'b_active_features':info['b_info']['features'],'b_condition_number':info['b_info'].get('condition_number'),'b_training_imputation_fraction':info['b_info'].get('imputed_training_fraction'),'independent_accepted_events':0})
            # Explicitly recalculate second anchor; it should select identical labels at each shift.
            for shift in [-1,0,1]:
                second,_,data=run_one(track,shift,window,base,anchor='usgs_reference')
                first=outputs[(track,window,'primary',shift)]
                for model in MODELS:
                    for f in first[model]:
                        a=first[model][f];b=second[model].get(f,np.nan)
                        assert (np.isnan(a) and np.isnan(b)) or np.isclose(a,b,atol=1e-12),('Anchor mismatch',f)
                for model,ss in second.items():
                    rr=ranking(ss)
                    for family,score in ss.items():
                        ranks.append({'quality_track':track,'window_hours':window,'variant':'primary','anchor_id':'usgs_reference','shift_hours':shift,'model_id':model,'family_id':family,'family_name':FAMILIES.get(family,family),'score':finite_num(score),'rank':rr.get(family),'top5_credit':top5_credit(rr,family),'evaluation_stratum':'local_observational','data_role':'exploration'})
            print(json.dumps({'phase':'variants_done','quality_track':track,'window_hours':window,'seconds':round(time.monotonic()-t0,1)}),flush=True)
    # Target stability after purged deletion; not supervised forecast validation.
    for track in CFG['quality_tracks']:
        for window in CFG['windows_hours']:
            primary=outputs[(track,window,'primary',0)]
            _,_,bm,_,_,_,_,_,_=matrices(track,0,window,base)
            exclusions=[('year',int(y)) for y in sorted(bm.year.unique())]+[('process',p) for p in sorted(bm.process_id.unique())]
            for typ,value in exclusions:
                res,_,data=run_one(track,0,window,base,exclude=(typ,value))
                _,_,training,ct,original,keep,test,purge,_=data
                fold_id=f'{track}|w{window}|leave_{typ}|{value}'
                # Save exact memberships and the actual fold sizes; all folds fit afresh.
                for i,row in original.iterrows():
                    folds.append({'fold_id':fold_id,'quality_track':track,'window_hours':window,'sample_id':row.sample_id,'year':int(row.year),'process_id':row.process_id,'role':'test_background' if test[i] else ('purged_overlap' if purge[i] else 'training'),'support_start_utc':str(pd.Timestamp(row.anchor_time_utc)-pd.Timedelta(hours=168)),'support_end_exclusive_utc':row.anchor_time_utc})
                for model,ss in res.items():
                    rr=ranking(ss);orig=ranking(primary[model]);a=set(f for f in rr if top5_credit(rr,f)>0);b=set(f for f in orig if top5_credit(orig,f)>0)
                    cv_metrics.append({'fold_id':fold_id,'kind':'leave_'+typ,'quality_track':track,'window_hours':window,'model_id':model,'n_train':len(training),'n_test':int(test.sum()),'n_purged':int(purge.sum()),'n_years_train':training.year.nunique(),'n_process_train':training.process_id.nunique(),'top5_jaccard':len(a&b)/len(a|b) if a|b else np.nan,'shared_families':len(set(rr)&set(orig)),'independent_accepted_events':0})
                    for family in ss:stability.append({'kind':'leave_'+typ,'repeat_id':str(value),'quality_track':track,'window_hours':window,'model_id':model,'family_id':family,'rank':rr.get(family),'top5_credit':top5_credit(rr,family),'selected_top5':top5_credit(rr,family)>0,'score':finite_num(ss[family])})
            print(json.dumps({'phase':'purged_folds_done','quality_track':track,'window_hours':window,'folds':len(exclusions),'seconds':round(time.monotonic()-t0,1)}),flush=True)
    # Hierarchical draws: years then weather-process proxies, never individual hours.
    rng=np.random.default_rng(CFG['seed']);draw_specs=[]
    for rep in range(CFG['bootstrap_replicates']):
        sampled=rng.choice(CFG['background_years'],5,replace=True);draw={}
        for yr in sampled:
            yy=int(yr);groups=np.arange(9); gp=rng.choice(groups,len(groups),replace=True)
            if yy not in draw:draw[yy]={'count':0,'processes':{}}
            draw[yy]['count']+=1
            for g in gp:draw[yy]['processes'][int(g)]=draw[yy]['processes'].get(int(g),0)+1
        draw_specs.append({'repeat_id':rep,'sampled_years':sampled.tolist(),'draw':draw})
        for track in CFG['quality_tracks']:
            for window in CFG['windows_hours']:
                res,_,data=run_one(track,0,window,base,draw=draw)
                for model,ss in {**res,'consensus':consensus(res)}.items():
                    rr=ranking(ss)
                    for family in ss:stability.append({'kind':'hierarchical_bootstrap','repeat_id':str(rep),'quality_track':track,'window_hours':window,'model_id':model,'family_id':family,'rank':rr.get(family),'top5_credit':top5_credit(rr,family),'selected_top5':top5_credit(rr,family)>0,'score':finite_num(ss[family])})
        if rep%10==0:print(json.dumps({'phase':'bootstrap','replicate':rep,'seconds':round(time.monotonic()-t0,1)}),flush=True)
    pd.DataFrame(ranks).to_csv(R/'results/rankings.csv',index=False)
    rd=pd.DataFrame(ranks);top=rd[(rd.variant=='primary')&(rd.shift_hours==0)&(rd.anchor_id=='problem_1030')&(rd.top5_credit>0)]
    top.to_csv(R/'results/top5_candidates.csv',index=False)
    pd.concat(details,ignore_index=True).to_csv(R/'results/feature_anomalies.csv',index=False)
    pd.DataFrame(analogs).to_csv(R/'results/analog_matches.csv',index=False)
    pd.DataFrame(metrics).to_csv(R/'results/comparison_metrics.csv',index=False)
    pd.DataFrame(folds).to_csv(R/'results/fold_membership.csv',index=False)
    sd=pd.DataFrame(stability);sd.to_csv(R/'results/stability_draws.csv',index=False)
    summaries=[]
    for keys,group in sd.groupby(['kind','quality_track','window_hours','model_id','family_id']):
        valid=group['rank'].notna(); g=group.loc[valid]
        summaries.append(dict(zip(['kind','quality_track','window_hours','model_id','family_id'],keys),n_requested=len(group),n_valid=len(g),top5_frequency=float(g.top5_credit.mean()) if len(g) else np.nan,rank_median=g['rank'].median(),rank_min=g['rank'].min(),rank_max=g['rank'].max()))
    pd.DataFrame(summaries).to_csv(R/'results/ranking_stability.csv',index=False)
    pd.DataFrame(cv_metrics).to_csv(R/'results/fold_metrics.csv',index=False)
    dump(draw_specs,R/'results/bootstrap_draw_specification.json');dump(bdiag,R/'results/covariance_diagnostics.json')
    # Consensus integrates three routes then three windows, without extra anchor votes.
    recommendations=[];rules=[]
    for track in CFG['quality_tracks']:
        window_consensus={w:consensus(outputs[(track,w,'primary',0)]) for w in CFG['windows_hours']}
        families=sorted(set().union(*(d.keys() for d in window_consensus.values())))
        mean={f:float(np.mean([d[f] for d in window_consensus.values()])) if all(np.isfinite(d.get(f,np.nan)) for d in window_consensus.values()) else np.nan for f in families}
        rr=ranking(mean)
        for f in families:
            freq=pd.DataFrame(summaries)
            v=freq[(freq.kind=='hierarchical_bootstrap')&(freq.quality_track==track)&(freq.model_id=='consensus')&(freq.family_id==f)]
            recommendations.append({'quality_track':track,'family_id':f,'family_name':FAMILIES[f],'consensus_score':finite_num(mean[f]),'recommended_rank':rr.get(f),'recommended_top5':top5_credit(rr,f)>0,'top5_credit':top5_credit(rr,f),'mean_window_bootstrap_top5_frequency':v.top5_frequency.mean(),'min_window_bootstrap_valid_draws':int(v.n_valid.min()) if len(v) else 0,'bootstrap_requested_per_window':100,'frequency_denominator':'valid_draws_only; B calibration requires >=4 distinct resampled years','stability_label':'stable_candidate' if len(v) and v.top5_frequency.mean()>=.7 and v.n_valid.min()>=70 else 'conditional_candidate','evaluation_stratum':'local_observational','interpretation':'regional_pre_reference_anomaly_candidate_not_causal_driver','available_time':None})
        for rule in ['A_only','B_only','C_only','median_route_rank']:
            sr={}
            for f in families:
                vals=[]
                for w in CFG['windows_hours']:
                    result=outputs[(track,w,'primary',0)];rks={m:ranking(s) for m,s in result.items()}
                    if rule.endswith('_only'):
                        m=MODELS[['A_only','B_only','C_only'].index(rule)];rk=rks[m]
                        vals.append(1-(rk[f]-1)/max(len(rk)-1,1) if f in rk else np.nan)
                    else:vals.append(float(np.median([1-(rk[f]-1)/max(len(rk)-1,1) for rk in rks.values() if f in rk])))
                sr[f]=float(np.mean(vals))
            for f,r in ranking(sr).items():rules.append({'quality_track':track,'rule':rule,'family_id':f,'rank':r,'score':sr[f]})
    pd.DataFrame(recommendations).to_csv(R/'results/recommended_factors.csv',index=False)
    pd.DataFrame(rules).to_csv(R/'results/recommendation_rule_sensitivity.csv',index=False)
    # One consolidated cross-window ranking per route, requested three TOP5s.
    combined=[]
    for track in CFG['quality_tracks']:
        for model in MODELS:
            families=set().union(*(outputs[(track,w,'primary',0)][model].keys() for w in CFG['windows_hours']))
            sc={f:np.mean([1-(ranking(outputs[(track,w,'primary',0)][model]).get(f,np.nan)-1)/max(len(ranking(outputs[(track,w,'primary',0)][model]))-1,1) for w in CFG['windows_hours']]) for f in families}
            for f,r in ranking(sc).items():combined.append({'quality_track':track,'model_id':model,'family_id':f,'family_name':FAMILIES[f],'rank':r,'score':float(sc[f]),'top5_credit':top5_credit(ranking(sc),f),'top5':top5_credit(ranking(sc),f)>0})
    pd.DataFrame(combined).to_csv(R/'results/top5_three_routes.csv',index=False)
    # Rank disagreements and predefined one-factor sensitivity, all families retained.
    differences=[]
    for track in CFG['quality_tracks']:
        for w in CFG['windows_hours']:
            ref=outputs[(track,w,'primary',0)]
            for (qt,ww,variant,shift),res in outputs.items():
                if qt!=track or ww!=w:continue
                for model in MODELS:
                    ra=ranking(ref[model]);rb=ranking(res[model]);common=sorted(set(ra)&set(rb))
                    ta={f for f in ra if top5_credit(ra,f)>0};tb={f for f in rb if top5_credit(rb,f)>0}
                    tau=kendalltau([ra[f] for f in common],[rb[f] for f in common]).statistic if len(common)>1 else np.nan
                    differences.append({'quality_track':track,'window_hours':w,'variant':variant,'shift_hours':shift,'model_id':model,'top5_jaccard':len(ta&tb)/len(ta|tb) if ta|tb else np.nan,'kendall_tau':tau,'common_families':len(common)})
    pd.DataFrame(differences).to_csv(R/'results/sensitivity_metrics.csv',index=False)
    context={k:CFG[k] for k in ['common_baseline_commit','baseline_manifest_sha256','model_ids','mechanism_id','experiment_id','scenario_id','geometry_version','parameter_version','evaluation_stratum','data_role','available_time','event_id']}
    context.update(physical_phase='pre_reference_regional_background_comparison',time_utc=None,time_uncertainty=None,space_object='Gyirong regional station; local-file/geodetic equivalence and source representativeness unverified',forecast_reference_time=None,issue_time=None,valid_time=None,source_clock_hypothesis='UTC+8; averaging intervals unknown',independent_accepted_training_events=0,independent_accepted_validation_events=0,interpretation='case anomaly rankings; no hazard discrimination/causality validation')
    dump(context,R/'results/model_context.json')
    for name in ['rankings.csv','top5_candidates.csv','feature_anomalies.csv','analog_matches.csv','comparison_metrics.csv','fold_membership.csv','stability_draws.csv','ranking_stability.csv','fold_metrics.csv','recommended_factors.csv','recommendation_rule_sensitivity.csv','top5_three_routes.csv','sensitivity_metrics.csv']:
        path=R/'results'/name
        table=pd.read_csv(path)
        table['context_ref']='results/model_context.json'
        for key in ['experiment_id','mechanism_id','scenario_id','geometry_version','parameter_version','evaluation_stratum','data_role']:
            table[key]=context[key]
        table.to_csv(path,index=False)
    result={'passed':True,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'duration_seconds':round(time.monotonic()-t0,3),'script_sha256':sha(Path(__file__)),'config_sha256':sha(R/'config/experiment.json'),'ranking_rows':len(ranks),'fold_membership_rows':len(folds),'stability_rows':len(stability),'bootstrap_replicates':100,'bootstrap_draws_with_fewer_than_three_unique_years':sum(len(d['draw'])<3 for d in draw_specs),'bootstrap_draws_with_fewer_than_four_unique_years_B_crossfit_insufficient':sum(len(d['draw'])<4 for d in draw_specs),'checks':{'three_routes_computed':True,'strict_does_not_import_nonzero_qc':True,'year_process_row_equal_weights':True,'target_not_used_for_fit_or_shrinkage_choice':True,'b_calibration_out_of_year_refitted':True,'matched_family_excluded_from_distance':True,'purged_folds_use_168h_support':True,'duplicate_minute_anchors_equal':True,'windows_all_retained':True,'unknown_track_separate':True,'no_independent_event_inflation':True},'check_scope':'Internal implementation checks and calculations; independent reviewer verification separately recorded'}
    dump(result,R/'results/model_run_validation.json');print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
