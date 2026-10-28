# A 题实现规格说明（供论文"方法"章节与附录代码说明使用）

> 本文档由逐行核对 `A题_数学手记/code/` 下 12 个脚本得到，所有参数、折数、阈值、种子均取自代码常量；凡标注"运行结果"的数字，来自同一代码版本生成的 `results/` 产物（文件名随文给出），可直接在论文中引用。
> 阅读约定：`SEED` 恒为 `20261026`；`n` 指对象数 250；`V…`、`Y…`、`R…` 为编码变量名；公式中的下标 `j` 表示目标（50 个），`k` 表示特征（231 个）。

---

## 0 全局约定

### 0.1 路径解析（决定相对路径怎么写）

| 脚本 | `ROOT`（数据根） | `WORK`/输出目录 |
|---|---|---|
| `run_all.py` | 不定义 | 依赖各子脚本 |
| `data_audit.py` | `parents[2]`＝项目根（含 `data/`） | `ROOT/A题_数学手记/results` |
| `derived_search.py` | `parents[2]` | `ROOT/A题_数学手记/results` |
| `derived_relations.py` | 无（纯函数库） | 无 |
| `prediction.py` | `parents[2]` | `ROOT/A题_数学手记/results`（`RESULTS`），图在 `.../figures` |
| `scoring_protocols.py` | `parents[2]` | `parents[1]/results` |
| `grade_identification.py` | `parents[2]` | `ROOT/A题_数学手记/results` |
| `threshold_reports.py` | `parents[2]` | `parents[1]/results` |
| `network_analysis.py` | `parents[2]` | `ROOT/A题_数学手记/results` |
| `generation.py` | `parents[1]`＝`A题_数学手记` | `ROOT/results`；`project=ROOT.parent`（可 `--project` 覆盖） |
| `empirical_copula.py` | 无（类库） | 无 |
| `structure_generation.py` | `parents[1]` | `ROOT/results`；`project=ROOT.parent` |

即：`results/` 与 `figures/` 均在 `A题_数学手记/` 下；原始 `data/` 只读，代码中无任何写回 `data/` 的语句。

### 0.2 数据规模（`data_audit.py` 运行结果，`data_audit_summary.json`）

| 文件/表 | 形状 | 说明 |
|---|---|---|
| `D01.csv` | 250×234 | `object`,`object_id`,`regime` + V001–V231 |
| `D04.csv` | 250×53 | `object`,`object_id`,`regime` + Y01–Y50（无缺失） |
| `D02.csv` | 231×232 | 231×231 相关阵（含 `var_id` 列） |
| `D05.csv` | 50×51 | 目标侧相关阵 |
| `D06.csv` | 44×51 | 44×50 交叉块（V×Y） |
| `D07.csv` | 250×189 | 仅用于缺失计数 |
| `D08.xlsx` | 7 张表 | `var_reference` 261×8、`target_reference` 101×5、`ref_importance` 231×2、`ref_attribution` 500×236、`ref_scale` 250×73、`aux_metadata` 250×11、`Sheet2` 空 |
| `D03.xlsx` | 13 张表 | `object_1`…`object_12` + `summary`；每卡 220 个勾选格，合计 2640；**非空勾选 0** |

- 缺失：`D01` 73 个单元格 / 63 行 / 9 列；`D04` 0；`D07` 750。
- 连接键：`object_id` 在 `D01` 与 `D04` 中 **250 行全部冲突**（相等 0 行）；`regime` 250/250 一致 → 一律按 `object` 对齐，`prediction.load_xy()` 内含断点检查。
- 22 个 regime 计数：R01=12, R02=31, R03=6, R04=12, R05=4, R06=9, R07=10, R08=3, R09=5, R10=8, R11=17, R12=10, R13=11, R14=8, **R15=11**, R16=10, R17=5, R18=13, R19=18, **R20=28**, R21=7, R22=12（合计 250）。
- 生成目标类：R20（训练 28）、R12（10）、R13（11）；迁移源类：R15（11 个对象）。

### 0.3 全局常量

| 名称 | 取值 | 出现位置 |
|---|---|---|
| `SEED` | **20261026** | `prediction.py`, `generation.py`, `structure_generation.py`, `network_analysis.main(seed=20261026)` |
| `FEATURES` | `V001`…`V231`（231 个） | 全部脚本 |
| `TARGETS` | `Y01`…`Y50`（50 个） | 全部脚本 |
| `DERIVED` | `V037, V228, V229, V230, V231` | `derived_search.py`, `generation.py`, `structure_generation.py` |
| `BASE` | 226 个 = `FEATURES` 去掉 5 个派生量 | `structure_generation.py` |
| `CRITICAL` | `V004=17.25, V039=0.29925, V021=0.206333333, V109=0.35` | `generation.py`, `structure_generation.py`，`threshold_reports.py` 用 D08 全精度覆写前三个，V109 来自题面补充 |
| `ATOM_FIELDS` | `V002, V004, V021, V026, V036` | `structure_generation.py`（原子/零质量诊断） |
| `QUANTILES` | `(1,2,3,4,5,6)/7` | `scoring_protocols.py`（协议 B 切点） |
| `METHODS` | `['spearman','rank_ridge','quantile_eta2']` | `network_analysis.py` |
| `LOG_FEATURES` | `V001`…`V037`（37 个） | `derived_relations.py`（取 log10 的列） |

### 0.4 线程与运行方式

- `run_all.main()` 用 `threadpool_limits(limits=2)` 包住全部 12 步（"防止小矩阵计算因过度并行反而变慢"）。
- `network_analysis.main()` 在关联打分 + bootstrap 段用 `threadpool_limits(limits=1)`。
- `structure_generation.py --observed-guard-only` 用 `threadpool_limits(limits=2)`。
- 未设置 `OMP_NUM_THREADS`/`MKL_NUM_THREADS`；无 `n_jobs` 参数（sklearn 全部单线程默认）。
- 绘图统一 Agg 后端（`data_audit`, `prediction`, `network_analysis`, `scoring_protocols`, `grade_identification` 显式 `matplotlib.use('Agg')`；`generation`/`structure_generation` 在作图层内设置）。

---

## 1 脚本清单：入口、函数、输入、输出

> 输出文件名均为 `results/` 下的文件名；`figures/` 只列主要图。

### 1.1 `run_all.py`（编排，40 行）

- **入口**：`main()`；`sys.stdout.reconfigure(encoding='utf-8')`。
- **依赖顺序**：`data_audit → derived_search → prediction → (write_cards) → network_analysis → generation → structure_generation.run_structure → scoring_protocols → grade_identification → threshold_reports`。
- 中间耦合：读取 `prediction.py` 产出的 `question1_working_grades_ASSUMPTION.csv`，用 `prediction.write_cards(grade_table[TARGETS], grade_table['object'])` 重建 D03 卡片。
- 无 `results/` 输出（除被调脚本产出）。

### 1.2 `data_audit.py`（228 行，问题 0：数据侦察）

- **入口**：`main()`。无其它顶层函数（统计逻辑全在 `main` 内）。
- **输入**：`data/D01.csv`、`D02.csv`、`D04.csv`、`D05.csv`、`D06.csv`、`D07.csv`、`D03.xlsx`（`data_only=False` 与 `True` 各载一次）、`D08.xlsx`。
- **输出**：`data_audit_feature_summary.csv`、`data_audit_target_summary.csv`、`data_audit_scale_candidates.csv`、`data_audit_scale_discrepancies.csv`、`data_audit_correlation_check.csv`、`data_audit_template_cells.csv`、`data_audit_critical_native_observed.csv`、`data_audit_attribution_hypothetical_scalar.csv`、`data_audit_attribution_target_alignment.csv`、`data_audit_summary.json`；图 `figures/data_audit_scale_evidence.png`。
- **关键参数**：鲁棒 z = `|x−median|/(1.4826·MAD)`，阈值 10；尺度候选误差 = `median(|a−b|/max(|b|,1e-12))`（identity）与 `median|a−log10 b|`、`median|a−ln b|`（仅 `b>0`）；`best_error<1e-8` 记为"严格识别"；恒等差异阈值 `1e-7`；仿射对齐用两参数最小二乘（`np.linalg.lstsq`）。
- **运行结果**：70 个有原生配对的变量中 log10 = 37、identity = 33（严格识别 37 / 31）；恒等差异 >1e-7 共 86 处；V021 有 168 个原生 0（替换下限 = 最小正原生/2 = 0.0097015833），V004 有 1 个非正值（下限 1.1122725）；最强归因目标 |r| = Y47（0.6513）。

### 1.3 `derived_search.py`（203 行，派生关系搜索）

- **入口**：`main()`。
- **输入**：`data/D01.csv`、`data/D08.xlsx[ref_scale]`；依赖 `derived_relations.CANDIDATE_COEFFICIENTS / candidate_derived_from_native`。
- **输出**：`data_audit_derived_candidates.csv`、`data_audit_derived_train_selected.csv`、`data_audit_derived_partition.csv`、`data_audit_derived_refinement.csv`、`data_audit_derived_consistency.csv`、`data_audit_derived_consistency_by_object.csv`、`data_audit_V229_decimal_precision.csv`。
- **关键参数**：训练/留出 = **165 / 85**（`np.random.default_rng(20261026).permutation(250)` 的前 165 为训练）；标准化只用训练行均值/标准差（`sd<1e-12→1`）；`OrthogonalMatchingPursuit` 稀疏项数 `k ∈ {1,2,3,4,6}`；响应 10 个 = 5 个派生量 × 2 种刻度（`recorded` 与 `10**recorded`）；成对公式 5 种算子（`sum, difference, product, ratio, reverse_ratio`）× 1 斜率 + 1 截距，按训练 RMSE 每响应保留前 3；精修阶段 `k ∈ {6,8,10,12,16}`，只针对 V228/V229 的 `10**` 刻度，并把 `native_V###`（全部 V 列）作为候选；一致性检验用"ref 前 37 列 + 5 候选公式"作代数核验（明确标注不是独立泛化）；V229 用十进制舍入区间（`Decimal.as_tuple().exponent`，0.5 ulp）判断区间是否相交。

### 1.4 `derived_relations.py`（75 行，纯函数库）

- **无 `main`**，除常量外三个函数：
  - `candidate_derived_from_native(native_frame)`：按 `CANDIDATE_COEFFICIENTS` 加权求和，`min_count=len(source)`（任一来源缺失则该聚合缺失，不当 0）。
  - `fit_positive_floors(native_training_frame)`：对 V001–V037，取**训练行**中每列"最小正值的一半"作为替代下限（V037 先由五项加权和算出再取正值）。
  - `native_to_recorded(native_frame, floors, recalculate_derived=True)`：先把 5 个派生量按公式算成原生聚合（非正聚合直接 `raise ValueError`），再把 `LOG_FEATURES`（V001–V037）与 `V228…V231` 取 log10（`x>0` 保留原值，`x≤0` 用 `floors` 替代；真实缺失保持缺失）。
- **五个候选公式的全部系数**（论文表格可直接抄）：

| 派生量 | 公式（原生量加权和，随后取 log10 得 D01 记录值） |
|---|---|
| `V037` | 0.0003·V027 + 0.4·V031 + 0.4·V033 + 5.523·V034 + 0.4·V036 |
| `V228` | V006/23 + V007/1.035 + V008/0.225 + V009/0.1 + V010/0.75 + V011/10 + V016/0.6 + V019/1.29 |
| `V229` | V164/0.625 + V118/1.5 + V155/0.23 + V121/0.0245 + V128/0.023 + V095/0.0045 |
| `V230` | V023/0.145 + V027/400 |
| `V231` | V002/50 + V003/1.2 + V004/19 + V012/3.5 + V022/11 |

