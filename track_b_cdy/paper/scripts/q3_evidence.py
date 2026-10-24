#!/usr/bin/env python3
"""Assemble/check Q3 paper evidence from frozen results; never fit or rerun models."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT/'track_b/paper'
EVIDENCE = PAPER/'evidence'
R = ROOT/'track_b/research/q3/round3'


def read(path):
    return json.loads(path.read_text())


def file_record(path):
    return {'path': path.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def source_records(*values):
    """Deduplicate repository-relative references found in nested audit records."""
    found = {}
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and 'sha256' in value:
                path = value['path']
                if path.startswith('track_b/'):
                    record = {'path': path, 'sha256': value['sha256']}
                    if path in found:
                        assert found[path] == record, path
                    found[path] = record
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for value in values:
        visit(value)
    return sorted(found.values(), key=lambda v: v['path'])


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def build():
    a, b, c = [read(EVIDENCE/f'q3_{name}_audit.json') for name in 'abc']
    figures = read(EVIDENCE/'q3_figure_data.json')
    claims = []
    def claim(identifier, statement, value, unit, sources, model, scenario, scope, anchor):
        assert sources, identifier
        claims.append({'claim_id': identifier, 'statement': statement, 'value': value,
                       'unit': unit, 'source_files': source_records(sources),
                       'model_id': model, 'scenario_id': scenario,
                       'scope': scope, 'paper_anchor': anchor})

    anchors = {'q3-a-design':'q3:sec:models', 'q3-a-fixed-bounds':'q3:eq:bounds',
               'q3-a-history-risk':'q3:eq:bounds',
               'q3-a-extrapolation-support':'q3:sec:models',
               'q3-a-weather-response':'q3:sec:models'}
    for item in a['claims']:
        copy = dict(item)
        copy['paper_anchor'] = anchors[item['claim_id']]
        copy['source_files'] = source_records(item['source_files'])
        claims.append(copy)
    claim('q3-a-clock-and-availability',
          '75个发布时刻各含8条假设延迟轨、1条理想轨、1条严格首发轨；严格历史首发时刻未知。',
          a['design'], 'count; UTC; h', a['source_files'],
          'A_analytic_erfc_fixed_history', 'GFS_three_18Z_cycles',
          '10是候选信息轨数；包含拒用/未知轨，非10条完整实际可用GFS轨。', 'q3:sec:models')
    claim('q3-a-firstpass-and-domain', '逐小时首次非正、线性插值、完整实际随访域诊断与固定历史风险信息界。',
          [x for x in a['formulas'] if x['formula_id'] in
           {'q3-a-first-crossing','q3-a-fixed-domain','q3-a-event-partition'}],
          'h; kPa; degC; dimensionless', a['formulas'],
          'A_analytic_erfc_fixed_history', 'delivered_2048_design_ensemble',
          '域外或随访不足转为未知；历史已启动分类保持。', 'q3:eq:firstpass')
    claim('q3-local-independent-initiation-labels', '本地首次机械启动的独立验证事件为0。',
          {'independent_local_first_mechanical_validation_events': 0},
          'physical_event', a['source_files'], 'A_analytic_erfc_fixed_history', 'local_source',
          '外部终末失稳标签不替代本地首次机械启动真值。', 'q3:sec:design')
    claim('q3-b-estimator-and-uncertainty',
          'OLS/局部趋势SS使用发布前数据，512次当前联合估计抽样；SS不另模拟未来过程噪声。',
          {'formulas': b['model_formulas'], 'sampling': b['sampling_and_abstention']},
          'h; inverse_normalized_deformation_rate', b['source_files'],
          ['B_IV','B_SS'], 'causal_terminal_collapse_forecast',
          '归一逆速度5点速率/16点拟合；Weissmiess为直接给定速率；截断当前逆速度正值。', 'q3:eq:deformation')
    claim('q3-b-fixed-cutoff-coverage',
          '在标签下界前24小时发布H72，完整覆盖/相交的机会分母保留全部13失稳组。',
          [x for x in b['fixed_lower_minus24h_table_24_48_72'] if x['horizon_hours']==72],
          'count; h', b['source_files'], ['B_IV','B_SS'],
          'label_lower_minus24h_H72_primary_sensor',
          '点误差为中位预测到标签区间距离；其跨组中位数仅基于有限点7/8组。', 'q3:tab:coverage')
    claim('q3-b-two-first-alert-definitions',
          '72小时滚动规则将首个时域内正确告警与首个任意告警分别汇总。',
          [x for x in b['rolling_lead_and_alert_table']
           if x['horizon_hours']==72 and x['evaluation_set']=='hourly'],
          'physical_group; h', b['source_files'], ['B_IV','B_SS'],
          'retrospective_last30days_hourly_p72_ge0.5',
          '13个预先选择失稳病例；提前量中位数的分母为各自有告警组，Brienz组内取最早。', 'q3:tab:lead')
    claim('q3-b-publication-scale-sensitivity',
          '同10物理组内比较小时发布与最后48小时原生发布，改变了观测时期及发布尺度。',
          [x for x in b['paired_same10groups_table_24_48_72'] if x['horizon_hours'] in [48,72]],
          'dimensionless_Brier', b['source_files'], ['B_IV','B_SS'],
          'same10groups_hourly_vs_native_last48',
          '不是只改变采样频率的受控实验；不把不同有效组分数直接排名。', 'q3:sec:results')
    claim('q3-c-exposure-and-group-denominators',
          'C使用13个终末失稳组、1个真实删失组，确知生存暴露56381.84小时。',
          c['dataset_and_exposure'], 'physical_group; h; daily_record',
          c['dataset_and_exposure'], 'nonlinear_rbf_hazard_no_record_age_raw',
          'external_terminal_collapse_LOSO',
          'Stampa725日属1个物理过程；56526.19小时上界含144.35小时标签不确定性，不全是生存暴露。', 'q3:sec:design')
    claim('q3-c-likelihood-and-fit',
          '无记录年龄RBF的10维基、分段指数风险及区间/删失似然在嵌套留组中拟合。',
          {'formulas':c['formula_tex_suggestions'], 'fitting_protocol': c['fitting_protocol'],
           'publication_scales':c['publication_and_result_scales']},
          'hazard_per_h; h', c['source_files'],
          'nonlinear_rbf_hazard_no_record_age_raw', 'external_terminal_collapse_LOSO',
          '预测固定最后发布前特征；记录年龄支线只作诊断；不是每小时完整C回放。', 'q3:eq:hazard')
    claim('q3-c-original10-known-scores',
          '原C锚点RBF raw的48/72小时分数用10个已知结局组计算。',
          [x for x in c['original_fixed_anchor_table_all_four_C_branches']
           if x.get('model_id')=='nonlinear_rbf_hazard_no_record_age_raw'],
          'dimensionless_Brier; physical_group', c['source_files'],
          'nonlinear_rbf_hazard_no_record_age_raw', 'original_C_predefined_anchors',
          '与B/C共同有效8组分数使用不同分母；原锚点回顾选取。', 'q3:sec:results')
    claim('q3-common-anchor-probability-comparison',
          'SS与无年龄RBF raw按同传感器/同锚点/同H配对，n分别为5/8/8。',
          c['fair_BSS_vs_C_same_issued_known_opportunities'],
          'dimensionless_Brier; physical_group', c['fair_BSS_vs_C_same_issued_known_opportunities'],
          ['B_SS','nonlinear_rbf_hazard_no_record_age_raw'], 'common_anchors_no_age',
          '总14物理组，回顾锚点followup_end-H；两模型都发布且结局已知才进入配对，弃权为空。', 'q3:tab:brier')
    claim('q3-conditional-interval-and-label-boundary',
          '模型条件中央95%区间、完整标签包含和标签相交是不同量；共同锚点的标签上界可能正好等于H。',
          c['coverage_and_conditional_interval_interpretation'],
          'h; count', c['source_files'], ['B_SS','nonlinear_rbf_hazard_no_record_age_raw'],
          'common_anchors_no_age',
          '连续条件分布97.5%分位小于H会使该锚点完整包含为0；不同于固定标签下界前24小时协议。', 'q3:eq:interval')
    claim('q3-conformal-rank-feasibility',
          'C另留独立校准组为0；乐观上界13组的95%秩14超出样本数。B实际留一12组的秩13同样超出。',
          {'C':c['conformal'], 'B':b['conformal']}, 'physical_group; rank',
          source_records(c['conformal'], b['source_files']),
          ['B_IV','B_SS','nonlinear_rbf_hazard_no_record_age_raw'], 'rank_feasibility_only',
          'C未计算独立共形分数或有限端点；无界是秩可行性状态，非已验证覆盖。', 'q3:sec:results')
    claim('q3-c-grid-sensitivity',
          '512与1024节点保持同一物理样本；RBF raw锚点最大概率变化0.01041154。',
          c['numerical_grid_512_1024'], 'absolute_probability; dimensionless_Brier',
          c['numerical_grid_512_1024'], 'nonlinear_rbf_hazard_no_record_age_raw',
          'same_data_512_vs_1024',
          '48/72小时Brier变化0.00295944/0.00214720；是数值敏感性，不是独立复现样本。', 'q3:sec:models')

    propagation_summary = read(R/'results/final_propagation_v4/summary.json')
    propagation_sources = [file_record(R/'results/final_propagation_v4'/name)
                           for name in ['summary.json','conditional_arrivals_49.csv','mapped_runs_7.csv','input_manifest.json']]
    claim('q3-release-clock-and-49-target-records',
          '同base有7个运行、4个设计、49条目标响应；未知启动至整体释放时延使绝对到达及到达概率为空。',
          {'summary':propagation_summary, 'junction_records':figures['release_response']},
          's; UTC; target_record', propagation_sources,
          'Q2_base_mapped_to_Q4_release_response', 'seven_runs_four_designs',
          'p0000/p0072仅给定释放；p0255全历史首跨阈与评价窗左删失分列；不是7个独立灾害。', 'q3:eq:arrival')
    claim('q3-release-support-footprints',
          '同体积全源面p0036的120/60米足迹面积为23.0112/12.1608平方千米，支撑距离11.554/10.841千米。',
          figures['footprints'], 'km2; km; m; s', figures['source_files'],
          'frozen_release_response', 'h_ge0.1_saved_frames_requested1800s',
          '距离从实际正释放栅格足迹计算；非河程、质心半径或已验证预警距离。', 'q3:fig:release')
    claim('q3-paper-figure-inputs',
          '两张论文图均由冻结R3结果重绘，发布概率信息界与外部评分使用不同证据对象。',
          {'selection':figures['information_bound_selection'],
           'information_bounds':figures['information_bounds'],
           'paired_scores':figures['paired_scores'], 'figures':figures['figures']},
          'probability; dimensionless_Brier', figures['source_files'],
          ['A_analytic_erfc_fixed_history','B_SS','nonlinear_rbf_hazard_no_record_age_raw'],
          'paper_only_redraw', '图1阴影为条件于原历史风险集的信息界，不是95%置信区间。', 'q3:fig:information')
    assert all(item['value'] not in [None, []] for item in claims)
    write(EVIDENCE/'q3_claims.json', claims)

    codes = {}
    for item in a['self_authored_code_files']+b['self_authored_code_files']+c['actual_code_files']:
        codes[item['path']] = dict(item)
    for name, role in [
        ('final_propagation_v4.py','join/check frozen seven-run conditional target response'),
        ('join_propagation.py','first conditional propagation join'),
        ('join_propagation_v2.py','compact/base parameter handoff'),
        ('join_propagation_v3.py','full source-mask join')]:
        path = R/'scripts'/name
        codes[path.relative_to(ROOT).as_posix()] = {**file_record(path), 'role':role}
    for path in sorted((PAPER/'scripts').glob('q3_*.py')):
        codes[path.relative_to(ROOT).as_posix()] = {**file_record(path),
            'role':'paper plotting, preview compilation or evidence assembly; no model refit'}
    write(EVIDENCE/'q3_code_files.json', {
        'authorship':'团队自编模型、后处理及论文程序，OpenAI Codex辅助；采用决定由队员审阅。',
        'rerun_for_paper':'仅绘图、证据复核和LaTeX编译；冻结模型不重跑。',
        'files':sorted(codes.values(), key=lambda value:value['path']),
        'third_party_solver_note':'传播求解器归Q4维护；此清单只收Q3映射、核对和后处理，不把第三方求解器列为自编。'})
    cited = set()
    for group in re.findall(r'\\cite\{([^}]+)\}', (PAPER/'sections/q3.tex').read_text()):
        cited.update(group.split(','))
    references = a['references']+b['references']+c['primary_references_checked']
    selected_references = [v for v in references if v['key'] in cited]
    assert {v['key'] for v in selected_references} == cited
    write(EVIDENCE/'q3_reference_reading.json', {
        'policy':'仅登记正文实际引用来源；阅读范围按实际HTML/摘要/原文或元数据区别。',
        'references':selected_references})


def check():
    claims = read(EVIDENCE/'q3_claims.json')
    codes = read(EVIDENCE/'q3_code_files.json')
    figure_data = read(EVIDENCE/'q3_figure_data.json')
    audited_sources = source_records(claims, codes, figure_data)
    for record in audited_sources:
        path = ROOT/record['path']
        assert path.is_file(), record['path']
        assert file_record(path)['sha256']==record['sha256'], record['path']
    required = {'claim_id','statement','value','unit','source_files','model_id','scenario_id','scope','paper_anchor'}
    assert all(required <= value.keys() and value['source_files'] for value in claims)
    text = (PAPER/'sections/q3.tex').read_text()
    assert not [c for c in text if ord(c)<32 and c not in '\n\r']
    labels = re.findall(r'\\label\{([^}]+)\}',text)
    assert len(labels)==len(set(labels)) and all(value.startswith('q3:') for value in labels)
    assert all(value['paper_anchor'] in labels for value in claims)
    cited = {key for group in re.findall(r'\\cite\{([^}]+)\}',text) for key in group.split(',')}
    bibkeys = set(re.findall(r'\\bibitem\{([^}]+)\}',(EVIDENCE/'q3_references.tex').read_text()))
    assert cited==bibkeys and all(key.startswith('q3-') for key in cited)
    log = (PAPER/'figures/q3/.qa/q3_preview.log').read_text(errors='replace')
    prohibited = ['Overfull', 'Missing character', 'undefined references', 'LaTeX Warning: Citation',
                  'LaTeX Font Warning', '! LaTeX Error']
    assert not [line for line in log.splitlines() if any(value in line for value in prohibited)]
    aux = (PAPER/'figures/q3/.qa/q3_preview.aux').read_text()
    end = re.search(r'\\newlabel\{q3:preview-end\}\{\{[^}]*\}\{(\d+)\}',aux)
    assert end
    result = {
        'passed':True, 'claims':len(claims), 'hashed_source_and_code_files':len(audited_sources),
        'body_han_characters':sum('\u4e00'<=char<='\u9fff' for char in text),
        'section_body_pages':int(end[1]), 'preview_references_on_separate_page':True,
        'figures':text.count(r'\begin{figure}'), 'tables':text.count(r'\begin{table}'),
        'numbered_equations':text.count(r'\begin{equation}'), 'cited_references':len(cited),
        'labels':labels, 'tex_errors_overfull_missing_glyphs_undefined_citations':0,
        'source_hashes_checked':True, 'no_model_refit':True,
        'compile_inputs':[file_record(path) for path in
                          [PAPER/'preamble.tex', PAPER/'sections/q3.tex', EVIDENCE/'q3_references.tex']],
        'compiled_artifacts':[file_record(path) for path in sorted((PAPER/'figures/q3').glob('*.pdf'))],
        'scope':'仅Q3论文层静态核对；不增加独立事件样本，不替代模型科学评价。'}
    write(EVIDENCE/'q3_validation.json', result)
    print(json.dumps({key:result[key] for key in
                      ['passed','claims','hashed_source_and_code_files','body_han_characters',
                       'section_body_pages','figures','tables','cited_references']},ensure_ascii=False))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    args = parser.parse_args()
    if not args.check_only:
        build()
    check()
