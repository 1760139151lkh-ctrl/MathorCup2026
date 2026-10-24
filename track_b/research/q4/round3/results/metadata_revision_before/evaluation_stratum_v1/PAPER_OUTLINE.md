# Q4 论文方法、结果与可靠性提纲（联合审查稿）

日期：2026-10-24。本文供队员组织论证、核对来源和选择图表，不是已定稿论文，也不代表模型已获科学采用。原题第四问要求“构建吉隆泥石流发生的仿真环境，设定明确的关键参数，给出仿真过程及可视化的仿真结果”；正文按这四个动词展开，可靠性与跨问交接贯穿其中。

**完成状态：** 最终根汇总于2026-10-24 11:23:40 UTC冻结为 `frozen_for_joint_review`：38个原生区域登记＝30个材料适用必跑全部闭合＋1个已完成通用代理诊断＋7个材料适用性排除、明确未运行的代理扫描。30项包括18项单相（10项参考／厚度／阻力／CFL／格网、1项有界夹带、7项Q2映射）、9项D-Claw及3项复合固体／水实验。34项reduced区域计算已完成；2项wrapper复现是既有案例复跑，增加模型案例和独立事件均为0。最终库存157行、真实区域执行尝试70次分别保留历史准备／隔离／失败／取消身份，不能把它们当30项正式必跑的分母。最终三表为157／139／844行，传播包 `exports/propagation_v4/bundle.json` 含777项字节哈希绑定成员；模型过程的完成不改变科学资格。

**科学采用状态：** `config/scientific_acceptance_decision_05.json` 的 `accepted_arrival_envelope_run_ids=[]`。最终v4以及新早交包的 `include_in_arrival_envelope=false`；`conditional_diagnostic_range_eligible` 和执行／时间／字段／材料／边界门禁只表示有限条件诊断可用性。全部区域的精度、质量守恒和预测资格均为false，队员科学采用仍为 `pending_team_review`。冻结v1历史true仅按其原诊断门禁解释；v2、v3、metadata adapter和compact delta按各自冻结说明引用，不追改早交字节。

## 一、构建仿真环境：研究对象、空间和数值环境

**段落1：先界定可计算阶段。** 本问求解给定释放状态后的传播，输出沿程／二维流动、域内范围及候选目标的相对到达时间。源区首次机械启动、成规模释放和下游到达是不同阶段，关系可写为

\[
T_{\rm arrival}=T_{\rm initiation}+\Delta_{\rm initiation\to release}+\tau_{\rm release\to target}.
\]

本轮 `initiation_to_release_delay_seconds=null`，不得默认0；传播时间不能直接替代Q3的首次机械启动时间。Q2 `never_crossed` 情景的条件传播保留 `if_released_propagation=true`，不以传播成功证明其机制已触发。所有绝对时刻、信息可用时刻和位置误差中未识别的量继续为空并解释原因。

**段落2：给出空间域及资料身份。** 共同区域采用EPSG:32645，60 m为154×300、120 m为77×150；新地形来自实际取得的Copernicus GLO-30 COG。产品为AWS 2021 COG发行，主体TanDEM-X采集2011—2015，垂直EGM2008；它是编辑DSM，不能称2026事发裸地测量。原供应DEM产品、年代和垂直基准仍未知。新减原的共同60 m差异均值+29.73 m、RMSE31.68 m仅是产品差异，不是时序变形或已知垂直改正。来源以 `sources/spatial_acquisition.json`、`sources/spatial_product_documentation.json` 和 `results/terrain_bundle.json` 为准，并保留产品署名。

**段落3：描述候选源区、通道与目标。** 源界、文献河线和纸图口岸符号来自事后图上重建；其配准误差不等于真实位置误差。60／120 m源支持分别为257／67格、925200／964800 m²。三个地形代价路线长20.698／21.415／21.655 km，未强制等于文献22.8 km。原647 m图上缺口另经三条源边缘接河候选研究：长709.71／794.56／939.41 m，局部当前DSM降高284.15／315.37／574.08 m且存在无上坡8邻路径；全域路线仍有累计上坡，不能将局部可计算连接写成真实全程轨迹验证。

