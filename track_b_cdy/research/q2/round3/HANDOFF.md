# Q2第三轮交接：机制竞争、真实SAR与数值/组成挑战

日期：2026-10-24（America/New_York）。**本问完整工作包及主参谋追加的组分、定向数值、解析热挑战均已执行，交第三轮联合审查。** 已完成真实模型积分、竞争、补证、消融、联合敏感性、可辨识性、图表与复跑材料。所有源区机制/释放数值是条件情景；本地独立训练与验证事件仍0，最终科学采用待队员审视。

## 执行与基线

- 唯一根`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2`，分支`codex/track-b-q2-r3`。
- 共同基线`904d7257b899b9f71d1ac9e0eab7479e459eab52`，preparation `de790034cf302de58e69329dbe288aad269a359c`。
- 冻结清单`track_b/audit/stage4/round3/baseline_manifest.json`：725项，SHA-256 `fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`；旧轮原字节/原清单保留，共享helper按本轮新基线使用。
- 原Python3.12.14/44包环境及公共精确锁保持不变，无安装/升级/远程服务器。所有Git写入限本问round3；大原始SAR在本问q2缓存，Q4获批DEM缓存只读。
- 启动5组检查已保存到`results/startup_workspace_verification.json`，收尾同一round3命令5组通过，见`workspace_verification.json`。来源/输入/输出清单均不自包含；HANDOFF由Git提交绑定，避免循环哈希。

## 实际模型与核心结果

先登记`EXPERIMENT_PROTOCOL.md`，再计算同256个19维空间填充设计点、四机制S/ST/SH/STH、两暖端策略、2089小时。平面板法向厚度应力、岩桥/冰填节理强度、现象学损伤、1D导热、储排水/有效应力共享方程与参数。状态margin=(R−tau)/tau正为稳定；首行已不稳标左删失，未越阈/缺失分开。无先验权重，不以设计点比例作概率。

完成粗热网格v1与细热网格v2各2048情景；v2主热网格0.125m、状态/边界1h，内部CFL子步。随后完成同2048情景解析热挑战，注册传热域内推荐以解析热作温度数值参考，保留FD v1/v2对照。v2线性策略的后续越阈/初始左删失/未越阈计数分别为S 4/31/221、ST 28/31/197、SH 6/31/219、STH31/31/194；最小裕度中位约0.6901/0.4849/0.6623/0.4714；解析热各类别计数相同。这是给定范围的条件竞争，不确认本事件唯一原因。

已交临界水头可达性/负根/不可达根、45组热响应时标、三组消融、站源偏移±3°C、16系数角点（冻结状态）与联合设计敏感性。可辨识性数值基准：单裕度/同条件24复测/+T/+T+压力/+T+压力+理想D的秩1/1/2/3/4，显示强度—损伤—孔压补偿。没有把合成或重复小时当独立灾害事件。

细节见`MODEL_COMPARISON.md`、`EVIDENCE_REVIEW.md`、`PAPER_OUTLINE.md`与`results/`。建议论文主方法为四组共同参数竞争，STH统一引擎，ST/SH与暖端接触保持挑战；纯导热不覆盖水热平流/潜热/三维裂隙，损伤律不是当地实测蠕变应变律，真实卸荷时序没有实现。

## 必须一并采用的数值限制

14组独立方程/量纲/解析/守恒/删失检查通过；连续溢流解析误差<3.3e−14m，模型水预算约1.5e−14m。粗网格完整轨迹检查发现0.177最大裕度差，因此实际计算了独立细网格v2，没有静默覆盖旧状态。

v2预定8代表的64组0.125/0.0625m检查最大margin差0.01027、8有限时刻对最大0.25424h，但这没有代表全设计。随后实际完成全256参考检查：2048类别一致、137有限时刻对、248初始左删失、1663未越阈；**10/2048未通过0.02裕度目标，最大margin差0.178787，最大时刻差18.943779h**。暖端分支切换44小时。已另交前5不同敏感参数40条，24有限时刻对、16未越阈，含三网格原生小时/UTC跨越区间。

v1→v2虽类别未变，最大插值时刻移动46.819h。Q3必须换用v2并接数值附加包，不能沿用旧时刻；类别一致不等于时刻收敛。18.94h只是两网格此设计下的观测差异，不是严格误差上界/95%区间。技术完整性检查通过与全设计精度未统一通过在`results/validation.json`分字段报告，不能统称全部数值精度通过。见`NUMERICAL_LIMITS.md`。

## 解析热新挑战与推荐数值参考

同256×四机制×两策略完整2048积分，133696行代表状态；只替换热模块，冻结水/损伤引擎不改。对均匀初温、常alpha、分段保持地表，用erfc阶跃增量因果卷积，FFT8192≥4177，不用循环卷积/未来边界；API有`thermal_transfer_analytic`和`simulate_analytic`，base_scenario_id与已有包相接。

全256新FD0.0625m直接配对137有限时刻对，另248左删失/1663未越阈，类别2048相同。解析—FD0.0625最大启动差0.347080h，解析—v2最大19.07238h；连续强度分支最大逐时margin差0.009287，thaw分支仍0.179032及12个分支切换小时。不能把不连续强度域或小时状态误差藏在温度解析精度后。

43项独立检查通过，包含直接卷积、正负阶跃、未来扰动、镜像/本征有限域、边界/单位及四机制wrapper委托。有限40m底边界与半无限近似的实际总变差反射温差界2.38e−26°C，只约束所声明理想边界；FFT舍入约1e−14°C量级。水/损伤仍1h、真实初态/材料/物源/气象外推仍未知，不是整个耦合系统解析解或本地启动验证。支持域/API非有限输入建议见API_LIMITS；生产参数全部有限且dt=1h。见`ANALYTIC_THERMAL.md`和独立审查报告。

