# Q3 R3 增量交接：固定风险集与映射传播包 v2

本增量接在原三引擎研究提交 `bb9258d791a6e9735c28528ff4408c7434c3d149` 和适用性补包提交 `e54f0596ceb847c71afd628b9c16524e0b6774a5` 后。只重新汇总已计算的参数路径、审核交付文件及真实保存场，不重新运行物理求解器。旧研究包、早期事件接口及适用性 v1 的注册字节均保留；本目录根 `HANDOFF.md` 仍是原研究记录。

## 主要适用性对照已固定历史风险集

新增 `results/applicability_sensitivity/risk_set_revision/`。主策略为 `fixed_history_risk_out_of_domain_to_unknown`：保留原历史条件风险集、原先验权重及 `already_started_prior_mass`，只把风险集内越域的事件／不启动结局转为 unknown。原历史已启动质量转 unknown 严格为 0。

主策略实际有 **60,750 行**，与原分布逐键比较的风险质量及已启动质量差均严格为 0；与旧四策略合并后共 **303,750 行、五个明确策略**。旧策略中的历史分类撤销另命名为 `revoke_out_of_domain_history_classification_diagnostic`，保留作为附加诊断。它改变可能风险集，不能替代主对照。

主对照所有行均有正 unknown 质量，精确启动概率与条件时间区间全部为空；下界为 0，数值设计质量上界最小约 **0.488584**、最大 1。附加历史撤销诊断上界最小约 0.540984、最大 1。这些是给定设计与假设下的信息界，不能当作当地风险上界或安全结论。子集重归一后的零启动质量也不能说明安全。

10 项聚合检查、独立只读审计的 8 项边界检查与 38 项实际结果检查均通过。五策略表保留旧 243,000 行的共同 48 字段与空值结构；CSV 浮点往返最大差为 5.68e-14。旧源文件哈希不变。

原局限仍成立：342 个未来跨阈记录全部依赖同一物理设计 p0149-S，其有效正应力约 820.306718kPa，超出所用拟合准则 100–400kPa 的适用范围。完整试验曾覆盖 100–800kPa，不能把拟合域与完整试验域混称。温度在所登记拟合温域内。域比例依赖未来已算状态并包含跨阈后延续，属于回顾适用性诊断，不能作为已验证的业务筛选；固定历史分类也没有认证历史材料适用性。来源为 [Mamot et al., 2018](https://tc.copernicus.org/articles/12/3333/2018/)，本轮阅读范围与缓存字节仍以旧来源登记为准。

解释入口为 `APPLICABILITY_FIXED_RISK.md` 和新目录 `RESULTS.md`，机器接口为 `exports/applicability_bundle_v2.json`。旧 v1 保留计算史；其封包脚本因 macOS 大小写文件名冲突已退役，不能重跑。旧聚合校验已恢复原字节，历史综合元数据单独保留为 `PACKET_VALIDATION_V1.json`；新包使用不同单词的 `packet_validation.json`。

## Q4 compact 映射谱系通过，传播质量仍未通过

读取主参谋交付的 `inputs/q4/bundle_q4-r3-propagation-v2/bundle.json`，SHA256 为 `9fec7f2083ab43f81b19da2c1cca3cef9b2ad0b5db36441495162412d1e8dda4`。39 个明确文件角色全部逐字节核验；未读取活动 Q2/Q4 树。包内冻结原 compact release 表与已执行 case 允许核验真实映射，不要求不存在的别名文件。

两条物理运行、七个目标代表点共 **14 行谱系接入、0 拒配**。每条运行的 20 项共同物理参数保持，通过显式登记把原热模型换为 analytic-erfc 的新起始时刻；原概念源区、机制几何、compact 计算释放栅格及另一个 broad-source v2 几何始终分别记录。compact vector 与独立 mapping CSV 未交付，精确多边形仍未独立审计，实际 release 栅格支撑和体积已审核。

- p0000 的解析结果仍为 `no_cross_observed_complete`，其七行传播仅表示 **if released**，不制造触发时刻。
- p0036 使用实际解析 `point_crossing_linear_between_samples`，区间为 **2026-07-08 15:00–16:00 UTC**，线性插值为 15:34:17.258933921 UTC。这是回顾理想天气下的条件机械跨阈，不能当作八月实测事件或已验证业务预报。
- 保存场在预登记的 h≥0.1m、100m 代表点缓冲定义下，仅 p0036 的 paper junction 有一条原始命中，释放后保存帧区间 **(1360.5, 1380.1] 秒**。其余 13 行只表示保存输出未达阈，不证明连续时间未到达或安全。请求 1800 秒与实际末帧 1800.1／1801.7 秒分别保留。

两条运行均为 compact 源区欠分辨与质量预算未闭合：native 内部残差约 **+21.372917%／+12.716325%**，按实际 release 栅格调整的残差约 **+21.153363%／+12.613015%**。这两种表述不能平均或改称守恒。

因此有效到达包络行、合格到达区间、绝对到达时间与到达概率均为 **0 行／null**。机械启动至整体释放的延迟未知，未设为零。谱系与适配检查通过不升级物理质量。

另从已哈希实际保存场计算 h≥0.1／1／5m 的足迹与量距，不重跑仿真。请求期内 h≥0.1m 的面积为 p0000 **2.5704km²**、p0036 **4.3416km²**，距实际正释放栅格单元足迹的最大受影响单元中心距离约 **5601.73m／6669.59m**。使用全部保存帧则为 2.5956／4.3596km² 与 5645.26／6709.95m。60m 栅格的 8／16 个正释放单元超过精确 compact 部分单元边界，指标明确是栅格支撑距离，不是精确多边形滑程、验证预警有效距离或已验证危险区。

适配检查 **387／387** 通过，输入索引 50 条、输出索引 17 条逐字节复验，另经独立只读审查；这是数据与适配核验，不是预测质量通过。入口为 `results/arrival/propagation_v2/RESULTS.md`；机器接口为 `exports/propagation_join_bundle_v2.json`。旧泛化包 v1 的 42 行拒配结果保持原字节，不能用此次显式谱系适配覆盖旧记录。后续 fullmask 包另作增量。

## 复核、复跑与集成

综合接口 `exports/r3_followup_bundle_v2.json`，封包校验 `results/followup_v2/packet_validation.json`，输入／输出完整清单位于同目录。封包时核验原研究清单、适用性 v1 清单、39 个 Q4 文件、独立审计及实际打开后的图像哈希。标准五项工作区核验报告另存增量目录，原报告字节随即恢复。

在 Q3 worktree 的研究副本执行下列命令会重写增量输出，需重新审图与封包：

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 track_b/.venv/bin/python track_b/research/q3/round3/scripts/applicability_fixed_risk.py
track_b/.venv/bin/python track_b/research/q3/round3/scripts/plot_fixed_risk.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 track_b/.venv/bin/python track_b/research/q3/round3/scripts/join_propagation_v2.py
track_b/.venv/bin/python track_b/research/q3/round3/scripts/seal_followup_v2.py
```

本地独立 first-motion 真值事件仍为 **0**，独立训练／覆盖率验证事件没有增加，经验覆盖率仍为空。原三引擎的条件设计输出与外部终末破坏回放不能升级为当地已验证 95% 预报。依赖锁和环境不变，只作本地提交。
