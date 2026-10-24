# Q2 第二轮交接：速度链有限结论与指定VV访问失败证据

日期：2026-10-24（America/New_York）。**第二轮已执行，停在联合审查点。** 本轮得到可采用、排除和仍未知的有据结论，没有改原速度、首轮研究包、公共标签/QC或正式模型。

## 执行与版本

- 唯一执行根：/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2；分支codex/track-b-q2-r2，首轮分支codex/track-b-q2-r1保留。
- 共同基线：76ee1532cb2acf36fb82c5f4749a4288507dfcc8。
- 本轮冻结清单：track_b/audit/stage4/round2/baseline_manifest.json，SHA-256为c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d，共565项；未覆盖首轮清单。
- 复用本worktree既有Python3.12.14/44包精确锁，没有安装、升级或修改系统。主参谋启动5项检查通过；交接前再次运行同一round2验证器，见workspace_verification.json。
- 所有本轮新增/修改仅在本问round2目录；input_manifest.json记录实际35项输入/来源/批准副本，output_manifest.json逐项绑定交付。清单均不包含自身；输出另排除HANDOFF和运行缓存，交接正文由Git提交绑定。

## 结果索引

| 入口 | 本轮结果 |
|---|---|
| VELOCITY_REVIEW.md、results/velocity_definition_chain.csv | 16条速度定义/本地链证据，区分原始声明、固定官方代码、推断和未知 |
| REMOTE_ACCESS_REVIEW.md、results/pair_access.json、network_budget.json | 唯一轨道121两景VV实测均401，各96字节，总192；无TIFF/像元 |
| results/aoi_pixel_support.csv、aoi_support_check.json | 已批准search_only AOI的两景离线足迹支持；均相交、不完整包含，三个图上候选锚点在两足迹内 |
| ROUTE_UPDATE.md、results/parameter_evidence_update.csv | 9项采用/排除/未知及下一动作，未重写首轮参数表 |
| results/result_index.json | 已解决、仍未知、当前阻断和可继续项的机器摘要 |
| results/source_register.json、sources/velocity_source_register.json | 官方URL/版本/UTC/实际阅读范围/文件哈希；PDF核读页与当前图哈希分列 |
| results/network_guard_checks.json、INDEPENDENT_REVIEW.md | 7项离线守卫夹具及独立内存/几何复核；不计科学验证样本 |

## 速度链结论

**可采用为有限背景解释：** 原NC无time维，声明2014—2024气候态、meter/year、2018-01-01截距。固定NASA/JPL代码8a39afbd8279d94c4b1d3e7b99b722527f66a85c的默认年份/截距语义一致，并可直接读到先对年度分量作加权线性拟合、再合成气候态模长的步骤；还存在截距两侧观测不足时退回分量加权均值的分支。没有执行外部生产脚本。

**版本与链仍未知：** NSIDC v2指南描述2014—2022/120m，不能单独认证本地v2.1/2014—2024。原产品URL/格点/生成脚本、改名映射、统计/拼接/合成/重采样顺序、NoData和分量旋转缺少本地证据。30m只是本地声明的目标间距。官方当前代码可实现某定义，不等于本NC确用该提交生成。

**已排除一条处理原因：** 阶段3脚本仅读取/排序并检查raw/decoded相等，没有重新生成速度，因此不能把本地已有残差归因于阶段3速度重采样。

本轮直接引用冻结首轮结果，没有重算全表：最大abs(v-hypot(vx,vy))为0.4946554486149263m/year，7142/7152格超过算术容差1e-4。残差成因仍unknown；插值、先合成后平均等只能作待核实假说，原值不替换。

给Q4：各原字段仅作声明的历史背景探索，v与重算模长不互换；不能当2026初速度、加速或已验收流向向量。最小后续证据是原对象ID/版本/哈希、生成参数日志、原/目标CRS及分量旋转、必要少量匹配原生格点；没有这些时本项以unknown结束，不扩扫或联系作者。