**段落4：补充观测线索如何约束解释。** 三景TCI／SCL、两景红／近红外实际像元表明源区事前多暗区、事后多雪冰，不能认证失稳面。OSM的167条河／溪及5种目标几何仅代表3个逻辑实体；桥、设施与纸图符号分开，编辑时间不是观测时间。经同产品C1辐射核验并修正legacy重复offset后，在两景SCL4／5且DN>1的有效配对范围内，47天光谱筛选在250 m走廊7.4511 km²中得到候选植被变化4.0537 km²（54.40%），旁侧500—1000 m环带为0.5816／14.2262 km²（4.09%）。这是探索线索，不能称实测泥石流影响面或独立验证。最近邻重投影到10 m不提高模型分辨率，重叠指标不用于调参择优。

**段落5：用模型能力说明环境。** 简化1D求解沿路径传播、2D增加横向铺展；r.avaflow求解原生均质或各相厚度／动量；D-Claw求解混合物流动、固相体积分数和孔压演化。固定本地Linux运行时、源码与二进制身份见 `REPRODUCE.md` 和官方来源记录。原单相csurface2不适用状态索引的旧输出隔离，正式单相为csurface0；小格网资源清理修正版与大域原版分别登记。环境搭建的实质是明确输入、网格、方程、初边值及输出对象，不能仅用安装成功说明已回答题目。

## 二、设定明确关键参数：可追溯情景与公平配对

**段落6：列共同条件和模型专属参数。** 共同参考为初速0、参考厚15 m／体积13.878 Mm³，5／30 m及文献136 m作为挑战；136 m在本候选源上对应125.8272 Mm³，不能强制等于作者另一源面重建的103.35 Mm³。跨网格按同体积调整厚度；存在对应阻力项时列mu=.08／.15／.25、xi=500／1000／2000。这些均为条件或迁移参数，不是本地标定真值。D-Claw专属固相、初始孔压和渗透率另列，零初始孔压仍保留后续压力演化，不称关闭孔压模型；无同名物理项的参数填NA。

**段落7：写清实际材料映射与消融。** 2700／1850／1000 kg/m³的三材料组仅为通用代理诊断，1850摩擦性P2不是纯冰。当前阻力闭合的密度因子含 `1-rho3/rho2`，直接P2冰917／P3水1000不适用；交换标签又改变原生流体相逻辑。材料适用性排除的7项不算数值失败或完成实验。

正式复合映射将岩0.6＋冰0.1合为体积分数0.7、密度约2445.286 kg/m³的P1，P2空，P3水0.3；与全岩固体0.7＋水0.3配对，同体积但不同总质量。它允许水与整体固相分离，不解岩冰相对运动、热力或融化。另一配对仅关闭drag与virtual-mass两类项，浮力／压力等其他耦合仍在，不能称all-coupling-off。最终表逐对核对地形、相场、初速、总量、阻力、构建与边界，避免把非控制变量差异当新增物理收益。

**段落8：有界夹带条件单列。** 零夹带参考之外，预登记1 m床层位于P1路径250 m缓冲，排除初始源与外3圈；有效零值覆盖床外，容量9.5472 Mm³、床密度2105 kg/m³。原生centrainment=1、entrainment=-7,0；按实际源码实现的动量相关速率和剩余床层约束解释，不写成已测侵蚀率或动能反演。该床层是分析者情景，未增加融化过程。总质量预算扣除新增床质量，体积预算另列新增床体积，不能混用单位或把物源增长直接当守恒误差。

**段落9：Q2映射与跨框架公平性。** Q2 v1小面积物源和v2全候选mask为不同几何／释放版本；保留scenario_id、base_scenario_id、mechanism/model/parameter及条件释放身份，不静默替代。normal／vertical厚度与体积基准分开，孔压储水量不直接变成自由水份额。跨框架虽共享原始DEM与体积，实际离散初态、有效床面、阻力与边界仍不同；复杂度本身不构成改进证据。

## 三、给出仿真过程：实际计算、比较和可靠性反证

**段落10：先交代可复查的计算过程。** 简化1D／2D的实际方程、Rusanov通量、水静力重构、CFL和隐式摩阻以 `REDUCED_MODELS.md` 与源码为准：

\[
\partial_t h+\nabla\!\cdot(h\mathbf u)=0,\qquad
\partial_t(h\mathbf u)+\nabla\!\cdot(h\mathbf u\otimes\mathbf u+\tfrac12gh^2\mathbf I)
=-gh\nabla z-h\mathbf a_f,
\]
\[
\mathbf a_f=\left(\mu g\cos\theta+\frac{g|\mathbf u|^2}{\xi h}\right)\frac{\mathbf u}{|\mathbf u|}.
\]

