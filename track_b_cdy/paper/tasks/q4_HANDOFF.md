# Q4 论文工作包交接

已完成成果导向中文章节：约2600汉字、3个公式、2幅复合图、3张表。单节预览为4页正文＋1页参考文献；全文集成后的图号、引用顺序与最终页数由主参谋统一编排。只写本问论文责任区，研究包及33,934项科学缓存只读，没有重跑物理模型。

## 文件与内容

- `sections/q4.tex`：空间与释放设计→深度平均方法／响应定义→全源面ST过程及结构对照→源项与数值评价；以p0036-ST／120m为主过程，保留60m、D-Claw扩域孔压与复合固水状态。
- `figures/q4/process_fullmask_st120.pdf`及300dpi PNG：真实存帧0、180.6、600.2、1800.5 s，统一对数流深色标与J/P代表点。
- `figures/q4/model_comparison.pdf`及PNG：ST双格网1800s内累计最大厚度，D-Claw180s基底压力及复合固水180.5s水相份额。压力0—1kPa线性、1—600kPa对数显示。
- `figures/q4/preview/q4_preview.pdf`及5页审阅图：使用共享documentclass／preamble；`q4_preview.tex`仅为独立编译包装。已复用主参谋同步的bbc7b5a字体修复，未改公共preamble。
- `evidence/q4_claims.json`：25条声明，绑定repo相对来源路径与SHA；外部NPZ另以`source_arrays`记录实际路径／SHA及repo索引。
- `evidence/q4_numeric_review.json`：9份NPZ只读核对、正式1800s与实际末帧两套统计，以及实际过程帧。
- `evidence/q4_references.tex`与`q4_reference_review.json`：5条实际引用，作者、题名、年份、DOI及实际阅读范围。
- `evidence/q4_code_files.json`：自编有限体积模型、接口／后处理／论文绘图源码，第三方求解器单列。
- `evidence/q4_plot_manifest.json`、`q4_visual_review.json`、`q4_validation.json`：输入／输出绑定、实际页审及末尾核对结果。

## 数值与叙述核对

主参谋定点复核后已明确写出“全岩交叠0.3s、关闭drag／VM交叠0.4s”，并区分15m释放厚度与120m格网。独立代理对正文体积、密度、SH/STH自由水0、4设计／7运行／49目标、阶段时刻／湿面积／峰深、目标括号和两类质量账逐项核对。ST／120m和60m的正式1800s内足迹为23.0112／12.1608km²，末帧分别1800.5／1801.2s；主过程图末帧单列，不混用为正式足迹。D-Claw扩域采用全域60.899m／83.3904km²，没有混入原核心参考41.049m／51.48km²。

表3分开r.avaflow原生内部终态预算与D-Claw总域质量变化，侵蚀新增源单列。相模型为岩冰复合固体＋水、中间固相空；drag／VM关闭只改变这两类项。有效应力与未知启动至释放延迟、0个本地独立事件和无统计权重保持原义，正文以给定条件下的过程响应组织。

## 复跑命令

从worktree根执行：

```sh
track_b/.venv/bin/python track_b/paper/scripts/q4_plot_results.py
bash track_b/paper/scripts/q4_compile_preview.sh
pdftoppm -r 140 -png track_b/paper/figures/q4/preview/q4_preview.pdf track_b/paper/figures/q4/preview/q4_page
track_b/.venv/bin/python track_b/paper/scripts/q4_validate_paper.py
```

绘图脚本直接核验冻结NPZ SHA，并输出确定性图像和plot manifest；已实际重绘一次，2个PDF与2个PNG全部逐字一致。编译使用现有XeLaTeX和共享字体文件名，双遍后无overflow、未解析引用或缺字；参考文献3条underfull排版提示不影响可读性。最终5页已逐页实际打开，公式、图例、色标、表注、页码无遮挡／裁切。

## 来源与AI贡献

数值来自R3最终v4及实际场索引，主过程运行身份、源面体积、各相状态和预算分别保留。r.avaflow v4原论文算例为Revision6，本研究实际执行为固定Rev7／20250902；D-Claw理论与1.0.0软件分别引用。Copernicus数据集DOI的出版年为2022，实际栅格release2021与主要获取2011—2015分别登记。

正文整理、绘图／校核程序、证据索引和版式检查由OpenAI Codex辅助；两个辅助代理分别核对数值和原始／官方文献。队员负责最终解释与采用。正文末尾已使用共享`\AIcredit`。

## 提交与集成

仅本问paper文件本地提交，不push。共同论文基线为`eecf07db7873b3c2c63275fa0b419867d8bdd3b2`，已有共享字体提交`bbc7b5a`属于主参谋公共工作，不重复交付。此交接本身属于本问提交，完整提交哈希随最终交付消息提供，可用`git log -1 -- track_b/paper/sections/q4.tex`查询。集成时按Q4前缀合并label与5条bibitem，引用顺序由总表重排；预览包装与PNG页审不加入主文。
