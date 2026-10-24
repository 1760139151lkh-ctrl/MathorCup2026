# Q1 气象关联：首轮任务书

状态：**任务已定义，研究与小实验待执行。** 此文件不是 TOP5 或模型结果。调度、共同基线与联合审查按 `track_b/docs/14_stage4_workflow.md`；基线绑定以主参谋发布的 `track_b/audit/stage4/baseline_manifest.json` 为准。

## 1. 目的与本轮终点

围绕 MET、RADM、SOIL、FLUX 四类资料，确认哪些观测能够进入区域天气背景、边界层及极端过程诊断，比较候选关联研究设计，为队员独立确定特征、目标与 TOP5 排序协议准备证据。

首轮终点为“有依据的数据适用范围＋可复查描述图＋数据诊断小实验＋候选排序及稳定性评价方案”。不在本轮选出最终 TOP5、训练灾害预测模型或声称因果机制成立。

## 2. 已知输入（均为仓库根相对路径，只读）

| 输入 | 精确路径与用途 |
|---|---|
| 四问题意与口径 | `track_b/docs/01_task_matrix.md`、`track_b/docs/02_definitions_validation.md` |
| 阶段 3 交接与时序语义 | `track_b/docs/13_stage3_handoff.md`、`track_b/docs/09_temporal_pipeline.md` |
| 变量字典 | `track_b/data/processed/temporal/data_dictionary.json` |
| 时间与血缘 | `track_b/data/processed/temporal/hourly_time_axis.parquet`、`track_b/data/processed/temporal/hourly_provenance.parquet` |
| 原值与严格视图 | `track_b/data/processed/temporal/hourly_raw_numeric.parquet`、`track_b/data/processed/temporal/hourly_strict_qc0.parquet` |
| 原始 QC 与未知标记 | `track_b/data/processed/temporal/hourly_raw_qc.parquet`、`track_b/data/processed/temporal/hourly_mask_qc_unknown.parquet` |
| 数值与接受掩膜 | `track_b/data/processed/temporal/hourly_mask_is_numeric_present.parquet`、`track_b/data/processed/temporal/hourly_mask_strict_qc0_accepted.parquet` |
| 质量／验证与哈希 | `track_b/data/processed/temporal/hourly_quality_summary.csv`、`track_b/data/processed/temporal/verification.json`、`track_b/data/processed/temporal/input_manifest.json`、`track_b/data/processed/temporal/output_manifest.json` |
| 原审计线索 | `track_b/audit/temporal/hourly_variables.csv`、`track_b/audit/temporal/hourly_event_windows.csv`、`track_b/audit/temporal/hourly_qc_value_crosstab.csv` |
| 事件证据 | `track_b/data/external/event_remote/event_evidence_ledger.json`、`track_b/docs/11_event_remote_evidence.md` |
| 来源清单 | `track_b/docs/05_research_sources.md`、`track_b/audit/research_sources.json` |
| 县日补充资料（有条件使用） | `track_b/data/processed/temporal/daily_county_raw.parquet`；单位、日界和县域聚合未核实，不能直接拼接塔站 |

所有小时宽表按 `hour_index` 对应相同行序；若筛选或排序，必须用同一索引同时处理时钟、数值与掩膜。不要独立排序其中一张表后按行拼接。

## 3. 已知边界

- 52,584 小时、63 测量变量；37 个字段附 QC。降水与 25 个 FLUX 字段为 unknown QC，严格 QC0 视图中为空；这不表示它们全部无研究价值，也不允许自动视为合格。
- 9999.9 与 NaN/NAN 缺测必须按已有掩膜识别。有限数值不等于质量合格；原有 QC0 也不代替物理诊断。
- 小时标签起止／中心、FLUX 正负方向与部分单位尚未核实。UTC+8 是已记录的解释假设，不能用电脑时区代替。未核实前不宣称已得到明确积分边界的累计雨量。
- 塔站距口岸约 65 km，属于区域背景；不能直接解释为真实源区天气。边界层梯度与湍流参数还需仪器高度、参考面和处理方式的证据。
- 当前仅一条重点灾害链，独立训练标签未审核通过。禁止把任意其他小时标为“确认无灾害”，或把同事件多个窗口作为独立灾害样本。
- 题面时刻、目录代理时刻和论文阶段重建分别保留；窗口选择不能靠事后最显著结果决定。季节性、自相关、共线与风向环变量必须纳入候选设计。

## 4. 本轮步骤与许可小实验

