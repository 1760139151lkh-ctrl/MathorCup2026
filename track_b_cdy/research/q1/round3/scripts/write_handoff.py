#!/usr/bin/env python3
"""Write the completed handoff from executed model/check tables, before final manifest."""
from pathlib import Path
import json
import pandas as pd
R=Path(__file__).resolve().parents[1]
def main():
 run=json.loads((R/'results/model_run_validation.json').read_text());assert run['passed']
 hourly=pd.read_parquet(R/'exports/hourly_drivers.parquet');hourly['time_utc']=pd.to_datetime(hourly.time_utc,utc=True)
 fa=pd.read_csv(R/'results/feature_anomalies.csv')
 selected=[('air_temperature_2m','degC','original_qc_view'),('relative_humidity_2m','%','original_qc_view'),('wind_speed_10m','m s-1','original_qc_view'),('shortwave_down','W m-2','original_qc_view'),('soil_temperature_0p1m','degC','original_qc_view'),('soil_vwc_0p1m','m3 m-3','original_qc_view'),('precipitation_label','mm per unverified label interval','unknown_qc_exploration'),('latent_heat_flux','W m-2','unknown_qc_exploration')]
 reference=pd.Timestamp('2026-08-26T02:30:00Z');state=[]
 for driver,unit,track in selected:
  for window in [24,72,168]:
   hh=hourly[(hourly.quality_track==track)&(hourly.time_utc>=reference-pd.Timedelta(hours=window))&(hourly.time_utc<reference)]
   valid=hh[hh[driver].notna()];d=fa[(fa.quality_track==track)&(fa.driver_id==driver)&(fa.window_hours==window)&(fa.variant=='primary')&(fa.shift_hours==0)]
   median=d[d.statistic=='median'].iloc[0];trend=d[d.statistic=='trend_per24h']
   state.append({'driver_id':driver,'unit':unit,'quality_track':track,'window_hours':window,'n_valid':len(valid),'n_labels':len(hh),'first_valid_time_utc':valid.time_utc.iloc[0].isoformat(),'last_valid_time_utc':valid.time_utc.iloc[-1].isoformat(),'first_valid_value':float(valid[driver].iloc[0]),'last_valid_value':float(valid[driver].iloc[-1]),'endpoint_change':float(valid[driver].iloc[-1]-valid[driver].iloc[0]),'target_median':median.target_value,'background_median_percentile':median.background_percentile,'target_trend_per24h':float(trend.iloc[0].target_value) if len(trend) else None,'context_ref':'results/model_context.json'})
 pd.DataFrame(state).to_csv(R/'results/case_state_evidence.csv',index=False)
 soil=next(a for a in state if a['driver_id']=='soil_vwc_0p1m' and a['window_hours']==168)
 rec=pd.read_csv(R/'results/recommended_factors.csv')
 sel=rec[(rec.quality_track=='original_qc_view')&rec.recommended_top5.astype(bool)].sort_values('recommended_rank')
 names='、'.join(sel.family_name)
 txt=f'''# Q1 第三轮交接：三路线竞争与候选因素

**状态：完整研究计算已完成，提交主参谋联合审查；队员最终科学采用待定。** 本地提交号由最终回复和Git记录提供；不把包含本文件的提交号写入自身。未push。

## 身份与共同输入

唯一执行根 `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1`，分支 `codex/track-b-q1-r3`。共同基线 `904d7257b899b9f71d1ac9e0eab7479e459eab52`；准备提交 `de790034cf302de58e69329dbe288aad269269a359c` 以workspace_binding的完整值为准。冻结输入725项，manifest SHA-256 `fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`。所有新成果限本问round3，公共原值、前两轮包及原44包环境未修改，没有远程计算或新依赖。

原venv实际Python/包版本见config/runtime_environment.json；本轮启动五组检查副本为results/startup_workspace_verification.json，收尾五组检查在workspace_verification.json。历史工具升级按第三轮基线验，不重跑旧轮生成管线。

## 核心研究结果

固定主轨跨三路线、三窗口的预登记共识候选为：**{names}**。这是吉隆区域站本次参考标签窗的异常候选，不是源区因果或通用灾害预测TOP5。三套路线名单与全部分歧见MODEL_COMPARISON和results/top5_three_routes.csv；不以本次异常分数决定哪个模型预测获胜。

- A为边际加权ECDF；B为固定收缩协方差条件距离挑战；C为排除待评因素族后的相似天气过程对照挑战。每族/驱动层级聚合，跨窗等权，无多高度重复占席。
- 特征银行5526样本（5490历史、36目标）、24驱动、112特征；132624条驱动支持记录。37个原QC变量仍只接受原QC0，26个unknown变量不升级质量；实际选用驱动和所有63变量排除/合并原因有表。
- 实际输出{run['ranking_rows']}行排名、{run['fold_membership_rows']}行折成员、{run['stability_rows']}行稳定性明细。两质量轨×三窗口，各5个留年+45个过程代理留出，共300个折配置；按真实168h标签支持剔除重叠。天气过程为7日历日依赖代理，3/14日块与季节±15日另作敏感性。
- 主参考及目录参考各−1/0/+1h确实更换小时集合；同偏移的两个分钟锚点仍重复，不增加独立证据。24/72/168h全部保留，没有挑最显著窗。
- 完全并列使用midrank，TOP5边界保留fractional credit，故共享第五席时可显示多于5行，不按字母任意截断。
- 100次层级draw全部保存；其中{run['bootstrap_draws_with_fewer_than_three_unique_years']}次少于3个唯一背景年，{run['bootstrap_draws_with_fewer_than_four_unique_years_B_crossfit_insufficient']}次少于4年，B留年校准在相应draw可能不可估计。n_requested与n_valid、条件入选频率同时报告；不重抽凑数，频率不是事件概率。

主推荐的频率与实际有效次数（各窗有效draw条件下，再取三窗均值）：

| 因素族 | 共识分数 | 跨窗平均TOP5频率（有效draw条件下） | 每窗最少有效draw /100 | 采用层级 |
| --- | --- | --- | --- | --- |
'''
 for _,row in sel.iterrows():
  txt+=f"| {row.family_name} | {row.consensus_score:.4f} | {row.mean_window_bootstrap_top5_frequency:.3f} | {int(row.min_window_bootstrap_valid_draws)} | {row.stability_label} |\n"
 txt+=f"\n图像和实际数值显示：0.1m土壤含水量在168h标签窗从{soil['first_valid_value']:.4f}降至{soil['last_valid_value']:.4f} m³/m³，OLS趋势为{soil['target_trend_per24h']:.4f} m³/m³/24h；其窗口median的季节背景百分位仍为{soil['background_median_percentile']:.3f}。因此土水候选不能写成近期持续增湿；状态水平与变化方向须分开。全部图示驱动的首末值、趋势和背景位置见case_state_evidence.csv，区域站变化也不直接证明源区水压。\n"
 txt+='''
第5项平均风场的跨窗入选频率约0.527，候补土壤热通量约0.559（均每窗44个有效共识draw）；按预登记规则仍交付平均风场，但第五席并不稳固，论文和跨问采用须保留这一竞争。

## 质量、有效年数与不可估计结果

rankings中的n_background_years=5只表示名义选择池。实际逐特征有效年、缺年、每年窗数/过程数见results/effective_feature_support.csv；家族与B留年观测校准分母见effective_family_support.csv。unknown通量不能称完整五年，amb_e_sat已知常值也不能升级为质量合格；该量仅诊断，不进本轮候选评分。

QC主轨九族B可评分。扩展轨B的湍流热交换/湍流机械交换缺少合格留年校准；168h机械量虽可有raw条件贡献，校准为0仍给null，三路线共识也保留null，不当作低风险/末名。扩展轨空气湿状态加入VPD后实际校准为4年；VPD与amb_e_sat的处理依赖未闭环，名次变化不是新增独立湿度证据。A/C中降水或FLUX的异常只作unknown探索，不因三条路线运行成功就接受源区机制。

固定代表变量方向和数值在results/factor_directions.csv与feature_anomalies.csv；不能把整族非负异常分写成单一升温/增湿。降水标签median为0不表示无雨，max/持续统计也不是累计雨量；辐射差值不是已认证能量收支；名义梯度不是源区冰岩温度。

## 证据与跨问交接

早交稳定接口exports/feature_bundle.json，SHA-256 `4e65566a1a473d7fdd16af10f209c2cb6841282b215e8c9d4981f748d6c1cc8e`，10个绑定文件均有path/bytes/sha256/role且不含自身，主参谋已核验分发Q2/Q3。v1保持原字节，不在本轮后半段覆盖。

Q3本地约束包在inputs/q3/event_bundle_q3-r3-event-v1-local/bundle.json，SHA-256 `04016b75b0af3be4439952705f39d83493317b2b3b594d9bed49448ea13a1ff3`，3文件已核验；实际使用和主参谋采纳范围见results/interface_usage.json。接受的独立灾害训练/验证仍各0；没有把代理时刻、后续事件、重复小时或背景年变成监督标签。没有读取他问活动产物。

本轮实际取得并保存4个公开原响应；源URL/版本/获取UTC/阅读范围/字节/hash见source_register与EVIDENCE_REVIEW。目标TPDC仍为前端壳，FLUX QC1—9、处理版本、小时积分边界和实际available_time仍未闭环。站点坐标28.86N/85.29E、4140m仅元数据声明，坐标/高程基准与误差未知；约65km是至口岸，非至源区。源区几何/站源转移仍需经主参谋核验后接入。

主参考最后标签为源钟8月26日10:00；+1h与小时export含11:00，晚于原参考。它们是时刻扰动/事后材料，不可直接作较早发布的可得输入。所有结果规范字段通过results/model_context.json关联，physical_phase保留参考前区域对照，available_time等未知为null。

## 实际复跑、审查与文件入口

完整离线命令、原44包精确锁、来源获取方法见REPRODUCE。实际完整模型命令：

```sh
track_b/.venv/bin/python -X faulthandler -u track_b/research/q1/round3/scripts/run_models.py > track_b/research/q1/round3/model_run.log 2>&1
track_b/.venv/bin/python track_b/research/q1/round3/scripts/summarize_results.py
track_b/.venv/bin/python track_b/research/q1/round3/scripts/validate_results.py
```

成功运行版本、起止UTC、耗时、源码/config哈希在model_run_validation。早期一次本地进程exit139无Python栈，精确原因未定位；单独真实依赖导入成功，原环境未改，最终完整运行成功证据单列。主动终止的性能修订与支持守卫过程见PROTOCOL_DEVIATIONS、execution_history与保留日志。最终版本的NumPy timedelta弃用提示为非致命警告；数值审查已对真实标签交集核对purge，未把警告当未来依赖兼容证明。

独立最终结果复核另有2743项检查通过，80个严格数值对比最大误差1.11e−16，15份文件快照与最终表一致，见results/independent_result_review.json。

独立特征复算覆盖36目标、4032特征值/864支持、全部5526时间窗和65088小时驱动单元，0实质错误；最大浮点差6.82e−13。独立数值基准12组通过，含480组权重对旧循环最大差5.55e−17、条件贡献恒等式最大差5.55e−16、SPD/训练折隔离/缺测/并列/C自族排除。它们是AI辅助技术检查，不是队员科学采用或灾害预测验证。

五张研究图由真实表/逐小时资料生成并实际打开，检查范围及图哈希见figures/visual_review.json。MODEL_COMPARISON给主共识/解释底座与两挑战路线、支持/反对证据；PAPER_OUTLINE给方法/结果/讨论材料；results/question_requirement_map.csv逐项对照题意。最终独立算术/清单/重叠检查见results/validation.json。

直接输入清单results/input_manifest.json和稳定输出清单output_manifest.json均不自包含；输出清单含输入清单、稳定文档/代码/结果/图/来源及分发输入，排除自身、可变workspace_binding/workspace_verification、*.log与pycache，排除理由明确，日志仍由Git保留。最终manifest哈希在最终交接消息提供，避免写回产生循环。

本轮计算和完整研究包到此交回主参谋；源区物理采用、正式因果/泛化解释和最终论文贡献由队员联合决定。
'''
 # Full preparation hash is copied from the authoritative binding, avoiding manual transcription.
 binding=json.loads((R/'workspace_binding.json').read_text())
 txt=txt.replace('de790034cf302de58e69329dbe288aad269269a359c',binding['preparation_commit'])
 (R/'HANDOFF.md').write_text(txt)
 print(json.dumps({'written':'HANDOFF.md','recommended_main_families':names,'model_run_duration_seconds':run['duration_seconds']},ensure_ascii=False))
if __name__=='__main__':main()