> 代码与论文均须注明：这五条是"数据支持的候选关系"，**不是**提供者给出的官方定义。

### 1.5 `prediction.py`（423 行，问题 1 主计算）

- **入口**：`main()`；另有 CLI `--cards-only` → `cards_main()`（只重建 D03 卡片，`__main__` 内以 `import prediction as canonical` 保证 joblib 反序列化类来自模块而非 `__main__`）。
- **主要函数**：`feature_array`, `RobustPreprocessor.fit/transform`, `make_estimator`, `load_xy`, `tune`, `PredictionBundle.__init__/predict`, `fit_final_model`, `load_final_model`（`lru_cache(maxsize=1)`）, `predict_continuous`, `working_grades`, `metric_rows`, `nested_cv`, `conformal`, `card_mappings`, `build_card_payload`, `write_cards`, `cards_main`。
- **输入**：`data/D01.csv`、`data/D04.csv`、`data/D03.xlsx`。
- **输出**：`question1_model.joblib`、`question1_metrics.csv`、`question1_inner_selection.csv`、`question1_cv_folds.csv`、`question1_continuous_oof.csv`、`question1_working_grades_oof_ASSUMPTION.csv`、`question1_continuous_D04_ID_oof_sensitivity.csv`、`question1_final_selection.csv`、`question1_continuous_fitted.csv`、`question1_working_grades_ASSUMPTION.csv`、`question1_observed_working_grades_ASSUMPTION.csv`、`question1_grade_rule_ASSUMPTION.csv`、`question1_grade_sensitivity_ASSUMPTION.csv`、`question1_conformal_metrics.csv`、`question1_conformal_test_intervals.csv`、`question1_conformal_joint_widths.csv`、`question1_conformal_joint_coverage.csv`、`question1_conformal_split.csv`、`question1_summary.json`、`question1_working_grades_D03_ASSUMPTION.xlsx`（`write_cards`）；图 `figures/question1_cv_r2.png`、`question1_oof_scatter.png`、`question1_grade_sensitivity.png`。

### 1.6 `scoring_protocols.py`（311 行，协议 A/B 与跨分支 K 比较）

- **入口**：`main()`。
- **主要函数**：`_score_array`, `fit_protocols`, `apply_protocol`, `_parameter_rows`, `_agreement_rows`, `_k_distribution_rows`, `_read_profiles`, `_comparison_rows`, `build_transfer_comparisons`, `draw_protocol_figure`, `main`。
- **输入**：`data/D04.csv`、`results/question1_continuous_fitted.csv`、`question1_continuous_oof.csv`、`question1_cv_folds.csv`，以及（存在时）各迁移前后画像 CSV。
- **输出**：`question1_protocol_A_fitted_grades.csv`、`question1_protocol_B_fitted_grades.csv`、`question1_protocol_A_oof_grades.csv`、`question1_protocol_B_oof_grades.csv`、`question1_protocol_difference_fitted_B_minus_A.csv`、`question1_protocol_difference_oof_B_minus_A.csv`、`question1_protocol_cutpoints.csv`、`question1_protocol_agreement.csv`、`question1_protocol_K_distribution.csv`、`question3_structure_generated_profiles_PROTOCOL_B.csv`、`question3_structure_representatives_profiles_PROTOCOL_B.csv`、`question3_protocol_K_comparison.csv`、`question3_protocol_K_summary.csv`；图 `figures/question1_protocol_AB_Y38.png`。

### 1.7 `grade_identification.py`（238 行，等级识别界）

- **入口**：`main()`。
- **主要函数**：`validated_anchors`, `grade_bounds`, `strict_threshold_witness`, `critical_state`, `grade_identification_table`, `transfer_comparison`, `plot_envelope`, `main`。
- **输入**：`data/D04.csv`（以 `dtype=str` 读入以保留十进制文本）、`results/` 下 8 个迁移画像/基线文件（见 §1.6、§1.11）。
- **输出**：`question1_grade_identification_bounds.csv`、`question1_grade_identification_summary.csv`、`question1_grade_identification_witnesses.csv`、`question1_grade_identification_row_summary.csv`、`question1_grade_identification_summary.json`、`question3_all_monotone_grade_comparison.csv`；图 `figures/question1_grade_identification_envelope_Y38.png`。
- **关键实现**：全部用 `fractions.Fraction` 精确有理数；`common_monotone` 假设下每格界为 `[max(0, 满足 p≤z 的锚点等级), min(6, 满足 p≥z 的锚点等级)]`；`ALL7` 假设下按"250 个互异值的升序名次 r"给界 `[max(0,6−(m−r)), min(6,r−1)]`，`m`=该目标互异值个数（本数据 m=250）。

### 1.8 `threshold_reports.py`（42 行，临界阈值全精度统一）

- **入口**：`main()`。
- **输入**：`data/D08.xlsx[var_reference]`、`results/question3_tail_compatibility.csv`、三张 critical 比较表。
- **输出**（原地重写 + 新增）：`question3_transfer_critical_comparison.csv`、`question3_structure_transfer_critical_comparison.csv`、`question3_observed_source_guard_critical_comparison.csv`（仅更新 `threshold`、`before_ratio/source_ratio`、`after_ratio` 三列）、`question3_feasibility_bounds.csv`、`question3_critical_thresholds_used.csv`。
- 阈值来源：V004/V039/V021 取 `var_reference.threshold_mean`；**V109=0.35 来自题面补充**（原表该格为空，代码显式声明不假装来自原表）。

### 1.9 `network_analysis.py`（325 行，问题 2）

- **入口**：`main(bootstrap=200, seed=20261026)`；CLI `--bootstrap`、`--seed`（`--bootstrap<1` 报错）。
- **主要函数**：`rank_standardize`, `association_scores`, `graph_partition`, `bh_adjust`, `threshold_analysis`, `main`。
- **输入**：`data/D01.csv`、`D04.csv`、`D02.csv`、`D06.csv`、`D08.xlsx[ref_scale, var_reference, ref_importance]`。
- **输出**：`question2_all_feature_scores.csv`、`question2_top3.csv`、`question2_bootstrap_top3.csv`、`question2_method_Jaccard.csv`、`question2_ridge_alpha_sensitivity.csv`、`question2_network_sensitivity.csv`、`question2_network_bootstrap.csv`、`question2_network_edges.csv`、`question2_network_nodes.csv`、`question2_module_stability.csv`、`question2_threshold_hinge_exploratory.csv`、`question2_summary.json`；图 `figures/question2_correlation_modules.png`、`question2_top3_stability.png`、`question2_network.png`。

### 1.10 `generation.py`（439 行，问题 3 联合基线 + 迁移）

- **入口**：`main(project=None, repeats=5, reuse_heldout=False)`；CLI `--project`、`--repeats`（默认 5）、`--reuse-heldout`。
- **主要函数**：`ConditionalGaussian.fit/transform/mean/sample/nll`, `distribution_distances`, `evaluate_generators`, `native_critical`, `tail_compatibility`, `feasibility_bounds`, `predict_profiles`, `transfer_candidates`, `main`, `make_figures`。
- **输入**：`data/D01.csv`、`data/D08.xlsx[ref_scale]`、`data/D04.csv`（经 `prediction.load_final_model()` 与 `prediction.predict_continuous/working_grades`）。
- **输出**：`question3_heldout_generator_metrics.csv`、`question3_heldout_generator_summary.csv`、`question3_generated_features_D01_scale.csv`、`question3_novelty_diagnostic.csv`、`question3_tail_compatibility.csv`、`question3_feasibility_bounds.csv`、`question3_generated_profiles_D04_scale.csv`、`question3_generated_profiles_WORKING_GRADES_NOT_IDENTIFIED.csv`、`question3_R15_to_R20_candidates.csv`、`question3_transfer_critical_comparison.csv`、`question3_transfer_optimization.csv`、`question3_transfer_source_inputs.csv`、`question3_source_critical_supplements.csv`、`question3_transfer_before_profiles_D04_scale.csv`、`question3_transfer_after_profiles_D04_scale.csv`、`question3_transfer_K_WORKING_ONLY.csv`、`question3_summary.json`；图 `figures/question3_heldout_models.png`、`question3_critical_tail_curves.png`、`question3_transfer_distances.png`。

### 1.11 `empirical_copula.py`（92 行，类库）

- 类 `ShrunkEmpiricalCopula(tau=5.0)`，方法 `fit/transform/mean/sample/nll/atom_probability`。
- 无输出文件；被 `structure_generation.py`（`evaluate_structure_generators`、`run_structure`、`run_observed_source_guard`、`select_saved_representatives`）调用。
- `nll` 恒返回 `NaN`（有原子的联合分布不能沿用 rank-Gaussian 密度）；`atom_probability(group, column_index, value=0.)` 返回该列在收缩边际中取 `value` 的总权重。

### 1.12 `structure_generation.py`（1122 行，问题 3 结构修复与迁移）

- **入口**：`run_structure(project=None, repeats=5, reuse_heldout=False)`；CLI `--project`、`--repeats`、`--reuse-heldout`、`--observed-guard-only`、`--guard-reuse-solver`。
- **主要函数**：`load_native_inputs`, `expand_native`, `valid_native`, `sample_valid`, `evaluate_structure_generators`, `tagged`, `relation_diagnostics`, `state_diagnostics`, `aggregate_range_diagnostics`, `working_k_table`, `write_representatives`, `select_saved_representatives`, `transfer_structure`, `refine_guard_with_exact_subspace`, `write_qp_platform_profiles`, `run_observed_source_guard`, `make_exact_qp_curve_figure`, `make_observed_guard_figure`, `make_figures`, `run_structure`。
- **输入**：`data/D01.csv`、`data/D08.xlsx[ref_scale]`、`data/D04.csv`（观测源守卫用 `D04.Y38`）、`question1_model.joblib`（经 `prediction.load_final_model()`）。
- **输出**（按 `run_structure` 顺序）：
  `question3_structure_heldout_metrics.csv`、`question3_structure_heldout_summary.csv`、`question3_structure_marginal_effective_counts.csv`、`question3_structure_recording_floors.csv`、`question3_structure_generated_base226_native.csv`、`question3_structure_generated_full231_native.csv`、`question3_structure_generated_full231_D01_scale.csv`、`question3_structure_zero_negative_rates.csv`、`question3_structure_derived_ranges.csv`、`question3_structure_generated_profiles_D04_scale.csv`、`question3_structure_generated_profiles_WORKING_GRADES_NOT_IDENTIFIED.csv`、`question3_structure_representative_selection.csv`、`question3_structure_representative_summary.csv`、`question3_structure_representatives_D01_scale.csv`、`question3_structure_representatives_native_mixed.csv`、`question3_structure_representatives_profiles_D04_scale.csv`、`question3_structure_representatives_WORKING_GRADES_NOT_IDENTIFIED.csv`、`question3_structure_novelty.csv`、`question3_structure_transfer_slsqp_base226_native.csv`、`question3_structure_transfer_original_D01_source_profiles.csv`、`question3_structure_transfer_{source,proposal,after}_native.csv`、`..._{source,proposal,after}_D01_scale.csv`、`question3_structure_transfer_{source,after}_profiles_D04_scale.csv`、`question3_structure_transfer_K_WORKING_ONLY.csv`、`question3_structure_candidate_relation_residuals.csv`、`question3_structure_transfer_critical_comparison.csv`、`question3_structure_transfer_optimization.csv`、`question3_structure_transfer_original_D01_source.csv`、`question3_structure_summary.json`。
  观测源守卫前缀 `question3_observed_source_guard_`：`{feasible_initial_base,slsqp_base,exact_qp_base,plateau_polished_qp_base}226_native_mixed.csv`、`exact_qp_certificate.csv`、`feasible_candidate_selection.csv`、`exact_qp_curve_object124.csv`、`QP_platform_profile_comparison.csv`、`{source,proposal,after}_native_mixed.csv`、`{source,proposal,after}_D01_scale.csv`、`after_profiles_D04_scale.csv`、`original_source_profiles_D04_scale.csv`、`reexpressed_source_profiles_D04_scale.csv`、`critical_comparison.csv`、`optimization.csv`、`candidate_relation_residuals.csv`、`K_WORKING_ONLY.csv`、`versus_model_only_branch.csv`、`summary.json`。
