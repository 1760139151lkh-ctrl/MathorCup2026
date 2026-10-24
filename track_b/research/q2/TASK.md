# Q2 触发评估：首轮任务书

状态：**任务已定义，研究与小实验待执行。** 本文件不是已确认触发机制、临界条件或评估模型。工作流见 `track_b/docs/14_stage4_workflow.md`；共同基线与哈希由主参谋在 `track_b/audit/stage4/baseline_manifest.json` 发布。

## 1. 目的与本轮终点

区分长期物源／结构背景、动态水热状态及失稳阶段，评估现有与可取得资料能约束哪些参数，形成“参数—证据—可辨识性”表、候选研究路线和有边界的最小实验。Q2 不把 Q1 候选气象因素或未来 TOP5 当作全部触发机制。

首轮只确认资料与方法的可行性，为队员独立选定核心评估模型准备证据；不从单事件反推出普适阈值，不发布已验证临界条件。

## 2. 已知输入（仓库根相对路径，只读）

| 输入 | 精确路径与用途 |
|---|---|
| 题意／口径／阶段 3 状态 | `track_b/docs/01_task_matrix.md`、`track_b/docs/02_definitions_validation.md`、`track_b/docs/13_stage3_handoff.md` |
| 机制与来源登记 | `track_b/docs/05_research_sources.md`、`track_b/audit/research_sources.json`、`track_b/docs/11_event_remote_evidence.md` |
| 事件阶段证据 | `track_b/data/external/event_remote/event_evidence_ledger.json`、`track_b/data/external/event_remote/supplemental_original_source.json` |
| 已取得研究校样 | `track_b/data/external/event_remote/jms_2026_uncorrected_proof.pdf`；为事后研究且是校样，引用版本及阅读范围要留痕 |
| 小时时序与语义 | `track_b/data/processed/temporal/hourly_time_axis.parquet`、`track_b/data/processed/temporal/hourly_raw_numeric.parquet`、`track_b/data/processed/temporal/hourly_strict_qc0.parquet`、`track_b/data/processed/temporal/data_dictionary.json`、`track_b/docs/09_temporal_pipeline.md` |
| 空间诊断与地形 | `track_b/data/processed/spatial/pipeline_report.json`、`track_b/data/processed/spatial/dem_utm45_30m.tif`、`track_b/data/processed/spatial/nc_dem_native_grid.tif`、`track_b/data/processed/spatial/nc_glacier_mask.tif`、`track_b/data/processed/spatial/spatial_diagnostic.gpkg` |
| 空间来源与哈希 | `track_b/data/processed/spatial/source_manifest.json`、`track_b/data/processed/spatial/output_manifest.json`、`track_b/audit/spatial/netcdf.json`、`track_b/docs/10_spatial_pipeline.md` |
| 可读取背景分类 | `track_b/data/external/event_remote/worldcover_2021_v200_test_aoi.tif`、`track_b/data/external/event_remote/worldcover_crop_summary.json`、`track_b/audit/stage3/worldcover_nc_alignment.json` |
| 2026 遥感候选与获取限制 | `track_b/data/external/event_remote/scene_candidates.csv`、`track_b/data/external/event_remote/scene_inventory.json`、`track_b/data/external/event_remote/asset_access_tests.json` |
| 预报技术样本 | `track_b/data/processed/forecast_sample/gfs_2026082518_f009_aoi.nc`、`track_b/data/processed/forecast_sample/summary.json`、`track_b/docs/12_environment_forecast.md` |
| 外部样本完整性 | `track_b/data/external/event_remote/manifest.json` |

原始 NC 物理变量的实际文件路径从 `source_manifest.json` 查询，禁止凭目录名猜时间或事件状态。输入清单需登记最终实际读取的原路径和 SHA-256。

## 3. 科学边界

- 冰岩体初始失稳、水源作用、演化为泥石流及下游传播分层解释。降雨型泥石流阈值不能无条件迁移为冰岩崩启动条件。
- 参数 NC 无 time 维；速度属于 2014—2024 气候态。NC mask 为四个 RGI 冰川参数域，不是已核实的 2026 失稳面；历史厚度／速度不自动是事发初值。
- 两套 DEM 在 NC 正 mask 内均值差约 −30.74 m、范围约 −80.49 至 109.37 m，产品年代／垂直基准未知。禁止静默拼接、任意加常数或把差值解释为真实冰川变化。
- 本地四年土地覆盖在 NC mask 全部无有效类别；WorldCover 2021 可读，但仅为背景，不是 2026 灾前状态、真实失稳边界或精度保证。
- 41 个 2026 官方遥感候选为目录元数据，匿名像元访问测试未成功。场景存在、整体云量或预览图不证明源区可解译；需检查实际像元、云／雪／影、配准及获取时间。
- 所有现有事件台账训练标签标志均为 false。单事件事后拟合不能证明普适临界值；仿真能复现某结果也不能证明触发机制成立。
- 区域塔站与粗网格 GFS 不能直接替代高海拔源区真实状态；历史 available_time 未核实的补充资料只能用于明确标注的事后研究或情景。

