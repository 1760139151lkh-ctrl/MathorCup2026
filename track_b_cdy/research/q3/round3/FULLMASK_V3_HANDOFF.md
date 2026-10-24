# Q3 增量交接：全源面传播 v3

本包接在 `0d5326d6e3428df4d714d8101c41c7c925eca0ef` 后，只新增 fullmask 对接、保存场诊断、图和可移植清单。原 core、compact v2、适用性及 portable-manifest v3 均保留原字节；没有重新运行物理求解器或改变参数、先验、适用域规则。旧冻结范围共 **651 个 tracked Q3 round3 文件**，逐项 SHA256／字节保全记录见 `results/fullmask_v3/frozen_prior_files.json`。

## 输入版本与谱系

consumer 包 `inputs/q4/bundle_q4-r3-propagation-v3/bundle.json` 的 SHA256 为 `8457a9db624c33c0d0988ad8f4d8c8513ff21ac858ccff830bae577f77f0b683`；producer 快照 SHA256 为 `150c72537ee162d29cc2e20e3e31183df1915f64999234789e1875d368c09b9c`。66 个明确角色文件已逐字节核验。只读取本问复制的 metadata 与明确授权的 11 个 Q4 cache 对象；`source_path`、`upstream_path`、parser 源位置和容器二进制路径仅作历史溯源，不授予额外读取权限。

本次为 **3 运行 × 7 目标代表点 = 21 条**，来自 **2 个选定 base 参数情景**。五个 OSM 代表点对应三个候选实体，另有两个论文候选点；不是七个独立验证事件。采用 Q2 `release_bundle_v2` 的全候选源面，与旧 compact release-v1 不同。冻结 Q2 fullmask 表及 TIFF 与本包复制版本一致，原 base 至 analytic-erfc 的 20 个共同物理参数、law 与参数版本保持；热模型替换显式记录，不混用旧模型起始时刻。

- p0000-S 仍为 `no_cross_observed_complete`，没有机械启动时刻，传播只表示 **if released**。
- p0036-S_T 仍为实际解析条件机械跨阈区间 **2026-07-08 15:00–16:00 UTC**，线性插值 15:34:17.258933921 UTC。这是理想天气回顾情景，不能当作八月观测事件、整体释放真值或经验证的业务预报。

## 实际源量与保存场结果

实际源量逐项核对 Q2-v2 表、释放 TIFF、已执行 case、保存初态和 native t0。case 中遗留的 `expected_reference_grid_volume_m3=13,878,000` 只是旧参考字段，没有用作实际源量、预算分母或预测权重。机械法向厚度与网格竖直厚度分别保留；120m 的厚度按面积归一以维持 p0036 的同一释放体积。

|运行|正释放格数|实际 TIFF 体积 m³|保存场汇流点阈值首达区间，释放后秒|保存栅格预算残差|
|---|---:|---:|---|---:|
|p0000-S，60m|257|51,755,728.592650|(161.1, 180.2]|+0.947210%|
|p0036-S_T，120m|67|31,184,139.128430|(240.6, 260.1]|−0.397350%|
|p0036-S_T，60m|257|31,184,139.128430|(221.0, 240.7]|+1.663189%|

native 内部预算残差分别为 +0.947784%、−0.388377%、+1.665052%，与保存栅格表示分开记录；没有把某个残差大小自行改称守恒通过。保存初态的 ASCII 深度舍入误差另有 I/O 一致性检查，不是物理准确度证书。

21 条谱系全部接通，三条原始命中均为 paper junction，另外 **18 条口岸／OSM 代表点在保存输出未命中**。定义为 h≥0.1m、100m 代表点缓冲内的网格中心，区间来自上一未达帧至首个达阈帧；不等于求解步时刻或精确结构相交。未命中不能说明连续时间未到达或安全。请求 1800 秒与真实末帧 1800.5／1800.5／1801.2 秒分别保留。

所有运行仍未通过区域、预测和质量守恒资格，decision05 的 accepted-envelope 列表为空。机械启动至整体释放延迟未知，未置零。因此 **合格时延、绝对到达、到达概率与概率权重全部为空，包络纳入均 false**。这三个选定案例也不是 2048 参数设计的全权重集合，不能据此组成概率预报或声称 95% 覆盖率。

## 足迹与距离的解释

实际保存场按预先指定 h≥0.1／1／5m 输出两种时域：请求期内保存帧、全部实际保存帧。h≥0.1m 且不超过请求 1800 秒的结果如下：

|运行|受影响栅格面积 km²|最远受影响格中心距实际释放栅格足迹 m|
|---|---:|---:|
|p0000-S，60m|15.3036|11,325.626|
|p0036-S_T，120m|23.0112|11,554.012|
|p0036-S_T，60m|12.1608|10,841.005|

距离为 EPSG:32645 中，受影响格中心至该运行正释放栅格单元足迹并集的欧氏距离；不是质心距离、流路长度、精确实测源边界滑程或验证预警有效距离。图 `results/arrival/propagation_v3/conditional_footprints.png` 已实际打开审查。粗细网格的这些不同不能单凭两例宣称收敛；与 compact-v2 的比较也同时改变了源几何和源量，不能归因于单一算法改进。

## 复核和集成

研究记录：`results/arrival/propagation_v3/RESULTS.md`、`release_mapping_audit.csv`、`saved_field_target_checks.csv`；499 项对接检查通过，83 条唯一输入索引及 16 条唯一输出索引均逐字节复验；独立审计见其 `review/final_review.json`。技术检查通过仅说明数据绑定和对接规则通过，物理资格仍为 false。

新接口为 `exports/fullmask_propagation_join_bundle_v3.json`。独立 `results/fullmask_v3/input_manifest.json` 仅登记仓库相对路径或 66 角色中精确批准的 cache 引用，以规范路径去重；相同字节但不同路径的快照与 cache 不合并，重复注册的全部角色和原行号保留。输出完整清单及无循环封包校验亦在该目录。旧 v1/v2 和先前 portable-v3 包均不重封。

只读校验可在源树或已集成仓库根运行，不依赖 producer worktree 位置或 Git 对象：

```sh
track_b/.venv/bin/python track_b/research/q3/round3/scripts/seal_fullmask_v3.py --verify-only
```

实际对接复跑命令（会重写本增量结果，随后须重新审图、独立审计及封包）：

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 track_b/.venv/bin/python track_b/research/q3/round3/scripts/join_propagation_v3.py
```

本包只处理本 PIN 的 fullmask S／S_T 三例；后交的 compact S_H／S_T_H 和无 Q2 父谱系的一般比较保持独立版本。本地首次机械启动独立真值仍为 0，未增加独立训练／覆盖率验证事件，经验覆盖率为空。队员科学采用仍待审视。
