# Q4 第三轮最终交接：传播模型竞争

研究执行已闭合，最终传播包状态为 `frozen_for_joint_review`。原生区域共31例完成：30个材料适用必跑＋1个通用代理诊断；7个材料不适用代理明确未运行；34个简化区域情景完成。论文主展示建议单相120m sf0与同框架对照，孔压和复合相作结构挑战。科学采用为 `pending_team_review`，已接受的到达包络为空，独立本地验证事件为0。本交接仅覆盖Q4，不代表其他问或整篇论文已完成。

## 恢复入口与共同基线

- 唯一执行根 `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4`，分支 `codex/track-b-q4-r3`。Git仅改本问 `track_b/research/q4/round3/`，大型数据仅在 `/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/`。
- 共同基线 `904d7257b899b9f71d1ac9e0eab7479e459eab52`；preparation `de790034cf302de58e69329dbe288aad269a359c`；725文件基线清单SHA256 `fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`。前两轮、公共输入和基线原字节保持不变。
- 原Python3.12.14／44包环境用于标准验证。独立局部Numba0.62.1／llvmlite0.45.1／NumPy2.3.5锁见 `config/reduced_environment.*`。启动快照 `sources/startup_workspace_verification.json` 与收尾 `workspace_verification.json` 的五组检查均已通过。
- 本地linux/amd64原镜像 `sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29`；r.avaflow4.0G Rev7／20250902，D-Claw1.0.0 commit `7d48663bbed916372ba18732627c52043afb109f`，Clawpack5.11.0 commit `285b7de9837702276213b7deb040495adc60c4cc`。
- 小格网资源修复的实际二进制 `45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c` 通过原镜像与只读addon执行，仅改45处最终资源关闭调用。派生镜像 `sha256:3d8d8b4a31a520f64c52c2e8d3e23684181222c40ffd246f2d9e25d5cd511bce` 另供重放，不能倒写为历史实际镜像；原生物理与资源修复身份分开。
- Q2三套输入catalogue与Q3事件包只消费主参谋分发到 `inputs/` 的哈希副本；不直接读取其他问活动目录。完整来源、成员和空值原因见 `INTERFACE_HANDOFF.md`、`results/comparison_input_index.json`。

## 最终传播包

本版包头已作 `q4-r3-evaluation-stratum-v1` 元数据修订：`evaluation_stratum` 为允许列表，分层说明另字段。修订前头部SHA `d3b87e86ceacd0709b6f9278aee7096e6671964b8baec0c4055eac1355d529e4` 与旧验证／清单原字节保存在 `results/metadata_revision_before/evaluation_stratum_v1/`；旧清单仅对应提交0219316时的live路径，现行根清单／验证优先。777科学成员、三表、全部资格与33934缓存原字节不变，未重跑模型。修订记录见 `sources/metadata_revision_v1.json`。

稳定版本入口 `exports/propagation_v4/bundle.json`，浮动最终入口 `exports/propagation_bundle.json` 与其逐字相同。

- SHA256：`9ae2ac6e93d6972b351f76fd1a441b5d6a670f7ffb842426bc1feeecc326fbf0`；499148 bytes，777个成员，已独立逐一核对大小与SHA。
- `partial=false`、`all_routes_completed=true`；required30/30、诊断1/1、材料排除7项均有明确终态；pending、未结attempt、读时输入变化及字段／预算解析矛盾均为空。
- 冻结三表 `model_runs.csv` 157行、`comparison_metrics.csv` 139行、`target_arrivals.csv` 844行，与根最终CSV逐字同SHA。库存含历史配置、隔离、失败、外部基准与未运行登记，157不是独立区域科学案例数。
- Q2七个实际映射场景49条目标记录齐全，6条汇流命中、43条未达；各自的parent/model/parameter/geometry、never_crossed／if_released、真实时域、case／execution／控制／字段与三套上游catalogue成员绑定保留。无显式Q2父场景者记为未知，不能强行与Q2启动结果联接。
- 科学接受决定 `config/scientific_acceptance_decision_05.json`：全部区域 `include_in_arrival_envelope=false`；质量、区域精度、预测资格均未接受。执行／时间／字段／材料／边界诊断门禁另列，不等于accepted ensemble。
- 原生最终稳定回执 `results/official_final_delivery.json` SHA256 `9c510981ad94b93d84ff444b305bffe99e71936e2ab6c96a71d66e23349f8cd8`；45个字段接口、3194项CSV绑定检查，原生持续写入进程已结束。

