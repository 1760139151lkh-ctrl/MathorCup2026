# DeepSeek_A —— 2026 MathorCup 大数据竞赛 赛道 A 完整解答

本题为「赛道 A：啤酒酿造化合物分析与啤酒风味预测」。本目录包含**完整论文、全部源代码、可复现结果、
官方 3.xlsx 格式评分表与 AI 工具使用说明**，对应初赛三个问题的完整求解。

> 说明：目录名 `DeepSeek_A` 即「DeepSeek + 赛道 A」。论文首页的「队伍编号/赛道」表格中，
> 队伍编号为占位符 `MCB26XXXXX`，**提交前请替换为本队实际报名号**；赛道已填 A。

## 1. 交付物一览

| 路径 | 内容 |
| --- | --- |
| `paper/A赛道论文_DeepSeek队.docx` | 论文源文件（可编辑，30 页，正文 22 页 + 附录） |
| `paper/A赛道论文_DeepSeek队.pdf` | **提交用论文 PDF**（16:9 A4，目录页码、页脚页码齐全） |
| `paper/AI工具使用详情说明.pdf` | 竞赛 AI 规定要求的「AI 工具使用详情说明」 |
| `results/Q1_评分表_3xlsx格式.xlsx` | **问题 1 最终答案**：按官方 3.xlsx 评分卡格式填写的 12 款啤酒 0–6 分评分表 |
| `results/Q1_pred_grades_0to6.csv` | 问题 1：250 款啤酒 × 50 维的 0–6 分级评分矩阵 |
| `results/Q1_pred_grades_long.csv` | 问题 1：同上，长表格式（样本×维度×等级） |
| `results/Q1_pred_z.csv` | 问题 1：连续 z 值预测（未离散化，便于二次分析） |
| `results/Q2_top3_table.csv` | 问题 2：50 个感官维度的 Top-3 关键化合物 + 稳定性 + 合理性指标 |
| `results/Q2_importance_aggregate.csv` 等 | 问题 2：五方法重要性聚合矩阵、bootstrap 频率、社区划分 |
| `results/Q3_generated_Tripel.csv` 等 | 问题 3：Tripel / Kriek / Lambic 各 200 条生成化合物谱（1.csv 原始量纲） |
| `results/Q3_transfer_Pils_to_Tripel.csv` | 问题 3：11 款 Pils/Lager → Tripel 迁移后的化合物谱 |
| `results/Q3_sensory_portrait.csv` | 问题 3：三风格生成样本的 50 维感官画像（z 值 + 0–6 等级） |
| `results/*.json` | 三个问题的模型卡片、数据核验报告、汇总指标 |
| `figures/*.png` | 论文全部 15 幅图（220 dpi，可单独使用） |
| `code/*.py` | 全部源代码（按序号运行即可复现） |
| `data_processed/` | 预处理后的特征矩阵、感官标签、缺失填补结果、可逆变换器 |

## 2. 复现方式

环境：Windows + Python 3.13（numpy / pandas / scipy / scikit-learn / matplotlib / networkx / torch）。
在 `code/` 目录按下列顺序运行（总耗时约 45 分钟，主要耗时在问题 1 的模型交叉验证）：

```text
python 10_preprocess.py            # 数据核验（2.csv 相关性类型、1.csv 对数底数、量纲）
python 20_dataset.py               # 缺失填补、秩-高斯变换、0–6 等级反演参数拟合
python 21_q1.py                    # 问题 1：7 模型 × 3 次重复 5 折交叉验证、缺失鲁棒性（约 31 分钟）
python 22_inversion_validation.py  # 0–6 等级反演仿真验证
python 23_finalize_q1.py           # 生成 0–6 评分并填制 3.xlsx 官方评分表
python 24_q2.py                    # 问题 2：共表达图 + Top-3 + bootstrap 稳定性（约 1.5 分钟）
python 25_q3.py                    # 问题 3：PPCA/CVAE 生成 + 三风格画像 + 跨风格迁移（约 1 分钟）
python 26_redraw_figures.py        # 重绘问题 1 图件（论文用，去除图内编号）
python 50_build_paper.py           # 生成论文 DOCX
python 51_toc_pages.py             # 从 PDF 抽取目录页码（二次排版用）
python 60_build_ai_statement.py    # 生成 AI 工具使用详情说明 DOCX
```

说明：`code/` 中各脚本的随机种子已固定，结果可复现；`data_processed/`、`results/`、`figures/`
中的文件均由上述脚本生成，无需人工干预。

## 3. 核心结论摘要

- **数据核验**：1.csv 的 37 个参数列为 log10 变换值（pH、乙醇、色度、苦度、CO₂ 等亦然）；
  2.csv 实为 **Spearman** 相关矩阵（与重算结果 r=0.9999，Pearson 假设下仅 0.82）；
  4.csv 为逐品评员 z 化后的连续感官值，需反演为 0–6 等级。
- **问题 1**：秩-高斯 + 极端随机树在按风格分层 3×5 折交叉验证下平均 R²=0.242，50 维全部为正；
  30% 特征缺失时 R² 仅下降 0.019；0–6 反演与参考等级完全一致率 50.2%、±1 级以内 90.4%
  （仿真上限 86.2% / 99.7%）。
- **问题 2**：218 节点、591 边、模块度 0.649 的共表达图识别出酵母酯类/酒花萜烯/美拉德呋喃-吡嗪等模块；
  Top-3 在 100 次 bootstrap 下平均入选频率 0.500、方法间 Jaccard 0.337；仅用 Top-3 保留全特征
  87.2% 的预测信息；X4VG、乙酸阈值效应显著（p=1.4×10⁻¹²、9.5×10⁻⁷）。
- **问题 3**：CVAE 风格保真度 0.90/0.94/0.99、感官画像相关 0.88/0.96/0.99；跨风格迁移使
  Pils/Lager 的 Tripel 判别概率 0→0.48、感官相关 −0.14→0.81，四项化学缺陷逐样本不恶化率 100%。

## 4. AI 工具使用

按竞赛 AI 使用规定，本作品使用 DeepSeek（DeepSeek-V3.2，深度求索）作为辅助工具，使用日期 2026-10-23，
用途包括分析脚本辅助编写与调试、绘图脚本、论文文字润色与排版；核心建模、算法设计、结果分析与结论由
参赛队完成，并对 AI 生成内容逐项验证与修改。详见 `paper/AI工具使用详情说明.pdf` 与论文文末声明。

## 5. 备注

- 论文与说明中的统计数据均与 `results/` 下的 JSON/CSV 一一对应，可由脚本重新生成。
- 原始附件未做任何修改，全部处理结果另存于 `data_processed/`、`results/`。
- `paper/toc_pages.json` 为目录页码缓存，重新生成论文时可删除后按 50→51 顺序重跑以更新页码。

