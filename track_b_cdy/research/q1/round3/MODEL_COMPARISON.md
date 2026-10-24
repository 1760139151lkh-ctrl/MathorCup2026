# Q1 第三轮模型竞争与推荐

已实际完成三路线及全部预登记敏感性、留年/过程删除、100次年→过程重采样。结果层级为区域站本次参考时刻前的异常候选；不是灾害因果、风险概率或已验证触发TOP5。精确启动真值与独立灾害训练/验证事件均未新增。

## 三套候选TOP5（跨24/72/168h等权名次）

### 原QC0主轨

**A_marginal_ecdf**

| family_name | rank | score | top5_credit |
| --- | --- | --- | --- |
| 土壤水分 | 1.000 | 0.792 | 1.000 |
| 空气热状态 | 2.500 | 0.708 | 1.000 |
| 短波辐射 | 2.500 | 0.708 | 1.000 |
| 土壤热通量 | 4.000 | 0.583 | 1.000 |
| 空气湿状态 | 5.000 | 0.542 | 1.000 |

**B_shrunk_conditional**

| family_name | rank | score | top5_credit |
| --- | --- | --- | --- |
| 土壤热状态 | 1.000 | 0.833 | 1.000 |
| 空气湿状态 | 2.000 | 0.792 | 1.000 |
| 空气热状态 | 3.000 | 0.708 | 1.000 |
| 平均风场 | 4.000 | 0.667 | 1.000 |
| 土壤水分 | 5.000 | 0.500 | 1.000 |

**C_other_family_analog**

| family_name | rank | score | top5_credit |
| --- | --- | --- | --- |
| 土壤水分 | 1.000 | 0.938 | 1.000 |
| 平均风场 | 2.000 | 0.792 | 1.000 |
| 空气湿状态 | 3.000 | 0.667 | 1.000 |
| 土壤热状态 | 4.000 | 0.583 | 1.000 |
| 空气热状态 | 5.000 | 0.417 | 1.000 |

### QC0 + unknown探索轨

**A_marginal_ecdf**

| family_name | rank | score | top5_credit |
| --- | --- | --- | --- |
| 土壤水分 | 1.000 | 0.818 | 1.000 |
| 空气热状态 | 2.500 | 0.697 | 1.000 |
| 短波辐射 | 2.500 | 0.697 | 1.000 |
| 空气湿状态 | 4.000 | 0.667 | 1.000 |
| 土壤热通量 | 5.500 | 0.576 | 0.500 |
| 湍流热交换 | 5.500 | 0.576 | 0.500 |

**B_shrunk_conditional**

| family_name | rank | score | top5_credit |
| --- | --- | --- | --- |
| 空气湿状态 | 1.000 | 0.889 | 1.000 |
| 土壤热状态 | 2.000 | 0.852 | 1.000 |
| 空气热状态 | 3.500 | 0.704 | 1.000 |
| 平均风场 | 3.500 | 0.704 | 1.000 |
| 土壤热通量 | 5.000 | 0.556 | 1.000 |

**C_other_family_analog**

| family_name | rank | score | top5_credit |
| --- | --- | --- | --- |
| 土壤水分 | 1.000 | 0.955 | 1.000 |
| 空气湿状态 | 2.000 | 0.818 | 1.000 |
| 平均风场 | 3.000 | 0.682 | 1.000 |
| 土壤热状态 | 4.000 | 0.591 | 1.000 |
| 湍流热交换 | 5.000 | 0.545 | 1.000 |

## 预登记共识推荐

主报告保留三路线共识；A提供可解释的边际异常底座，B为共线条件异常挑战路线，C为天气过程对照选择挑战路线。没有独立灾害真值，不能以本次目标的异常大小宣称某路线预测获胜。B对组数/缺测和收缩假设敏感，C的对照是匹配代理过程，均保留作挑战证据。

**原QC0主轨**

| family_name | recommended_rank | consensus_score | mean_window_bootstrap_top5_frequency | min_window_bootstrap_valid_draws | stability_label |
| --- | --- | --- | --- | --- | --- |
| 土壤水分 | 1.000 | 0.743 | 0.814 | 44 | conditional_candidate |
| 空气湿状态 | 2.000 | 0.667 | 0.814 | 44 | conditional_candidate |
| 土壤热状态 | 3.000 | 0.639 | 0.843 | 44 | conditional_candidate |
| 空气热状态 | 4.000 | 0.611 | 0.890 | 44 | conditional_candidate |
| 平均风场 | 5.000 | 0.583 | 0.527 | 44 | conditional_candidate |

