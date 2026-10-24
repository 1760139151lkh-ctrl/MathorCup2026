#!/usr/bin/env python3
"""Independent read-only review. Writes only beside this script; no physics.

Artificial edge inputs below are software/audit cases, never research events.
The parent summarize function is AST-extracted without running its main/imports.
--complete also checks all actual output rows against the frozen base table.
"""
from __future__ import annotations
import argparse
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

D = Path(__file__).resolve().parent
R = D.parents[2]
A = R / 'results/applicability_sensitivity'
F = R / 'results/mechanistic_replay/analytic_erfc'
SRC = R / 'scripts/applicability_sensitivity.py'
KEYS = ['issue_time', 'forecast_input_mode', 'space_object', 'assumed_latency_hours',
        'model_id', 'mechanism_id', 'law_policy', 'horizon_hours', 'probability_prior']
FIELDS = ['probability_start_within_horizon', 'probability_no_start_within_horizon',
          'probability_start_lower', 'probability_start_upper',
          'probability_no_start_lower', 'probability_no_start_upper',
          'conditional_lower_hours', 'conditional_median_hours', 'conditional_upper_hours',
          'conditional_interval_level', 'already_started_prior_mass', 'at_risk_prior_mass',
          'event_prior_mass', 'no_start_prior_mass', 'unresolved_future_prior_mass']
CONDITIONAL = ['probability_start_within_horizon', 'probability_no_start_within_horizon',
               'probability_start_lower', 'probability_start_upper',
               'probability_no_start_lower', 'probability_no_start_upper',
               'conditional_lower_hours', 'conditional_median_hours', 'conditional_upper_hours']


def record(p):
    h = hashlib.sha256()
    with p.open('rb') as s:
        for b in iter(lambda: s.read(4194304), b''):
            h.update(b)
    return {'path': str(p.relative_to(R)), 'bytes': p.stat().st_size, 'sha256': h.hexdigest()}


def extracted():
    tree = ast.parse(SRC.read_text())
    keep = [x for x in tree.body if
            isinstance(x, ast.FunctionDef) and x.name == 'summarize' or
            isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and
                                             t.id in ('PRIORS', 'POLICIES') for t in x.targets)]
    ns = {'np': np, 'pd': pd}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(SRC), 'exec'), ns)
    return ns


def test_frame(risk, domain, point=None, length=72):
    n = len(risk)
    return pd.DataFrame(dict(initial_margin_at_issue=np.ones(n),
                            known_at_risk_under_conditional_history=risk,
                            crossing_point_hours_after_issue=[np.nan] * n if point is None else point,
                            followup_hours=[length] * n, strength_domain_fraction_observed=domain,
                            parameter_set_id=[f'test_only_p{i}' for i in range(n)], mechanism_id=['S'] * n))


def edge_review(ns):
    fn, policies, prior = ns['summarize'], ns['POLICIES'], ns['PRIORS'][0]
    checks = {}
    x = fn(test_frame([True], [1]), 72, prior, policies[0])
    checks['complete_nonfailure_p0_no_time_interval'] = x['probability_start_within_horizon'] == 0 and x['conditional_lower_hours'] is None
    x = fn(test_frame([True], [1], length=24), 72, prior, policies[0])
    checks['short_followup_unknown_not_noevent'] = x['probability_start_within_horizon'] is None and x['probability_start_lower'] == 0 and x['probability_start_upper'] == 1
    x = fn(test_frame([True], [0]), 72, prior, policies[1])
    checks['zero_total_weights_all_conditionals_null'] = all(x[k] is None for k in CONDITIONAL) and x['identification_status'] == 'no_positive_total_weight'
    x = fn(test_frame([False], [1]), 72, prior, policies[0])
    checks['empty_risk_all_conditionals_null'] = all(x[k] is None for k in CONDITIONAL) and x['identification_status'] == 'no_positive_at_risk_weight'
    x = fn(test_frame([False], [0]), 72, prior, policies[3])
    checks['outdomain_past_to_state_unknown'] = x['at_risk_prior_mass'] == 1 and x['unresolved_future_prior_mass'] == 1 and x['probability_start_within_horizon'] is None and x['probability_start_lower'] == 0 and x['probability_start_upper'] == 1 and x['original_history_already_started_prior_mass'] == 1
    f = test_frame([True, True, True, False], [1, 1, 1, 0], [12, np.nan, np.nan, np.nan])
    # Generic summarizer branch case; parent actual batches separately enforce a
    # common followup. These artificial rows are never inserted in actual data.
    f.loc[2, 'followup_hours'] = 24
    x = fn(f, 72, prior, policies[3])
    checks['mixed_possible_risk_bounds'] = x['probability_start_lower'] == .25 and x['probability_start_upper'] == .75 and x['probability_start_within_horizon'] is None
    checks['mixed_partition_mass_closed'] = abs(x['event_prior_mass'] + x['no_start_prior_mass'] + x['unresolved_future_prior_mass'] - x['at_risk_prior_mass']) < 1e-15
    return {k: bool(v) for k, v in checks.items()}


