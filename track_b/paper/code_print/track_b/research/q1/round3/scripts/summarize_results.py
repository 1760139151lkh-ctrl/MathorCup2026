#!/usr/bin/env python3
"""Produce scientific figures and written comparison from the computed route tables."""
import os
os.environ['MPLBACKEND']='Agg'
os.environ['MPLCONFIGDIR']='<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q1/plot_runtime_v1'
os.makedirs(os.environ['MPLCONFIGDIR'],exist_ok=True)
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
NAMES={'air_thermal':'Air thermal','air_moisture':'Air moisture','mean_wind':'Mean wind','air_pressure':'Air pressure','shortwave':'Shortwave','longwave':'Longwave','soil_thermal':'Soil thermal','soil_moisture':'Soil moisture','soil_heat_flux':'Soil heat flux','precipitation':'Precip label','turbulent_heat':'Turbulent heat','turbulent_mechanics':'Turbulent mechanics'}
MODELS=['A_marginal_ecdf','B_shrunk_conditional','C_other_family_analog'];TRACKS=['original_qc_view','unknown_qc_exploration']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
def csv(name):return pd.read_csv(R/'results'/name)
def save(fig,name):
 fig.savefig(R/'figures'/name,bbox_inches='tight');plt.close(fig)
def mdtable(df,cols):
 head='| '+' | '.join(cols)+' |\n| '+' | '.join('---' for _ in cols)+' |\n'
 def show(v):return '未知/不可估计' if pd.isna(v) else (f'{v:.3f}' if isinstance(v,(float,np.floating)) else str(v))
 return head+'\n'.join('| '+' | '.join(show(row[c]) for c in cols)+' |' for _,row in df.iterrows())+'\n'