其中h为垂直厚度、u为水平速度，1D沿站距并采用等效恒宽；该简化路线未解曲率、孔压、相间交换、融化或夹带。原生模型按各自状态变量和实际步进／输出分析，不能把上式当作其全部方程。按实际原生time_s保留过程帧和到达括号，不以frame_index×20推造时刻。请求1800 s与实际末帧分列，例如单相参考1801.2 s、CFL半值1800.9 s、复合配对1800.4 s、夹带1800.2 s；超出请求时域的命中不算1800 s内到达。

**段落11：简化路线的完整结果与反证同段出现。** 已完成24个1D和10个2D区域计算，均至1800 s，最大体积账相对残差约8.05e−16；纸图主目标均未达。常坡薄层速度在20／10／5 m格网相对误差约0.755／0.377／0.188，区域60 m源区97.276%像元四邻最大地形落差大于15 m，故区域薄流速度／到达精度不合格，34项均排除accepted到达集合。1D厚136 m的P1存在约19.0113 Mm³边界流入，体积账闭合也不能将其当夹带。OSM170行中120 missing来自1D空间支持不足、50未达；两者都不支持设施安全。安全wrapper已复现1d_P1_ref和2d_ref_120m，物理summary和数值数组完全相等，验证复跑入口而不消除数值缺陷，也不增加案例或验证事件。

**段落12：报告CFL-only反证。** 实际native控制文件仅CFL criterion由0.50改0.25，run_id归一后其余参数相同、二进制相同，见 `results/official_cfl_control_crosscheck.json`。120 m单相保存帧水平峰速92.394→53.256 m/s，最大流深38.297→35.050 m，汇流括号(420.9,441.3]→(461.0,480.7] s；原生累计地形标量152.356→92.633 m/s另列。内部预算约−1.0263%／−1.5512%。这是时间步敏感性的实证，不能宣布时间步收敛；两网格对照也不能证明渐近网格收敛。10项单相配对均已完成；60 m参考实际末时1801.4 s、汇流(540.1,560.8] s，内部预算+11.5057%，而120 m参考为−1.0263%。加密并未自动改善预算，峰值响应也非单调；这些结果支持数值敏感性解释，尚不支持收敛或事件精度。

**段落13：D-Claw过程、边界和raw质量审查一起报告。** 9项D-Claw必跑已完成，包括60／120 m参考及初压、固相、渗透率挑战和120 m扩域。120 m参考的汇流(40,60] s、口岸(160,180] s均相对释放；边界首保存触及80 s，口岸结果发生于此后。扩域保留核心DEM，口岸括号仍(160,180] s且91帧边界h/hu/hv均0；这仅说明该扩域未改变保存到达括号，不证明无限域收敛或精确连续到达时间。

原生qinit积分使总体积近保持，却将源支持67→111格、约6.95%体积移到原mask外，局部厚度归一L1差13.899%、有效底床RMSE8.083 m。因此跨框架快慢不能全归孔压。独立解码3算例共273帧binary64，按

\[
V=\sum hA,\qquad V_s=\sum hmA,\qquad M=\sum[\rho_fh+(\rho_s-\rho_f)hm]A
\]

分别积分；hm不是m或固相质量。扩域到180 s总M已−2.1612%、1800 s−4.1473%，同期终态V−5.2033%、Vs−3.1614%；高渗透原域20 s总M已+11.6012%。理论源项组合抵消，不能用膨胀笼统解释总M缺口。20 s保存边界近似账的+1.019%也不是原生守恒精度。缺逐步面通量／源项／裁剪账时保留未定量归因，详见 `DCLAW_MASS_AUDIT.md`，不临时设容忍线宣布合格。

**段落14：复合相和Q2结果保留预算限制。** RI＋水、drag／VM两项关闭、全岩＋水三例均实际至1800.4 s，P2全程0、初始相厚一致；全岩配对改变固相密度和总质量。三例原生内部预算依次−10.3010%／−1.9841%／−13.145469%，ASCII预算另列。汇流括号依次(200.0,220.4]／(181.1,200.4]／(220.1,240.2] s，前两配对存在交叠，保存上界之差不是精确因果效应。合法材料映射不等于质量或区域精度合格。Q2共7项映射已全部完成，保留4项compact v1和3项fullmask v2，不能静默混用几何或重复计算早交包为新案例。

Q2七项均使用父参数 `q2r3-design-v1`；表中体积为实际释放栅格积分，时延为相对成规模释放的保存帧阈值括号。compact映射为 `q4-r3-q2-mapped-release-v1`，fullmask为 `q2-r3-release-v2-spatial-copdem-v1`。完整 `scenario_id/base_scenario_id/model/parameter/mapping`、原Q2v1物源和实际原生输入／控制均绑定于最终v4；无明确Q2父情景的通用条件算例保持 `unknown_Q2_parent`。

