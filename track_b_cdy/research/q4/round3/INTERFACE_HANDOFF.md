# Q4 R3 最终接口交接

最终完整传播版本为 `q4-r3-propagation-v4`，状态 `frozen_for_joint_review`、`partial=false`。它用于有明确条件和限制的跨问研究；原生区域31完成＝30必跑＋1代理诊断，另7材料不适用未运行；论文主展示建议单相120m与同框架对照，孔压／复合相为挑战。全部区域科学到达包络接受标记false。唯一执行根、共同基线与全部历史哈希见 `HANDOFF.md`；本文件给接收方的字段和版本使用规则。

## 已接收输入

| 主参谋分发副本 | SHA256 | 实际用途 |
|---|---|---|
| `inputs/q2/release_bundle_q2-r3-release-v1/bundle.json` | `ed745576ff706a4d82a560269b0e07804add6fc9bde2b3948cced43932ddf5b5` | 小面积释放目录32行；实际承接S／ST／SH／STH四个传播映射 |
| `inputs/q2/release_bundle_v2_q2-r3-release-v2-spatial-copdem-v1/bundle.json` | `108ce2d34289fe3c5cdb5dacf6927bf977439bd9f06b959ff931f7d06b57f683` | 全候选mask目录64行；承接S60、ST60／120三例，与compact保持不同几何和体积 |
| `inputs/q2/composition_bundle_q2-r3-literature-composition-v1/bundle.json` | `c8fb79484b4455ab5b64d4099fedcd0a9945ff8da6e00e30b44b51648ef54b4c` | 组成证据与上游lineage；敏感性.85／.90不自动替换既定释放或增加Q4运行 |
| `inputs/q3/event_bundle_q3-r3-event-v1-local/bundle.json` | `b38711d8e34e7ab79a21a8856099aa5fb2bd003f31fdab4a5074b55337003724` | 2组登记、5条可用性、11条阶段标签；本地独立训练／验证事件0 |

以上catalogue及其成员均核验原字节；Q2三套目录和成员绑定已收入v4。Q3来源不提供已接受的首次机械启动精确真值或独立到达标定。`results/interface_input_usage.json` 与 `results/comparison_input_index.json` 给读时记录，禁止用他问活动文件替换分发副本。

## 输出版本与分发状态

规范v4包头修订后SHA为 `9ae2ac6e93d6972b351f76fd1a441b5d6a670f7ffb842426bc1feeecc326fbf0`；原头 `d3b87e86ceacd0709b6f9278aee7096e6671964b8baec0c4055eac1355d529e4` 和旧清单已归档至 `results/metadata_revision_before/evaluation_stratum_v1/`。本次仅把`evaluation_stratum`说明串拆为允许列表及独立说明，文件成员、数值与科学接受保持不变。消费者须以修订后canonical／v4头和现行根manifest为准；旧output清单不再验证更新后的live别名。

| 包入口 | SHA256 | 成员／目标及状态 |
|---|---|---|
| `exports/geometry_v1/bundle.json` | `5a2315f807bac296e5ae9bf877e655499b7a2b40e39df8edd3b0cccbeade853a` | 8成员；主参谋已审读并分发Q2／Q3，仅接受条件几何用途 |
| `exports/propagation_handoff_v1.json` | `ef63555c5decb383a66eeb01ef48a7cfe1c1a29ec52cd435a9ed55a801ba2c16` | D-Claw6例、42目标、40成员；已交Q3作部分传播背景 |
| `exports/propagation_v2/bundle.json` | `2a54e77d811faa8d949f92a2e45788751122517b6e91839ca8742cda20ea88a4` | compact S／ST，14目标、39成员；质量修订04全部排除到达范围 |
| `exports/propagation_v3/bundle.json` | `150c72537ee162d29cc2e20e3e31183df1915f64999234789e1875d368c09b9c` | fullmask三例21目标、66成员；主参谋已审读原包并交Q3 |
| `exports/propagation_handoff_v3.json` | `9bb9fb3cd4242e728d22412dbea0191853307c7c647cf5bd3c607110053ccee1` | 原v3同66成员加体积metadata注释，共67成员；已提供主参谋，消费者receipt待主参谋记录 |
| `exports/compact_delta_v1/bundle.json` | `28c67deb49d694e992c005365cf19c73d1db31a89126f64dbe8b6973adba61cb` | SH／STH额外14目标、48成员；主参谋已核验并交Q3 |
| `exports/propagation_v4/bundle.json` | `9ae2ac6e93d6972b351f76fd1a441b5d6a670f7ffb842426bc1feeecc326fbf0` | 最终全部路线777成员、844条目标记录；已独立全部bytes／SHA核验，供主参谋联合审查与分发 |

`exports/propagation_bundle.json` 与v4原字节相同，三张冻结表与根最终CSV同SHA：model_runs157行、comparison_metrics139行、target_arrivals844行。目录中的历史配置、数值基准、失败／隔离／未运行登记和诊断单列，表总行数不能充当独立事件或正式区域运行分母。正式范围为30必跑完成＋1代理诊断完成＋7材料适用性排除未运行；简化34项与2项既有案例实际复现另计。

