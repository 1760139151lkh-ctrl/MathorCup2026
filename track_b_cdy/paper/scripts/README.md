# 论文工程构建与核查

这些工具读取现有研究源文件，不运行模型、不修改研究包。默认从脚本位置确定仓库与论文根目录；可用 `--paper` 和 `--repo` 指定临时工程作技术测试。

在仓库根目录按顺序运行：

```sh
track_b/.venv/bin/python -B track_b/paper/scripts/build_evidence.py --require-all
track_b/.venv/bin/python -B track_b/paper/scripts/build_references.py
track_b/.venv/bin/python -B track_b/paper/scripts/build_program_appendix.py
# 在 track_b/paper 内完成 XeLaTeX/latexmk 编译后：
track_b/.venv/bin/python -B track_b/paper/scripts/verify_paper.py
track_b/.venv/bin/python -B -m unittest discover -s track_b/paper/scripts -p 'test_paper_tools.py'
```

`verify_paper.py --pdf /absolute/path/draft.pdf` 允许指定其他文件名，其 `.aux`、`.log` 应在同目录。当前最终验收使用 `--pdf track_b/paper/build/main/main.pdf`（从仓库根目录运行）。PDF文字检查使用原44包环境中的 `pypdf`；逐页渲染由主参谋排版检查完成。四个脚本的报告分别在 `qa/evidence_check.json`、`references_check.json`、`programs_check.json`、`paper_check.json`。历史完整性默认比较论文共同基线 `eecf07db7873b3c2c63275fa0b419867d8bdd3b2`，核对研究、数据、审计、配置、处理脚本、依赖锁和原始比赛资料，并按旧注册表核对四条R3分支；论文层和活动顶层文档可以调整。旧轮报告不重跑或改写。

## 章节接口

- `evidence/qN_claims.json` 及可选的 `common_claims.json`、`public_claims.json` 为列表或 `{"claims":[...]}`。仅以上明确文件名进入合并，不通配扫描 `claim_index.json`。每项保留章节声明，并以 `claim_id` 唯一标识。`source_files` 为 `{"path":"仓库相对路径","sha256":"64位哈希"}` 的列表；也接受明确的 `repo_path`／`file` 字段别名。合并后的 `claim_index.json` 不包含自身作为来源。
- `checks` 可选，用于逐项数值检查。JSON 示例：`{"source_path":"...json","json_pointer":"/summary/count","expected":13}`；CSV 示例：`{"source_path":"...csv","where":{"model":"A"},"column":"score","expected":0.5,"rtol":1e-8,"atol":1e-12}`。CSV条件必须选中唯一行；必要时明确 `row`。仅核对来源哈希的条目使用 `source_hash_verified_author_value_mapping` 状态，避免将来源核验等同于逐值复算。
- `evidence/qN_references.tex` 与 `common_references.tex` 包含 `\bibitem{key}`。脚本按 `main.tex` 递归展开 `\input` 后的首次引用顺序生成 `references.tex`；重复且冲突的key及缺失引用使构建失败。同key同内容去重并记录。
- `evidence/qN_code_files.json` 为仓库相对路径列表，或 `{"code_files":[{"path":"...","title":"程序用途","sha256":"可选的预期哈希"}],"third_party":[{"name":"框架","version":"固定版本","configuration":"配置索引"}]}`。自编列表别名接受 `files`、`programs`、`self_authored`、`self_authored_files`，条目用途接受 `title`、`description`、`role`；非空对象若无可识别列表将明确报错。报告按章节列出采用程序数，便于核查完整交付。自编代码按原字节复制到 `code/原仓库路径`，源码、哈希及行数进入 `evidence/program_manifest.json`；第三方框架仅登记版本。显示副本位于 `code_print/原仓库路径`，只用 `<LOCAL_HOME>` 替换 `/Users/<用户名>` 路径前缀，另记显示SHA和替换次数。`appendices/programs.tex` 通过论文根目录下的 `code_print/` 相对路径全文导入显示副本，长行折行且保留行号。`verify_paper.py` 同时核对原副本和显示副本，并对整份PDF（包括附录）扫描本机身份路径。

源文件已删除或哈希有变动时，不自动更新原声明哈希。修订应由相应章节作者核对来源，再明确更新章节证据记录。程序清单缩减后，旧的未引用副本不再进入清单和附录；脚本不自动删除文件。

## 技术测试

十二项临时fixture检查来源篡改、JSON数值、公共证据显式纳入且不重新导入生成索引、CSV唯一选择、真实引用顺序、冲突引用、完整源码和路径越界、正文页码标签解析、研究冻结/论文可写边界、Q4别名完整附录输出、未知代码清单明确报错、动态本机用户名匿名检测，以及第三方版本索引的人可读排版和完整JSON保留。第三方索引仅打印软件/依赖名称、版本、发布或短提交号及可折行URL；完整字段与SHA留在程序JSON索引。fixture在系统临时目录创建并清除，不进入论文证据。
