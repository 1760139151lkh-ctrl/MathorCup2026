#!/usr/bin/env python3
"""Offline R2 equal-year background summaries and one bounded constant trace.

Reuses the saved R1 annual-window medians; never rebuilds R1 hourly windows.
AI assistance: OpenAI Codex, 2026-10-24. No core association model or QC adoption.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[5]
R1 = ROOT / 'track_b/research/q1'
R2 = R1 / 'round2'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def normalize(value):
    import numpy as np
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if isinstance(value, np.generic):
        return normalize(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalize(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def preserve_round1():
    p = ROOT / 'track_b/audit/stage4/round2/round1_preservation.json'
    policy = json.loads(p.read_text())
    for entry in policy['files']:
        path = ROOT / entry['path']
        assert path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], entry['path']
    return {'files_verified': len(policy['files']), 'policy_sha256': sha(p)}


def summarize_years(values):
    """Plain scalar arithmetic; callers determine valid annual values explicitly."""
    return {'mean': statistics.mean(values) if values else None,
            'median': statistics.median(values) if values else None,
            'minimum': min(values) if values else None,
            'maximum': max(values) if values else None, 'n': len(values)}


def mechanical_checks():
    tests = [
        ('unequal_hour_counts_do_not_weight_years', summarize_years([10., 20.])['mean'] == 15.),
        ('missing_year_not_filled_with_zero', summarize_years([10.])['mean'] == 10.),
        ('zero_is_a_valid_annual_median', summarize_years([0., 10.])['mean'] == 5.),
        ('empty_background_is_null', summarize_years([])['mean'] is None and summarize_years([])['n'] == 0)]
    assert all(ok for _, ok in tests)
    return [{'case': name, 'passed': ok, 'role': 'synthetic_arithmetic_check_not_observed_background'} for name, ok in tests]


def main():
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    cfg_path = R2 / 'config/analysis.json'
    cfg = json.loads(cfg_path.read_text())
    binding = json.loads((R2 / 'workspace_binding.json').read_text())
    assert ROOT == Path(binding['execution_root'])
    assert Path(sys.prefix).resolve() == (ROOT / 'track_b/.venv').resolve()
    assert json.loads((R2 / 'workspace_verification.json').read_text())['passed']
    freeze_path = ROOT / 'track_b/audit/stage4/round2/baseline_manifest.json'
    assert sha(freeze_path) == cfg['round2_manifest_sha256']
    assert sha(ROOT / cfg['round1_window_table']) == cfg['round1_window_table_sha256']
    preservation_before = preserve_round1()
    result, figures = R2 / 'results', R2 / 'figures'
    result.mkdir(parents=True, exist_ok=True)
    figures.mkdir(exist_ok=True)

    inputs = [cfg_path, freeze_path,
        ROOT / 'track_b/config/stage4_round2_contract.json',
        ROOT / 'track_b/audit/stage4/round2/round1_preservation.json',
        ROOT / cfg['round1_window_table'], R1 / 'results/constant_run_candidates.csv',
        R1 / 'results/variable_semantics.csv', R1 / 'results/remote_flux_comparison.json',
        R1 / 'results/remote_flux_column_comparison.csv', R1 / 'results/remote_flux_candidate_qc_tokens.csv',
        R1 / 'config/round1.json', R1 / 'sources/waternet_metadata.html', R1 / 'sources/access_log.json',
        R1 / 'sources/waternet_flux_2026.csv',
        ROOT / 'track_b/data/processed/temporal/data_dictionary.json',
        ROOT / 'track_b/data/processed/temporal/hourly_raw_numeric.parquet',
        ROOT / 'track_b/data/processed/temporal/hourly_time_axis.parquet']
    inputs += [ROOT / r['file'] for r in cfg['constant_segment']['raw_ranges']]
    inputs += sorted(p for p in (R2 / 'sources').glob('*') if p.is_file())
    before = {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in inputs}
    save(R2 / 'input_manifest.json', {'scope': 'Direct inputs only; excludes itself and output_manifest.json; R1 immutable inputs plus saved R2 evidence/config.',
         'files': [{'path': name, **value} for name, value in before.items()]})

    dictionary = json.loads((ROOT / 'track_b/data/processed/temporal/data_dictionary.json').read_text())['hourly']
    meta = {v['variable_id']: v for v in dictionary}
    context = {'input_version': {'common_baseline_commit': cfg['common_baseline_commit'],
              'round2_manifest_sha256': cfg['round2_manifest_sha256'],
              'round1_window_table_sha256': cfg['round1_window_table_sha256']},
        'event_id': 'B20260826_Chhochen', 'physical_phase': 'background',
        'time_utc': None, 'time_uncertainty': None,
        'space_object': {'id': 'Gyirong_regional_background', 'crs': 'EPSG:4326',
                         'longitude': 85.29, 'latitude': 28.86,
                         'status': 'same-title metadata assertion; not a verified source-area local observation'},
        'variable_semantics': {'units': 'original header labels',
              'quality_view': 'original_qc0 and diagnostics_unknown_qc kept separate',
              'reporting_interval': None},
        'available_time': None, 'forecast_reference_time': None, 'issue_time': None, 'valid_time': None,
        'data_role': 'exploration', 'evidence_status': 'local_fact',
        'limitations': ['Reference clocks are not new accepted event truths',
                       'Annual medians, not hourly samples, receive equal weight',
                       'Background years are not confirmed no-event labels',
                       'Raw degree-median arithmetic is not a circular mean']}
    save(result / 'context.json', context)

    table = pd.read_csv(ROOT / cfg['round1_window_table'])
    table['source_row_1based'] = np.arange(len(table)) + 2
    keys = cfg['group_keys']
    assert len(table) == 2268 and not table.duplicated(keys + ['year']).any()
    assert set(table['window_hours']) == set(cfg['window_hours'])
    assert set(table['quality_view']) == {'original_qc0', 'diagnostics_unknown_qc'}
    assert ((table['descriptive_view_count'] > 0) == table['median'].notna()).all()
    assert (table['descriptive_view_count'] <= table['labels']).all()
    backgrounds = table[table['role'].eq('historical_calendar_background')].copy()
    assert set(backgrounds['year']) == set(cfg['background_years'])
    targets = table[table['year'].eq(cfg['target_year']) & table['role'].eq('target_descriptive')].copy()
    assert len(backgrounds) == 1890 and len(targets) == 378
    backgrounds['valid_annual_value'] = np.isfinite(backgrounds['median']) & backgrounds['descriptive_view_count'].gt(0)
    backgrounds['year_weight'] = backgrounds['valid_annual_value'].astype(int)
    backgrounds['source_r1_table'] = cfg['round1_window_table']
    backgrounds['physical_phase'] = 'background'
    backgrounds['data_role'] = 'exploration'
    backgrounds['context_ref'] = 'context.json'
    backgrounds.to_csv(result / 'background_year_values.csv', index=False)
    targets['source_r1_table'] = cfg['round1_window_table']
    targets['physical_phase'] = 'background'
    targets['context_ref'] = 'context.json'
    targets.to_csv(result / 'target_year_values.csv', index=False)
    target_lookup = {key: group.iloc[0] for key, group in targets.groupby(keys, sort=False)}

    rows = []
    for key, group in backgrounds.groupby(keys, sort=False):
        assert len(group) == 5 and set(group['year']) == set(cfg['background_years'])
        valid = group.loc[group['valid_annual_value']].sort_values('year')
        values = valid['median'].tolist()
        stats = summarize_years(values)
        target = target_lookup[key]
        variable = key[2]
        direction = variable.startswith('MET__WD_')
        rows.append({**dict(zip(keys, key)), 'kind': meta[variable]['kind'],
            'raw_unit_label': meta[variable]['raw_unit_label'],
            'mean_of_valid_annual_medians': stats['mean'], 'median_of_valid_annual_medians': stats['median'],
            'minimum_of_valid_annual_medians': stats['minimum'], 'maximum_of_valid_annual_medians': stats['maximum'],
            'valid_year_count': stats['n'], 'valid_years': json.dumps(valid['year'].astype(int).tolist()),
            'missing_years': json.dumps(sorted(set(cfg['background_years']) - set(valid['year']))),
            'valid_year_weights': json.dumps([1] * stats['n']),
            'valid_annual_source_rows_1based': json.dumps(valid['source_row_1based'].astype(int).tolist()),
            'minimum_hour_labels_in_valid_year': int(valid['descriptive_view_count'].min()) if len(valid) else None,
            'maximum_hour_labels_in_valid_year': int(valid['descriptive_view_count'].max()) if len(valid) else None,
            'target_2026_median': target['median'], 'target_2026_view_count': int(target['descriptive_view_count']),
            'target_source_row_1based': int(target['source_row_1based']),
            'formula': 'sum(valid annual-window medians)/count(valid years); weight=1 per year',
            'interpretation_status': 'exclude_physical_mean_direction_interpretation' if direction else 'descriptive_annual_median_summary_only',
            'qc_accepted_by_this_round': False,
            'physical_phase': 'background', 'data_role': 'exploration', 'available_time': None,
            'context_ref': 'context.json'})
    summary = pd.DataFrame(rows)
    summary.to_csv(result / 'background_equal_year.csv', index=False)
    summary[summary['valid_year_count'] < 5].to_csv(result / 'background_missing_years.csv', index=False)

    # Independent pandas arithmetic cross-check against the plain-statistics path.
    pandas_means = backgrounds.loc[backgrounds['valid_annual_value']].groupby(keys)['median'].mean()
    for row in rows:
        key = tuple(row[k] for k in keys)
        if row['valid_year_count']:
            assert np.isclose(row['mean_of_valid_annual_medians'], pandas_means.loc[key], rtol=1e-14, atol=1e-14)
        else:
            assert row['mean_of_valid_annual_medians'] is None and key not in pandas_means.index
    anchor_comparisons = []
    compare_fields = ['year', 'window_hours', 'variable_id', 'quality_view', 'median', 'labels',
                      'numeric_present', 'original_qc0_accepted', 'descriptive_view_count']
    for anchor in sorted(table['anchor_id'].unique()):
        part = table.loc[table['anchor_id'].eq(anchor), compare_fields].sort_values(['year','window_hours','variable_id']).reset_index(drop=True)
        if not anchor_comparisons:
            first = part
        else:
            pd.testing.assert_frame_equal(first, part)
        anchor_comparisons.append({'anchor_id': anchor, 'rows': len(part), 'same_values_and_counts_as_first_anchor': True,
            'limitation': 'Same saved whole-hour samples are not independent timing-sensitivity evidence'})
    save(result / 'anchor_equivalence.json', anchor_comparisons)

    # Trace only the specified segment and two labels on each outside boundary.
    spec = cfg['constant_segment']
    raw_segment, boundary_rows = [], []
    for i, limits in enumerate(spec['raw_ranges']):
        start, end = limits['first_row_1based'], limits['last_row_1based']
        lower = start - 2 if i == 0 else start
        upper = end + 2 if i == len(spec['raw_ranges']) - 1 else end
        with (ROOT / limits['file']).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            for number, record in enumerate(reader, start=2):
                if number > upper:
                    break
                if number < lower:
                    continue
                is_segment = start <= number <= end
                item = {'source_file': limits['file'], 'source_row_1based': number,
                    'source_clock': record['Timestamp'], 'amb_e_sat_raw_token': record[spec['raw_column']],
                    'amb_e_raw_token': record['amb_e(kPa)'], 'T_SONIC_raw_token': record['T_SONIC(deg C)'],
                    'role': 'specified_constant_segment' if is_segment else 'minimal_outside_neighbor',
                    'physical_phase': 'background', 'data_role': 'exploration'}
                if is_segment:
                    raw_segment.append(item)
                if number in {start-2, start-1, start, start+1, end-1, end, end+1, end+2}:
                    boundary_rows.append(item)
    segment = pd.DataFrame(raw_segment)
    parsed_time = pd.to_datetime(segment['source_clock'])
    assert len(segment) == spec['hour_labels']
    assert parsed_time.iloc[0].isoformat() == spec['start_source_clock']
    assert parsed_time.iloc[-1].isoformat() == spec['end_source_clock_inclusive']
    assert (parsed_time.diff().dropna() == pd.Timedelta(1, unit='h')).all()
    values = pd.to_numeric(segment['amb_e_sat_raw_token']).to_numpy()
    assert np.all(values == spec['expected_raw_value'])
    start, end = spec['processed_start_hour_index'], spec['processed_end_hour_index_inclusive']
    processed = pd.read_parquet(ROOT / 'track_b/data/processed/temporal/hourly_raw_numeric.parquet', columns=[spec['variable_id']]).iloc[start:end+1, 0].to_numpy()
    processed_clock = pd.read_parquet(ROOT / 'track_b/data/processed/temporal/hourly_time_axis.parquet', columns=['time_source_naive']).iloc[start:end+1, 0]
    np.testing.assert_array_equal(values, processed)
    np.testing.assert_array_equal(parsed_time.to_numpy(), processed_clock.to_numpy())
    pd.DataFrame(boundary_rows).to_csv(result / 'constant_segment_boundary_excerpt.csv', index=False)
    trace = {'variable_id': spec['variable_id'], 'raw_unit_label': 'kPa',
        'attachment_source_clock_assumption': 'UTC+8; no new interval convention accepted',
        'start_source_clock': spec['start_source_clock'], 'end_source_clock_inclusive': spec['end_source_clock_inclusive'],
        'hour_label_count': len(segment), 'unique_raw_tokens': sorted(set(segment['amb_e_sat_raw_token'])),
        'exact_constant_value': spec['expected_raw_value'], 'attachment_and_saved_pipeline_equal': True,
        'pipeline_introduced_constant': False, 'raw_ranges_inclusive': spec['raw_ranges'],
        'row_counting': 'CSV header=physical row1, first data row=2; no embedded newlines in this selected CSV range',
        'outside_neighbors_each_side': 2, 'all_other_constant_segments_reaudited': False,
        'originating_instrument_or_processing_or_fill_cause': None,
        'cause_status': 'unknown_with_evidence_and_next_action',
        'observation_status': 'present in competition attachment; not proof of true atmospheric stability',
        'data_changed_or_quality_labels_created': False,
        'physical_phase': 'background', 'data_role': 'exploration', 'context_ref': 'context.json'}
    save(result / 'constant_segment_trace.json', trace)

    affected = [
        ('FLUX__amb_e_sat', 'ambient_saturation_vapour_pressure_background', 'one_verified_constant_segment',
         '2022 annual medians for all three fixed windows equal1.776582; retained without filtering',
         'unknown: no verified mechanism permits atmospheric/bias direction claim', 'Q1: original processing record; human quality sensitivity choice'),
        ('FLUX__amb_e_sat;FLUX__amb_e', 'candidate_10x_ambient_vapour_pressure_difference', 'candidate_definition_only',
         'Any prospective derived ambient difference would inherit the constant operand; not computed as a final feature here',
         'unknown physical validity/direction', 'Verify formula/averaging/sign and QC before scientific use'),
        ('FLUX__VPD', 'reported_vpd_field', 'direct_dependency_on_amb_e_sat_not_proved',
         'R1 consistency with another e_sat/e pair does not certify source processing',
         'unknown; no automatic deletion or substitution', 'Retain unknown QC and obtain derivation chain'),
        ('FLUX__FC_mass;FLUX__LE;FLUX__H;FLUX__TAU', 'remote_candidate_qc_mapping', 'remote_tokens_1to9_and_dataset_version_mismatch',
         'Four remote fields cannot inherit MET QC definitions or be transferred by timestamp alone',
         'unknown effect on accepted samples; no new acceptance', 'Require target-specific codebook/version mapping'),
        ('MET__Precip', 'accumulated_precipitation_candidate', 'reporting_interval_unknown',
         'Median labels are descriptive; zero median is not zero total rainfall',
         'unknown accumulation-window meaning', 'Get target hourly integration convention before sums'),
        ('MET__WD_1m;MET__WD_2m;MET__WD_4m;MET__WD_10m;MET__WD_20m', 'wind_direction_family', 'circular_quantity',
         'Annual scalar median arithmetic retained for traceability only',
         'exclude physical mean-direction interpretation', 'Later human-defined circular representation; do not recalculate R1 here'),
        ('RADM__Rsd;RADM__Rsu;RADM__Rld;RADM__Rlu', 'radiation_energy_or_net_radiation_candidate', 'sign_interval_and_orientation_unverified',
         'Annual-window medians are not integrated energy or verified net radiation',
         'unknown sign/energy interpretation', 'Retain component labels; verify conventions'),
        ('MET;RADM;SOIL', 'other_saved_background_summaries', 'no_direct_dependency_on_this_single_flux_column',
         'Original quality views and fixed R1 table can continue descriptively',
         'no inferred causal direction', 'Q2/Q3 receive limitations; source-area representativeness still needed')]
    pd.DataFrame(affected, columns=['variables', 'candidate_feature_or_use', 'issue', 'known_impact', 'impact_direction_status', 'next_action']).to_csv(result / 'affected_features.csv', index=False)

    selected = summary.loc[summary['anchor_id'].eq(cfg['plot_anchor']) & summary['variable_id'].isin(cfg['representative_variables'])].copy()
    selected.to_csv(result / 'representative_background.csv', index=False)
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    for ax, variable in zip(axes.flat, cfg['representative_variables']):
        subset = selected.loc[selected['variable_id'].eq(variable)].set_index('window_hours').loc[cfg['window_hours']]
        x = np.arange(3)
        for position, hours in enumerate(cfg['window_hours']):
            annual = backgrounds.loc[backgrounds['anchor_id'].eq(cfg['plot_anchor']) & backgrounds['variable_id'].eq(variable)
                                     & backgrounds['window_hours'].eq(hours) & backgrounds['valid_annual_value'], 'median']
            ax.scatter(np.full(len(annual), position), annual, color='#6f8192', marker='.', alpha=.7,
                       label='One point per valid annual median' if position == 0 else None)
        ax.plot(x, subset['mean_of_valid_annual_medians'], 'o-', color='#356781', label='Equal-year mean of annual medians')
        color = '#b2622d' if variable.startswith('FLUX') or variable == 'MET__Precip' else '#233b47'
        ax.scatter(x, subset['target_2026_median'], marker='x', s=55, color=color, label='2026 window median (separate)')
        for position, n in enumerate(subset['valid_year_count']):
            ax.text(position, 1.01, f'n={n} years', transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=8)
        ax.set_xticks(x, [f'{h} h' for h in cfg['window_hours']])
        ax.set_ylabel(meta[variable]['raw_unit_label'])
        suffix = 'unknown QC' if variable.startswith('FLUX') or variable == 'MET__Precip' else 'original QC0'
        ax.set_title(f'{variable} | {suffix}', pad=22, fontsize=10)
        ax.grid(alpha=.15)
        ax.legend(fontsize=6, loc='best')
    fig.suptitle('Fixed R1 windows | each valid 2021-2025 annual median has weight 1\n2026 separate; missing years not zero; no confidence interval, ranking or causal claim', fontsize=11)
    fig.savefig(figures / 'equal_year_background.png', dpi=160)
    plt.close(fig)

    after = {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in inputs}
    assert before == after
    preservation_after = preserve_round1()
    assert preservation_before == preservation_after
    checks = {'round1_window_table_hash_bound': True, 'unique_group_year_records': True,
        'background_role_and_years_only': True, 'target_2026_separate': True,
        'quality_views_preserved': True, 'equal_year_mean_independently_cross_checked': True,
        'missing_years_not_zero_and_zero_is_valid': True, 'duplicate_anchors_not_independent': True,
        'single_constant_segment_raw_and_pipeline_equal': True,
        'direct_inputs_unchanged': before == after, 'round1_preservation_unchanged': True}
    record = {'analysis_version': cfg['analysis_version'], 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'script_sha256': sha(Path(__file__)), 'config_sha256': sha(cfg_path),
        'input_rows': len(table), 'background_year_rows': len(backgrounds), 'target_rows': len(targets),
        'groups': len(summary), 'valid_year_count_distribution': summary['valid_year_count'].value_counts().sort_index().to_dict(),
        'groups_with_fewer_than_five_years': int((summary['valid_year_count'] < 5).sum()),
        'same_sample_anchors': True, 'year_weights_are_hour_counts': False,
        'constant_segment_labels': len(segment), 'raw_boundary_excerpt_rows': len(boundary_rows),
        'round1_preservation': preservation_after, 'synthetic_arithmetic_checks': mechanical_checks(),
        'checks': checks, 'passed': all(checks.values()), 'physical_phase': 'background', 'data_role': 'exploration',
        'no_final_top5_or_causality_or_qc_migration': True}
    save(result / 'analysis_checks.json', record)
    print(json.dumps(normalize(record), ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