def main():
 top=csv('top5_three_routes.csv');rec=csv('recommended_factors.csv');st=csv('ranking_stability.csv');sens=csv('sensitivity_metrics.csv');fold=csv('fold_metrics.csv');fa=csv('feature_anomalies.csv')
 context=json.loads((R/'results/model_context.json').read_text())
 context.update(input_version={'common_baseline_commit':context['common_baseline_commit'],'frozen_manifest_sha256':context['baseline_manifest_sha256'],'feature_bundle_version':'q1-r3-feature-v1','feature_bundle_sha256':'4e65566a1a473d7fdd16af10f209c2cb6841282b215e8c9d4981f748d6c1cc8e','advisor_q3_bundle_sha256':'04016b75b0af3be4439952705f39d83493317b2b3b594d9bed49448ea13a1ff3'},evidence_status='inference_and_candidate_from_local_numeric_facts; metadata_equivalence_unverified',variable_semantics={'contract_ref':'results/feature_contract.csv','quality_rule':'original paired QC0 remains strict in both tracks; unknown finite labels separate; 0.75 support primary with 0.50/0.90 sensitivity','units':'feature-specific contract; all scores/ranks dimensionless','integration_interval':None,'availability_status':'unknown'},model_id='multiple_models; see per-row model_id or model_ids list',space_object={'station_id':'Gyirong_regional_background','longitude':85.29,'latitude':28.86,'elevation_m':4140,'crs':None,'positional_uncertainty':None,'status':'metadata assertion; local equivalence and source-area representativeness unverified'})
 (R/'results/model_context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2)+'\n')
 # Per-feature actual support distinguishes five nominal years from observed years.
 meta=csv('sample_metadata.csv');contract=csv('feature_contract.csv')
 bank=pd.read_parquet(R/'results/features.parquet').set_index('sample_id')
 coverage=csv('feature_support.csv').pivot(index='sample_id',columns='driver_id',values='coverage')
 diag=json.loads((R/'results/covariance_diagnostics.json').read_text())
 effective=[];family_support=[]
 for track in TRACKS:
  for window in [24,72,168]:
   bm=meta[(meta.quality_track==track)&(meta.window_hours==window)&(meta.shift_hours==0)&(~meta.is_target.astype(bool))].reset_index(drop=True)
   tm=meta[(meta.quality_track==track)&(meta.window_hours==window)&(meta.shift_hours==0)&meta.is_target.astype(bool)&(meta.anchor_id=='problem_1030')].iloc[0]
   bd=next(d for d in diag if d['quality_track']==track and d['window_hours']==window and d['variant']=='primary' and d['shift_hours']==0)
   for _,ft in contract.iterrows():
    values=bank.loc[bm.sample_id,ft.feature_id].to_numpy(float);co=coverage.loc[bm.sample_id,ft.driver_id].to_numpy(float)
    ok=np.isfinite(values)&(co>=.75);years=sorted(bm.loc[ok,'year'].unique().tolist())
    effective.append({'quality_track':track,'window_hours':window,'feature_id':ft.feature_id,'driver_id':ft.driver_id,'family_id':ft.family_id,'nominal_background_years':5,'actual_numeric_supported_years':len(years),'years_json':json.dumps(years),'missing_years_json':json.dumps([y for y in range(2021,2026) if y not in years]),'n_supported_windows':int(ok.sum()),'n_nominal_windows':len(bm),'n_supported_process_proxies':int(bm.loc[ok,'process_id'].nunique()),'per_year_supported_window_counts':json.dumps({str(y):int(((bm.year==y)&ok).sum()) for y in range(2021,2026)}),'target_coverage':coverage.loc[tm.sample_id,ft.driver_id],'target_value_available':bool(np.isfinite(bank.loc[tm.sample_id,ft.feature_id]) and coverage.loc[tm.sample_id,ft.driver_id]>=.75),'B_active_feature':ft.feature_id in bd.get('active_features',[]),'context_ref':'results/model_context.json'})
   for f in contract.family_id.unique():
    ee=[d for d in effective if d['quality_track']==track and d['window_hours']==window and d['family_id']==f]
    es=[d['actual_numeric_supported_years'] for d in ee if d['target_value_available']]
    cal=bd.get('calibration_support',{}).get(f,{})
    family_support.append({'quality_track':track,'window_hours':window,'family_id':f,'nominal_background_years':5,'minimum_actual_feature_years':min(es) if es else 0,'maximum_actual_feature_years':max(es) if es else 0,'target_available_feature_count':sum(d['target_value_available'] for d in ee),'B_active_feature_count':sum(d['B_active_feature'] for d in ee),'B_observed_calibration_rows':cal.get('n_observed_rows',0),'B_observed_calibration_years':cal.get('n_observed_years',0),'B_observed_calibration_processes':cal.get('n_observed_processes',0),'context_ref':'results/model_context.json'})
 pd.DataFrame(effective).to_csv(R/'results/effective_feature_support.csv',index=False)
 pd.DataFrame(family_support).to_csv(R/'results/effective_family_support.csv',index=False)
 summary=[]
 for track in TRACKS:
  for model in MODELS:
   t=top[(top.quality_track==track)&(top.model_id==model)&top.top5.astype(bool)].sort_values('rank')
   sf=st[(st.quality_track==track)&(st.model_id==model)&(st.kind=='hierarchical_bootstrap')]
   fy=fold[(fold.quality_track==track)&(fold.model_id==model)&(fold.kind=='leave_year')]
   fp=fold[(fold.quality_track==track)&(fold.model_id==model)&(fold.kind=='leave_process')]
   ss=sens[(sens.quality_track==track)&(sens.model_id==model)]
   summary.append({'quality_track':track,'model_id':model,'three_window_top5':'、'.join(t.family_name),'leave_year_mean_jaccard':fy.top5_jaccard.mean(),'leave_process_mean_jaccard':fp.top5_jaccard.mean(),'leave_process_min_jaccard':fp.top5_jaccard.min(),'anchor_shift_min_jaccard':ss[(ss.variant=='primary')&(ss.shift_hours!=0)].top5_jaccard.min(),'predefined_sensitivity_min_jaccard':ss[ss.variant!='primary'].top5_jaccard.min(),'bootstrap_min_valid_draws':sf.n_valid.min(),'bootstrap_max_valid_draws':sf.n_valid.max(),'bootstrap_requested':100,'independent_accepted_events':0})
 comp=pd.DataFrame(summary);comp['context_ref']='results/model_context.json';comp.to_csv(R/'results/comparison_summary.csv',index=False)
 quality=[]
 for model in MODELS:
  a=top[(top.quality_track==TRACKS[0])&(top.model_id==model)].set_index('family_id');b=top[(top.quality_track==TRACKS[1])&(top.model_id==model)].set_index('family_id')
  for f in sorted(set(a.index)|set(b.index)):
   quality.append({'model_id':model,'family_id':f,'rank_original_qc':a.loc[f,'rank'] if f in a.index else None,'rank_unknown_included':b.loc[f,'rank'] if f in b.index else None,'rank_change':b.loc[f,'rank']-a.loc[f,'rank'] if f in a.index and f in b.index else None,'top5_credit_original_qc':a.loc[f,'top5_credit'] if f in a.index else None,'top5_credit_unknown_included':b.loc[f,'top5_credit'] if f in b.index else None,'context_ref':'results/model_context.json'})
 pd.DataFrame(quality).to_csv(R/'results/quality_sensitivity.csv',index=False)
 # Rank heatmaps include every family, missing remains visibly blank.
 fig,axes=plt.subplots(1,2,figsize=(12,6),constrained_layout=True)
 for ax,track,title in zip(axes,TRACKS,['Original QC0 view','QC0 + unknown exploration']):
  t=top[top.quality_track==track];families=[f for f in NAMES if f in set(t.family_id)]
  matrix=t.pivot(index='family_id',columns='model_id',values='rank').reindex(index=families,columns=MODELS)
  rr=rec[rec.quality_track==track].set_index('family_id');matrix['Consensus']=rr.recommended_rank.reindex(families)
  im=ax.imshow(matrix.to_numpy(),cmap='viridis_r',vmin=1,vmax=12,aspect='auto')
  ax.set_yticks(range(len(families)),[NAMES[f] for f in families]);ax.set_xticks(range(4),['A marginal','B conditional','C analog','Consensus'],rotation=20,ha='right');ax.set_title(title)
  for i in range(len(families)):
   for j in range(4):
    v=matrix.iloc[i,j];ax.text(j,i,'NA' if pd.isna(v) else f'{v:g}',ha='center',va='center',color='white' if pd.notna(v) and v>=7 else '#102030',fontsize=9)
 fig.suptitle('Physical-family ranks across the three fixed windows\nRegional station case anomalies; tied scores retain midranks; NA is not normal')
 fig.colorbar(im,ax=axes,label='Rank (lower = greater relative anomaly)',shrink=.75)
 save(fig,'route_rank_comparison.png')
 # Conditional bootstrap frequencies and denominator explicitly distinguished.
 fig,axes=plt.subplots(1,2,figsize=(13,6),constrained_layout=True)
 for ax,track,title in zip(axes,TRACKS,['Original QC0','QC0 + unknown']):
  t=st[(st.kind=='hierarchical_bootstrap')&(st.quality_track==track)]
  families=[f for f in NAMES if f in t.family_id.unique()]
  data=t.groupby(['family_id','model_id']).top5_frequency.mean().unstack().reindex(index=families,columns=MODELS+['consensus'])
  im=ax.imshow(data.to_numpy(),vmin=0,vmax=1,cmap='Blues',aspect='auto')
  ax.set_yticks(range(len(families)),[NAMES[f] for f in families]);ax.set_xticks(range(4),['A','B','C','Consensus']);ax.set_title(title)
  for i in range(len(families)):
   for j,m in enumerate(data.columns):
    v=data.iloc[i,j];rows=t[(t.family_id==families[i])&(t.model_id==m)];n=int(rows.n_valid.min()) if len(rows) else 0
    ax.text(j,i,'NA' if pd.isna(v) else f'{v:.2f}\nn≥{n}',ha='center',va='center',fontsize=7,color='white' if pd.notna(v) and v>.65 else '#17324a')
 fig.suptitle('Top-five fractional inclusion, averaged over 24 / 72 / 168h\nConditional on estimable draws out of 100; these are stability frequencies, not event probabilities')
 fig.colorbar(im,ax=axes,label='Mean valid-draw top-five credit',shrink=.75);save(fig,'bootstrap_stability.png')
 # Actual feature directions: same fixed representative median features.
 fixed=['air_temperature_2m','relative_humidity_2m','wind_speed_10m','air_pressure','shortwave_down','longwave_down','soil_temperature_0p1m','soil_vwc_0p1m','soil_heat_flux_0p1m','precipitation_label','latent_heat_flux','friction_velocity']
 t=fa[(fa.variant=='primary')&(fa.shift_hours==0)&(fa.statistic=='median')]
 directions=t[t.driver_id.isin(fixed)].copy();directions.to_csv(R/'results/factor_directions.csv',index=False)
 fig,axes=plt.subplots(1,2,figsize=(12,6),constrained_layout=True)
 for ax,track,title in zip(axes,TRACKS,['Original QC0','QC0 + unknown']):
  data=directions[directions.quality_track==track].pivot(index='driver_id',columns='window_hours',values='background_percentile')
  order=[d for d in fixed if d in data.index];data=data.reindex(order)
  im=ax.imshow(data.to_numpy(),vmin=0,vmax=1,cmap='coolwarm',aspect='auto')
  ax.set_yticks(range(len(data)),[d.replace('_',' ') for d in data.index]);ax.set_xticks(range(len(data.columns)),[f'{w}h' for w in data.columns]);ax.set_title(title)
  for i in range(len(data)):
   for j in range(len(data.columns)):
    v=data.iloc[i,j];ax.text(j,i,'NA' if pd.isna(v) else f'{v:.2f}',ha='center',va='center',fontsize=9)
 fig.suptitle('Direction of fixed representative window medians\nYear / process weighted seasonal background ECDF; percentiles are descriptive, not p-values')
 fig.colorbar(im,ax=axes,label='Background percentile',shrink=.75);save(fig,'feature_direction_percentiles.png')
 # All predefined sensitivities, not a selected favourable subset.
 fig,axes=plt.subplots(1,2,figsize=(12,6),constrained_layout=True)
 for ax,track,title in zip(axes,TRACKS,['Original QC0','QC0 + unknown']):
  t=sens[sens.quality_track==track].copy();t['comparison']=np.where(t.variant=='primary','anchor '+t.shift_hours.astype(str)+'h',t.variant)
  data=t.groupby(['comparison','model_id']).top5_jaccard.mean().unstack().reindex(columns=MODELS)
  im=ax.imshow(data.to_numpy(),vmin=0,vmax=1,cmap='YlGnBu',aspect='auto');ax.set_yticks(range(len(data)),data.index);ax.set_xticks(range(3),['A','B','C']);ax.set_title(title)
  for i in range(len(data)):
   for j in range(3):ax.text(j,i,f'{data.iloc[i,j]:.2f}',ha='center',va='center',color='white' if data.iloc[i,j]>.65 else '#102030')
 fig.suptitle('Top-five set overlap with the preregistered primary setting\nJaccard averaged over fixed windows; boundary ties retained')
 fig.colorbar(im,ax=axes,label='Jaccard overlap',shrink=.75);save(fig,'sensitivity_comparison.png')
 # Source-label time series: four data classes, last 168h before the fixed primary reference.
 hourly=pd.read_parquet(R/'exports/hourly_drivers.parquet')
 hourly['time_utc']=pd.to_datetime(hourly.time_utc,utc=True)
 reference=pd.Timestamp('2026-08-26T02:30:00Z')
 panels=[('air_temperature_2m','Air temperature 2m / degC',TRACKS[0]),('relative_humidity_2m','Relative humidity 2m / %',TRACKS[0]),('wind_speed_10m','Wind speed 10m / m s-1',TRACKS[0]),('shortwave_down','Downward shortwave / W m-2',TRACKS[0]),('soil_temperature_0p1m','Soil temperature 0.1m / degC',TRACKS[0]),('soil_vwc_0p1m','Soil water 0.1m / m3 m-3',TRACKS[0]),('precipitation_label','Precip labels / mm, interval unknown',TRACKS[1]),('latent_heat_flux','Latent heat / W m-2, QC unknown',TRACKS[1])]
 fig,axes=plt.subplots(4,2,figsize=(13,9),sharex=True,constrained_layout=True)
 import matplotlib.dates as mdates
 for ax,(driver,label,track) in zip(axes.flat,panels):
  hh=hourly[(hourly.quality_track==track)&(hourly.time_utc>=reference-pd.Timedelta(hours=168))&(hourly.time_utc<reference)]
  ax.plot(hh.time_utc,hh[driver],lw=1,color='#235d79' if track==TRACKS[0] else '#a65c28')
  ax.set_title(label,fontsize=9,loc='left');ax.grid(alpha=.16);ax.set_xlim(reference-pd.Timedelta(hours=168),reference);ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
 for ax in axes[-1]:ax.set_xlabel('UTC hour labels; 2026')
 fig.suptitle('Observed regional station context, fixed 168h before the 02:30 UTC reference\nOriginal QC0 in blue; unknown QC in brown; gaps retained; hourly integration boundaries unverified')
 save(fig,'event_hourly_context.png')
 # Written model comparison with actual computed tables.
 text='''# Q1 第三轮模型竞争与推荐

已实际完成三路线及全部预登记敏感性、留年/过程删除、100次年→过程重采样。结果层级为区域站本次参考时刻前的异常候选；不是灾害因果、风险概率或已验证触发TOP5。精确启动真值与独立灾害训练/验证事件均未新增。

## 三套候选TOP5（跨24/72/168h等权名次）

'''
 for track,label in zip(TRACKS,['原QC0主轨','QC0 + unknown探索轨']):
  text+='### '+label+'\n\n'
  for model in MODELS:
   d=top[(top.quality_track==track)&(top.model_id==model)&top.top5.astype(bool)].sort_values('rank')
   text+='**'+model+'**\n\n'+mdtable(d,['family_name','rank','score','top5_credit'])+'\n'
 text+='''## 预登记共识推荐

主报告保留三路线共识；A提供可解释的边际异常底座，B为共线条件异常挑战路线，C为天气过程对照选择挑战路线。没有独立灾害真值，不能以本次目标的异常大小宣称某路线预测获胜。B对组数/缺测和收缩假设敏感，C的对照是匹配代理过程，均保留作挑战证据。

'''
 for track,label in zip(TRACKS,['原QC0主轨','unknown纳入影响']):
  d=rec[(rec.quality_track==track)&rec.recommended_top5.astype(bool)].sort_values('recommended_rank')
  text+='**'+label+'**\n\n'+mdtable(d,['family_name','recommended_rank','consensus_score','mean_window_bootstrap_top5_frequency','min_window_bootstrap_valid_draws','stability_label'])+'\n'
 q=rec[rec.quality_track==TRACKS[0]].set_index('family_id')
 text+=f"第五席需要保留争议：主点估计的平均风场跨窗平均入选频率为{q.loc['mean_wind','mean_window_bootstrap_top5_frequency']:.3f}，候补土壤热通量为{q.loc['soil_heat_flux','mean_window_bootstrap_top5_frequency']:.3f}；两者以每窗44个有效共识draw为条件。按预登记共识仍保留平均风场为第5，但不应将其写成稳定唯一第五致灾因素。\n\n"
 text+='''TOP5边界若并列，候选表保留所有有第五席fractional credit的族，不用字母序制造胜负。主推荐仅为9个已有QC族中的相对异常，unknown轨的新增族不自动得到质量认证；某族在B中因零尺度/不足支持不可估计时，三路共识保持null。

## 实际稳定性与比较分母

'''+mdtable(comp,['quality_track','model_id','leave_year_mean_jaccard','leave_process_mean_jaccard','anchor_shift_min_jaccard','predefined_sensitivity_min_jaccard','bootstrap_min_valid_draws','bootstrap_max_valid_draws'])+'''
`rankings.n_background_years=5`是名义抽取池；每特征实际有效年/过程、缺年与逐年窗口数见effective_feature_support，家族及B校准分母见effective_family_support，尤其unknown通量不能读成全部5年。所有Jaccard是目标排名对训练背景变动的敏感性，非灾害分类准确率。5个背景年与45个7日块代理不等于45个独立灾害。重采样中不足4个唯一年份会使B的留年校准不可估计；其频率仅以有效draw为分母，完整n_requested/n_valid在ranking_stability.csv。推荐表有效draw不足70/100不标稳定。原始100次抽样全部保存，不重抽凑数。

## 方法分歧与限制

A对常值和偏态稳健，但边际差异不排除共线；B可减弱线性共享变化，但收缩、维数、填补和高斯二次距离不是已证实物理过程；C在待评族之外匹配且每年选不同代理过程，仍可能遗漏真实气象背景。比较基于相同因素族、质量轨和窗口，路线间的原始分数不可直接当同一种概率。

方向需逐描述量读取factor_directions和feature_anomalies，不可把整族非负异常分改写成单一升温/增湿方向。名义垂直/土层梯度仅属区域站；降水标签分布不是累计雨量；辐射差值未经本地仪器符号认证；FLUX质量/处理/小时区间unknown；VPD是否依赖已知常值amb_e_sat的上游处理也未证实，不能把它看作独立湿度证据。未取得独立源区配对与位置基准，站点异常不能直接作为源区物理输入。

## 题面要求对照与后续使用

四类气象资料均有变量映射、特征、覆盖和异常；三套TOP5、主推荐、方向、留年/过程/窗口/锚点/质量敏感性均有真实计算。统计关联支线未启动：Q3审核包仍有0个接受的独立启动/暴露单位，不能把区域背景年当无灾标签。Q2/Q3先接收冻结feature_bundle及限制，正式物理输入和历史业务可用性另由主参谋审查。
'''
 (R/'MODEL_COMPARISON.md').write_text(text)
 paper='''# Q1 论文方法、结果与讨论提纲

## 研究问题与可写主张

研究本次参考时段前，吉隆区域站气象—土壤—通量变量相对近年同季节背景的异常候选因素。明确题面启动对象与参考时间差别，排名为个案关联线索，后续Q2机制验证与Q3外部事件验证各自保留。

## 方法材料

1. 数据：四类原附件/规范化输入、37个原QC变量与26个unknown变量的逐列映射；24个驱动、112个描述量，给出名义层间梯度、趋势与持续链定义，缺口不插值。
2. 背景：2021—2025季节±30日、每天固定时刻、24/72/168h；年→7日过程代理→锚点等权。报告实际305窗/窗口、5年、45代理过程，不能当独立灾害数；±15日与3/14日块对照。
3. A加权ECDF双侧异常；B稳健缩放、Σ=(1−λ)C+λI及Schur条件距离/自由度、留年观测校准；C剔除待评族的等族匹配、每年k个不同过程。写出所有超参数先于计算登记，原始分数不作p值。
4. 因素族层级聚合与跨路线/窗口名次共识，保留边界并列credit；五年留出、真实168h支持清除重叠、100个层级draw、有效分母与两锚点±1h小时集合。

## 结果呈现

'''
 d=rec[(rec.quality_track==TRACKS[0])&rec.recommended_top5.astype(bool)].sort_values('recommended_rank')
 paper+=mdtable(d,['family_name','recommended_rank','consensus_score','mean_window_bootstrap_top5_frequency','min_window_bootstrap_valid_draws'])
 paper+='''
结果图1：三路线/质量轨全因素族名次。图2：有效draw条件下的TOP5频率与分母。图3：预先固定代表变量的方向/背景百分位。图4：全部预定敏感性Jaccard。图5：原参考前168h四类资料实际逐小时标签时序，缺口保留。表格同时呈现三套TOP5、unknown新增因素和B不可估计族，不只报告一致结果。

## 讨论与跨问衔接

解释共识与分歧对应何种统计问题，不用异常度证明机制。区域站坐标/高度为元数据声明，站源转移未校验；约65km指站至口岸，不是站至失稳源区。FLUX处理/QC、小时时段和真实available_time未闭环，unknown结果降低解释层级。相邻小时和同链目录不充独立事件；源区首次启动、传播和到达时间分别引用Q3/Q4。五年背景限制外推与bootstrap可估计性，零尺度不是零风险。

## 可复现与披露

引用EXPERIMENT_PROTOCOL、PROTOCOL_DEVIATIONS、REPRODUCE和来源/输入/产物清单，正文写明AI辅助实现/资料整理、独立AI技术复核范围及队员最终科学采用。当前未建立外部灾害关联/预测效能验证，最终论文须保留此范围或在取得真实独立证据后增加单独研究支线。
'''
 (R/'PAPER_OUTLINE.md').write_text(paper)
 print(json.dumps({'figures_created':5,'comparison_rows':len(comp),'quality_comparison_rows':len(quality),'recommendation_rows':len(rec)}))
if __name__=='__main__':main()
