"""Local, read-only-source evidence transcription and arithmetic checks.

No fitting, model editing, download, dependency installation or event tuning.
The parent strength audit owns the canonical worksheet transcription.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ROOT = BASE.parents[3]
SOURCES = BASE / "sources/strength"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def item(path, role):
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=sha(path), role=role)


def write_json(path, obj):
    assert path.resolve().is_relative_to(HERE)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def write_csv(path, rows):
    assert path.resolve().is_relative_to(HERE)
    text = io.StringIO(newline="")
    w = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    path.write_text(text.getvalue())


def main():
    assert str(ROOT) == "/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2" and Path.cwd().resolve() == ROOT
    frozen_names = ["analytic_thermal_bundle.json", "composition_bundle.json", "mechanism_bundle.json", "mechanism_bundle_v2.json",
                    "numerical_supplement_bundle.json", "release_bundle.json", "release_bundle_v2.json"]
    frozen = [item(BASE/"exports"/name, "pre_existing_frozen_bundle") for name in frozen_names]
    register_path = SOURCES / "source_register.json"
    register = json.loads(register_path.read_text())
    originals = {r["source_id"]: r for r in register["sources"]}
    article = SOURCES / "mamot2018_article.pdf"
    supplement = SOURCES / "mamot2018_supplement.pdf"
    archive = SOURCES / "mamot2018_supplement.zip"
    assert sha(article) == "08662fb95d594e5a882957281aea00232918c1fa33f64c48748a2c9516670471"
    assert sha(supplement) == "4efee06535c2673304d5cb325bc03b0d24dec8f9eb86deedbb7cafe566f96bfe"
    assert sha(archive) == "5fcd735a88654af1f4c150313ee79afb855a0ae67ed9319a851d8e125fa420a0"
    with zipfile.ZipFile(archive) as z:
        zip_inventory = [dict(member=r.filename, uncompressed_bytes=r.file_size, crc32=f"{r.CRC:08x}") for r in z.infolist()]
        assert hashlib.sha256(z.read("Supplement/Supplement_Mamot et al.pdf")).hexdigest() == sha(supplement)
    # Actual visual reads by this reviewer, not inherited claims from old logs.
    article_pages = [5, 6, 7, 9, 10, 11, 12, 13, 14, 16]
    supplement_pages = [3, 4, 7, 8, 9, 10]
    visual = []
    for source, folder, stem, pages in [(article, "article_pages", "article", article_pages),
                                       (supplement, "supplement_pages", "supplement", supplement_pages)]:
        for number in pages:
            png = HERE/folder/f"{stem}-{number:02d}.png"
            visual.append(dict(source_path=source.relative_to(ROOT).as_posix(), source_sha256=sha(source),
                               pdf_page_one_based=number, printed_page=number+3332 if stem=="article" else number,
                               **item(png, "rendered_page_actually_opened_with_view_image"),
                               inspection="complete page opened; figure/table/body context and relevant footnotes inspected"))
    for unneeded in [HERE/"article_pages/article-15.png", HERE/"supplement_pages/supplement-05.png", HERE/"supplement_pages/supplement-06.png"]:
        if unneeded.exists():
            unneeded.unlink()  # only this reviewer's unneeded generated renders
    input_rows = [item(article,"article_pdf"), item(supplement,"supplement_pdf_extracted_from_official_zip"),
                  item(archive,"official_supplement_zip"), item(SOURCES/"mamot2018_article_extracted.txt","existing_article_text"),
                  item(SOURCES/"mamot2018_supplement_extracted.txt","existing_supplement_text"),
                  item(SOURCES/"mamot2018_table_s2_transcribed.csv","prior_tableS2_transcription_cross_checked_visually"),
                  item(register_path,"prior_retrieval_metadata_only")]
    audit = dict(review_version="q2-lab-strength-literature-v1", reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
                 evaluation_stratum="external_transfer", local_independent_event_count=0, network_requests=0,
                 model_runs=0, new_scientific_model_fits=0, source_reconstruction_probe="stage1_weight_probe.json;54closed-form source-only checks,not new model adoption", inputs=input_rows,
                 original_retrievals=[{k:originals[sid][k] for k in ["source_id","canonical_url_or_product_id","product_version","retrieved_at_utc","published_at_date"]}
                                     for sid in ["mamot2018_pdf","mamot2018_supplement_zip"]],
                 actual_text_read_scope={"article":"Sections2.2-2.4;3.2-3.5;4.1-4.3;4.5;Eq3-6;Fig6-9/11;Tables1-2; extracts of conclusion. Not full bibliography or all21pages read.",
                                         "supplement":"All10-page existing extracted text read; relevant FigS1/S2/S5-S8,TableS1/S2 visually checked on6 complete pages.",
                                         "zip":"25-member inventory and Supplement PDF hash matched; initial PDF review did not parse XLSX. Later bounded stage1_weight_probe independently read experiments Sheet1 D/E/F/G/L for141rows and coefficient Sheet1 two nominal-stress-domain blocks values/literal headers (Sheet2 parsed empty and unused),verified705rawfields against canonical audit and performed source-only reconstruction;canonical audit unchanged."},
                 actual_visual_pages=visual, zip_inventory=zip_inventory,
                 rendering_commands=["pdftoppm -f9 -l16 -r150 -png article.pdf literature/article_pages/article",
                                     "pdftoppm -f5 -l7 -r150 -png article.pdf literature/article_pages/article",
                                     "pdftoppm -f3 -l10 -r150 -png supplement.pdf literature/supplement_pages/supplement"],
                 renderer_status="all3 exit0; supplement renderer emitted fontconfig warning but actual opened page images were legible",
                 frozen_bundles=frozen)
    write_json(HERE/"literature_input_audit.json", audit)
    temperatures = [-10, -8, -6, -5, -4, -3, -2, -1, -.5]
    counts = {100:[5,5,5,6,5,5,4,4,4], 200:[4,4,4,6,5,5,6,5,1],
              400:[5,4,5,5,4,3,5,4,3], 800:[0,0,0,0,4,5,3,4,4]}
    design = [dict(nominal_normal_stress_kpa=stress, nominal_temperature_c=temp, trials=n,
                   performed=n>0, source="Supplement TableS1,PDFpage4")
              for stress, ns in counts.items() for temp,n in zip(temperatures,ns)]
    write_csv(HERE/"published_table_s1_design.csv", design)
    assert sum(r["trials"] for r in design) == 141
    low_keep = [-8,-5,-4,-2,-.5]
    low_holdout = [-10,-6,-3,-1]
    high_keep = [-4,-2,-1,-.5]
    n_low = sum(r["trials"] for r in design if r["nominal_normal_stress_kpa"]<=400)
    n_selected = sum(r["trials"] for r in design if r["nominal_normal_stress_kpa"]<=400 and r["nominal_temperature_c"] in low_keep)
    assert n_low == 121 and n_selected == 67
    # Rounded figure labels, not a new regression fit.
    fig6_low = [(-10,-10,.4,967.4,.70,.08,.34),(-8,-8,.1,655.5,1.57,.43,.01),
                (-6,-6.1,.2,783.6,1.29,.22,.09),(-5,-4.9,.2,347.9,1.79,.36,.01),
                (-4,-4.2,.2,313.9,2.02,.52,None),(-3,-3.1,.2,589.2,.23,.02,.61),
                (-2,-2.2,.2,285.2,.97,.35,.02),(-1,-1.1,.2,345.3,.17,.04,.49),
                (-.5,-.5,.1,86.,.49,.68,.01)]
    fig6_high = [(-4,-4.1,.2,601.3,.65,.25,.03),(-3,-3.1,.3,591.9,.21,.16,.10),
                 (-2,-2.2,.2,418.3,.38,.24,.04),(-1,-1.1,.2,320.4,.29,.39,None),
                 (-.5,-.5,.1,133.1,.25,.50,.01)]
    screens=[]
    for stress_scope, values, keep in [("100-400_nominal",fig6_low,low_keep),("100-800_nominal",fig6_high,high_keep)]:
        for nominal,actual,sd,c,mu,r2,p in values:
            screens.append(dict(stress_scope=stress_scope,nominal_temperature_c=nominal, actual_mean_temperature_c=actual,
                                reported_temperature_sd_c=sd,c_intercept_kpa=c,mu_slope=mu,r_squared=r2,
                                p_value=p,p_label="<0.01" if p is None else str(p),included_by_author_p_le_0p05=nominal in keep,
                                source="Article Fig6,PDFpage10;rounded display coefficients"))
    write_csv(HERE/"figure6_temperature_screen.csv", screens)
    relations=[]
    specs=[("eq6_lowstress_full","100-400_nominal",-8,-.5,"c",53.3,20.6,-73.5,8.8,.96,None),
           ("eq6_lowstress_full","100-400_nominal",-8,-.5,"mu",.42,.15,-.21,.06,.78,.05),
           ("fig7_green_lowstress_warm","100-400_nominal",-4,-.5,"c",49.4,39.1,-83.5,32.9,.87,.24),
           ("fig7_green_lowstress_warm","100-400_nominal",-4,-.5,"mu",.28,.08,-.38,.07,.97,.11),
           ("fig7_orange_highstress_warm","100-800_nominal",-4,-.5,"c",104.5,59.7,-143.8,42.5,.85,.08),
           ("fig7_orange_highstress_warm","100-800_nominal",-4,-.5,"mu",.19,.02,-.10,.02,.95,.02)]
    for relation,stress,lo,hi,param,inter,seinter,slope,seslope,r2,p in specs:
        relations.append(dict(relation_id=relation,normal_stress_scope=stress,temperature_lower_c=lo,temperature_upper_c=hi,
                              parameter=param,intercept=inter,reported_intercept_se=seinter,temperature_slope=slope,
                              reported_slope_se=seslope,r_squared=r2,p_value=p,p_label="<0.01" if p is None else str(p),
                              value_unit="kPa" if param=="c" else "dimensionless",source="Article Eq6/ Fig7,PDFpages10-11",
                              uncertainty_note="SE,not95pctCI;Eq6 c-slope SE8.8;Fig7 shows8.7;Fig9 more digits8.75" if relation=="eq6_lowstress_full" and param=="c" else "reported fitted coefficient standard errors; covariance not supplied here"))
    write_csv(HERE/"published_relations.csv", relations)
    totals=[(551.3,86.0,73.5),(1.58,75.0,.21),(257.3,74.1,83.5),(.74,58.3,.38),(503.3,74.1,143.8),(.35,59.3,.10)]
    consistency=[]
    for relation, published in zip(relations,totals):
        lo,hi=relation["temperature_lower_c"],relation["temperature_upper_c"]
        at_lo=relation["intercept"]+relation["temperature_slope"]*lo
        at_hi=relation["intercept"]+relation["temperature_slope"]*hi
        drop=at_lo-at_hi
        published_drop,published_percent,published_rate=published
        consistency.append(dict(relation_id=relation["relation_id"],parameter=relation["parameter"],
                                figure_fit_value_at_lower=at_lo,figure_fit_value_at_upper=at_hi,
                                figure_fit_total_drop=drop,figure_fit_percent_drop=100*drop/at_lo,
                                table2_total_drop=published_drop,table2_percent_drop=published_percent,
                                table2_per_degree_drop=published_rate,
                                table_total_minus_figure_fit_drop=published_drop-drop,
                                discrepancy_status="warm_lowstress_total_and_rate_columns_inconsistent" if "green" in relation["relation_id"] else "consistent_with_display_rounding",
                                source="Article Table2 PDFpage12 vs Fig7 PDFpage11; arithmetic only,no refit"))
    write_csv(HERE/"table2_consistency.csv",consistency)
    facts=dict(facts_version="q2-lab-literature-facts-v1", evaluation_stratum="external_transfer",
               publication="Mamot et al2018,The Cryosphere12:3333-3353,DOI10.5194/tc-12-3333-2018",
               experiment=dict(total_trials=141,physical_rock_pairs=7,independent_material_pairs_not_equal_to_trial_count=True,
                               nominal_stress_classes_kpa=[100,200,400,800], nominal_temperature_levels_c=temperatures,
                               table_s1_trials_by_stress={str(k):sum(v) for k,v in counts.items()},
                               observed_condition_cells=32,replicates_per_condition_min=1,replicates_per_condition_max=6,
                               single_replicate_condition="nominal200kPa,-0.5C", highstress800_trials=20,
                               highstress800_temperature_scope_c=[-4,-.5], highstress_cold_tests_present=False,
                               material="Triassic dolomised fine-grained Wetterstein limestone,porosity approx4.4pct;tap-water ice",
                               cylinder_diameter_mm=[148,1],cylinder_height_mm=[82,3],nominal_ice_thickness_mm=[3,1],
                               supplement_ice_thickness_range_mm=[1.5,4],grit_roughness_amplitude_mm=.185,
                               saturation_hours_min=72,freezing_hours_min=14,freezing_temperature_c=-14,
                               reported_mean_shear_speed_mm_min=[.7,.1],supplement_shear_speed_range_mm_min=[.3,1.],
                               reported_mean_strain_rate_s_inv=[4.8e-3,1.4e-3],reported_minimum_strain_rate_s_inv=1.58e-3,
                               nominal_min_speed_over_max_thickness_s_inv=.005/4,
                               min_rate_arithmetic_status="printed1.58e-3 differs from rounded0.005/4=1.25e-3;do not overwrite source,prefer actual trial values",
                               actual_measured_stress_class_mean_and_sd_kpa={"100":[106,8],"200":[210,8],"400":[419,22],"800":[828,16]},
                               stress_semantics="applied actual normal and shear stresses corrected for changing contact area;group inclusion uses nominal classes;no controlled pore-pressure validation"),
               derivation=dict(equation="tau_kpa=c(T)+mu(T)*sigma_lab_kpa",cohesion="tau-axis intercept at sigma0",friction="slope,mu=tan(phi),not phi degrees",
                               stage1="per-temperature peak tau vs actual sigma,Fig6;five selected lowstress temperature classes based on slope p<=0.05",
                               lowstress_temperature_classes_kept=low_keep,lowstress_temperature_classes_heldout=low_holdout,
                               lowstress_kept_trials_from_table_s1=n_selected,lowstress_heldout_trials_from_table_s1=n_low-n_selected,
                               warm_lowstress_selected_temperature_classes=[-4,-2,-.5],warm_lowstress_selected_trial_count=37,
                               warm_highstress_selected_temperature_classes=high_keep,warm_highstress_selected_trial_count=65,
                               weighting_ambiguity="Sect2.4 says predictor inverse variance;Fig7 caption says inverse squared standard errors;do not silently identify without checking coefficient workbook",
                               author_validation="temperature-layer holdout plus800 lab extrapolation;not independent local hazards or probability coverage",
                               eq6_reported_scope="nominal100-400kPa,-8..-0.5C;actual stresses depart from classes;rapid brittle limestone-ice joint tests"),
               publication_inconsistencies=[dict(id="table2_warm_lowstress",status="confirmed_visual_and_arithmetic",
                   claim="lowstress warm totals257.3kPa/.74 and74.1pct/58.3pct match broad Eq4/5 endpoints,while per-degree83.5/.38 andR2/p match green warm fit;do not combine columns into a fit",
                   author_intent="unknown;matching broad endpoints is arithmetic inference,not an author correction"),
                   dict(id="failure_figure_stress_counts",status="confirmed_display_discrepancy",
                   table_s1_counts=[43,40,38,20],supplement_figS8_display_counts=[43,41,37,20],stress_classes_kpa=[100,200,400,800],
                   resolution="canonical worksheet audit required;do not reassign a trial from display alone"),
                   dict(id="failure_figure_temperature_counts",status="confirmed_display_discrepancy",
                   nominal_minus5C_table_s1_count=17,figure8_display_count=16,figure8_all_display_count=140,
                   resolution="canonical worksheet audit required;do not infer excluded test or missing failure class"),
                   dict(id="rounding_and_minrate",status="minor_reporting_difference",note="Eq6 c slopeSE8.8,Fig7 8.7,Fig9 8.75;minimumstrainrate arithmetic mismatch also retained"),
                   dict(id="warm_green_cohesion_temperature_axis",status="independent_numeric_reconstruction",
                   nominal_temperature_inverse_response_error_squared_fit=[49.42855601457558,-83.52348550634723],
                   measured_mean_temperature_same_weight_fit=[49.76733087583959,-79.81312730607986],
                   interpretation="nominalT reproduces printed49.4-83.5T whereas actualmeanT doesnot;thisdoesnot proveuniqueauthorcode;see stage1_weight_probe.json")],
               failure_physics=dict(all800_samples_failed_by_fracturing=True,creep_transition_observed_here=False,
                                    observed_modes=["ice_internal","rock_ice_interface","composite"],
                                    near_minus0p5_only_interface_in_this_sample=True,
                                    highstress800_interface_fraction=.75,highstress800_pure_ice_fraction=0,
                                    mechanism_identification_limit="800 lacks coldtests;temperature/stress/failure-mode mix confounded. Enhanced pressure melting is author hypothesis,not directly demonstrated liquid pressure or a400kPa switch.",
                                    why800_not_merged_into_eq6=["onlywarmrange,-4..-0.5;lowstresscoverswholetemperaturedesign","higher-stress lower-than-linear peak strengths flatten slope/raise intercept","selectedtemperatureclasses anddegreesoffreedom change;distinct physical extrapolation question"],
                                    no_above_minus0p5_tests=True,rock_to_rock_transition_not_calibrated=True,
                                    local_material_transfer="author assumes broad rock similarity but also calls for additional rocktype/roughness/rate tests;not locally validated"),
               proposed_fitting_design=[dict(id="D0",role="immutable_external_baseline",form="publishedEq6;no refit",domain="nominal100-400,-8..-0.5C"),
                   dict(id="D1",role="transparent_reproduction_and_sensitivity",form="two-stage per-T MC then c(T),mu(T);report authorselected vs all121lowstress;OLS/WLS explicit",validation="temperatures held out;all screening repeated inside training if evaluating own prediction"),
                   dict(id="D2",role="new_pooled_comparator",form="tau=beta0+betaT*T+betaS*sigma+betaTS*T*sigma,all matched-range rawtrials;physical positivity andjointcovariance",validation="leave-temperature/condition/pair blocks where IDs permit;no randomrow-only claims"),
                   dict(id="D3",role="warm_highstress_challenger",form="common5warmT unfiltered paired comparison of<=400 vs800;optional fixed400hinge(T) with declaredidentifiability limits",validation="800 holdout directionalbias/MAD/RMSE andtemperaturegroups;400..800 breakpointnotestimatedfromonly800addedstress")],
               falsification_conditions=["Iflowstressfit systematically overpredicts800 under matched warmtemperature andactualsigma,do not extend singleMC slope without a challenger;thisalone doesnot identifycreep/melting.",
                   "If800deficits vanish after using actualsigma,units,temperaturematching,pair/cellblocking,highstressmechanismclaimweakens.",
                   "Ifrawresiduals trackstrainrate,icethickness,roughness/pair identity orfailuremode,stress/temperature-only fit lacks sufficiency.",
                   "Ifheldout-T errors orcoefficients are unstable/negative/physicallyinadmissible,do not call broaderparametricfit validated.",
                   "No800colddata,no>800data,noT>-.5data andnoslowratecreep tests:corresponding extrapolations remain falsifiable unknowns."],
               source_reconstruction_addendum=dict(file="stage1_weight_probe.json",role="independent source-only check,no new model choice",
                   stage1_candidates=3,stage1_records_including_unavailable=42,stage2_axis_checks=12,
                   individual_ols_matches_12_of_14=True,both_minus0p5_layers_unreproduced=True,
                   source_error_header_remains_untyped=True,numeric_correspondence_to_ols_se_not_header_definition=True),
               boundaries=dict(local_stress_used_for_tuning=False,local_time_used_for_tuning=False,model_modified=False,canonical_raw_audit_owned_by_other_strength_agent=True,
                               statistical_prior_created=False,local_independent_events=0,human_scientific_adoption="pending_team_review"))
    write_json(HERE/"literature_facts.json",facts)
    report="""# Mamot2018 原文与补充材料独立核查