- 图：`figures/question3_structure_heldout_models.png`、`question3_structure_generated_profiles.png`、`question3_structure_transfer_distances.png`、`question3_observed_source_guard_exact_qp_curve_object124.png`、`question3_observed_source_guard_comparison.png`。

> **一致性提醒**：`results/` 中 `question3_structure_zero_negative_rates_BEFORE_MARGINAL_REPAIR.csv` 与 `scorecard_payload.json` **不由当前 12 个脚本生成**（历史归档 / 外部 artifact 工具产物），复现说明中不应把它们当作脚本输出。

---

## 2 随机种子与随机化位置

| 位置 | 调用 | 种子 |
|---|---|---|
| 内层 CV（最终模型 `tune`） | `KFold(3, shuffle=True, random_state=seed)` / `GroupKFold(3)` | `SEED`=20261026 |
| 内层 CV（嵌套外层第 `k` 折） | 同上 | `SEED + k`（20261027…20261031） |
| 外层 CV（随机协议） | `KFold(5, shuffle=True, random_state=SEED)` | 20261026 |
| 外层 CV（regime / D04_ID 协议） | `GroupKFold(5)` | 无随机 |
| conformal 三分 | `train_test_split(..., test_size=100, random_state=SEED+99)`；再 `test_size=50, random_state=SEED+100` | 20261125 / 20261126 |
| conformal 选模 | `tune(..., seed=SEED+101)` | 20261127 |
| 派生搜索划分 | `np.random.default_rng(20261026).permutation(250)` | 20261026 |
| 网络关联 bootstrap | `rng = np.random.default_rng(seed)`；`rng.integers(0,250,250)` | 20261026（`--seed` 可改） |
| Louvain | `nx.community.louvain_communities(g, weight='weight', seed=seed)` | 20261026；敏感性另扫 0…19 |
| 网络 spring 布局 | `nx.spring_layout(..., seed=seed, k=.3, iterations=300)` | 20261026 |
| 分位变换 | `QuantileTransformer(..., random_state=SEED)` | 20261026 |
| 留出重复切分 | `StratifiedShuffleSplit(n_splits=5, test_size=.30, random_state=SEED)` | 20261026 |
| 生成评估重采样（联合基线） | `np.random.default_rng(SEED+split)` | 20261026+0…4 |
| 生成评估重采样（结构分支） | `np.random.default_rng(SEED+100*split)` | 20261026+0,100,200,300,400 |
| 最终生成抽样 | `np.random.default_rng(SEED)`（三类共用同一 RNG，顺序 R20→R12→R13） | 20261026 |
| 岭回归 α 敏感性 / 网络种子扫描 | α∈{10,1000}，无随机；seed 扫 `range(20)` | 20261026 / 0…19 |

- 代码中**没有** `np.random.seed`、`random.seed` 或环境变量式种子；所有随机性都通过显式构造器参数或 `default_rng` 传入。
- 折大小（运行结果 `question1_cv_folds.csv`）：随机协议 50/50/50/50/50；D04_ID 留组 50×5；**regime 留组 52/51/50/47/50**（整类不切分，故不恰好均分）。

---

## 3 问题 1 规格（连续评分预测 → 工作等级）

### 3.1 输入与对齐

- `load_xy()`：读 `D01.csv`、`D04.csv`；`object` 唯一性检查；`y.set_index('object').reindex(x.object)`；目标缺失或 `regime` 冲突直接 `raise`。
- `feature_array(X)`：按 `FEATURES` 固定列序取 231 列（缺列报错），非有限值 → `NaN`，只接受二维 n×231。

### 3.2 预处理：严格顺序（每步参数只来自当前训练折）

`RobustPreprocessor`（自定义 `TransformerMixin`，放在 `Pipeline` 第一步，随折重拟合）：

1. **中位数填补**：`median_ = nanmedian(X_train, axis=0)`；非有限中位数替换为 0；`fill = where(isnan, median_, x)`。
2. **分位裁剪**：`low_, high_ = quantile(fill_train, [0.01, 0.99], axis=0)`（numpy 默认 `linear`，"1%/99%"），`clip(fill, low_, high_)`。
3. **标准化**：`mean_ = mean(clipped_train, axis=0)`；`scale_ = std(clipped_train, axis=0)`（ddof=0），`sd ≤ 1e-12 → 1`；`z = (clip − mean_)/scale_`。
4. **目标标准化**（`TransformedTargetRegressor(transformer=StandardScaler())`）：每个 `Y_j` 用该折训练均值/标准差单独标准化，预测后反变换回 D04 连续刻度。
5. **预测**：`predict` 时对测试数据重复第 1–3 步的**训练折参数**（`transform` 不重估任何量）。

> 裁剪的定位：不是判极端值为错，而是限制少数巨大数值对线性模型的支配；生成样本的物理阈值**不在**该变换空间里检查。

### 3.3 候选模型与超参数网格

- 候选集合 `CANDIDATES`（9 个）：
  - `Ridge(alpha=value)`，`alpha ∈ {0.1, 1, 10, 100, 1000}`（5 个，`fit_intercept` 默认 True）；
  - `PLSRegression(n_components=int(value), scale=False, max_iter=1000)`，`n_components ∈ {2, 5, 10, 20}`（4 个）。
- 统一封装：`Pipeline([("preprocess", RobustPreprocessor()), ("reg", reg)])` 外包 `TransformedTargetRegressor`。

### 3.4 交叉验证结构

| 层 | 折数 | 构造 | 说明 |
|---|---|---|---|
| 外层 | **5** | 随机协议 `KFold(5, shuffle=True, random_state=20261026)`；分组协议 `GroupKFold(5)`（分组 = `regime` 或 `D04.object_id`） | 折大小：随机 50×5；D04_ID 50×5；regime 52/51/50/47/50（整类不切分） |
| 内层 | **3** | 随机 `KFold(3, shuffle=True, random_state=SEED+fold)`；分组 `GroupKFold(3)` | 只在训练折内选模 |
| 内层选择指标 | — | 每折：`mean_j[ ((Y_va − pred)/(std(Y_tr,j)+1e-12))² ]`，再对 3 折取平均 `inner_normalized_mse` | 逐目标按训练标准差归一化 |
| 排序/决胜 | — | `sort_values(["inner_normalized_mse","family","parameter"])` | 同分时 `pls` 先于 `ridge`（字母序），再取小参数 |

**内层同时给出两条基线**：`mean`（训练折逐目标均值）、`ridge`（内层最优 ridge）、`pls`（内层最优 pls）；`selected` = 内层总最优。

### 3.5 三种验证协议（`question1_metrics.csv` 的 `protocol` 取值）

| 协议名 | 分组变量 | 含义 |
|---|---|---|
| `nested_random_5x3` | 无（`KFold`） | 随机 5 折外层 + 3 折内层 |
| `nested_regime_holdout_5x3` | `D01.regime`（22 类） | 留组：整类不进入训练 |
| `nested_D04_ID_holdout_5x3_sensitivity` | `D04.object_id` | 敏感性分析（重复 ID 语义未知，故标 sensitivity） |

指标：逐目标 `mae`、`rmse`、`r2`，以及 `mae_improvement_over_mean = 1 − mae/mae_mean(同协议同目标)`。

### 3.6 最终模型与模型选择规则

- `fit_final_model(X, Y)`：在全部 250 行上用 `tune(seed=SEED)` 选模 → 运行结果 **(pls, 10)**，`inner_normalized_mse = 0.8828711086887444`；次优 `ridge,1000` = 0.9028605621938697；其余：pls20 0.92264、ridge100 0.92952、pls5 0.93441、pls2 0.99787、ridge10 1.43160、ridge1 2.61210、ridge0.1 3.31255（`question1_final_selection.csv`）。
- 逐外层折的内层选择（`question1_inner_selection.csv`）：
  - 随机协议：pls10（折1,2,4,5）/ ridge1000（折3）；
  - regime 协议：pls10（1,3）/ ridge1000（2,5）/ pls5（4）；
  - D04_ID 协议：pls10（全部 5 折）。
  即"选择规则本身"在 regime 留组下不稳定，这是论文应报告的敏感性。
- 最终 bundle 保存 `grade_location_ = Y.mean(axis=0)`、`grade_scale_ = max(Y.std(axis=0),1e-12)`（全 250，ddof=0）。
- **线性化系数**（供问题 3 的解析约束使用）：`linear_coef_ = β_jk · s_y,j`（标准化坐标导数，50×231）；`linear_intercept_ = μ_y,j + s_y,j · b_j`；**原始 D01 尺度导数 = `linear_coef_ / pre.scale_`**（`generation.py` 的 `score_slope`、`structure_generation.py` 的 `β` 都这样换算）。PLS 的截距先做 `intercept − coef @ reg._x_mean` 修正。注意该导数是**分段线性**的：只在每列的 clip 箱 `[low_, high_]` 内成立，箱外评分恒定（平台），这正是 §5.4(d) 平台修复的依据。

### 3.7 Conformal 区间（分离式 90% 边际 + 90% 联合箱）

- 样本切分：从 250 个对象中 `train = 150`，再从剩余 100 中取 `calibration = 50`、`test = 50`（`random_state = SEED+99`、`SEED+100`）。
- 校准前重新选模：`tune(X[tr], Y[tr], seed=SEED+101)` → 运行结果 **(pls, 10)**（`question1_summary.json.conformal_selection`）。
- **名次公式**：`rank = ceil((n_cal + 1) × 0.9) = ceil(51×0.9) = 46`；逐目标 `q_j` = 50 个校准绝对残差的**第 46 小值**（0 基索引 `rank-1`）。
- 边际区间：`[pred_j − q_j, pred_j + q_j]`，名义边际覆盖率 0.9。
- 覆盖率区间：`Beta.ppf(0.025, c, n−c+1)` 与 `Beta.ppf(0.975, c+1, n−c)`（`c` 为被覆盖数，`n=50`）。
- 联合箱：先算 `joint_score_i = max_j |resid_ij| / std(Y_tr,j)`，取第 46 小值 `joint_q = 4.083056454898014`，半宽 `= joint_q × std(Y_tr,j)`；判据 `all 50 targets` 同时落入。
- 运行结果（`question1_summary.json`、`question1_conformal_metrics.csv`）：50 个目标的边际覆盖率均值 **0.9012**（50 个测试对象 × 50 目标 = 2500 个格子，覆盖 2253 个）；联合箱覆盖 **42/50 = 0.84**，95% CI **[0.7089, 0.9283]**；"50 个边际区间同时覆盖"的经验频率 **0.10**。

### 3.8 工作等级协议 A / B 的精确定义

**协议 A（均值/标准差定尺）**：

```
raw_j   = 3 + slope · (x_j − μ_j) / σ_j
grade_j = clip( floor(raw_j + 0.5), 0, 6 )
```

