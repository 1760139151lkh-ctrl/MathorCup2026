# Q2 首轮交接：参数可辨识性与遥感可行性

日期：2026-10-24（America/New_York）。**首轮已完成，停在联合审查点。** 未选择正式核心模型，未估计临界阈值，未接受新训练标签，未生成2026失稳面或变化解译。

## 基线与实际运行

- 执行根：/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2；分支：codex/track-b-q2-r1。
- 聊天：01a16c20-e7a7-77b1-86c5-8831d1a6a8a2；应用关联父目录，由workspace_binding.json显式绑定独立Git worktree。
- 共同起点：1d64f91fe057075df7c9199b5c17c68839bc6153；准备提交：1a31c6f2c3e11fcc32ac870b7a5896a7ef67f06e。
- results/input_manifest.json记录16个直接数据／语义输入及代码配置哈希；431个共同冻结输入由标准验证器覆盖。
- 主参谋验收独立Python3.12.14、44发行包精确锁后才运行数值实验；本窗再次运行5组标准检查，见workspace_verification.json。
- 核心建模与最终科学采用仍由队员独立完成。内部代理证据／计算复查不是人类验收。

从执行根运行：

    track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --question q2 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q2 --expected-base 1d64f91fe057075df7c9199b5c17c68839bc6153
    track_b/.venv/bin/python track_b/research/q2/scripts/diagnose_inputs.py

程序离线读取共享输入，只写本问结果；配置为config/diagnostic.json，无插补、源区体积推算或阈值拟合。最终版本同版本再执行一次，6个确定性表／清单字节哈希一致，科学摘要除执行时间外一致，见results/reproducibility.json。复跑会更新执行时间戳，需要刷新交付哈希清单。

## 交付入口

| 文件 | 实际内容与结果 |
|---|---|
| METHOD_OPTIONS.md | 经验条件、物理启发稳定性、文献条件情景三路线的证据需求、可执行部分和退出门槛 |
| results/parameter_evidence.csv | 26项：9个网格背景字段、12个事件参数缺口、5项代理／分类／遥感／阈值能力；事件参数值保持空缺，每项有下一动作 |
| results/nc_parameter_support.csv | 9字段在7152格参数域的有限值／范围诊断；非物理质量或2026状态验收 |
| results/remote_feasibility.csv | 41景逐景足迹、时钟、轨道、云量及实际获取状态；35景覆盖全部NC正mask格心、6景部分支持 |
| results/s1_pair_screen.json | 最近前后S1轨道不一致；3个轨道组各选一对兼容候选，间隔约12天，像元／配准均未验收 |
| results/window_support.csv | 8变量×24/72/168小时的24行覆盖诊断；固定题面候选时钟，未挑选最优窗口 |
| results/input_check.json | 6项技术诊断检查通过；速度恒等关系标为未确认，不属于科学模型验收 |
| results/input_manifest.json、results/output_manifest.json | 输入、代码配置、交付文件的大小与SHA-256；输出清单排除自身和HANDOFF以避免循环自引，交接正文由Git提交绑定 |
| sources/MECHANISM_EVIDENCE.md、两份reading JSON | 8条原始研究机制／方法论述、3份官方产品说明；实际阅读范围、快照与失败状态分列 |
| PROPOSALS.md | 8项待审提案，含速度处理链追溯及Q4参数使用限制 |
| results/INDEPENDENT_REVIEW.md | 内部代理直接读回NC与逐点足迹的独立技术复查；本轮未新制图，无图像视觉验收 |

## 关键发现与边界

1. **背景不等于事件状态。** NC为138×145、30m参数网格；正mask7152格、6.4368km²，无time维。历史厚度和2014—2024气候态速度不能直接作为本次释放厚度、初速度或加速。真实失稳面仍未知。
2. **速度表达存在待解释差异。** 对存储float32值作float64运算，abs(v-hypot(vx,vy))最大0.4946554486m/year，中位数0.0244700533，p95为0.1670116623；7142/7152格超过算术筛查容差1e-4m/year。这不是触发阈值；原值全部保留。插值顺序、先合成后平均等只是候选解释，未断定成因。
3. **对Q4的影响与最小动作。** 不可将给定v与重算模长静默互换，不可据差异判定加速，也不可把历史气候态设为本次释放初速度。先取得NC生成脚本／原ITS_LIVE格点，核对统计定义、拟合时段及重采样顺序，再决定背景变量如何使用；公共采用由主参谋发布。
4. **地形与分类只支持背景。** 两DEM在参数域差值均值约-30.7407m，范围-80.4927至109.3730m，基准／年代未解释。WorldCover2021背景nearest对齐后7152格有类别，不证明2026状态。
5. **足迹与像元分开。** S2有1景、Landsat有5景仅覆盖部分NC正mask格心。当前S1为GRD，不含干涉相位。既有S2 401／Landsat登录HTML失败证据仍保留；本轮没有取得新2026影像像元、验证AOI清晰率或执行SAR处理。
6. **区域代理不能替代源区水热。** 按待核实站点元数据，至NC正mask格心经纬度均值参考点约67.77km，不是至真实源区的实测距离。GFS仅5×5、0.25°，历史业务可用时刻未知。
7. **数值支持与质量分开。** 固定窗口降水有数值但无QC；FLUX的LE/H在24/72小时完整、168小时各167个数值，严格QC视图均不接受unknown。严格视图0条不等于原始观测全缺失，也不能直接当合格源区数据。
8. **标签不足以验证经验阈值。** 9行本事件证据只有1灾害链、0个已批准独立事件。没有将文献重建或合成样例计入训练／验证。

## 统一交接与下一动作

机器字段采用physical_phase/time_utc/space_object/variable_semantics/available_time/forecast_reference_time/issue_time/valid_time/data_role/input_version/evidence_status等规范名，主角色为exploration。未知时效、误差与源区保持null或显式未核实。STAC的published/created没有自动当作available_time。

本轮核读两篇事件原站完整摘要、Hock与Berti相关正文段落，没有声称本轮完成JMS校样方法推导重读。JMS/Yin与3份产品文档保存了有界HTML；Hock原始HTML超过1MiB上限、Berti直接保存返回403，未伪写来源哈希；网页工具实际可读范围另行登记。没有联系作者、注册账户或付费。

联合审查优先事项：Q4源区／接触面与DEM版本；Q1变量质量和累计时段；Q3同机制标签、对照与历史时效。Q2牵头结构／水热证据及最少必要遥感补齐。队员确认研究对象和核心路线后，由主参谋派发正式基线任务；本窗停在此检查点。