## 搜索AOI与访问结论

已接收主参谋正式分发的q4-r2-fig1-search-v1，仅用本问inputs内副本：

- search_aoi.geojson：14db392ea6d318c2df34152af950b227653fd1f938aed1f4aa9eedf92c29579f。
- search_aoi_evidence.json：78ff69266903ee77626679b0bba542ec36f1e73e3d39581909543d63ba262d14。
- advisor_aoi_review.json：5be13b550bcf9f3f06dae87ac5e6a5cc731bf569af08331da27d46aaf9deda5e。
- 另含georeference_review.json和controls CSV，均按advisor记录校验；没有自行跨工作树取临时几何。

两景目录足迹都与约175.36km²搜索AOI相交但不完整包含；三个回溯地图符号锚点在两足迹内。原图投影/基准/定位精度未知、纬度无独立留出，2km余量不是误差界；生产者pending原字节保留，独立advisor记录只确认search_only。没有将其用作释放多边形、物源体积或灾前状态。

只对固定2026-08-19/08-31下降轨121的VV资产各发一次Range bytes=0-16383请求；两次均401 JSON，正文各96字节，累计192/134217728。没有TIFF、像元、配准、地形可见性或变化解释。401不证明提供方不支持Range。AOI到达后仅离线核对足迹，网络项没有重试或扩选；没有静默缩小AOI。

字节账统计显式消费的响应正文，包括失败/元数据/头部范围请求，不包含HTTP头、TLS开销或OS缓冲。5份速度官方文档共571918正文另行登记，不属于两时相SAR数据请求。未注册、登录、使用凭据、付费、联系作者或修改系统设置。

## 复跑命令与技术验收

以下命令在唯一执行根运行，全部离线：

    track_b/.venv/bin/python track_b/research/q2/round2/sources/velocity_build_chain.py
    track_b/.venv/bin/python track_b/research/q2/round2/scripts/check_network_guards.py
    track_b/.venv/bin/python track_b/research/q2/round2/scripts/probe_pair.py --offline
    track_b/.venv/bin/python track_b/research/q2/round2/scripts/check_aoi_support.py --aoi track_b/research/q2/round2/inputs/search_aoi.geojson --expected-sha256 14db392ea6d318c2df34152af950b227653fd1f938aed1f4aa9eedf92c29579f --approval-record track_b/research/q2/round2/inputs/advisor_aoi_review.json --expected-approval-sha256 5be13b550bcf9f3f06dae87ac5e6a5cc731bf569af08331da27d46aaf9deda5e
    track_b/.venv/bin/python track_b/research/q2/round2/scripts/consolidate_round2.py

首次真实访问命令是probe_pair.py --online；已有尝试不会自动重试，预算不按景或重跑重置。离线夹具覆盖200拒读、重定向、超范围206、累计失败正文、64KiB错误体界限、预算不足时不请求等7项；独立审查另做近上限内存边界探测。它们只验请求守卫，不验真实提供方像元能力。

速度CSV同版本离线复跑哈希一致；AOI和参数表也可按上述保存证据离线生成。consolidate需最后执行，以更新被重跑时间戳影响的产物哈希。四张官方PDF页渲染图已由内部阅读代理实际打开，源PDF一基页4/5/10/11及当前PNG哈希在来源登记中；不冒称人类科学验收。

交接前执行：

    track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q2 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q2 --expected-base 76ee1532cb2acf36fb82c5f4749a4288507dfcc8

## 联合审查的下一动作

已解决：官方定义上下文、阶段3速度保留事实、指定匿名访问结果、批准搜索AOI的目录足迹支持。仍未知：本地原链/残差成因/分量旋转、真实源区结构水热、像元内容与质量。

当前阻断：通过本轮匿名入口做2026像元变化分析，以及以事件状态约束临界条件。可继续：背景证据分层、源区/地形来源核查和条件性不确定性设计。核心模型/阈值/最终科学采用待队员决定；本窗到第二轮联合审查即交付，不push。
