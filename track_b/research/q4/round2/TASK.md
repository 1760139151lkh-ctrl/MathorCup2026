# Q4 第二轮任务：候选几何、搜索 AOI 与地形追溯

状态：派单任务书；第二轮尚未执行。日期：2026-10-24（America/New_York）。

## 身份与恢复

- 唯一执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4`；新分支 `codex/track-b-q4-r2`。
- 阅读 `track_b/docs/16_stage4_round2_workflow.md`、`track_b/docs/15_stage4_round1_review.md`、本问首轮 `HANDOFF.md` 与 `PROPOSALS.md`。
- 本轮合同 `track_b/config/stage4_round2_contract.json`；清单 `track_b/audit/stage4/round2/baseline_manifest.json`。
- 新共同基线提交/清单哈希由主参谋派单绑定，记录核对后再运行；不复制首轮基线冒充本轮。
- 复用本工作树现有 `track_b/.venv/bin/python`，只写 `track_b/research/q4/round2/`。
- 优先交付搜索 AOI 给主参谋审核分发 Q2；无需等待真实失稳面闭合，不自行给其他聊天发送消息。

## 已核对存在的输入

- `track_b/data/external/event_remote/pdf_preview/jms-06.png`：已保存 Fig.1/图注所在有坐标刻度页。
- `track_b/data/external/event_remote/jms_2026_uncorrected_proof.pdf`、`track_b/data/external/event_remote/runs/20261024T034202Z/raw/jms_article.html`。
- `track_b/research/q4/sources/geometry_reading.json`、`results/geometry_evidence.csv`、`parameter_evidence.csv`、`terrain_feasibility.json`。
- `04_B赛道/07_DEM（2026-08-26）/DEM.tif`、`DEM.tif.xml`、`DEM.tif.aux.xml`、`DEM.tfw`。
- `04_B赛道/04_冰川地形、冰厚及表面速度/Glacier topographic and dynamic drivers (Glacier-collapse and debris-flow disasters at Langtang Lirung, Nepal).nc`。
- `track_b/audit/spatial/netcdf.json`、`source_documentation.json`、`track_b/data/processed/spatial/source_manifest.json`、`coordinate_operations.json`。
- `track_b/data/processed/spatial/dem_utm45_30m.tif`、`dem_on_nc_grid.tif`、`nc_dem_native_grid.tif`、`nc_glacier_mask.tif`。
- 首轮两 DEM 均差/重采样试验直接引用，不重跑首轮数值或合成平流检查。

## 执行步骤 A：先发布搜索 AOI 候选

1. 核对根目录/分支/新基线/现有环境并保存启动验证；核对原 Fig.1 图像与 PDF 页及来源哈希。
2. 实际打开有刻度的 Fig.1，登记图幅、刻度、投影说明及可用控制点；新裁切/标注仅保存在 round2。
3. 从坐标刻度选取可复查控制点，记录像素坐标/地图坐标、拟合方式、变换残差及留出检查；不足以配准则明确失败。
4. 分开记录数字化/配准残差、原地图定位精度和地物识别不确定性；不能用小残差声称高真实定位精度。
5. 先形成覆盖文献候选源区/流路的**搜索 AOI**（WGS84 GeoJSON），给出边界依据、误差/缓冲依据、版本与哈希。
6. 立即写 `AOI_HANDOFF.md`、`results/search_aoi.geojson` 与 `results/search_aoi_evidence.json`，通知主参谋读取；公共采用待其审查，Q2 未收到批准前不得视为有效。
7. 若刻度/图像不足以提供可用 AOI，也立即交付失败依据与可支持范围，不等待后续地形追溯才上报。

## 执行步骤 B：候选对象与地形

8. 分别建立源区候选、口岸保护对象候选和河道候选；每个对象保留来源、CRS、定位误差、定义与时间属性。
9. 文献图描绘标为 retrospective_reconstruction_candidate；独立可追溯地理资料单列来源，不把二者混成现场测绘真值。
10. 不用 NC 库存正mask、USGS代理点或文献长度替代释放边界/真实中心线，不强制把路径长度调至22.8km。
11. 保护对象明确是口岸设施、桥位或候选代表点；来源无法区分则保留定义未知，不以地名首个搜索点自动定案。
12. 先读本地 XML、NC 属性/说明和现有变换记录，追溯独立 DEM 与 NC DEM 的产品、采集/合成年代、垂直基准及生成链。
13. 目录日期、文件生成日期与观测日期分别保存；追不到源产品时保持未知，不据“2026-08-26”目录断定事前/事后地形。
14. 在新候选走廊上检查两 DEM 的实际有效覆盖、NoData/断裂、边界余量和可算纵剖面；无可靠中心线时报告走廊范围支持即可。
15. 提出两地形的用途与适用范围，引用首轮差值但不静默拼接、改基准、填洼/烧河道或解释为事件形变。
16. 将空间可行性、几何真值状态与正式物理模型门槛分开；不安装求解器、不做释放体积/参数标定/事件还原。

## 本轮交付（均位于 round2）

- **早交件：** `AOI_HANDOFF.md`、`results/search_aoi.geojson`、`search_aoi_evidence.json`、`georeference_controls.csv`、`georeference_review.json`（后三项同属 results）；不能生成时交有证据的失败记录。
- `results/geometry_candidates.geojson`、`geometry_evidence.csv`：源区/目标/河道各对象含来源、误差、候选状态与版本。
- `TERRAIN_REVIEW.md`、`results/dem_provenance.csv`、`corridor_coverage.json`：产品/日期/垂直基准证据、覆盖与用途建议。
- `figures/candidate_geometry_coverage.png`：源区/目标/河道候选与有效 DEM 范围并列，实际打开后记录图像哈希和阅读结果。
- `ROUTE_UPDATE.md`、本轮 `HANDOFF.md`：已解决/仍未知/阻断项/可继续分析与跨问需求。
- 新来源及日志放 `sources/`，新代码放 `scripts/`；`results/source_register.json`、`input_manifest.json`、`output_manifest.json` 不包含清单自身。

## 验收与交接

- AOI 给 Q2 的版本须经过主参谋审查；研究窗不直接修改公共几何或批准真实释放边界。
- 控制点、变换、坐标与误差可追溯；图配准残差不能替代地图定位精度，候选线长度不能当实际传播距离。
- DEM 有效覆盖统计引用实际候选几何/走廊版本；覆盖通过不等于地形年代/基准或动力学模型通过。
- 启动和结束运行：`track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q4 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q4 --expected-base <主参谋发布的本轮基线提交>`。
- 可采用/可排除/仍未知及依据即结束补证；不扩扫目录/联系作者/注册/付费，仅本轮本地提交、不 push，交联合审查。
