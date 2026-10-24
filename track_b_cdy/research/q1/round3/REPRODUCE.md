# Q1 第三轮离线复跑与来源获取

唯一执行根为 `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1`，分支 `codex/track-b-q1-r3`，共同基线 `904d7257b899b9f71d1ac9e0eab7479e459eab52`；冻结清单SHA-256 `fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`（725项）。所有命令先在该根运行。

使用原本树 `track_b/.venv/bin/python`；原44包环境和 `track_b/requirements-lock.txt` 未安装或升级。实际版本另存 `config/runtime_environment.json`。numpy/pandas/scipy/matplotlib使用现有精确锁。本问没有大原始数据、容器或新增venv，也没有远程计算。绘图的可变字体运行缓存固定在允许的q1命名空间 `/Users/maxchen/Documents/MathorCup/research_cache/round3/q1/plot_runtime_v1`，不作为科学输入或分发数据。

## 核验已交付结果

```sh
track_b/.venv/bin/python track_b/research/q1/round3/scripts/finalize_packet.py --verify-only
track_b/.venv/bin/python track_b/research/q1/round3/scripts/independent_numerical_review.py
```

第一条只读验包；第二条重跑数值基准与公式检查，输出其独立审查记录，不重写研究结果。最终工作区技术检查会刷新本轮可变验证记录：

```sh
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round3 --question q1 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q1 --expected-base 904d7257b899b9f71d1ac9e0eab7479e459eab52
```

## 完整离线计算

来源原响应已保存，无需网络。特征v1脚本使用确定性输出并在现有字节不同时拒绝覆盖；需要新定义时另建版本，不修改已分发v1。

```sh
track_b/.venv/bin/python track_b/research/q1/round3/scripts/build_features.py
track_b/.venv/bin/python -X faulthandler -u track_b/research/q1/round3/scripts/run_models.py > track_b/research/q1/round3/model_run.log 2>&1
track_b/.venv/bin/python track_b/research/q1/round3/scripts/summarize_results.py
track_b/.venv/bin/python track_b/research/q1/round3/scripts/write_handoff.py
```

真实计算不是从模型表反推示意图。模型脚本先读取特征/支持，以预登记阈值筛选，运行三条路线、全预定变体、5折留年/45代理块留出及100次年→过程重采样，保存全部候选分数、方向、匹配对象、协方差诊断和折成员。计算日志有阶段时长；不把请求draw次数当有效统计分母。

数值审查会刷新其UTC记录；重算会改变时间戳及相应清单哈希。图像须实际重新打开并更新视觉核验记录，独立审查须绑定新源码/产物，运行validate_results后再生成输出清单：

```sh
track_b/.venv/bin/python track_b/research/q1/round3/scripts/validate_results.py
track_b/.venv/bin/python track_b/research/q1/round3/scripts/finalize_packet.py
track_b/.venv/bin/python track_b/research/q1/round3/scripts/finalize_packet.py --verify-only
```

清单不包含自身；稳定产物清单排除可变工作区绑定/收尾报告、运行日志与pycache，精确范围见清单字段。早交feature_bundle保持版本、文件大小和哈希，输出清单仅作为最终包入口，不包含自身。

## 联网获取命令（复现时使用新版本目录）

实际使用 `evidence/fetch_sources.py` 取得4个公开响应，`evidence/finalize_register.py`记录实际阅读范围、版本和采纳边界。已保存文件与获取UTC见 `source_register.json`、`evidence/access_log.json`。

```sh
track_b/.venv/bin/python track_b/research/q1/round3/evidence/fetch_sources.py
track_b/.venv/bin/python track_b/research/q1/round3/evidence/finalize_register.py
```

这些是本次实际获取方法，运行会再次访问外部并改写当前来源路径。交付后的来源不应覆盖：重获时复制脚本到新的版本命名空间并更改目标目录，再产生新注册表和输入版本。HTTP200前端壳不记正文；获取时间不记成历史available_time。

Q3事件包由主参谋按哈希分发至本问inputs；本问核验及使用范围见 `results/interface_usage.json`，不从其他问活动目录读取输入。它没有新增接受的启动标签或独立灾害样本，故本轮无监督灾害关联支线。
