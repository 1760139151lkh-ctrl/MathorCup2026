# Q3 预报区间：首轮任务书

状态：**任务已定义，研究与小实验待执行。** 尚无已验证预报、95% 区间或经验覆盖率。工作流见 `track_b/docs/14_stage4_workflow.md`；主参谋发布 `track_b/audit/stage4/baseline_manifest.json` 后绑定共同基线与输入哈希。

## 1. 目的与本轮终点

明确“预测哪个物理阶段、在何时发布、届时有什么数据、如何评价”，核验事件标签与业务时效，构造最小无泄漏回放技术检查。先交付可执行评价协议与证据缺口，再由队员独立选择预报与区间方法。

首轮可独立推进，不需等待 Q1 最终 TOP5 或 Q2 最终条件。若以后采用其结果，需要遵守探索／训练／校准／验证分组；不能用全事件事后选出的阈值再验证同一事件。

## 2. 已知输入（仓库根相对路径，只读）

| 输入 | 精确路径与用途 |
|---|---|
| 题面对象与协议草案 | `track_b/docs/01_task_matrix.md`、`track_b/docs/02_definitions_validation.md`、`track_b/docs/13_stage3_handoff.md` |
| 事件与遥感证据说明 | `track_b/docs/11_event_remote_evidence.md`、`track_b/docs/05_research_sources.md` |
| 事件证据台账 | `track_b/data/external/event_remote/event_evidence_ledger.json` |
| 历史候选与来源 | `track_b/data/external/event_remote/historical_candidates.json`、`track_b/data/external/event_remote/supplemental_original_source.json` |
| 官方事件快照 | `track_b/audit/event_metadata.json`、`track_b/data/external/event_remote/runs/20261024T034202Z/raw/usgs_event.json`、`track_b/data/external/event_remote/runs/20261024T034202Z/raw/usgs_origin_quakeml.xml` |
| 研究版本／阅读记录 | `track_b/data/external/event_remote/jms_2026_uncorrected_proof.pdf`、`track_b/data/external/event_remote/runs/20261024T034202Z/paper_reading.json` |
| 预报说明与逐消息时效 | `track_b/docs/12_environment_forecast.md`、`track_b/data/processed/forecast_sample/summary.json` |
| 最小天气预报样本 | `track_b/data/processed/forecast_sample/gfs_2026082518_f009_aoi.nc` |
| 降水原始消息／获取日志 | `track_b/data/external/forecast_sample/precip_accum_6_9h.grib2`、`track_b/data/external/forecast_sample/precip_accum_0_9h.grib2`、`track_b/data/external/forecast_sample/precip_accum_6_9h.http.json`、`track_b/data/external/forecast_sample/precip_accum_0_9h.http.json` |
| 小时资料的时钟／可用性限制 | `track_b/data/processed/temporal/hourly_time_axis.parquet`、`track_b/data/processed/temporal/data_dictionary.json`、`track_b/docs/09_temporal_pipeline.md` |
| 外部数据版本与完整性 | `track_b/data/external/event_remote/manifest.json`、`track_b/audit/stage3/integration_checks.json` |

如果要读其他 GRIB 字段，实际文件在 `track_b/data/external/forecast_sample/`，并从既有 summary 中绑定字段路径和哈希，不靠名称猜时段。

## 3. 时间对象与科学边界

- 明确分开题面 10:30（UTC+8）、USGS 目录参考 10:52:10（UTC+8）及论文的启动／撞击／到达重建。它们是同一灾害链的不同证据或阶段，不能取平均或复制为独立事件。
- USGS 为 reviewed landslide 类目录记录，其时刻和位置是代理信息且有误差；不能自动成为源区首次失稳的精确真值。论文事后重建也不能直接作为当时可用输入。
- 当前 9 行事件证据均非已批准训练标签；NASA 54 条候选机制混合、尚未完成时间／来源／重复核验，**可直接用于独立历史训练或 95% 覆盖验证的已审核事件数为 0**。
- GFS 只有一次起报 `2026-08-25T18:00:00Z`、f009、六条字段；实际业务可得时刻未知。起报时间、有效时间、下载时间、S3 修改时间和 available_time 是不同概念。
- GFS 0.25° AOI 每字段 5×5 格，不能通过插值获得独立事件样本或分钟级现场信息。两段降水是 0—9h 与 6—9h 累计，不是瞬时雨强，不能相加。
- 带 available_time 未知的本地观测／再分析／遥感不能声称满足历史实时预报。只能做标注清楚的事后分析或理想化／延迟情景，不把情景时效当已证实业务事实。
- 题面要求的“触发时间 95% 置信区间”须在论文说明实际统计对象。参数置信区间、未来启动预测区间、事后时间重建区间不能混称。
- 下游到达由 Q4 支持；启动提前量与到达提前量分开。无预警真实事件须计漏报，不能从覆盖率或提前量分母删除。

## 4. 本轮步骤与许可小实验