## 4. 本轮步骤与许可小实验

1. **核对输入与对象。** 绑定共同基线，创建本问输入清单；分别列长期背景、候选失稳阶段、动态状态与下游传播需要的空间／时间对象。
2. **建立参数证据表。** 每项参数记录符号、定义、单位、空间尺度、时间尺度、观测或推导方法、数据路径、来源阅读范围、误差、可辨识／仅可界定／未约束、跨问使用者。
3. **定向机制核验。** 优先实际取得的原始研究和官方产品说明；为各候选机制列支持／反证／未观测项。摘要、校样、作者推断和现场观测分级，不把文献假设升级成本地实测。
4. **遥感获取与覆盖小试验。** 先从已有候选表做少量事前／事后场景的覆盖及可用性表；如合法像元可访问，仅取满足具体问题的小 AOI／少量场景并存本问 `sources/`。实际检查源区可见性、配准及时间；认证阻碍原样记录，不反复下载不明资产。
5. **数据可辨识性小实验。** 可做现有参数的有限值／范围／空间支持统计、单位与分辨率一致性核验、候选时序窗口覆盖；可对参数依赖公式做量纲和输入缺失检查。尚未核实源区时，只报告“NC 参数域”诊断。
6. **比较候选模型并交接。** 明确每条路线需要哪些新证据、可回答的题目部分及退出条件，队员独立决定核心模型／失稳条件之后才进入正式估计。

许可范围是来源审计、几何／像元可用性、参数诊断和计算通路试验。不得替队员求解核心失稳模型、拟合最终阈值或从任意情景参数生成已验证触发结论。

## 5. 候选路线比较

| 路线 | 必须比较的条件和限制 |
|---|---|
| 可解释单变量／联合经验条件 | 独立事件和可靠对照的需求；阈值估计、误报漏报与样本外验证条件；目前标签缺口 |
| 物理启发的稳定性／失稳条件 | 几何、物源、密度、结构、水热等参数能否观测；不可辨识参数与尺度误差 |
| 文献约束的条件／情景范围 | 文献对象和本事件机制是否可比；迁移范围；仅支持条件性结论的限制 |

每条路线列时间尺度／空间聚合改变时如何验证可靠性，以及计算成本、输出、证据门槛和失败条件。统计估计、文献迁移、情景指定三种阈值来源必须分列。

## 6. 首轮交付与验收

只在 `track_b/research/q2/` 写入：

- `METHOD_OPTIONS.md`：分阶段机制图示／说明、候选路线比较、队员待决定项。
- `results/parameter_evidence.csv`：参数—证据—可辨识性表；`results/remote_feasibility.csv`：场景／像元真实获取与可解译性。
- `results/input_check.json` 与实际执行的数据诊断表；需要时在 `figures/` 保存背景或覆盖图。
- `scripts/`、`config/`、`sources/`：本问可重跑小实验、固定配置、官方来源及获取／阅读记录。
- `PROPOSALS.md`：遥感／机制公共结论、补充获取、参数范围或源区问题提案；未获采用明确待审。
- `HANDOFF.md`：命令、证据、版本哈希、适用范围、失败／未执行项、跨问需求。

验收：每个关键参数有证据状态和下一动作；元数据与像元解译区分；背景与事发状态区分；无未核实实测值或普适阈值；时空可靠性方案可执行；公共输入哈希不变；小实验可复跑，图像实际检查后才登记视觉验收。

## 7. 跨问接口与公共缺口责任

- **接收 Q1：** 经过统一审查的候选水热／气象特征、质量与窗口限制；这些不构成排他性机制清单。
- **向 Q3：** 候选触发对象、输入参数可用性、适用范围、临界条件的证据等级和不确定性；未经队员确认的参数不得直接成为正式预报规则。
- **与 Q4：** 交换源区／物源／初始状态候选和参数约束，接收地形与可行性反馈。传播校准结果不回填为机制真值。
- **本窗牵头：** 机制证据、少量合法遥感获取与可见性、物源／结构／水热参数来源。Q1 牵头语义／质量，Q3 牵头事件标签／预报时效，Q4 牵头空间／地形；公共几何采用由 Q4 提案、主参谋发布。

交接至少记录 `event_id`、`phase`、`time+time_uncertainty`、`space_id+crs`、`units+qc_policy`、`available_time+issue_time`、`data_role`、共同基线、输入版本与 SHA-256。由主参谋读取本问落盘成果并分发，不主动给其他研究聊天发消息。
