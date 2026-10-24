#!/usr/bin/env python3
"""Read-only numerical review of run_models helpers; writes only its own JSON.

Run from the Q1 worktree with its original interpreter:
  track_b/.venv/bin/python track_b/research/q1/round3/scripts/independent_numerical_review.py

The full production source is read and hashed before compile/exec. Its __main__
is never run. No production outputs, inputs or source files are changed. This
saved review uses real imports, including scipy.stats: there is no import stub.
Earlier interactive helper-only checks stubbed the unused scipy.stats import to
avoid native-loader waiting; those exploratory checks are not this run's proof.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import traceback
import warnings

sys.dont_write_bytecode = True
for variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'

R3 = Path(__file__).resolve().parents[1]
ROOT = R3.parents[3]
SOURCE = R3 / 'scripts/run_models.py'
OUTPUT = R3 / 'results/independent_numerical_review.json'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def run():
    assert ROOT == Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1')
    assert Path(sys.prefix).resolve() == (ROOT / 'track_b/.venv').resolve()
    source = SOURCE.read_bytes()
    source_hash = digest(source)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    print(json.dumps({'phase': 'source_snapshot_bound', 'sha256': source_hash}), flush=True)
    report = {
        'schema_version': 'q1-r3-independent-numerical-review-v1',
        'started_at_utc': started,
        'source_path': str(SOURCE.relative_to(ROOT)),
        'source_sha256_at_compile': source_hash,
        'review_script_sha256': digest(Path(__file__).read_bytes()),
        'interpreter': sys.executable,
        'environment_prefix': sys.prefix,
        'platform': platform.platform(),
        'scipy_stats_import_stubbed': False,
        'main_called': False,
        'data_role': 'exploration',
        'evaluation_stratum': 'numerical_benchmark',
        'tests': {},
        'passed': False,
        'scope': 'Synthetic helper-level checks only; not real event validation, full experiment rerun or primary-data certification.',
        'historical_interactive_checks': 'Earlier transient review processes used an unused scipy.stats stub; this saved execution uses the actual production imports and reports its own snapshot hash.',
    }
    collected_warnings = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            namespace = {'__name__': 'q1_independent_review_snapshot', '__file__': str(SOURCE)}
            exec(compile(source, str(SOURCE), 'exec'), namespace)
            import numpy as np
            import pandas as pd
            import scipy
            report['packages'] = {'numpy': np.__version__, 'pandas': pd.__version__, 'scipy': scipy.__version__}
            print(json.dumps({'phase': 'real_imports_complete'}), flush=True)
            tests = report['tests']
            rng = np.random.default_rng(617)

            # Independent algebraic identity for conditional Mahalanobis removal.
            matrix = rng.normal(size=(4, 4))
            covariance = matrix @ matrix.T + np.eye(4)
            precision = np.linalg.inv(covariance)
            fit = {'ids': np.arange(4), 'median': np.zeros(4), 'scale': np.ones(4), 'mean': np.zeros(4)}
            contract = pd.DataFrame({'family_id': ['a', 'a', 'b', 'b'],
                                     'feature_id': ['a1', 'a2', 'b1', 'b2'],
                                     'driver_id': ['a1', 'a2', 'b1', 'b2'], 'statistic': ['median'] * 4})
            targets = rng.normal(size=(8, 4))
            contributions = namespace['contributions'](fit, precision, targets, contract)
            full_distance = np.einsum('ij,jk,ik->i', targets, precision, targets)
            identity_errors = {}
            for family, deleted in [('a', [2, 3]), ('b', [0, 1])]:
                marginal = np.einsum('ij,jk,ik->i', targets[:, deleted],
                                     np.linalg.inv(covariance[np.ix_(deleted, deleted)]), targets[:, deleted])
                error = float(np.max(np.abs(2 * contributions[family] - (full_distance - marginal))))
                assert error < 1e-10
                assert np.all(contributions[family] >= 0)
                identity_errors[family] = error
            tests['conditional_contribution_equals_full_minus_deleted_marginal'] = {
                'passed': True, 'n_targets': 8, 'family_dimensions': 2,
                'max_absolute_error_by_family': identity_errors,
                'formula': 'family_dimension * contribution = full_D2 - deleted_family_marginal_D2'}

            # Equal year/process weights with deliberately unequal anchor counts.
            weight_meta = pd.DataFrame({'year': [2021] * 3 + [2022] * 4,
                                        'day_offset': [-30, -29, -23, -30, -29, -28, -23]})
            weight = namespace['weights'](weight_meta)
            year_totals = [float(weight[weight_meta.year == year].sum()) for year in [2021, 2022]]
            process_totals = [float(weight[(weight_meta.year == 2021) & (weight_meta.day_offset < -23)].sum()),
                              float(weight[(weight_meta.year == 2021) & (weight_meta.day_offset == -23)].sum())]
            assert np.allclose(year_totals, [.5, .5]) and np.allclose(process_totals, [.25, .25])
            valid = np.ones(len(weight_meta), bool)
            valid[0] = False
            valid_weight = namespace['weights'](weight_meta, valid)
            assert valid_weight[0] == 0
            assert np.allclose([valid_weight[weight_meta.year == year].sum() for year in [2021, 2022]], [.5, .5])
            draw = {2021: {'count': 2, 'processes': {0: 2, 1: 1}},
                    2022: {'count': 1, 'processes': {0: 1, 1: 2}}}
            draw_weight = namespace['weights'](weight_meta, draw=draw)
            draw_years = [float(draw_weight[weight_meta.year == year].sum()) for year in [2021, 2022]]
            assert np.allclose(draw_years, [2 / 3, 1 / 3])
            tests['hierarchical_weights_and_finite_reweighting'] = {
                'passed': True, 'year_weight_totals': year_totals,
                'year2021_process_weight_totals': process_totals,
                'bootstrap_year_weight_totals': draw_years, 'invalid_row_weight': float(valid_weight[0])}

            # Independent pre-optimization loop, not an alias of production code.
            def reference_loop_weights(metadata, valid=None, draw=None, block=7):
                if valid is None:
                    valid = np.ones(len(metadata), bool)
                output = np.zeros(len(metadata))
                years = metadata.year.to_numpy()
                groups = ((metadata.day_offset.to_numpy() + 30) // block).astype(int)
                active_years = np.unique(years[valid])
                if draw is not None:
                    active_years = np.array([year for year in active_years
                                             if draw.get(int(year), {}).get('count', 0) > 0])
                for year in active_years:
                    active_groups = np.unique(groups[valid & (years == year)])
                    if draw is not None:
                        active_groups = np.array([group for group in active_groups
                                                  if draw[int(year)]['processes'].get(int(group), 0) > 0])
                    year_multiplicity = 1 if draw is None else draw[int(year)]['count']
                    group_multiplicity = (np.ones(len(active_groups)) if draw is None else
                                          np.array([draw[int(year)]['processes'][int(group)]
                                                    for group in active_groups]))
                    if not len(active_groups):
                        continue
                    for group, multiplier in zip(active_groups, group_multiplicity):
                        selected = valid & (years == year) & (groups == group)
                        output[selected] = year_multiplicity * multiplier / group_multiplicity.sum() / selected.sum()
                return output / output.sum() if output.sum() else output

            weight_rng = np.random.default_rng(2026102401)
            weight_cases = []
            maximum_weight_error = 0.0
            for case in range(240):
                block = (3, 7, 14)[case % 3]
                size = int(weight_rng.integers(0, 380))
                random_meta = pd.DataFrame({'year': weight_rng.integers(2021, 2026, size=size),
                                            'day_offset': weight_rng.integers(-30, 31, size=size)})
                valid = weight_rng.random(size) > (.15 if case % 2 else .65)
                if case % 19 == 0:
                    valid[:] = False
                for use_draw in (False, True):
                    draw = None
                    if use_draw:
                        draw = {}
                        for year in range(2021, 2026):
                            if weight_rng.random() < .2:
                                continue
                            draw[year] = {'count': int(weight_rng.integers(0, 4)),
                                          'processes': {group: int(weight_rng.integers(0, 5))
                                                        for group in range(61 // block + 1)
                                                        if weight_rng.random() > .3}}
                    expected = reference_loop_weights(random_meta, valid, draw, block)
                    actual = namespace['weights'](random_meta, valid, draw, block)
                    error = float(np.max(np.abs(expected - actual))) if size else 0.0
                    assert np.allclose(expected, actual, rtol=1e-12, atol=1e-14)
                    assert np.all(actual >= 0) and np.all(actual[~valid] == 0)
                    assert np.isclose(actual.sum(), 0) or np.isclose(actual.sum(), 1)
                    maximum_weight_error = max(maximum_weight_error, error)
                    weight_cases.append({'case': case, 'block': block, 'rows': size,
                                         'valid_rows': int(valid.sum()), 'uses_draw': use_draw,
                                         'maximum_absolute_error': error})
            tests['vectorized_weights_equal_independent_loop_under_missingness_and_draws'] = {
                'passed': True, 'seed': 2026102401, 'n_comparisons': len(weight_cases),
                'blocks': [3, 7, 14], 'maximum_absolute_error': maximum_weight_error,
                'tolerance': {'rtol': 1e-12, 'atol': 1e-14},
                'cases_include': ['empty input', 'all invalid', 'unequal year/process sizes',
                                  'missing draw years', 'zero year multiplicity', 'zero/missing process multiplicity'],
                'case_digest_sha256': digest(json.dumps(weight_cases, sort_keys=True).encode())}

            rows = []
            for year in range(2021, 2026):
                for group in range(3):
                    for row in range(2):
                        rows.append({'year': year, 'day_offset': -30 + 7 * group + row,
                                     'sample_id': f'{year}-{group}-{row}', 'process_id': f'{year}-p{group}'})
            meta = pd.DataFrame(rows)
            values = rng.normal(size=(len(meta), 4))
            target = np.array([1., 2., -1., 1.5])
            fit = namespace['fit_matrix'](values, meta, range(4), target=target)
            spectrum = []
            for alpha in (.1, .5, .9):
                fitted_precision, condition = namespace['precision_fit'](fit, alpha)
                fitted_covariance = np.linalg.inv(fitted_precision)
                smallest = float(np.linalg.eigvalsh(fitted_covariance).min())
                assert smallest >= alpha - 1e-10
                assert np.linalg.eigvalsh(fitted_precision).min() > 0
                assert np.isfinite(condition)
                spectrum.append({'alpha': alpha, 'minimum_covariance_eigenvalue': smallest, 'condition_number': condition})
            tests['shrinkage_positive_definiteness'] = {'passed': True, 'spectra': spectrum}

            # Explicitly exercise the effective number of distinct resampled years.
            year_checks = []
            diagnostic_mismatch = []
            for unique_years in (3, 4, 5):
                draw = {year: {'count': 1, 'processes': {0: 1, 1: 1, 2: 1}}
                        for year in range(2021, 2021 + unique_years)}
                scores, _, info = namespace['b_scores'](values, target, meta, contract, .5, draw)
                count = sum(bool(np.isfinite(value)) for value in scores.values())
                assert count == (0 if unique_years == 3 else 2)
                year_checks.append({'active_distinct_years': unique_years,
                                    'finite_family_scores': count,
                                    'reported_unweighted_calibration_support': info['calibration_support']})
                if unique_years == 4:
                    reported = info['calibration_support']['a']['n_observed_years']
                    diagnostic_mismatch.append({'active_years': 4, 'expected_positive_weight_calibration_years': 4,
                                                'expected_positive_weight_calibration_rows': 24,
                                                'reported_unweighted_calibration_years': int(reported),
                                                'reported_unweighted_calibration_rows': int(info['calibration_support']['a']['n_observed_rows'])})
            tests['B_crossfit_effective_year_requirement'] = {'passed': True, 'cases': year_checks}

            # Holdout perturbation cannot change that holdout fold's training fit.
            original_fit_matrix = namespace['fit_matrix']
            captured = []
            def capture_training_fit(array, metadata, *args, **kwargs):
                result = original_fit_matrix(array, metadata, *args, **kwargs)
                if result is not None and set(metadata.year.unique()) == {2022, 2023, 2024, 2025}:
                    captured.append({key: result[key].copy() for key in ['ids', 'median', 'scale', 'mean', 'z', 'weights']})
                return result
            namespace['fit_matrix'] = capture_training_fit
            try:
                namespace['b_scores'](values, target, meta, contract, .5)
                altered = values.copy()
                altered[meta.year.to_numpy() == 2021] = 1000000.0
                namespace['b_scores'](altered, target, meta, contract, .5)
            finally:
                namespace['fit_matrix'] = original_fit_matrix
            assert len(captured) == 2
            errors = {key: float(np.max(np.abs(captured[0][key] - captured[1][key]))) for key in captured[0]}
            assert all(error == 0 for error in errors.values())
            tests['B_fold_training_fit_ignores_heldout_values'] = {'passed': True, 'heldout_year': 2021,
                                                                 'maximum_parameter_errors': errors}

            missing = values.copy()
            missing[0, :2] = np.nan
            _, _, missing_info = namespace['b_scores'](missing, target, meta, contract, .5)
            support = missing_info['calibration_support']
            assert support['a']['n_observed_rows'] == 29 and support['b']['n_observed_rows'] == 30
            tests['B_unobserved_holdout_family_not_counted_as_observed_contribution'] = {'passed': True, 'support': support}

            # Midrank/fractional inclusion under full and boundary ties.
            ties = namespace['ranking']({f'f{i}': .5 for i in range(9)})
            credit = {family: namespace['top5_credit'](ties, family) for family in ties}
            assert set(ties.values()) == {5.0}
            assert np.isclose(sum(credit.values()), 5)
            assert all(np.isclose(value, 5 / 9) for value in credit.values())
            boundary = namespace['ranking']({'f0': 1., 'f1': .9, 'f2': .8, 'f3': .7,
                                             'f4': .6, 'f5': .6, 'f6': .6, 'f7': .5, 'f8': .4})
            boundary_credit = {family: namespace['top5_credit'](boundary, family) for family in boundary}
            assert np.isclose(sum(boundary_credit.values()), 5)
            assert all(np.isclose(boundary_credit[family], 1 / 3) for family in ['f4', 'f5', 'f6'])
            tests['midranks_and_fractional_TOP5_boundary'] = {
                'passed': True, 'fully_tied_rank': 5., 'fully_tied_each_credit': 5 / 9,
                'total_credit': float(sum(credit.values())), 'boundary_tie_credit': boundary_credit}

            # Compare production purge to explicit intersecting hourly label sets.
            anchors = pd.date_range('2021-08-01 02:30:00+00:00', periods=18, freq='D')
            purge_meta = pd.DataFrame({'year': 2021, 'day_offset': np.arange(18) - 30,
                                       'anchor_time_utc': anchors.astype(str),
                                       'process_id': ['test' if i in (7, 8) else f'other{i}' for i in range(18)]})
            _, heldout, purged = namespace['select_train'](purge_meta, None, ('process', 'test'))
            labels = [set(pd.date_range(anchor - pd.Timedelta(hours=168), anchor, freq='h', inclusive='left').ceil('h'))
                      for anchor in anchors]
            expected = np.array([not heldout[i] and any(labels[i] & labels[j] for j in np.flatnonzero(heldout))
                                 for i in range(len(purge_meta))])
            assert np.array_equal(purged, expected)
            tests['purge_equals_actual_168_hour_label_intersection'] = {
                'passed': True, 'heldout_rows': int(heldout.sum()), 'purged_rows': int(purged.sum()),
                'note': 'Same-clock hourly-label supports; does not certify the original instrument averaging intervals.'}

            # B's main fit is also C's fit; the private reuse cache must not leak.
            fit_calls = []
            original_fit_matrix = namespace['fit_matrix']
            def count_fit(array, metadata, *args, **kwargs):
                fit_calls.append(len(metadata))
                return original_fit_matrix(array, metadata, *args, **kwargs)
            namespace['fit_matrix'] = count_fit
            try:
                _, reusable_info = namespace['routes'](values, target, meta, contract)
            finally:
                namespace['fit_matrix'] = original_fit_matrix
            assert len(fit_calls) == 6  # one primary fit plus five out-of-year fits
            assert '_fit_for_routes' not in reusable_info['b_info']
            json.dumps(reusable_info, allow_nan=False)
            tests['B_C_fit_reuse_is_private_and_serializable'] = {
                'passed': True, 'fit_call_count': len(fit_calls), 'training_rows_per_fit': fit_calls,
                'private_fit_cache_removed_from_public_info': True}

            # Self-family target values never enter that family's matching metric.
            _, first_detail = namespace['routes'](values, target, meta, contract, save_detail=True)
            altered_target = target.copy()
            altered_target[:2] = [7., -7.]
            _, second_detail = namespace['routes'](values, altered_target, meta, contract, save_detail=True)
            first_matches = [item['selected_sample_id'] for item in first_detail['analogs'] if item['family_id'] == 'a']
            second_matches = [item['selected_sample_id'] for item in second_detail['analogs'] if item['family_id'] == 'a']
            assert first_matches == second_matches and len(first_matches) == 10
            tests['C_matching_excludes_evaluated_family'] = {'passed': True, 'selected_sample_ids': first_matches}
            matching_missing = values.copy()
            matching_missing[0, 2:] = np.nan
            _, missing_detail = namespace['routes'](matching_missing, target, meta, contract, save_detail=True)
            selected = [item for item in missing_detail['analogs'] if item['family_id'] == 'a']
            assert selected and all(item['selected_sample_id'] != meta.iloc[0].sample_id for item in selected)
            minimum_support = min(item['observed_outside_family_matching_fraction'] for item in selected)
            assert minimum_support >= .8
            tests['C_matching_rejects_unobserved_outside_family_row'] = {
                'passed': True, 'rejected_sample_id': meta.iloc[0].sample_id,
                'minimum_selected_matching_support': minimum_support}
            collected_warnings = sorted({str(item.message) for item in caught})

        report['known_limitations'] = [
            {'issue': 'Under bootstrap draw weights, calibration_support currently reports finite unweighted calibration rows, including zero-weight unsampled years.',
             'observed_example': diagnostic_mismatch,
             'impact': 'Scores use the correctly reweighted finite ECDF; current production covariance_diagnostics exports only draw=None, where this discrepancy does not arise. No production code changed by review.',
             'future_action': 'Intersect finite calibration rows with positive draw weights before exporting bootstrap-specific effective support, or label unweighted diagnostic counts explicitly.'},
            {'issue': 'The tests do not establish real-event discrimination, physical causality, sample independence or empirical hazard coverage.',
             'impact': 'Numerical helper correctness is separate from scientific validation.'}
        ]
        report['source_sha256_at_end'] = digest(SOURCE.read_bytes())
        report['source_unchanged_during_review'] = report['source_sha256_at_end'] == source_hash
        assert report['source_unchanged_during_review'], 'Production source changed during numerical review; rerun against final bytes.'
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    report['warnings'] = collected_warnings
    report['finished_at_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': report['passed'], 'test_groups': len(report['tests']),
                      'output': str(OUTPUT), 'bytes': OUTPUT.stat().st_size,
                      'sha256': digest(OUTPUT.read_bytes())}, ensure_ascii=False), flush=True)
    if not report['passed']:
        print(report.get('error', 'unknown review error'), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    run()
