# A 赛道复原解答：啤酒感官评分与风味指纹

本目录是 2026 年 MathorCup 大数据挑战赛 **赛道 A（啤酒酿造化合物分析与啤酒风味预测）** 的完整解答、
论文与支撑材料。解答先在数学等价的「脱敏版」数据上完成（编码变量 V001–V231、Y01–Y50、R01–R22），
再逐项复原为原题的啤酒语义。**原始附件 1–8 未做任何修改。**

## 一、交付物一览

| 路径 | 内容 |
| --- | --- |
| `paper/A赛道论文_啤酒风味复原版.pdf` | **提交用论文 PDF**（正文 29 页 + 参考文献 + AI 声明 + 附录） |
| `paper/A赛道论文_啤酒风味复原版.docx` | 论文源文件（可编辑） |
| `paper/AI工具使用详情说明.pdf` / `.docx` | 竞赛人工智能工具使用规定要求的 AI 使用详情说明 |
| `results/Q1_评分表_官方3xlsx格式.xlsx` | **问题 1 最终答案**：按官方 3.xlsx 格式填写的 12 张评分卡 + summary（600 个卡片分数格、600 个 summary 格，逐格回读一致） |
| `results/Q1_连续评分预测_*.csv` | 250×50 连续感官预测（全拟合 / 折外） |
| `results/Q1_0-6分级_协议A_*.csv` 等 | 250×50 的 0–6 工作等级（协议 A/B、全拟合/折外）与敏感性 |
| `results/Q1_逐维度交叉验证指标.csv` 等 | 问题 1 的模型比较、共形区间、等级可识别性 |
| `results/Q2_Top3关键化合物_汇总.csv` | **问题 2 答案**：50 个感官维度 × Top-3 关键化合物 + bootstrap 频率 + 模块 |
| `results/Q2_Top3关键化合物_明细.csv` | 150 个席位的完整证据（Borda 名次、三方法分数、模块、来源、阈值） |
| `results/Q2_网络节点与模块.csv`、`Q2_网络边.csv`、`Q2_共变模块构成.csv` | 共变网络（266 条边、120 个社区）与模块化学构成 |
| `results/Q2_阈值折线检验_*.csv` | 1050 组阈值 hinge 检验（BH/HC3） |
| `results/Q3_生成化合物谱_Tripel/Kriek/Lambic.csv` | **问题 3 答案**：三类各 100 条结构一致的化合物谱（231 列，1.csv 记录刻度） |
| `results/Q3_生成感官画像_D04尺度.csv`、`Q3_生成感官画像_0-6工作等级_协议A.csv` | 300 条生成样本的 50 维感官画像与工作等级 |
| `results/Q3_跨风格迁移_PilsLager到Tripel_迁移前/后.csv` | **问题 3 答案**：11 款 Pils/Lager→Tripel 的迁移配方 |
| `results/Q3_迁移_缺陷化合物对照.csv`、`Q3_迁移_陈酒花味Y38安全对照.csv`、`Q3_迁移_安全判据汇总.csv` | C1–C4 缺陷与 Y38 的逐对象安全对照 |
| `results/Q3_迁移可行性下界_W1.csv` | “逐对象不恶化 vs 完整匹配目标分布”的一维 Wasserstein 下界 |
| `results/参照表_*.csv`、`核验_*.csv` | 编码↔原题映射表、数据核验结果 |
| `figures/*.png` | 论文全部 13 幅图 + 2 幅附录图 + 30 个公式图片 |
| `code/*.py` | 恢复、补充分析、绘图、评分卡、论文排版脚本（见下） |
| `code/full_pipeline_project/` | 脱敏版完整计算工程（12 个脚本 + 8 个数据文件；运行 `run_all.py` 可复现问题 1–3 全部数值） |
| `code/_impl_spec.md` | 完整计算工程的逐脚本实现规格说明（参数、种子、公式、限制） |

## 二、复原方法（脱敏版 → 原题）

1. **数值等价核验**：`code/labels.py` 的 `check_identity()` 逐元素比较 D01–D07 与 1–7.csv，
   全部 `True`（250×231 特征、50 个感官维度、231×231 相关矩阵逐元素相同）。
2. **标签翻译**：`code/extract_results.py` 按映射表把 V001–V231 → 1.csv 化合物名、Y01–Y50 → 4.csv 感官维度、
   R01–R22 → 22 个啤酒风格，生成 `results/` 下的复原结果；数值不做任何改动。
3. **评分卡**：`code/make_scorecard.py` 把问题 1 的 0–6 工作等级按 `映射_模板项目.csv`
   写入原题官方 3.xlsx 的对应分数格（A-16/F-16 无目标列，标 N/A）。
