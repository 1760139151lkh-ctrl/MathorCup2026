# 阶段1—2交付核验

日期：2026-10-23（America/New_York）。核验主体为主代理和独立审查代理；不等于队员人工验收。

本页为阶段1—2交付时快照。后续阶段的脚本复跑会更新机器检查记录和当前文档/链接数量；阶段3另见[阶段3交接](13_stage3_handoff.md)，不将新增处理结果追写为本页当时已完成的事实。

## 实际执行的检查

| 检查 | 命令/方式 | 结果与限制 |
|---|---|---|
| 原始完整性 | `python3 track_b/scripts/audit_inventory.py` | 270份全部匹配仓库索引，B266文件无新增/缺失；不是官方签名认证 |
| 环境盘点 | `python3 track_b/scripts/audit_environment.py` | 三个现有Python运行时版本和已装包已保存；没有安装新依赖 |
| 时序完整入口 | `/usr/local/anaconda3/bin/python track_b/scripts/audit_temporal.py` | 退出0，24CSV、21XLSX及说明共47原始文件审计；前后哈希相同 |
| 空间完整入口 | `/usr/local/anaconda3/bin/python track_b/scripts/audit_spatial.py` | 退出0，218文件、173TIFF全像元、5矢量和1NC结构/数值审计；源文件哈希不变 |
| 外部事件通路 | `python3 track_b/scripts/fetch_event_metadata.py` | 官方API字段快照已保存；不把目录参考时刻当已证明的物理启动 |
| 历史预报最小通路 | `python3 track_b/scripts/probe_forecast_archive.py` | idx HTTP200，GRIB2头Range HTTP206；未解码全球场，未证明业务实际发布延迟 |
| Python语法 | `python3 -m py_compile track_b/scripts/*.py` | 全部通过；不代替实际包导入和数据处理验证 |
| 文档/证据结构 | `python3 track_b/scripts/verify_delivery.py` | 检查本地Markdown链接、JSON可解析、来源字段、审计数字和时序输出哈希；结果见下方机器记录 |
| Git原始目录 | `git diff --exit-code -- 01_比赛规范 02_提交模板 03_A赛道 04_B赛道` | 无变更；工作区仅新增研究资料与根README入口 |
| 差异格式 | `git diff --check` | 通过；未自动检查未跟踪文件的全部排版 |

机器记录：[delivery_checks.json](../audit/delivery_checks.json)。文档检查只验证本地文件目标存在，不声称网络链接全部可用；外部URL按来源报告逐条记录阅读范围及失败情形。

最终检查通过：13份Markdown文档、75个本地目标链接、15份JSON解析及16份时序输出哈希；来源登记为15条研究/模型依据和13项官方数据候选，错误清单为空。检查器首跑曾把本轮自身生成的记录视为缺失，已修正生成顺序处理并复跑通过。

## 独立审查代理的抽查

- 用标准库CSV逐行重计全部24份小时文件，各年数值在场、首末边界、QC总表、事件日63字段24/24和37个QC字段全0与报告一致。
- 直接读原DBF，确认84条记录的解译日期均为2020-07-25，影像日期计数一致；未误作事件发生时间。
- 抽读2005/2024/2025逐日XLSX，确认365/366/214日和2025-08-02截止。
- 直接读NC属性，确认2014—2024速度气候态和无时间轴。
- 独立按GeoTIFF元数据提取略包住NC区域的144×169矩形，四年每幅24,336格全为0，支持mask区域无有效土地覆盖的粗诊断。尚未进行正式CRS变换或精确面域叠加。
- 重新提取题面四页文字，确认任务矩阵覆盖四问。
- 未发现需要阻断阶段1/2交付的实质问题；未全面复审外部来源或最后的综合文档，也未独立重抓USGS/GFS接口。

## 图像检查

时序`quality_overview.png`及空间`spatial_coverage_diagnostic.png`均已实际打开目视检查，标签、图例、范围和限制说明可读；时序首次左标签裁切已修复。图中“在场率”不作为QC通过率，空间矩形不作为有效覆盖面。

## 当前未验证的内容

正式GIS/NetCDF4/GRIB处理管线、源区与河道精确空间连通、外部影像获取/云影可用性、数据提供方原版全量一致性、事件标签/真值与发布延迟、核心模型和科学结论、队员人工采用与修改。以上均不能由本次脚本通过替代。

本轮无commit/push；审计产物保存在本地分支`codex/track-b-stage1-2`。
