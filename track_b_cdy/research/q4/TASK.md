# Q4 传播仿真：首轮任务书

状态：**任务已定义，研究与小实验待执行。** 尚未形成事件仿真、传播路径或到达结果。工作流见 `track_b/docs/14_stage4_workflow.md`；基线由主参谋通过 `track_b/audit/stage4/baseline_manifest.json` 绑定。

## 1. 目的与本轮终点

核验实际源区、口岸目标、连续流路和地形支持，比较适合现有证据的传播模型层级，明确初边值／关键参数来源与数值验证要求，交付空间可行性图和小规模技术试验。

Q4 可立即并行开展几何、地形和计算可行性；正式初始状态与情景参数需同 Q2 交接，到达输出再支持 Q3。队员独立选择核心动力学模型和算法，本轮不完成实际灾害反演或最终传播仿真。

## 2. 已知输入（仓库根相对路径，只读）

| 输入 | 精确路径与用途 |
|---|---|
| 题意、协议、阶段状态 | `track_b/docs/01_task_matrix.md`、`track_b/docs/02_definitions_validation.md`、`track_b/docs/13_stage3_handoff.md` |
| GIS 处理与坐标限制 | `track_b/docs/10_spatial_pipeline.md`、`track_b/data/processed/spatial/pipeline_report.json`、`track_b/data/processed/spatial/coordinate_operations.json`、`track_b/config/spatial_policy.json` |
| 独立 DEM 米制候选 | `track_b/data/processed/spatial/dem_utm45_30m.tif` |
| 两套 DEM 对齐比较 | `track_b/data/processed/spatial/dem_on_nc_grid.tif`、`track_b/data/processed/spatial/nc_dem_native_grid.tif` |
| NC 参数域 | `track_b/data/processed/spatial/nc_glacier_mask.tif`、`track_b/audit/spatial/netcdf.json`；原 NC 路径从下列 source_manifest 查询 |
| 矢量／足迹与历史覆盖 | `track_b/data/processed/spatial/spatial_diagnostic.gpkg`、`track_b/data/processed/spatial/history_dem_coverage.csv` |
| GIS 输入输出哈希 | `track_b/data/processed/spatial/source_manifest.json`、`track_b/data/processed/spatial/output_manifest.json` |
| 事件／来源证据 | `track_b/data/external/event_remote/event_evidence_ledger.json`、`track_b/data/external/event_remote/supplemental_original_source.json`、`track_b/docs/11_event_remote_evidence.md`、`track_b/docs/05_research_sources.md` |
| 研究校样及核读记录 | `track_b/data/external/event_remote/jms_2026_uncorrected_proof.pdf`、`track_b/data/external/event_remote/runs/20261024T034202Z/paper_reading.json` |
| 遥感获取可行性 | `track_b/data/external/event_remote/scene_candidates.csv`、`track_b/data/external/event_remote/asset_access_tests.json` |
| 可读背景分类 | `track_b/data/external/event_remote/worldcover_2021_v200_test_aoi.tif`、`track_b/audit/stage3/worldcover_nc_alignment.json` |

只读原 NC 时从源清单绑定实际文件、变量、单位、时间属性与哈希；不要把目录名或变量名直接解释为 2026 初始条件。

## 3. 空间与物理边界

- 当前 `source_to_port_continuity_verified=false`；真实失稳面、口岸保护点及独立沟道线尚未核定。USGS 代理位置误差较大，不能直接当精确物源起点；不能凭地名猜点、用直线连接当河道。
- NC 网格 138×145、30 m，正 mask 7,152 格；它是 RGI 参数域，不是实际失稳面。速度为 2014—2024 气候态，无 time 维，不能宣称灾前即时流速或初始运动速度。
- 独立 DEM 与 NC DEM 来源、年代、垂直基准不明；在 mask 内差值均值约 −30.74 m、范围约 −80.49 至 109.37 m。不能静默拼接、随意平差或把差值归因于事件变化。
- 独立 DEM 投影副本 EPSG:32645、30 m，为双线性重采样候选，不是水文校正成果；外缘 NoData 不等于原始内部缺失。水文填洼／河道烧入会改变地形，若试验必须另存本问目录并量化影响。
- CGCS2000→WGS84 仅 ballpark、精度未知；水平转换技术可用不代表测绘精度。垂直基准、源边界、河岸／桥位误差应进入适用尺度限制。
- 2021 WorldCover 只是背景；四年本地土地覆盖在 NC mask 全 NoData。未核实分类／地表状态不能直接映射成事件摩阻系数。
- 事后论文路径／时间可用于约束候选或校准，但同一资料不再作为独立验证；仿真到达时刻不能替代触发真值，仿真成功不能证明机制成立。
- 无几何／参数依据时，可以进行明确标注的技术或合成测试；不能称事件还原、已核实影响区或实际预警距离。

