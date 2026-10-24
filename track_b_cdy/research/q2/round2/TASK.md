# Q2 第二轮任务：速度处理链与唯一同轨影像对

状态：派单任务书；不代表第二轮已执行。日期：2026-10-24（America/New_York）。

## 身份与恢复

- 唯一执行根：`/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2`；新分支 `codex/track-b-q2-r2`。
- 阅读 `track_b/docs/16_stage4_round2_workflow.md`、`track_b/docs/15_stage4_round1_review.md`、本问首轮 `HANDOFF.md` 与 `PROPOSALS.md`。
- 本轮合同 `track_b/config/stage4_round2_contract.json`；清单 `track_b/audit/stage4/round2/baseline_manifest.json`。
- 本轮精确基线提交/清单哈希由主参谋派单绑定；不得使用首轮提交替代。
- 复用本工作树现有 `track_b/.venv/bin/python`，不安装 SAR 大型工具或新增依赖。
- 所有新文件只写 `track_b/research/q2/round2/`；首轮/公共输入不改、不重跑阶段3管线。

## 已核对存在的输入

- `04_B赛道/04_冰川地形、冰厚及表面速度/Glacier topographic and dynamic drivers (Glacier-collapse and debris-flow disasters at Langtang Lirung, Nepal).nc`。
- `track_b/audit/spatial/netcdf.json`、`source_documentation.json`、`track_b/data/processed/spatial/source_manifest.json`。
- `track_b/research/q2/results/input_check.json`、`nc_parameter_support.csv`、`parameter_evidence.csv`、`s1_pair_screen.json`。
- `track_b/research/q2/sources/official_product_reading.json`、`sentinel1_grd_processing.html`、`sentinel1_product_types.html`。
- `track_b/data/external/event_remote/scene_inventory.json`、`asset_access_tests.json`、`scene_candidates.csv`。
- `track_b/data/processed/spatial/nc_glacier_mask.tif` 仅为库存参数域，不能替代待审搜索 AOI/真实失稳面。
- 搜索 AOI 为本轮 Q4 先交、主参谋审查后分发的新输入；此时尚不能假称已经收到或核定。

## 固定影像范围与访问预算

- 唯一组合：Sentinel-1D、descending、relative orbit 121、GRD/VV，禁止自动改选其它日期/轨道。
- 灾前：`S1D_IW_GRDH_1SDV_20260819T001036_20260819T001101_004187_007ABD_B38C_COG`。
- 灾后：`S1D_IW_GRDH_1SDV_20260831T001037_20260831T001102_004362_0080EC_65B9_COG`。
- 两时相合计实际网络读取上限 **128 MiB = 134217728 bytes**；累计失败/重试、元数据/头部及像元响应正文，不能每景重置。
- 只作 VV 必要范围/块读取；不下载完整场景，VH 或扩大 AOI 不在本轮授权范围。

## 执行步骤

1. 核对本窗根/分支/新基线/环境和冻结输入；记录启动验证。先完成速度定义与访问核查，不等待 AOI 才开始。
2. 读 NC 全局/变量属性和本地来源文档，沿已声明 ITS_LIVE v2.1 原产品追溯 vx、vy、v 的统计定义、年代和单位。
3. 寻找已附本地生成说明/脚本，核对“原生格点→统计→模长合成→重采样”的实际顺序；不存在即明确缺失，不编造脚本。
4. 把产品定义、直接可证本地操作和未核实假说分列；首轮残差直接引用，非必要不重算全表。
5. v 与 hypot(vx,vy) 不相等的成因无证据时保持未知，不替换任一原值，不称本次加速或释放初速度。
6. 从固定 scene ID 提取合法官方资产入口，记录匿名状态、Range 能力、产品格式、内容类型和访问失败；登录 HTML 不能当 TIFF。
7. 在实际传输前启用总字节计数与停止条件；不使用无法限制读取的自动整景下载/栅格驱动，不通过多次会话绕过预算。
8. 等主参谋明确分发 AOI 及哈希后，仅把该版本作为搜索支持输入；保存分发记录，不能自行提前采纳 Q4 未审核草图。
9. 核对两景足迹与 AOI；若不覆盖、认证失败、Range 不支持或无法有界读取，保存失败链即结束本项。
10. 能读取时，先取必要头/目录，再读 AOI 对应 VV 块；记录每次请求 Range、状态、实收字节、累计字节和 SHA-256。
11. 核查坐标、变换、分辨率、窗口边界、有效/NoData 支持及两景实际读取范围；必要缩小 AOI 的方案须报告而非静默执行。
12. 元数据兼容、像元支持、配准、地形遮蔽/叠掩和变化解释分别登记；仅完成前两项不得声称配准/变化解译通过。
13. 更新参数可辨识性与路线：背景速度可用程度、真实事件参数仍缺什么、下一步最小证据需求；不拟合正式触发阈值。

## 本轮交付（均位于 round2）

- `VELOCITY_REVIEW.md`、`results/velocity_definition_chain.csv`：原定义、本地处理链、残差解释状态与采用建议。
- `REMOTE_ACCESS_REVIEW.md`、`results/pair_access.json`、`network_budget.json`：唯一两景访问/预算/退出状态。
- `results/aoi_pixel_support.csv`：收到 AOI 后的几何支持及实际像元状态；失败时保留 null 和明确原因。
- `results/parameter_evidence_update.csv`、`ROUTE_UPDATE.md`：新增证据与阻断项，不重写首轮表。
- `sources/` 存新增有界来源/必要像元及获取日志；`results/source_register.json` 记录官方 URL、UTC、版本、实际阅读范围和哈希。
- `round2/scripts/` 中的新代码有离线复跑命令；`input_manifest.json`、`output_manifest.json` 不包含自身；更新本轮 `HANDOFF.md`。

## 验收与交接

- 必须同时给出速度产品定义与本地处理链的证据强度；原值不变，未知不自动解释为插值/平均造成。
- 请求字节账累计不超过预算，影像索引区分“访问成功/元数据/像元”；未获像元可验收为有证据的失败交付。
- 机器合同规范字段和 AOI 版本/误差完整；背景、探索、事后影像不混为事前状态/独立验证。
- 启动和结束运行：`track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify --round round2 --question q2 --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q2 --expected-base <主参谋发布的本轮基线提交>`。
- 得到可采用/可排除/仍未知及依据即退出，不注册、付费、联系作者或扩选影像；仅本轮本地提交、不 push，交主参谋联合审查。
