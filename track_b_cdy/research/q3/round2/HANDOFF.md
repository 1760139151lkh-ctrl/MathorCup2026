# Q3 第二轮交接：单事件审核与固定起报可用性

**状态：本轮有界补证和离线审核完成；收尾工作区验证5/5通过。停止于第二轮联合审查，队员尚未作最终科学采用。**

AI辅助：OpenAI Codex，2026-10-24。执行仅限本问 round2；无模型拟合、真实95%区间或覆盖率结果。

## 执行身份与输入版本

| 项目 | 实际记录 |
|---|---|
| 唯一执行根 | `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3` |
| 分支 | `codex/track-b-q3-r2`；首轮分支保留 |
| 共同基线 | `76ee1532cb2acf36fb82c5f4749a4288507dfcc8` |
| 冻结清单 | `track_b/audit/stage4/round2/baseline_manifest.json`，565文件 |
| 清单SHA-256 | `c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d` |
| 合同 | `stage4-r2-v1`；主对象为源区首次机械启动，具体真值未接受 |
| 环境 | 本工作树 `track_b/.venv/bin/python`，Python3.12.14、44个精确包；未安装／升级 |
| 启动验收 | 2026-10-24T05:56:52.810096Z，5/5通过；快照见 `results/workspace_readiness_at_run.json` |
| 来源获取 | 2026-10-24T05:58:45.822571Z 至06:07:32.188380Z；早期USGS日志只记录retrieved_at，未补造起止 |
| 最近离线审核 | 06:12:32.178465Z 至06:12:32.697722Z；完整UTC、解释器、根目录见 `results/summary.json` |
| 计算直接输入 | `results/input_manifest.json`，28文件；SHA-256=`b634b06ab3fba523ef91fc97915830c6f7ae122df330f2e09766d261e0717791` |

计算输入登记包含冻结清单、契约、实际读取的已有事件／预报文件和本轮来源正文及请求日志。代码和最终报告由输出清单绑定。首轮54候选目录未扩扫；首轮研究包及公共数据没有重写。

## 结论与采用边界

| 审核项 | 本轮结果 | 采用提案及影响 |
|---|---|---|
| us7000tc90 | reviewed landslide，2026-08-26T06:00:35Z；时间误差2.64秒90%；水平误差20km90%并保留椭球参数 | 可作较晚区域滑坡的事后背景；排除主案例首次机械启动真值 |
| 与原事件关系 | 不同物理子事件、区域序列有官方相互说明；严格因果关系与统计独立性未知 | `strict_causal_link=null`、`independent_event_group=null`；不自动增加独立样本 |
| 首次机械启动映射 | 原us7000tbwb仍为目录代理；新us7000tc90不对应首次启动 | 主对象精确时刻仍为null；目录误差同未知代理偏差分列 |
| 固定GFS对象 | 起报2026-08-25T18Z、f009；对象Last-Modified=21:38:07Z；ETag同首轮六条Range一致，索引哈希一致 | 对象元数据／对应关系可采用；未证明首次公开可用 |
| GDEX条目 | 相应目标显示Date Archived=2026-08-27 | 属另一归档渠道，时区／时分秒／完整二进制同一性未知；不作为业务首发时间 |
| 历史可用门禁 | `available_time=null`；灾前上下界未建立 | `unknown_not_eligible`；未认证实时历史回放 |

新增接受训练事件=0、新增接受独立验证事件=0，当前总数仍为0；`real_coverage=null`。目录钟差11,305秒不是传播时间；目录中心距离约7.21km不是精准源区间距。原误差保持90%语义，没有转换成95%未来预测区间。

## 文件索引

- [EVENT_REVIEW.md](EVENT_REVIEW.md)：USGS版本、机制／阶段、原误差、关系及采用提案。
- [AVAILABILITY_REVIEW.md](AVAILABILITY_REVIEW.md)：固定对象、历史可用证据与未知边界。
- [ROUTE_UPDATE.md](ROUTE_UPDATE.md)：可继续协议工作、正式分析阻断项及跨问提案。
- [us7000tc90_review.json](results/us7000tc90_review.json)、[mechanical_initiation_mapping.csv](results/mechanical_initiation_mapping.csv)：事件卡及3行对象映射。
- [gfs_f009_availability_chain.json](results/gfs_f009_availability_chain.json)：单起报证据链与门禁。
- [source_register.json](results/source_register.json)：9条官方请求记录，URL／版本／UTC／实际阅读范围／正文和日志哈希；原快照及日志在 `sources/`。
- [evidence_checks.json](results/evidence_checks.json)、[summary.json](results/summary.json)：10项证据一致性检查及机器摘要。
- [input_manifest.json](results/input_manifest.json)、[output_manifest.json](results/output_manifest.json)：输入／最终产物哈希；二者均排除自身和彼此，避免循环摘要。输出清单也排除可变运行绑定／验收原件，其执行时副本已列入输出。
- [review_evidence.py](scripts/review_evidence.py)：默认离线审核；缓存核对URL、方法、状态、预期路径、大小和正文哈希，失败响应仅保留日志，不能充当可用证据。

无新增图像，本轮不需要图像质量验收。没有新GRIB正文传输，没有重新运行首轮GRIB处理、72条延迟情景或20项机械测试。

## 复跑与验证

所有命令均在上表唯一执行根运行，并使用自己的venv。默认复跑不联网：

```sh
track_b/.venv/bin/python track_b/research/q3/round2/scripts/review_evidence.py
```

实际有界获取曾执行 `review_evidence.py --collect`。现有9条日志与正文齐全时只校验缓存；缺失时仅填本轮限定官方小体量来源。GRIB精确对象只允许HEAD，索引允许有界GET，不扩大事件／起报。网络失败留日志并终止作为可用来源，不能把认证或错误页面写为证据。

文档完成后重建并逐项复核最终产物清单：

```sh
track_b/.venv/bin/python track_b/research/q3/round2/scripts/review_evidence.py --finalize
```

启动和收尾同一验收命令：

```sh
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q3 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q3 --expected-base 76ee1532cb2acf36fb82c5f4749a4288507dfcc8
```

已完成的离线审核10/10通过；这是证据一致性与有界查询核对，不能解释为科学模型通过验证。独立只读复核已检查缓存身份、目录误差、因果／独立性分列和历史可用边界；没有发现遗留实质问题。

收尾工作区验证：2026-10-24T06:17:07.003453+00:00，5/5通过；565个冻结输入哈希保持一致、环境及文件责任范围通过。实际报告另存 `results/workspace_exit_verification.json`。最终manifest在本文件定稿后生成，最终提交完整哈希与manifest哈希在聊天交付中报告，不向本文件写入自身提交号或循环摘要。仅本轮本地提交，不push。

## 下一动作与跨问交接

由主参谋审查后统一发布 [路线更新](ROUTE_UPDATE.md)：Q1事件窗口、Q2首次失稳同较晚堰塞阶段、Q4源区误差及早期／较晚几何须分开。研究窗未直接修改公共标签、状态、契约或他问文件。

已排除新条目作主标签；真正阻断正式预报验证的是首次机械启动真值及独立事件未审核、历史可用证据不足。仍可继续对象／截止协议、事件隔离评价设计和论文证据局限整理。进一步读取波形、扩查目录或追逐历史分发日志均需后续派单；本轮任务已经有可复查结论，停止于联合审查。
