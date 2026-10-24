# 阶段 4 研究窗协作规则

本文件作用于 `track_b/research/`，继承 `track_b/AGENTS.md`。当前已授权四问分窗、独立 worktree、首轮方案论证及数据诊断／可行性技术试验；队员仍独立完成核心建模、算法设计、求解与最终科学判断。

## 第二轮当前派单（优先于下方首轮快照）

用户已确认实施有界补证与背景分析，研究目标/范围见`track_b/docs/16_stage4_round2_workflow.md`和`track_b/config/stage4_round2_contract.json`。各窗恢复本问`round2/TASK.md`及`round2/HANDOFF.md`，只写本问`round2/`；原有首轮文件、报告、清单保持不变。当前基线/分支/目录以最新派单与本轮绑定文件为准，不能从首轮绑定推断。

使用原工作树自己的venv，不重建/安装；运行标准检查时加`--round round2`。公共清单改用`audit/stage4/round2/baseline_manifest.json`，机器字段继承原契约，本轮主预测对象为源区首次机械启动（非已接受精确真值）。Q4先交search_only AOI，主参谋审核并哈希绑定后交Q2。补证得可采用/排除/未知及依据均可结束，不无限扩扫、不自动升级质量/标签/几何。本轮到第二轮联合审查点停止。

## 恢复与基线

1. 阅读 `track_b/STATUS.md`、`track_b/docs/13_stage3_handoff.md`。
2. 阅读主参谋发布的 `track_b/docs/14_stage4_workflow.md`、`track_b/audit/stage4/baseline_manifest.json`，核对本窗基线提交、版本与输入哈希。文件缺失或基线未绑定时，先记录并向主参谋提交问题，不能自行填写不存在的哈希。
3. 阅读本问 `TASK.md`、已有 `HANDOFF.md`；只接续未完成事项，不把模板或他窗进展当作本窗已完成工作。
4. 使用本 worktree 的 `track_b/.venv/bin/python`；环境应由主参谋按锁文件重建并发布核验记录。虚拟环境未就绪时先做只读文档核验；不复用其他 worktree 环境后声称本窗环境已验收。

## 文件所有权

- Q1 只写 `track_b/research/q1/`；Q2 只写 `track_b/research/q2/`；Q3 只写 `track_b/research/q3/`；Q4 只写 `track_b/research/q4/`。
- 本问脚本放 `scripts/`，试验配置放 `config/`，数据／表格放 `results/`，图片放 `figures/`，补充来源快照放 `sources/`。创建必要目录即可，空目录不算交付。
- 研究窗不改原始资料、公共 `data/`、`scripts/`、`config/`、依赖锁、总状态、决策或公共来源／事件台账，也不直接改他问文件。不要在公共目录重跑会覆盖阶段 3 产物的脚本。
- 任何补充下载限定本问 `sources/`，先限定所需条目／时段和体量，记录官方 URL、检索时刻、获取状态及 SHA-256。认证失败留痕；不把登录 HTML 或场景元数据当作影像像元。需新增依赖时先提案，不能自行改公共锁或全局环境。
- 所有公共口径、标签接受、共享数据更新和跨问引用版本，由主参谋审查后集成。候选记录可以写在本问提案文件，不能直接宣布为全项目新事实。

## 首轮工作与暂停点

- 先核验输入、科学对象、候选方法比较，再做本问任务书许可的数据诊断或小型技术试验。
- 不以通路运行成功替代科学验证。未审核事件不能构造真值；人工情景与合成样例不能补充独立事件数或覆盖率分母。
- 需要队员选定核心模型、作机制判断、选择最终阈值／TOP5／区间方法／动力学参数时，交付证据与方案比较，标为“待队员决定”，不要代为完成核心分析。
- 资料不足时交付可复查失败或缺口、影响和下一动作；已经得到的诊断仍应落盘。
- 首轮结束更新本问 `HANDOFF.md`，停止于联合审查。后续正式基线任务由主参谋在联合审查后发布。

## 最小交接合同

机器记录以 `track_b/config/stage4_contract.json` 为规范。本目录任务书／模板中的简写仅为显示别名：`phase`→`physical_phase`，`time`→`time_utc`，`space_id+crs`→`space_object`（含 CRS、分辨率和位置误差），`units+qc_policy`→`variable_semantics`。落盘机器记录使用规范名，并记录 `event_id`、`time_uncertainty`、`available_time`、`forecast_reference_time`、`issue_time`、`valid_time`、`data_role`、`input_version`、`evidence_status`；不因别名创建第二套数据口径。`input_version` 绑定共同基线提交与 manifest SHA-256，较新获准证据单独版本化。

下列信息出现在每一份结果索引或交接表中；不适用写明原因，未知用 `null` 并说明，不能编造值：

| 字段 | 含义 |
|---|---|
| `event_id` | 灾害链唯一标识；同链不同阶段、不同点位或多个来源不能复制成独立事件 |
| `phase` | `background`、`initiation`、`debris_onset`、`propagation`、`arrival` 等明确对象；候选定义标明待确认 |
| `time` / `time_uncertainty` | 带时区时刻或区间、原始写法、误差及代理关系；计算交换用 UTC，事件叙述可用 UTC+8 |
| `space_id` / `crs` | 可追溯空间对象、坐标系、距离定义和定位误差；源区／流路／目标点须分别标识 |
| `units` / `qc_policy` | 原单位与转换、观测高度／深度、质量规则、缺测处理及接受样本数 |
| `available_time` / `issue_time` | 真正可获得时刻和模拟发布时刻；天气预报另留起报／有效／累计时段；未知不视为满足历史实时可用条件 |
| `data_role` | `exploration`、`calibration`、`validation`、`scenario`；同一证据用于校准后不再作为独立验证 |
| `baseline_commit` / `input_version` / `sha256` | 主参谋共同基线、输入路径／来源版本、读取文件哈希；输出单独登记哈希 |

每窗还需保留运行命令、代码／配置版本、运行时环境、实际执行与未执行项、来源实际阅读范围、人工采用／修改状态。公共原始时区、单位、QC、垂直基准和业务时效的待核实项保持可见。

## 调度与消息

用户已授权主参谋向四个可见研究聊天派发任务并收集交接。研究窗通过本问 `HANDOFF.md` 及提案文件落盘，主参谋读取、集成和分发；研究窗无需主动给其他聊天发送消息，也不自行创建聊天／worktree／自动化。

当前首轮各问共同缺口负责人：Q1 变量语义／质量，Q2 机制／遥感证据，Q3 事件标签／预报时效，Q4 空间几何／地形。负责人负责提出有证据的更新，公共采用权属于主参谋集成与队员科学确认。