- `μ_j, σ_j`：训练目标的均值与总体标准差（`ddof=0`，`scoring_protocols.fit_protocols` 显式声明 `sd_ddof=0`；`prediction.working_grades` 用 `np.std` 默认 ddof=0）。
- 任务书约定 `slope=1`；敏感性分析扫 `slope ∈ {0.5, 1, 1.5, 2}`；`floor(+0.5)` 明确半级向上，避免 numpy 银行家舍入。
- `σ_j = 0` 直接报错（"不暗中补一把尺子"）。

**协议 B（训练分位点定尺）**：

```
cuts_j = quantile(Y_train_j, [1/7, 2/7, …, 6/7], method="linear")   # 6 个切点
grade_j = searchsorted(cuts_j, x_j, side="right")                  # 0…6
```

- 恰等于切点者归右侧；重复切点允许（可能跳过某些等级，不保证 7 箱都有对象）；`B_distinct_cutpoint_count`、`B_duplicate_cutpoints` 逐折记录。
- 两协议都只改刻度，**不重训**连续预测器。

**参数来源（fitted 与 OOF 的关键区别）**：

- `fitted`：`μ/σ`、6 个切点均来自**全部 250 个 D04 观测**（`scope="fullfit"`, `random_outer_fold=0`, `training_n=250`）。
- `oof`：按 `question1_cv_folds.csv` 的 `random_outer_fold`，**每折只用该折之外的 200 个 D04 目标**拟合 `μ/σ` 与切点（`scope="oof"`, `training_n=200`），再应用到该折的 50 个 OOF 预测上；`question1_protocol_cutpoints.csv` 因此有 6 组参数（1 个 fullfit + 5 个 oof）。
- 与 `prediction.nested_cv` 内部生成的 `question1_working_grades_oof_ASSUMPTION.csv` 完全等价（同一折外 200 行、同一公式），已核对 **12500 格全部相同**。

**协议一致性（运行结果）**：

| dataset | n_scores | exact_agreement | meanAbsDiff | mean(B−A) | B>A | B<A | maxAbsDiff |
|---|---|---|---|---|---|---|---|
| fitted | 12500 | 0.23384 | 1.0364 | 0.42136 | 0.54792 | 0.21824 | — |
| oof | 12500 | 0.25864 | 0.98624 | 0.47536 | 0.55528 | 0.18608 | — |

Y38 的 K（=`Y38≥2`）分布（`question1_protocol_K_distribution.csv`）：fitted 协议 A K≥2 = 249/250（0.996），协议 B = 231/250（0.924）；oof 协议 A = 249/250，协议 B = 238/250（0.952）。**同一批数据、两套协议给出的 K 判定不同**，这是"原始等级不可识别"的直接证据。

### 3.9 等级识别界（`grade_identification.py`，运行结果）

- 无锚点时，`common_monotone` 假设下每个单元格的可行等级集恒为 **[0,6]**（7 个可能）。
- 额外 `ALL7` 假设（本批 7 个等级都出现，m=250）后：平均集合大小 **6.73416**（12500 格），945 格集合变小，162 格收缩为单点；`Y38≥2` 状态可判定的格子仅 **476/12500**，其中 Y38 目标 **17/250** 行。
- 250 行的 `distinct_values_across_50_targets` 全为 50 → 与"逐行无噪声仿射整数等级"不相容（`incompatible_with_single_rowwise_noiseless_affine_integer_grades=True`）。
- 迁移比较（`question3_all_monotone_grade_comparison.csv`）：对每个分支/基线逐格用 Fraction 比较，`all_nondecreasing_maps_nonincrease_exact` 只有在"迁移后 ≤ 迁移前"时成立；`numeric_tolerance_1e_minus_8_pass` 单独标记"差值在 1e-8 内但严格为正"的情形（明确标注容差不是全映射证书）。

### 3.10 关键数值速查（问题 1）

| 项 | 数值 |
|---|---|
| 样本/特征/目标 | 250 / 231 / 50 |
| 候选模型数 | 9（ridge 5 + pls 4） |
| 外层/内层折数 | 5 / 3（随机与 D04_ID 每折 50；regime 52/51/50/47/50） |
| 最终选择 | pls, 10 components |
| 三种协议：selected 的 50 目标平均 MAE / R² | 随机 0.3544 / 0.2172；regime 0.3688 / 0.1573；D04_ID 0.3563 / 0.2104 |
| 同协议 `mean` 基线平均 R² | 随机 −0.0069、regime −0.0290、D04_ID −0.0136 |
| selected R² 中位数（min–max） | 随机 0.1503（0.0021–0.6953）；regime 0.1282（−0.1325–0.6030）；D04_ID 0.1355（−0.0268–0.6729） |
| 平均 MAE 相对均值基线的改进 | 随机 13.15%、regime 10.88%、D04_ID 12.89% |
| conformal 切分 | 150 / 50 / 50，`rank`=46 |
| conformal 平均边际覆盖 / 联合箱覆盖 | 0.9012 / 0.84（42/50） |
| D03 卡片 | 12 张，每张 220 格，非空 0 |

---
## 4 问题 2 规格（相关结构、三种关联视角、网络稳定性）

### 4.1 相关矩阵核验方式

| 矩阵 | 核验对象 | 方法 | 运行结果 |
|---|---|---|---|
| `D02`（231×231） | 由 `D01` 重算 | 上三角 26565 个单元格 | Spearman MAE = **1.609e-16**（max 6.66e-16）；Pearson MAE = 0.0877（max 1.123） |
| `D05`（50×50） | 由 `D04` 重算 | 1225 个单元格 | Spearman MAE = 1.595e-16；Pearson MAE = 0.0513 |
| `D06`（44×50） | 由 `concat([X,Y])` 重算后取 `[D06.index, D06.columns]` 块 | 2200 个单元格 | Spearman MAE = **1.506e-16**；Pearson MAE = 0.0579 |

结论写法（代码口径）：`D02`/`D05`/`D06` 保存的是 **Spearman** 相关；`network_analysis` 的 `audit` 里另有 `D02_spearman_MAE=1.602e-16`（全矩阵 `nanmean`，不裁上三角）、`D06_rows=44`、`missing_features=73`。

### 4.2 三种关联度量（同一套秩标准化，三个固定规则）

**统一的秩标准化** `rank_standardize(a)`：在当前数据（含 bootstrap 袋）内按列中位数插补 → `rankdata(axis=0, method='average')` → `z = (r − mean(r))/std(r, ddof=1)`（`std≤0→1`）。

| 视角 | 公式 | 含义 | 参数 |
|---|---|---|---|
| `spearman` | `S = Zx'·Zy/(n−1)`（231×50；分数取 `\|S\|`） | 单调关联（秩 Pearson） | — |
| `rank_ridge` | `B = (Zx'Zx + λI_231)^{-1} Zx'Zy`（`scipy.linalg.solve(assume_a='pos')`，分数取 `\|B\|`） | 控制其余 230 个秩变量后的多元线性（偏）关联 | **λ = 100**；无截距（列已中心化） |
| `quantile_eta2` | 见下式（分数取 η²） | 5 箱低自由度非线性关联，抗过拟合 | **5 个等频箱** |

**η² 分箱与调整公式**（`n=250`，`r_j` 为第 j 列平均名次）：

```
bins_i   = min( floor((r_i − 1) · 5 / n), 4 )        # 5 个等频箱，并列名次留在同箱
G        = 非空箱数 (≤5)
between  = Σ_{g∈bins} n_g · ( mean_{i: bins_i=g} zy_i )²
raw      = between / (n − 1)
η²_j     = max( 0, 1 − (1 − raw) · (n − 1) / (n − G) )
```

即：先算未调整的 `raw`（组间平方和/总平方和），再按"扣掉 G 组均值占用的自由度"调整，最后截到非负。

**类内秩相关**（用于判断"整体关联是否为类间差异造成"）：

```
对 22 个 regime 分别去均值：wx ← zx − mean_{regime}(zx)，wy ← zy − mean_{regime}(zy)
within_jk = (wx'wy)_jk / sqrt( Σ_i wx_ij² · Σ_i wy_ik² )
```

运行结果：Top-3 条目中"整体符号与类内符号相反"的仅 **1** 个（`top3_overall_within_regime_sign_reversals`）。

### 4.3 Borda 平均名次的精确定义

1. 对每个方法 m ∈ {spearman, rank_ridge, quantile_eta2}，在**同一目标**的 231 个变量内按分数**降序**排名：`R^(m)_jk = rankdata(−score^(m)_jk, method='average')`（1 = 最强）。
2. `borda_mean_rank_jk = (R^(spearman)_jk + R^(rank_ridge)_jk + R^(quantile_eta2)_jk) / 3`。
3. 每目标取 `borda_mean_rank` 最小的 3 个变量为 **Top-3**（`argsort(kind='stable')`，名次并列时按变量在 `FEATURES` 中的先后）。
4. 性质：只用名次、不用分数绝对值 ⇒ 规避 |ρ|、|岭系数|、η² 三者量纲不可比的问题；Borda 值域 [1,231]，越小越一致。

### 4.4 bootstrap（200 次）与重采样对象

- **重采样对象：250 个 object 的"行"**（不是特征、不是目标）：`ids = rng.integers(0, 250, 250)`，有放回；`X`（231 列）与 `Y`（50 列）用同一 `ids` 同步抽取。
- 每 replicate 重算三种度量、三个方法内名次、Borda、Top-3（并记录每个方法的 Top-3 以供 `question2_bootstrap_top3.csv`）。
- 统计量：
  - `bootstrap_selection_frequency = 命中次数 / 200`
  - `bootstrap_MC_standard_error = sqrt(p(1−p)/200)`（蒙特卡洛误差，不是置信区间）
  - `fixed_module_selection_frequency`：Top-3 命中者所属**全样本模块**的入选频率
  - `{method}_bootstrap_frequency`：各方法各自的 Top-3 命中频率
- 运行结果：150 个 Top-3 条目的频率中位数 **0.4125**、最小 **0.07**、≥0.8 的仅 **20** 个。

### 4.5 Jaccard 定义（三处用法）

- 定义：`J(A,B) = |A ∩ B| / |A ∪ B|`；本处 `A,B` 为某目标某方法的 Top-3 变量集合（|A|=|B|=3），并集大小 `= 6 − |A∩B|`，故 `J = k/(6−k)`，交集 `k∈{0,1,2,3}` → 取值只能是 **{0, 0.2, 0.5, 1}**。
- 用法 1：方法两两之间（3 对）→ `question2_method_Jaccard.csv`；每目标的 `mean_method_Jaccard` = 三对均值；全表均值 **0.266**。
- 用法 2：岭 α 敏感性：α∈{10,1000} 的 Top-3 对 α=100 的 Top-3（`Jaccard_vs_alpha_100`）。
- 用法 3：网络边集：全样本边集 vs 每个 bootstrap 重采样边集的 `edge_Jaccard`。

### 4.6 网络构建（阈值、边权、Louvain、模块数）

| 项 | 设定 |
|---|---|
| 输入矩阵 | **`D02`**（已核验 = Spearman，231×231） |
| 边判据 | `\|ρ_ij\| ≥ 0.6`（i<j，上三角；等价于 266 条无向边） |
| 边权 | `weight = \|ρ_ij\|`；另存 `signed_correlation = ρ_ij` |
| 节点 | 231 个 V 变量（无向图，`nx.Graph`） |
| 社区发现 | `nx.community.louvain_communities(g, weight='weight', seed=20261026)`；**resolution 未显式设置 → 默认 1.0**；其它参数默认（`threshold=1e-7`, `max_level=None`） |
| 社区排序/标号 | `sorted(communities, key=(-len, min))`，标签 1…K |
| 模块度 | `nx.community.modularity(g, communities, weight='weight')` |
| 运行结果 | 边 **266**、模块 **120**（其中 19 个含 ≥2 变量、最大 23 个变量，其余 101 个为孤立点即单点模块）、孤立点 **101**、模块度 **0.7446380**、最大连通分量 **99** 个变量 |

