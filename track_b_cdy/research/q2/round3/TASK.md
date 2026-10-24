# Q2 第三轮任务：结构—温度—水的机制竞争与耦合

状态：已获用户实施授权的任务书；不代表已执行。本轮必须交机制计算、对照结果与证据，不以方法综述结束。

## 身份、授权与共同基线

- 唯一执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2`；分支 `codex/track-b-q2-r3`，不在父目录执行。
- 读 `track_b/docs/18_stage4_round3_workflow.md`、`track_b/config/stage4_round3_contract.json`、`track_b/docs/17_stage4_round2_review.md`、本问第二轮 `HANDOFF.md`；核对本轮 `workspace_binding.json` 中的精确基线、合同、清单和SHA-256，不借用旧轮绑定。
- 第三轮已授权直接本地完整模型研究；旧轮不装依赖/不做核心模型/单对影像/128MiB限制不延续。简化模型作为对照，热—水—结构耦合是正式竞争者，队员负责最终科学采用。
- Git新文件仅写 `track_b/research/q2/round3/`；公共资料与前两轮原字节保留，不运行会覆盖公共产物的阶段3管线。
- 保留本树原44包venv，标准五组验证用 `track_b/.venv/bin/python`；新依赖使用本问局部锁定环境，不修改原锁。不使用远程服务器。

## 输入、补证与分工

- 读NC原始属性与说明、`track_b/data/processed/spatial/source_manifest.json`、本问前两轮参数可辨识性与速度定义链，引用已核验残差而不静默改原v/vx/vy。
- NC冰川正mask是库存参数域，多年速度是背景统计；不能直接作真实释放边界或2026初始速度。两套DEM年代/基准未知项保留。
- Q1负责变量/QC与站点代表性，Q2负责机制/裂隙/冰岩界面/水路/温度/真实变形与SAR，Q3负责标签/波形/预报，Q4负责DEM/光学/河网/几何；下载前核对缓存，避免重复采集。
- 以[Mamot等原文](https://tc.copernicus.org/articles/12/3333/2018/tc-12-3333-2018.html)为强度关系核查入口，实际读公式、实验温度/应力/速率及外推限制，不能仅凭摘要采参数。
- 影像不限旧两景；获取能区分机制的公开前后SAR及实际像元，选择产品/时相/轨道与处理方法要有目标。GRD幅度、SLC相位、像元支持、配准、遮蔽/叠掩、变化解释分开验收。
- 大型数据只写 `/Users/maxchen/Documents/MathorCup/research_cache/round3/q2/`，按版本和哈希去重、追加后只读引用，不写他问缓存或runtime。Git仅保存来源索引、小样本、代码与配置；登记URL/DOI、获取UTC、实际读取范围/字节/哈希。认证失败停止该入口并找合法公开替代，不伪装登录或元数据为像元。
- 公共证据采用与跨问新文件经主参谋审查、按哈希发布副本；不要直接修改公共参数或读他问未冻结的活动文件。

## 计算计划

1. 标准启动验证后先登记 `EXPERIMENT_PROTOCOL.md`：共同几何/物源条件、参数范围依据、模型方程/状态、可检验预测、反证条件、比较指标及校准/验证分工。
2. 建立结构基础 S、结构＋温度 S+T、结构＋水 S+H、结构＋温度＋水 S+T+H 四组竞争；用相同可比输入、参数抽样和边界进行对照。
3. S包含结构面、岩桥、卸荷/损伤、蠕变与渐进破坏的候选表达；明确哪些由观测约束、哪些是假设、哪些参数无法区分。
4. T从地表能量/温度边界经热传导到冰岩界面温度、强度及损伤，计算深度、边界与热惯性的响应时间。不能把区域站温度直接等同深部界面温度。
5. H从降雨/融水经储排水、入渗与连通路径到孔压/有效应力，比较排水条件与延迟；明确水量输入、状态单位、出入流和阈值。
6. 联合模型通过有物理定义的状态/参数耦合，不只把两种评分相加。对每种深度、热边界、排水条件计算状态轨迹、稳定裕度及首次机械启动判据。
7. 对强度关系检查适用温度、有效应力、变形速率、材料与几何范围；超域计算保留外推标识及独立敏感性，不包装成校准关系。
8. 运行参数联合敏感性、结构/温度/水消融和参数补偿实验；给出可识别组合、条件临界关系与区分机制最有价值的观测。
9. 实测约束、外部迁移和条件情景分层计算。来源未知不停止所有模型；对该分支保留参数/初态范围，不能将情景结果称本事件已证触发因果。
10. 接收Q1因素/气象契约、Q4计算几何/地形以及Q3标签版本后，仅更新受影响的实验；初期用明确标注的几何/边界集合推进，不等待唯一模型。
11. 条件范围没有概率意义；若向Q3提供参数分布，要给先验依据、相关结构和版本，区分后验拟合与人为先验，并检查先验敏感性。

## 早交接口（优先于长篇报告）

- 先交 `INTERFACE_HANDOFF.md`、`results/mechanism_contract.json`：各机制ID、状态/单位、输入、状态转移/方程、启动判据、适用域及代码入口，便于Q3尽早接引擎。
- `results/parameter_ensemble.csv`：统一 `scenario_id`、参数版本、范围/分布/相关性、来源和证据层级；`results/state_trajectories.csv`：场景/机制/UTC时刻/状态/稳定裕度。
- `results/release_states.csv`：供Q4的源区/物源/体积或厚度/组分/初速集合、几何版本、来源与情景身份；未被实测约束的值明确为情景。
- 标准交接入口是 `exports/mechanism_bundle.json`、`exports/release_bundle.json`，遵守本轮contract的bundle字段/文件哈希要求及q2_state_exchange/q4_release_exchange。状态表稳定裕度正为稳定、零临界、负为越过判据，并写明量纲/归一方式；未过阈或缺测情景保留，不能筛掉以制造启动概率。
- 经主参谋哈希冻结和分发后再供他问使用。后续修订生成新版本，不原地改变已交接口字节。

## 最终交付与验收

- `MODEL_COMPARISON.md`、`EVIDENCE_REVIEW.md`、`PAPER_OUTLINE.md`：四组实际计算、响应时间/稳定裕度/临界关系、支持与反对证据、主方案与挑战方案及淘汰/暂存理由。
- `results/model_comparison.csv`、`sensitivity.csv`、`ablation.csv`、`identifiability.csv`；图放 `figures/` 并实际打开记录哈希；源/参数/物理量可追溯，不能只报一个最优参数。
- `scripts/`、`config/`、`REPRODUCE.md` 和局部环境锁实现本地复跑；登记来源、直接输入和输出manifest（不自包含，缓存哈希可解析）、`results/validation.json`、最终本轮 `HANDOFF.md`。
- 检查量纲、稳态/边界、热/水响应与适用域、收敛、参数补偿、消融可比性；实测/迁移/情景分别报告，校准资料不能再次记为独立验证。
- 交换记录统一模型/机制/实验/情景/几何/参数版本及事件/阶段/UTC/可用时间/角色/输入版本；源区启动与传播到达始终分开。
- 启动及收尾：`track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round3 --question q2 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q2 --expected-base <主参谋发布的第三轮共同基线>`。
- 只本问round3本地提交、不push；交提交、manifest、复跑命令与早交接口。软件或单项证据失败写明实际失败并继续其他竞争路线，不能以unknown或综述替代整轮计算。