主体工作核文献、转录公开图式并做算术核对；后按主参谋追加要求，以闭式回归核查作者14组来源摘要及温度轴，详见`STAGE1_WEIGHT_NOTE.md`。没有新模型选择、运行机制模型、修改源数据或使用本地应力/事件时刻。原始试验表的规范审计由另一强度审计窗负责。来源、实际阅读页、PNG哈希和原七包哈希见`literature_input_audit.json`。

## 可直接采用的证据

Eq6为`τ=σ(0.42−0.21T)+(53.3−73.5T)`，τ/σ/c单位kPa，T单位°C，μ是tanφ而非角度。作者先按温层拟合τ对σ，再只保留斜率p≤.05的温层−8/−5/−4/−2/−.5，拟合c(T)、μ(T)。有效声明为名义100–400kPa、−8至−.5°C；按S1这5温层67次试验，另4温层54次用于作者留出检验。800kPa另20次，温度仅−4至−.5°C，未并入Eq6主拟合。

**按名义应力类筛样本、用实测σ回归。** S5组均值分别106±8、210±8、419±22、828±16kPa；σ/τ按变化接触面积修正。直接删掉实测σ>400的行会错误删除400类有效试验。试验没有对现场孔压有效应力替换作验证。

141是试验次数，只有7对石灰岩圆柱，全文保留配对和方向；每个应力×温度格1–6次，−.5°C/200kPa仅1次。冰层3±1mm（补充范围1.5–4mm）、标准粗糙度约.185mm。平均速度.7±.1mm/min，平均应变率(4.8±1.4)e−3s−1；这是最终快速脆断实验，不是慢蠕变参数。最小应变率印为1.58e−3s−1，但文字所列.005mm/s÷4mm为1.25e−3，不能擅改源值，需回逐试验记录。

