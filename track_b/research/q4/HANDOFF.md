# Q4 首轮交接：空间可行性与通用数值环境

日期：2026-10-24（America/New_York）。状态：首轮方案比较、证据表、地形诊断及合成数值/I-O小实验已完成，交主参谋联合审查；未选择或求解正式灾害模型。

## 执行与版本

- 唯一执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4`；分支`codex/track-b-q4-r1`。
- 聊天`01a16c21-82cb-7f80-8b44-204ba9b8cc04`仍关联父目录；文件隔离来自真实 Git worktree 与显式执行路径，非应用原生 worktree 绑定。
- 共同起点：`1d64f91fe057075df7c9199b5c17c68839bc6153`。冻结清单及SHA-256见`results/result_index.json`，该索引也绑定全部科学产物和规范交接字段。
- 主参谋明确通知环境正式就绪后才运行实验。解释器为本 worktree 的`track_b/.venv/bin/python`，Python3.12.14、44包精确锁。
- 本轮仅本问目录本地提交，不push；确切提交hash由最终聊天回复与Git日志给出，避免文档自引用提交hash。

## 成果入口

| 内容 | 入口 | 可支持的结论 |
|---|---|---|
| 结果与边界 | `RESULTS.md` | 本地地形支持、差值、重采样敏感性与通用技术试验 |
| 模型层级与原始来源 | `METHOD_OPTIONS.md`、`sources/model_sources.json` | 一维、二维深度平均及多相/孔压候选的资料门槛；核心选择待队员 |
| 空间对象/描述符 | `results/geometry_evidence.csv` | 定性来源、库存掩膜、代理位置和真实几何的状态分开 |
| 初边值/参数证据 | `results/parameter_evidence.csv` | 缺失与事后候选约束清楚，不用默认参数充当实测 |
| 地形实测诊断 | `results/terrain_feasibility.json`、`figures/terrain_feasibility.png` | 同格支持和两产品差异；不证明源至口岸连续 |
| 合成数值/I-O | `results/synthetic_numerics.json`、`results/synthetic_grid_checks.csv`、`results/synthetic_advection_frames.nc`、`figures/synthetic_numerics.png` | 标量积分、非负、细化、精确移位与帧读回；不认证灾害模型 |
| 可复跑脚本/配置 | `scripts/run_feasibility.py`、`config/feasibility.json` | 所有写入限制本问，公共输入不变 |
| 提案与交接需求 | `PROPOSALS.md` | 几何、地形、物源与校准/独立验证对象需进一步闭环 |
| 统一机器索引 | `results/result_index.json` | 各产物路径、字节数、SHA-256、版本与规范字段 |

## 核心发现与未解决事项

1. NC 参数网格20,010格及正mask7,152格均有独立 DEM 支持；正mask面积6.4368 km²属于库存参数域，不是实际失稳面。
2. 正mask内独立DEM减NC DEM均值−30.7407 m、RMSE33.7224 m、范围−80.4927至109.3730 m。未确认产品年代/垂直基准，未拼接、纠偏或解释为事件变化。
3. 同一独立 DEM nearest减已有bilinear，正mask内RMSE5.3882 m、范围−29.9194至33.8291 m。这是重采样敏感性，不是地形误差界或校正量。
4. 真实源区、口岸保护点和独立沟道几何仍未核定，完整走廊与实际路径距离保持null/未验收；没有据目录代理点、地名或文献长度生成实际路径。
5. 合成平流100/200/400格的相对L1误差为0.1319923/0.0703073/0.0364095，标量积分相对漂移≤3.8×10⁻¹⁶；非负、Courant=1精确移位、非法Courant拒绝、NetCDF三帧读回检查通过。所有速度/时间/距离为合成测试值。
6. 九条方法原始/官方来源按实际阅读范围登记；论文数字仅候选，不自动成为初值或独立验证。
7. 主参谋审查后交接Q2发现：NC的v与hypot(vx,vy)逐格不完全相等，最大残差约0.494655 m/year，原因待核实。本窗未独立复算此项，未重算/替换v；单列为跨问待核实证据，精确数和来源追溯由Q2继续交接。

## 规范交接语义

`event_id=B20260826_Chhochen`；`physical_phase=propagation_feasibility_only`。`time_utc/time_uncertainty/available_time/forecast_reference_time/issue_time/valid_time=null`，因为本轮没有事件到达输出或历史业务时效声明。`space_object`保留EPSG:32645技术网格，实际source/channel/target均null。`variable_semantics`明确高程米制但垂直基准未知；合成量纲和坐标单列。真实诊断`data_role=exploration`；合成测试`data_role=scenario, synthetic=true`，不计独立事件数。

各产物具体语义、输入版本/哈希及未知原因见机器索引，CSV表按行保留来源/可辨识性，不由公共字段覆盖其不确定状态。

## 复跑命令与检查

在上述唯一执行根运行：

```bash
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --question q4 --expected-root '/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4' --expected-base 1d64f91fe057075df7c9199b5c17c68839bc6153
track_b/.venv/bin/python track_b/research/q4/scripts/run_feasibility.py
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --question q4 --expected-root '/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4' --expected-base 1d64f91fe057075df7c9199b5c17c68839bc6153
```

实验前工作区五组检查通过。实验后检查结果以本问`workspace_verification.json`为准；图像已实际打开检查，哈希绑定在`results/visual_review.json`。重跑会改变运行耗时/时间戳和机器报告哈希，需要刷新结果索引及图像检查记录，不能沿用旧清单。

首次运行的NoData元数据NaN序列化问题已修复并完整重跑，失败与修复记录见`results/execution_notes.json`。数值、物理、事件验证分层记录；目前只有通用技术检查通过，未做实际灾害校准或独立事件验证。内部代理静态/来源审查不等于队员人工验收。

## 交主参谋分发的需求

- 给Q2：请求可追溯源区/夹带冰舌影像及物源、水量、组分候选，注明误差与证据等级；本问交付地形/几何缺口和参数可辨识性。
- 给Q3：请求分阶段时钟及独立到达观测。Q4首轮没有事件到达时间、真实预警距离或95%覆盖输出。
- 主参谋/队员：联合审查保护对象、公共几何版本、地形来源与正式物理路线。下一轮任务由主参谋发布，本窗停在首轮交接点。
