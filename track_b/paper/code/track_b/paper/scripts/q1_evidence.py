#!/usr/bin/env python3
"""Register Q1 paper claims from frozen R3 files; fit no model and draw no figure.

Run: track_b/.venv/bin/python -B track_b/paper/scripts/q1_evidence.py
Writes only evidence/q1_claims.json, q1_code_files.json, q1_numeric_review.json.
AI-assisted implementation: OpenAI Codex, 2026-10-24.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'track_b/paper'
R3 = ROOT / 'track_b/research/q1/round3'
QC = 'original_qc_view'
UNKNOWN = 'unknown_qc_exploration'
MODELS = ['A_marginal_ecdf', 'B_shrunk_conditional', 'C_other_family_analog']
WINDOWS = [24, 72, 168]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def records(frame):
    return json.loads(frame.to_json(orient='records', force_ascii=False, double_precision=15))


def main():
    checks = Counter()

    def check(condition, category, detail=''):
        if not bool(condition):
            raise AssertionError((category, detail))
        checks[category] += 1

    input_manifest = R3 / 'results/input_manifest.json'
    output_manifest = R3 / 'output_manifest.json'
    manifest_index = {}
    manifests = {}
    for manifest_path, base in [(input_manifest, ROOT), (output_manifest, R3)]:
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest['files']:
            path = (base / entry['path']).resolve()
            check(path.is_relative_to(ROOT), 'manifest_path_within_repository', entry['path'])
            check(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'],
                  'frozen_manifest_file_hash', str(path))
            relative = str(path.relative_to(ROOT))
            if relative in manifest_index:
                check(manifest_index[relative]['sha256'] == entry['sha256'],
                      'overlapping_manifest_entries_agree', relative)
            manifest_index[relative] = {'path':relative, 'bytes':entry['bytes'], 'sha256':entry['sha256']}
        manifests[str(manifest_path.relative_to(ROOT))] = {
            'bytes':manifest_path.stat().st_size, 'sha256':sha(manifest_path),
            'file_count':len(manifest['files'])}

    source_snapshots = {}

    def source(path):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve()
        relative = str(path.relative_to(ROOT))
        value = {'path':relative, 'sha256':sha(path)}
        if path.is_relative_to(R3) or relative.startswith('track_b/data/') or relative == 'track_b/config/temporal_policy.json':
            check(relative in manifest_index and manifest_index[relative]['sha256'] == value['sha256'],
                  'claim_source_bound_to_frozen_manifest', relative)
        source_snapshots[relative] = {'bytes':path.stat().st_size, 'sha256':value['sha256']}
        return value

    def csv(name):
        path = R3 / 'results' / name
        source(path)
        return pd.read_csv(path, low_memory=False)

    cfg_path = R3 / 'config/experiment.json'
    features_path = R3 / 'config/features.json'
    cfg = json.loads(cfg_path.read_text())
    feature_cfg = json.loads(features_path.read_text())
    policy_path = ROOT / 'track_b/config/temporal_policy.json'
    policy = json.loads(policy_path.read_text())
    dictionary_path = ROOT / 'track_b/data/processed/temporal/data_dictionary.json'
    dictionary = json.loads(dictionary_path.read_text())['hourly']
    text_path = PAPER / 'sections/q1.tex'
    text = text_path.read_text()
    source(text_path)
    figures_path = PAPER / 'figures/q1/q1_figure_values.json'
    figure_values = json.loads(figures_path.read_text())
    source(figures_path)
    for entry in figure_values['source_files']:
        check(source(entry['path'])['sha256'] == entry['sha256'], 'figure_source_hash', entry['path'])
    check(figure_values['fit_performed'] is False, 'figure_redraw_not_model_fit')

    contract = csv('feature_contract.csv')
    variable_map = csv('variable_family_map.csv')
    meta = csv('sample_metadata.csv')
    routes = csv('top5_three_routes.csv')
    recommended = csv('recommended_factors.csv')
    stability = csv('ranking_stability.csv')
    fold_metrics = csv('fold_metrics.csv')
    memberships = csv('fold_membership.csv')
    directions = csv('factor_directions.csv')
    state = csv('case_state_evidence.csv')
    sensitivity = csv('sensitivity_metrics.csv')
    effective = csv('effective_family_support.csv')
    diagnostics_path = R3 / 'results/covariance_diagnostics.json'
    diagnostics = json.loads(diagnostics_path.read_text())
    draws_path = R3 / 'results/bootstrap_draw_specification.json'
    draws = json.loads(draws_path.read_text())
    source(draws_path)
    source(diagnostics_path)
    for path in [cfg_path, features_path, policy_path, dictionary_path]:
        source(path)

    claims = []

    def claim(identifier, statement, value, unit, paths, anchor, model=None, scope=None):
        if anchor.startswith('q1-sec/'):
            anchor = 'q1-sec'
        claims.append({'claim_id':identifier, 'statement':statement, 'value':value, 'unit':unit,
            'source_files':[source(p) for p in paths], 'model_id':model,
            'scenario_id':cfg['scenario_id'],
            'scope':scope or 'Regional background station, local_observational/exploration; case anomaly description, not causal or hazard-probability validation.',
            'paper_anchor':anchor})

    dictionary_by_id = {item['variable_id']:item for item in dictionary}
    driver_by_id = {item['driver_id']:item for item in feature_cfg['drivers']}
    table_counts = {}
    for kind in ['MET', 'RADM', 'SOIL', 'FLUX']:
        drivers = [d for d in feature_cfg['drivers'] if dictionary_by_id[d['source_variables'][0]]['kind'] == kind]
        known_drivers = {d['driver_id'] for d in drivers if d['availability_track'] == 'both_tracks_original_qc0'}
        all_drivers = {d['driver_id'] for d in drivers}
        known_count = int(contract.driver_id.isin(known_drivers).sum())
        unknown_count = int(contract.driver_id.isin(all_drivers-known_drivers).sum())
        table_counts[kind] = [sum(d['kind']==kind for d in dictionary), len(drivers), known_count, unknown_count]
        claim('q1-counts-'+kind.lower(), f'{kind}原变量、驱动量、主轨特征及探索增量的实际规模。',
              {'raw_variables':table_counts[kind][0], 'drivers':len(drivers),
               'original_qc_features':known_count, 'unknown_increment_features':unknown_count},
              'counts', [dictionary_path, features_path, R3/'results/feature_contract.csv'], 'q1-tab-features')
    totals = np.sum(list(table_counts.values()),axis=0).astype(int).tolist()
    known_families = {d['family_id'] for d in feature_cfg['drivers'] if d['availability_track']=='both_tracks_original_qc0'}
    all_families = {d['family_id'] for d in feature_cfg['drivers']}
    check(totals==[63,24,82,30] and len(known_families)==9 and len(all_families-known_families)==3,
          'feature_table_totals')
    check(len(variable_map)==63, 'all_raw_variables_mapped')
    statistic_counts = contract.statistic.value_counts().astype(int).to_dict()
    claim('q1-feature-schema-total', '完整特征库包含24驱动及112列，主轨82列、探索增量30列；18主轨驱动和6探索驱动。',
          {'raw_variables':63, 'drivers':24, 'original_qc_drivers':18, 'unknown_drivers':6,
           'features':112, 'original_qc_features':82, 'unknown_increment_features':30,
           'main_families':9, 'new_unknown_families':3, 'ordinary_drivers_times_five':21,
           'direction_drivers_times_one':2, 'precipitation_drivers_times_five':1,
           'statistic_counts':statistic_counts}, 'counts',
          [dictionary_path, features_path, R3/'results/feature_contract.csv', R3/'results/variable_family_map.csv'],
          'q1-tab-features')

    station = policy['hourly']['station']
    reference = pd.Timestamp(cfg['anchor_sources'][0]['source_time']).tz_convert('UTC')
    check(reference.isoformat()=='2026-08-26T02:30:00+00:00', 'reference_clock_conversion')
    claim('q1-station-and-clock', '区域背景站元数据位置及源时钟换算；坐标与海拔是元数据声明。',
          {'latitude':station['latitude'],'longitude':station['longitude'],'elevation_m':station['elevation_m'],
           'source_reference':cfg['anchor_sources'][0]['source_time'],'reference_utc':reference.isoformat(),
           'source_timezone':cfg['source_timezone'],'geodetic_datum':None,
           'timezone_status':policy['hourly']['timezone_status'],
           'hourly_interval_status':policy['hourly']['timestamp_label_semantics']},
          'degree; m; timezone-aware ISO8601', [policy_path,cfg_path,R3/'evidence/waternet_target.html'],
          'q1-sec/comparison-object', scope='Metadata regional-station coordinates; datum and positional error unspecified. UTC+8 is the documented source-clock assumption; not a source-area measurement or event initiation truth.')

    background = meta[(meta.quality_track==QC)&(meta.shift_hours==0)&(meta.window_hours==24)&~meta.is_target]
    check(len(background)==305 and background.process_id.nunique()==45, 'background_305_45')
    check(len(meta)==5526 and (~meta.is_target).sum()==5490 and meta.is_target.sum()==36, 'sample_bank_5526')
    claim('q1-background-and-sample-counts', '五年各61个同钟点日历背景组成每窗305样本、45个七日过程代理；完整敏感性样本库5526行。',
          {'background_years':cfg['background_years'],'inclusive_day_offsets':[-30,30],
           'daily_anchors_per_year':61,'background_anchors_per_track_shift_window':305,
           'process_days':7,'processes_per_year':9,'processes_per_track_shift_window':45,
           'window_hours':WINDOWS,'quality_tracks':cfg['quality_tracks'],'anchor_shifts_hours':[-1,0,1],
           'target_reference_count':2,'samples':5526,'background_samples':5490,'target_samples':36,
           'formula':'2 * (5 * 61 * 3 * 3 + 2 * 3 * 3)'}, 'counts; hours; days',
          [cfg_path,R3/'results/sample_metadata.csv',R3/'results/feature_build_validation.json'],
          'q1-sec/comparison-object')
    folds = fold_metrics.drop_duplicates('fold_id').copy()
    folds['template'] = folds.fold_id.str.split('|',n=2).str[2]
    check(len(folds)==300 and folds.template.nunique()==50 and len(fold_metrics)==900,
          '300_evaluation_folds_reuse_50_group_templates')
    check(all(g.template.nunique()==50 for _,g in folds.groupby(['quality_track','window_hours'])),
          'same_50_templates_in_six_track_window_combinations')
    check(len(memberships)==91500, 'fold_membership_rows')
    fold_counts = {}
    for kind,g in folds.groupby('kind'):
        fold_counts[kind] = {c:{'minimum':int(g[c].min()),'maximum':int(g[c].max())}
                            for c in ['n_train','n_test','n_purged','n_years_train','n_process_train']}
    check((folds.n_train+folds.n_test+folds.n_purged).eq(305).all(), 'fold_partition_305')
    for fold_id,g in memberships.groupby('fold_id'):
        train=g[g.role=='training'];test=g[g.role=='test_background']
        a=pd.to_datetime(train.support_start_utc,utc=True).astype('int64').to_numpy()
        b=pd.to_datetime(train.support_end_exclusive_utc,utc=True).astype('int64').to_numpy()
        c=pd.to_datetime(test.support_start_utc,utc=True).astype('int64').to_numpy()
        d=pd.to_datetime(test.support_end_exclusive_utc,utc=True).astype('int64').to_numpy()
        check(not np.any((a[:,None]<d[None,:])&(b[:,None]>c[None,:])),
              'actual_168h_fold_supports_disjoint', fold_id)
    claim('q1-fold-counts-and-isolation', '两质量轨、三窗口复用50种分组形成300个评估折，所有训练与留出168小时支持无交叠。',
          {'group_templates':50,'leave_year_templates':5,'leave_process_templates':45,
           'evaluation_folds':300,'route_fold_records':900,'membership_records':91500,
           'counts_by_fold_kind':fold_counts,'max_support_hours':168,'overlap_violations':0},
          'counts; hours', [R3/'results/fold_metrics.csv',R3/'results/fold_membership.csv',R3/'scripts/run_models.py'],
          'q1-sec/method-and-evaluation')

    algorithm_parameters = {
        'coverage_primary':cfg['coverage_primary'],'coverage_sensitivity':cfg['coverage_sensitivity'],
        'distribution_minimum_valid_labels':2,'trend_minimum_valid_labels':6,
        'ordinary_statistics':cfg['ranking_stats'],'precipitation_statistics':cfg['precip_stats'],
        'trend':'OLS against true label hour index; slope multiplied by24',
        'growth_run':'longest consecutive accepted +1hour positive increments / nominal label count; missing breaks',
        'quality_rule':'37 supplied-QC variables remain QC0 in both tracks; only26 supplied no-QC variables may use numeric-present values in exploration',
        'wind_direction':'sin/cos of nominal10m degrees; median only',
        'precipitation':'label statistics; no rainfall accumulation or energy integration'}
    claim('q1-feature-definitions', '特征、缺测链、质量轨及覆盖规则按登记定义实现。',algorithm_parameters,
          'mixed; see each parameter', [cfg_path,features_path,R3/'scripts/build_features.py',policy_path],
          'q1-tab-features')
    claim('q1-method-A', 'A使用加权中点ECDF双侧偏离，驱动内和族内依次取中位数。',
          {'weights':'1/(Y * P_y * n_yp), recalculated for finite feature support',
           'ecdf':'sum_i w_i * (I[x_ij<x] +0.5 I[x_ij=x])',
           'feature_score':'2*abs(F_j-0.5)','aggregation':'median statistics within driver, then median drivers within family',
           'minimum_actual_years':3,'interpretation':'relative marginal anomaly, not a p-value'},
          'dimensionless', [R3/'scripts/run_models.py',cfg_path], 'q1-eq-ecdf',model=MODELS[0])
    claim('q1-method-B', 'B在训练折内拟合稳健尺度与收缩协方差，计算按族维数归一的条件块贡献并留年校准。',
          {'minimum_weighted_observation_fraction':.8,'minimum_actual_years':3,'target_observed':True,
           'imputation':'training weighted median','primary_scale':'1.4826*weighted_MAD','fallback_scale':'weighted_IQR/1.349; zero scale excluded',
           'transform':'clip((x-median)/scale,-8,8) minus training weighted mean',
           'covariance':'C=sum_i w_i z_i z_i^T; Sigma=(1-lambda)C+lambda*I; P=inverse(Sigma)',
           'lambda':.5,'lambda_sensitivity':[.1,.9],
           'conditional_block':'eta=P*delta; b_g=eta_g^T inverse(P_gg) eta_g / d_g',
           'equivalence':'(full squared Mahalanobis distance minus deleted-family marginal distance using same fitted covariance)/d_g',
           'calibration':'upper midpoint ECDF of out-of-year family contributions; not a two-sided transformation',
           'heldout_support':'all active family columns must actually be observed; each fold refits transforms and active columns',
           'family_contributions_additive':False}, 'dimensionless',
          [R3/'scripts/run_models.py',cfg_path], 'q1-eq-conditional',model=MODELS[1])
    claim('q1-method-C', 'C排除待评族，用其他族等权距离选取不同过程类比，再用双侧分数及两层中位数聚合。',
          {'matching_columns':'complete-training B fit active columns; all tested-family columns excluded',
           'distance_squared':'mean over other families of mean over their active feature squared standardized differences',
           'minimum_matching_observed_fraction':.8,'processes_per_year':2,'maximum_primary_analogs':10,
           'selection':'nearest anchor per process, then2 nearest distinct processes per year',
           'feature_score':'2*abs(midpoint weighted ECDF in selected analogs -0.5)',
           'aggregation':'median statistics within driver, then median drivers within family',
           'processes_per_year_sensitivity':[1,3]}, 'dimensionless; counts',
          [R3/'scripts/run_models.py',cfg_path], 'q1-sec/route-C',model=MODELS[2])
    claim('q1-consensus-definition', '每路线每窗口先归一中间名次，再等权汇总三路线三窗口；缺路不计零。',
          {'fractional_rank':'Q=1-(r-1)/(G-1)','primary_finite_family_count':9,
           'per_route_cross_window_score':'mean over24/72/168h of Q',
           'consensus':'mean over24/72/168h of mean over A/B/C of Q; all3 routes and all3 windows required',
           'tie_definition':'midrank after score rounding to12 decimal places',
           'top5_credit':'clip((5-number_ranked_above_tie)/tie_size,0,1)',
           'duplicate_minute_anchors_extra_votes':False}, 'dimensionless',
          [R3/'scripts/run_models.py',cfg_path], 'q1-eq-consensus',model='consensus')

    primary_rec = recommended[recommended.quality_track==QC].sort_values('recommended_rank')
    aliases={'土壤水分':'soil_moisture','空气湿状态':'air_moisture','土壤热状态':'soil_thermal',
             '空气热状态':'air_thermal','平均风':'mean_wind','土热通量':'soil_heat_flux',
             '短波辐射':'shortwave','长波辐射':'longwave','气压':'air_pressure'}

    def tex_rows(label):
        block=re.search(r'\\label\{'+re.escape(label)+r'\}.*?\\begin\{tabular\}.*?\n(.*?)\\end\{tabular\}',text,re.S)
        check(block is not None,'tex_table_found',label)
        result={}
        for line in block.group(1).splitlines():
            if '&' not in line:continue
            cells=[re.sub(r'\\textbf\{([^{}]*)\}',r'\1',x).strip() for x in line.split('&')]
            cells[-1]=cells[-1].replace('\\\\','').strip()
            result[cells[0]]=cells[1:]
        return result

    count_rows=tex_rows('q1-tab-features')
    for kind,values in {**table_counts,'合计':totals}.items():
        check([int(x) for x in count_rows[kind][:4]]==values,'tex_feature_table_transcription',kind)
    rank_rows=tex_rows('q1-tab-ranks')
    for displayed,family in aliases.items():
        row=primary_rec[primary_rec.family_id==family].iloc[0]
        rr=[float(routes[(routes.quality_track==QC)&(routes.model_id==model)&(routes.family_id==family)].iloc[0]['rank']) for model in MODELS]
        paper_values=rank_rows[displayed]
        check(np.array_equal(np.array(paper_values[:3],float),rr),'tex_rank_transcription',family)
        check(paper_values[3]==f'{row.consensus_score:.3f}' and paper_values[4]==f'{row.mean_window_bootstrap_top5_frequency:.3f}',
              'tex_consensus_frequency_three_decimal_transcription',family)
        claim('q1-table-rank-'+family, f'主质量轨{displayed}三路线跨窗名次、共识及条件入选份额。',
              {'family_id':family,'route_ranks':dict(zip(MODELS,rr)),
               'consensus_score':float(row.consensus_score),'consensus_rank':float(row.recommended_rank),
               'mean_window_top5_credit_frequency':float(row.mean_window_bootstrap_top5_frequency),
               'valid_consensus_draws_per_window':44,'requested_draws_per_window':100,
               'paper_rounded_consensus':paper_values[3],'paper_rounded_frequency':paper_values[4]},
              'rank; dimensionless', [R3/'results/top5_three_routes.csv',R3/'results/recommended_factors.csv',R3/'results/ranking_stability.csv'],
              'q1-tab-ranks',model='consensus')
    wind=primary_rec[primary_rec.family_id=='mean_wind'].iloc[0]
    ground=primary_rec[primary_rec.family_id=='soil_heat_flux'].iloc[0]
    claim('q1-fifth-slot-competition', '风场名义共识第五，土热通量的条件入选份额较高，两种排序摘要刻画不同性质。',
          {'wind_consensus':float(wind.consensus_score),'ground_heat_consensus':float(ground.consensus_score),
           'wind_frequency':float(wind.mean_window_bootstrap_top5_frequency),
           'ground_heat_frequency':float(ground.mean_window_bootstrap_top5_frequency),
           'frequency_difference_percentage_points':float((ground.mean_window_bootstrap_top5_frequency-wind.mean_window_bootstrap_top5_frequency)*100)},
          'dimensionless; percentage points', [R3/'results/recommended_factors.csv'],
          'q1-sec/stability-and-fifth-slot',model='consensus')

    boot=stability[(stability.quality_track==QC)&(stability.kind=='hierarchical_bootstrap')]
    denominators={model:sorted(boot[boot.model_id==model].n_valid.unique().astype(int).tolist()) for model in MODELS+['consensus']}
    check(denominators=={MODELS[0]:[89],MODELS[1]:[44],MODELS[2]:[89],'consensus':[44]},'bootstrap_89_44_denominators')
    year_hist=Counter(len(set(d['sampled_years'])) for d in draws)
    check(year_hist=={2:11,3:45,4:40,5:4},'bootstrap_distinct_year_histogram')
    claim('q1-bootstrap-denominators', '100次原始层级抽样全部保留；主QC的A/C每窗89次有效，B及共识每窗44次。',
          {'requested_draws':100,'valid_draws_per_window':denominators,
           'unique_year_count_histogram':dict(sorted(year_hist.items())),
           'fewer_than_three_distinct_years':11,'fewer_than_four_distinct_years':56,
           'frequency_definition':'within each window mean fractional TOP5 credit over finite-rank draws; then equally average3 windows',
           'independent_events_added':0,'minimum_valid_draws_for_stable_label':70,
           'all_primary_labels':sorted(primary_rec.stability_label.unique().tolist())},
          'counts; conditional frequency', [draws_path,R3/'results/ranking_stability.csv',R3/'results/recommended_factors.csv',R3/'scripts/run_models.py'],
          'q1-fig-stability',model='consensus')

    vwc=state[(state.driver_id=='soil_vwc_0p1m')&(state.quality_track==QC)&(state.window_hours==168)].iloc[0]
    claim('q1-soil-water-state-and-direction', '0.1m体积含水率的较高季节背景位置与168小时内下降同时成立。',
          {key:(int(vwc[key]) if key in ['window_hours','n_valid','n_labels'] else str(vwc[key]) if 'time' in key else float(vwc[key]))
           for key in ['window_hours','n_valid','n_labels','first_valid_time_utc','last_valid_time_utc','first_valid_value','last_valid_value','endpoint_change','target_median','background_median_percentile','target_trend_per24h']},
          'm3 m-3; OLS slope in m3 m-3 per24h; UTC',
          [R3/'results/case_state_evidence.csv',R3/'results/factor_directions.csv'],
          'q1-fig-state',model=MODELS[0],
          scope='Accepted original-QC regional0.1m soil values,168 hourly labels spanning167h between endpoints. A negative window OLS trend is not proof of monotonic change, source-area pressure or causation.')
    representative=figure_values['state']['representative_driver_ids']
    main_directions=directions[(directions.quality_track==QC)&directions.statistic.eq('median')]
    for driver in representative:
        rows=main_directions[main_directions.driver_id==driver].sort_values('window_hours')
        check(rows.window_hours.tolist()==WINDOWS,'representative_windows',driver)
        claim('q1-median-direction-'+driver, f'{driver}的固定代表中位数、季节背景中位秩和方向。',
              records(rows[['window_hours','target_value','background_percentile','signed_direction']]),
              {'value':driver_by_id[driver]['unit'],'background_percentile':'fraction from0 to1'},
              [R3/'results/factor_directions.csv',features_path], 'q1-fig-state',model=MODELS[0])

    hourly_path=R3/'exports/hourly_drivers.parquet'
    source(hourly_path)
    hourly=pd.read_parquet(hourly_path)
    clock=pd.to_datetime(hourly.time_utc,utc=True)
    lower=pd.to_datetime(reference.value-168*3_600_000_000_000,utc=True)
    sub=hourly[(hourly.quality_track==QC)&(clock>=lower)&(clock<reference)].copy()
    times=pd.to_datetime(sub.time_utc,utc=True)
    series=sub.soil_vwc_0p1m.to_numpy(float)
    percentile_matrix=main_directions.pivot(index='driver_id',columns='window_hours',values='background_percentile').loc[representative,WINDOWS].to_numpy()
    check(np.isfinite(series).sum()==figure_values['state']['n_vwc']==168,'state_figure168_values')
    check(series[0]==figure_values['state']['vwc_first'] and series[-1]==figure_values['state']['vwc_last'],'state_figure_endpoints')
    check(np.allclose(percentile_matrix,figure_values['state']['median_percentiles'],rtol=0,atol=1e-12),'state_figure_complete_percentile_matrix')
    series_records=[{'time_utc':t.isoformat(),'hours_before_reference':float((t-reference).total_seconds()/3600),
                     'soil_vwc_0p1m':None if not np.isfinite(y) else float(y)} for t,y in zip(times,series)]
    claim('q1-figure-state-complete-data', '状态图完整168点时序及7代表量×3窗口背景位置，直接重绘冻结结果。',
          {'state_figure_values':figure_values['state'],'hourly_series':series_records,
           'aggregation':'time series is every accepted original-QC0.1m soil label in [reference-168h,reference); heatmap is each preselected driver median midpoint background ECDF, not family scores or an average over drivers'},
          'UTC; hours; m3 m-3; fraction',
          [hourly_path,R3/'results/factor_directions.csv',figures_path,PAPER/'scripts/q1_figures.py',PAPER/'figures/q1/q1_state.pdf'],
          'q1-fig-state',model=MODELS[0])

    sf=figure_values['stability'];ids=sf['family_ids']
    frequency=boot.groupby(['family_id','model_id']).top5_frequency.mean().unstack().loc[ids,MODELS].to_numpy()
    check(np.allclose(frequency,sf['frequency_mean_over_three_windows'],rtol=0,atol=1e-12),'stability_figure_complete_frequency_matrix')
    sm=sensitivity[sensitivity.quality_track==QC]
    categories=[('参考时刻 ±1 h',(sm.variant=='primary')&(sm.shift_hours!=0)),
        ('过程块 3 / 14 d',sm.variant.isin(['process_3','process_14'])),
        ('季节范围 ±15 d',sm.variant=='season_15'),
        ('支持率 50% / 90%',sm.variant.isin(['support_0.5','support_0.9'])),
        ('收缩系数 0.1 / 0.9',sm.variant.isin(['shrinkage_0.1','shrinkage_0.9'])),
        ('每年类比数 1 / 3',sm.variant.isin(['analogs_1','analogs_3']))]
    jaccard=np.array([sm[mask].groupby('model_id').top5_jaccard.mean().reindex(MODELS).to_numpy() for _,mask in categories])
    check([name for name,_ in categories]==sf['sensitivity_categories'],'sensitivity_category_order')
    check(np.allclose(jaccard,sf['jaccard_mean_over_three_windows_and_listed_variants'],rtol=0,atol=1e-12),'stability_figure_complete_sensitivity_matrix')
    category_support=[{'category':label,'records_per_route':{m:int((sm.loc[mask,'model_id']==m).sum()) for m in MODELS},
                       'variants':sorted(sm.loc[mask,'variant'].unique().tolist()),
                       'shift_hours':sorted(sm.loc[mask,'shift_hours'].unique().astype(int).tolist())} for label,mask in categories]
    claim('q1-figure-stability-complete-data', '稳定性图完整9族×3路线频率及6类×3路线Jaccard均值，使用各自有效分母。',
          {'figure_values':sf,'sensitivity_record_support':category_support,
           'left_aggregation':'per family/route equal mean of3 window-specific TOP5 fractional-credit frequencies; A/C denominator89 and B44 per window; not consensus frequency',
           'right_aggregation':'per category/route arithmetic mean TOP5 set Jaccard over all3 windows and all listed variants or hour shifts; deterministic sensitivity, not event prediction accuracy',
           'fit_performed':False}, 'fraction from0 to1; counts',
          [R3/'results/ranking_stability.csv',R3/'results/sensitivity_metrics.csv',R3/'results/recommended_factors.csv',
           figures_path,PAPER/'scripts/q1_figures.py',PAPER/'figures/q1/q1_stability.pdf'],
          'q1-fig-stability',model=MODELS)

    unknown_rec=recommended[recommended.quality_track==UNKNOWN].sort_values('recommended_rank')
    main_top=primary_rec.loc[primary_rec.recommended_top5,'family_id'].tolist()
    unknown_top=unknown_rec.loc[unknown_rec.recommended_top5,'family_id'].tolist()
    check(set(main_top)==set(unknown_top) and main_top[:2]==['soil_moisture','air_moisture'] and unknown_top[:2]==['air_moisture','soil_moisture'],
          'unknown_same_top5_first_two_exchange')
    unknown_turb=unknown_rec[unknown_rec.family_id.isin(['turbulent_heat','turbulent_mechanics'])]
    check(unknown_turb.consensus_score.isna().all() and unknown_turb.recommended_rank.isna().all(), 'unknown_primary_consensus_null')
    raw_rank=csv('rankings.csv')
    missing_B=raw_rank[(raw_rank.quality_track==UNKNOWN)&(raw_rank.variant=='primary')&
        (raw_rank.anchor_id=='problem_1030')&(raw_rank.shift_hours==0)&
        (raw_rank.model_id==MODELS[1])&raw_rank.family_id.isin(['turbulent_heat','turbulent_mechanics'])]
    check(len(missing_B)==6 and missing_B.score.isna().all(), 'unknown_B_all_three_windows_two_turbulent_families_null')
    claim('q1-unknown-track-comparison', '探索轨前五集合相同、前两项互换；湍流热和湍流机械的主设置B分数及共识保持空值。',
          {'main_top5':main_top,'unknown_top5':unknown_top,
           'unknown_consensus_rows':records(unknown_rec[['family_id','consensus_score','recommended_rank','mean_window_bootstrap_top5_frequency','min_window_bootstrap_valid_draws']]),
           'unknown_B_missing_scores':records(missing_B[['window_hours','family_id','score','rank']]),
           'actual_primary_family_support':records(effective[effective.quality_track==UNKNOWN]),
           'bootstrap_denominator_turbulent_A_C':61,'bootstrap_denominator_turbulent_B_consensus':10,
           'unknown_B_valid_draw_rule':'four non2022 years all present and2022 absent; all-five-year draws fail80% LOYO support'},
          'rank; dimensionless; actual-year counts',
          [R3/'results/recommended_factors.csv',R3/'results/rankings.csv',R3/'results/effective_family_support.csv',R3/'results/ranking_stability.csv',draws_path],
          'q1-sec/stability-and-fifth-slot',model='consensus')

    code_files=['track_b/research/q1/round3/scripts/build_features.py',
                'track_b/research/q1/round3/scripts/run_models.py',
                'track_b/research/q1/round3/scripts/summarize_results.py',
                'track_b/paper/scripts/q1_figures.py','track_b/paper/scripts/q1_evidence.py']
    for path in code_files:
        source(path)
    check(len({c['claim_id'] for c in claims})==len(claims), 'unique_claim_ids')
    for item in claims:
        check(all(k in item for k in ['claim_id','statement','value','unit','source_files','model_id','scenario_id','scope','paper_anchor']),
              'mandatory_claim_fields',item['claim_id'])
    for path,entry in source_snapshots.items():
        check(sha(ROOT/path)==entry['sha256'], 'source_unchanged_during_registration',path)
    dump(PAPER/'evidence/q1_claims.json',claims)
    dump(PAPER/'evidence/q1_code_files.json',code_files)
    review={'review_version':'q1-paper-numeric-v1','passed':True,
        'execution':'Actually read frozen data, reconstructed displayed summaries and transcribed TeX tables; no research model fit, plot render, network call or other-question read.',
        'script':'track_b/paper/scripts/q1_evidence.py','script_sha256':sha(Path(__file__)),
        'paper_section_sha256':sha(text_path),'figure_values_sha256':sha(figures_path),
        'manifest_snapshots':manifests,'source_snapshots':source_snapshots,
        'checks':dict(checks),'check_count':sum(checks.values()),'claims_count':len(claims),
        'table_transcription':{'q1-tab-features':'All4 category rows and total counts match frozen dictionary/schema',
                               'q1-tab-ranks':'All9 family rows,27 route ranks and18 rounded consensus/frequency values match frozen CSVs'},
        'figure_reconstruction':{'q1-fig-state':'168 complete hourly points, exact endpoints and21 background percentile cells',
                                  'q1-fig-stability':'27 route-specific frequency cells and18 Jaccard cells; all aggregation record counts retained'},
        'fold_support_checks':{'distinct_evaluation_folds':300,'group_templates':50,
                               'membership_records':91500,'overlap_violations':0},
        'output_files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)}
                        for p in [PAPER/'evidence/q1_claims.json',PAPER/'evidence/q1_code_files.json']],
        'boundaries':['ECDF positions, normalized ranks and conditional bootstrap frequencies are different quantities; none is a hazard probability or p-value.',
            'A/C use driver-then-family medians; B uses a conditional block distance and upper out-of-year ECDF, not the A/C two-sided transformation.',
            '300 evaluation folds reuse50 grouping templates; overlapping backgrounds and repeated windows are not independent disasters.',
            '44 valid consensus draws per window are conditional on supported sampled years; window means do not create132 independent draws.',
            'The0.1m soil-water median may be high in background rank while its168h temporal slope is negative.',
            'Regional station coordinates/UTC+8 are metadata assertions; original datum, source representativeness and true operational availability remain unspecified.',
            'Unknown-QC increments remain separate; empty B/calibration/consensus scores are not zeros.',
            'Figure verification covers source numbers/aggregation and artifact hashes; visual layout/LaTeX compilation belongs to the separate QA workflow.',
            'QA wrapper, shared preamble, references and volatile preview metadata were not bound as model evidence.']}
    dump(PAPER/'evidence/q1_numeric_review.json',review)
    print(json.dumps({'passed':True,'claims':len(claims),'checks':sum(checks.values()),
        'section_sha256':sha(text_path),'numeric_review_sha256':sha(PAPER/'evidence/q1_numeric_review.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
