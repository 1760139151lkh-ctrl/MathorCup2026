# Q1 首轮交接：已完成，等待联合审查

日期：2026-10-24（America/New_York）。真实数据诊断、描述图、候选方案比较和有界来源核查已完成；无最终TOP5、核心关联估计、显著性或灾害预报模型。队员人工采用/修改尚未完成。

## 1. 执行身份与输入版本

- 聊天：01a16c20-9e9f-7a93-b025-2e8a46f905d3，名称“赛道B · Q1 气象特征与关联因素”。
- 唯一执行根：/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1；分支：codex/track-b-q1-r1。
- 共同起点：1d64f91fe057075df7c9199b5c17c68839bc6153；准备提交：1a31c6f2c3e11fcc32ac870b7a5896a7ef67f06e。
- 冻结清单 track_b/audit/stage4/baseline_manifest.json，SHA-256 c520962ce8cc9e1b2a261b0ce289a19d657e8b392c3421b4b556f6569eaf5c97，共431文件。
- 本窗Python3.12.14、44包精确锁、pip check与六真实格式已由主参谋明确通知passed；实验前后用同一验证器。运行绑定和检查见 workspace_binding.json、workspace_verification.json。
- 最终提交hash由本窗最终回复和 git log -1 给出，避免提交内容自引用。未push。

## 2. 成果索引与关键发现

入口：[结果解释](FINDINGS.md)、[方法比较](METHOD_OPTIONS.md)、[公共提案](PROPOSALS.md)。稳定交付哈希见 results/output_manifest.json，覆盖文档、代码、配置、全部结果、图像和有界来源；明确排除自身、运行绑定/验证快照和易变日志。

