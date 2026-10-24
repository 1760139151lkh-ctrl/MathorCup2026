# Q4 R3 空间输入、独立像元与可计算几何

本轮已实际取得有产品身份的 Copernicus GLO-30 原始 COG、三景事前／事后 Sentinel-2 TCI 与 SCL 像元、两景红／近红外反射率窗口，以及 OSM 河网和桥／设施几何。已交付共同 60／120 m 地形、源区候选掩膜、三条区域路线和三条源边缘接河候选，并完成局部升降地形、辐射口径和植被变化筛查。**这些材料支持完整条件传播计算；释放面、真实流路和灾害影响面仍未作为事件真值接受。**

## 稳定早交与模型接口

`exports/geometry_bundle.json` 的版本为 `q4-r3-spatial-copdem-v1`，原字节 SHA256 为 `64cd8369ce79d599890d4ed726a87833b63f64472c4dbea54408e39e79a40561`。它引用的地形、NPZ、CSV、GeoJSON、原始图均在早交后保持不变。主窗另外复制的 `exports/geometry_v1/` 属主窗冻结分发记录。本子任务后续只追加新文件，不替换早交绑定项。

| 共同输入 | 60 m | 120 m |
|---|---:|---:|
| 行×列 | 154×300 | 77×150 |
| 全域有效像元 | 46,200 | 11,550 |
| 源候选掩膜像元 | 257 | 67 |
| 栅格化源面积 m² | 925,200 | 964,800 |
| 源质心单元 row,col | 114,265 | 57,132 |
| 纸图口岸代表点单元 row,col | 128,25 | 64,12 |

两网格同域 EPSG:32645，范围 `[339480,3127680,357480,3136920]` m，左上角 `(339480,3136920)`。60 m 仿射为 `[60,0,339480,0,-60,3136920]`；120 m 同原点。重采样均为双线性，未填洼、烧河、平差或转换垂直基准。源质心 `(355385.809,3130026.408)`，纸图口岸点 `(340981.541,3129214.005)`。

- `results/spatial_inputs_60m.npz`／`spatial_inputs_120m.npz`：`z,source_mask,channel_distance_m,x,y,dx,source_rc,target_rc,transform,geometry_version`；`source_mask` 为 uint8，统计／逻辑须先 `astype(bool)`。
- DEM 在缓存 `.../round3/q4/spatial/q4-r3-spatial-copdem-v1_dem_60m.tif` 及同名 120 m 文件；完整哈希在早交 bundle。
- `results/spatial_paths.csv`：`path_id,node_index,x_m,y_m,elevation_m,distance_m,row,col,geometry_version,data_role`。P1／P2／P3 长 20.698／21.415／21.655 km。它们由同一源质心到同一纸图代表点，以距离、上坡代价及纸图河线邻近代价作 8 邻域最短路，未强制匹配 22.8 km。全路径累计上升约 218／226／226 m，未削除上坡或把路径称为严格重力流线。
- 两网格面积相差约 4.28%。跨网格收敛试验应固定共同体积后调整厚度；不能同时固定两网格厚度再把体积差当纯网格误差。参考 60 m 面积×15 m 为 13,878,000 m³，仅为厚度情景。

## 新地形的身份及比较