## 补证与输入接入

- Mamot2018全文公式/试验域与补充表实际核读：cj=53.3−73.5T kPa，mu=.42−.21T，冰填石灰岩快速剪切，T−8至−0.5°C/100–400kPa；外推、速率/材料、水压替代和面积混合边界显式。另读外部热扩散与裂隙流研究。5官方原件及7个实际查看PDF页记录见sources/strength。
- 新取得3个连续S1D SAR autoRIFT影像对的真实NC，52,149,417字节；本地1875像元/3裁片/6面板图。局地速度中位27/26/28m/year，产品误差48/55/52m/year，未给出可辨识临灾加速证据，也未证明无加速；不是本地GRD/InSAR处理。R2认证失败入口未重试，旧API404后转官方公开STAC。缺测/插值标记、相关误差/配准/遮蔽限制保留。
- Q1 feature-v1已逐文件验证，1356重叠小时温度逐值相同；降水仍unknown标签，不接受累计雨量/源区代表性。Q3 event-v1只采阶段/标签/时效约束，精确首次启动真值未接受、事件数0，不按参考时刻校准。
- Q4 spatial-copdem-v1作为条件计算几何/独立来源地形，两个源mask面积925200/964800m²。释放v2有64行/4张厚度TIF，V=16.477–51.756Mm³为条件指定，双网格固定V/质量；最大体积相对差1.44e−16。地表坡度非结构面倾角，源mask非已接受真实释放面。通过base_scenario_id衔接细热v2，旧几何onset_status不是真值。

## 新文献组分域对照

主参谋指出原rock0.2–0.8未覆盖事后文献冰约10–15%。本轮实际重读两冻结摘要，精细103.35/90.75Mm³仍仅主参谋已读候选。单独登记并积分8预定代表×rock0.85/0.90×四机制×两策略=128新情景，64旧v2只读基线，267392行新状态，所有非组成参数与桥面积比例保持不变。

密度2432.55/2521.7kg/m³，两组各8越阈/56未越阈、类别未变，但有限越阈时刻中位提前218.11/234.60h，最小裕度中位降低0.2053/0.2198，原实验数值域覆盖0.625→0.375。不能把更接近文献候选就当本地校准；整体组分→均质板密度是额外假设，未自动改变界面冰、fb、扩散率、排水或旧释放包。见`COMPOSITION_SENSITIVITY.md`。

## 已发布稳定接口

以下所有成员逐文件path/bytes/SHA-256，均无自包含，已发布者不重写：

| 入口（本问round3相对路径） | SHA-256 | 用途 |
|---|---|---|
| exports/mechanism_bundle.json | 250f25f180bfd2f7c6c296b679dd2c9aea18826411f5e7195f18b9ee07a56bc1 | 粗v1对照 |
| exports/mechanism_bundle_v2.json | dc53a9f805e96ff32b2c1fd064b0b7b33d90034e7d2c987f42403ae70bfcb093 | 推荐细热机制接口 |
| exports/numerical_supplement_bundle.json | 151a7c7f822f3970a7dbdc0194b4c1df18548dbb70afca19a5927f49f3206b03 | Q3须一并读的全量/定向精度限制 |
| exports/release_bundle.json | a22c0949d16f3f1f50efc6f97a74734bed45a8553096ec3084c84298c474d56b | 原小面积通用释放情景 |
| exports/release_bundle_v2.json | 3a6924f3ca796b39fad65c3c300e5417b08ed5343347388af938242d35dc1de3 | Q4条件源mask/同体积双网格 |
| exports/composition_bundle.json | 14f96d7d1e8600154a831dba9921a9efbf70eeacfd71e54b12af78879b762335 | 独立高岩石组分域挑战 |
| exports/analytic_thermal_bundle.json | ff989d23894f9b2d44daf032418583430791ef5b8367d423aa5cb54763767684 | 注册传热域内解析参考、同2048完整竞争与FD配对 |

机制v2 suffix `__thermal125v2`，解析suffix `__analytic_erfc_v1`；参数数值/UTC原点/1h/信息截止沿用，base_scenario_id对旧释放；新组分为另场景，不静默替换参数先验/旧释放相分数。释放phase_fractions为体积基准和为1、密度kg/m³、零初速明确坐标，垂直厚度积分体积；水库水头不自动换成释放自由水相。

## 复跑、审查与下一动作

实际主要命令为原venv运行`run_experiments.py`、`validate_engine.py`、`analyze_robustness.py`、`analyze_numerics.py`、`analyze_identifiability.py`、`integrate_geometry.py`、`run_refined_v2.py`、full_reference_check/top5_reference_extract、`analyze_composition.py --prepare/--run`、`run_analytic_thermal.py`、`review_analytic_thermal.py`及SAR离线复跑。全顺序/缓存/单位/冻结规则见`REPRODUCE.md`；图14张已实际打开并绑定当前哈希，见visual_review。

输入/输出清单和source_register、validation、result_index均已生成；收尾工作区命令：

```bash
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round3 --question q2 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q2 --expected-base 904d7257b899b9f71d1ac9e0eab7479e459eab52
track_b/.venv/bin/python track_b/research/q2/round3/scripts/finalize_packet.py
```

本问仅本地提交、不push。下一动作是主参谋集成这些稳定版本并联合审查，特别是Q3时刻敏感性、Q4体积/密度/相分数的情景身份；队员核验结构/材料/边界及最终论文科学采用。当前未解决项不是未执行计算：真实源面/结构与水热初态、精确启动真值、历史天气可用性、当地构成律与独立跨事件验证仍未知。AI实际贡献及人工采用待补见`AI_ASSISTANCE.md`。
