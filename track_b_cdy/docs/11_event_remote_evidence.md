# 阶段 3：事件时效登记与小样本遥感补数

核验日期：2026-10-23（America/New_York）；机器记录以 UTC 保存，跨至 2026-10-24。工作包 E02 / E05 的资料侧成果。没有拟合、阈值、95% 覆盖率或真实灾害仿真结果。

**本轮完成了实际获取与读取闭环。** 三条官方遥感目录返回 41 个场景，NASA 官方目录取得 54 条局部候选记录；取得并核读本次事件原始研究 PDF 的相关页面；从 ESA 官方公开 COG 真正读出一个小范围土地覆盖裁剪。事件标签精度、源区边界和原始到达观测仍有缺口。

## 1. 机器入口与复跑

产物目录：[event_remote](../data/external/event_remote/)。入口文件：

| 文件 | 可复查内容 |
|---|---|
| [summary.json](../data/external/event_remote/summary.json) | 最新完整运行目录、响应数量与字节数、各目录返回数、实际成功和限制 |
| [manifest.json](../data/external/event_remote/manifest.json) | 目录内逐文件相对路径、大小、SHA-256；不包含 manifest 自身 |
| [event_evidence_ledger.json](../data/external/event_remote/event_evidence_ledger.json) | 同一事件的各来源、各物理阶段、时间、空间精度和适用角色 |
| [scene_inventory.json](../data/external/event_remote/scene_inventory.json) | 41 个官方 STAC item 的观测、处理、发布、资产与位置元数据 |
| [scene_candidates.csv](../data/external/event_remote/scene_candidates.csv) | 便于领取的少量灾前/灾后候选及选取理由 |
| [historical_candidates.json](../data/external/event_remote/historical_candidates.json) | NASA 候选、原始来源、日期/时刻、位置精度、待审状态 |
| [asset_access_tests.json](../data/external/event_remote/asset_access_tests.json) | Sentinel-2 匿名资产 401、Landsat 登录重定向的实测证据 |
| [worldcover_crop_summary.json](../data/external/event_remote/worldcover_crop_summary.json) | 源对象、HTTP 范围块、实际裁剪范围、类别统计与读回检查 |

在仓库根目录运行：

```bash
track_b/.venv/bin/python track_b/scripts/collect_event_remote.py
track_b/.venv/bin/python track_b/scripts/collect_event_remote.py --verify-only
```

脚本为每次运行创建新的 `runs/<UTC时间>/`，保存有界原始响应及 `http_requests.json`；稳定文件指向最新一次结果。`--verify-only` 不访问网络。联网复跑可能取得修订版本，不能要求官方响应哈希永远不变；比较时同时看 URL、版本、更新时间与保存快照。没有账号注册、付费、凭据读取或 requester-pays 请求。网络会话显式关闭 `.netrc` / 环境认证继承。

## 2. 事件时间分列，暂不冻结秒级真值

| 证据 | 北京时间 UTC+8 | 当前含义与证据层级 |
|---|---|---|
| 本地题面 | 8 月 26 日 10:30 | 比赛背景原值；未明确所有物理阶段，不覆盖其他来源 |
| USGS 当前 reviewed origin | 10:52:10 | 目录地震信号参考；类型为 `landslide`，不是机械启动的直接观测 |
| JMS 原站 PDF，p9 | 约 10:51:50 / 10:52:20 | 作者重建的运动起始 / 首次撞击 |
| JMS 原站 PDF，p10–11 | 约 10:54:00 / 10:59:50 | 汇流撞击 / 口岸近似到达 |
| 殷跃平等原站搜索正文摘录 | 初步推测 10:52:07 / 约 11:00:00 | 主启动 / 主体到达候选；本轮未取得动态全文，不能写为全文核验 |

