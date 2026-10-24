# Q1 第三轮早交：区域站特征 v1

本接口已实际提取并通过检查；尚未进行因素排序。只交主参谋核验后分发。

- bundle：`exports/feature_bundle.json`，SHA-256 `4e65566a1a473d7fdd16af10f209c2cb6841282b215e8c9d4981f748d6c1cc8e`。
- 共同基线：`904d7257b899b9f71d1ac9e0eab7479e459eab52`；冻结清单 SHA-256 `fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`。
- 5526个样本（背景5490、目标36），24驱动、112排名描述量，完整63原变量选择／排除表。
- `results/features.parquet`为`sample_id`加浮点feature_id列；元数据、覆盖支持另表，以sample_id连接。feature_id=`driver_id__statistic`，模型须先按每驱动coverage筛选。
- 每个quality_track有2021—2025×61日×3锚点小时偏移×3窗口背景，以及2026两参考×3偏移×3窗口目标。背景去重为problem_1030；分钟参考相同样本不得多投票。
- 24/72/168h的support_start/end为左闭右开请求区间，实际标签由first/last_hour_index精确确定。process_id是季节首日开始7日历日块代理，不是真实天气事件。
- 原QC轨仅37个原QC0变量；扩展轨只添加原本无QC变量，37列仍QC0。派生量逐小时取原量有效交集，不填补。unknown不升级质量。
- 构建器只要求分布／持续性>=2有效标签、趋势>=6；不套75%阈值。增长持续按正相邻小时增量数/名义窗标签数；缺口打断。降水仅标签统计，未做累计。
- `exports/hourly_drivers.parquet`按quality_track长表，UTC时间与24个驱动，2026-07-01 00:00至2026-08-26 11:30（UTC+8）内实际整点标签，共2712行。时效未知，不代表历史实时可获得。
- 离线命令：`track_b/.venv/bin/python track_b/research/q1/round3/scripts/build_features.py`。再次运行必须产生逐字节相同产物；v1有变化即拒写，须新版本。
- 实际检查：5526唯一样本、24/72/168标签数、±1h支持集合、37QC列跨轨相同、unknown主轨全空、63变量映射、R1固定median对照、缺口持续和趋势机械用例、公共输入哈希不变。详见`results/feature_build_validation.json`。

空间、时区等价、小时起止／中心、FLUX处理及真实业务时效仍未核实。因素族只是区域观测候选，不是源区触发证明；论文最终科学采用待队员审视。v1清单不包含自身，所有文件按真实bytes/SHA-256列出。

## 已接收主参谋分发与请求

已核验Q3 `inputs/q3/event_bundle_q3-r3-event-v1-local/bundle.json`（SHA256 04016b75b0af3be4439952705f39d83493317b2b3b594d9bed49448ea13a1ff3）和3个绑定文件；使用见results/interface_usage.json。它不增加接受的源区启动真值、独立训练/验证事件或历史可用证据，本问仍不拟合监督灾害关联支线。

需要的后续接口：审核通过的源区几何/坐标基准及地形高程以便站源距离/高差审查；合法可读的目标FLUX处理/QC/小时支持文档；有事件/暴露独立单位的真实标签。缺项只限制对应局地或统计关联用途，不阻断本轮区域因素竞争。

时序使用提醒：主参考原窗最后标签为2026-08-26 10:00（UTC+8）；+1h敏感性和小时export延伸到11:00，晚于原10:30与10:52:10参考。它们属于参考时间扰动/事后研究，不能直接充当较早发布时刻的可用输入。所有available_time仍未知；小时平均实际支撑也未认证。