实际下载 `Copernicus_DSM_COG_10_N28_00_E085_00_DEM.tif`，38,402,839 字节，完整读取、校验和及 URL 见 `sources/spatial_acquisition.json`。AWS 官方登记说明该桶为 2021 COG 发布版；CDSE 官方说明 Copernicus DEM 为编辑 DSM、主 TanDEM-X 采集为 2011—2015 年、存在更早填补，水平 WGS84-G1150、垂直 EGM2008 米。这里没有把发布年或产品总体精度规格当作本地实际观测年代／误差。[AWS 产品说明](https://registry.opendata.aws/copernicus-dem/)，[CDSE 产品说明](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)。完整文档响应和读取范围在 `sources/spatial_product_documentation.json`。

新 DEM 与原提供区域 DEM 在本轮共同 60 m 网格上的新比较：46,200 像元均值差 `新−原=+29.73 m`，RMSE 31.68 m；源候选 257 像元均值 +17.67 m，RMSE 20.16 m。原 DEM 产品／年代／垂直基准仍未知，不能把均值差作为垂直改正，更不能称冰川时序高程变化。这里的“独立”指独立获取、产品可追溯；原 DEM 是否同源于 Copernicus 尚未知。前两轮差异实验未重跑。

## 647 m 未解释区与局部地形检查

`results/spatial_edge_connectors_v2.geojson`／CSV 在纸图源边界最近点及沿边界周长 ±300 m 取三起点，以纸图河候选最近点为接河端，局部限定窗口内计算长度＋30×正升高的最短路。距离均在 EPSG:32645 计算。

| 候选 | 几何直线缺口 m | 实际栅格路径 m | 净降高 m | 累计／最大单步上升 m | 当前 DSM 严格不增高可达 |
|---|---:|---:|---:|---:|---|
| C1 | 647.13 | 709.71 | 284.15 | 0／0 | 是 |
| C2 | 761.06 | 794.56 | 315.37 | 0／0 | 是 |
| C3 | 891.62 | 939.41 | 574.08 | 0／0 | 是 |

端点到 60 m 像元中心吸附分别约 15—36 m／26 m，另列于 `spatial_edge_review_v2.json`。这提供“所选旧 DSM 中存在下坡接河候选”的证据，未证明真实灾害沿其中之一运动；测试未包括动量、流深、相互作用、侵蚀及地形／配准误差。不能把局部结果扩展为全程无障碍或真实源界接受。

## 实际光学像元与质量

三景均从公开 Earth Search／AWS COG 取得完整 TCI 与 SCL 文件，另读取相同范围的全分辨率窗口：2026-08-12 05:10:48.070Z、08-24 05:00:49.736Z、09-28 05:00:54.257Z。TCI 是显示产品，不作为反射率。实际文件 bytes／hash、请求状态／UTC 在 `spatial_optical_osm_acquisition.json`，窗口派生 hash／实际范围在 `spatial_optical_reads.json`。目录返回 31 景，未将其称全部存在景的穷尽清单；历史可用时间未知。

SCL 逐类保留。配置可见类别 4/5/6/11 与 unclassified7、saturated1、topographic-dark2、cloud-shadow3、cloud8/9、cirrus10 分开；“暗／影／云”不能简称云量。源候选的类别2比例在 08-12 为 75.92%、08-24 为 52.74%；09-28 的 90.81% 为雪冰类11、9.19% 为类别2。故事后源区并非清晰裸地失稳面。08-24 与 09-28 还存在条带 NoData：全共同域有效率约69.37%和80.48%。像元覆盖、SCL 可观测性、影像配准精度和地物识别误差分别报告，没有用 tile cloud 百分比替代源区质量。

新增 B04／B08 实际 10 m 窗口用于 08-12→09-28 植被变化筛查。首次按 band offset=-0.1 直接换算产生越界 NDVI，已记 `spatial_spectral_naive_offset_rejected.json` 为 **REJECTED，禁止采用**。两景 legacy item 均声明 `earthsearch:boa_offset_applied=true`；按照维护者说明仅用 scale，随后获取同 product_uri 的 C1 红／NIR 各 100×100 像元实际交叉检查。非裁剪像元的 C1 DN−legacy DN 均为1000，换算反射率最大差≤2.22e−16；事后 red/NIR 有19/24个 legacy DN1 裁剪像元，差异最大约0.006，另行排除。该检查是同一观测的两种资产表示核验，不增加独立影像数。[提供方 offset 说明](https://github.com/Element84/earth-search/issues/41#issuecomment-2885104901)。

有效 paired mask 为两景 SCL4/5、两波段 DN>1、NDVI有限；雪、水、暗／影／云、未分类均排除。在事先登记的 `preNDVI>0.4, postNDVI<0.3, delta<-0.3` 条件下：

| 区域 | 配对可用面积 km² | 候选变化面积 km² | 占配对可用面积 |
|---|---:|---:|---:|
| 三路径并集250 m走廊 | 7.4511 | 4.0537 | 54.40% |
| 路径500—1000 m旁侧环带 | 14.2262 | 0.5816 | 4.09% |

delta 阈值 −0.2／−0.4 的敏感性及全部分母在 `spatial_spectral_screen.json`。这表明河谷邻域有显著空间集中的47天植被光谱变化线索；季节变化、配准／分类误差和其他过程尚未排除。旁侧环带非匹配因果对照，相关像元不是独立事件。候选 GeoJSON 与不少于9个4邻像元的连通斑块均为探索，**不是已接受泥石流影响面**，不可拿来同时校准并声称独立验证。

冻结 mask：`/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial/q4-r3-spectral-screen-v2_masks.npz`，50,721 bytes，SHA256 `b350e6022beadd7f0bbecd53f29415b3d15fbc756cd90a33d595509ed9b0562b`。包含 `valid_pair,change_candidate,change_candidate_ge9,affine,crs,geometry_version,pre_scene,post_scene`。924×1800、10 m、EPSG32645、affine `[10,0,339480,0,-10,3136920]`。模型 hmax≥0.1 m 可 nearest 重投影到此格网，仅在 `valid_pair` 内报告探索性空间重叠，遮蔽像元不能作负例，10 m 输出不增加模型分辨率。详见 `spatial_spectral_mask_index.json`。

## 独立河网与分离目标

Overpass POST 406，另一公开 GET 读超时后，合法 OSM API GET 实际成功200，7,089,549字节，SHA256 `903e813b392dcaf7fe310a5aa09ee8f891858282ed241ffb9229408fec002484`。解析167条河／溪线，桥和设施等共184个选定几何。`spatial_osm_objects_v2.geojson` 保留每对象ID／版本／末次编辑时间／原标签；编辑时间不是观测时间。多处灾损标签引用 Wikipedia 且事后编辑，未接受为独立灾损真值。[OSM API](https://api.openstreetmap.org/api/0.6/map?bbox=85.35,28.25,85.55,28.36)。

| 逻辑对象 | UTM45N代表坐标 m | 对应关系／限制 |
|---|---|---|
| 纸图口岸符号 | 340981.541,3129214.005 | 仍为代表点，不等于桥或全口岸 |
| OSM临时便桥 | 340937.604,3129150.896 | way1552746552中心线／1552746560结构是同一实体两种表示 |
| OSM旧热索桥 | 340927.835,3129139.009 | way1443180803／1552746559；与临时桥生命周期分开 |
| OSM中国移民管理设施 | 340865.162,3129272.217 | way1553369440 footprint；不是口岸完整设施边界 |

五个目标几何表示仅对应**三个逻辑实体**，见 CSV `entity_id`，不能作五个独立目标／事件。临时桥结构与纸图点最近58.78 m；设施边界最近118.84 m。定位误差、现场状态及实际保护范围仍未知。

纸图两段河线到“任何 OSM 河／溪”的120 m采样距离中位数约53.85／68.61 m，但存在支流歧义，不能直接算真实中心线误差。OSM中最近河线距纸图源边界仍918.44 m，故独立河网并未关闭647 m源区接河的事件证据缺口。下游河谷几何得到另一个机器来源支持；上游真实释放／连接仍待独立解译。

## 复跑、检查与采用边界

所有 shell 在 `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4`，使用原 `track_b/.venv/bin/python`，未安装或修改共享 runtime／依赖。首轮协议 `config/spatial_protocol.json` 先于地形计算；光谱 `spatial_spectral_protocol_v1/v2.json` 保留 QA 口径修订。

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_acquire.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_optical_osm.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_auxiliary_acquire.py
# spatial_build.py 是已冻结早交生成命令；不要在现有交付目录重写它的绑定文件。
# 在新重放目录或独立checkout复现同一输入的地形构建后，核对早交hash。
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_build.py --output-root /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial/replay_new_version
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_edge_review.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_compare.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_osm_read.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_optical_read.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_radiometry.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_spectral.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_validate.py
```

缓存原始输入按版本引用；来源／版本／实际范围／bytes／hash 在 `sources/spatial_*` 和 `results/spatial_source_index.json`。图实际打开后写 `spatial_visual_review.json`，最终建议用 km 刻度 v2，原 v1图仅保留早交历史。机器检查在 `spatial_validation.json`；本子任务不编造触发／到达时刻、不把NC库存mask或多年速度作为释放面／初速。科学接受及跨问采用由主窗和队员审查。

Copernicus 派生地形署名：produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved。影像：Contains modified Copernicus Sentinel data 2026。OSM：© OpenStreetMap contributors, ODbL。
