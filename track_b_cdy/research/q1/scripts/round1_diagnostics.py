#!/usr/bin/env python3
"""Q1 round-1 data diagnostics; all output is confined to this question.

AI assistance: OpenAI Codex, 2026-10-24. No final research model or ranking.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
Q = ROOT / 'track_b/research/q1'
DATA = ROOT / 'track_b/data/processed/temporal'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    import numpy as np
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    expected_root = Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1')
    if ROOT != expected_root or Path(sys.prefix).resolve() != (ROOT / 'track_b/.venv').resolve():
        raise RuntimeError('Use the assigned q1 worktree and its own virtual environment')
    readiness = json.loads((Q / 'workspace_verification.json').read_text())
    if not readiness['passed']:
        raise RuntimeError('Wait for the advisor-published workspace readiness check')

    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize

    cfg_path = Q / 'config/round1.json'
    cfg = json.loads(cfg_path.read_text())
    result = Q / 'results'
    figures = Q / 'figures'
    result.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    input_paths = [DATA / f for f in (
        'data_dictionary.json', 'hourly_time_axis.parquet', 'hourly_raw_numeric.parquet',
        'hourly_strict_qc0.parquet', 'hourly_raw_qc.parquet',
        'hourly_mask_qc_unknown.parquet', 'hourly_mask_is_numeric_present.parquet',
        'hourly_mask_strict_qc0_accepted.parquet', 'hourly_provenance.parquet')]
    input_paths += [ROOT / 'track_b/config/temporal_policy.json',
                    ROOT / 'track_b/data/external/event_remote/event_evidence_ledger.json',
                    ROOT / 'track_b/audit/stage4/baseline_manifest.json']
    before = {str(p.relative_to(ROOT)): digest(p) for p in input_paths}
    dictionary = json.loads((DATA / 'data_dictionary.json').read_text())['hourly']
    lookup = {v['variable_id']: v for v in dictionary}
    clock = pd.read_parquet(DATA / 'hourly_time_axis.parquet')
    raw = pd.read_parquet(DATA / 'hourly_raw_numeric.parquet')
    strict = pd.read_parquet(DATA / 'hourly_strict_qc0.parquet')
    qc = pd.read_parquet(DATA / 'hourly_raw_qc.parquet')
    unknown = pd.read_parquet(DATA / 'hourly_mask_qc_unknown.parquet')
    present = pd.read_parquet(DATA / 'hourly_mask_is_numeric_present.parquet')
    accepted = pd.read_parquet(DATA / 'hourly_mask_strict_qc0_accepted.parquet')
    provenance = pd.read_parquet(DATA / 'hourly_provenance.parquet')
    source_clock = pd.to_datetime(clock['time_source_naive'])
    years = source_clock.dt.year.to_numpy()
    assert raw.shape == strict.shape == unknown.shape == present.shape == accepted.shape == (52584, 63)
    assert list(raw.columns) == [v['variable_id'] for v in dictionary]
    for frame in (strict, unknown, present, accepted):
        assert frame.columns.equals(raw.columns) and frame.index.equals(raw.index)
    assert clock.index.equals(raw.index) and qc.index.equals(raw.index) and provenance.index.equals(raw.index)
    np.testing.assert_array_equal(clock['hour_index'], np.arange(len(raw)))
    np.testing.assert_array_equal(source_clock.diff().dropna().to_numpy(), np.full(len(raw)-1, np.timedelta64(1, 'h')))
    np.testing.assert_array_equal(present.to_numpy(), np.isfinite(raw.to_numpy()) & (raw.to_numpy() != 9999.9))
    assert int(accepted.to_numpy().sum()) == 1712112
    assert qc.shape == (52584, 37)
    independent_qc0 = np.zeros(raw.shape, dtype=bool)
    for i, col in enumerate(raw.columns):
        if col in qc:
            independent_qc0[:, i] = present[col].to_numpy() & (qc[col].to_numpy() == '0')
    np.testing.assert_array_equal(accepted.to_numpy(), independent_qc0)
    np.testing.assert_array_equal(strict.to_numpy(), np.where(independent_qc0, raw.to_numpy(), np.nan))
    diagnostic = raw.where(present)
    unknown_variables = [v for v in raw.columns if v not in qc.columns]
    assert len(unknown_variables) == 26 and strict[unknown_variables].isna().all().all()
    metadata = {
        'input_version': {'baseline_commit': cfg['baseline_commit'],
                          'manifest_sha256': before['track_b/audit/stage4/baseline_manifest.json']},
        'event_id': cfg['event_id'], 'physical_phase': 'regional_background_descriptive_diagnostic',
        'time_utc': None, 'time_uncertainty': None,
        'space_object': {'id': 'Gyirong_regional_background', 'crs': 'EPSG:4326',
                         'latitude': 28.86, 'longitude': 85.29,
                         'status': 'same-title external metadata assertion; not a source-area measurement'},
        'variable_semantics': {'source': 'data_dictionary.json', 'units': 'original labels; no common input conversion',
                               'qc': 'original QC0 or separately named diagnostics_unknown_qc',
                               'reporting_interval': None},
        'available_time': None, 'forecast_reference_time': None, 'issue_time': None, 'valid_time': None,
        'data_role': 'exploration', 'evidence_status': 'local_fact',
        'limitations': ['Hourly timestamp convention and historical availability unverified',
                        'No accepted independent training/coverage events; no hazard association or ranking',
                        'Background year/hour samples are not independent disaster events']}
    save_json(result / 'context.json', metadata)

    semantic_rows = []
    quality_rows = []
    year_rows = []
    for v in dictionary:
        col = v['variable_id']
        values = raw[col].to_numpy()
        valid = present[col].to_numpy()
        semantic_rows.append({
            **{k: v.get(k) for k in ('variable_id', 'kind', 'raw_column', 'raw_unit_label',
                'unit_label_standardized', 'unit_status', 'description', 'description_status',
                'height_m', 'height_status', 'depth_m', 'depth_status', 'qc_raw_column',
                'timestamp_timezone_status', 'timestamp_label_semantics', 'available_time',
                'temporal_integration_interval')},
            'quality_view': 'original_qc0' if col in qc else 'diagnostics_unknown_qc',
            'sign_and_processing_verified': False,
            'sufficient_for': 'coverage/distribution diagnostics, not source causation or real-time eligibility'})
        quality_rows.append({'variable_id': col, 'kind': v['kind'], 'total_labels': len(raw),
            'numeric_present': int(valid.sum()), 'sentinel_9999_9': int((values == 9999.9).sum()),
            'null_values': int(np.isnan(values).sum()), 'nonfinite_nonnull': int(np.isinf(values).sum()),
            'original_qc0_accepted': int(accepted[col].sum()), 'unknown_qc_labels': int(unknown[col].sum()),
            'qc_provided': col in qc, 'new_qc_accepted_labels': 0})
        for year in sorted(set(years)):
            select = years == year
            year_rows.append({'variable_id': col, 'kind': v['kind'], 'year': int(year),
                'labels': int(select.sum()), 'numeric_present': int(valid[select].sum()),
                'original_qc0_accepted': int(accepted[col].to_numpy()[select].sum()),
                'numeric_present_fraction': float(valid[select].mean()),
                'original_qc0_fraction': float(accepted[col].to_numpy()[select].mean()) if col in qc else None,
                'quality_view': 'original_qc0' if col in qc else 'diagnostics_unknown_qc'})
    pd.DataFrame(semantic_rows).to_csv(result / 'variable_semantics.csv', index=False)
    pd.DataFrame(quality_rows).to_csv(result / 'quality_accounting.csv', index=False)
    year_df = pd.DataFrame(year_rows)
    year_df.to_csv(result / 'coverage_by_year.csv', index=False)

    distribution_rows, constant_rows, jump_rows = [], [], []
    constant_short, constant_long = cfg['candidate_constant_run_lengths_hours']
    assert constant_short == 6 and constant_long == 24, 'Output column names bind the configured 6/24-label diagnostics'
    for col in unknown_variables:
        x = raw[col].to_numpy()
        valid = present[col].to_numpy()
        vals = x[valid]
        same = valid[1:] & valid[:-1] & (x[1:] == x[:-1])
        edges = np.r_[0, np.flatnonzero(~same) + 1, len(x)]
        starts = edges[:-1]
        lengths = np.diff(edges)
        good = valid[starts]
        starts, lengths = starts[good], lengths[good]
        pair = valid[1:] & valid[:-1]
        difference = np.abs(np.diff(x))[pair]
        positive_diff = difference[difference > 0]
        jump = float(np.quantile(positive_diff, cfg['candidate_jump_quantile'])) if positive_diff.size else None
        q = np.quantile(vals, [0, .01, .05, .5, .95, .99, 1]) if vals.size else np.full(7, np.nan)
        distribution_rows.append({'variable_id': col, 'quality_view': 'diagnostics_unknown_qc',
            'numeric_present': int(valid.sum()), 'zero_count': int((vals == 0).sum()),
            'negative_count_numeric_property_only': int((vals < 0).sum()),
            **dict(zip(('min', 'q01', 'q05', 'median', 'q95', 'q99', 'max'), q)),
            'maximum_exact_constant_run_labels': int(lengths.max()) if lengths.size else 0,
            'constant_runs_ge6_labels': int((lengths >= constant_short).sum()),
            'constant_runs_ge24_labels': int((lengths >= constant_long).sum()),
            'nonzero_constant_runs_ge24_labels': int(((lengths >= constant_long) & (x[starts] != 0)).sum()),
            'adjacent_present_pairs': int(pair.sum()), 'candidate_jump_threshold': jump,
            'candidate_jump_count': int((difference > jump).sum()) if jump is not None else 0,
            'diagnostic_flags_remove_values': False, 'new_qc_acceptance': False})
        kind = lookup[col]['kind']
        for start, length in zip(starts[lengths >= constant_short], lengths[lengths >= constant_short]):
            constant_rows.append({'variable_id': col, 'start_hour_index': int(start),
                'end_hour_index_inclusive': int(start + length - 1), 'labels': int(length),
                'value': float(x[start]), 'zero_run': bool(x[start] == 0),
                'time_utc': clock['time_utc'].iloc[start].isoformat(),
                'end_time_utc': clock['time_utc'].iloc[start + length - 1].isoformat(),
                'start_source_file': provenance[f'{kind}__source_file'].iloc[start],
                'start_source_row_1based': int(provenance[f'{kind}__source_row_1based'].iloc[start]),
                'end_source_file': provenance[f'{kind}__source_file'].iloc[start + length - 1],
                'end_source_row_1based': int(provenance[f'{kind}__source_row_1based'].iloc[start + length - 1]),
                'interpretation': 'candidate_review_only; not an error or exclusion decision'})
        if jump is not None:
            indices = (np.flatnonzero(pair) + 1)[difference > jump]
            for current in indices:
                jump_rows.append({'variable_id': col, 'previous_hour_index': int(current - 1),
                    'hour_index': int(current), 'time_utc': clock['time_utc'].iloc[current].isoformat(),
                    'previous_value': float(x[current - 1]), 'value': float(x[current]),
                    'absolute_step': float(abs(x[current] - x[current - 1])),
                    'candidate_threshold': jump, 'source_file': provenance[f'{kind}__source_file'].iloc[current],
                    'source_row_1based': int(provenance[f'{kind}__source_row_1based'].iloc[current]),
                    'interpretation': 'exploratory review location, not invalidity or exclusion'})
    pd.DataFrame(distribution_rows).to_csv(result / 'diagnostics_unknown_qc.csv', index=False)
    pd.DataFrame(constant_rows).to_csv(result / 'constant_run_candidates.csv', index=False)
    pd.DataFrame(jump_rows).to_csv(result / 'jump_candidates.csv', index=False)

    def view_for(col):
        return strict[col] if col in qc else diagnostic[col]

    def window(anchor, hours, year):
        local = pd.Timestamp(anchor['source_time']).tz_convert(cfg['source_clock_timezone_assumption'])
        local = local.replace(year=year).tz_localize(None)
        choose = (source_clock >= local - pd.Timedelta(hours, unit='h')) & (source_clock < local)
        return choose.to_numpy(), local

    window_rows, feature_rows, label_set_comparisons = [], [], []
    for hours in cfg['label_windows_hours']:
        selections = [window(anchor, hours, cfg['target_year'])[0] for anchor in cfg['anchors']]
        label_set_comparisons.append({'window_hours': hours, 'anchor_ids': [a['id'] for a in cfg['anchors']],
            'same_selected_hour_labels': all(np.array_equal(selections[0], s) for s in selections[1:]),
            'interpretation': 'Same whole-hour labels cannot establish minute-scale timing sensitivity'})
    for anchor in cfg['anchors']:
        for hours in cfg['label_windows_hours']:
            for year in cfg['reference_years'] + [cfg['target_year']]:
                choose, local = window(anchor, hours, year)
                for col in raw.columns:
                    s = view_for(col)[choose].dropna()
                    is_target = year == cfg['target_year']
                    window_rows.append({'event_id': cfg['event_id'] if is_target else None,
                        'anchor_id': anchor['id'], 'physical_phase': anchor['physical_phase'] if is_target else 'matched_calendar_background_not_confirmed_nonevent',
                        'time_utc': pd.Timestamp(local, tz=cfg['source_clock_timezone_assumption']).tz_convert('UTC').isoformat(),
                        'year': year, 'role': 'target_descriptive' if is_target else 'historical_calendar_background',
                        'window_hours': hours, 'interval_rule': '[anchor-hours,anchor) on hour labels only',
                        'variable_id': col, 'quality_view': 'original_qc0' if col in qc else 'diagnostics_unknown_qc',
                        'labels': int(choose.sum()), 'numeric_present': int(present[col][choose].sum()),
                        'original_qc0_accepted': int(accepted[col][choose].sum()),
                        'descriptive_view_count': len(s), 'minimum': s.min(), 'median': s.median(), 'maximum': s.max(),
                        'available_time': None, 'data_role': 'exploration', 'context_ref': 'context.json'})
                for feature in cfg['candidate_features']:
                    matrices = pd.concat([view_for(c) for c in feature['variables']], axis=1)
                    count = int(matrices.loc[choose].notna().all(axis=1).sum())
                    feature_rows.append({'anchor_id': anchor['id'], 'year': year, 'window_hours': hours,
                        'feature_id': feature['id'], 'formula': feature['formula'],
                        'candidate_unit': feature['candidate_unit'], 'redundancy_group': feature['redundancy_group'],
                        'required_variables': ';'.join(feature['variables']), 'labels': int(choose.sum()),
                        'joint_present_in_assigned_view': count,
                        'all_variables_have_original_qc': all(c in qc for c in feature['variables']),
                        'status': 'availability_only; not selected or ranked', 'limitation': feature['limitation']})
    pd.DataFrame(window_rows).to_csv(result / 'window_descriptives.csv', index=False)
    pd.DataFrame(feature_rows).to_csv(result / 'candidate_feature_coverage.csv', index=False)

    consistency = []
    candidates = [
        ('pressure_label_relation', 'FLUX__PA', [('MET__Pressure', .1)], 'PA(kPa) versus 0.1*Pressure(hPa)'),
        ('vpd_ambient_candidate', 'FLUX__VPD', [('FLUX__amb_e_sat', 10), ('FLUX__amb_e', -10)], 'VPD(hPa) versus 10*(amb_e_sat-amb_e)'),
        ('vpd_e_candidate', 'FLUX__VPD', [('FLUX__e_sat', 10), ('FLUX__e', -10)], 'VPD(hPa) versus 10*(e_sat-e)'),
        ('vpd_probe_candidate', 'FLUX__VPD', [('FLUX__e_sat_probe', 10), ('FLUX__e_probe', -10)], 'VPD(hPa) versus 10*(e_sat_probe-e_probe)')]
    for name, response, terms, formula in candidates:
        columns = [response] + [c for c, _ in terms]
        pair = pd.concat([view_for(c) for c in columns], axis=1).dropna()
        residual = pair[response] - sum(pair[c]*factor for c, factor in terms)
        consistency.append({'candidate_id': name, 'formula_for_definition_review_only': formula,
            'joint_labels': len(pair), 'median_residual_original_response_unit': residual.median(),
            'median_absolute_residual': residual.abs().median(),
            'residual_q05': residual.quantile(.05), 'residual_q95': residual.quantile(.95),
            'no_correlation_or_hazard_association_estimated': True,
            'interpretation': 'header-based consistency clue; processing/height definitions unverified; no QC accepted'})
    pd.DataFrame(consistency).to_csv(result / 'candidate_definition_consistency.csv', index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 16), sharey=True, constrained_layout=True)
    for ax, field, title in zip(axes, ('numeric_present_fraction', 'original_qc0_fraction'),
                               ('Finite non-sentinel values', 'Original QC0 acceptance (gray = no QC)')):
        table = year_df.pivot(index='variable_id', columns='year', values=field).reindex(raw.columns)
        cmap = plt.get_cmap('viridis').copy(); cmap.set_bad('#d9d9d9')
        im = ax.imshow(table.to_numpy(), cmap=cmap, norm=Normalize(0, 1), aspect='auto', interpolation='nearest')
        ax.set_xticks(np.arange(len(table.columns)), table.columns)
        ax.set_yticks(np.arange(len(table.index)), table.index, fontsize=7)
        ax.set_title(title, fontsize=10)
        for boundary in (21.5, 25.5, 37.5): ax.axhline(boundary, color='white', lw=1.0)
    fig.colorbar(im, ax=list(axes), shrink=.6, label='Fraction of recorded hour labels')
    fig.suptitle('Q1 input coverage by year | 63 variables, 4 data classes\nUnknown QC is never promoted to QC0; no new quality screening', fontsize=12)
    fig.savefig(figures / 'coverage_by_year.png', dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True, constrained_layout=True)
    envelope_rows = []
    anchor = next(a for a in cfg['anchors'] if a['id'] == cfg['plot_anchor'])
    for ax, col in zip(axes.flat, cfg['plot_variables']):
        background = []
        for year in cfg['reference_years']:
            choose, local = window(anchor, cfg['plot_window_hours'], year)
            offsets = ((source_clock[choose] - local).dt.total_seconds()/3600).to_numpy()
            values = view_for(col)[choose].to_numpy()
            background.append(pd.Series(values, index=offsets))
        matrix = pd.concat(background, axis=1)
        for offset in matrix.index:
            envelope_rows.append({'variable_id': col, 'hour_label_offset': float(offset),
                'available_year_count': int(matrix.loc[offset].notna().sum()),
                'possible_reference_year_count': len(cfg['reference_years']),
                'minimum': matrix.loc[offset].min(), 'median': matrix.loc[offset].median(),
                'maximum': matrix.loc[offset].max(), 'data_role': 'exploration'})
        median = matrix.median(axis=1)
        low, high = matrix.min(axis=1), matrix.max(axis=1)
        ax.fill_between(matrix.index, low, high, color='#b9c6d5', alpha=.55, label='2021-2025 available-year min-max')
        ax.plot(matrix.index, median, color='#596b7d', lw=1.1, label='Available-year median (descriptive)')
        choose, local = window(anchor, cfg['plot_window_hours'], cfg['target_year'])
        offsets = ((source_clock[choose] - local).dt.total_seconds()/3600).to_numpy()
        target = view_for(col)[choose]
        color = '#236e91' if col in qc else '#b15c20'
        ax.plot(offsets, target.to_numpy(), color=color, lw=1, label='2026 original QC0' if col in qc else '2026 unknown QC, numeric-present only')
        ax.set_title(f'{col} | {int(target.notna().sum())}/{len(target)} target labels', fontsize=10)
        ax.set_ylabel(lookup[col]['raw_unit_label'])
        ax.axvline(0, color='#8a3030', ls='--', lw=.8)
        ax.grid(alpha=.18)
        ax.legend(fontsize=6, loc='best')
    for ax in axes[-1]: ax.set_xlabel('Hour-label offset to 2026-08-26 10:30 UTC+8 reference')
    fig.suptitle('Retrospective same-calendar background: fixed 168-hour label window\nIntegration endpoints / availability unknown; band is not a confidence interval; no causal inference', fontsize=11)
    fig.savefig(figures / 'same_calendar_descriptives.png', dpi=160)
    plt.close(fig)
    pd.DataFrame(envelope_rows).to_csv(result / 'historical_envelope_counts.csv', index=False)

    after = {str(p.relative_to(ROOT)): digest(p) for p in input_paths}
    assert before == after
    checks = {'shape_and_alignment': True, 'hour_label_spacing': True,
              'numeric_presence_mask_recomputed': True, 'unknown_qc_not_promoted': True,
              'original_qc0_mask_and_strict_view_independently_recomputed': True,
              'original_qc0_count_retained': True, 'input_hashes_unchanged': before == after,
              'labels_per_window_match_configured_hours': all(r['labels'] == r['window_hours'] for r in window_rows),
              'no_new_qc_acceptance': all(r['new_qc_accepted_labels'] == 0 for r in quality_rows)}
    assert all(checks.values())
    summary = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'experiment_version': cfg['experiment_version'], 'script_sha256': digest(Path(__file__)),
        'config_sha256': digest(cfg_path), 'baseline_commit': cfg['baseline_commit'],
        'dimensions': {'hour_labels': len(raw), 'variables': len(raw.columns), 'qc_variables': len(qc.columns), 'unknown_qc_variables': len(unknown_variables)},
        'counts': {'numeric_present': int(present.to_numpy().sum()), 'original_qc0_accepted': int(accepted.to_numpy().sum()),
                   'window_summary_rows': len(window_rows), 'candidate_feature_coverage_rows': len(feature_rows),
                   'constant_run_candidates': len(constant_rows)},
        'anchors': cfg['anchors'], 'reference_years': cfg['reference_years'],
        'anchor_label_set_comparisons': label_set_comparisons,
        'checks': checks, 'passed': all(checks.values()),
        'scope': cfg['scope'], 'figures_visually_reviewed_at_generation': False,
        'visual_review_record': 'figures/visual_review.json (created only after actual image inspection)'}
    save_json(result / 'diagnostic_summary.json', summary)
    save_json(result / 'input_check.json', {'context_ref': 'context.json', 'files': [{'path': p, 'sha256': h, 'technical_available': True, 'semantics': 'partial; see variable_semantics.csv and existing policies', 'supports': 'Q1 first-round descriptive/quality diagnostics only'} for p,h in before.items()], 'before_after_equal': before == after})
    files = sorted([p for p in result.glob('*') if p.name != 'output_manifest.json'] + list(figures.glob('*.png')))
    save_json(result / 'output_manifest.json', {'context_ref': 'context.json', 'files': [{'path': str(p.relative_to(Q)), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files]})
    print(json.dumps(clean(summary), ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
