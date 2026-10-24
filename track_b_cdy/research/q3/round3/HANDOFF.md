# Q3 第三轮交接：三引擎研究包完成

本轮Q3本地计算、比较、来源／缓存核验、图表、论文提纲及通用Q4首版配对均已完成。Q4正在计算的Q2映射新版尚未交付，不把它写为已关联；收到后仅追加release适配／join和相应清单。科学结论最终采用仍由队员联合评审。

唯一根`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3`；分支`codex/track-b-q3-r3`；基线`904d7257b899b9f71d1ac9e0eab7479e459eab52`。725冻结文件清单SHA`fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`。收尾原Python3.12.14／44包环境5/5通过，未安装依赖；报告`results/workspace_exit_verification.json`。仅本问round3与q3缓存写入，本地提交、不push；提交号由包含本文件的Git提交与最终消息给出，避免自引用。

## 审阅入口

- `exports/research_bundle.json`：最终主结果、实际原预测索引、输入／缓存／来源、图审查、比较与复跑文档，逐文件path/bytes/SHA；不包含自身或最终validation，后者由同一提交绑定。
- `results/validation.json`与`output_manifest.json`：最终技术验包及全输出字节，不等于科学95%验收。
- `MODEL_COMPARISON.md`：实际三引擎结果、主候选／挑战、适用层级与具体分母；`REQUIREMENTS_MAP.md`逐条映射题意。
- `EVIDENCE_REVIEW.md`、`PAPER_OUTLINE.md`、`REPRODUCE.md`、`AI_RESEARCH_LOG.md`：来源／迁移限制、论文可用内容、实际命令、AI贡献和队员采用边界。
- `results/predictions.csv`：20,502行＝主解析热参考均匀假设先验20,250＋B/C精确同锚点252；其他先验与全部原生／滚动行均在`raw_prediction_index.json`精确绑定，未丢弃权或不启动质量。评价／分折／区间／先验／配对表分别保留，条件情景与外部迁移不混池。

## 完成的研究与关键结果

**A机制／天气：** Q2粗FD、0.125m FD和解析erfc三版完整2048首次过阈适配，各2048记录／3375预测。三版类别均137有限、248左删失、1663随访内未越阈；按base情景配对，粗FD至0.125m最大46.819h，0.125m至解析最大19.07238h，解析至0.0625m参考最大0.34708h。全2048 FD附加参考仍有10条未达0.02裕度目标，不当严格误差界／概率范围。

三版逐issue天气均实际运行同75×10×2048，各1536000参数结果、60750三先验预测、20250范围。FD原索引`results/mechanistic_replay/delivery_index.json` SHA`404bba4b1a429d16ac154fd73549fe2e69aff05fd5be6bc54c89a0030e69a4a7`保持原字节。解析新目录索引`results/mechanistic_replay/analytic_erfc/delivery_index.json` SHA`ede475a5a18d78c56503d7154aa092b69b37345db9b6380cf1ce161c219e16e1`，31文件；23模型／因果／谱系检查、7导出检查通过。解析原预测SHA`a3dc1602e9d4ea7c80173286f5e78e5ef6cc15b2e00a0b0fb5d33f5ff3fa122d`；1536000参数Parquet SHA`fd557599f6fa54ad21bd7a44dd19aa74f5578ce73533db1ad8aeef19de2688d5`。

历史热记忆、损伤／储水暖启动及首次启动风险排除均保留。所有历史first-availability仍unknown；业务轨拒绝，四延迟假设与理想轨分开。唯一窗口内非零支持为S-p0149一个物理设计，零宽条件区间是离散退化。实际天气仍可改变状态，96同随访终点对照最大温差2.78954°C／裕度差1.07956／压力差约40.87kPa；17280个概率对不变不能解读为天气无效。原设计与文献组成候选均非实测概率先验。

