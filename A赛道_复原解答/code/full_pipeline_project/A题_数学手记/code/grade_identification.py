"""评分刻度的集合识别：只计算识别界与已有预测的顺序，不拟合新模型。

运行：python A题_数学手记/code/grade_identification.py
共同单调切点及本批七级全出现，都是额外假设，未由附件证实。
"""
from pathlib import Path
from fractions import Fraction
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parents[1]
RESULTS=WORK/"results"
FIGURES=WORK/"figures"
TARGETS=[f"Y{i:02d}" for i in range(1,51)]


def validated_anchors(anchors=()):
    """先全局检查，再求界；不能只检查query附近而漏掉远处矛盾。"""
    items=[]
    for position,grade in anchors:
        if not np.isfinite(float(position)):
            raise ValueError("真实锚点的位置必须是有限实数")
        if not np.isfinite(float(grade)) or int(grade)!=float(grade) or not 0<=int(grade)<=6:
            raise ValueError("真实锚点等级必须是0–6整数")
        items.append((Fraction(str(position)),int(grade)))
    items.sort()
    unique=[]
    for position,grade in items:
        if unique and position==unique[-1][0]:
            if grade!=unique[-1][1]:
                raise ValueError("相同位置的真实锚点等级冲突")
            continue
        if unique and grade<unique[-1][1]:
            raise ValueError("真实锚点等级随位置增加而下降，不满足共同非降校准假设")
        unique.append((position,grade))
    return unique


def grade_bounds(values,anchors=()):
    """在额外共同非降校准假设下的逐点紧界；并非置信区间。"""
    checked=validated_anchors(anchors)
    lower=[]
    upper=[]
    for value in np.asarray(values).reshape(-1):
        if not np.isfinite(float(value)):
            raise ValueError("被识别位置必须有限，缺失值不能静默进入证明")
        z=Fraction(str(value))
        lower.append(max([0]+[grade for position,grade in checked if position<=z]))
        upper.append(min([6]+[grade for position,grade in checked if position>=z]))
    return np.asarray(lower,dtype=int),np.asarray(upper,dtype=int)


def strict_threshold_witness(value,grade,anchors=()):
    """加入(z,k)后，在相邻锚点间放切点，返回六个精确有理数见证。

    使用Fraction不是做高精度拟合，而是防止狭小间隙里六个浮点切点
    被舍入成同一个数；有限实数锚点的数学证明不依赖浮点容差。
    """
    items=validated_anchors(list(anchors)+[(value,grade)])
    cuts=[]
    first,first_grade=items[0]
    cuts.extend(first-(first_grade-r+1) for r in range(1,first_grade+1))
    for (left,left_grade),(right,right_grade) in zip(items[:-1],items[1:]):
        count=right_grade-left_grade
        cuts.extend(left+Fraction(s,count+1)*(right-left) for s in range(1,count+1))
    last,last_grade=items[-1]
    cuts.extend(last+s for s in range(1,7-last_grade))
    return cuts


def critical_state(lower,upper):
    return np.select([np.asarray(upper)<=1,np.asarray(lower)>=2],["below_2_identified_under_assumption","at_least_2_identified_under_assumption"],default="unidentified")