**阈值敏感性**（`seed=20261026` 固定，`question2_network_sensitivity.csv`）：

| cutoff | 边 | 模块 | 孤立点 | 模块度 | ARI vs 0.6 |
|---|---|---|---|---|---|
| 0.4 | 1660 | 21 | 14 | 0.5021 | 0.2143 |
| 0.5 | 645 | 58 | 48 | 0.6552 | 0.3833 |
| **0.6** | **266** | **120** | **101** | **0.7446** | 1 |
| 0.7 | 109 | 171 | 150 | 0.7442 | 0.3844 |
| 0.8 | 39 | 208 | 194 | 0.6853 | 0.0977 |

**种子敏感性**（cutoff=0.6，`seed=0…19`）：边数恒 266、模块数恒 120、孤立点恒 101；模块度 0.7422–0.7450；ARI vs seed=20261026 在 seed 6/7 为 0.9554/0.9811，其余 1.0。→ 结论写法：**cutoff 敏感、Louvain 随机种子不敏感**。

**网络 bootstrap（40 次）**：

- 只对前 `min(40, bootstrap)=40` 个重采样做：`bcorr = Spearman(重采样 X)` → 同 cutoff 0.6、同 seed 20261026 重跑 Louvain。
- 记录：`edges`、`communities`、`modularity`、`ARI_vs_full`（与全样本标签的调整兰德指数）、`edge_Jaccard`（与全样本边集）。
- 运行结果：ARI 中位数 **0.7492**、边 Jaccard 中位数 **0.7182**（`question2_network_bootstrap.csv` 40 行 + 表头）。

### 4.7 阈值 hinge 回归（公式、HC3、BH、21 变量筛选条件）

- **筛选条件（得到 21 个变量、1050 个检验）**：
  1. 变量在 `D08.var_reference` 的 `threshold_mean` 非空（该表仅这些变量有阈值）；
  2. 变量同时在 `D08.ref_scale` 与 `D01` 的列中；
  3. `threshold > 0`；
  4. 原生观测数 `n ≥ 30`；
  5. `n_below = #{x_i ≤ 1} ≥ 10` 且 `n_above = #{x_i > 1} ≥ 10`；
  6. `design1` 列秩 = 3（否则 hinge 不可估）。
  运行结果为 21 个变量：`V003, V004, V005, V006, V008, V010, V012, V013, V016, V021, V023, V024, V027, V029, V032, V033, V039, V118, V121, V128, V155`；×50 目标 = **1050** 行。
- **模型**（逐变量 × 逐目标）：`x = native/threshold`（原生值取 `ref_scale`，不用 10^D01，避免对数地板被当成精确原生测量）
  ```
  M0: y = a0 + a1·x
  M1: y = b0 + b1·x + b2·(x−1)_+          # hinge，折点即归一化阈值 1
  ```
- **F 检验（同方差假设）**：`F = max(rss0 − rss1, 0) / max(rss1/(n−3), 1e-30)`，`p = F.sf(F, 1, n−3)`；`hinge_slope_change = b2`；`relative_rss_reduction = (rss0−rss1)/rss0`。
- **HC3**：`H = inv(D1'D1)`；leverage `h_i = Σ_k D1_ik H_ik`；调整残差 `ẽ_i = e_i/(1−h_i)`（`1−h≥1e-10` 截断）；`SE(b2) = sqrt(Σ_i H_{3i}² ẽ_i²)`；`p_HC3 = 2·t.sf(|b2|/SE, n−3)`；并存 `max_leverage`。
- **BH（Benjamini–Hochberg）**：对 p 值升序 `p_(1)≤…≤p_(m)`，`q_(i) = min_{k≥i} (p_(k)·m/k)`，截断到 1，回填原序；**m = 1050**（全部检验一起校正），两列 p 值分别校正 → `q_BH_exploratory`、`q_BH_HC3_exploratory`。
- 运行结果：`q_BH < 0.05` 共 **174** 行，`q_BH_HC3 < 0.05` 共 **166** 行；代码与论文均标为**探索性**。

### 4.8 关键数值速查（问题 2）

| 项 | 数值 |
|---|---|
| D02 核验 | Spearman，MAE 1.6e-16；Pearson 0.0877 |
| 关联视角 | 3 个（spearman / rank_ridge λ=100 / quantile_eta2，5 箱） |
| 网络 | cutoff 0.6、266 边、120 模块（19 个非单点）、101 孤立点、模块度 0.7446、最大连通分量 99 |
| Louvain | resolution 1.0（默认）、seed 20261026 |
| bootstrap | 200 次行重采样；Top-3 频率中位数 0.4125、最小 0.07、≥0.8 共 20 |
| 网络 bootstrap | 40 次；ARI 中位数 0.7492、边 Jaccard 0.7182 |
| 方法间 Jaccard | 平均 0.266 |
| 阈值 hinge | 21 变量 × 50 目标 = 1050 检验；q_BH<0.05 174、q_BH_HC3<0.05 166 |

---

## 5 问题 3 规格（条件生成 + 结构修复 + 受约束迁移）

### 5.1 联合基线生成器 `ConditionalGaussian`

超参数（默认值即最终取值）：`covariance="lw"`, `rank=5`, `tau=5.0`, `conditional=True`, `posterior_predictive=False`。

拟合顺序（`fit(x, groups)`，`x` 为 231 维 D01 混合刻度）：

1. `SimpleImputer(strategy="median")`（只用训练行统计）。
2. `QuantileTransformer(n_quantiles=min(n,100), output_distribution="normal", random_state=SEED, subsample=None)` → 逐列经验 CDF 映射到标准正态（`n=250` 时 100 个分位点）。
3. **类均值收缩（伪计数 τ=5）**：
   ```
   w_c = n_c / (n_c + 5)
   m_c = w_c · mean_c + (1 − w_c) · m_global
   ```
   （R20: 28/(28+5)=0.848；R12: 10/15=0.667；R13: 11/16=0.688）
4. 残差：`r_i = z_i − mean_{c(i)}`（conditional=True）或 `z_i − m_global`（global_lw）。
5. **协方差：Ledoit–Wolf** `LedoitWolf(assume_centered=True).fit(residual)` → `Σ`；`shrinkage_` 写入结果（231 维联合模型：**0.14375**）。类间共享同一 `Σ`（"牺牲类特有相关性，换取小样本可估参数"）。
6. **PPCA 版本**（`covariance="ppca"`）：对样本协方差（`r'r/n`）特征分解，`q = min(rank, 230, n−2)`，`σ² = max(尾部特征值均值, 1e-4)`，`W = V_q·sqrt(max(λ_q − σ², 0))`，`Σ = WW' + σ²I`。
7. **后验预测修正**（`posterior_predictive=True`，仅 conditional）：`Σ ← Σ·n/(n−C)`（C=类数），采样方差因子 `vf_c = 1 + 1/(n_c+τ)`，NLL 相应加 `d·log vf` 并把二次型除以 `vf`。
8. 采样：`z = m_c + sqrt(vf_c)·N(0,I_d)·factor.T`，再 `inverse_transform` 回原刻度；`factor = V·sqrt(max(λ,1e-8))`。
9. **秩空间高斯 NLL**：
   ```
   NLL_i = 0.5·( d·log2π + logdet Σ + d·log vf_i + (z_i−m_c)' Σ^{-1} (z_i−m_c)/vf_i )
   ```

### 5.2 生成模型对比（指标定义与运行结果）

**协议**：`StratifiedShuffleSplit(n_splits=5, test_size=0.30, random_state=20261026)`，按 regime 分层 → 每次 **175 训练 / 75 留出**；每个候选在每折重新 `fit`（留出样本不进入分位数或插补值）。

- **核宽**：`bandwidth = median( pdist(z_train) )`（训练集变换后两两欧氏距离的中位数），只用训练、不看留出；结构分支另加 `max(·, 1e-8)`。
- **能量距离（V 统计量）**：`E = 2·mean(A2B) − mean(A2A) − mean(B2B)`。
- **MMD²（V 统计量，高斯核）**：`exp(−d²/(2h²))` 三个块的均值组合 `MMD² = mean(AA)+mean(BB)−2·mean(AB)`。
- **生成参照量**：每类每次生成 `n = 该类训练样本数`，重复 **10 次**取均值（消除样本量不对称偏差）。
- **参照底线**：真实训练 vs 留出同类 的同指标（`real_train_vs_holdout_*`）也一并输出。

**231 维联合基线运行结果**（`question3_heldout_generator_summary.csv`，5 折 × 22 类均值）：

| method | energy_v | mmd2_v | NLL |
|---|---|---|---|
| conditional_lw | 27.7696 | 0.31272 | 417.06 |
| conditional_ppca10 | 28.8706 | 0.32964 | 435.27 |
| conditional_ppca5 | 29.2125 | 0.33480 | 437.88 |
| global_lw | 29.8929 | 0.34601 | 397.02 |

**226 维结构分支运行结果**（`question3_structure_heldout_summary.csv`，同协议）：

| method | energy_v | mmd2_v | NLL |
|---|---|---|---|
| conditional_lw | 27.2519 | 0.30766 | 409.83 |
| conditional_posterior_predictive | 27.3579 | 0.30986 | 398.21 |
| empirical_marginal_copula | **22.4676** | **0.23293** | NaN（有原子，不适用） |
| global_lw | 29.6480 | 0.34532 | 390.21 |

> 两表**不可直接比较**：表示空间不同（231 D01 混合 vs 226 原生混合）、核宽各自按训练集重算、指标在同一模型自己的秩空间内定义。

### 5.3 结构生成分支（226 基础量 → 5 派生量）

**表示定义**

- `BASE` = 226 列 = `FEATURES` 去掉 `{V037,V228,V229,V230,V231}`。
- `load_native_inputs`：`V001–V036` 换成 `D08.ref_scale` 的**原生值**（保留 0、负值和真实缺失：V024 缺 1、V035 缺 39）；`V039`、`V109` 若 D01 缺失用 ref 补；其余列保留 D01 观测刻度。→ "native_mixed"。
- `expand_native`：由 226 个基础量按 §1.4 五条公式算派生聚合，拼成 231 列原生混合表示；`native_to_recorded` 再取 log10 得 231 列 D01 混合刻度（派生量的记录值 = log10(原生聚合)）。
- `valid_native`：226 个基础量全有限，且 5 个派生聚合有限且 **> 0**。

**拒绝重采样规则（`sample_valid`）**

```
while remaining > 0 and attempts < 60:
    批量 = model.sample(group, max(2·remaining, 50), rng)     # 至少 50 个候选
    保留其中 valid_native 为真的前 remaining 个
    attempts += 1
若 remaining > 0 → RuntimeError（不回退、不取绝对值、不截断成 ε）
```
运行结果：R20/R12/R13 各 1 批、每批 200 个候选、拒绝 0 个、保留 100 个；`rejection_rate = 0`；零率诊断（V002 0.92/0.69/0.85、V021 0.87/0.94/0.79、V004 0、V026 0.02/0.18/0.10、V036 0）。

**最终生成器 `ShrunkEmpiricalCopula(tau=5)`**

1. **逐列逐类收缩经验 CDF（步进函数）**：对类 c、列 j，
   ```
   w_jc = n_jc / (n_jc + 5)          # n_jc = 该类该列"非缺失"观测数
   权重：类内每个观测 w_jc/n_jc，全局每个观测 (1−w_jc)/N_j
   值：类内观测 ∪ 全局观测，按值排序后权重同序累加，末位归一为 1
   ```