**B真实变形：** 主13终末失稳物理组、75588完整原预测，55/55技术检查。小时72h共同有效8070机会／13组，IV/SS Brier0.169775/0.207600；原生末48h共同1685机会／10组为0.450391/0.421959，排名反转。原固定提前24h／预测72h的独立事件全标签包含IV3/13、SS6/13，分别10/13、11/13发有效概率。Stampa725日1右删失挑战另保留；单站不足认证一般误报率。

**C风险／生存：** 13失败＋1真实右删失组，已知生存暴露56381.8406h，标签不确定带144.35h。发现记录年龄受事后180日选窗污染后，重新拟合无年龄全14组LOSO，512/1024各1608固定锚点；RBF raw主候选，48/72h自身10个可判定组Brier0.373917/0.307760，节点敏感性最大约0.002959。旧含年龄3968856行降为截窗敏感挑战并绑定aade执行源快照；行政50%/75%各1879008/2910000行不增加真实稳定站点。7视图输入／缓存核验、196外层最终拟合均通过，图审查随包。

**B/C公平比较：** 两套特征域各252行，6×14×3；主无年龄表按完全同传感器、同issue/H重算B。72h只有13组可发布，Weiss仍占14案例总分母，保留弃权。比较分数只用共同有效概率子集；例如SS/RBF48h8组0.242887/0.308827，72h8组0.346922/0.243395，无统一冠军。C72h全标签包含0/7、相交6/7，发区间条件下6/6；标签上界常恰在end−H锚点时域末端，连续条件97.5%分位小于H，不能把全包含0直接说成一般精确真值覆盖失效。B原独立固定提前24h事件能力另主报。共形只审计组数上界和秩，实际独立共形校准未执行，有限95%保证不支持。

## 可供其他问使用的冻结包

- 本地事件v1 `exports/event_bundle.json` SHA`075b149214b5c9a8827af45af221ee6ee6b6428090e6d9337afb1943698d2faf`。
- 外部事件v2 `exports/event_bundle_v2_external.json` SHA`359f1e9868a1a63125296fd43e37ea22928815396a76d529669f8332baa8bbde`；9文件／15登记外部物理组，主13失败＋1右删失，Veslemannen主评价排除。
- 阶段证据v3 `exports/phase_evidence_bundle_v3.json` SHA`db5f1b6c1f4c04a7233b8b964e18dfa90b45c061a24009247aeef562cbe98898`；13文件。USGS54 manual picks均远台，无KKN／EVN。KKN连续50min／50Hz／150001样本，10/10 QC，所有九频带阈值组合保留；02:52后增强与更早高频候选并存，69片段不是69事件。仍不接受机械真值。miniSEED内部样本由官方GeoCSV提供，独立核对仅头／blockette／STEIM2端点；未去仪器响应。

三个早交包字节未改。本地主对象首次机械启动训练／真值／覆盖验证事件仍0，实测95%覆盖为null；外部终末崩塌不能替代它。

## Q4交接现状与下一次增量

通用首版`q4-r3-propagation-v1-metadata-handoff` SHA`ca2687f43fbca865fea8556435c9765ccc429fed4bf3f05dd5df8f79deb2fda0`，40文件已读哈希，6完成DClaw／42目标。严格join实际42拒绝、0合法对应、0绝对到达，完整上下文和拒绝原因见`results/arrival/propagation_v1/`。扩域参考口岸为bulk release后(160,180]s，目标空间／阈值、边界与数值限制保留；数值质量／全竞争仍未终审。

最终Q2映射版到达后，实际字段为base_scenario_id/upstream_model_id/upstream_parameter_version/release_mapping_version/geometry_version。须显式对照Q2冻结release表参数值、mask／几何、分辨率及新解析onset版本，不以别名差异拒绝合法谱系或以相似字符串接受非法谱系。即便映射通过，机械→bulk-release滞后未知，主绝对arrival仍null；no-start父保留if-released反事实。届时仅新增adapter／join和清单、必要文档及增量本地提交，A/B/C已完成计算不重开。

原始数据、全部真实预测缓存、版本和运行源均可复查；队员负责核心机制解释、参数采用和论文最终陈述。
