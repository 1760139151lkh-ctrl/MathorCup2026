"""按数据依赖顺序重现本题科研计算，不依赖Codex或当前工作目录。

从项目根目录运行：python A题_数学手记/code/run_all.py
原始data只读，所有产物写入A题_数学手记。
"""
import sys
import pandas as pd
from threadpoolctl import threadpool_limits
import data_audit
import derived_search
import prediction
import network_analysis
import generation
import structure_generation
import scoring_protocols
import grade_identification
import threshold_reports


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    # 各脚本本身也能单独运行；这里仅表达前后依赖，避免复制数学逻辑。
    # 限制底层线程，防止小矩阵计算因过度并行反而变慢。
    with threadpool_limits(limits=2):
        data_audit.main()
        derived_search.main()
        prediction.main()
        grade_table = pd.read_csv(prediction.RESULTS / 'question1_working_grades_ASSUMPTION.csv')
        prediction.write_cards(grade_table[prediction.TARGETS], grade_table['object'].to_numpy())
        network_analysis.main()
        generation.main()
        structure_generation.run_structure()
        scoring_protocols.main()
        grade_identification.main()
        threshold_reports.main()


if __name__ == '__main__':
    main()