## 暖域关系与不能合并的图表

Fig7绿线（≤400、−4至−.5）为c=49.4−83.5T、μ=.28−.38T；只含−4/−2/−.5三个显著温层，温度斜率p=.24/.11。橙线（100–800同暖域）为c=104.5−143.8T、μ=.19−.10T；保留−4/−2/−1/−.5四温层，p=.08/.02。新增800使−1温层通过第一阶段筛选，因此两条暖拟合连温层集合也不相同。不能把系数变化全部归因高应力效应，也不能把橙线当Eq6已经验证的全温高应力延长。

**Table2的≤400暖域行内部不自洽。** c总降257.3、μ总降.74及74.1%/58.3%等于宽域Eq4/5在−4与−.5的端点差；每°C83.5/.38及R²/p却对应Fig7绿线。绿线自身端点总降应为292.25kPa、1.33。这里只确认算术关系，作者意图未知，不自行勘误。橙线总降503.3kPa/.35与斜率143.8/.10相符。正文权重称predictor逆方差，Fig7 caption称逆SE²，复现必须写清阶段和SE列并比较OLS/WLS，不能默称唯一无歧义流程。±数值是系数SE语境，没有给出完整协方差，不能直接当95%预测区间或独立先验。

另有图示计数差：S1各σ类43/40/38/20，S8图字43/41/37/20；Fig8的−5°C为16而S1为17、图示总数140。应交原始worksheet核对，不能凭图给某行改类或删除。Eq6斜率SE在Eq6/Fig7/Fig9分别8.8/8.7/8.75属显示精度差，亦保留来源级别。