4. **论文**：`code/build_paper.py` + `code/paper_content_*.py` 生成 DOCX，`code/update_toc.py`
   从渲染后的 PDF 回填目录页码；公式由 `code/make_equations.py` 渲染为图片。

原始题面、附件与「脱敏版」对照材料见上一级目录：
`03_A赛道/`、`多通道测量数据_研究题目/`、`A题去生化_对照（勿上传）/`。

## 三、论文核心结果速览

- **数据核验**：37 个参数列为 log10 记录值；2/5/6.csv 均为 Spearman（平均偏差 1.6×10⁻¹⁶）；
  231 个特征仅 73 个缺失格，但删行会损失 25.2% 样本；复原 5 个派生量的精确关系（热量 + 四类 OAV 式加和，残差约 10⁻¹⁰）。
- **问题 1**：嵌套交叉验证选出 PLS(10)；随机 5 折平均 MAE=0.354（基线 0.417）、平均 R²=0.217（50 维全正），
  整风格留组 R²=0.157；90% 共形区间边际覆盖 90.1%、50 维联合覆盖 84%；协议 A/B 的逐格一致率仅 23.4%，
  原始 0–6 等级不可唯一还原，已按公开协议给出 250×50 工作等级并填制 3.xlsx。
- **问题 2**：|ρ|≥0.6 共变网络：266 条边、19 个非单点模块、模块度 0.745；Top-3 由三视角 Borda 聚合给出，
  200 次 bootstrap 入选频率中位数 0.41、方法间平均 Jaccard 0.27；阈值 hinge 1050 组检验中 BH 校正后 174 组显著。
- **问题 3**：226 基础量 + 5 派生量的结构一致生成，留出能量距离 22.47（全局 29.65）；三类各生成 100 条，
  画像与真实风格均值相关 0.88/0.96/0.97；11 款 Pils/Lager→Tripel 迁移的四项缺陷与陈酒花味 Y38 全部逐对象不升高，
  分类器判定 Tripel 概率由 2.4% 升至 39.1%；一维 Wasserstein 下界说明“逐对象不恶化”与“完整匹配目标分布”不可兼得。

## 四、复现步骤

```bash
# 0) 环境：Python 3.11+；依赖见 code/full_pipeline_project/README.md
# 1) 运行完整计算工程（约 30–50 分钟；结果为编码标签）
cd code/full_pipeline_project
python A题_数学手记/code/run_all.py

# 2) 复原为啤酒语义的结果
cd ../..
python code/extract_results.py

# 3) 补充分析（额外缺失实验、风格保真度、迁移判别概率）
python code/extra_analyses.py

# 4) 论文图 + 公式
python code/make_figures.py
python code/make_equations.py

# 5) 官方 3.xlsx 评分表
python code/make_scorecard.py

# 6) 论文（DOCX → PDF → 回填目录页码 → 再导出 PDF）
python code/build_paper.py
# 用 LibreOffice 将 paper/A赛道论文_啤酒风味复原版.docx 转为同名 PDF
python code/update_toc.py
python code/build_paper.py
# 再次用 LibreOffice 转为 PDF

# 7) AI 使用说明
python code/build_ai_statement.py
# 用 LibreOffice 转为 PDF
```

> 说明：`code/full_pipeline_project/` 中的数据为脱敏编码版（与 1–8.csv 数值相同）；之所以不直接读原题附件，
> 是为了保留“先在等价砂箱上求解、再复原标签”的可追溯过程。两者数值一致性由 `labels.py` 自动核验。

> 克隆仓库后：对照目录 `A题去生化_对照（勿上传）/` 不会随仓库提供，`labels.py` 会自动退回
> `results/参照表_*.csv` 完成同样的标签复原（已测试两种模式结果完全一致）；`code/full_pipeline_project/`
> 自带数据，运行 `run_all.py` 即可生成 `extract_results.py` 所需的 `A题_数学手记/results/`。

## 五、AI 工具使用

按竞赛规定，论文在参考文献后给出「AI 工具使用声明」，并单独提交《AI 工具使用详情说明》。
本作品使用 DeepSeek（DeepSeek-V3.2，深度求索，2026-10-26）辅助了**部分论文段落的文字组织与润色**、
绘图/排版脚本的语法检查与文档整理；核心建模、算法设计、参数选择、结果计算与结论由参赛队独立完成并逐项核验。
详见 `paper/AI工具使用详情说明.pdf`。

## 六、注意事项

- 论文首页的队伍编号为占位符 `MCB26XXXXX`，提交前请替换为实际报名号；
- 论文 PDF 文件名若按提交规范命名，应为 `A<队伍编号>.pdf`（如 `A2600001.pdf`），
  支撑材料命名为 `A<队伍编号>附件.zip`；
- 原始数据与题目版权归 MathorCup 组委会与原始数据作者所有，本目录仅用于参赛与学习。
