# Q2第三轮本地复跑

唯一根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2`。全部命令显式在此目录执行。原环境`track_b/.venv/bin/python`为Python3.12.14、原44包精确锁；本轮未安装/升级包、未改原锁、无远程计算。局部快照在`config/environment_lock.txt`与`config/environment.json`。不执行下载的外部源码，只有本问作者脚本是运行入口。

## 顺序

```bash
track_b/.venv/bin/python track_b/research/q2/round3/sources/strength/build_evidence.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/acquire_sar_evidence.py --offline
track_b/.venv/bin/python track_b/research/q2/round3/scripts/run_experiments.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/check_interfaces.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/validate_engine.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/analyze_identifiability.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/analyze_robustness.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/analyze_numerics.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/integrate_geometry.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/run_refined_v2.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/make_figures.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/make_figures.py --refined
track_b/.venv/bin/python track_b/research/q2/round3/scripts/run_analytic_thermal.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/review_analytic_thermal.py
track_b/.venv/bin/python track_b/research/q2/round3/scripts/make_figures.py --analytic
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round3 --question q2 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q2 --expected-base 904d7257b899b9f71d1ac9e0eab7479e459eab52
track_b/.venv/bin/python track_b/research/q2/round3/scripts/finalize_packet.py
```

以上数据/模型命令离线；必要原始SAR缓存位于`/Users/maxchen/Documents/MathorCup/research_cache/round3/q2/sar_v1/`，输入清单逐文件含绝对位置/字节/哈希。Q4两个DEM在经主参谋批准的q4缓存，只读引用。Q1/Q3/Q4其余副本只读取本问inputs，不能用嵌套保留的上游活动路径替换。

本轮已追加执行全256细网格及前5时刻敏感参数审查，见`NUMERICAL_LIMITS.md`。复跑全量：`track_b/.venv/bin/python track_b/research/q2/round3/results/refined_v2/full_reference_check.py`；同一结果定向提取：`track_b/.venv/bin/python track_b/research/q2/round3/results/refined_v2/top5_reference_extract.py`。两者不改17成员的v2包。类别全一致但部分时刻/裕度尚敏感，不能把全部数值精度写为通过。

主参谋新增文献组分域对照亦已实际完成，先`track_b/.venv/bin/python track_b/research/q2/round3/scripts/analyze_composition.py --prepare`登记协议，再`track_b/.venv/bin/python track_b/research/q2/round3/scripts/analyze_composition.py --run`计算128新场景；不改原0.2–0.8设计与已分发包。来源/密度单项物理映射/配对结果见`COMPOSITION_SENSITIVITY.md`。

如SAR完整缓存缺失，显式`acquire_sar_evidence.py --online`按已冻结产品选择获取合法公开资产，记录每次正文和UTC；不重试旧认证失败入口。公开原件可能变化/下架，缺失则无法离线重做对应像元诊断，但Git内小裁片、统计和来源仍可复核，不把重下成功当历史可用性证明。Mamot/其他文献原件及PDF核读页已经在sources保存。

## 复现与冻结

v1参数seed260826、256设计点、四机制/两暖端策略，2089小时；8个代表参数索引固定0/36/72/109/145/182/218/255。`run_experiments.py`重算后断言两份已发布v1bundle的成员字节一致，不能用重跑改变已分发模型；若代码、参数或数值格式确需变化，另版。`run_refined_v2.py`是v1粗热网格收敛问题的独立v2，不覆盖旧状态。

可辨识性rank/参数补偿、解析基准、SAR像元统计和几何体积检查已在本轮实际执行；只有新的修改或错误才需要额外重跑。图像重绘后若哈希改变，必须重新实际打开并更新`results/visual_review.json`，再运行finalize。数值输出可在相同锁环境逐字节复现，浮点/Parquet跨版本可能有格式差异，须核对计算值而非篡改旧清单。

清单在最后重建：input_manifest不自包含；output_manifest排除自身、HANDOFF（由Git绑定）、缓存环境与运行诊断。它可包含input_manifest和validation，后两者不引用输出清单，避免循环。finalize只检查/登记现存证据与结果，不联网、不重跑阶段3公共管线、不把验哈希说成独立科学验证。最终HANDOFF记录实际完成和未完成项。

## 量纲与边界

应力kPa、法向厚度/深度m、时间h（传热内部换s）、alpha m²/s、降水条件解释mm/h、融水mm/(°C day)、水储量m水当量、压力水头m、稳定裕度无量纲。释放体积分数和为1，密度kg/m³，速度m/s；体积基于垂直厚度积分，不将法向厚度直接乘平面面积。主参谋分发数据只采纳限定角色，独立本地训练/验证为0。