def grade_identification_table(y):
    rows=[]
    column_summary=[]
    for target in TARGETS:
        values=y[target].to_numpy()
        lower,upper=grade_bounds(values)
        exact_values=[Fraction(str(value)) for value in values]
        distinct=sorted(set(exact_values))
        m=len(distinct)
        rank_by_value={value:rank for rank,value in enumerate(distinct,start=1)}
        ranks=np.asarray([rank_by_value[value] for value in exact_values],dtype=int)
        if m<7:
            raise ValueError(f"{target}少于7个不同值，额外ALL7假设不相容")
        all7_lower=np.maximum(0,6-(m-ranks))
        all7_upper=np.minimum(6,ranks-1)
        states=critical_state(all7_lower,all7_upper)
        for i,record in y.iterrows():
            rows.append({"object":int(record.object),"target":target,"observed_D04":float(values[i]),"observed_D04_serialized_decimal":str(values[i]),
                         "unconditional_domain_lower":0,"unconditional_domain_upper":6,
                         "common_monotone_ASSUMPTION_lower":int(lower[i]),
                         "common_monotone_ASSUMPTION_upper":int(upper[i]),
                         "common_monotone_ASSUMPTION_set_size":int(upper[i]-lower[i]+1),
                         "true_anchor_count":0,"distinct_value_count":m,"distinct_ascending_rank":int(ranks[i]),
                         "ALL7_ASSUMPTION_lower":int(all7_lower[i]),"ALL7_ASSUMPTION_upper":int(all7_upper[i]),
                         "ALL7_ASSUMPTION_set_size":int(all7_upper[i]-all7_lower[i]+1),
                         "ALL7_ASSUMPTION_grade_at_least_2_status":states[i],"is_critical_target_Y38":target=="Y38",
                         "status":"conditional identification, not original-grade recovery or probabilities"})
        size=all7_upper-all7_lower+1
        column_summary.append({"target":target,"n":len(values),"distinct_values":m,"true_anchor_count":0,
                               "base_common_monotone_set_size":7,"ALL7_ASSUMPTION_mean_set_size":float(size.mean()),
                               "ALL7_ASSUMPTION_rows_with_smaller_set":int((size<7).sum()),
                               "ALL7_ASSUMPTION_singleton_rows":int((size==1).sum()),
                               "ALL7_ASSUMPTION_threshold2_status_identified_rows":int((states!="unidentified").sum())})
    table=pd.DataFrame(rows)
    table.to_csv(RESULTS/"question1_grade_identification_bounds.csv",index=False)
    pd.DataFrame(column_summary).to_csv(RESULTS/"question1_grade_identification_summary.csv",index=False)
    # 对一个真实D04位置，输出7种严格切点见证。每行是一种数学可能性，
    # 不是7个模拟样本，也没有给这些可能性分配相等概率。
    value=str(y.iloc[0].Y38)
    witnesses=[]
    for grade in range(7):
        cuts=strict_threshold_witness(value,grade)
        z=Fraction(str(value))
        witnesses.append({"object":int(y.iloc[0].object),"target":"Y38","observed_D04":value,
                          "proposed_grade":grade,"grade_from_exact_witness":sum(z>=cut for cut in cuts),
                          **{f"strict_cut_{r+1}_exact_rational":str(cut) for r,cut in enumerate(cuts)},
                          "scope":"extra common strict-threshold calibration assumption; no true anchors"})
    pd.DataFrame(witnesses).to_csv(RESULTS/"question1_grade_identification_witnesses.csv",index=False)
    return table


def transfer_comparison():
    """读取已生成结果，严格比较CSV所表示的数；正的小数差也不算精确通过。"""
    configurations=[
        ("structure","original_D01_source","question3_structure_transfer_original_D01_source_profiles.csv","question3_structure_transfer_after_profiles_D04_scale.csv"),
        ("structure","reexpressed_candidate_relations_source","question3_structure_transfer_source_profiles_D04_scale.csv","question3_structure_transfer_after_profiles_D04_scale.csv"),
        ("structure","observed_source_D04","D04.csv","question3_structure_transfer_after_profiles_D04_scale.csv"),
        ("joint_control","original_D01_source","question3_transfer_before_profiles_D04_scale.csv","question3_transfer_after_profiles_D04_scale.csv"),
        ("joint_control","observed_source_D04","D04.csv","question3_transfer_after_profiles_D04_scale.csv")]
    guard_after="question3_observed_source_guard_after_profiles_D04_scale.csv"
    if (RESULTS/guard_after).exists():
        configurations.extend([
            ("observed_source_guard","original_D01_source","question3_observed_source_guard_original_source_profiles_D04_scale.csv",guard_after),
            ("observed_source_guard","reexpressed_candidate_relations_source","question3_observed_source_guard_reexpressed_source_profiles_D04_scale.csv",guard_after),
            ("observed_source_guard","observed_source_D04","D04.csv",guard_after)])
    rows=[]
    for branch,baseline,before_name,after_name in configurations:
        # 保留序列化的十进制文本，避免两个极近数先转float而被合并。
        after=pd.read_csv(RESULTS/after_name,dtype={target:str for target in TARGETS}).set_index("source_object")
        if before_name=="D04.csv":
            before=pd.read_csv(ROOT/"data/D04.csv",dtype={target:str for target in TARGETS}).set_index("object")
            before=before.reindex(after.index)
        else:
            before=pd.read_csv(RESULTS/before_name,dtype={target:str for target in TARGETS}).set_index("source_object")
        if before.index.duplicated().any() or after.index.duplicated().any() or set(before.index)!=set(after.index):
            raise ValueError("迁移前后source_object不唯一或不一致")
        after=after.reindex(before.index)
        for obj in before.index:
            for target in TARGETS:
                b=Fraction(str(before.loc[obj,target]))
                a=Fraction(str(after.loc[obj,target]))
                if a<b:
                    low,high=-6,0
                elif a==b:
                    low,high=0,0
                else:
                    low,high=0,6
                rows.append({"branch":branch,"baseline":baseline,"source_object":int(obj),"target":target,
                             "critical_target_Y38":target=="Y38","before_D04_value":float(b),
                             "before_value_kind":"observed_D04" if before_name=="D04.csv" else "model_prediction",
                             "after_D04_prediction":float(a),"after_minus_before":float(a-b),
                             "all_nondecreasing_maps_nonincrease_exact":a<=b,
                             "numeric_tolerance_1e_minus_8_pass":float(a-b)<=1e-8,
                             "numeric_tolerance_is_not_all_maps_certificate":a>b and float(a-b)<=1e-8,
                             "all_nondecreasing_maps_strict_improvement":False,
                             "common_monotone_ASSUMPTION_grade_delta_lower":low,
                             "common_monotone_ASSUMPTION_grade_delta_upper":high,
                             "true_K_nonworsening_identified":False,
                             "true_anchor_count":0,"scope":"same unknown nondecreasing map applied to recorded baseline value and fixed after prediction only"})
    frame=pd.DataFrame(rows)
    frame.to_csv(RESULTS/"question3_all_monotone_grade_comparison.csv",index=False)
    return frame