| 产物 | 实际完成内容 |
|---|---|
| results/input_check.json、context.json | 输入哈希和规范机器上下文；技术可用、部分语义核实和结论适用范围分开 |
| variable_semantics.csv、quality_accounting.csv、coverage_by_year.csv | 63字段四类语义和账目；2,769,457数值在场、1,712,112原QC0；26 unknown变量未新增接受 |
| diagnostics_unknown_qc.csv、constant_run_candidates.csv、jump_candidates.csv | 分布、常值/突跳候选及原文件行号；不删值、不补QC |
| window_descriptives.csv、candidate_feature_coverage.csv | 2参考×3窗长×6年，2268变量窗记录、288候选覆盖记录，无筛选/排名 |
| historical_envelope_counts.csv、两张figures/*.png | 历年覆盖和固定168h描述；LE每偏移点只有2—4个背景年，其余五个展示量为5年；图经实际打开检查并绑定SHA |
| candidate_definition_consistency.csv | PA/Pressure和三组VPD候选定义的共同在场/残差检查，不是灾害关联或仪器质量认证 |
| remote_flux_comparison.json、remote_flux_column_comparison.csv、remote_flux_candidate_qc_tokens.csv | 8760标签25列比对及QC原token；远端与本地非严格同版，不迁移任何QC |
| sources/及READING.md | 一个2.23MB远端FLUX2026样本、元数据响应、TPDC前端壳和实际访问/哈希；不冒充详情全文核验 |
| diagnostic_summary.json、independent_review.json、figures/visual_review.json | 程序检查、独立AI只读复核、图像检查，均不冒充人工验收 |

结果表未带目录前缀时均位于 results/。

优先审查：FLUX__amb_e_sat连续4317标签保持1.776582，定位2022原CSV第4751行—2023第307行；原因未知，原值保留。降水209段≥24标签常值均为零，不能因此删除正常干期。

题面10:30与USGS代理10:52:10在24/72/168h选取同一小时标签集合，不能声称已验证分钟级时刻敏感性。168h实际为8月19日11:00—8月26日10:00（源钟UTC+8假设）。

新增远端与本地8760标签相同，但各列本地独有在场578—586、远端独有0，共同数值最高绝对差4.428×10⁻⁸，差异原因未定。固定168h的LE/H/TAU为本地167、远端153；FC_mass为166/153。四远端QC词法均1—9及NaN、无0，含MET政策没有的3/5/6/7，不能套用MET释义、不能直接迁移公共QC0。

## 3. 实际复跑命令

先进入上述唯一执行根。以下两个实验最终均已实际执行退出0，不运行会修改公共审计的阶段3脚本：

```bash
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --question q1 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q1 --expected-base 1d64f91fe057075df7c9199b5c17c68839bc6153
track_b/.venv/bin/python -W error::DeprecationWarning track_b/research/q1/scripts/round1_diagnostics.py
track_b/.venv/bin/python track_b/research/q1/scripts/compare_remote_flux.py
```

首次运行发现pandas/NumPy的Timedelta关键字构造弃用警告，已改显式unit=h，配置和窗口不变，以弃用警告升级错误方式成功复跑。运行输出保存在 round1_run.log、remote_comparison_run.log（日志不纳入稳定交付清单）。

重绘后实际打开两图并刷新 figures/visual_review.json；报告完成后重建完整稳定清单：

```bash
track_b/.venv/bin/python track_b/research/q1/scripts/finalize_output_manifest.py
track_b/.venv/bin/python track_b/research/q1/scripts/finalize_output_manifest.py --verify-only
```

单独重跑主诊断会生成初始产物清单，必须在远端比较、文档、图像核查完成后运行finalize，避免漏列新增产物。只校验已有交付使用 --verify-only，不重写清单。

## 4. 规范交接字段

规范以 track_b/config/stage4_contract.json 为准；共同上下文为 results/context.json，逐变量/锚点补充在配置、变量表和summary。

- input_version：共同提交和manifest SHA；新增源文件另绑URL、抓取时刻与SHA。
- event_id：B20260826_Chhochen；同灾害链不复制，历史背景不称确认无灾害。
- physical_phase：区域背景诊断；题面未指定阶段和USGS目录代理分列。
- time_utc：题面候选2026-08-26T02:30:00Z，目录代理2026-08-26T02:52:10Z；time_uncertainty：目录7.9秒/90%目录误差，非95%未来预测区间，其余未知。
- space_object：Gyirong区域背景站，EPSG:4326，85.29E/28.86N为同名元数据声明；源区/目标几何未核实。
- variable_semantics：原表头单位、原QC0或unknown诊断；小时积分/FLUX处理未知。
- available_time、forecast_reference_time、issue_time、valid_time：均null；本轮回溯诊断不主张历史业务可用。
- data_role：exploration；evidence_status：本地计数local_fact、候选规则candidate、来源声明external_source，保留实际阅读范围。

## 5. 验证、限制和下一动作

- 首末工作区5组检查：共同起点、431输入、独立环境、六格式、文件责任；见workspace_verification.json。稳定manifest另逐项核对大小/哈希和漏列。
- 主实验9项检查通过：行列与索引、逐单元原QC0/strict、窗口数量、输入不变、不新增QC接受等。
- 独立AI只读复核原Parquet和两份原CSV，确认关键计数、两锚点同集合、降水常值、远端差异及原QC token；审查SHA在independent_review.json。原数据真实性、仪器处理与官方QC手册未认证。
- 两图已实际目视并绑定哈希，队员人工验收未发生。
- 给Q2/Q3：候选因素族/冗余组、质量/覆盖、固定标签窗与来源差异，经主参谋审查后分发；Q2不受候选TOP5限制。
- 需Q3：物理阶段、标签误差、历史信息截止；需Q4：站点/源区/目标几何与代表性。当前未接收对方最终成果。
- 仍未闭环：小时时段、UTC+8全版本等价、FLUX高度/坐标/方向/订正、县日语义、源区代表性、独立标签、available_time。
- 下一动作：主参谋审查公共提案，队员确认核心关联目标、对照、质量与稳定性协议，再另行派发正式分析。本窗停在首轮联合审查点。

本轮代码、配置、图文和来源检索由OpenAI Codex辅助；精确模型标识未作为可审计运行事实提供。辅助代理为AI交叉检查；队员最终采用/修改及披露由主参谋汇入公共记录后补齐。
