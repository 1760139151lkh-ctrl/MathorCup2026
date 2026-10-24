# Q3 第二轮任务：单事件审核与一个起报的可用证据

状态：本轮有界审核已执行，结果及实际验收见 `HANDOFF.md`；本文件保留派单范围。日期：2026-10-24（America/New_York）。

## 身份与恢复

- 唯一执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3`；新分支 `codex/track-b-q3-r2`。
- 阅读 `track_b/docs/16_stage4_round2_workflow.md`、`track_b/docs/15_stage4_round1_review.md`、本问首轮 `HANDOFF.md` 与 `PROPOSALS.md`。
- 本轮合同 `track_b/config/stage4_round2_contract.json`；清单 `track_b/audit/stage4/round2/baseline_manifest.json`。
- 精确基线提交/清单 SHA-256 以主参谋新派单为准；记录绑定后再作工作区验收，不借用首轮提交。
- 复用本工作树已有 `track_b/.venv/bin/python`；只写 `track_b/research/q3/round2/`。
- 不拟合预报模型、不生成真实95%区间/覆盖率、不将目录条数当独立事件数。

## 研究对象与已核对存在的输入

- 主对象已确认为**源区首次机械启动**；精确时刻仍待审核，题面参考/目录代理/下游到达分别保存。
- `track_b/data/external/event_remote/event_evidence_ledger.json`、`historical_candidates.json`。
- `track_b/research/q3/results/label_review.csv`、`label_summary.json`、`availability_review.csv`、`forecast_metadata_checks.json`。
- `track_b/research/q3/EVALUATION_PROTOCOL.md`、`EVIDENCE_REVIEW.md`、`results/source_register.json`、`results/source_reading.json`。
- `track_b/data/external/event_remote/runs/20261024T034202Z/raw/usgs_event.json`、`usgs_origin_quakeml.xml`：已有事件证据，不预设就是本轮待查记录。
- `track_b/audit/forecast_probe/summary.json`、`track_b/data/external/forecast_sample/gfs_2026082518_f009.idx` 与六个 `.http.json` 访问记录。
- `track_b/data/processed/forecast_sample/summary.json`、`gfs_2026082518_f009_aoi.nc`：起报/有效/累计边界已有核验，不必重跑 GRIB 处理。
- `track_b/research/q3/sources/ncep_current_production.html`、`ncep_gfs_inventory.html`：已存当前说明不能自动证明历史首次可用。

## 执行步骤 A：只审核 us7000tc90

1. 核对工作根、分支、新基线和环境；保存启动工作区验证，新增直接输入单独登记哈希。
2. 定向访问 USGS 官方记录 `us7000tc90`，取得小体量详情与必要 origin/机制说明；记录 URL、获取 UTC、产品版本/更新时间和实际阅读范围。
3. 核对 ID、event type、origin UTC、原误差定义/置信水平、定位及说明；缺少字段保持 null，不把更新时间当发生时刻。
4. 判断“独立灾害/同链后续阶段/机制不同/无法判断”，逐项引用原始依据，区分目录类型与真正物理机制。
5. 同已有 2026-08-26 灾害链比对时间、位置、原叙述与来源；独立性未知时保留分组未知，不强行新增独立事件。
6. 建立首次机械启动映射：该记录直接观测、代理还是不对应；仅有目录时刻不能自动接受为机械启动真值。
7. 将原误差、未量化代理偏差、不同阶段时间分列；不把90%目录误差拼成95%未来区间，也不将两时刻差随意解释为真值范围。
8. 输出训练/独立验证采用**提案**及门槛；当前0接受数不会因访问成功自动增加，公共标签由主参谋审查更新。

## 执行步骤 B：固定 GFS 起报 f009

9. 只追溯 `2026-08-25T18:00:00Z`、`gfs.t18z.pgrb2.0p25.f009`；先读已存 HTTP 记录和官方归档入口，限定历史可用证据问题。
10. 区分起报、有效、累计起止、归档对象写入/修改、业务发布、检索时刻和研究中模拟发布；不要复算已核验六条 GRIB。
11. 寻找该历史对象可追溯的官方发布/完成/归档记录，记录当前可读内容与能支持的最强结论；一般生产计划不等于该次实际发布。
12. Last-Modified 等仅在可证明对应关系和版本稳定性时作有限界约束；未证明首次可用时 `available_time=null`，说明可得的上下界或缺口。
13. 不下载新 GRIB、不扩大起报/时次、不扩扫54事件目录；认证/缺档/证据不足均留痕后结束。
14. 更新信息截止及主目标的路线建议：继续允许无泄漏协议/门禁设计，不以延迟假设替代真实业务可用证据。

## 本轮交付（均位于 round2）

- `EVENT_REVIEW.md`、`results/us7000tc90_review.json`：一条完整事件审核卡、同链关系和采用建议。
- `results/mechanical_initiation_mapping.csv`：直接/代理/不对应/未知、时间及位置误差、与本轮主对象的关系。
- `AVAILABILITY_REVIEW.md`、`results/gfs_f009_availability_chain.json`：一个起报对象的证据链、首次可用状态和未解项。
- `ROUTE_UPDATE.md`：可继续的方法论工作、正式拟合/区间验证阻断项、需要谁补证。
- `sources/` 保存有界官方响应与日志；`results/source_register.json` 列 URL、版本、UTC、阅读范围、哈希。
- 必要新增脚本放 `round2/scripts/`；`results/input_manifest.json`、`output_manifest.json` 不包含自身；最终更新本轮 `HANDOFF.md`。

## 验收与交接

- 事件 ID、物理阶段、同链/独立性和原误差有来源；未知不得放行，事后标签与预报信息集角色分开。
- 预报可用链明确“证明了什么/没有证明什么”；当前下载成功和发布时间计划均不能冒充历史首次可用。
- 规范字段保留 `physical_phase/time_utc/time_uncertainty/available_time/forecast_reference_time/issue_time/valid_time/data_role/input_version/evidence_status`。
- 不增加合成事件或滚动小时作为独立样本；不重跑首轮72条延迟情景和20项机械测试，除非新证据影响相关代码。
- 启动和结束运行：`track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q3 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q3 --expected-base <主参谋发布的本轮基线提交>`。
- 得到可采用/可排除/仍未知及依据即交付；仅本轮本地提交、不 push、不联系作者/注册/付费，停于联合审查。
