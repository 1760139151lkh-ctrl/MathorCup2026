# Q1 第二轮任务：语义追溯与等权背景草稿

状态：派单任务书；本文件不代表第二轮已经执行。日期：2026-10-24（America/New_York）。

## 身份与恢复

- 唯一执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1`；新分支 `codex/track-b-q1-r2`。
- 阅读 `track_b/docs/16_stage4_round2_workflow.md`、`track_b/docs/15_stage4_round1_review.md`、本问首轮 `HANDOFF.md` 与 `PROPOSALS.md`。
- 本轮合同 `track_b/config/stage4_round2_contract.json`；冻结清单 `track_b/audit/stage4/round2/baseline_manifest.json`。
- 精确共同基线提交与清单哈希以主参谋派单为准，未绑定时先报告；不得复制首轮提交冒充本轮。
- 复用本工作树现有 `track_b/.venv/bin/python`，不重建环境、不新增依赖。
- 只写 `track_b/research/q1/round2/`；首轮全部文件和公共输入保持原样。

## 已核对存在的输入

以下路径相对工作树根；新增公共任务书/合同/清单须在启动时另行核对。

- `track_b/research/q1/results/window_descriptives.csv`：两参考时刻、24/72/168h、2021—2026，含年度 median、角色与质量视图。
- `track_b/research/q1/results/constant_run_candidates.csv`、`variable_semantics.csv`、`quality_accounting.csv`。
- `track_b/research/q1/results/remote_flux_comparison.json`、`remote_flux_column_comparison.csv`、`remote_flux_candidate_qc_tokens.csv`。
- `track_b/research/q1/sources/waternet_metadata.html`、`sources/access_log.json`、`sources/READING.md`。
- `04_B赛道/01_逐小时地气观测（2021-2026）/FLUX_Gyirong_2022.csv` 与 `FLUX_Gyirong_2023.csv`。
- `track_b/data/processed/temporal/data_dictionary.json`、`hourly_quality_summary.csv`、`track_b/config/temporal_policy.json`。
- 首轮远端样本由 `sources/access_log.json` 实际路径读取；不按猜测文件名再次下载。

## 执行步骤

1. 在指定根核对分支、新共同基线和清单；按末节命令验证工作区，记录启动结果和实际解释器。
2. 先复用已存元数据和来源入口，只定向寻找 FLUX 处理版本、QC 编码、平均/订正链及小时标签起止/中心说明。
3. 对每一主张记录官方 URL/DOI、获取 UTC、版本、实际阅读范围、哈希及“可采用/可排除/仍未知”；HTTP 200 前端壳不能记作正文已读。
4. 核对远端 QC 的 1—9 与缺测含义和本地版本关系；找不到对应链即保持 unknown，不移植远端标记、不按 MET 编码解释。
5. 仅复查 `FLUX__amb_e_sat` 的一个 4317 标签常值段：2022-07-17 21:00—2023-01-13 17:00（UTC+8，含末端）。
6. 回看原行 2022 CSV 第 4751 行至 2023 CSV 第 307 行及最少邻行；解释行号计数规则，不扩扫全部常值段。
7. 将原观测、处理产物与候选填值解释分列；无处理证据时原因保持未知，不删值、不创建 QC、不解释为真实稳定状态。
8. 读取首轮固定窗口表，保留 `anchor_id × window_hours × variable_id × quality_view`；不重算首轮小时窗口或覆盖表。
9. 仅对 `historical_calendar_background` 的 2021—2025 年记录做年度等权汇总；2026 事件窗单列，背景年份不称“已确认无事件”。
10. 每年有效的年度 median 权重均为 1，输出年度值及其等权均值、中位数、范围、有效背景年数和年份列表；空年不填零。
11. 原 QC0 与 unknown 描述视图分列；报告不足 5 年的变量，两个参考选中相同小时集合时明确其并非独立敏感性结果。
12. 写 MET/RADM/SOIL/FLUX 四类背景草稿，明确区域站、单位/时段、缺测和质量限制；不挑最优窗、不发布 TOP5、因果或显著性结论。

## 本轮交付（均位于 round2）

- `SEMANTICS_REVIEW.md`：主张/版本/QC/时段/常值段的证据与采纳提案；`results/semantic_adoption.csv`。
- `results/affected_features.csv`：受语义或常值段影响的变量/候选特征、影响方向是否可识别及下一动作。
- `results/background_year_values.csv`、`results/background_equal_year.csv`：保留首轮输入行引用、质量视图、年数与等权公式。
- `BACKGROUND_DRAFT.md`、`ROUTE_UPDATE.md`：四类背景分析与后续路线；已知事实、解释和未知分别陈述。
- `sources/` 保存新增有界资料；`results/source_register.json`、`input_manifest.json`、`output_manifest.json` 绑定来源与大小/哈希。
- 所需新脚本仅放 `round2/scripts/`，记录离线复跑命令；最终更新本轮 `HANDOFF.md`，不覆盖首轮交接。

## 验收与交接

- 独立抽查等权汇总：有观测较多的年份不能获得更大权重；缺年、unknown、重复锚点有明确处理。
- 新产物使用合同规范字段；`physical_phase=background`、`data_role=exploration`；未知时段/可用时刻为 null 并说明。
- 输入与输出清单不包含自身；首轮哈希不变；图若新增，实际打开并记录所检查图的哈希。
- 可采用/可排除/仍未知均可结束补证，但需证据、影响和下一动作；不无限追索手册、不联系作者/注册/付费。
- 启动和收尾均运行：`track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q1 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q1 --expected-base <主参谋发布的本轮基线提交>`。
- 仅本问本轮文件按派单本地提交、不 push；将提交号、产物索引、未解阻断项和可继续分析交主参谋，等待联合审查。