2. **依赖（共享相关矩阵）**：对每个 (类, 列) 用"质量块中点名次" `mid = 0.5·(F(left−1) + F(right−1))`，`ndtri(clip(mid, 1e-6, 1−1e-6))` 得正态分数；对 **226 维**正态分数做 `LedoitWolf()`（默认 `assume_centered=False`）→ 协方差 → 归一成相关阵 `R`（`R_ij = Σ_ij/(σ_i σ_j)`，对角置 1）；`R = VΛV'`，`factor = V·sqrt(max(Λ,1e-10))`。
3. **采样（无类均值位移）**：`z = N(0,I)·factor.T`，`u = Φ(z)`，逐列 `idx = searchsorted(cumulative, u, side='left')`，取该列池化边际的取值（离散广义逆，**零/负值不会被插值跨过**）。
4. 原子概率可查：`atom_probability(c, j, 0)` = 边际中取 0 的权重和（如 V021 的 P(0) 三类分别为 0.799/0.891/0.835）。

**每类 100 的抽样/截断方式**

- R20、R12、R13 各抽 100 个，共 **300** 行；`id` 形如 `R20_s001`…`R13_s100`；三类共用 `np.random.default_rng(20261026)` 顺序抽取（R20→R12→R13）。
- 抽样即 §5.3 的拒绝重采样；"截断"体现在批量 `max(2·remaining,50)` 与"取前 remaining 个"（不重排、不加权）。
- 输出三份：`..._base226_native.csv`（226 列）、`..._full231_native.csv`、`..._full231_D01_scale.csv`（各 300 行 + `generated_id`/`regime`）。

**代表筛选规则（`write_representatives`，`max_per_class=3`）**

- 兼容性条件：5 个派生聚合**同时**落在同类真实观测的 `[min, max]` 内（`all_five_ranges_pass`）。
- 排序键：`(nearest_real_class_rank_distance, class_center_rank_distance, generated_id)`，取前 3。
- 运行结果：R20 66/100、R12 20/100、R13 21/100 通过；各取 3 个，**共 9 个代表**（`question3_structure_representative_summary.csv`）。
- 明确限制：代表样本继承的是**未筛选生成器**的留出指标；筛选改变输出分布；真实 min/max 不是总体支持边界。

### 5.4 迁移：类别均值平移、SLSQP、182 自由坐标、精确 QP、输入修复、三重上界

**(a) 类别均值平移公式**

- 结构分支（226 原生坐标，中位数插补后）：
  ```
  shift = mean_{R20}(X_filled) − mean_{R15}(X_filled)      # 逐坐标
  proposal = X_source + shift                              # 再按 box 裁剪
  ```
- 联合基线分支（`generation.py`，秩空间）：
  ```
  z_prop = z_source − m_R15 + m_R20
  proposal = QuantileTransformer.inverse_transform(z_prop)
  ```
两种写法都是"把 R15 的类中心平移到 R20 的类中心"，差别只在表示空间（原生 vs 秩空间）。

**(b) SLSQP 目标与约束（结构分支，226 维）**

- 归一化尺度 `s_k = q90(X_filled,k) − q10(X_filled,k)`，`<1e-8 → 1`；位移 `u` 以初值 `origin` 为原点：`x = origin + u∘s`。
- 目标（到 proposal 的加权平方距离）：
  ```
  min_u  ½ · Σ_k ( (x_k − candidate_k)/s_k )² ，  ∇_u = (x − candidate)/s
  ```
- 不等式约束（一次返回 1 + 5 个分量）：
  ```
  g0 = optimization_cap − ŷ38(x) ≥ 0                  # 评分上界
  g1..g5 = (aggregate_r(x) − ε_r)/scale_r ≥ 0 ,  ε_r = 1e-10·max(median|aggregate_r|, 1e-6)
  ```
  派生无效（非正或非有限）的点返回惩罚 `−1000 − Σ max(−g,0)`，**不**对无效点取对数或评分。
- 约束 Jacobian：前向差分 `h = 1e-6`，一次把 `len(BASE)+1 = 227` 个点送入评分器（避免 226 次逐列调用）。
- 边界：`[min(lower,src), max(upper,src)]`，C 坐标上界再压到源值；`SLSQP(maxiter=120, ftol=1e-9)`。
- 事后：C 坐标 `result ≤ src + 1e-9`；重算派生与评分；不满足 → 回退（`verified_feasible_initial` → `source`）。
- 路径搜索：若求解点的 R20 中心距离 ≥ 源点距离，则在 `α∈{0,0.01,…,1}`（101 点）的 `src + α(result−src)` 上取可行且距离最小者；`selected_path_alpha` 记录 α。
- **联合基线分支（`generation.transfer_candidates`，231 维）的差异**：约束只有 `ŷ38(u) ≤ ŷ38(src)`（无 original / observed 两个上界），`score_tolerance = 1e-8`；C 坐标上界用 `nextafter(log10(原生值), −inf)` 回推，避免"观测刻度相等"掩盖原生量级的微小上升；可行域取 `[min(全样本, src), max(全样本, src)]`；目标与 SLSQP 选项相同；不满足则 `fallback_to_source`（运行结果 fallback 0）。

**(c) 182 个自由坐标与精确 QP 乘子解析式**

- 固定坐标 = C 坐标 {V004,V039,V021,V109} ∪ 25 个派生父变量 ∪ V001–V036 三者的并集 = **44** 个（V004、V021 与 C 集重叠，只计一次）；`226 − 44 = 182` 个自由坐标。
- 在 182 维上，只要坐标落在评分器 clip 箱 `[pre.low_, pre.high_]` 内，`ŷ38` 就是**严格仿射**的：
  ```
  β = linear_coef_[37, free] / pre.scale_[free]        # 原始坐标导数
  box_low_k  = min( min_i(X_filled,ik), src_k )         # 逐坐标：原始箱 ∪ 源值
  box_high_k = max( max_i(X_filled,ik), src_k )
  low  = max( box_low[free],  pre.low_[free]  )
  high = min( box_high[free], pre.high_[free] )
  a    = ŷ38(reference) − β'x_init          # 仿射常数（用实际评分锚定，reference = 源点+初值自由坐标）
  rhs  = target − a                          # target = optimization_cap
  ```
- **乘子参数化（解析解）**：对 box + 半空间凸二次规划
  ```
  min_x ½ Σ_j ((x_j − p_j)/s_j)²     s.t.  β'x ≤ rhs,  low ≤ x ≤ high
  ```
  其 KKT 解随乘子 `m ≥ 0` 单调地写成**截断形式**：
  ```
  x(m) = clip( p − m · s² ∘ β , low , high )        # 逐坐标
  ```
  `β'x(m)` 关于 m 单调不增；若 `β'p ≤ rhs` 取 `m=0`；否则：
  - 倍增找括号：`right ← 1, 2, 4, …`（至多 80 次）直到 `β'x(right) ≤ rhs`（找不到则 `qp_bracket_found=False`）；
  - 二分：固定 75 次，保留可行端的 `m`。
- 证书：`qp_actual_prediction − qp_affine_prediction` 的最大值 **2.78e-16**（验证仿射精确）；`qp_linear_halfspace_margin = rhs − β'x(m) ≥ 0`。
- 对象 124 额外输出 `multiplier` 曲线（61 个网格点 + 选中点）：实际预测、仿射预测、加权目标、触碰边界数。

**(d) 平台（clip 箱外）等输入修复**

在 clip 箱外，评分对输入是**平的**，因此"把箱外坐标拉回箱边/改用 proposal 的可行投影"不改变任何目标的预测。`plateau_polish(point)`：

| 情形 | 修复 |
|---|---|
| `pre.low_[k] == pre.high_[k]`（常数坐标） | `x_k ← clip(proposal_k, box_low, box_high)` |
| `x_k ≥ pre.high_[k]` | `x_k ← clip(proposal_k, max(box_low, pre.high_), box_high)` |
| `x_k ≤ pre.low_[k]` | `x_k ← clip(proposal_k, box_low, min(box_high, pre.low_))` |

结果另存 `..._QP_platform_profile_comparison.csv`：50 个目标预测的最大绝对差、Y38 前后、加权目标前后、中心距离前后、箱外坐标数与最大超出量，并注明 `"polished_point_not_original_clip_box_QP_solution"`（修复后的点不是原凸问题的解）。

**(e) 观测源守卫的三重上界与数值内缩**

```
cap              = min( ŷ38(原始 D01 源), ŷ38(重表达源), 观测 D04.Y38 )
optimization_cap = cap − 1e-6        # 仅当有观测源时内缩
score_tolerance  = 0                 # 有观测源时无正容差
```
- 若初值预测 > `optimization_cap`，先做 phase-1 锚点 + 45 次二分找最大可行 λ（只动 182 个自由坐标，按 `linear_coef_[37,k]` 的符号把坐标推向使 Y38 下降的一侧）。
- 交付前用**保存后重读的 CSV**再评一次分，判据 `≤ cap`（无正容差）；`strict_saved_score_margin = cap − ŷ38`。
- 运行结果（11 个源对象）：C 坐标 44/44 通过；`all_score_caps_pass` 11/11；`strict_observed_source_pass_count` 11/11；`unresolved` 0；`source_unchanged` 0；`optimizer_success` 9；`max_guard_minus_observed = −9.9966e-07`（恰好等于 −1e-6，说明守卫是紧的）；旧模型分支中超出观测源的有 5 个。

### 5.5 Wasserstein 下界的计算

对 4 个 C 变量，用 R15/R20 的原生观测值并集作网格 `t`：

```
S_c(t) = mean( x_c > t )                     # 尾概率（经验）
Δ(t)   = S_R20(t) − S_R15(t)                 # = 1−F_target − (1−F_source) = F_source − F_target
W1_lower = Σ_i max( Δ(t_i), 0 ) · ( t_{i+1} − t_i )
归一化 = W1_lower / threshold_native
```

（记号：source = R15，target = R20；即"迁移后分布"记作 Q、R15 记作 source。）

依据（代码注释）："不增"要求 `F_Q ≥ F_source`；而 `F_source − F_target = target_tail − source_tail`；一维 W1 等于 CDF 间面积，故把正尾差按相邻断点间距求和即为下界。

运行结果（`question3_feasibility_bounds.csv`）：

| feature | 阈值 | W1 下界 | 归一化 | 最大正尾差 |
|---|---|---|---|---|
| V004 | 17.25 | 30.7226 | 1.78102 | 0.71429 |
| V039 | 0.29925 | 0.439847 | 1.46983 | 0.44481 |
| V021 | 0.206333 | 0.00490749 | 0.0237843 | 0.087662 |
| V109 | 0.35 | 0.408472 | 1.16706 | 0.548701 |

### 5.6 关键数值速查（问题 3）

| 项 | 数值 |
|---|---|
| 均值收缩伪计数 τ | 5（权重 `n_c/(n_c+5)`） |
| 协方差 | Ledoit–Wolf，`assume_centered=True`（联合模型 shrinkage 0.14375） |
| PPCA 维数 | rank 5 / 10 两个对照（`q=min(rank,230,n−2)`，`σ²≥1e-4`） |
| 留出 | 5 折 × 30%（175/75）；每类生成 10 次 |
| 结构表示 | 226 基础 + 5 派生（V001–V036 原生）；派生须 >0 |
| 每类生成 | 100 × {R20,R12,R13} = 300 |
| 代表 | 3/类，共 9（通过率 66/20/21 per 100） |
| 迁移源/目标 | R15（11 个）→ R20（28 个） |
| 自由坐标 | 182（固定 44） |
| 数值内缩 | 1e-6（守卫 cap） |
| SLSQP | maxiter 120、ftol 1e-9、差分 h=1e-6 |
| QP 二分 | 括号 ≤80 次倍增 + 75 次二分；仿射误差 2.8e-16 |
| 守卫结果 | 11/11 通过三重上界，最大 margin −1e-6 |
| W1 下界 | V004 30.72、V039 0.4398、V021 0.00491、V109 0.4085 |