def granularity():
    n, smallest, err, max_l = 0, 1., 0., 0
    for b in pq.ParquetFile(F / 'parameter_first_passages.parquet').iter_batches(
            batch_size=65536, columns=['strength_domain_fraction_observed', 'followup_hours']):
        d, length = b.column(0).to_numpy(), b.column(1).to_numpy()
        n += len(d)
        if np.any(d > 0):
            smallest = min(smallest, float(d[d > 0].min()))
        max_l = max(max_l, int(length.max()))
        err = max(err, float(abs(d * (length + 1) - np.rint(d * (length + 1))).max()))
    floor = float(np.exp(-10) / 2048 * smallest)
    return dict(rows=n, maximum_followup_hours=max_l, minimum_positive_factor=smallest,
                maximum_integer_count_residual=err, conservative_positive_weight_floor=floor,
                tolerance=1e-12, passed=bool(n == 1536000 and max_l == 72 and err < 1e-12 and floor > 1e-12),
                scope='frozen binary-state means and original clipped-margin priors only; not arbitrary future weighting')


def complete_review():
    pred = pd.read_csv(A / 'predictions.csv.gz', low_memory=False)
    base = pd.read_csv(F / 'predictions.csv.gz', low_memory=False)
    original = pred[pred.applicability_policy.eq('original_design')]
    paired = original.merge(base, on=KEYS, suffixes=('_new', '_old'), validate='one_to_one')
    differences, nulls = {}, {}
    for field in FIELDS:
        x, y = paired[field + '_new'], paired[field + '_old']
        nulls[field] = bool(x.isna().equals(y.isna()))
        d = (x - y).abs().dropna()
        differences[field] = float(d.max()) if len(d) else 0.
    checks = {'four_policies_243000_rows': len(pred) == 243000 and pred.applicability_policy.nunique() == 4,
              'every_policy_60750': bool(pred.groupby('applicability_policy').size().eq(60750).all()),
              'original_all_keys_and_15_numeric_fields_reproduced': len(base) == len(original) == len(paired) == 60750 and all(nulls.values()) and max(differences.values()) < 1e-12}
    positive_total = pred.original_prior_mass_retained.gt(0)
    checks['past_risk_mass_partition'] = bool(np.allclose(pred.loc[positive_total, 'already_started_prior_mass'] + pred.loc[positive_total, 'at_risk_prior_mass'], 1, rtol=1e-12, atol=1e-12))
    checks['event_no_unknown_partition'] = bool(np.allclose(pred.event_prior_mass + pred.no_start_prior_mass + pred.unresolved_future_prior_mass, pred.at_risk_prior_mass, rtol=1e-12, atol=1e-12))
    checks['all_empty_risk_conditionals_null'] = bool(pred.loc[pred.at_risk_prior_mass.eq(0), CONDITIONAL].isna().all().all())
    checks['all_zero_total_conditionals_null'] = bool(pred.loc[~positive_total, CONDITIONAL].isna().all().all())
    checks['any_actual_positive_unknown_never_exact'] = bool(pred.loc[pred.unresolved_future_prior_mass.gt(0), ['probability_start_within_horizon', 'probability_no_start_within_horizon']].isna().all().all())
    zero_event = pred.event_physical_design_count.eq(0)
    checks['zero_event_support_all_time_quantiles_null'] = bool(pred.loc[zero_event, ['conditional_lower_hours', 'conditional_median_hours', 'conditional_upper_hours']].isna().all().all())
    checks['no_validation_or_operational_claim_added'] = bool(pred.empirical_coverage.isna().all() and pred.independent_observed_events.eq(0).all() and pred.available_time.isna().all() and not bool(pred.operational_filter_approved.any()))
    w = pred[pred.applicability_policy.eq('out_of_domain_mass_to_unknown')]
    joined = w.merge(original, on=KEYS, suffixes=('_fourth', '_original'), validate='one_to_one')
    e = joined.event_prior_mass_original - joined.event_prior_mass_fourth
    no = joined.no_start_prior_mass_original - joined.no_start_prior_mass_fourth
    past = joined.already_started_prior_mass_original - joined.already_started_prior_mass_fourth
    checks['fourth_original_weights_unchanged'] = bool(np.allclose(w.original_prior_mass_retained, 1, rtol=1e-12, atol=1e-12) and w.zero_weight_scenario_count.eq(0).all())
    checks['fourth_risk_reincludes_exact_outdomain_past'] = bool(np.allclose(joined.at_risk_prior_mass_fourth, joined.at_risk_prior_mass_original + joined.out_of_domain_originally_already_started_mass_fourth, rtol=1e-12, atol=1e-12))
    checks['fourth_transferred_classes_are_nonnegative'] = bool((e >= -1e-12).all() and (no >= -1e-12).all() and (past >= -1e-12).all())
    checks['fourth_unknown_mass_contains_all_transfers'] = bool(np.allclose(joined.unresolved_future_prior_mass_fourth, joined.unresolved_future_prior_mass_original + e + no + past, rtol=1e-12, atol=1e-12))
    ix = w.at_risk_prior_mass.gt(0)
    lo = w.loc[ix, 'event_prior_mass'] / w.loc[ix, 'at_risk_prior_mass']
    hi = (w.loc[ix, 'event_prior_mass'] + w.loc[ix, 'unresolved_future_prior_mass']) / w.loc[ix, 'at_risk_prior_mass']
    checks['fourth_possible_risk_bounds_formula'] = bool(np.allclose(w.loc[ix, 'probability_start_lower'], lo, rtol=1e-12, atol=1e-12) and np.allclose(w.loc[ix, 'probability_start_upper'], hi, rtol=1e-12, atol=1e-12))
    valid = pred.probability_start_lower.notna()
    checks['bounds_in_unit_interval_ordered'] = bool((pred.loc[valid, 'probability_start_lower'] >= -1e-12).all() and (pred.loc[valid, 'probability_start_upper'] <= 1 + 1e-12).all() and (pred.loc[valid, 'probability_start_lower'] <= pred.loc[valid, 'probability_start_upper'] + 1e-12).all())
    checks['complementary_no_event_bounds'] = bool(np.allclose(pred.loc[valid, 'probability_no_start_lower'], 1 - pred.loc[valid, 'probability_start_upper'], rtol=1e-12, atol=1e-12) and np.allclose(pred.loc[valid, 'probability_no_start_upper'], 1 - pred.loc[valid, 'probability_start_lower'], rtol=1e-12, atol=1e-12))
    return dict(checks={k: bool(v) for k, v in checks.items()}, original_null_patterns_equal=nulls,
                original_maximum_absolute_differences=differences, actual_prediction_rows=len(pred),
                actual_empty_risk_rows=int(pred.at_risk_prior_mass.eq(0).sum()),
                actual_zero_total_rows=int((~positive_total).sum()),
                actual_positive_unknown_rows=int(pred.unresolved_future_prior_mass.gt(0).sum()),
                passed=all(checks.values()))


