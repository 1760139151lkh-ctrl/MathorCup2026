"""由题目数据支持的五个派生关系候选；不冒充提供者给出的官方定义。

native_frame 中 V001–V036 是参照原生量，保留零和负值；
V038–V227 仍采用 D01 已观察刻度，其中 V229 的六个来源已核验为原生刻度。
调用者必须另外处理真实缺失，并从训练数据拟合非正值替代下限。
"""
import numpy as np
import pandas as pd

CANDIDATE_COEFFICIENTS = {
    'V037': {'V027':0.0003, 'V031':0.4, 'V033':0.4, 'V034':5.523, 'V036':0.4},
    'V228': {'V006':1/23, 'V007':1/1.035, 'V008':1/0.225, 'V009':1/0.1,
             'V010':1/0.75, 'V011':1/10, 'V016':1/0.6, 'V019':1/1.29},
    'V229': {'V164':1/0.625, 'V118':1/1.5, 'V155':1/0.23,
             'V121':1/0.0245, 'V128':1/0.023, 'V095':1/0.0045},
    'V230': {'V023':1/0.145, 'V027':1/400},
    'V231': {'V002':1/50, 'V003':1/1.2, 'V004':1/19, 'V012':1/3.5, 'V022':1/11},
}
LOG_FEATURES = [f'V{i:03d}' for i in range(1,38)]
DERIVED_FEATURES = list(CANDIDATE_COEFFICIENTS)


def candidate_derived_from_native(native_frame):
    """返回五列原生聚合值；任何来源缺失时该聚合仍缺失，不偷偷当作0。"""
    result = pd.DataFrame(index=native_frame.index)
    for target, coefficients in CANDIDATE_COEFFICIENTS.items():
        source = list(coefficients)
        values = native_frame[source].mul(pd.Series(coefficients),axis=1)
        result[target] = values.sum(axis=1,min_count=len(source))
    return result


def fit_positive_floors(native_training_frame):
    """已观察原生训练值中每列最小正值的一半。

    请给原生参照的训练行；不能拿10^D01补出的未知原生值或生成样本重估。
    尤其缺参照的下限记录若被当成新正数，会让替代下限被错误地再次减半。
    """
    floors = {}
    frame = native_training_frame.copy()
    coefficients=CANDIDATE_COEFFICIENTS['V037']
    frame['V037']=frame[list(coefficients)].mul(pd.Series(coefficients),axis=1).sum(axis=1,min_count=len(coefficients))
    for var in LOG_FEATURES:
        positive = frame.loc[frame[var]>0,var]
        if positive.empty:
            raise ValueError(f'{var}训练数据没有正值，无法拟合替代下限')
        floors[var] = float(positive.min()/2)
    return floors


def native_to_recorded(native_frame, floors, recalculate_derived=True):
    """按本题已核验规则回到D01刻度，保留其他列与真实缺失。

    五个候选聚合需为正，才能取log10；若生成产生非正聚合则报错，
    由调用者修复或重采样，避免把无效聚合悄悄截断后宣称结构一致。
    """
    frame = native_frame.copy()
    if recalculate_derived:
        derived = candidate_derived_from_native(frame)
        for var in DERIVED_FEATURES:
            if (derived[var].dropna()<=0).any():
                raise ValueError(f'{var}候选聚合出现非正值，无法生成有效对数')
            frame[var] = derived[var]
    for var in LOG_FEATURES:
        if var not in floors or not np.isfinite(floors[var]) or floors[var]<=0:
            raise ValueError(f'{var}缺少有效训练替代下限')
        observed = frame[var].notna()
        q = frame[var].where(frame[var]>0,floors[var]).where(observed)
        frame[var] = np.log10(q)
    for var in DERIVED_FEATURES:
        if var!='V037':
            if (frame[var].dropna()<=0).any():
                raise ValueError(f'{var}原生聚合出现非正值，无法转换为有效对数')
            frame[var] = np.log10(frame[var])
    return frame
