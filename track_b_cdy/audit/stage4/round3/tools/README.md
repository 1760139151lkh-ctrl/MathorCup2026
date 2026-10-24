第三轮集成检查器 `review_integration.py` 只读各研究树及缓存，只将 `--report` 指定的 JSON 写入主仓库 `audit/stage4/round3/`，不调用第二轮旧检查器。它验证文件和版本交接，不能自动采纳科学结论。

```sh
track_b/.venv/bin/python track_b/audit/stage4/round3/tools/review_integration.py --mode setup --report track_b/audit/stage4/round3/setup_integration_checks.json
track_b/.venv/bin/python track_b/audit/stage4/round3/tools/review_integration.py --mode final --report track_b/audit/stage4/round3/integration_checks.json
track_b/.venv/bin/python -m unittest discover -s track_b/audit/stage4/round3/tools -p 'test_*.py'
```

`setup` 检查共同基线、五个 checkout 的历史保护字节，以及已出现的 export bundle；不要求研究中的窗口 clean 或已有最终提交。`final` 还要求四窗最终 source/integration commit、分支、清洁状态、五项退出检查、输入/输出清单、全部 contract bundle 和 `docs/19_stage4_round3_review.md`。缺最终字段或交付物输出 `incomplete`，退出码 2；内容不符为 `failed`，退出码 1；通过为 0。

清单只接受顶层列表或 `{"files": [...]}`，每项必须是 `path`、非负整数 `bytes`、小写十六进制 `sha256`。拒绝并列 `entries/artifacts` 列表、重复目标、自含、目录穿越、软链接越界和相对路径歧义。默认在问目录根部或 `results/` 查找 `input_manifest.json`、`output_manifest.json`，若在其他位置，可在该问 registry 项指定仓库相对路径 `input_manifest_path`、`output_manifest_path`。

输入清单的相对路径可引用仓库内冻结资料；输出和 export 的相对路径只能引用本问 `round3/`。清单支持无歧义的问目录相对路径，contract export 只接受仓库相对路径。绝对路径仅允许 R3 缓存：输入默认本问及 `runtime/`，输出和 export 仅本问。已审核分发的跨问缓存目录可在该问 registry 项 `accepted_cache_roots` 显式登记，限定在 R3 缓存下的具体目录，不能放行整个缓存；实际采纳证据仍由主参谋交接记录证明。目录中的文件按大小和流式 SHA256 验证，每次检查内去重缓存，不能仅凭存在性通过。

最终 registry 每问必需字段：`source_commit`、`integration_commit`、`git_branch`、`previous_branch`、`previous_source_commit`、`execution_root`。若填写 `output_files_verified` 或 `final_output_manifest_sha256` 也核对相符。版本和工具自身 SHA256 自动写入报告。工具不自动解释 handoff ledger，也不评估模型得分、事件独立性或概率含义。