def mass_review():
    pred = pd.read_csv(A / 'predictions.csv.gz', low_memory=False)
    mass = pd.read_csv(A / 'mixture_mechanism_masses.csv.gz', low_memory=False)
    transfer = pd.read_csv(A / 'conservative_mass_transfers.csv.gz', low_memory=False)
    keys = ['issue_time', 'forecast_input_mode', 'space_object', 'assumed_latency_hours', 'probability_prior']
    mix = pred[pred.model_id.eq('mechanism_policy_mixture')]
    mkeys = keys + ['applicability_policy']
    grouped = mass.groupby(mkeys, dropna=False)
    totals = grouped[['original_mixture_mechanism_mass', 'new_mixture_mechanism_mass',
                      'original_at_risk_mechanism_mass', 'new_possible_at_risk_mechanism_mass',
                      'original_domain_outside_mass']].sum().reset_index()
    totals['retained_factor_unique_count'] = grouped.original_full_group_prior_mass_retained.nunique().to_numpy()
    totals['retained_factor'] = grouped.original_full_group_prior_mass_retained.first().to_numpy()
    paired = totals.merge(mix[mix.horizon_hours.eq(24)], on=mkeys, validate='one_to_one')
    close = lambda x, y: bool(np.allclose(x, y, rtol=1e-12, atol=1e-12))
    checks = {
        '36000_mechanism_rows_9000_mixture_groups': len(mass) == 36000 and len(paired) == 9000,
        'four_distinct_mechanisms_every_mixture_group': bool(grouped.mechanism_id.nunique().eq(4).all()),
        'original_mechanism_mass_sum_one': close(paired.original_mixture_mechanism_mass, 1),
        'new_mechanism_mass_sum_one_or_zero': close(paired.new_mixture_mechanism_mass, paired.original_prior_mass_retained.gt(0).astype(float)),
        'new_possible_risk_mass_matches_main': close(paired.new_possible_at_risk_mechanism_mass, paired.at_risk_prior_mass),
        'original_outdomain_mass_matches_main': close(paired.original_domain_outside_mass, paired.out_of_domain_prior_mass),
        'retained_mass_matches_main': bool(paired.retained_factor_unique_count.eq(1).all()) and close(paired.retained_factor, paired.original_prior_mass_retained)
    }
    original = mix[mix.applicability_policy.eq('original_design')]
    reference = original[original.horizon_hours.eq(24)][keys + ['at_risk_prior_mass']].rename(columns={'at_risk_prior_mass': 'original_main_risk'})
    original_pairs = totals.merge(reference, on=keys, validate='many_to_one')
    checks['original_risk_mass_matches_original_main'] = close(original_pairs.original_at_risk_mechanism_mass, original_pairs.original_main_risk)
    tkeys = keys + ['horizon_hours']
    fourth = mix[mix.applicability_policy.eq('out_of_domain_mass_to_unknown')]
    t = transfer.merge(fourth, on=tkeys, validate='one_to_one')
    checks['6750_transfer_rows_all_matched'] = len(transfer) == len(t) == 6750
    for field, target in [('conservative_unknown_mass', 'unresolved_future_prior_mass'),
                          ('conservative_known_event_mass', 'event_prior_mass'),
                          ('conservative_known_no_start_mass', 'no_start_prior_mass'),
                          ('conservative_known_past_mass', 'already_started_prior_mass')]:
        checks[field + '_matches_main'] = close(t[field], t[target])
    baseline = original[tkeys + ['event_prior_mass', 'no_start_prior_mass', 'unresolved_future_prior_mass', 'already_started_prior_mass']]
    t = t.merge(baseline, on=tkeys, suffixes=('', '_original'), validate='one_to_one')
    for field, source in [('original_event_mass', 'event_prior_mass_original'),
                          ('original_no_start_mass', 'no_start_prior_mass_original'),
                          ('original_future_unknown_mass', 'unresolved_future_prior_mass_original'),
                          ('original_already_started_mass', 'already_started_prior_mass_original')]:
        checks[field + '_matches_original'] = close(t[field], t[source])
    reconstructed_unknown = t.original_future_unknown_mass + t.event_mass_transferred_to_unknown + t.no_start_mass_transferred_to_unknown + t.already_started_mass_transferred_to_state_unknown
    checks['unknown_transfer_no_loss_or_double_count'] = close(reconstructed_unknown, t.conservative_unknown_mass)
    checks['event_no_past_transfer_equal_class_losses'] = close(t.event_mass_transferred_to_unknown, t.original_event_mass - t.conservative_known_event_mass) and close(t.no_start_mass_transferred_to_unknown, t.original_no_start_mass - t.conservative_known_no_start_mass) and close(t.already_started_mass_transferred_to_state_unknown, t.original_already_started_mass - t.conservative_known_past_mass)
    return dict(checks={k: bool(v) for k, v in checks.items()}, passed=all(checks.values()),
                mixture_mechanism_rows=len(mass), mixture_groups=len(paired), mass_transfer_rows=len(transfer),
                scope='independent table-to-main-mass reconciliation plus source reading; no physics rerun')