| Q2父情景／模型 | 映射／格网 | 释放体积Mm³ | 父状态／if-released | 汇流括号s | ASCII／native内部预算残差% |
|---|---|---:|---|---|---:|
| p0000 S／`q2r3_S_v1` | compact v1／60m | 0.559400 | never_crossed／true | 1800s窗口未达，travel=null | +21.1534／+21.3729 |
| p0036 ST／`q2r3_ST_v1` | compact v1／60m | 1.348212 | interval_crossing／false | (1360.5,1380.1] | +12.6130／+12.7163 |
| p0072 SH／`q2r3_SH_v1` | compact v1／60m | 5.100007 | never_crossed／true | (801.1,820.6] | +11.6385／+11.6655 |
| p0255 STH／`q2r3_STH_v1` | compact v1／60m | 1.255515 | interval_crossing／false | (1400.1,1420.5] | +12.2897／+12.4028 |
| p0000 S／`q2r3_S_v1` | fullmask v2／60m | 51.755729 | never_crossed／true | (161.1,180.2] | +0.94721／+0.94778 |
| p0036 ST／`q2r3_ST_v1` | fullmask v2／60m | 31.184139 | interval_crossing／false | (221.0,240.7] | +1.66319／+1.66505 |
| p0036 ST／`q2r3_ST_v1` | fullmask v2／120m | 31.184139 | interval_crossing／false | (240.6,260.1] | −0.39735／−0.38838 |

七项共49目标行：6个保存帧命中、43个有限时域未达，全部接受／质量／区域／预测资格为false；未达不是设施安全。fullmask原case中 `expected_reference_grid_volume_m3=13,878,000` 是继承的15m参考基线，不能作为这些Q2释放的期望体积；以实际 `release_grid_volume_m3`、冻结Q2v2和原生t0积分核对，原case／execution字节保持不变，说明见 `exports/propagation_handoff_v3_annotation.json`。两种预算表示分别保留，未临时设置百分比通过线。


**段落15：夹带过程与末态残余分开。** 有界床实际新增5.61843 Mm³／11.82679515 Gkg，床外侵蚀0、层厚未超1 m；源项修正原生内部预算约−1.1572%，ASCII约−1.1747%。零夹带和夹带实际末帧1801.2／1800.2 s中，总厚≥0.1 m且湿相水平速度最大值<0.1 m/s的静止面积／体积均0；湿相检查下限1e−6 m。图中同时展示运动物质的末态流深，0静止残余不等于无残余或已证明不会沉积，hmax更不是最终堆积。高摩阻mu=.25案例在实际1802.0 s的静止残余体积约0.380506 Mm³、面积0.3168 km²；它仍是有限时刻运动学集合，不能称永久沉积。

**段落16：解释执行诊断与科学接受。** 原适配失败、非零退出、旧单相csurface2、失败前字段、取消／替代、历史未执行准备和真正完成分列；最终实际尝试已全部取得终态。csuccess=1初值不覆盖退出码与真实终时。小网格Segment清理修复只替换45处最终资源关闭调用，实际二进制／挂载与原版分开；纯流体60 m csurface0盆地仍未保持预期静水平衡，不能把退出修复当物理通过，也不据此否定全部颗粒路线。官方Cascadia／gully仅属外部数值／流程基准。上述反证与条件过程均有研究价值，但decision05下尚无accepted到达包络，不将完整性验证pass写成区域精度pass。

## 四、可视化仿真结果：每幅图回答一个问题

图中统一空间轴、目标身份、单位、阈值和实际原生时刻；图例区分保存帧最大值与逐步累计量。r.avaflow水平速度由原始动量除相厚得到，湿相最大水平速度与D-Claw混合物水平速度仍有定义差异；reduced原峰速阈值h>1e−9 m与正式湿层阈值不同，不能直接按峰值排序。主参谋已于11:22:10 UTC实际打开并审查10幅最终comparison图，逐图bytes／SHA及审读内容见 `results/comparison_visual_review.json`；其中单相敏感性图覆盖10项配对，两幅复合相图覆盖3项完成实验。图形可读性审查不代表科学采用。

