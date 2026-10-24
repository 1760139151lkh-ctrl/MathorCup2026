# 赛道B完整论文初稿

本工程按用户已评审的第三轮结果制作中文完整初稿，以“气象因素识别—结构水热稳定性—启动时间预测—传播响应”为主线。论文正文、参考文献和声明控制在30页以内；参数补表与完整自编程序列为附录。本版正文连同参考文献和声明27页，前置摘要/目录2页，附录320页；独立AI说明5页。

## 阅读与编辑

- `main.tex`为论文主文件，章节位于`sections/`，统一排版与字体定义在`preamble.tex`。
- `ai_details.tex`为《AI工具使用详情说明》的独立源文件。
- `output/赛道B论文初稿.pdf`和`output/AI工具使用详情说明.pdf`为最终初稿PDF。
- `evidence/claim_index.json`关联论文论断、源表、图表、情景和来源哈希；各问交接位于`tasks/`。
- 图件由标准科学绘图工具读取现有结果生成，绘图程序及来源保留在工程。

## 一键构建

从仓库根执行，使用已锁定的原环境以及已安装的XeLaTeX/latexmk：

```sh
track_b/.venv/bin/python -B track_b/paper/scripts/build_paper.py --render
```

构建依次生成补充参数表、证据索引、按首次引用排序的参考文献、完整源码附录，编译论文和AI说明，执行论文检查，再写出PDF并渲染逐页检查图。此过程读取既有研究结果，直接重建论文材料。

独立源码包仅重排版时，在包含`main.tex`的工程根执行：

```sh
latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=build/main main.tex
latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=build/ai ai_details.tex
```

分步命令见`scripts/README.md`。正文PDF和相应aux/log位于`build/main/`，AI说明位于`build/ai/`。`qa/`保存来源、数值、文献、程序、页码、匿名和历史完整性检查；`qa/pages/`与`qa/contact_sheets/`为视觉检查缓存。

在Codex内打开工程文件夹即可编辑TeX和预览。独立复制源码包时，附带的图件、参考文献及代码显示副本支持直接排版；完整研究重放通过各问原REPRODUCE及数据缓存索引进行。

## 采用、表述与来源

用户已完成第三轮评审并批准论文计划，记录在`adoption_record.json`。论文按方法、结果和解释陈述成果，适用条件集中于定义、表注和模型评价。因素入选频率、设计空间计数、外部经验覆盖与模型条件概率各按其原定义呈现。

源研究包和第三轮分支保持可追溯。程序原字节副本保存在`code/`；PDF附录使用`code_print/`显示副本，仅对本机用户目录前缀做匿名替换，两种哈希均保留。第三方求解器登记固定版本、配置和引用。AI贡献与人工评审/修改分别记录于`AI_DISCLOSURE.md`及配套说明。

本初稿使用中性文件名，论文元数据和版面采用匿名形式。后续正式提交文件名按实际队号填写。所有改动与提交保存于本地。
