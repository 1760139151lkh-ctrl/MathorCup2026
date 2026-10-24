# 可移植输入清单 v3：仅元数据修订

此包解决集成审核对非批准 cache 绝对引用的限制。新 `input_manifest.json` 是已封存 `results/followup_v2/input_manifest.json` 的可移植视图：只把第 46–56 行的 11 个本 Q3 仓库路径转换为仓库根相对路径。原 62 行顺序及四组重复记录全部保留；其他行字段、目标 bytes、SHA256 和科研口径不变。规范化后是 55 个相对引用及 7 个原样保留的批准 Q4 cache 引用。

本包的可执行输入入口为 v3 清单。v2 清单仍保留其真实历史路径和原始字节，作为来源记录；本包没有重封它，也没有改写任一 v1/v2 清单、导出、源码或结果。`normalization_report.json` 用原清单行号、相对目标及原清单哈希追溯变换，避免把原绝对源码引用重新写入新元数据。源工作树路径前缀只用于词法识别，目标文件一律从执行当前脚本的仓库根解析，因此同一清单可在 Q3 源树与集成仓库逐项复核。未访问其他活动 worktree。

源 v2 输入清单 SHA256：`91d1dc933de07b435a625c4177252229785f3e58f5949c481301fdd5949816df`。原综合研究包 SHA256 仍为 `b134d88deadd2f2a5f92e954881dc3c38349a787ae41348e2245b7026fbdbb96`。规范化范围仅路径表示；不排序、不去重、不改变 cache 权限，不重新运行科学计算，不消费后续 fullmask 包。

新接口为 `exports/portable_manifest_bundle_v3.json`。`validation.json` 绑定新清单、变换记录和新接口，独立于旧封包。它不在 bundle 的 files 列表内，避免循环自哈希。固定风险集、unknown、空合格到达、未知机械启动至整体释放滞后、无到达概率和空经验覆盖率的边界不变。

在任一已集成当前研究产物的仓库根执行只读复核；不写文件，不依赖旧工作树文件位置：

```sh
track_b/.venv/bin/python track_b/research/q3/round3/scripts/portable_manifest_v3.py --verify-only
```

不带 `--verify-only` 只重建本 v3 元数据目录及新接口。正常集成仅需上述只读模式。旧 v1/v2 的封包脚本均不调用。