## 已冻结历史交接

下列文件均保留原字节，消费者继续使用哪个版本以主参谋分发回执为准。v4完整包可替代早交子集用于联合审查，不能把历史包的诊断旗标升级为预测接受。

| 版本入口 | SHA256 | 范围 |
|---|---|---|
| `exports/geometry_bundle.json` | `64cd8369ce79d599890d4ed726a87833b63f64472c4dbea54408e39e79a40561` | 原空间入口 |
| `exports/geometry_v1/bundle.json` | `5a2315f807bac296e5ae9bf877e655499b7a2b40e39df8edd3b0cccbeade853a` | 8成员空间早交，主参谋已分发Q2／Q3 |
| `results/spatial_supplement_bundle_v2.json` | `81273f2f7f19ff5e598674542504ed012d96c4db7766224b7299a8351fd027ff` | 23成员产品、像元、OSM及局部接河补证 |
| `results/reduced_delivery_index.json` | `cd82c52cc772ed7702a6f4452f4bfbbe5c9a092bbbeeed46d356d09709a4a7dc` | 93文件与60缓存／来源绑定 |
| `exports/propagation_v1/bundle.json` | `aeafa98159440c675eaae00b2cbd7afec21b31b92a2511f8cb3ed988594ad9e7` | 6个D-Claw情景、42目标、40成员 |
| `exports/propagation_handoff_v1.json` | `ef63555c5decb383a66eeb01ef48a7cfe1c1a29ec52cd435a9ed55a801ba2c16` | v1同40成员，仅结构化input_version；主参谋已交Q3作部分背景 |
| `exports/propagation_v2/bundle.json` | `2a54e77d811faa8d949f92a2e45788751122517b6e91839ca8742cda20ea88a4` | compact S／ST两例14目标、39成员 |
| `exports/propagation_v3/bundle.json` | `150c72537ee162d29cc2e20e3e31183df1915f64999234789e1875d368c09b9c` | fullmask三例21目标、66成员；主参谋已审读并交Q3 |
| `exports/propagation_handoff_v3.json` | `9bb9fb3cd4242e728d22412dbea0191853307c7c647cf5bd3c607110053ccee1` | v3原66成员加独立体积语义注释，共67成员 |
| `exports/compact_delta_v1/bundle.json` | `28c67deb49d694e992c005365cf19c73d1db31a89126f64dbe8b6973adba61cb` | SH／STH两例14目标、48成员 |

v3适配已给主参谋路径／SHA，其消费者receipt以主参谋记录为准。主参谋已核验compact delta全部48成员／14目标并交Q3，consumer SHA256 `044a9a08ce09e8b2b5470a6a4351942fb08054e52e9728e2bb4d51a2295841ac`；四机制映射已齐。v4包含相应完整结果。fullmask原case继承的 `expected_reference_grid_volume_m3=13878000` 是旧h15基线参考；实际输入／解析使用 `release_grid_volume_m3`，S约51.755729Mm³、ST约31.184139Mm³。注释 `exports/propagation_handoff_v3_annotation.json` SHA256 `1b4db70b8a19b92860267b14912ed435a89624e8db1d8a9df4c84c541ab87f39`，没有改raw case、execution或重跑。

## 主要比较结果与限制

| 路线 | 本轮实际完成 | 可用于论文的证据与限制 |
|---|---|---|
| 简化1D／2D | 24＋10个区域情景均1800s，另6组13配置基准 | 含边界项体积账最大相对残差8.05e−16；陡坡薄流速度系统偏低，区域计时资格false，34例不进入到达包络 |
| r.avaflow单相 | 10个厚度／摩阻／xi／CFL／网格情景 | 120m参考汇流(420.9,441.3]s，内部预算−1.0263%；CFL减半变为(461.0,480.7]s，60m参考(540.1,560.8]s且预算+11.5057%；未建立收敛，不能因加细或低残差接受 |
| D-Claw | 120／60m参考、零初压、低固相、高渗透及120m扩域，共9例 | 原域80s已触边；扩域到口岸仍(160,180]s且保存边界全干，但终态M−4.1473%。273帧raw审查排除简单解码／hm混淆；逐步预算归因仍缺 |
| 复合固体＋水 | RI参考、drag／VM两项关闭、全岩配对，共3例 | 原生内部预算约−10.3010%／−1.9841%／−13.1455%；P2全程0，保留相厚和水份额过程；不解岩冰相对运动或熔化，同体积并非同质量干预 |
| Q2映射 | compact四例＋fullmask三例 | 完整lineage与原始命中／未达；compact内部预算约+11.67%至+21.37%，全部预测接受false；源区未启动情景仍明确if_released |
| 有界夹带 | 120m参考匹配1m床层对照1例 | 容量9.5472Mm³，实际夹带5.61843Mm³；新增质量单列后内部残差−1.1572%。零夹带／夹带两例终态静止集合均0，不能称永久沉积 |

