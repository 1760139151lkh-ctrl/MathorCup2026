# 阶段 3 E03：时序标准化最小闭环

日期：2026-10-23（America/New_York）。本工作包只准备可追溯的数据与质量视图；没有插补、重采样、物理阈值删值、衍生特征、训练或核心建模结果。原始资料只读。

## 本轮交付与运行

入口脚本：[prepare_temporal.py](../scripts/prepare_temporal.py)；显式策略：[temporal_policy.json](../config/temporal_policy.json)。正式运行使用仓库独立 Python 3.12 环境，命令在仓库根目录执行：

```bash
track_b/.venv/bin/python -u track_b/scripts/prepare_temporal.py
```

默认产物在 [data/processed/temporal](../data/processed/temporal/)。另设 `--out` 可写入新的派生目录；脚本拒绝向两份原始附件目录内输出。现有派生产物可以重建，原始资料保持原样。

本轮实际保留 **52,584 个完整小时、63 个测量字段、37 个原始 QC 字段**。逐日表独立保留 **7,519 日 × 5 县 = 37,595 个原值**，范围为 2005-01-01 至 2025-08-02。没有把县域再分析表拼接成塔站观测，也没有把 2025 年补成完整年。

| 小时单元状态 | 数量 | 含义 |
|---|---:|---|
| 全部测量单元 | 3,312,792 | 63 字段 × 完整 52,584 小时时间轴 |
| 数值在场 | 2,769,457 | 有限数值，且不是 9999.9；不等于质量合格 |
| 9999.9 哨兵 | 222,341 | 数值表中仍保留原值，另设哨兵掩膜 |
| 文本缺测 | 320,994 | `NaN` 315,345 个、`NAN` 5,649 个，精确词法单独保留 |
| 严格 QC0 视图 | 1,712,112 | 数值在场且原始配对 QC=0；其他位置为 null |
| QC 未知 | 1,367,184 | 26 个无 QC 字段 × 52,584 小时；不能自动判定合格 |

前三个数值状态满足 `2,769,457 + 222,341 + 320,994 = 3,312,792`。QC 未知是一种质量标记状态，与数值缺测状态分别记录，不能与前三项继续相加。`Precip(mm)` 与 FLUX 的 25 个变量均属于 QC 未知。

## 文件与关联方式

所有小时宽表严格保留原完整时间轴和相同行序。`hourly_time_axis.parquet` 的 `hour_index` 是从 0 开始的行号；其他小时宽表的第 `hour_index` 行与其对应。不要只重排其中一张表后按行拼接。原文缺测长表包含显式 `hour_index` 与 `variable_id`，逐日表拥有自己的来源日标签与原文件行号。

| 文件 | 内容 |
|---|---|
| [hourly_time_axis.parquet](../data/processed/temporal/hourly_time_axis.parquet) | `hour_index`、UTC、UTC+8、来源无时区时钟、时区假设标记 |
| [hourly_raw_numeric.parquet](../data/processed/temporal/hourly_raw_numeric.parquet) | 63 变量原数值；9999.9 保留；NaN/NAN 在本表是 null |
| [hourly_raw_text_missing.parquet](../data/processed/temporal/hourly_raw_text_missing.parquet) | NaN/NAN 的原始大小写、变量与小时行号，避免词法缺测被静默抹去 |
| [hourly_raw_qc.parquet](../data/processed/temporal/hourly_raw_qc.parquet) | 37 变量对应的 QC 原字符串；配对关系见字典，保留原列大小写 |
| [hourly_provenance.parquet](../data/processed/temporal/hourly_provenance.parquet) | 各类别逐行的原 CSV、含表头的 1 基行号、原时间字符串 |
| `hourly_mask_is_finite_numeric.parquet` | 有限数值掩膜，包含 9999.9 |
| `hourly_mask_is_missing_sentinel.parquet` | 数值 9999.9 哨兵掩膜 |
| `hourly_mask_is_text_missing.parquet` | 配置声明的 NaN/NAN/空词法缺测掩膜；本轮没有空字符串 |
| `hourly_mask_is_numeric_present.parquet` | 有限且非哨兵的数值在场掩膜 |
| `hourly_mask_qc_0/1/2/4/8/9.parquet` | 六份分别保存的 QC 分类掩膜；值来自原始相邻 QC 字段 |
| `hourly_mask_qc_unknown.parquet` | 无 QC 或无法识别 QC 的掩膜；本轮为 26 个未附 QC 的变量 |
| `hourly_mask_strict_qc0_accepted.parquet` | 数值在场与 QC0 的交集 |
| [hourly_strict_qc0.parquet](../data/processed/temporal/hourly_strict_qc0.parquet) | QC0 严格视图；保留 63 列及完整时间轴，26 个未知 QC 变量全部为 null |
| [daily_county_raw.parquet](../data/processed/temporal/daily_county_raw.parquet) | 来源日期标签、县域原值与文件/工作表/行号；不赋予 UTC 或摄氏度 |
| [data_dictionary.json](../data/processed/temporal/data_dictionary.json) | 全部 63 小时变量及 5 县变量的单位、高度/深度、QC、时钟、可用时间与限制 |
| [hourly_quality_summary.csv](../data/processed/temporal/hourly_quality_summary.csv) | 逐变量数值、哨兵、文本缺测、各 QC 与事件日计数 |
| `hourly_processing_counts.csv`、`daily_processing_counts.csv` | 逐文件/工作表读取行数和字段数 |
| [quality_summary.json](../data/processed/temporal/quality_summary.json) | 总计数、环境/脚本/配置版本、验证状态和限制 |
| [verification.json](../data/processed/temporal/verification.json) | 18 项实际检查及结果 |
| [input_manifest.json](../data/processed/temporal/input_manifest.json)、[output_manifest.json](../data/processed/temporal/output_manifest.json) | 输入/输出的大小与 SHA256；前后核对原始输入哈希 |

