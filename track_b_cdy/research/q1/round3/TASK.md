# Q1 第三轮任务：因素族 TOP5 的三路线竞争

状态：已获用户实施授权的任务书；不代表研究已经执行。本轮须交付实际计算、图表与模型比较，不能仅作方法综述。

## 身份、授权与共同基线

- 唯一执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1`；分支 `codex/track-b-q1-r3`。聊天的父目录不是执行根。
- 先读 `track_b/docs/18_stage4_round3_workflow.md`、`track_b/config/stage4_round3_contract.json`、`track_b/docs/17_stage4_round2_review.md`、本问第二轮 `HANDOFF.md`，再核对本轮 `workspace_binding.json`。
- 精确共同基线、合同、冻结清单及其 SHA-256 以主参谋派单和本轮绑定为准；未发布时不猜测、不借用旧轮基线。
- 第三轮直接在本地开展完整模型研究；旧任务中的“只背景、不发布 TOP5、不作核心计算、不装依赖”不是本轮限制。简化模型是对照，不是研究上限；队员保留最终科学采用权。
- Git 管理的新文件仅写 `track_b/research/q1/round3/`；原始资料、首轮、第二轮及其他问保持原字节，不重跑会改公共输入的阶段3管线。
- 原 `track_b/.venv/bin/python` 保留，标准五组验证仍使用它；新增实验依赖使用本问局部锁定环境，不改原44包锁。本轮不使用远程服务器。

## 输入与数据责任

- 读 `track_b/data/processed/temporal/hourly_raw_numeric.parquet`、`hourly_strict_qc0.parquet`、各质量 mask、`hourly_time_axis.parquet`、数据字典及 `track_b/config/temporal_policy.json`。
- 复用首轮 `results/window_descriptives.csv`、质量与语义表，第二轮 `results/background_equal_year.csv`、`background_year_values.csv`、语义采纳表和背景草稿作为固定对照；不覆盖旧结果。
- Q1 负责变量定义、质量、小时/累计时段和站点代表性补证；Q2 负责机制与 SAR，Q3 负责事件/波形/预报，Q4 负责 DEM/光学/河网/几何，避免重复获取。
- 新公开资料可扩展至必要区域、产品和时期；第二轮单对影像/128MiB约束不延续。大型资料只写 `/Users/maxchen/Documents/MathorCup/research_cache/round3/q1/`，按内容版本追加并只读引用实际哈希；不写其他问缓存或runtime。Git保存来源索引、代码、配置及必要小样本。
- 来源记录 URL/DOI、版本、获取 UTC、实际阅读/读取范围、字节与哈希。认证失败关闭该入口并寻找合法公开替代，不把 HTML/元数据当像元或观测。
- 新公共质量结论或他问新输入先交主参谋审查、按哈希发布副本；不直接改公共规则或读取他问未交接的活动文件。

## 执行与实验设计

1. 核对身份、基线和冻结输入，保存启动标准验证；先登记 `EXPERIMENT_PROTOCOL.md`，写清因素族、特征、质量视图、分组与评分，再计算结果。
2. 因素族按物理量/过程组织，避免多个高度、深度、窗口重复占据 TOP5；登记原变量、派生公式、单位、支持时段、方向及物理含义。
3. 保留24/72/168小时固定结果；新增极值、趋势、持续时间、垂直梯度与土层梯度，明确缺测分母、最低支持和累积语义未知项。
4. 共同背景为2021—2025年目标日历日期前后30日；年度等权，按天气过程分组。先定义过程划分并保存组号；重叠窗口的训练/评价使用隔离，避免相邻小时冒充独立样本。
5. 路线 A：边际异常与背景对照，计算方向、背景位置和持续性；同时保留有效年数和有效过程数。
6. 路线 B：收缩协方差与因素族条件贡献，检查共线性、尺度、维度和样本支持；缩放/协方差仅在各训练折内估计。
7. 路线 C：相似天气过程对照，比较季节范围、背景选择与过程匹配变化下的排名；匹配不得使用事后结果挑对照。
8. MET/RADM/SOIL已有接受质量视图与FLUX/降水unknown视图分开；分别计算纳入/排除后的三路线结果，unknown不能自动升为通过QC。
9. 对真实改变小时样本集合的参考时刻±1小时重算；记录各锚点实际小时标签，旧两个分钟锚点集合相同不算新增敏感性。
10. 使用留年、留过程和组级重采样评估排序稳定性，保留随机种子、入选频率、名次变化和方法分歧；报告年份少时的不确定性。
11. 三路线分别交候选 TOP5，再给推荐因素表；综合采用规则应在协议中登记，并保留对该规则的敏感性，不能看结果后只报有利排名。
12. 主动追溯FLUX处理/QC/小时时段及区域站到源区的代表性。单条来源未知不停止已可开展的因素竞争；降低相应结果的适用层级并量化纳入影响。
13. 收到Q3审核通过的事件与监测暴露后，增加统计关联支线并按独立事件留出；未收到时个案关联结果仍计算，不能虚增真实训练/验证样本数。

## 早交接口与最终交付

- 先交 `INTERFACE_HANDOFF.md`、`results/feature_contract.csv`：因素族/变量、公式、单位、时间支持、质量视图、站点空间对象、可用性及版本，供Q2/Q3通过主参谋接入。标准入口为 `exports/feature_bundle.json`，字段严格按本轮contract的bundle要求，files逐项登记path/bytes/sha256/role，清单不含自身。
- `results/rankings.csv`、`top5_candidates.csv`、`recommended_factors.csv`、`ranking_stability.csv`：三路线及质量/锚点/背景变体可关联，不能只留最终五行。
- `results/fold_membership.csv`、`feature_support.csv`、`comparison_metrics.csv`：年度、天气过程、隔离、有效年数及实际比较分母。
- `MODEL_COMPARISON.md`、`EVIDENCE_REVIEW.md`、`PAPER_OUTLINE.md`：计算结果、主方案/挑战方案、支持与反对证据、局限及论文方法/结果/讨论材料；个案关联、统计关联、机制证据分层。
- 新脚本放 `scripts/`，参数放 `config/`；`REPRODUCE.md` 给完整本地离线复跑命令、环境锁与联网获取命令。图放 `figures/`，实际打开并记录所读图哈希。
- `results/input_manifest.json`、`output_manifest.json`、`source_register.json`、`validation.json` 记录大小/哈希、缓存引用及实际验证；清单不自包含，易变记录排除理由写明。最终更新本轮 `HANDOFF.md`。

## 验收和交接

- 必须有三路线实际计算、三套候选TOP5、推荐因素表、入选稳定性及可复跑图表；缺证据限制具体解释，不以unknown结束整个工作包。
- 检查年份等权、因子族去重、折内拟合、重叠隔离、QC与unknown分列、±1小时确实改变样本、空年不填零和有效分母；不把排名称因果证明。
- 所有跨问结果保留 `model_id/mechanism_id/experiment_id/scenario_id/geometry_version/parameter_version`，不适用明确说明；继承公共规范的事件/阶段/UTC/信息截止/角色/输入版本字段。
- 启动及收尾：`track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round3 --question q1 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q1 --expected-base <主参谋发布的第三轮共同基线>`。
- 仅本问round3本地提交、不push；将提交号、manifest哈希、实际复跑命令、早交接口和剩余缺口交主参谋，队员在联合审查中确定最终采用。