30项必跑分解为单相10＋D-Claw9＋Q2映射7＋复合相3＋夹带1。通用2700／1850／1000代理仅作诊断；7个未运行代理按材料适用性排除，不能把1850摩擦性固体称纯冰。直接917冰／1000水不适用固定阻力密度因子，合法复合映射也不自动具有质量或预测资格。

地形是可追溯Copernicus编辑DSM，主体采集2011—2015、EGM2008，不是2026事发裸地；源、路径、口岸与OSM实体仍为候选。三条完整路径20.70／21.42／21.66km，局部接河709.7—939.4m，不强制凑文献22.8km。光学47天配对变化受预设SCL／反射率／NDVI规则约束，事后雪冰或暗区不能独立圈真实失稳面。

最终光谱探索比较为40个已完成二维模型、160条统计；此前role筛选漏掉11个已登记角色家族已显式修正，29模型旧表保留，见 `sources/optical_role_filter_correction.json`。阈值、掩膜、分母及域均未调整；它不提供独立事件精度或参数择优。

## 论文组织与跨问接口

建议以单相120m sf0参考和完整同框架对照为主展示，D-Claw扩域孔压过程及RI复合固体／水为结构挑战，reduced为守恒而计时失真的数值反证。选择依据为解释性与对照完整性，最终采用由队员审视，不能宣称复杂度已转化为精度增益。详见 `MODEL_COMPARISON.md`、`EVIDENCE_REVIEW.md`、`PAPER_OUTLINE.md`、`QUESTION_REQUIREMENT_MAP.md`。

所有传播时间相对bulk release。首次机械启动→成规模释放延迟为null，绝对释放UTC、起报／发布时间及历史可用截止未知；不能默认零延迟加到Q3启动预测。目标为注册100m缓冲内格心总厚≥0.1m首次保存命中，括号记录前一保存帧与首次命中，真实时刻取原生时间。未达限定实际计算时域，有限时未达不代表永久安全；无概率权重，不生成95%覆盖率。

10张根比较图均已实际打开并哈希登记于 `results/comparison_visual_review.json`。相图、水份额与相体积为模型状态，不是观测分选或相变；高摩阻约380506m³静止残余仅为实际1802s的阈值统计。原生请求1800s与实际1800—1802.4s末帧分列，越过1800后的命中不倒算作1800以内。

## 复现、审计与交付检查

完整命令见 `REPRODUCE.md`。`results/replay_execution_comparison.json` 记录实际安全复跑1d_P1_ref与2d_ref_120m，全部数值场和物理summary一致；2项复现不增加新模型或独立事件。50个native重放计划完成哈希／shell检查，额外完整native复跑为0。50组实际控制已索引，22组早期adapter起点快照缺失明确保留，不能用当前源码补造历史哈希。

最终196项artifact／接口检查已实际通过，原环境收尾五组检查已通过。检查和冻结使用原44包环境，复核顺序为：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/validate_round3.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/freeze_round3.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/validate_round3.py --check-manifests
```

`results/validation.json` 记录最终artifact／接口检查；`source_register.json`、`input_manifest.json`、`cache_manifest.json`、`output_manifest.json` 记录交付字节。冻结前脚本再次只读核对最终绑定并检查扫描期间无写入，冻结后只读校验完整路径集合。解释器／Numba缓存及局部venv排除规则显式登记。完整性通过只确认该研究包可复核，不授予物理精度或预测资格。本轮仅本地提交，不push，提交身份以Git记录和最终交付消息为准。

联合审查下一动作是队员确定论文展示与科学采用范围，主参谋按版本把Q2父情景与Q3时延接口联接。若今后申请定量预测资格，仍需原生逐步预算与收敛、独立释放／到达标签、事件时期源面／地形／设施以及物性观测；这些作为后续证据缺口，本轮不再扩扫或拟合文献时长。
