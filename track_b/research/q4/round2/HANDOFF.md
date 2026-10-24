# Q4 第二轮交接：候选几何、搜索 AOI 与地形追溯

**状态：第二轮研究交付完成，待联合审查；正式物理模型及队员科学采用尚未完成。** 日期：2026-10-24（America/New_York）。本轮给出了可检索的 AOI、五个论文图上候选与地形覆盖证据，没有确认真实释放边界、全程连接、实际传播距离或时间。

## 身份与共同基线

- 执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4`；分支：`codex/track-b-q4-r2`；首轮分支保留。
- 本轮共同基线：`76ee1532cb2acf36fb82c5f4749a4288507dfcc8`。
- 565 项冻结清单：`track_b/audit/stage4/round2/baseline_manifest.json`，SHA-256 `c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d`。
- 解释器：本树 `track_b/.venv/bin/python`，Python 3.12.14，44 包锁；无安装或升级。启动报告另存 [sources/startup_workspace_verification.json](sources/startup_workspace_verification.json)，收尾见 [workspace_verification.json](workspace_verification.json)。验证仅确认工作区、输入、环境及 I/O，不代表模型通过。
- 仅写 `track_b/research/q4/round2/`；首轮代码、试验及公共资料未修改。提交号由交付此文件的 Git commit 与聊天收尾提供，避免将提交自身写入内容。

## 早交 AOI：保持主参谋采用的原字节

版本 **`q4-r2-fig1-search-v1`**；文件 [results/search_aoi.geojson](results/search_aoi.geojson)，SHA-256 **`14db392ea6d318c2df34152af950b227653fd1f938aed1f4aa9eedf92c29579f`**。
早交证据 [results/search_aoi_evidence.json](results/search_aoi_evidence.json)，SHA-256 **`78ff69266903ee77626679b0bba542ec36f1e73e3d39581909543d63ba262d14`**。

主参谋已反馈审核通过并将原字节及独立采用记录分发 Q2，**仅限 search_only**，反馈记录见 [sources/advisor_aoi_receipt.json](sources/advisor_aoi_receipt.json)。早交证据和 [AOI_HANDOFF.md](AOI_HANDOFF.md) 内的 pending 是生成时状态，特意保留，没有静默改写为新版本；这不是队员对真实事件几何的人工采用。

实际打开 JMS 校样 PDF 第 6 页及 300 dpi 裁切，以 3 个经度、2 个纬度单轴刻度，按 `lon=a*x+b`、`lat=c*y+d` 拟合。中间经度刻度先留出再最终拟合，留出等效误差 **20.85 m**。纬度仅两点，无独立留出。轴刻度不是完整二维地面控制点，零旋转／剪切未独立验证；原图基准、精度和地物识别误差均未知。

GeoJSON 采用 WGS84/CRS84 经度—纬度的搜索假设，范围 `[85.35717450521027, 28.261058229928057, 85.54598368048458, 28.34920248297248]`；UTM45N 面积 **175.36 km²**。2 km 是分析者选择的搜索扩展，±5 渲染像素仅为敏感性，二者都不是精度或置信界。不能用于释放面、体积、真实距离或独立验证。

## 五对象与地形检查

候选版本 `q4-r2-fig1-candidates-v1`，见 [results/geometry_candidates.geojson](results/geometry_candidates.geojson) 和 [results/geometry_evidence.csv](results/geometry_evidence.csv)。五对象均来自同一图：源区红色轮廓、口岸符号代表点、交汇点、Chhochen 蓝线、Lende 蓝线。全部在搜索 AOI 内。候选 GeoJSON SHA-256 为 `cd68bf0bda80ab1d075fa33dbf0d713307d535e95e0f2494e41ce16b698b113e`。

| 检查 | 实际结果 | 解释边界 |
|---|---|---|
| 源区轮廓至上段蓝线 | 最近间隔 **647.13 m** | 图上候选缺口；未画连接，真实源区至通道连续性未知 |
| 口岸对象 | 图上符号代表点 | 无法区分具体设施、桥位或保护对象 |
| 独立 DEM | 五对象及三种候选走廊全部有效覆盖 | 仅证明候选空间范围的栅格支持 |
| NC DEM | 完整覆盖源区候选；其余四对象未完整覆盖 | 参数域范围不能代表全程流路 |
| 真实纵剖面／传播距离 | 未生成 | 两条候选线约 6.04／13.98 km，仅为描线长度，不作为事件距离，也未强制对齐 22.8 km |

候选河道走廊统计（半宽由分析者选择，不是河宽或定位误差界）：

| 半宽 | 独立 DEM 有效面积覆盖 | 独立 DEM 有效／走廊内像元中心数 | 独立 DEM 边界余量 | NC DEM 面积覆盖 |
|---|---:|---:|---:|---:|
| 100 m | 100% | 4484/4484 | 3632.01 m | 11.17% |
| 250 m | 100% | 11334/11334 | 3482.03 m | 11.63% |
| 500 m | 100% | 23096/23096 | 3232.06 m | 12.21% |

精确值、像元中心与面积统计口径、输入哈希见 [results/corridor_coverage.json](results/corridor_coverage.json)。NC 范围内像元有效不代表范围外走廊被覆盖。GEOS 极小面积舍入残差单列保存；当有效足迹严格 covers 走廊时使用完整面积，未让比例越出 [0,1]。

两张最终图已实际打开核查轴向、文字、候选叠加与 DEM 范围，绑定哈希见 [results/visual_review.json](results/visual_review.json)：[控制点图](figures/georeference_controls.png)、[候选与覆盖图](figures/candidate_geometry_coverage.png)。视觉审阅为 Codex 检查，不是队员人工科学验收。

## DEM 追溯与独立地理补证

详细证据见 [TERRAIN_REVIEW.md](TERRAIN_REVIEW.md)、[results/dem_provenance.csv](results/dem_provenance.csv) 与来源日志。独立 DEM XML 只追到 ArcGIS 10.8 Clip 上游 `GeBainiDEM_30M.tif`；2026-08-26 17:18:43 时区未知，是加工钟而非观测时间。XML 明确为 VERTCS unknown、VDATUM unknown；双重 HTML 转义已在 [本地复核](results/local_metadata_recheck.json) 中正确解码。NC 只给原始文件名和格网／单位，其速度时间不能作地形年代。论文产品名不能绑定本地文件。

本地处理链可追溯：独立 DEM 双线性映射至 UTM45 30 m 和 NC 格网；NC dem 按坐标排序后原格网导出，无垂直转换。两套地形产品、观测／合成年代、垂直基准及上游加工仍未知。暂以独立 DEM 作区域候选研究背景、NC 作参数域共格检查；不拼接、不平差、不填洼或烧河道。

**TERRAIN_REVIEW 中“本子任务没有验证新走廊覆盖”仅限 DEM 来源子任务；Q4 已另行完成上表实际候选走廊检查。** 覆盖结果没有解决地形年代／基准，也不证明动力学模型可用。

按主参谋补充要求完成有界独立地理核查：3 次定向搜索、4 次官方 URL 请求。HydroRIVERS 产品说明与 FAQ 已读并登记响应字节哈希；未下载或匹配本地河网。海关定向搜索无可采用定位命中；尼泊尔官网只取得索引地名，直读两次 TLS 链失败，未取得原始正文或坐标。此结果不证明独立资料不存在。**五对象独立机器几何、CRS／精度／观测时间仍未取得**，继续维持同图重建候选。日志见 [sources/independent_geography_review.json](sources/independent_geography_review.json)，逐对象补充状态见 [results/geometry_independent_status.json](results/geometry_independent_status.json)。

首轮差值与重采样试验仅引用，未重跑：7152 正 mask 格上的独立 DEM 减 NC DEM 均值 −30.7407 m、RMSE 33.7224 m，nearest 减 bilinear RMSE 5.3882 m。它们不是事件形变、精度认证或统一高程改正。未用 NC 库存 mask 作释放面，未用多年平均速度作初始流速。

## 复跑与验证

均从上述唯一 worktree 根执行；无联网、无依赖安装：

```bash
# 新建输出子目录复现已采用 AOI；必须使用尚不存在的目录，保护早交原字节。
track_b/.venv/bin/python track_b/research/q4/round2/scripts/replay_search_aoi.py results/replay_check_NEW
# 重建候选、覆盖与两张图；会更新本轮结果时间和哈希，之后须重新视觉审阅及冻结索引。
track_b/.venv/bin/python track_b/research/q4/round2/scripts/build_candidates.py
track_b/.venv/bin/python track_b/research/q4/round2/scripts/recheck_local_metadata.py
# 内容验证，以及按现有文件重建索引（不运行 AOI 原构建脚本）。
track_b/.venv/bin/python track_b/research/q4/round2/scripts/validate_delivery.py
track_b/.venv/bin/python track_b/research/q4/round2/scripts/freeze_delivery.py
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q4 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q4 --expected-base 76ee1532cb2acf36fb82c5f4749a4288507dfcc8
```

本次实际 AOI 安全复跑保存在 `results/replay_check/`，与采用原几何逐字节相同；复跑证据新时间不构成替换或新批准。候选、覆盖、元数据与图均已实际执行／检查。收尾工作区验证后最后重建清单；`validate_delivery.py --check-index` 仅只读检查交付哈希。机器验证见 [results/delivery_validation.json](results/delivery_validation.json)；源、输入与完整输出索引分别为 [source_register.json](results/source_register.json)、[input_manifest.json](results/input_manifest.json)、[output_manifest.json](results/output_manifest.json)，均不自包含。

## 可继续与阻断项

[ROUTE_UPDATE.md](ROUTE_UPDATE.md) 给出逐项可采用／排除／未知与下一动作。Q2 已获 search_only AOI；其两景 SAR 匿名访问 401 的反馈不支持本窗推导任何像元几何。Q3 不可接收本轮候选线长作为真实距离，触发与下游到达继续分开。Q2/Q4 仍需明确物源、释放状态和参数约束；正式事件传播还缺独立源区—通道连接、明确保护对象及适用的正式地形。

本轮有界补证以可采用／排除／未知结束，不继续扩扫、联系作者或安装求解器。仅作本地提交，不 push；交主参谋组织第二轮联合审查。
