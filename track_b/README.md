# 赛道 B 工作入口

目标：围绕“泥石流灾害预报及防灾策略”组织可追溯研究。原始资料位于[`04_B赛道`](../04_B赛道/)，本目录保存审计、任务口径、调研与后续派生成果。

**中文完整初稿已形成。** 直接阅读[论文PDF](paper/output/赛道B论文初稿.pdf)、[AI工具使用详情说明](paper/output/AI工具使用详情说明.pdf)和[LaTeX工程](paper/README.md)。正文连同参考文献和声明27页，补充参数及完整自编程序列于附录。四问方法、结果与图表已统一集成，当前进入队员集中阅稿与修改；状态见[STATUS](STATUS.md)。研究底稿与主方案/挑战方案依据保留于[第三轮联合审查](docs/19_stage4_round3_review.md)。

[第二轮工作流](docs/16_stage4_round2_workflow.md)已实施：沿用四窗/环境，r2分支与round2目录隔离；147项稳定产物、8组集成检查通过，首轮成果不改。本轮[工作窗登记](audit/stage4/round2/workspaces.json)，四份路线建议由联合报告链接。

主仓复核第二轮历史交付：`track_b/.venv/bin/python track_b/scripts/review_stage4_round2.py`；不重跑阶段3生成管线。首轮历史见[首轮联合审查](docs/15_stage4_round1_review.md)。

阶段4首轮历史入口：[四问并行工作流](docs/14_stage4_workflow.md)、[研究窗约定](research/AGENTS.md)。各窗任务为[Q1](research/q1/TASK.md)、[Q2](research/q2/TASK.md)、[Q3](research/q3/TASK.md)、[Q4](research/q4/TASK.md)；聊天与worktree登记见[audit/stage4/workspaces.json](audit/stage4/workspaces.json)。

阶段3先读：[技术交接与四问基线工作包](docs/13_stage3_handoff.md)。

[第三轮工作流](docs/18_stage4_round3_workflow.md)已实施，[四窗与提交登记](audit/stage4/round3/workspaces.json)保留源提交、集成提交及缓存位置。各问独立复跑见[Q1](research/q1/round3/REPRODUCE.md)、[Q2](research/q2/round3/REPRODUCE.md)、[Q3](research/q3/round3/REPRODUCE.md)、[Q4](research/q4/round3/REPRODUCE.md)。原环境及前两轮保留，新增研究位于各问round3；重跑前按对应文档选择局部环境、固定容器及缓存，不重跑旧公共生成管线。

## 推荐阅读顺序

1. [当前状态与下一动作](STATUS.md)
2. [四问任务矩阵](docs/01_task_matrix.md)
3. [统一口径与验证协议](docs/02_definitions_validation.md)
4. [时序与逐日气温审计](docs/03_temporal_audit.md)
5. [GIS、冰川与人口资料审计](docs/04_spatial_audit.md)
6. [文献与补充数据源登记](docs/05_research_sources.md)
7. [综合判断、P0缺口与下一阶段工作包](docs/06_synthesis_next_steps.md)

阶段3专项：[实施范围](docs/08_stage3_spec.md)、[时序管线](docs/09_temporal_pipeline.md)、[正式GIS管线](docs/10_spatial_pipeline.md)、[事件与遥感](docs/11_event_remote_evidence.md)、[环境与预报](docs/12_environment_forecast.md)。

辅助入口：[当前决定与待定选择](DECISIONS.md)、[AI辅助记录](AI_USAGE.md)、[协作与恢复约定](AGENTS.md)。

## 重现阶段3数据管线

隔离环境为`track_b/.venv/`，版本锁与重建命令见[环境说明](docs/12_environment_forecast.md)。在仓库根运行：

```bash
track_b/.venv/bin/python track_b/scripts/capture_stage3_environment.py
track_b/.venv/bin/python track_b/scripts/prepare_temporal.py
track_b/.venv/bin/python track_b/scripts/prepare_spatial.py
track_b/.venv/bin/python track_b/scripts/prepare_forecast_sample.py
track_b/.venv/bin/python track_b/scripts/collect_event_remote.py --verify-only
track_b/.venv/bin/python track_b/scripts/verify_stage3.py
```

派生结果位于`data/processed/`，有界外部样本与元数据位于`data/external/`，6组集成验证证据见[audit/stage3/integration_checks.json](audit/stage3/integration_checks.json)。外部来源联网刷新、图像重新验收及尚缺科学证据见[交接](docs/13_stage3_handoff.md)。

## 重现阶段1—2审计

从仓库根目录执行。前两条只需Python标准库；阶段1—2时序和空间审计使用当时本机已有Anaconda环境，该阶段没有安装新依赖。默认输出会更新`track_b/audit/`中的派生审计文件，原始文件只读。

```bash
python3 track_b/scripts/audit_inventory.py
python3 track_b/scripts/audit_environment.py
/usr/local/anaconda3/bin/python track_b/scripts/audit_temporal.py
/usr/local/anaconda3/bin/python track_b/scripts/audit_spatial.py
python3 track_b/scripts/verify_delivery.py
```

官方事件元数据单独读取（需要网络；保留当前审计快照以便核对版本变化）：

```bash
python3 track_b/scripts/fetch_event_metadata.py
python3 track_b/scripts/probe_forecast_archive.py
```

- [原始资料清单与SHA-256](audit/inventory/original_manifest.csv)、[完整性摘要](audit/inventory/summary.json)
- [时序机器报告](audit/temporal/summary.json)、[空间机器报告](audit/spatial/summary.json)
- [运行时与依赖清单](audit/environment.json)、[USGS事件元数据快照](audit/event_metadata.json)
- [历史GFS最小获取通路](audit/forecast_probe/summary.json)：只取索引与16字节GRIB头，不下载全球场或建立模型。
- [文献与产品结构化登记](audit/research_sources.json)

审计脚本产生的“数值在场”不等于QC通过，更不等于物理合理；空间包络相交不等于精确多边形裁剪。具体定义及限制见相应报告。

## 当前协作方式

主参谋统一问题口径、共享输入和阶段证据；独立工作包按文件责任并行推进；队员承担核心建模和最终科学判断。任何技术路线仍须通过数据可行性、队员审视和后续验证。本目录的实验候选不会自动成为已确认决定。

仓库沿用原README的分支协作方式。主参谋沿用`codex/track-b-stage1-2`，阶段4四窗使用独立worktree及各自分支。用户已授权本地保存共同基线和研究交接；本轮不推送远端。