1. **恢复与核验。** 核对基线、输入哈希和本窗环境；建立 `results/input_check.json`，登记每项输入技术可用／语义已核实／足以支持何种结论三个状态。
2. **四类变量语义清点。** 逐字段整理单位、高度／深度、QC、正方向、时段语义及来源。对 unresolved 项只提出可查证的问题，不通过经验常识补成测量定义。
3. **补充 FLUX／降水质量诊断。** 在本问输出侧分别统计哨兵、缺测、非有限、长连续常值／突跳、分布和与相关变量的一致性。检测阈值须写为候选诊断规则并标来源／假设；不覆盖原值，不把被标记数据永久删除。输出每步纳入数和排除原因。
4. **描述性最小实验。** 在预先写明的同季节背景与候选事前窗口内，制作原观测／QC／覆盖图和分布对照；同时保留题面与目录候选时刻的时间对象差异。窗口先写入本问配置再运行；不能依据显著性反选窗口。
5. **候选特征登记。** 按物理含义列温湿风梯度、辐射、土壤水热、湍流及降水等候选族，记录公式、单位、窗口、滞后、缺测门槛、共线组与可用时间未知项。这里只做可计算性和覆盖诊断，不执行最终特征筛选。
6. **提出比较与交接。** 基于数据条件说明候选研究设计的优劣、最小成立条件和失败边界；由队员决定核心设计后，再由主参谋派发正式分析。

许可代码仅完成读取、质量／覆盖统计、描述图和特征公式的维度／可计算性检查；核心关联估计、算法排名、显著性结论及其最终模型由队员独立完成。本轮不训练复杂模型，不发布 TOP5。

## 5. 候选方法比较内容

至少比较下列三类设计的目标、对照、独立样本单位、季节／自相关处理、四类资料覆盖、信息泄漏风险、输出与局限：

| 候选设计 | 需重点论证 |
|---|---|
| 单事件同季节背景／异常诊断 | 支持描述性关联；对照年缺测与长期趋势如何影响可比性 |
| 匹配天气过程／相似窗口比较 | 匹配变量和窗口如何预先固定；重叠窗口不独立的处理 |
| 多事件统计关联与排序（条件候选） | 需要独立事件与对照审核；当前标签不足，不能直接开训 |

排序方案须说明相关变量冗余、多重比较、方向与排名稳定性评估。可比较分块重抽样／留年稳定性等设计的适用条件，不把重抽样数量当独立事件数。

## 6. 首轮交付与验收

只在 `track_b/research/q1/` 写入：

- `METHOD_OPTIONS.md`：目标、候选路线比较、待队员决定项。
- `results/input_check.json`、变量语义／QC 诊断表、样本纳入统计、候选特征登记表；表名在交接索引中明确。
- `figures/` 描述图，注明资料类别、单位、时区、候选事件阶段和质量视图。
- `scripts/`、`config/`：实际运行代码与固定配置；能从仓库根用本窗环境重跑并只写本问目录。
- `PROPOSALS.md`：公共字典／质量策略修订提案和所需来源，区分已核实与待核实。
- `HANDOFF.md`：执行状态、命令、输入／输出哈希、限制、跨问接口和下一动作。

验收：四类资料均逐项解释可用性；未知 QC 未误作合格；原值与公共哈希不变；窗口与时钟可复查；图表可重跑；无虚构 TOP5／因果；全部关键缺口有负责人。图像输出后实际打开检查，再登记检查对象的哈希；未看过不能标“已目视核验”。

## 7. 跨问接口与缺口责任

- **向 Q2／Q3 输出：** 经主参谋审查的变量语义提案、质量视图、候选特征登记、窗口与滞后约束；Q2 不限于这些候选或未来 TOP5。
- **需要 Q3：** 事件阶段与时间证据的候选表、误差、历史可用性约束；标签接受由主参谋统一发布。
- **需要 Q4：** 经核验的站点／源区／目标空间对象及代表性说明；位置未核实前不进行精确空间归因。
- **本窗牵头公共缺口：** 小时时段语义、FLUX 单位／方向／处理方法、降水质量、县日单位／日界／聚合。Q2 牵头机制／遥感，Q3 牵头标签／时效，Q4 牵头空间／地形；重复检索前先读主参谋分发的提案。

跨问交接均包含 `event_id`、`phase`、带误差的 `time`、`space_id+crs`、`units+qc_policy`、`available_time+issue_time`、`data_role`、版本和 SHA-256；未知保持 null。研究窗落盘，由主参谋读取、集成并分发。