def protocol_review():
    binding = json.loads((A / 'protocol_snapshot_binding.json').read_text())
    snapshot = R.parents[3] / binding['snapshot_path']
    registration = json.loads((A / 'input_registration.json').read_text())
    registered_protocol = next(x for x in registration['inputs'] if x['path'].endswith('/PROTOCOL.md'))
    registered_source = next(x for x in registration['inputs'] if x['path'].endswith('/scripts/applicability_sensitivity.py'))
    checks = dict(execution_protocol_snapshot_matches_bound_hash=record(snapshot)['sha256'] == binding['executed_protocol_sha256'],
                  registration_protocol_matches_bound_execution=registered_protocol['sha256'] == binding['executed_protocol_sha256'],
                  reviewed_main_source_matches_executed_source=record(SRC)['sha256'] == registered_source['sha256'])
    return dict(checks=checks, passed=all(checks.values()), snapshot=record(snapshot),
                note='Current explanation is a later revision; executed protocol snapshot and original registration are separately retained.')


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--complete', action='store_true')
    args = cli.parse_args()
    sources = [SRC, A / 'PROTOCOL.md', F / 'parameter_first_passages.parquet', F / 'predictions.csv.gz']
    out = dict(reviewed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
               scope='read-only source/output audit; only review_boundary files written; no physics or parent output modified',
               artificial_edge_inputs_are_research_data=False, review_script=record(Path(__file__)),
               inputs=[record(p) for p in sources], edge_checks=edge_review(extracted()), domain_granularity=granularity())
    if args.complete:
        out['complete_actual_output_review'] = complete_review()
        out['explicit_mechanism_and_transfer_tables'] = mass_review()
        out['protocol_version_binding'] = protocol_review()
        out['inputs'].extend(record(p) for p in [A / 'predictions.csv.gz', A / 'summary.json',
                                               A / 'mixture_mechanism_masses.csv.gz', A / 'conservative_mass_transfers.csv.gz',
                                               A / 'input_registration.json', A / 'protocol_snapshot_binding.json',
                                               R / 'scripts/applicability_mass_audit.py'])
    out['status'] = 'complete_actual_output_review' if args.complete else 'boundary_review_only_actual_outputs_not_checked_in_this_run'
    out['limitations'] = [
        'All domain-fraction selection is retrospective and uses future scenario states, not an operational eligibility gate.',
        'Fourth-policy bounds condition on the stated retained in-domain original-history classification; forecast-domain validity alone does not certify all earlier history.',
        'E/(R+U) and (E+V+U)/(R+U) are coherent possible-risk bounds under those classifications; neither is a local population-risk guarantee.',
        'No event support does not establish safety; null and unresolved masses must remain visible.',
        'Only temperature/effective-stress experimental-domain flags are audited, not complete material or slow-creep applicability.'
    ]
    out['passed'] = all(out['edge_checks'].values()) and out['domain_granularity']['passed'] and (not args.complete or all(out[k]['passed'] for k in ['complete_actual_output_review', 'explicit_mechanism_and_transfer_tables', 'protocol_version_binding']))
    target = D / ('final_readonly_audit.json' if args.complete else 'boundary_checks.json')
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': str(target.relative_to(R)), 'passed': out['passed'], 'status': out['status']}))
    assert out['passed'], out


if __name__ == '__main__':
    main()