**unknown纳入影响**

| family_name | recommended_rank | consensus_score | mean_window_bootstrap_top5_frequency | min_window_bootstrap_valid_draws | stability_label |
| --- | --- | --- | --- | --- | --- |
| 空气湿状态 | 1.000 | 0.791 | 0.893 | 44 | conditional_candidate |
| 土壤水分 | 2.000 | 0.745 | 0.833 | 44 | conditional_candidate |
| 土壤热状态 | 3.000 | 0.663 | 0.648 | 44 | conditional_candidate |
| 空气热状态 | 4.000 | 0.608 | 0.822 | 44 | conditional_candidate |
| 平均风场 | 5.000 | 0.563 | 0.436 | 44 | conditional_candidate |

第五席需要保留争议：主点估计的平均风场跨窗平均入选频率为0.527，候补土壤热通量为0.559；两者以每窗44个有效共识draw为条件。按预登记共识仍保留平均风场为第5，但不应将其写成稳定唯一第五致灾因素。

TOP5边界若并列，候选表保留所有有第五席fractional credit的族，不用字母序制造胜负。主推荐仅为9个已有QC族中的相对异常，unknown轨的新增族不自动得到质量认证；某族在B中因零尺度/不足支持不可估计时，三路共识保持null。

## 实际稳定性与比较分母

| quality_track | model_id | leave_year_mean_jaccard | leave_process_mean_jaccard | anchor_shift_min_jaccard | predefined_sensitivity_min_jaccard | bootstrap_min_valid_draws | bootstrap_max_valid_draws |
| --- | --- | --- | --- | --- | --- | --- | --- |
| original_qc_view | A_marginal_ecdf | 0.822 | 0.838 | 0.667 | 0.667 | 89 | 89 |
| original_qc_view | B_shrunk_conditional | 0.790 | 0.934 | 0.667 | 0.429 | 44 | 44 |
| original_qc_view | C_other_family_analog | 0.711 | 0.867 | 0.625 | 0.250 | 89 | 89 |
| unknown_qc_exploration | A_marginal_ecdf | 0.778 | 0.910 | 0.667 | 0.667 | 61 | 89 |
| unknown_qc_exploration | B_shrunk_conditional | 0.670 | 0.882 | 0.667 | 0.429 | 10 | 44 |
| unknown_qc_exploration | C_other_family_analog | 0.634 | 0.809 | 0.500 | 0.429 | 61 | 89 |

`rankings.n_background_years=5`是名义抽取池；每特征实际有效年/过程、缺年与逐年窗口数见effective_feature_support，家族及B校准分母见effective_family_support，尤其unknown通量不能读成全部5年。所有Jaccard是目标排名对训练背景变动的敏感性，非灾害分类准确率。5个背景年与45个7日块代理不等于45个独立灾害。重采样中不足4个唯一年份会使B的留年校准不可估计；其频率仅以有效draw为分母，完整n_requested/n_valid在ranking_stability.csv。推荐表有效draw不足70/100不标稳定。原始100次抽样全部保存，不重抽凑数。

## 方法分歧与限制

A对常值和偏态稳健，但边际差异不排除共线；B可减弱线性共享变化，但收缩、维数、填补和高斯二次距离不是已证实物理过程；C在待评族之外匹配且每年选不同代理过程，仍可能遗漏真实气象背景。比较基于相同因素族、质量轨和窗口，路线间的原始分数不可直接当同一种概率。

方向需逐描述量读取factor_directions和feature_anomalies，不可把整族非负异常分改写成单一升温/增湿方向。名义垂直/土层梯度仅属区域站；降水标签分布不是累计雨量；辐射差值未经本地仪器符号认证；FLUX质量/处理/小时区间unknown；VPD是否依赖已知常值amb_e_sat的上游处理也未证实，不能把它看作独立湿度证据。未取得独立源区配对与位置基准，站点异常不能直接作为源区物理输入。

## 题面要求对照与后续使用

四类气象资料均有变量映射、特征、覆盖和异常；三套TOP5、主推荐、方向、留年/过程/窗口/锚点/质量敏感性均有真实计算。统计关联支线未启动：Q3审核包仍有0个接受的独立启动/暴露单位，不能把区域背景年当无灾标签。Q2/Q3先接收冻结feature_bundle及限制，正式物理输入和历史业务可用性另由主参谋审查。