JMS 的 Figure 1、Figure 2 已渲染目视检查，正文按相关整页读取；文中时刻约束来自地震峰与到达报道。原始波形、报道/视频的时钟校准和机器可读源区多边形未取得，不能把这些重建值作为独立验证。PDF p31 表明研究数据需向通讯作者合理申请，本轮没有联系作者。原站为 **Uncorrected proof**，CMS 发布记录为灾后。来源：[JMS 原站](https://jms.imde.ac.cn/article/doi/10.1007/s11629-026-1482-y)、[PDF 原始入口](https://jms.imde.ac.cn/en/article/pdf/preview/10.1007/s11629-026-1482-y.pdf)、[殷跃平等原站](https://www.zgdzzhyfzxb.com/article/doi/10.16031/j.cghc.202610008)。

USGS 完整 QuakeML 补充了前阶段未登记的误差：时间 uncertainty 为 **7.90 秒**，水平 uncertainty 为 **13,390 米**，相应 confidence level 为 **90%**。坐标约 85.515°E、28.271°N 只能作为目录代理；小数位不代表米级精度。当前 origin 的 creation/update 均在灾后，USGS 事后文字还记载初报“地震”后经分析改为冰川崩塌/泥石流。本轮不据此推断灾前构造地震触发。[USGS 官方 API](https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000tbwb&format=geojson)

**处理决定：** 同一链所有时刻保留同一 `independent_event_group`；既不取平均，也不复制为独立事件。题面、目录参考、机械启动、阶段撞击、口岸首次/主体到达分别登记。目录 90% 测量不确定度不等于题目要求的未来触发时间 95% 区间。

### 时间时效字段

- `event_time_utc` / `source_time_text`：事件或阶段所指时刻及原始写法；“约”与未知误差保留。
- `source_publication_*` / `source_product_updated_*`：论文 CMS 日期、目录产品更新等来源记录。
- `discovered_by_this_audit_at_utc` / `retrieved_at_utc`：本轮发现、取回记录；不是灾害首次发现或历史实时可得时刻。
- `event_first_discovery_time_verified`、`available_time_verified`：未核实即 `null`。STAC 的 `published` / `created` 保留为提供方元数据，不能自动改名为历史可用真值。

当前论文来源均不得进入灾前实时输入；本轮台账支持事后证据审查。第二篇只有原站元数据、摘要和原站搜索片段；附 [阅读范围登记](../data/external/event_remote/supplemental_original_source.json)。两篇相近时间也不能消除共同原始观测来源、阶段定义或校时误差的可能影响。

## 3. 官方遥感目录已实际查询

测试 AOI 为本地 NC 的粗边界 **85.5053–85.5501°E、28.2691–28.3069°N**。它用于管线测试，尚不是已确认失稳源区。查询窗口为 8 月 1 日 00:00 UTC 至 9 月 11 日 00:00 UTC，覆盖 9 月 10 日；查询结果不受“只选低云量”过滤。

| 官方目录 | 返回数 | 产品与实际读取范围 |
|---|---:|---|
| CDSE Sentinel-2 L2A | 21 | item、观测/处理/发布时刻、云量、足迹、资产 href 与认证声明 |
| CDSE Sentinel-1 GRD | 10 | item、观测/发布、轨道、极化、足迹、资产；无光学云量值 |
| USGS Landsat C2 L2 SR | 10 | Landsat-8/9 L2SP、观测/created、云量、足迹、资产；已追读 next 页至空结果 |

使用官方现行接口并保存返回体，未通过第三方 STAC 镜像取代原始目录。依据：[CDSE 官方 STAC 文档](https://documentation.dataspace.copernicus.eu/APIs/STAC.html)、[USGS 官方 STAC 说明](https://www.usgs.gov/landsat-missions/spatiotemporal-asset-catalog-stac)。

少量候选例子（完整 product ID、资产 href 和处理/发布时刻在 JSON/CSV）：

| 用途 | product / item 提示 | UTC 观测时刻 | 目录云量 |
|---|---|---|---:|
| 近灾前光学，同日补充选择 | `S2B_MSIL2A_20260824T044659_…_T45RUM_20260824T083447` | 8/24 04:46:59 | 38.57% |
| 窗口内低云量灾前候选 | `S2C_MSIL2A_20260812T045701_…_T45RUM_20260812T100317` | 8/12 04:57:01 | 18.75% |
| 最近灾后 S2 | `S2B_MSIL2A_20260827T045659_…_T45RUM_20260827T084453` | 8/27 04:56:59 | 78.47% |
| 灾害当天灾后 Landsat | `LC09_L2SP_141040_20260826_20260827_02_T1_SR` | 8/26 04:47:48 | 47.54% |
| 最近灾前 / 后 S1 | `S1D_…20260824T001844…` / `S1D_…20260828T122141…` | 8/24 00:18:44 / 8/28 12:21:41 | 不适用 |

其中 8/26 Landsat 观测晚于所有本次启动候选，必须归入灾后资料。它的目录 `created` 为 8/27，不能用于灾前输入。S2 8/24 有多条轨道/平台记录，不能只凭日期认为是同一影像。自动候选按“最近”和“全 tile/scene 最低云量”选取；上表的 S2B 8/24 是同日较低云量的额外可查项，自动最近项是晚约 16 分钟的 S2A。

**影像取得的实际边界：** Sentinel-2 的公开目录可读，但匿名请求一个 B04 资产返回 401；Landsat thumbnail HTTPS 返回 200，最终内容却是 USGS ERS 登录 HTML，JPEG 文件头未通过。两种官方路线的失败/重定向证据均保留。未使用认证、未访问声明 requester-pays 的替代资产，没有把目录查询成功写成影像解译完成。

光学 scene/tile 云量不代表这个小 AOI 的可见性；目前 `aoi_clear_fraction=null`、`pixel_visibility_verified=false`。S1 也不能因为穿云就跳过辐射/地形校正、叠掩阴影、斑点与同轨几何核对。最近前后 S1 只是元数据候选，未确认是合格变化检测配对。

## 4. ESA WorldCover 小 AOI 已成为可读取实物

源对象为 **ESA WorldCover 2021 v200 N27E084 Map**。官方全球 3°×3° COG 为 EPSG:4326、36,000×36,000，源对象 104,225,123 bytes；本轮仅请求 65,536 bytes TIFF 头及所需 4 个 Deflate 块，共 **358,545 bytes**，没有下载完整 tile。官方入口与公开 S3 无需账号路径已核验。[ESA 数据访问说明](https://esa-worldcover.org/en/data-access)

输出：[worldcover_2021_v200_test_aoi.tif](../data/external/event_remote/worldcover_2021_v200_test_aoi.tif)，**454 行 × 539 列、uint8、20,662 bytes**。像元对齐后的实际边界为 `[85.50525, 28.26908333, 85.55016667, 28.30691667]`；NoData=0，244,706 像元均有效。没有插值、重投影或提高空间分辨率，保存后逐像元读回一致。

| 类别 | 代码 | 像元数 |
|---|---:|---:|
| 冰雪 | 70 | 115,508 |
| 裸地 / 稀疏植被 | 60 | 89,451 |
| 草地 | 30 | 25,061 |
| 苔藓与地衣 | 100 | 7,271 |
| 永久水体 | 80 | 7,173 |
| 树木覆盖 | 10 | 242 |

裁剪 SHA-256：`77b7f73e68f9f0940c322610de343d6748360120616b5de67554e40277ea40e4`。

这解决的是跨境空间背景的公开取数与格式读取问题。**2021 分类不是 2026 实测状态；有效覆盖也不是分类正确性验证。** 与 NC 或其他网格对齐时，类别量必须用 nearest，冰川有效掩膜及真实失稳边界另行判断。原县域土地覆盖的 NoData 成因不能由本轮全球产品反推。

## 5. 历史事件目录取得候选，未产生合格回测样本

NASA Earthdata 官方 `COOLR_Reports_Points/Polygons` 服务，在较大检索框 **85–86°E、27.8–28.8°N** 返回 **53 点 + 1 多边形**，无 transfer-limit 截断。较大检索框用于周边候选发现，不等于本题的已验证适用域。[NASA COOLR 官方介绍](https://gpm.nasa.gov/applications/landslides/coolr)、[官方点服务](https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_Points/FeatureServer/0)。

53 点中：45 `landslide`、4 `mudslide`、2 `debris_flow`、1 `rock_fall`、1 unknown。位置精度：16 条 5 km、11 条 25 km、10 条 1 km、8 条 10 km、4 条 50 km、3 条 exact、1 条 unknown；22 条 `event_time` 非空，但本轮未核实其时区、校时或来源所指阶段。“exact”是提供方分类，不应理解为测量零误差。点记录最新 event_date 为 2020-09-13，唯一多边形为 2023 年个人观测候选；本次 2026 事件不在这批返回中。

原始字段包括 `source_name/source_link/event_date/event_time/location_accuracy/submitted_date/last_edited_date`。NASA 是目录提供方，底层不少来源仍是媒体或个人记录；机器台账均标记 `raw_primary_source_reviewed=false`、`approved_training_label=false`，没有沿媒体链接进行无边界扩展。本轮**获批的独立历史训练/95%覆盖率验证事件数仍为 0**。这表示未完成必要核验，不表示附近从未发生灾害。未报告时段不能直接当真负例；机制不同的记录也不能合并为冰岩崩触发样本。

## 6. 验收结果、AI 辅助与后续接点

已实际完成：官方目录响应读取和续页检查、PDF 文件头/页数/关键时间文本检查、QuakeML 不确定度读取、两条匿名影像资产路径实测、COG 范围块解压和小裁剪 GeoTIFF 读回、逐文件 SHA-256 清单。最新响应数量和保存字节数以 `summary.json` 为准；本文件不把后续联网产生的新版本误作旧快照。

AI 辅助范围为来源发现、资料下载、元数据审计、证据分层与代码实现；未生成核心建模结论。队员应复读将采用的原文/官方规范，核实模型输入与标签，并记录采用、修改及引用情况。

下一工作包可以直接接续：

1. **事件证据复核：** 队员审读各阶段定义，获取原始地震波形与到达报道/视频校时信息，确定首次到达或主体到达指标；先保留未定误差。
2. **空间配准：** 用正式 GIS 叠加本轮 WorldCover crop 与 NC 正掩膜，保留 native 年代与 nearest 重采样记录；确认源区和口岸目标几何后重新限定 AOI。
3. **影像许可与取得：** 根据队员现有合法访问条件领取表中少量候选；本轮不代为注册。先检查 AOI 有效像元、云雪/阴影与配准，再做灾前后解释。
4. **验证设计：** NASA 候选逐条回溯原始机构/论文/观测，按事件链去重和机制筛选；在合格样本不足时，Q1–Q3保持单事件诊断、情景或方法演示的相应边界，不能填造覆盖率。