---

## 6 结果文件字段字典

### 6.1 `question1_metrics.csv`（600 行 = 50 目标 × 4 模型 × 3 协议）

| 列 | 含义 |
|---|---|
| `target` | `Y01`…`Y50` |
| `model` | **{`mean`, `ridge`, `pls`, `selected`}**：`mean`=训练折逐目标均值基线；`ridge`/`pls`=内层该族最优；`selected`=内层 9 候选中总最优 |
| `protocol` | **{`nested_random_5x3`, `nested_regime_holdout_5x3`, `nested_D04_ID_holdout_5x3_sensitivity`}** |
| `mae` / `rmse` / `r2` | 折外（OOF）逐目标指标 |
| `mae_improvement_over_mean` | `1 − mae/mae_mean`（同协议同目标；`mean` 行为 0） |

### 6.2 `question2_top3.csv`（150 行 = 50 目标 × Top-3；列数 30）

| 列 | 含义 |
|---|---|
| `target`, `feature` | 目标与入选变量 |
| `borda_mean_rank` | 三方法名次均值（1 最好，231 最差） |
| `top_rank` | 该目标内 Borda 名次（1/2/3） |
| `spearman_signed_after_median_imputation` | 中位数插补后的**有符号** Spearman ρ |
| `within_regime_rank_correlation` | 去类均值后的秩相关（类内关联） |
| `bootstrap_selection_frequency` | 200 次重采样中进入 Top-3 的频率 |
| `bootstrap_MC_standard_error` | `sqrt(p(1−p)/200)` |
| `module` | 该变量所属 Louvain 模块编号（1–120） |
| `fixed_module_selection_frequency` | 按全样本模块标签统计的模块入选频率 |
| `mean_method_Jaccard` | 三对方法 Top-3 的平均 Jaccard |
| `borda_mean_rank_alpha_10` / `_alpha_1000` | 岭 λ=10 / 1000 时的 Borda 平均名次 |
| `spearman_score` / `_rank` / `_bootstrap_frequency` | 方法 1 的 \|ρ\|、名次、方法内入选频率 |
| `rank_ridge_score` / `_rank` / `_bootstrap_frequency` | 同上（λ=100 的 \|标准化岭系数\|） |
| `quantile_eta2_score` / `_rank` / `_bootstrap_frequency` | 同上（5 箱 η²，已调整） |
| `source_group`, `unit_code`, `trend`, `threshold_mean`, `threshold_median` | 来自 `D08.var_reference` 的元数据（无则空） |
| `derived_feature` | 该变量是否 5 个派生量之一 |
| `D06_same_data_reference_correlation` | 同数据参照块 `D06` 中该 (V,Y) 的相关系数 |
| `global_reference_importance_unknown_procedure` | `D08.ref_importance` 的 importance（生成过程未说明） |

> 同结构的全表版本 `question2_all_feature_scores.csv` 有 231×50 = 11550 行；`question2_bootstrap_top3.csv` 有 200×50 = 10000 行（`replicate,target,top1,top2,top3`）。

### 6.3 `question3_structure_heldout_summary.csv`（4 行）

| 列 | 含义 |
|---|---|
| `method` | `global_lw` / `conditional_lw` / `conditional_posterior_predictive` / `empirical_marginal_copula` |
| `energy_v` | 5 折 × 22 类 × 10 次生成的能量距离 V 统计量均值（226 维训练秩空间） |
| `mmd2_v` | 同上，高斯核 MMD² V 统计量（核宽 = 训练集 `median(pdist)`） |
| `gaussian_rank_space_nll` | 秩空间高斯 NLL 均值；`empirical_marginal_copula` 为 **NaN**（有原子） |

对应明细 `question3_structure_heldout_metrics.csv`（440 行 = 5 折 × 4 方法 × 22 类）列：`split, method, regime, n_train, n_holdout, energy_v, mmd2_v, gaussian_rank_space_nll, real_train_vs_holdout_energy_v, real_train_vs_holdout_mmd2_v, invalid_candidates_rejected, evaluation_space`；其中 `evaluation_space = "226_native_mixed_base_training_rank_space"`。

### 6.4 `question3_structure_transfer_critical_comparison.csv`（55 行 = 11 源对象 × (4 个 C 坐标 + 1 个 Y38)）

| 列 | 含义 |
|---|---|
| `source_object` | R15 源对象编号（如 124, 81, 218…） |
| `criterion` | `V004`/`V039`/`V021`/`V109`（原生坐标）或 `Y38_model_continuous`（拟合连续评分） |
| `threshold` | 对应的临界阈值（V004 17.25、V039 0.29925、V021 0.206333333、V109 0.35；由 `threshold_reports.py` 用 D08 全精度统一） |
| `source_native` | 源值（C 坐标为原生坐标；Y38 行为源预测值） |
| `proposal_native` | 未投影的平移提案值 |
| `after_native` | 迁移后值（C 坐标为原生坐标；Y38 行为最终预测） |
| `source_ratio` / `after_ratio` | 除以阈值（仅 C 坐标行；Y38 行为空） |
| `nonworsening` | `after ≤ source + 容差`（C 坐标 1e-9；Y38 为 `score_tolerance`，本分支 1e-8） |
| `completion_status` | `feasible_moved_candidate` / `source_retained_no_transfer` / `unresolved_no_feasible_candidate_found` |
| `scope` | C 坐标行 `"native_candidate_coordinate; candidate_derived_relations"`；Y38 行说明"仅拟合预测、真实 K 未识别" |
| `original_source_prediction` | 原始 D01 源（未重表达）的 Y38 预测（仅 Y38 行） |
| `constraint_score_cap` | 评分上界（本分支 `min(src_score, original_score)`；守卫分支再加观测值） |
| `original_source_nonworsening` | `after ≤ original_source_prediction + tol` |
| `observed_source_y38` | 观测 D04.Y38（**仅守卫分支有值**，本表为空） |
| `optimization_cap` | 实际优化用的 cap（有观测源时 `= cap − 1e-6`） |
| `numerical_margin` | 0 或 1e-6（浮点内缩量，非统计安全界） |
| `observed_source_nonworsening` | 仅守卫分支（本表空） |
| `all_score_caps_pass` | 仅 Y38 行 |

### 6.5 其它关键表（简表）

| 文件 | 行数 | 关键列（含义） |
|---|---|---|
| `question1_final_selection.csv` | 9 | `family, parameter, inner_normalized_mse`（全数据内层 3 折排序） |
| `question1_inner_selection.csv` | 135 | `family, parameter, inner_normalized_mse, outer_fold, selected_in_fold, protocol` |
| `question1_cv_folds.csv` | 250 | `object, random_outer_fold, regime_outer_fold, D04_ID_outer_fold`（每折 50） |
| `question1_conformal_metrics.csv` | 50 | `calibration_n=50, test_n=50, nominal_marginal_coverage=0.9, test_covered, test_coverage, coverage_ci95_low/high, interval_width=2q, calibration_order_statistic=46` |
| `question1_conformal_joint_widths.csv` | 50 | `joint_box_halfwidth, calibration_max_residual_quantile=4.083056, train_target_scale` |
| `question1_conformal_joint_coverage.csv` | 50 | `object, all_50_covered_by_joint_box, all_50_covered_by_marginal_intervals, nominal_joint_coverage=0.9` |
| `question1_conformal_split.csv` | 250 | `object, split ∈ {train, calibration, test}`（150/50/50） |
| `question1_protocol_cutpoints.csv` | 300 | `scope(fullfit/oof), random_outer_fold, training_n(250/200), target, A_mu, A_sd_ddof0, B_cutpoint_1..6, B_distinct_cutpoint_count, B_duplicate_cutpoints` |
| `question1_protocol_agreement.csv` | 102 | `dataset(fitted/oof), target, n_scores, exact_agreement_rate, mean_absolute_grade_difference, mean_B_minus_A, fraction_B_greater_A, fraction_B_less_A, maximum_absolute_grade_difference, comparison_kind`（50 目标 × 2 数据集 + 2 行 `overall`） |
| `question1_protocol_K_distribution.csv` | 7×2 + 生成 | `dataset, protocol, grade, count, frequency, n_objects, K_ge2_count, K_ge2_rate`（生成部分另有 `grouping, regime`） |
| `question1_grade_identification_bounds.csv` | 12500 | `observed_D04, observed_D04_serialized_decimal, unconditional_domain_lower/upper, common_monotone_ASSUMPTION_lower/upper/set_size, distinct_value_count, distinct_ascending_rank, ALL7_ASSUMPTION_lower/upper/set_size, ALL7_ASSUMPTION_grade_at_least_2_status, is_critical_target_Y38` |
| `question2_ridge_alpha_sensitivity.csv` | 100 | `target, alpha(10/1000), Top3, Jaccard_vs_alpha_100` |
| `question2_network_sensitivity.csv` | 25 | `cutoff, seed, edges, communities, isolates, modularity, ARI_vs_cutoff_0_6` |
| `question2_network_bootstrap.csv` | 40 | `replicate, edges, communities, modularity, ARI_vs_full, edge_Jaccard` |
| `question2_network_nodes.csv` | 231 | `feature, module, degree, strength, source_group` |
| `question2_network_edges.csv` | 266 | `feature_a, feature_b, weight=\|ρ\|, signed_correlation=ρ` |
| `question2_module_stability.csv` | 120×50 | `target, module, module_size, any_top3_bootstrap_frequency` |
| `question2_threshold_hinge_exploratory.csv` | 1050 | `feature, target, n, n_below, n_above, threshold_native, hinge_slope_change, relative_rss_reduction, F, p_normal_homoskedastic_assumption, p_HC3_approximate, max_leverage, q_BH_exploratory, q_BH_HC3_exploratory` |
| `question3_feasibility_bounds.csv` | 4 | `feature, critical_threshold_native, native_W1_lower_bound, W1_bound_divided_by_critical_threshold, max_positive_tail_gap, scope` |
| `question3_tail_compatibility.csv` | 4×网格 | `feature, native_threshold, R15_tail, R20_tail, target_minus_source_tail` |
| `question3_structure_representative_summary.csv` | 3 | `regime, existing_pool_count=100, all_five_ranges_pass_count(66/20/21), selected_count=3, selection_rule, interpretation, heldout_metric_scope` |
| `question3_structure_zero_negative_rates.csv` | 30 | `regime, feature, sample(real_reference/generated), n_rows, n_observed, missing_rate, zero/negative/positive_rate_among_observed, theoretical_zero_probability_before_rejection, proposal_zero_rate_before_rejection, valid_pool_zero_rate_before_truncation, proposal_count, valid_proposal_count, kept_count, rejection_rate` |
| `question3_structure_marginal_effective_counts.csv` | 22×226=4972 | `regime, feature, class_rows, effective_observed_count=n_jc, global_observed_count, class_cdf_weight=w_jc, global_cdf_weight=1−w_jc` |
| `question3_structure_recording_floors.csv` | 37 | `feature, positive_floor`（每列最小正原生值/2） |
| `question3_structure_transfer_optimization.csv` | 11 | `optimizer_success, iterations, fallback_to_source, fallback_to_feasible_initial, source_unchanged, completion_status, unresolved, mathematical_score_cap, optimization_cap, phase1_applied, phase1_selected_lambda, final_candidate_origin, path_search_applied, selected_path_alpha, distance_to_R20_mean_before/after, standardized_displacement, after_min_derived_value` |
| `question3_observed_source_guard_exact_qp_certificate.csv` | 11 | `free_coordinate_count=182, fixed_coordinate_count=44, qp_bracket_found, qp_multiplier, mathematical_cap, optimization_cap, qp_actual_prediction, qp_affine_prediction, actual_minus_affine_prediction, qp_linear_halfspace_margin, qp_free_objective, endpoint_actual_prediction, proof_scope` |
| `question3_protocol_K_summary.csv` | 9 | `branch, baseline_kind(model_prediction/observed_D04), n_objects=11, continuous_nonincrease_exact_count, A_nonincrease_count, B_nonincrease_count, both_protocols_nonincrease_count, all_criteria_pass_count, maximum_continuous_delta` |