`hourly_mask_qc_0/1/2/4/8/9.parquet` 是表格中的简写，实际文件为 `hourly_mask_qc_0.parquet`、`hourly_mask_qc_1.parquet` 等六份，不是包含斜杠的文件名。

读取示例：

```python
from pathlib import Path
import pandas as pd

out = Path("track_b/data/processed/temporal")
clock = pd.read_parquet(out / "hourly_time_axis.parquet")
raw = pd.read_parquet(out / "hourly_raw_numeric.parquet")
strict = pd.read_parquet(out / "hourly_strict_qc0.parquet")
assert len(clock) == len(raw) == len(strict)
strict_with_clock = pd.concat([clock, strict], axis=1)
```

数值表不保存原小数的排版格式；完整词法可由哈希锁定的原文件、来源行号和原列名恢复。非数值缺测的原大小写另行保留。

## 时间、单位、QC 的采用边界

**小时 UTC+8 是明确记录的假设。** 来源是阶段 2 已阅读的同名 WaterNet 元数据镜像，本地 CSV 不带时区，本轮仍未取得远端下载文件并逐份核验相同版本。因此转换使用固定 UTC+8（`Etc/GMT-8`），展示使用 `Asia/Shanghai`，并保留原无时区时钟；计算不依赖电脑时区。转换与往返正确不意味着元数据版本假设已获证明。

本地首个非哨兵数值为 2021-04-23 11:00，镜像宣称开始日为 2021-04-26；两者均留在字典中，未按镜像开始日裁掉本地观测。降水的年度 00:00 哨兵保持原样，未平移、未填零。所有变量的小时标签究竟代表时段起点、末端、中心或瞬时值仍未被核实，特别不能据列名自行构造已知累计雨量区间。

**单位只整理标签，未转换数值。** 每个变量都有 `raw_unit_label`；无歧义的标签另存标准化文字，`mg/m2*s`、`kg/m*s2` 等斜杠与乘法结合不明确的标签不给出确定的规范单位。MET 的 1/2/4/10/20 m 高度、SOIL 的 0.1/0.2/0.4/0.8/1.6 m 深度及热通量 0.1/0.2 m 深度均从列名提取并逐字段记录，参考面与仪器方法未另行验证；其他未提供的仪器高度/深度明确为 null。FLUX 符号释义是列名解读，通量正方向、FC 物质种类、处理方法仍不据此确定。

**QC 掩膜不改写原值。** 0/1/2/4/8/9 依据镜像分别表示正确、可疑、错误、插补、缺失、未质控。六类与 unknown 逐单元互斥且穷尽所有小时单元。严格视图只接受“数值在场且 QC0”；QC4 的来源插补值仍保留于原值和插补标记视图，但不进入严格观测视图。本管线没有自行生成任何插补。QC0 尚需物理合理性检查，且站点仍是距受灾口岸约 65 km 的区域背景站，不能直接标成源区天气。

**每日表保留未决语义。** 来源说明只指出 ERA5-Land 日统计产品，未提供实际 CDS 请求、单位、日界、时区或县域聚合方法。数据字典因此保留 null；2 m 只来自原文件名，不证明实际 CDS 参数。没有做 K→°C，没有将日期标签当 UTC 午夜，没有把县均值当塔站值，也没有赋予原表缺失哨兵 9999.9 的确定含义（本轮候选值出现次数为零）。

小时和每日资料均无已核验的 `available_time`，只能供明确的事后描述或后续合规回报研究设计，当前不能宣称满足历史实时预警的信息条件。

## 实际验证与尚待核验

正式环境运行后，`verification.json` 的 **18 项检查全部通过**：

- 用标准库 `csv` 重新读取全部 24 份小时文件，逐单元比对 3,312,792 个数值和 1,945,608 个 QC 原字符串，同时独立重新计数哨兵、缺测及各类 QC。
- 文本缺测的 320,994 条词法记录逐项对应原变量、原行号和大小写，并与掩膜计数一致；没有其他未知非有限词法被静默吞掉。
- QC 六类与 unknown 计数守恒；严格掩膜等于数值在场与 QC0 交集；严格值与被保留原值完全一致；严格视图没有 9999.9，也没有 QC 未知的值。
- UTC↔UTC+8 往返正确，各表保留完整相同行数；事件情景日 2026-08-26 的 63 变量均有 24 小时数值，37 个带 QC 变量均有 24 个严格 QC0 值，26 个未知 QC 变量在严格视图中仍为空。
- 用 `openpyxl` 另行读取 21 个工作簿，逐项核对 37,595 个县日原值和日期；与阶段 2 独立审计的小时网格、变量总数、每日总行数一致。
- 对包含 45 份数值文件、来源说明 DOC 和附图 JPG 的 47 份输入做前后 SHA256 核对，原始文件未改。

这些检查验证格式、转换实现、血缘与保留策略；没有验证数据的物理可信度、元数据与本地版本相同、预报当时可用性、每日表的单位/日界/聚合，也没有验证模型适用性。

下一步应优先取得原发布说明或 CDS 下载请求以核实时间与单位；随后由队员制定物理质量检查、各用途纳入规则和事件标签，才进入特征及基线建模。

## AI 辅助说明

本工作包脚本、配置、技术说明与验证代码由 Codex（OpenAI，2026-10-23）辅助生成和运行。精确模型版本在本工作包中未暴露，提交前需队员补齐工具版本及实际采用/修改情况。队员尚未完成人工验收；本工作包没有代替队员完成核心建模、算法求解或论文结论。