追加独立核查：逐试验OLS复现14组来源系数中的12组；应力格均值OLS为0/14，格均值逆σ方差WLS为0/12、2组因单例方差未知不计算。两组−.5°C来源系数未精确重现，不删行或补值。工作簿只写`_error`，即使12组系数误差数值等于OLS SE，也保留字面未定型语义。暖绿c在名义温度轴/逆来源response_error²下为49.4286−83.5235T，实测温度均值轴下为49.7673−79.8131T；前者重现印刷式，不能据此宣称作者全流程唯一已知。

## 机制边界与拟合建议

800kPa样本**全都仍以断裂失效**；本研究没有直接观测400以上必然转蠕变。作者提出暖高压下压力融化降低摩擦的解释，但800缺冷温试验，界面失效占比75%且纯冰断裂为0的对比受温度设计混杂。−.5°C以上未测，岩–岩转接与c=0后的摩擦未被本表校准。

建议并列：D0保留作者Eq6；D1明确两阶段、选层/全层与OLS/WLS复现；D2用完整逐试验τ~T+σ+Tσ作低复杂度共同域比较；D3仅暖共同5温层检查≤400外推800的有向残差与备选高应力关系。可预设400铰链作挑战，但只有额外800一个水平，不足反演真实转折应力。使用actualσ、温度/条件分组留出，若物理试件ID可追踪再做配对分组；p筛选也应留在训练折内。不要把141个重复制样试验当141个独立材料或事件，不以本地失稳时刻挑系数。