| 论文作用 | 候选图表／数据 | 采用前须回答 |
|---|---|---|
| 图A：环境、源区／河谷／分离目标 | `figures/spatial_terrain_paths_review_v2.png`、`spatial_osm_objects_v2.png`；空间子包 | 标明候选身份、DSM年代、对象与局部连接限制，不称真实轨迹 |
| 图B：像元质量及独立来源的变化线索 | `figures/spatial_optical_candidates.png`、`spatial_spectral_screen.png`；修正后的光谱子包 | 使用corrected v2和有效pair分母，不称实测泥石流影响面 |
| 图C：共同区域深度与D-Claw过程／孔压 | `figures/comparison_regional_fields.png`、`comparison_dclaw_process.png`、`comparison_dclaw_pressure.png` | 锁定合法映射与有效完成案例；说明初态／床面不同及压力变量，不作预测排名 |
| 图D：CFL、网格和简化数值反证 | `figures/comparison_single_sensitivity.png`、`reduced_numerical_checks.png`；`official_cfl_control_crosscheck.json` | 10项实际单相配对已齐；保存数值／参数条件差异，不能只展示守恒通过 |
| 图E：扩域与总质量预算 | `figures/comparison_domain_sensitivity.png`、`comparison_mass_budget.png`；`domain_sensitivity_comparison.json`、D-Claw raw审查 | 全域／原核心面积分开，V／Vs／M分开；保存边界不湿不是逐步通量证明 |
| 图F：有界夹带、实际侵蚀与末态残余 | `figures/comparison_entrainment_residuals.png`、`results/entrainment_residual_comparison.json` | 预设床与实际侵蚀分开，源项修正预算；空静止集合和运动末态同时展示 |
| 图G：复合固体／水的相场与配对 | `comparison_composite_phases.png`／`comparison_composite_phase_volumes.png` 已生成并实际审读，覆盖3组完成案例 | P2零、相厚／水份额与时刻标明，预算漂移同图文说明，不称纯冰或全耦合关闭 |
| 表A：参数、来源及实际初边值 | `results/terrain_bundle.json`、Q2 receipts、各case与actual native controls | 参数基准、相类型、normal／vertical、实测／迁移／情景逐项核对 |
| 表B：模型竞争与资格 | 根 `model_runs.csv`、`comparison_metrics.csv`、`numerical_validation.json`；子包索引 | 当前accepted空，诊断门禁、质量／区域／预测资格分开，成本以实际执行记录为准 |
| 表C：分目标传播交接 | 根 `target_arrivals.csv` 及最终v4传播包、v3／adapter／compact delta早交入口 | 保留null、未达／missing／失败、100 m／0.1 m、实际时域和括号；不把桥／设施合并 |

## 写作采用与已冻结交接

正式扫描和图表已完成，后续是队员对路线与论文论证的采用审查。为组织条件过程展示，可将r.avaflow单相120m及其对照作为主展示、D-Claw扩域及压力／渗透率对照作为孔压结构挑战、合法复合固体／水三例作为相结构挑战，reduced 1D／2D作为可审查数值对照；这些角色不赋予预测资格。CFL／网格敏感、D-Claw质量缺口、复合相及compact预算漂移均须与结果同段报告，不以模型复杂度宣布更接近真实事件。

光学探索对照已按原 `all_completed_2d_models` 协议修正角色筛选，实际报告为40个模型、160行；原29／116有限角色结果已保留legacy。修正补回7项Q2、3项复合相、1项夹带，不改mask、阈值、域、指标、模型或调参规则，见 `sources/optical_role_filter_correction.json` 与 `results/optical_model_agreement.json`。47天变化仍非事件影响真值、独立验证事件仍0，不能据重叠选择参数或认证到达。

早交v1／v2／v3字节冻结。主参谋已向Q3分发原fullmask v3；`exports/propagation_handoff_v3.json` 为同66结果成员加1项legacy体积说明的67成员metadata adapter；`exports/compact_delta_v1/bundle.json` 仅补SH／STH两例14目标，不增加新案例。完整最终入口为 `exports/propagation_v4/bundle.json`（SHA256 `d3b87e86ceacd0709b6f9278aee7096e6671964b8baec0c4055eac1355d529e4`），三表与根结果逐字一致；`exports/propagation_bundle.json` 指向相同v4描述。最终manifest与来源／图像审查由主参谋统一锁定。

Q3接收给定释放后的条件时延、原始观察状态、括号和资格。首次机械启动到成规模释放的延迟为null；无概率权重，独立本地训练／验证事件为0，集合不产生置信区间或95%覆盖率。队员逐项核对来源、公式、物理映射、阈值、人工采用与AI辅助披露，科学采用仍为pending。
