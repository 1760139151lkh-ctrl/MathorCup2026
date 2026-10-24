# Q2 完整论文初稿交接

状态：本问论文工作包完成，可并入成果导向完整初稿。唯一工作树 `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2`，分支 `codex/track-b-q2-paper`。共同论文基线 `eecf07db7873b3c2c63275fa0b419867d8bdd3b2`；执行中同步主参谋公共字体/断行提交 `bbc7b5a2027a81ce358353061a0f305322a2c184`。本问提交号见最终聊天交接，亦可用 `git log -1 --format=%H -- track_b/paper/tasks/q2_HANDOFF.md` 定位与本文件同次交付的提交；未推送。

## 内容与采用口径

`sections/q2.tex` 为完整中文 section，约2865汉字，7组方程、3幅矢量图、3张表、3条实际引用，末尾使用共享 `\AIcredit`。结构为共同力学骨架、热水损伤推进、临界关系、2048设计比较、141原始实验的外部挑战。图/表/公式label均为`q2:`前缀，文献key均为`q2-`前缀。

采用最终解析热结果：线性分支 ST/STH 最小裕度中位为0.4853/0.4718；137个有限配对对细FD最大差约0.347h。水量/损伤仍为小时支持，水头单位压力另定义`gamma_w`避免将重力加速度直接作kPa/m。S保留损伤，SH保留空气正温融水但内部温度固定。临界图显式解释超容量星号、无压力根斜线和干态越阈灰格。

外部实验明确141试验与14派生温层分开，主暖域83试验，32拟合、576留组折，训练误差与跨应力泛化分列；仅保留低复杂度外部挑战，本地引擎/概率不改。计数、设计分位、bootstrap均值范围和本地独立事件分母保持原义。论文用方法、结果和解释组织，条件放在定义/图表注及相应解释处。

## 文件与证据

- 正文：`sections/q2.tex`。
- 三图：`figures/q2/q2_mechanism_comparison.pdf`、`q2_critical_head_sensitivity.pdf`、`q2_lab_grouped_validation.pdf`；附300dpi PNG及源数据/选择规则/哈希、实际视觉审阅记录。
- `evidence/q2_claims.json`：22条数值/方程/图文映射，含repo相对来源与SHA256、模型/情景、层级、论文锚点。
- `evidence/q2_references.tex`、`q2_reference_audit.json`：Mamot2018、Weber2025、Ben-Asher2026三个实际引用，原官方来源元数据与读取范围。
- `evidence/q2_code_files.json`：7份本节采用的自编模型/后处理/绘图程序，含路径与哈希，可供主参谋生成程序附录。
- `evidence/q2_numeric_audit.json`：122项独立核对通过，51个唯一源文件；最终正文、22claims、引用和三图快照绑定一致。
- `evidence/q2_layout_check.json`、`q2_layout_visual_review.json`：独立章节5页正文；另1页仅用于本节参考文献预览，共6页，全部已实际打开。预览PDF为`figures/q2/preview/q2_preview.pdf`。

参考文献由主参谋并入公共总表，预览中参考文献单独分页不代表整篇目录/页码。共享字体现已使用可复现文件名，最终预览未应用额外字体替换；Q2脚本只生成自己的预览副本，不改公共preamble或main。编译无overfull、缺字、未定义引用警告；最终页数由全文组装复核。

## 实际复跑顺序

在唯一工作树根运行，使用原44包venv，无安装、联网下载或大模型重算：

```bash
track_b/.venv/bin/python track_b/paper/scripts/q2_make_figures.py
track_b/.venv/bin/python track_b/paper/scripts/q2_prepare_evidence.py
track_b/.venv/bin/python track_b/paper/scripts/q2_compile_preview.py --render
track_b/.venv/bin/python track_b/paper/scripts/q2_review_paper.py --paper
track_b/.venv/bin/python track_b/paper/scripts/q2_finalize_paper.py
```

主编译器为现有XeLaTeX，图稿为matplotlib矢量PDF与300dpi PNG。图稿重绘或正文变化后，重新核对对应图/页并刷新视觉记录，再最终生成交付清单；`q2_review_paper.py`的手工阅读快照会如实提示正文变更，不把自动源码/数值检查当成再次人工阅读。

## 责任范围与AI贡献

本次仅新增/维护本问获准论文路径：`sections/q2.tex`、`figures/q2/`、`scripts/q2_*`、`evidence/q2_*`、本文件。历史研究包只读；共享正文、宏、参考文献总表、附录和其他问文件由主参谋维护。

AI参与文字组织、公式对照、绘图、证据映射和版面核验；三个并行代理分别负责参考文献/公式边界、矢量图重绘、独立数值与引用检查。所有源数据使用原取得资料，AI辅助说明由共享宏及主参谋总声明统一呈现。核心结果和来源条件保留，终稿的整体论证、语言及科学采用由队员审视。
