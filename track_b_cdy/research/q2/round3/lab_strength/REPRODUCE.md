# 增量复跑

唯一目录 `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2`，原 Python3.12.14、44 包精确锁，不安装/重建环境。原官方 ZIP、PDF 和文本均已在本问来源目录；全流程离线。原始试验所有行都保留，候选和分组见 `PROTOCOL.md` 与拟合前审计修订。机器结果的已执行命令如下：

```bash
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/audit/scripts/extract_canonical.py
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/model/competition.py
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/model/author_reproduction.py
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/model/summarize.py
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/model/make_figures.py
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/independent_review/review_lab_strength.py
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/verify_workspace.py
track_b/.venv/bin/python track_b/research/q2/round3/lab_strength/finalize.py
```

独立来源闭式探针命令见 `literature/STAGE1_WEIGHT_NOTE.md`、对应脚本和审计 JSON；正文及补充 16 页图像的渲染/实际阅读另有记录，不把脚本生成图当成已经人工打开。独立 review 先用标准库解析 ZIP/XML 再另行复算，没有复用父拟合函数。主计算固定 seed26082418，共 32000 次 bootstrap；单元内方案假定不同试验独立，整标签方案假定标签代表相关岩对，两者的限制均保留。

`verify_workspace.py` 调用原标准 `stage4_workspace.py` 的同一套五组检查，仅把报告保存回调重定向到本增量，避免覆盖原已分发的 `round3/workspace_verification.json`。原标准函数打印的旧目标路径由重定向说明纠正；实际报告为 `lab_strength/workspace_verification.json`，代码/结果已登记。`capture_baseline.py` 首次记录 a4a034e 的 1104 个既有 tracked 文件；后续运行只验证，不能把新文件重新当基线。

`finalize.py` 不重跑实验、不写原文件；核对全部旧 tracked 字节、原 220 项输出和七个核心包、原环境与新输入，生成独立增量 manifest/bundle。清单不自包含，HANDOFF 和 bundle 由 Git 绑定或显式外部哈希绑定，避免循环哈希。源码若变动，重新执行受影响计算和独立复核；图若重绘，重新实际打开并登记新哈希，然后再 finalize。

数值 CSV、固定种子 bootstrap 系数和绘图数据在此环境可复现；运行时长、审计 UTC 与 PDF 创建元数据属于运行记录，字节可能随复跑变化。复跑得到等价数值后仍须重建相应增量哈希，不能改写旧七包或原 220 项清单。研究终点是外部适用性和条件挑战依据，不自动执行本地 Q2/Q3 引擎。