原v1、v1 metadata、v2、v3、v3 annotation和compact delta原字节均保持冻结。需要修订时新建版本，不能覆盖已交包。本窗通过文件与commentary交主参谋，不主动发送其他聊天消息。分发和全项目采用以主参谋回执为准。compact delta消费者回执由主参谋提供：SHA256 `044a9a08ce09e8b2b5470a6a4351942fb08054e52e9728e2bb4d51a2295841ac`，四机制映射已齐。

## 场景、时间与状态规则

- `scenario_id`、`base_scenario_id`、mechanism／model／parameter／geometry版本按实际上游保留。Q2 never_crossed仍保持 `if_released_propagation=true`；条件释放可计算，不证明上游实际已经启动。无Q2 parent的独立Q4情景保持 `unknown_Q2_parent`，不靠名称近似联接。
- `travel_time_seconds` 与上下界均相对成规模 `bulk_release`。`initiation_to_release_delay_seconds=null`，绝对release UTC未知；Q3不能默认延迟0叠加到首次机械启动。若将来研究零延迟，需要另登记显式假设。
- 首达定义为注册目标100m缓冲内格心总厚≥0.1m首次保存命中；1D等效定义与各求解器细节另列。区间为 `(前一保存时刻, 首次命中时刻]`，它表示输出采样范围，不是概率区间或精确求解器步首达。
- 时间来自原生tsum或fort.t，未用frame_index×20填造。请求1800s与实际1800—1802.4s末帧分开；1800以后命中不计作1800内。`not_arrived_by_horizon`保留null及实际时域；outside_domain、missing、numerical_failure／pipeline_failure、quarantined和not_run分别保留，不能合并为安全。
- 原生官方表 `official_arrivals.csv` 的命中词为 `arrival`，综合接口 `target_arrivals.csv` 为 `arrived`。消费者应使用交接综合表和字段定义，不直接混用词表。
- v4中无概率权重、独立本地验证数0、accepted arrival envelope空。`conditional_diagnostic_range_eligible` 或执行／时间／字段／边界门禁通过只支持有限诊断，不授予质量、区域精度或预测资格；旧v1的12条true保留其当时明示的执行诊断含义。

## Q2映射专项

七例共49条目标记录，6条汇流候选命中、43条未达；各自口岸候选在实际末帧前均未达。compact S仍未达；ST／SH／STH汇流为(1360.5,1380.1]／(801.1,820.6]／(1400.1,1420.5]s。SH仍never_crossed、if-released，STH为上游interval crossing；不能以这些条件传播时延替上游构造精确启动标签。

fullmask S60／ST60／ST120汇流为(161.1,180.2]／(221.0,240.7]／(240.6,260.1]s；实际体积分别51.755728593／31.184139128／31.184139128Mm³。原case继承的 `expected_reference_grid_volume_m3=13878000` 是旧h15参考；输入TIFF、Q2v2、`release_grid_volume_m3`及native t0才是实际物源链。固定解析器实际使用release_grid_volume计算t0差。独立注释 `exports/propagation_handoff_v3_annotation.json` SHA `1b4db70b8a19b92860267b14912ed435a89624e8db1d8a9df4c84c541ab87f39` 解释舍入／原生积分细微差异，未改raw或重跑。

compact与fullmask源面积、支持格数、体积和密度各自独立，不能合并为同一物源；法向厚度转垂直厚度与格网积分有检查。单相等效密度承接岩／冰／水体积分数，未显式求解岩冰相对速度或冰融化。compact内部预算+11.67%至+21.37%及fullmask较小残差均保留，全部科学接受false；不能依结果给新权重。

## 空间、物理与证据边界

EPSG:32645、east/north、m为计算约定；GeoJSON为CRS84经纬度。新地形为Copernicus编辑DSM，EGM2008、主体2011—2015采集；源、路线、设施／桥和OSM几何仍为候选，位置误差未知。5个OSM代表几何对应3个候选实体，不能当5个独立验证对象。60／120m初始参考按同体积归一，但D-Claw native topointegral改变局部h与有效床面，跨框架不能称逐格同初态。

r.avaflow水平速度为各相动量除厚后合成；原生地形标量与保存峰值／逐步累计峰值分开。复合固体＋水支持固水相对运动，不解岩冰分离或热力；drag／virtual-mass关闭只关闭这两类项。终态静止残余用厚≥0.1m、湿相最大水平速度<0.1m/s，有限时刻结果不等于永久沉积。侵蚀新增质量与预算误差分列。

D-Claw扩域到口岸(160,180]s、保存边界干仍有终态M−4.1473%；固定raw／源码审计已完成，缺少逐步账而不能定量归因。单相CFL与格网敏感、简化HR薄流反证、复合相预算漂移均限制定量采用。文献重建、光谱候选和官方训练基准均不能增加本地独立验证分母；40模型／160条光谱比较为探索性一致性，不能用于宣称事件精度或95%覆盖。

接收方下一步由主参谋审核版本、场景与阶段定义后联接Q2／Q3；队员审视论文主展示和挑战方案。新的科学接受需另行明确发布，不能由完整性通过或消费者读包成功自动产生。
