# Q3 最终传播交接：七条映射运行与四个机械设计

本轮增量范围自 `0d5326d6e3428df4d714d8101c41c7c925eca0ef` 开始。fullmask 先单独保存为 `c6200b95db074775cc1cb24b163e3caef29f5cd2`；最终包再追加已执行 compact S_H／S_T_H 对接及综合清单。所有旧 core、exports、compact-v2、适用性、portable-manifest-v3 保留；新冻结 fullmask-v3 也不改写。最终 `results/final_propagation_v4/frozen_prior_files.json` 逐字节保护截至 c6200b 的 **740 个 Q3 round3 tracked 文件**，其中包含此前 651 个旧文件和 fullmask 的 89 个新增文件。

## 接口版本及实际复核

原 compact S／S_T 来自 `q4-r3-propagation-v2`（consumer SHA256 `9fec7f2083ab43f81b19da2c1cca3cef9b2ad0b5db36441495162412d1e8dda4`）；fullmask S60／ST120／ST60 来自 `q4-r3-propagation-v3`（consumer `8457a9db624c33c0d0988ad8f4d8c8513ff21ac858ccff830bae577f77f0b683`）。两者分别保留 compact release-v1 与 Q2 release-v2 全源面的物源假设。全源面实际体积、257／67 格支撑和旧 expected-reference 字段的区别见 `FULLMASK_V3_HANDOFF.md`。

最后两例来自 `q4-r3-compact-delta-v1`，consumer SHA256 **`044a9a08ce09e8b2b5470a6a4351942fb08054e52e9728e2bb4d51a2295841ac`**，producer 快照 **`28c67deb49d694e992c005365cf19c73d1db31a89126f64dbe8b6973adba61cb`**。48 个明确角色逐字节核验，14 条谱系接通。显式映射为 `q2r3_SH_v1 → q2r3_S_H_analytic_v1` 与 `q2r3_STH_v1 → q2r3_S_T_H_analytic_v1`，原/analytic 的 20 个物理参数、law、parameter version、机械几何和原 compact 父物源保持。按完整 linear base ID 区分同参数集的 thaw 兄弟条目，未按模型名称猜测匹配。

fullmask 对接 499 项检查、83 条输入／16 条输出索引通过；delta 对接 328 项检查、61 条输入／16 条输出索引通过。两者均另有独立审计，报告位于各自 `review/final_review.json`；技术通过不升级物理预测资格。使用实际已保存的 TIFF／NPZ 重算目标与足迹，没有重跑求解器、调整参数、增加实验或读取未批准的活动工作树。

## 七条条件运行如何解释

`results/final_propagation_v4/conditional_arrivals_49.csv` 仅按来源合并已冻结的 **14＋21＋14＝49** 条记录，保留原始全部列、空值、时间对象与评价状态；`mapped_runs_7.csv` 是逐运行摘要。

|机械设计|物源／网格|机械起始状态|paper junction 释放后保存帧首达区间（秒）|
|---|---|---|---|
|p0000-S|compact 60m|未跨阈，仅 if-released|保存输出未命中|
|p0000-S|fullmask 60m|未跨阈，仅 if-released|(161.1, 180.2]|
|p0036-S_T|compact 60m|解析全历史 7月8日15–16 UTC|(1360.5, 1380.1]|
|p0036-S_T|fullmask 120m|同一解析机械设计|(240.6, 260.1]|
|p0036-S_T|fullmask 60m|同一解析机械设计|(221.0, 240.7]|
|p0072-S_H|compact 60m|未跨阈，仅 if-released|(801.1, 820.6]|
|p0255-S_T_H|compact 60m|解析全历史 7月1日11–12 UTC；评价窗左删失|(1400.1, 1420.5]|

p0255 的新解析全历史插值为 **2026-07-01 11:01:09.649776747 UTC**，原模型全历史插值 11:19:16.802118373 只作原版本记录。原／解析的后续评价窗均为 `left_censored_already_unstable`，第一份评价样本已不稳不能成为评价窗内新启动。全历史跨阈区间、新点、旧点、评价分类及其来源分别落列，没有把窗口起点不稳硬接成新的启动或风险集观测。

p0072 原 compact 规定体积约 **5,100,006.8658m³**，p0255 约 **1,255,514.6298m³**；两者均零初速、岩冰体积分数组成、自由水为 0。H 机制不等于释放自由水相。实际 TIFF、case、密度、体积和 passive composition 已核，精确 compact 多边形／独立 mapping 表未交付，不能声称实测源界已认证。p0072 的 TIFF 有 40 个正支撑格，native t0 只有 39 个：一格深约 0.0000740281m、体积约 0.2665011m³，被三位小数输出舍入归零。该 I/O 差异单列，不写成支撑逐格完全一致；p0255 为 16／16 格。

delta 的 native 内部预算残差约 **+11.66547%／+12.40282%**，保存栅格表示另列。三个 fullmask 的较小预算残差也不自动成为守恒通过。七条运行的预测、区域准确度、质量守恒和 accepted-envelope 资格均为 false。

所有首达仍为 h≥0.1m、100m 代表点缓冲内格中心的保存输出阈值区间，不是精确结构相交或求解步时刻。未命中不说明连续时间安全。请求 1800 秒、请求期内最后保存帧及实际末帧分别保留。足迹使用原登记的 0.1／1／5m 阈值，距离取受影响格中心到实际正释放栅格单元足迹并集的欧氏距离；这不是精确实测多边形滑程或验证预警有效距离。原始图、数据及审图哈希各保留在对应包内，本次不新建额外图表路线。

## 统计与时间边界保持不变

7 次运行对应 **4 个机械设计**，不是 7 个独立事件，也不是 2048 参数设计的加权预测集合。49 条代表点记录也不能充当 49 个验证样本。五个 OSM 点始终对应三个候选实体。当地首次机械启动独立真值为 **0**，经验覆盖率为空，不能声称已验证 95% 覆盖率。

机械启动到整体释放滞后未知，未设为零；**绝对到达、合格时延、到达概率与统计权重全空**，accepted-envelope 为空。原始条件传播区间只作被指定释放假设下的诊断。Q4 没有 Q2 父 ID 的一般模型比较未被强制耦合，本包不依赖其后续计算。

## 可移植去重清单与集成

机器接口为 `exports/final_propagation_join_bundle_v4.json`。主输入／输出清单、740 文件旧字节记录及 `packet_validation.json` 位于 `results/final_propagation_v4/`。三包原始角色共 153 次注册、151 个唯一路径（DEM60 注册三次）；最终主清单还包括实际 adapter、独立审计及被冻结结果依赖，准确总数以 `unique_file_count` 为准。规范路径相同且 bytes／SHA 相同才合并，保留全部 roles、来源包／索引 SHA 与行号；相同内容但不同路径的快照与 cache 分别保留。

可执行路径只用仓库相对路径和三包精确批准的 **23 个 cache** 引用。历史 `source_path`、`upstream_path`、parser 位置和容器二进制路径不被递归提升为读取权限，也不为了清理这些历史字符串改原始快照。只读核验无需 producer 树位置或源 Git 对象：

```sh
track_b/.venv/bin/python track_b/research/q3/round3/scripts/final_propagation_v4.py --verify-only
```

该命令核验旧 fullmask 包、三包全部角色、delta 的实际执行及独立审计、49 条逐列投影、去重清单和冻结字节。旧封包均不重封；本地提交，不推送。最终科学采用仍由队员审视。
