# -*- coding: utf-8 -*-
"""标签复原模块：把脱敏版（多通道测量数据）的编码标签映射回 A 题（啤酒）的真实变量名。

数据事实（已逐元素核验）：
- 多通道版 D01/D02/D04/D05/D06/D07 与原题 1/2/4/5/6/7.csv 的数值逐元素相同；
- 仅列名、类别名、评分维度名被替换为 V###/Y##/R##；
- 本模块只做“标签翻译”，不修改任何数值。

运行本文件可直接打印映射摘要，并做一次数值一致性抽查。
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

# 仓库根目录：A赛道_复原解答/code/labels.py -> parents[2]
ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "A赛道_复原解答"
RESULTS = WORK / "results"
FIGURES = WORK / "figures"
PAPER = WORK / "paper"
ORIG = ROOT / "03_A赛道" / "01_附件"          # 原题附件 1-8

# 脱敏题面与“砂箱解答”目录：优先使用同级目录；克隆仓库后使用本目录内置的完整计算工程
_SAND_PROB = ROOT / "多通道测量数据_研究题目"
_PIPE = WORK / "code" / "full_pipeline_project"
if _SAND_PROB.exists():
    SAND = _SAND_PROB
    SAND_SOL = SAND / "A题_数学手记"
else:
    SAND = _PIPE
    SAND_SOL = _PIPE / "A题_数学手记"

# 对照映射：仓库不提交“勿上传”目录，缺失时退回 results/参照表_*.csv
MAP = ROOT / "A题去生化_对照（勿上传）"

def _read_mapping(filename, local_name, rename):
    path = MAP / filename
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    local = pd.read_csv(RESULTS / local_name, encoding="utf-8-sig")
    return local.rename(columns=rename)

FEATURE_MAP = _read_mapping("映射_特征变量.csv", "参照表_化合物231.csv",
                            {"column_1csv": "original_name"})[["var_id", "original_name"]]
TARGET_MAP = _read_mapping("映射_评分维度.csv", "参照表_感官维度50.csv",
                           {"column_4csv": "original_name"})[["target_id", "original_name"]]
STYLE_MAP = _read_mapping("映射_类别.csv", "参照表_风格22.csv",
                          {"style": "original_style"})[["regime_id", "original_style"]]
TEMPLATE_MAP = _read_mapping("映射_模板项目.csv", "参照表_模板项目.csv", {})
TEMPLATE_MAP = TEMPLATE_MAP[["template_item", "label_cell", "score_cell", "target_id", "original_item"]]

V2NAME = dict(zip(FEATURE_MAP.var_id, FEATURE_MAP.original_name))
V2ID = {v: k for k, v in V2NAME.items()}
Y2NAME = dict(zip(TARGET_MAP.target_id, TARGET_MAP.original_name))
Y2ID = {v: k for k, v in Y2NAME.items()}
R2STYLE = dict(zip(STYLE_MAP.regime_id, STYLE_MAP.original_style))

# ---------------------------------------------------------------- 感官维度显示名
Y_DISPLAY = {
    "A_malt_all": "麦芽香·总体", "A_malt_grain": "麦芽香·谷物", "A_malt_bread": "麦芽香·面包皮",
    "A_malt_cara": "麦芽香·焦糖", "A_malt_burn": "麦芽香·烟熏焦苦",
    "A_hops_all": "酒花香·总体", "A_hops_citrus": "酒花香·柑橘", "A_hops_tropical": "酒花香·热带水果",
    "A_hops_noble": "酒花香·草本", "A_hops_woody": "酒花香·木质树脂",
    "A_esters_all": "酯香·总体", "A_esters_ethac": "酯香·溶剂", "A_esters_isoaa": "酯香·香蕉",
    "A_esters_flower": "酯香·花香", "A_esters_fruity": "酯香·甜果",
    "F_malt_all": "麦芽风味·总体", "F_malt_grain": "麦芽风味·谷物", "F_malt_bread": "麦芽风味·面包皮",
    "F_malt_cara": "麦芽风味·焦糖", "F_malt_burn": "麦芽风味·烟熏焦苦",
    "F_hops_all": "酒花风味·总体", "F_hops_citrus": "酒花风味·柑橘", "F_hops_tropical": "酒花风味·热带水果",
    "F_hops_noble": "酒花风味·草本", "F_hops_woody": "酒花风味·木质树脂",
    "F_esters_all": "酯风味·总体", "F_esters_ethac": "酯风味·溶剂", "F_esters_isoaa": "酯风味·香蕉",
    "F_esters_flower": "酯风味·花香", "F_esters_fruity": "酯风味·甜果",
    "acidity": "酸度", "bitternes": "苦度", "sweetness": "甜度", "X4vg": "4-乙烯基愈创木酚",
    "diacetyl": "双乙酰", "dms": "二甲基硫(DMS)", "metallic": "金属味", "stale_hops": "陈酒花味",
    "t2n": "反-2-壬烯醛", "orange": "橙味", "coriander": "芫荽", "clove": "丁香/茴香",
    "lactic": "乳酸味", "acetic": "乙酸味", "barnyard": "马厩味", "alcohol": "酒精感",
    "aftertaste": "余味", "body": "酒体", "co2": "碳酸感", "overall": "总体喜好",
}

def _block(y):
    name = Y2NAME[y]
    if name.startswith("A_"):
        return "香气(Aroma)"
    if name.startswith("F_"):
        return "风味(Flavour)"
    return "口感/缺陷/总体"

# ---------------------------------------------------------------- 化合物参考信息（8.xlsx）
def _fix_mojibake(s):
    if not isinstance(s, str):
        return s
    return (s.replace("Î²", "β").replace("Î±", "α").replace("Ã©", "é")
             .replace("Ã ", "à").replace("Â", ""))

def _norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())

def _row_info(row, name):
    pretty = _fix_mojibake(row["chemical_name_short"]) if pd.notna(row["chemical_name_short"]) else name
    return dict(
        original=name, pretty=str(pretty),
        origin=str(row["origin_paper"]) if pd.notna(row["origin_paper"]) else "",
        calibrated=str(row["calibrated"]) if pd.notna(row["calibrated"]) else "",
        unit=str(row["unit"]) if pd.notna(row["unit"]) else "",
        threshold_mean=float(row["threshold_mean"]) if pd.notna(row["threshold_mean"]) else np.nan,
        threshold_median=float(row["threshold_median"]) if pd.notna(row["threshold_median"]) else np.nan,
        aging=str(row["aging"]) if pd.notna(row["aging"]) else "",
        off_flavor=str(row["off_flavors"]) if pd.notna(row["off_flavors"]) else "",
    )


def build_feature_info():
    """V### -> dict(original, pretty, origin, unit, threshold_mean, ...)

    若存在“勿上传”目录，则按映射_变量参考表的行序与 8.xlsx 对齐（已核验逐行一致）；
    否则用列名/化学名做归一化匹配（克隆仓库后的独立运行方式）。
    """
    ref = pd.read_excel(ORIG / "8.xlsx", sheet_name="Sensory thresholds", header=0)
    info = {}
    ref_map_path = MAP / "映射_变量参考表.csv"
    if ref_map_path.exists():
        ref_map = pd.read_csv(ref_map_path, encoding="utf-8-sig")
        assert len(ref) == len(ref_map), (len(ref), len(ref_map))
        for i, row in ref.iterrows():
            vid = ref_map.iloc[i]["var_id"]
            if isinstance(vid, str) and vid.startswith("V"):
                info[vid] = _row_info(row, V2NAME[vid])
    else:
        row_by_key = {}
        for _, row in ref.iterrows():
            for col in ["field_name_R", "field_name_python", "chemical_name_short", "chemical_name"]:
                key = _norm(row[col]) if pd.notna(row[col]) else ""
                if key and key not in row_by_key:
                    row_by_key[key] = row
        for vid, name in V2NAME.items():
            row = row_by_key.get(_norm(name))
            if row is None:
                for _, cand in ref.iterrows():
                    if _norm(cand["chemical_name_short"]) == _norm(name):
                        row = cand
                        break
            info[vid] = _row_info(row, name) if row is not None else dict(
                original=name, pretty=_fix_mojibake(name), origin="", calibrated="",
                unit="", threshold_mean=np.nan, threshold_median=np.nan, aging="", off_flavor="")
    # 缺行兜底
    for vid, name in V2NAME.items():
        if vid not in info:
            info[vid] = dict(original=name, pretty=_fix_mojibake(name), origin="", calibrated="",
                             unit="", threshold_mean=np.nan, threshold_median=np.nan,
                             aging="", off_flavor="")
    return info


FEATURE_INFO = build_feature_info()

def build_target_info():
    sn = pd.read_excel(ORIG / "8.xlsx", sheet_name="Sensory names", header=0)
    clean = {str(r.R_name): (r.CleanName_Paper, r.Category_Paper, r.Category)
             for r in sn.itertuples() if pd.notna(r.R_name)}
    info = {}
    for y, name in Y2NAME.items():
        c = clean.get(name, (name, "", ""))
        info[y] = dict(original=name, display=Y_DISPLAY.get(name, name),
                       clean=str(c[0]) if pd.notna(c[0]) else name,
                       category=str(c[1]) if pd.notna(c[1]) else "",
                       block=_block(y))
    return info

TARGET_INFO = build_target_info()

# ---------------------------------------------------------------- 数据读取与一致性自检
def read_orig_chem():
    df = pd.read_csv(ORIG / "1.csv")
    meta = df.iloc[:, :3].rename(columns={"beer": "beer", "beer_id": "beer_id",
                                          "tasting_category_fine": "style"})
    return meta, df.iloc[:, 3:].copy()

def read_orig_sensory():
    df = pd.read_csv(ORIG / "4.csv")
    meta = df.iloc[:, :3].rename(columns={"beer": "beer", "beer_id": "beer_id",
                                          "tasting_category_fine": "style"})
    return meta, df.iloc[:, 3:].copy()

def read_sand_d01():
    return pd.read_csv(SAND / "data" / "D01.csv")

def read_sand_d04():
    return pd.read_csv(SAND / "data" / "D04.csv")

def check_identity():
    meta1, chem1 = read_orig_chem()
    d01 = read_sand_d01()
    ok1 = np.array_equal(chem1.values.astype(float), d01.iloc[:, 3:].values.astype(float),
                         equal_nan=True)
    _, sens = read_orig_sensory()
    d04 = read_sand_d04()
    ok4 = np.array_equal(sens.values.astype(float), d04.iloc[:, 3:].values.astype(float),
                         equal_nan=True)
    d02 = pd.read_csv(SAND / "data" / "D02.csv", index_col=0)
    o2 = pd.read_csv(ORIG / "2.csv", index_col=0)
    ok2 = np.array_equal(d02.values, o2.values, equal_nan=True)
    ok_v = list(FEATURE_MAP.original_name) == list(chem1.columns)
    ok_y = list(TARGET_MAP.original_name) == list(sens.columns)
    ok_r = bool((d01["regime"].map(R2STYLE).values == meta1["style"].values).all())
    return dict(chem=ok1, sensory=ok4, corr=ok2, feature_order=ok_v,
                target_order=ok_y, style_map=ok_r)

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("映射表：特征", len(V2NAME), "评分维度", len(Y2NAME), "类别", len(R2STYLE))
    print("一致性自检：", check_identity())
    print("\n前 10 个化合物：")
    for v in list(V2NAME)[:10]:
        i = FEATURE_INFO[v]
        print(f"{v} {i['original']:<32s} -> {i['pretty']:<28s} {i['origin']:<12s} {i['unit']:<5s} thr={i['threshold_mean']}")
    print("\n50 个感官维度显示名：")
    for y in list(Y2NAME):
        t = TARGET_INFO[y]
        print(y, f"{t['original']:<18s} -> {t['display']:<12s} {t['block']}")