反证条件：匹配温度、实测σ、单位和试件/条件后800仍系统低于低应力外推，可反对统一线性包络，但不能单独证明融化或蠕变；若偏差被速率、冰厚或试件效应解释，则高应力机制主张减弱。冷800、>800、>−.5°C或慢应变率均无试验覆盖；这些边界保持未知。拟合优劣和物理适用性分别报告，最终科学采用待队员审视。
"""
    (HERE/"EVIDENCE_REVIEW.md").write_text(report)
    assert [item(BASE/"exports"/name,"pre_existing_frozen_bundle") for name in frozen_names] == frozen
    outputs=[item(p,"literature_review_output") for p in sorted(HERE.rglob("*")) if p.is_file() and p.name!="literature_output_manifest.json" and "__pycache__" not in p.parts]
    write_json(HERE/"literature_output_manifest.json",dict(output_files=outputs,self_entry_excluded=True,
                                                         frozen_bundles_unchanged=True,write_scope=HERE.relative_to(ROOT).as_posix()))
    print(json.dumps(dict(total_trials=141,lowstress_trials=n_low,author_eq6_selected_trials=n_selected,
                          visual_pages_actually_opened=len(visual),frozen_bundles_unchanged=7,
                          facts_sha256=sha(HERE/"literature_facts.json"),report_sha256=sha(HERE/"EVIDENCE_REVIEW.md"))))


if __name__ == "__main__":
    main()
