# Q3 第三轮滚动接口

首个本地区域事件包：`exports/event_bundle.json`，版本`q3-r3-event-v1-local`。其中三个CSV是`exports/event_v1/`下的冻结副本，逐文件path/bytes/sha256/role登记且不包含bundle自身；本地训练／验证接受数仍为0。外部数据随后以新版本另存，v1副本不覆盖。

Q3需要主参谋分发的稳定输入：

- Q2的`mechanism_bundle.json`及它引用的长表、方程、参数单位/范围或概率先验、状态初值、时钟与天气输入来源；至少scenario_id/model_id/mechanism_id/time_utc/elapsed_hours/failure_margin/margin_definition/data_role/forecast_input_mode。正稳定、零临界、负越阈；未越阈和缺失不能丢弃。需要区分状态是灾后实测驱动、理想未来天气，还是逐发布的真实／假设可用预报驱动。无未来天气支持的整条事后状态曲线只能作理想条件情景，不能认证灾前业务。
- Q1因素族/公式/QC与空间代表性，供本区域天气特征解释；Q3不直接跨树读活动文件。
- Q4稳定`propagation_bundle.json`及scenario_id、目标、几何/参数版本、相对释放传播时延、到达定义。只有情景ID同释放状态对应时才关联；下游到达另存，不替换源区启动。

此文件只登记输入需求，不向其他聊天直接发消息；主参谋核对并分发至本问`round3/inputs/`。自己的外部变形、生存模型和天气路线同步继续。

## 外部事件包 v2 已发布

`exports/event_bundle_v2_external.json`，SHA-256 `359f1e9868a1a63125296fd43e37ea22928815396a76d529669f8332baa8bbde`。9个文件逐项绑定，包括v2冻结事件/标签/天气可用表、真实变形规范化表与审核、Stampa真实右删失规范化表。登记15外部物理组，其中Veslemannen对时未核准而排出主评价；主风险集13失稳+1右删失。多传感器不增加事件数。

新增外部终末崩塌目标不等同本区域首次机械启动；本地主目标精确标签接受数仍0。v2全部历史天气可用时刻仍未知。原v1 bundle与`exports/event_v1/`字节不变。

## 已接入的跨问版本

- Q1 `q1-r3-feature-v1`：仅区域站因素定义、QC分轨数值及支持信息；未采纳排名或源区代表性，降水仍是标签统计。
- Q2 `q2-r3-mechanism-v1`：实际读取引擎、2048参数设计、完整结果表和64代表状态轨迹，用于理想条件首过阈和逐issue天气重启；设计点不是概率先验。v1 dz0.5m热误差作为数值敏感性，待主参谋分发的细化v2再追加，原v1保留。
- Q4 `q4-r3-spatial-copdem-v1-frozen-export`：8文件大小/哈希复核，实际读取两DEM；用于条件空间支持，源区并未被接受为实际释放面。
- Q2 release v2：已收到经主参谋核准的完整mask条件释放接口。最终传播到达仍需Q4相应版本；scenario的`__geomv2`与`base_scenario_id`须显式映射，不能笛卡尔相加。
- Q2细热网格`q2-r3-mechanism-thermal-refinement-v2`：副本SHA-256 `12eb0b329acede54face734b145cf33a8bfc5d329f6231b5a110c52ddec618c9`；原主参谋误写的7c92前缀已撤回。dz0.125m、参考0.0625m，分类相同但相对v1首过阈最大变化46.819h；实际追加A完整情景及热相关天气分支，保留v1数值对照，B/C及天气获取不受影响。新model_id、`base_scenario_id`与释放谱系分开核对。
- Q2全设计数值补包`q2-r3-numerical-limits-v1`：SHA `8ad708b3867ac35421ac1e3aa035969c52136e5bed1c845b190e9223fcad1b5b`。10/2048未过0.02裕度目标，137个有限时刻对最大差18.943779h；不能以64代表收敛推广完整设计，也不能当概率误差条。
- Q2组成补包`q2-r3-literature-composition-v1`：SHA `0837c492726e78b2fd7b945e64731ee989ce141ec4cb817c3a0abff8cb12fdf9`。128次配对积分只用于材料参数域敏感性；未把事后文献候选组成采用为先验，未改冻结释放接口。若将来采用，需要新情景映射。
- Q2解析热包`q2-r3-analytic-erfc-thermal-v1`：SHA `05e8b885198a3011e316472f562ba92480788cb04c6ab9bebfb3e04dbd3660ca`，21文件已实取核验。线性半空间分段边界erfc因果卷积作为热模块数值参考；相对0.0625m有限差分137个有限时刻对最大差0.34708h，相对0.125m v2最大差19.07238h。水／损伤仍按小时状态离散，未升级实测标签／校准概率；Q3追加独立版本，旧结果保留。

## 阶段补证 v3，供主参谋审查

`exports/phase_evidence_bundle_v3.json`，SHA `db5f1b6c1f4c04a7233b8b964e18dfa90b45c061a24009247aeef562cbe98898`，13文件。固定KKN波形miniSEED／官方GeoCSV、台站响应、日质量指标来源与实际解析；全部九个频带／阈值组合、69候选片段、两个实看图及USGS固定QuakeML审查均绑定。KKN有02:52以后增强的台站信号，也有02:30附近高频异常；源台路径、辐射相位、绝对台钟和滤波延迟未约束，不采用任何一个为首次机械启动。

该包只增加阶段候选证据，新增机械真值／训练／覆盖验证事件均0；不改v1/v2冻结文件，不以MUSTANG更新时间或当前下载时刻认证历史available_time。原始实波形缓存路径和SHA见其来源表。

## Q4通用传播早交已实际审核

`q4-r3-propagation-v1-metadata-handoff`副本SHA `ca2687f43fbca865fea8556435c9765ccc429fed4bf3f05dd5df8f79deb2fda0`，40文件已逐项核验，实际读取6个完成DClaw／42目标的表及数值限制。该版无Q2父映射，`join_propagation.py`实际执行得到42条明确拒绝、0关联、0绝对到达；这正是应有结果。全部目标保留于`results/arrival/propagation_v1/propagation_context.csv`，没有按相似scenario字符串强接。

扩域参考口岸数值首次保存场跨越为bulk release后(160,180]秒；目标阈值、空间范围、边界污染标志和`numerical_qualification`随行保留。包中允许纳入条件传播范围的标志不证明数值精度或实际到达。机械→释放滞后仍未知。后续Q2映射版本须以真实`base_scenario_id/upstream_model_id/upstream_parameter_version/release_mapping_version/geometry_version`对照冻结Q2 release表的参数值／几何，再显式选新解析onset版本，不能只因别名缺字段拒绝合法谱系，也不能凭同名接受非法谱系。
