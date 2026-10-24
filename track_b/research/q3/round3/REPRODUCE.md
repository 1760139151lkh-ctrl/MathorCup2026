# Q3 第三轮复查与复跑

唯一执行根`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3`，分支`codex/track-b-q3-r3`。共同基线`904d7257b899b9f71d1ac9e0eab7479e459eab52`，725冻结文件清单SHA`fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`。本轮没有安装依赖，使用自己原Python3.12.14／44包环境；最终版本清单在`results/runtime_environment.json`，依赖锁仍为公共原锁。

## 先复查封存字节

在该根目录执行。第一条只读核验输入、输出与实际大缓存，不重新拟合；缺失缓存明确报错。复现需要Git研究包与本问缓存，不能只复制根摘要CSV。

```bash
track_b/.venv/bin/python track_b/research/q3/round3/scripts/finalize.py --verify-only
track_b/.venv/bin/python track_b/research/q3/round3/scripts/verify_interfaces.py
```

`verify_interfaces.py`会重新写本轮核验报告时间戳；因此第二条之后输出清单字节会变化，应该在审查副本运行。`exports/event_bundle.json`、`event_bundle_v2_external.json`、`phase_evidence_bundle_v3.json`是一次发布不可变文件，构建脚本遇已存在即拒绝，不需要重复发布。最终清单不包含自身，validation与output manifest互相不成环；其SHA由包含它们的Git提交绑定。

标准环境／冻结输入检查会写本轮`workspace_verification.json`；最终副本已保存在`results/workspace_exit_verification.json`。它确认技术环境与所有权，不验收科学模型。

```bash
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round3 --question q3 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q3 --expected-base 904d7257b899b9f71d1ac9e0eab7479e459eab52
```

## 完整输入与缓存

`results/input_manifest.json`绑定输入、协议、配置及来源快照；`source_register.json`保留实际URL、版本、获取UTC、读取范围、状态与限制。`cache_manifest.json`实际逐字节检查本问缓存，不只是登记路径。`raw_prediction_index.json`逐项绑定所有B/C原始预测索引和A全逐参数Parquet／三先验gzip。共同根CSV只是主结果投影。

大原件／全预测只在`/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/`，不纳入Git。联网获取只在缺少原件时使用：`acquire_weather.py --collect`、`acquire_deformation.py --collect`、`acquire_waveform.py --collect`；默认使用现有缓存离线解析。Stampa固定作者CSV获取见`SURVIVAL_EVIDENCE.md`；`acquire_phase_evidence.py`无参数运行，USGS XML存在时离线读，缺少时获取固定产品。它没有`--help`模式。这些命令会重新写规范化／审计，精确封存交付应先复制工作包，在新版本中复算，不能改已绑定的冻结输入。第三方许可与引用条件分别保留。

## 实际模型复跑

以下均已实际运行。长运行建议只给本进程设置`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1`；绘图采用`MPL_IGNORE_SYSTEM_FONTS=1`，避免本机系统字体扫描错误。代码已默认使用本问缓存内Matplotlib配置，不改公共环境。

机制A适配，完整设计与64代表分别保留：

```bash
track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_a.py --full-design --bundle track_b/research/q3/round3/inputs/q2/mechanism_bundle_q2-r3-mechanism-v1/bundle.json --states track_b/research/q3/round3/inputs/q2/mechanism_bundle_q2-r3-mechanism-v1/files/results/state_trajectories.parquet
track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_a.py --full-design --bundle track_b/research/q3/round3/inputs/q2/mechanism_bundle_v2_q2-r3-mechanism-thermal-refinement-v2/bundle.json --states track_b/research/q3/round3/inputs/q2/mechanism_bundle_v2_q2-r3-mechanism-thermal-refinement-v2/files/results/refined_v2/state_trajectories.parquet --outdir results/engine_a/v2
track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_a.py --full-design --bundle track_b/research/q3/round3/inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1/bundle.json --states track_b/research/q3/round3/inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1/files/results/analytic_thermal/state_trajectories.parquet --outdir results/engine_a/analytic_erfc
track_b/.venv/bin/python track_b/research/q3/round3/scripts/weather_replay.py
track_b/.venv/bin/python track_b/research/q3/round3/scripts/numerical_checks.py
```