## 4. 本轮步骤与许可小实验

1. **输入与空间对象核验。** 绑定基线／哈希，独立读取 CRS、transform、NoData、有效足迹与 NC 变量；列 `source_area`、`channel`、`target_site` 的已核实／候选／缺失状态、来源与误差。
2. **定向核查几何。** 核读已有原研究的地名、图与坐标证据；提出源区、目标点及河道候选。影像需要时向 Q2 提出明确位置／时间需求；未获证据前不固定公共几何。取得可核验几何时，只在本问目录保存并向主参谋提案。
3. **地形可行性小实验。** 比较两套 DEM 的足迹、有限值、基准／年代缺口、重采样影响和差值分布。真实路径已有可核验依据时，再做走廊有效覆盖、边界余量和纵剖面检查；没有则记录连续性未验收，不输出臆造沿河距离。
4. **候选数值环境小试验。** 可验证栅格窗口读取、坐标和单位、时间步／网格组织、输出帧 I/O 与运行成本。若用合成坡面／水槽验证某一通用数值性质，须标 synthetic，与事件试验分目录／角色；不将合成到达时间当事件结果。
5. **初边值／参数可辨识性表。** 地形、物源体积／厚度、密度／组分、摩阻／流变、夹带／侵蚀、边界、网格／步长、求解器分别列来源／范围／是否实测。缺失留空或情景候选，不能用默认软件值充当实测。
6. **模型层级比较与交接。** 说明可用证据支持的最小模型、需补资料与数值检查，交队员确定核心方程、算法和参数后再开展正式基线。

许可范围为地形／几何诊断、技术 I/O 与计算成本试验、清楚标注的合成数值检查。不得替队员实现并求解最终核心动力学模型、以未证实端点生成实际传播路径，或发布事件到达／影响范围结论。

## 5. 候选方法比较

| 层级 | 必须比较的内容 |
|---|---|
| 沟道／沿程简化模型 | 需要可靠中心线与断面、源体积及阻力；能回答沿程到达的哪些问题，横向淹没能力的限制 |
| 深度平均运动／水动力 | 需要二维连续地形、物源、流变和侵蚀参数；稳定性／守恒／网格步长敏感性和计算成本 |
| 更复杂多相／耦合模型 | 新增参数是否可辨识、软件依赖与资源需求；现有证据为何足够或不足，是否有必要 |

每类均列方程／文献来源、输入、可观测输出、参数维度、校准与独立验证分工、失败条件。先比较证据与成本，不为比较而一次安装所有大型仿真软件。

## 6. 首轮交付与验收

只在 `track_b/research/q4/` 写入：

- `METHOD_OPTIONS.md`：候选模型层级、证据门槛、计算需求与队员待决定项。
- `results/geometry_evidence.csv`：源区／流路／目标空间对象及来源／误差／状态；未知保持未知。
- `results/terrain_feasibility.json`、`results/parameter_evidence.csv`：地形选择依据与初边值／关键参数表。
- `figures/`：CRS、有效足迹、NC 参数域、已核实／候选几何分层标注的空间可行性图；连续性未验收时图注直写。
- `scripts/`、`config/`、必要 `sources/`：可重跑诊断／技术试验与来源记录；合成试验另列角色。
- `PROPOSALS.md`、`HANDOFF.md`：公共空间／地形选择提案、运行命令、结果版本哈希、限制和下一动作。

验收：不把 NC mask 当实际失稳面；两套地形不混用；真实源区／目标／河道缺口明确；空间连续性有证据才标通过；数值／物理／事件三层验证分开；图像实际打开检查并登记哈希；公共原始与阶段 3 产物不变，小试验可复跑。

## 7. 跨问接口与公共缺口责任

- **接收 Q2：** 候选物源、结构／水热机制、初始状态／参数范围及证据等级；不把待审参数视为已知真值。
- **向 Q2：** 几何／地形支持、物源可辨识性和物理可行性约束；输出是诊断，不强迫 Q2 把某种机制当既成事实。
- **向 Q3：** 未来正式基线的 `source_id`、`site_id`、路径／距离定义、传播／到达时间与情景／误差；首轮只交可行性与接口，不交虚构结果。
- **本窗牵头：** 实际源区、保护点、独立流路、连续走廊、地形产品来源／年代／垂直基准。Q2 负责遥感像元及机制，Q3 负责时刻／时效，Q1 负责变量语义／QC；公共空间几何由主参谋集成发布。

交接记录 `event_id`、`phase`、`time+time_uncertainty`、`space_id+crs`、`units+qc_policy`、`available_time+issue_time`、`data_role`、共同基线／输入版本／SHA-256。只落盘，由主参谋读取、审查和分发，不直接改其他窗文件或主动发聊天消息。
