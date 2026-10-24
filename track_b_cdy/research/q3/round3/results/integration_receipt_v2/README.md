# Q3 当前已完成增量集成记录

有效载荷为 `bb9258d791a6e9735c28528ff4408c7434c3d149..f031f28c18ebf718b30876fd3250109e9ef11745`，顺序包含 `e54f0596ceb847c71afd628b9c16524e0b6774a5` 和 `f031f28c18ebf718b30876fd3250109e9ef11745`。共 130 个新增文件，无旧跟踪文件修改、删除或重命名。`integration_receipt.json` 逐项保留路径、字节数和 SHA256，并对原研究提交中已存在的全部 exports 逐字节比较；新增 v1/v2 导出不混入“旧 exports”统计。

本目录是随后独立新增的集成收据，两个文件均不改写任何已冻结封包。最终提交范围将有 132 个新增文件，其中 130 个为上述研究有效载荷、2 个为本收据。若主仓库已包含 bb9258d，可顺序集成上述两提交及本收据提交；最终收据提交 SHA 由聊天回报，避免文件自引用。原 `exports/research_bundle.json` 和旧事件／阶段证据接口保留原字节。

主接口为 `exports/r3_followup_bundle_v2.json`；详细说明为 `R3_FOLLOWUP_HANDOFF.md`。固定历史风险集与 already-started 质量保留，历史撤销只作附加诊断。unknown、空合格到达、未知机械启动至整体释放滞后、无到达概率的边界不变；QA 通过不意味着传播物理质量通过。本地独立真值仍为 0，经验覆盖率为空。

不等待后续 Q4 fullmask 包。本次未消费该包，未来仅在新交接范围更新受影响的 join 与清单，当前原始记录保留。

只读复核命令（研究有效载荷范围）：

```sh
git diff --name-status --no-renames bb9258d791a6e9735c28528ff4408c7434c3d149 f031f28c18ebf718b30876fd3250109e9ef11745
git diff --name-only --diff-filter=MDR bb9258d791a6e9735c28528ff4408c7434c3d149 f031f28c18ebf718b30876fd3250109e9ef11745
```