完整实际逐issue的FD状态／天气耦合命令、版本配对及导出审计见`MECHANISTIC_REPLAY.md`。默认`mechanistic_replay.py`运行FD v1，`--bundle/--output-dir/--experiment-id`绑定FD v2。解析热用独立消费端，计算前协议及最终命令见`results/mechanistic_replay/analytic_erfc/ANALYTIC_REPLAY.md`和`RESULTS.md`：

```bash
track_b/.venv/bin/python track_b/research/q3/round3/results/mechanistic_replay/analytic_erfc/replay.py
track_b/.venv/bin/python track_b/research/q3/round3/results/mechanistic_replay/analytic_erfc/postprocess.py
```

原解析目录拒绝覆盖，完整复算用其`reproduce.py --output-dir track_b/research/q3/round3/results/mechanistic_replay/analytic_erfc/reproduction_001`写新子目录。不要只运行适配器就声称已重算天气机制。历史首发未知的业务轨拒绝、四种假设延迟和理想轨独立保留。

B真实变形：

```bash
track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_b.py
```

完整规范化、单位、B窗口／噪声和Stampa挑战命令见`DEFORMATION_EVIDENCE.md`；`engine_b.py`是最终固定函数源，`common_anchor_comparison.py`使用同数学重新计算相同C锚点。

C主路线和数值敏感性：

```bash
track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_c.py --exclude-record-age --anchors-only
track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_c.py --exclude-record-age --max-nodes 1024 --anchors-only
track_b/.venv/bin/python track_b/research/q3/round3/scripts/engine_c.py --anchors-only
```

旧含记录年龄全滚动／行政截断的实际源是`sources/survival_engine_c_record_age_aade36485d977136b5ede96e0dd729ef0235756fe6d5cf48435a525c442e9e88.py`，用该快照而非后来修改的源重跑。分别无参数、`--max-nodes 1024 --anchors-only`、`--administrative-censor-fraction 0.5`、`--administrative-censor-fraction 0.75`。所有7视图的输入／缓存／执行源校验与196次外层最终拟合检查见`engine_c/final_packet_validation.json`。进一步说明见`SURVIVAL_EVIDENCE.md`，旧全表数百万行在内容地址缓存，未删弃权或无事件质量。

同锚点比较、投影及图：

```bash
track_b/.venv/bin/python track_b/research/q3/round3/scripts/common_anchor_comparison.py --c-predictions results/engine_c/no_record_age/anchor_predictions.csv --outdir results/common_anchors_no_age
track_b/.venv/bin/python track_b/research/q3/round3/scripts/common_anchor_comparison.py --c-predictions results/engine_c/record_age_anchor_reference/anchor_predictions.csv --outdir results/common_anchors_record_age_challenge
track_b/.venv/bin/python track_b/research/q3/round3/scripts/integrate_results.py
track_b/.venv/bin/python track_b/research/q3/round3/scripts/plot_results.py
track_b/.venv/bin/python track_b/research/q3/round3/scripts/plot_comparison.py
track_b/.venv/bin/python track_b/research/q3/round3/scripts/compare_a_versions.py
```

已实际执行的Q4通用早交严格配对（结果42拒绝、0合法源模型对应）：

```bash
track_b/.venv/bin/python track_b/research/q3/round3/scripts/join_propagation.py --bundle track_b/research/q3/round3/inputs/q4/propagation_handoff_v1_q4-r3-propagation-v1-metadata-handoff/bundle.json --expected-sha256 ca2687f43fbca865fea8556435c9765ccc429fed4bf3f05dd5df8f79deb2fda0
```

最终Q2映射版若随后分发，只追加对应adapter／join与清单；不能用v1通用情景字符串猜父模型，不把机械到释放的未知滞后置零，也不把无启动父情景的if-released传播转换为启动。

最后按实际产出目视检查图并登记SHA，再运行`finalize.py`；不能自动把“生成图片成功”写成“已看图”。运行时间戳、请求头和审计日志为运行相关元数据，不保证跨平台字节相同；模型输入原字节、固定seed、状态／概率数值和分母才是科学复跑对象，浮点容差与具体代码版本由各数值检查绑定。任何新输入都应追加版本和清单，保留本轮原包。
