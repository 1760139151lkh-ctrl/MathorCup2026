# Q1 第二轮交接：语义追溯与年度等权背景

**状态：本轮执行完成，提交第二轮联合审查。** 日期：2026-10-24（America/New_York）。核心模型、最终因素采用与质量敏感性方案仍待队员判断。本轮未发布 TOP5、显著性、因果或预测覆盖率结论，未 push。

## 执行身份与保存范围

- 实际执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1`；分支：`codex/track-b-q1-r2`。
- 第二轮共同基线：`76ee1532cb2acf36fb82c5f4749a4288507dfcc8`。冻结清单：`track_b/audit/stage4/round2/baseline_manifest.json`，565 项，SHA-256：`c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d`。
- 实际解释器：本树 `track_b/.venv/bin/python`，Python 3.12.14，44 个锁定包；没有重建、安装或升级依赖。
- 启动验证 UTC：`2026-10-24T06:00:29.599345+00:00`。本轮计算 UTC：`2026-10-24T06:08:15.386800+00:00`。最终收尾时刻及五组技术检查以 `workspace_verification.json` 为准；该记录会在最终提交前刷新。
- 只写本目录 `track_b/research/q1/round2/`。首轮分支保留；首轮 130 个受保护文件在计算前后均通过哈希校验。原始数据、公共规则和首轮窗口表没有改动。
- 本文件不嵌入包含自身的最终提交号；实际提交号见本轮最终交接消息或本分支 Git 记录。

## 结果与证据

| 工作项 | 本轮结果 | 入口 |
|---|---|---|
| 版本、QC、小时语义 | 12 项主张中 3 项可按明确角色采用、5 项排除直接推断、4 项仍未知；没有迁移远端 QC | `SEMANTICS_REVIEW.md`、`results/semantic_adoption.csv` |
| 指定常值段 | 原附件已有连续 4317 标签的 `1.776582`，与处理副本逐项一致；可排除阶段 3 标准化引入，更早成因仍未知 | `results/constant_segment_trace.json`、`results/constant_segment_boundary_excerpt.csv` |
| 年度等权背景 | 复用首轮 2268 行；1890 行历史年度值、378 行独立列示的 2026 值，形成 378 个分组 | `results/background_year_values.csv`、`results/background_equal_year.csv`、`results/target_year_values.csv` |
| 有效年数 | 234 组有 5 年；144 组有 4 年，均为 24 个 FLUX 变量缺少 2022 年数值有效记录 | `results/background_missing_years.csv` |
| 四类背景草稿 | MET/RADM/SOIL/FLUX 描述草稿，包含固定的 6 个代表变量与全部 24/72/168 小时窗 | `BACKGROUND_DRAFT.md`、`figures/equal_year_background.png` |
| 受影响用途与后续路线 | 8 类变量/用途的影响、未知和下一动作；分列可继续工作与实际阻断 | `results/affected_features.csv`、`ROUTE_UPDATE.md` |

年度等权规则固定为：在每个 `anchor_id × window_hours × variable_id × quality_view` 组内，仅汇总 2021—2025 年；年度 median 有限且 `descriptive_view_count > 0` 时该年权重为 1。缺年不填 0，不按有效小时数加权，不新增覆盖率剔除阈值。QC0 与 unknown 保持分列，2026 不参与背景计算。表中保留实际年份、缺年、小时计数及首轮 CSV 物理行号（表头为第 1 行）。

两个参考锚点选择了相同的已存整小时样本和值，不能把重复结果当作独立分钟敏感性证据。背景年份只表示历年同日历标签窗，不等于已确认的无事件对照。

`FLUX__amb_e_sat` 有 5 个数值有效背景年，但 2022 三个窗的年度 median 均为常值 `1.776582`。数值有效不等于质量认证；本轮没有自行删值、剔年或补 QC。常值段仅检查 2022-07-17 21:00—2023-01-13 17:00（源钟 UTC+8 假设，含末端）；2022 CSV 第 4751—8761 行接 2023 CSV 第 2—307 行。只保存 12 行边界摘录，未扩扫其他常值段。

## 来源、语义与机器字段

来源 URL、版本或未知状态、获取 UTC、实际阅读范围、文件大小和 SHA-256 均见 `results/source_register.json`。本轮复用首轮 WaterNet 元数据、TPDC 前端壳与远端 2026 样本，新增两次有界响应获取：ESSD 正式版 HTML 360458 字节、所引 AAS DOI 的 404 响应 10614 字节。错误响应不记作已读正文；HTTP 200 前端壳不记作已核验处理说明。

ESSD 的数据 DOI 指向 302428，目标为 303600，不能直接认证本地处理链。目标 FLUX 的 QC 1—9 字典、处理版本、小时平均标签起止/中心与实际可用时刻仍未知。WaterNet 的页面版本标记不等于本地数据处理版本。新增材料为事后取得，不能默认加入 Q3 灾前信息集。

机器上下文见 `results/context.json`：`physical_phase=background`、`data_role=exploration`，未知 `available_time`、发布时刻及小时边界使用 null，并保留说明。其他文件通过 `context_ref` 或相应规范字段关联。没有将源区启动、目录代理或下游到达混为同一时间对象。

## 复跑与验收

以下命令在上述唯一执行根运行。核验现有完整包（不修改文件）：

```sh
track_b/.venv/bin/python track_b/research/q1/round2/scripts/finalize_packet.py --verify-only
```

重新生成计算产物完全离线，读取首轮保存的窗口表及本轮已保存来源，不重新计算首轮小时窗口：

```sh
track_b/.venv/bin/python -W error::DeprecationWarning track_b/research/q1/round2/scripts/run_round2.py > track_b/research/q1/round2/run.log
```

重算会更新生成时刻和图表，使原产物清单及对应审查哈希失效。需重新检查图像、更新对应审查哈希后，再运行不带 `--verify-only` 的 finalizer 生成新输出清单。历史来源不需要联网重新获取；`scripts/capture_sources.py` 对现有响应只核验缓存，来源响应及回执已随包保存。

最终工作区检查命令：

```sh
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q1 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q1 --expected-base 76ee1532cb2acf36fb82c5f4749a4288507dfcc8
```

- `results/analysis_checks.json` 的 11 项检查通过，4 项合成算术检查与观测背景明确分开；核对缺年不填零、零值有效、小时数不改变年度权重、空背景为 null。
- 独立 AI 复核实际重算全部 378 组等权统计并检查 1890 行背景、378 行 2026 记录、年份/权重/物理行引用、代表变量和指定原始边界；见 `results/independent_review.json`。它没有重算首轮小时窗，也不代表队员科学采用。
- 六面板图已经实际打开检查，标签、年份计数与图例可读；对应 PNG 的 SHA-256 与检查范围见 `figures/visual_review.json`。该记录为 AI 视觉检查，非人工审稿。
- 启动及收尾工作区验证覆盖冻结输入、工作树基线、环境锁、六种真实格式与写入范围；这些是技术检查，不是模型通过证明。

直接输入索引为 `input_manifest.json`，稳定产物索引为 `output_manifest.json`，均不包含自身；输入清单也不包含输出清单。输出清单包含输入索引、任务快照、文档、代码、配置、结果、图像和保存的来源，排除自身、可变 `workspace_binding.json` / `workspace_verification.json`、`*.log` 与 `__pycache__`。这些排除项仍由 Git 或显式运行记录保留，不能把它们误认为清单已覆盖的稳定科学产物。

## 联合审查所需决定

可以继续使用固定标签窗、年度等权算术及有明确限制的四类区域站背景草稿。风向角度的标量均值不作物理平均方向解释；降水 median 为 0 不表示无雨或累计雨量为 0，辐射 median 不是积分能量。

尚未解决的语义实际阻断质量接受、通量物理解释、累计量、正式因素筛选和历史实时信息集；不阻断本轮描述性整理。更早常值成因需目标处理日志或原始观测支持；站点代表性、源区几何与事件真值也尚未由本轮建立。

向 Q2/Q3 交接的内容是背景表、语义限制和受影响用途提案。Q2 仍需独立考虑地形、物源与结构；Q3 需自行核验真实可用时刻。公共规则如需修改，由主参谋审查后发布，本窗没有直接改写。

下一轮由队员先确认描述性因素比较还是多事件关联、对照/分组、共线因素处理、质量敏感性及资料可用性，再派发正式分析。本轮到此停止，等待第二轮联合审查。
