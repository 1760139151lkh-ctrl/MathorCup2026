# Q3 预报与不确定性：首轮交接

**状态：首轮完成，待联合审查。** 已完成证据/方法比较、数据时效审计和最小门禁/评价公式实验；未拟合正式预报模型，未批准训练/验证标签，未生成真实95%区间或覆盖率。

## 1. 基线与运行

- 工作目录：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3`；分支：`codex/track-b-q3-r1`。
- 共同起点：`1d64f91fe057075df7c9199b5c17c68839bc6153`；契约：`stage4-r1-v1`。
- 聊天：`01a16c21-4a06-7653-be46-2f2ffcc0ff2c`；界面关联目录仍为父目录，文件操作实际绑定上述独立Git worktree。
- 本窗独立Python3.12.14、44包精确锁、六种真实格式、431冻结输入、仅本问文件责任，启动与交接检查5/5通过，证据`workspace_verification.json`。
- 本轮25个稳定直接输入及SHA-256见`results/input_manifest.json`；运行时派单/就绪记录另存`results/workspace_*_at_run.json`，避免后续验收更新混入科学输入。
- 结果记录UTC：`2026-10-24T04:39:58.022299+00:00`。本轮仅本地提交，不push；最终提交hash以本窗最终回复和Git HEAD为准，避免在提交内自引用。

## 2. 成果与关键发现

| 成果 | 路径 | 实际结果 |
|---|---|---|
| 评价对象/时间/区间/误报协议 | `EVALUATION_PROTOCOL.md` | 启动、题面参考、到达分开；条件覆盖和全部事件有效预警覆盖分开；误报分母/缺测/模糊真值明确 |
| 方法比较与采用条件 | `METHOD_OPTIONS.md` | 风险过程、分位数、共形校准、物理情景、事后重建分列；未选择最终核心模型 |
| 标签逐条审核 | `results/label_review.csv`、`results/label_summary.json` | 9案例证据=1灾害链；54历史候选；63行保留；接受训练/独立验证均0 |
| 标签实际缺陷 | `EVIDENCE_REVIEW.md` | 重复候选13282/13292；时钟字段冲突7723/14488；仅17482目录日期与小时轴重叠但时刻/时区/来源不足 |
| 实际GRIB时效核验 | `results/availability_review.csv`、`results/forecast_metadata_checks.json` | 6条消息时间/单位/累计窗口与summary及NetCDF一致；业务首次可用时刻仍null |
| 真实资料门禁 | `results/replay_gate.csv`、`results/replay_summary.json` | 33行=27 unknown不放行+6事后标签引用排除；没有预测性能含义 |
| 延迟假设情景 | `results/replay_delay_scenarios.csv` | 72行，54通过时间门禁、18排除；0/3/6/9h均为假设，不是已核验延迟 |
| 合成机械检查 | `results/synthetic_checks.json` | 20/20通过，包含未来起报、可用早于起报、未知时效、负/零提前量、重复/漏报/模糊真值；不增加真实事件分母 |
| 时钟示意图 | `figures/clock_audit.png` | 预报累计窗口与候选阶段分层展示；最新PNG已目视检查，记录绑定图哈希 |
| 来源与阅读范围 | `results/source_register.json`、`results/source_reading.json` | 新存4个官方/作者方法与产品说明快照共1,407,958字节；JMS相关正文核查；殷文未升级为全文 |
| 独立审查处理 | `results/review_resolution.json` | 起报门禁、误报定义、零提前量汇总、固定alpha配置一致性及最终清单范围均已处理 |
| 公共修订提案 | `PROPOSALS.md` | 6项提案待主参谋审查，未修改公共口径或台账 |

**零接受数表示当前审核状态，不表示没有历史灾害。** 事后可靠标签可用于回顾评价；需要防止的是它进入预报信息集，以及把同链/校准资料再充作独立验证。

## 3. 复跑

从本问worktree根目录执行，默认离线；不修改公共输入：

```bash
track_b/.venv/bin/python track_b/research/q3/scripts/audit_replay.py
track_b/.venv/bin/python track_b/research/q3/scripts/plot_clock_audit.py
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --question q3 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q3 --expected-base 1d64f91fe057075df7c9199b5c17c68839bc6153
track_b/.venv/bin/python track_b/research/q3/scripts/audit_replay.py --finalize-only
```

首次曾显式加`--fetch-sources`保存4个小快照；复跑不需要刷新。重绘后需重新目视核验`figures/visual_review.json`绑定的新图哈希；最终清单在所有文档/图表落盘后重建。`--finalize-only`逐项重新读取大小与SHA-256，不重跑数据实验。

## 4. 输入/输出版本与验证

| 文件 | SHA-256 |
|---|---|
| 共同输入清单 | `c520962ce8cc9e1b2a261b0ce289a19d657e8b392c3421b4b556f6569eaf5c97` |
| 本问直接输入清单 | `2e6c458d79584cb52cbfdc27f87b06efcb92c0b26a360c86f75278dba199917c` |
| 首轮机器摘要 | `a0d440a9f295e05753d7714665e0886346e4e9f8e3e23fd07510830a496e2e33` |
| 20项机械检查 | `432e311da88460e23a31a3fc8adf939b960ea5288b808bd099272665d6cffe37` |

全部最终产物的大小/SHA-256及逐项重读结果见`results/output_manifest.json`。范围包括本交接、协议/脚本/配置、全部结果、来源快照与图表。明确排除清单自身、易变安装日志/运行时就绪/派单文件和未变的TASK；其中运行时信息已另存不可变试验快照。排除项不是未检查科学输入，431共同输入仍由工作区验证器核对。

## 5. 最小交接字段与限制

- `input_version`绑定共同起点及清单哈希；`event_id/physical_phase/time_utc/time_uncertainty/space_object/variable_semantics/forecast_reference_time/issue_time/valid_time/available_time/data_role/evidence_status`使用规范字段。
- NASA目录epoch单列保留，未核实时区的`time_utc`为null；未审核候选独立分组保持null，不将来源条目数当事件数。
- 实际覆盖率、误报占比、单位监测时间误报率、无事件机会误报率及点预测误差均null；本轮没有相应模型/独立标签/完整监测暴露。
- 精确现场源区、目标点、独立启动与到达原始观测、真实业务发布时效仍未解决；没有用25个气象格或滚动小时扩充事件数。
- 事后重建范围、目录90%误差、物理情景范围与未来95%预测区间均分开。

## 6. 联合审查所需交接

- 主参谋/队员：审视Q3-P01—P06，确认主预测对象、发布网格/时域、预警匹配/合并、标签审核与区间处理路线；未确认不推进正式拟合。
- Q1：需要变量/单位/累计边界、QC和unknown规则、回看窗/滞后、实际可用时间及筛选所用样本。
- Q2：需要触发对象、参数/条件来源、估计样本、单位/不确定性/适用域；回测前冻结版本，避免测试事件反向定阈值。
- Q4：需要源区、目标、CRS、路径和距离类型、传播/到达情景及校准证据；不以到达替代启动。
- 后续补证候选：一个USGS记录`us7000tc90`、一个优先历史原始来源、一个历史起报产品的实际可用性记录；本轮均未擅自算入独立验证。

队员人工核验与采用/修改仍待完成。首轮到此停在联合审查点。