---

## 7 与论文方法描述相关的注意事项 / 限制

**关于问题 1（预测与等级）**

1. **目标标准化不可省**：50 个目标的 D04 量纲差异大，PLS 用 `TransformedTargetRegressor(StandardScaler())` 逐目标按训练标准差缩放，避免波动大的目标独占共同方向；因此 `R²`/`MAE` 可跨目标比较，但**回归系数不能在目标间直接比大小**。
2. **裁剪（1%/99%）是训练折统计量**：解释为"限制少数巨大数值对线性模型的支配"，**不是**判定极端值错误；原始数据不被改写。生成样本的物理阈值（如 V004 ≥ 17.25）**不在该标准化/裁剪空间里检查**。
3. **缺失值只填训练中位数**：`transform` 不重估；测试/生成数据用训练折中位数与边界。
4. **OOF 与 fitted 是两种东西**：`question1_continuous_fitted.csv`、`question1_protocol_{A,B}_fitted_grades.csv` 用全部 250 行参数，**不能**当作样本外精度；OOF 版本（5 折各用折外 200 行）才是泛化口径。两者数值不可混用（协议一致率 fitted 0.234 vs oof 0.259 即为参数集差异的体现）。
5. **三种验证协议的结论不同**：regime 留组下 selected 的平均 R² 从 0.2172（随机）降到 0.1573，且内层选择在 regime 协议下 2/5 折改选 ridge1000 → 论文应把"协议"作为结论的一部分，而不是只报一个数字。
6. **等级是人为约定，不是原始评分**：`grade = clip(floor(3 + slope·(x−μ)/σ + 0.5), 0, 6)`；`slope` 扫 {0.5,1,1.5,2} 会改变等级，尤其改变 `Y38≥2` 判定（代码中专门输出 `K_threshold_status_changed_fraction`）。**不存在**原始等级准确率，因为原始标签不可得（D03 非空勾选 = 0）。
7. **D03 空白 ≠ 0 分**：模板公式把未选的正等级默认记 0，代码用正则解析 `ISBLANK` 引用并显式补 `C/S` 格，避免把"空白模板"误当"评分者给的 0"。
8. **conformal 只做一次切分**：150/50/50 单一划分，覆盖率本身有抽样波动（论文给出 Beta 区间，如 Y09 覆盖 0.84 → CI [0.709, 0.928]）；`joint_box` 0.84 明显低于名义 0.9，且"50 个边际区间同时覆盖"仅 0.10 —— 说明**边际 90% 不等于联合 90%**。
9. **重复 `object_id` 语义未知**：D04 的 `object_id` 有重复，实体级依赖未解决，故只把 ID 留组作为敏感性协议。
10. **等级识别界不是概率**：`ALL7` 假设下界收缩到平均 6.73/7 个可能值，162 格为单点，但**没有任何概率解释**；`Y38≥2` 只有 17 行可判定，不能据此声称"安全"。

**关于问题 2（关联与网络）**

11. **关联不是因果**：三个视角是"探索性关联"，Borda 排名不是贡献度；代码注释明确 `association, not causal effect; grades unavailable`。
12. **三种分数不可直接比较**：`|ρ|`、`|岭系数|`、`η²` 量纲不同，因此只在**方法内部**排名再取平均名次（Borda）；跨方法比大小无意义。
13. **bootstrap 频率不是概率**：`bootstrap_selection_frequency` 是 200 次重采样的入选率，`MC standard error` 只反映重采样次数（`sqrt(p(1−p)/200)`），不构成对总体的置信区间；Top-3 频率中位数仅 0.41，说明"选谁"高度不稳定。
14. **网络对阈值敏感、对种子不敏感**：cutoff 0.4→0.8 使边数 1660→39、模块数 21→208，ARI 最低 0.098；而 Louvain 种子 0–19 结果几乎不变（ARI ≥ 0.955）。论文必须报告这条对照，不能只报 cutoff=0.6。
15. **101 个孤立点不是"无关联"**：只是 `|ρ|<0.6`；模块划分只在 19 个非单点模块内有意义（最大连通分量 99 个变量）。
16. **η² 的 5 箱是自由度折衷**：箱子等频、并列名次同箱，`n−G` 校正扣掉组均值自由度；不能当成连续非线性关系的完整刻画。
17. **阈值 hinge 是探索性的**：21 个变量（有 `threshold_mean` 者）× 50 目标 = 1050 个检验，BH 后 174/166 个显著；F 检验假设同方差，HC3 只是稳健替代；`threshold` 本身来自给定表而非估计，**未做阈值不确定性传播**。
18. **D06 只有 44 行**：交叉块核验是"同数据参照"，不是独立样本；`D06_same_data_reference_correlation` 列不能当外部验证。

**关于问题 3（生成与迁移）**

19. **不同表示空间不可直接比较**：231 维 D01 混合刻度、226 维原生混合、秩空间、D04 连续刻度是四种空间；能量距离/MMD/NLL 只在**同一模型自己的训练秩空间**内有意义（核宽也随模型重算）。跨表比较（如 `question3_summary.json` 与 `question3_structure_summary.json` 的 `energy_v`）只能在同空间同核宽下读。
20. **经验 copula 的 NLL 是 NaN**：分布有原子（如 V021 的 0 点占 80%–94%），不能用连续高斯密度；`mmd2_v`/`energy_v` 仍可算，但**没有似然可比**。
21. **拒绝重采样会改变分布**：只保留"5 个派生聚合均 > 0"的样本；本数据拒绝率 0，但机制上必须报告 rejection_rate；**绝不**通过取绝对值或截断成 ε 来"修复"无效派生量。
22. **代表样本是筛选后的**：3/类来自"五个派生聚合均在类内观测范围"的池（通过率 66/20/21 per 100），其分布已偏离生成器；留出指标只对**未筛选生成器**成立。
23. **真实 min/max 不是总体支持**：代表筛选的区间来自 28/10/11 个观测的极值，不能宣称"总体可行域"。
24. **零/负值语义**：V021 的 168 个原生 0 与 V004 的 1 个非正值在 log 刻度上共享一个有限地板；`native_to_recorded` 用"训练最小正值/2"作替代下限，且明确要求用**原生参照训练行**拟合地板（不能拿 10^D01 反推值或生成样本重估）。
25. **迁移约束的是拟合预测，不是真实评分**：`Y38` 上界、`K` 非增都是模型预测层面；`true_K = "unidentified"`，`question3_transfer_K_WORKING_ONLY.csv` 只是同一人为映射下的展示。
26. **1e-6 是浮点内缩，不是统计安全界**：`optimization_cap = cap − 1e-6` 只为吸收 CSV 序列化/重读误差；最终判定用保存后重读的 CSV、`≤ cap` 且**无正容差**（`min_strict_saved_cap_margin = 9.9966e-7`）。
27. **平台修复的点不是原 QP 解**：clip 箱外评分是平的，`plateau_polish` 只在不改变任何目标预测的前提下改善类相容距离；文件里明确写 `same_clipped_input; score_equivalence_only; polished_point_not_original_clip_box_QP_solution`。
28. **182 维 QP 的"精确"有边界**：只对"固定 44 列 + 仿射半空间 + box"这一子问题精确；**全 226 维**的类相容性选择没有全局最优保证（`not_global_226d_optimum`）。
29. **W1 下界是经验一维下界**：不是总体置信下界，也不是联合充分条件；`max_positive_tail_gap`（V004 0.714）说明尾部的确存在"必须移动"的部分。
30. **SLSQP/回退路径必须报告**：`fallback_to_source`、`path_search_applied`、`selected_path_alpha`、`phase1_applied` 都是结果的一部分（本次守卫：SLSQP 成功 9/11、路径搜索 2、回退 0）。
31. **随机种子固定但非"逐位可复现"**：BLAS/LAPACK 线程数变化会带来末位差异（`threadpool_limits` 只能限制到库层）；论文写"固定种子 20261026，单线程/2 线程运行"即可，不要承诺 bit-wise 一致。
32. **五条派生关系是候选**：`V037/V228/V229/V230/V231` 的系数来自有限搜索 + 简单系数精修，属于"数据支持的候选"，不是官方定义；`question3_structure_candidate_relation_residuals.csv` 的 1e-14 级残差只证明"实现与公式自洽"，不证明"公式为真"。
33. **冻结依赖版本**：`requirements.txt` 在项目根；`nx.community.louvain_communities`、`sklearn.cross_decomposition.PLSRegression`、`StratifiedShuffleSplit` 的行为随版本可能变动（尤其 Louvain 的默认参数与 PLS 的 `_x_mean` 属性），复现时应固定版本。

---

### 附：一页式参数总表（写论文"方法"时可直接引用）

| 环节 | 参数 |
|---|---|
| 全局 | n=250、231 特征、50 目标、22 类、SEED=20261026、threadpool 2（网络段 1） |
| 预处理 | 中位数填补 → 1%/99% 分位裁剪 → z-score（训练折统计）；目标逐列 z-score |
| 候选 | Ridge α∈{0.1,1,10,100,1000}（选中 1000）；PLS k∈{2,5,10,20}（选中 10） |
| CV | 外层 5 折（随机/留 regime/留 D04_ID），内层 3 折；指标 = 按训练 SD 归一的 MSE |
| 协议 | A：3+(x−μ)/σ → floor(+0.5) → clip[0,6]；B：6 个 (r/7) 分位切点 + searchsorted right |
| conformal | 150/50/50；rank=ceil(51×0.9)=46；覆盖率 0.9012；联合箱 42/50=0.84 |
| 关联 | Spearman；岭 λ=100；η² 5 箱；Borda 平均名次；bootstrap 200 |
| 网络 | \|ρ\|≥0.6；边权 \|ρ\|；Louvain resolution 1.0、seed 20261026；120 模块（19 非单点）、266 边、模块度 0.7446 |
| 网络稳定性 | cutoff 0.4–0.8；seed 0–19；bootstrap 40（ARI 中位 0.7492、边 Jaccard 0.7182） |
| 阈值 hinge | 21 变量 × 50 目标 = 1050 检验；HC3；BH（m=1050）；174/166 显著 |
| 生成 | 条件高斯 copula；τ=5；LW（shrinkage 0.14375）；QuantileTransformer 100 分位；PPCA 5/10 |
| 生成评估 | 5 折 × 30%；能量距离/MMD（核宽 = 训练 median pdist）/秩空间 NLL；每类 10 次 |
| 结构生成 | 226 基础 + 5 派生；收缩经验边际（w=n_jc/(n_jc+5)）+ 共享 LW 相关；拒绝重采样；每类 100 |
| 代表 | 5 范围筛选 + 最近同类 + 中心距离；3/类共 9 |
| 迁移 | 均值平移；SLSQP(120,1e-9)；182 自由坐标精确 QP（乘子解析 + 80/75 二分）；1e-6 内缩；三重上界 |
| W1 下界 | 30.72 / 0.4398 / 0.00491 / 0.4085（V004/V039/V021/V109） |