1. **锁定评价对象提案。** 先写 `EVALUATION_PROTOCOL.md`，列启动、题面触发、到达三种对象、时钟和不确定性；提出主分析与敏感性对象供队员／主参谋确认，未确认不替换公共定义。
2. **逐事件／逐证据审核。** 在本问副本核对官方原始记录、来源、阶段、机制、原时区、误差、更新时刻与同链重复。候选接受／拒绝／待核实必须有理由。拟接受标签提交主参谋，不直接改公共台账。
3. **天气预报时效审计。** 从已有 GRIB／NetCDF 逐字段验证起报、有效、累计起止、单位、抓取信息；查官方发布记录或资料说明。无法取得真实发布时间时保留 null，提出有出处或显式假设的保守延迟情景。
4. **最小无泄漏回放。** 只做读取和信息门禁检查：为预先写入配置的一个／少量候选 issue_time，列每个输入的 available_time、是否可判定纳入、排除或 unknown、角色和理由。对 unknown 不自动放行；如运行理想化延迟情景，单列 scenario 结果。不生成灾害概率或最终区间。
5. **评价机械正确性小试验。** 可用清楚标为 synthetic 的少量手工时间例子检验时区换算、门禁边界和覆盖／提前量公式；至少包括相等边界、晚到数据、负提前量、缺失真值、区间真值、重复事件和漏报。这些样例不计入任何真实验证分母。
6. **比较区间／验证设计。** 说明候选方法的样本、交换性／时序／删失等假设及当前不可满足条件；提交数据补齐清单和后续最小获取范围。

本轮允许标签与时效审计、输入门禁、小型公式／边界测试；不替队员拟合核心预报模型、校准最终区间或声称覆盖率有效。新增历史起报先提出有界获取提案，经主参谋集成避免重复下载。

## 5. 候选方案必须比较

| 维度／候选 | 比较要求 |
|---|---|
| 事件时间／风险过程的概率模型 | 精确／区间／删失标签需求、非事件暴露定义、时序泛化与不确定性对象 |
| 分位数／共形等预测区间候选 | 样本量、校准集、独立性／交换性条件、时间依赖影响；标签不足时为何不能校准 |
| 物理／情景参数传播至时间范围 | 条件性与情景范围的含义；与统计 95% 保证的区别；Q2／Q4 依赖 |
| 验证设计 | 按事件／时间或区域分组；窗口隔离；避免同链／邻近小时／像元泄漏；事件覆盖与滚动发布覆盖分别定义 |

预先定义覆盖率分子／分母、模糊真值判定、区间宽度、区间评分适用条件、提前量、漏报、误报暴露以及空间范围的距离类型。不能以任意均值±1.96标准差代替方法论证。

## 6. 首轮交付与验收

只在 `track_b/research/q3/` 写入：

- `EVALUATION_PROTOCOL.md`：预测对象、issue_time、信息截止、95% 统计对象、样本单位与评价定义；候选决定明确待审。
- `METHOD_OPTIONS.md`：候选预报／区间方法、可行性与数据需求比较。
- `results/label_review.csv`：逐条证据审核和同链分组；`results/availability_review.csv`：时效与来源审计；接受标签数分探索／校准／独立验证报告。
- `results/replay_gate.csv` 和小实验检查结果；每项真实／情景／合成角色清楚。
- `scripts/`、`config/`、必要 `sources/`：可复跑读取、门禁和边界检查，所有输出限制本问目录。
- `PROPOSALS.md`、`HANDOFF.md`：公共标签／时效提案、输入输出版本哈希、运行证据、限制和下一动作。

验收：源区启动与下游到达不混用；不把未知 available_time 视为通过；同链去重；真实事件数与合成样例数分列；门禁和公式边界检查可复跑；现有资料不足时诚实报告不可验证项，不虚构覆盖率或 95% 能力。

## 7. 跨问接口与缺口责任

- **接收 Q1：** 变量语义、候选特征／窗口、质量与可用性限制；特征筛选以后只能在探索／训练侧进行。
- **接收 Q2：** 触发对象、条件／参数候选、估计样本和不确定性；最终回测不得使用测试事件参与拟合的条件。
- **接收 Q4：** 指定 source／site 的路径、传播／到达情景与不确定性，仅用于到达预警和空间范围；仿真时刻不能替换启动真值。
- **向全项目输出：** 事件阶段／标签接受提案、信息截止与评价协议；主参谋发布后才成为公共口径。
- **本窗牵头：** 事件真值、历史候选去重／审核、业务发布时效。Q1 负责观测语义／QC，Q2 负责机制／遥感，Q4 负责源区／目标／距离与地形；缺失空间定位提交 Q4，不自行猜测精确坐标。

每项交接记录 `event_id`、`phase`、`time+time_uncertainty`、`space_id+crs`、`units+qc_policy`、`available_time+issue_time`、`data_role`、基线／版本／SHA-256，未知保留 null 并注明影响。落盘供主参谋读取与分发。
