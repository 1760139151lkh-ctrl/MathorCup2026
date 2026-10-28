# 脱敏版完整计算代码（与 A 题数值等价）

本目录是「多通道测量数据 · 研究性题目」的完整计算工程，用来复现论文中问题 1–3 的全部核心数值。

## 为什么可以用于 A 题

原题附件 `1–8.csv/xlsx` 与脱敏版 `D01–D08` **逐元素相同**，只是把列名、类别名、感官维度名换成了编码：

- `D01.csv` ↔ `1.csv`（231 个特征 V001–V231，250 个样品）
- `D02.csv` ↔ `2.csv`（231×231 Spearman 相关矩阵）
- `D03.xlsx` ↔ `3.xlsx`（评分卡模板）
- `D04.csv` ↔ `4.csv`（50 个感官连续值 Y01–Y50）
- `D05/D06/D07.csv` ↔ `5/6/7.csv`
- `D08.xlsx` ↔ `8.xlsx`（阈值、校准数据、重要性/归因等参考表）

数值一致性的逐元素核验见 `../../code/labels.py` 中的 `check_identity()`：
`chem=True, sensory=True, corr=True, feature_order=True, target_order=True, style_map=True`。

编码到原题标签的映射表（V↔化合物名、Y↔感官维度、R↔风格、模板项目↔目标列、阈值变量）在
`../../code/labels.py` 和原题对照目录 `A题去生化_对照（勿上传）/映射_*.csv` 中。本工程使用编码标签，
复原后的结果文件（带啤酒变量名）在 `../../results/` 与 `../../figures/`。

## 目录结构

```text
full_pipeline_project/
├── data/                        # D01–D08（与 1–8.csv/xlsx 数值相同，只改了标签编码）
└── A题_数学手记/
    └── code/                    # 12 个脚本
        ├── run_all.py           # 统一入口（按依赖顺序运行全部计算）
        ├── data_audit.py        # 数据核验（缺失、标度、相关类型、模板、归因）
        ├── derived_search.py    # 5 个派生关系的有限搜索与核验
        ├── derived_relations.py # 派生关系函数库
        ├── prediction.py        # 问题 1：嵌套交叉验证、共形区间、工作等级、评分卡
        ├── scoring_protocols.py # 协议 A/B、K 分布、迁移前后等级比较
        ├── grade_identification.py # 等级可识别性（部分识别）
        ├── network_analysis.py  # 问题 2：共变网络、三视角 Top-3、bootstrap
        ├── generation.py        # 问题 3 基线生成（条件高斯 copula、PPCA 对照）
        ├── empirical_copula.py  # 类条件收缩经验分布（零原子修复）
        ├── structure_generation.py # 问题 3：226 基础量 + 5 派生量的结构生成与约束迁移
        └── threshold_reports.py # 临界阈值全精度统一
```

## 运行方式

需 Python 3.11+，依赖：`numpy pandas scipy scikit-learn networkx matplotlib openpyxl joblib threadpoolctl`。

```bash
cd full_pipeline_project
python A题_数学手记/code/run_all.py
```

结果写入 `A题_数学手记/results/`（与原工程一致），主要文件：

- `question1_summary.json`、`question1_metrics.csv`、`question1_protocol_*.csv`
- `question2_summary.json`、`question2_top3.csv`、`question2_network_*.csv`
- `question3_*.json/csv`（生成、代表样本、迁移、可行性下界）
- `data_audit_*.csv/json`、`question1_grade_identification_*`

完整的运行时间约 30–50 分钟（主要耗时在问题 1 的嵌套交叉验证）。随机种子固定为 `20261026`；
在不同 BLAS/线程配置下，末位数字可能有微小差异属于正常现象。

## 与复原结果文件的关系

本工程输出的是编码标签（V/Y/R）的结果；`../../code/extract_results.py` 负责把编码标签翻译成
啤酒语义（化合物名、感官维度中文名、风格名），生成 `../../results/` 下的交付结果；
`../../code/make_figures.py` 生成 `../../figures/` 下的论文图。三者按
`run_all.py → extract_results.py → make_figures.py` 的顺序使用。