def plot_envelope(table):
    d=table[table.target=="Y38"].drop_duplicates("distinct_ascending_rank").sort_values("distinct_ascending_rank")
    rank=d.distinct_ascending_rank.to_numpy()
    lo=d.ALL7_ASSUMPTION_lower.to_numpy()
    hi=d.ALL7_ASSUMPTION_upper.to_numpy()
    fig,ax=plt.subplots(figsize=(11,4.4),dpi=160)
    ax.fill_between(rank,0,6,color="lightgray",alpha=.6,label="No anchors + common monotone calibration: [0,6]")
    ax.fill_between(rank,lo,hi,step="mid",color="#e9b65b",alpha=.65,label="EXTRA ASSUMPTION: all seven grades occur in this batch")
    ax.step(rank,lo,where="mid",color="#965817",lw=1.7)
    ax.step(rank,hi,where="mid",color="#965817",lw=1.7)
    ax.axhline(2,color="#245976",lw=1,ls="--",label="Critical grade 2; absolute scale remains unverified")
    ax.set(xlabel="Ascending rank of distinct observed Y38 values",ylabel="Possible grade under stated assumptions",ylim=(-.2,6.2),xlim=(1,len(d)))
    ax.set_yticks(range(7))
    ax.set_title("Identification envelopes, not confidence bands or recovered scores")
    ax.legend(loc="center",fontsize=8.3,framealpha=.95)
    fig.tight_layout()
    fig.savefig(FIGURES/"question1_grade_identification_envelope_Y38.png")
    plt.close(fig)


def main():
    RESULTS.mkdir(parents=True,exist_ok=True)
    FIGURES.mkdir(parents=True,exist_ok=True)
    y=pd.read_csv(ROOT/"data/D04.csv",dtype={target:str for target in TARGETS})
    row_summary=y[["object","object_id","regime"]].copy()
    row_summary["distinct_values_across_50_targets"]=[len({Fraction(value) for value in row}) for row in y[TARGETS].to_numpy()]
    row_summary["incompatible_with_single_rowwise_noiseless_affine_integer_grades"]=row_summary.distinct_values_across_50_targets>7
    row_summary.to_csv(RESULTS/"question1_grade_identification_row_summary.csv",index=False)
    table=grade_identification_table(y)
    transfer=transfer_comparison()
    plot_envelope(table)
    critical=transfer[transfer.critical_target_Y38]
    summary={"n_cells":len(table),"true_anchor_count":0,
             "unconditional_scope":"0..6 is only the defining grade domain; actual unknown standardization mechanism has not been characterized",
             "extra_common_monotone_calibration_assumption_verified":False,
             "common_monotone_ASSUMPTION_all_cells_set_size":7,
             "ALL7_batch_occupancy_assumption_verified":False,
             "ALL7_ASSUMPTION_mean_set_size":float(table.ALL7_ASSUMPTION_set_size.mean()),
             "ALL7_ASSUMPTION_cells_with_smaller_set":int((table.ALL7_ASSUMPTION_set_size<7).sum()),
             "ALL7_ASSUMPTION_singleton_cells":int((table.ALL7_ASSUMPTION_set_size==1).sum()),
             "ALL7_ASSUMPTION_threshold2_status_identified_cells_all_targets":int((table.ALL7_ASSUMPTION_grade_at_least_2_status!="unidentified").sum()),
             "ALL7_ASSUMPTION_Y38_critical_status_identified_rows":int(((table.target=="Y38")&(table.ALL7_ASSUMPTION_grade_at_least_2_status!="unidentified")).sum()),
             "rows_with_50_distinct_values":int((row_summary.distinct_values_across_50_targets==50).sum()),
             "observed_source_guard_branch_present":bool((transfer.branch=="observed_source_guard").any()),
             "transfer_Y38":[{"branch":branch,"baseline":baseline,"n":len(g),
                                "all_monotone_maps_exact_nonincrease_n":int(g.all_nondecreasing_maps_nonincrease_exact.sum()),
                                "largest_after_minus_before":float(g.after_minus_before.max())}
                               for (branch,baseline),g in critical.groupby(["branch","baseline"])],
             "warning":"Identified sets contain possibilities, not probabilities; no 1/7 accuracy claim, no true K safety claim, no model refit."}
    (RESULTS/"question1_grade_identification_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
