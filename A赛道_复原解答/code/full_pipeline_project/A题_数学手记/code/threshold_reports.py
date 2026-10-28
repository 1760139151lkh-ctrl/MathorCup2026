"""用D08完整精度统一临界比值与W1归一化，不重训或改变迁移向量。"""
from pathlib import Path
import pandas as pd
import generation

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[1] / 'results'


def main():
    reference = pd.read_excel(ROOT / 'data/D08.xlsx', sheet_name='var_reference').set_index('var_id')
    thresholds = {v: float(reference.loc[v, 'threshold_mean']) for v in ('V004', 'V039', 'V021')}
    thresholds['V109'] = 0.35  # 题面补充，不假装来自原表的空单元格。
    configurations = [
        ('question3_transfer_critical_comparison.csv', 'before_native', 'after_native_candidate', 'before_ratio'),
        ('question3_structure_transfer_critical_comparison.csv', 'source_native', 'after_native', 'source_ratio'),
        ('question3_observed_source_guard_critical_comparison.csv', 'source_native', 'after_native', 'source_ratio'),
    ]
    for filename, before, after, before_ratio in configurations:
        table = pd.read_csv(RESULTS / filename)
        for feature, threshold in thresholds.items():
            rows = table['criterion'].eq(feature)
            table.loc[rows, 'threshold'] = threshold
            table.loc[rows, before_ratio] = table.loc[rows, before] / threshold
            table.loc[rows, 'after_ratio'] = table.loc[rows, after] / threshold
        table.to_csv(RESULTS / filename, index=False)

    # 原生W1与非增条件不变；只有除以阈值时要使用同一完整精度。
    bounds = generation.feasibility_bounds(pd.read_csv(RESULTS / 'question3_tail_compatibility.csv'))
    for feature, threshold in thresholds.items():
        rows = bounds['feature'].eq(feature)
        bounds.loc[rows, 'critical_threshold_native'] = threshold
        bounds.loc[rows, 'W1_bound_divided_by_critical_threshold'] = bounds.loc[rows, 'native_W1_lower_bound'] / threshold
    bounds.to_csv(RESULTS / 'question3_feasibility_bounds.csv', index=False)
    pd.DataFrame([{'feature': v, 'threshold_native': t,
                   'source': 'problem supplement' if v == 'V109' else 'D08.var_reference.threshold_mean'}
                  for v, t in thresholds.items()]).to_csv(RESULTS / 'question3_critical_thresholds_used.csv', index=False)
    print('Critical reports use D08 full precision; C3 =', thresholds['V021'])


if __name__ == '__main__':
    main()
