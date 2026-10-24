#!/usr/bin/env python3
"""Independent, read-only fixed-risk audit. Writes only in this review folder.
No physical integration. Artificial function cases are software tests only.
"""
from __future__ import annotations
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent
N = D.parent
O = N.parent
R = D.parents[3]
BASE = R / 'scripts/applicability_sensitivity.py'
SRC = R / 'scripts/applicability_fixed_risk.py'
POLICY = 'fixed_history_risk_out_of_domain_to_unknown'
DIAG = 'revoke_out_of_domain_history_classification_diagnostic'
KEYS = ['issue_time', 'forecast_input_mode', 'space_object', 'assumed_latency_hours',
        'model_id', 'mechanism_id', 'law_policy', 'horizon_hours', 'probability_prior']
COND = ['probability_start_within_horizon', 'probability_no_start_within_horizon',
        'probability_start_lower', 'probability_start_upper',
        'probability_no_start_lower', 'probability_no_start_upper',
        'conditional_lower_hours', 'conditional_median_hours', 'conditional_upper_hours']


def rec(p):
    h = hashlib.sha256()
    with p.open('rb') as s:
        for b in iter(lambda: s.read(4194304), b''):
            h.update(b)
    return dict(path=str(p.relative_to(R)), bytes=p.stat().st_size, sha256=h.hexdigest())


def close(x, y):
    return bool(np.allclose(x, y, rtol=1e-12, atol=1e-12))


def functions():
    ns = {'np': np, 'pd': pd}
    for path, fn, constants in [(BASE, 'summarize', ('PRIORS', 'POLICIES')),
                                (SRC, 'fixed_summary', ('POLICY', 'DIAG'))]:
        keep = [x for x in ast.parse(path.read_text()).body if
                isinstance(x, ast.FunctionDef) and x.name == fn or
                isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in x.targets)]
        exec(compile(ast.Module(body=keep, type_ignores=[]), str(path), 'exec'), ns)
    return ns


def frame(risk, domain, point=None, length=72):
    n = len(risk)
    return pd.DataFrame(dict(initial_margin_at_issue=np.ones(n),
                            known_at_risk_under_conditional_history=risk,
                            strength_domain_fraction_observed=domain,
                            crossing_point_hours_after_issue=[np.nan] * n if point is None else point,
                            followup_hours=[length] * n, mechanism_id=['S'] * n,
                            parameter_set_id=[f'test_only_{i}' for i in range(n)]))


def boundary(ns):
    fn, original, prior = ns['fixed_summary'], ns['summarize'], ns['PRIORS'][0]
    out = {}
    x = fn(frame([False], [0]), 72, prior)
    out['outdomain_original_past_stays_past_not_unknown'] = x['already_started_prior_mass'] == 1 and x['at_risk_prior_mass'] == 0 and x['unresolved_future_prior_mass'] == 0
    out['empty_original_risk_has_all_conditionals_null'] = all(x[k] is None for k in COND)
    x = fn(frame([True], [0], [12]), 72, prior)
    out['outdomain_original_event_to_unknown'] = x['event_prior_mass'] == 0 and x['unresolved_future_prior_mass'] == 1 and x['event_mass_transferred_to_unknown'] == 1 and x['probability_start_within_horizon'] is None and x['probability_start_upper'] == 1
    x = fn(frame([True], [0]), 72, prior)
    out['outdomain_original_noevent_to_unknown'] = x['no_start_prior_mass'] == 0 and x['unresolved_future_prior_mass'] == 1 and x['no_start_mass_transferred_to_unknown'] == 1
    x = fn(frame([True], [1], length=24), 72, prior)
    out['short_followup_stays_unknown'] = x['unresolved_future_prior_mass'] == 1 and x['probability_start_within_horizon'] is None
    x = fn(frame([True], [1]), 72, prior)
    out['indomain_complete_nonfailure_p0_no_interval'] = x['probability_start_within_horizon'] == 0 and x['conditional_lower_hours'] is None
    x = fn(frame([True], [1], [12]), 72, prior)
    out['indomain_event_retained_with_its_time'] = x['probability_start_within_horizon'] == 1 and x['conditional_lower_hours'] == 12 and x['conditional_upper_hours'] == 12
    f = frame([True, True, False], [1, 0, 0], [np.nan, 12, np.nan])
    fixed, diag = fn(f, 72, prior), original(f, 72, prior, 'out_of_domain_mass_to_unknown')
    out['fixed_risk_and_history_revocation_bounds_distinguished'] = abs(fixed['at_risk_prior_mass'] - 2 / 3) < 1e-12 and abs(fixed['already_started_prior_mass'] - 1 / 3) < 1e-12 and abs(fixed['probability_start_upper'] - .5) < 1e-12 and abs(diag['probability_start_upper'] - 2 / 3) < 1e-12
    return {k: bool(v) for k, v in out.items()}


def main():
    paths = [SRC, BASE, N / 'PROTOCOL.md', N / 'input_registration.json',
             O / 'predictions.csv.gz', N / 'fixed_history_risk_predictions.csv.gz',
             N / 'five_policy_predictions.csv.gz', N / 'fixed_and_revoked_history_mass_comparison.csv.gz',
             N / 'summary.json', N / 'aggregation_validation.json',
             O / 'review_boundary/final_readonly_audit.json']
    inputs = [rec(p) for p in paths]
    old = pd.read_csv(paths[4], low_memory=False)
    fixed = pd.read_csv(paths[5], low_memory=False)
    combined = pd.read_csv(paths[6], low_memory=False)
    transfers = pd.read_csv(paths[7], low_memory=False)
    source = old[old.applicability_policy.eq('original_design')]
    pair = fixed.merge(source, on=KEYS, suffixes=('_fixed', '_original'), validate='one_to_one')
    checks = {
        '60750_fixed_rows_exactly_matched_to_original': len(fixed) == len(pair) == len(source) == 60750,
        '303750_rows_five_unambiguous_policy_names': len(combined) == 303750 and combined.applicability_policy.nunique() == 5 and combined.groupby('applicability_policy').size().eq(60750).all(),
        'primary_policy_named_fixed_history': fixed.applicability_policy.eq(POLICY).all(),
        'fixed_risk_prior_mass_unchanged': close(pair.at_risk_prior_mass_fixed, pair.at_risk_prior_mass_original),
        'already_started_prior_mass_unchanged': close(pair.already_started_prior_mass_fixed, pair.already_started_prior_mass_original),
        'original_past_never_transferred_to_unknown': fixed.already_started_mass_transferred_to_unknown.eq(0).all(),
        'original_weights_not_filtered_or_renormalized': close(fixed.original_prior_mass_retained, 1) and fixed.zero_weight_scenario_count.eq(0).all(),
        'risk_event_no_unknown_partition_closed': close(fixed.event_prior_mass + fixed.no_start_prior_mass + fixed.unresolved_future_prior_mass, fixed.at_risk_prior_mass),
        'fixed_risk_plus_past_closed': close(fixed.at_risk_prior_mass + fixed.already_started_prior_mass, 1),
        'event_transfer_equals_original_event_mass_lost': close(pair.event_mass_transferred_to_unknown, pair.event_prior_mass_original - pair.event_prior_mass_fixed),
        'noevent_transfer_equals_original_noevent_mass_lost': close(pair.no_start_mass_transferred_to_unknown, pair.no_start_prior_mass_original - pair.no_start_prior_mass_fixed),
        'unknown_is_original_unknown_plus_event_no_transfers_only': close(pair.unresolved_future_prior_mass_fixed, pair.unresolved_future_prior_mass_original + pair.event_mass_transferred_to_unknown + pair.no_start_mass_transferred_to_unknown),
        'all_actual_positive_unknown_probability_is_null': fixed.loc[fixed.unresolved_future_prior_mass.gt(0), ['probability_start_within_horizon', 'probability_no_start_within_horizon']].isna().all().all(),
        'empty_original_risk_all_conditionals_null': fixed.loc[fixed.at_risk_prior_mass.eq(0), COND].isna().all().all(),
        'zero_event_support_all_time_quantiles_null': fixed.loc[fixed.event_physical_design_count.eq(0), ['conditional_lower_hours', 'conditional_median_hours', 'conditional_upper_hours']].isna().all().all(),
        'fixed_role_still_scenario_no_truth_no_available_time': fixed.data_role.eq('scenario').all() and fixed.empirical_coverage.isna().all() and fixed.independent_observed_events.eq(0).all() and fixed.available_time.isna().all()
    }
    positive = fixed.at_risk_prior_mass.gt(0)
    checks['fixed_bounds_use_exact_original_risk_denominator'] = close(fixed.loc[positive, 'probability_start_lower'], fixed.loc[positive, 'event_prior_mass'] / fixed.loc[positive, 'at_risk_prior_mass']) and close(fixed.loc[positive, 'probability_start_upper'], (fixed.loc[positive, 'event_prior_mass'] + fixed.loc[positive, 'unresolved_future_prior_mass']) / fixed.loc[positive, 'at_risk_prior_mass'])
    checks['fixed_noevent_bounds_are_complements'] = close(fixed.loc[positive, 'probability_no_start_lower'], 1 - fixed.loc[positive, 'probability_start_upper']) and close(fixed.loc[positive, 'probability_no_start_upper'], 1 - fixed.loc[positive, 'probability_start_lower'])
    for field in ['original_at_risk_count', 'positive_weight_at_risk_count', 'positive_weight_at_risk_physical_design_count', 'at_risk_physical_design_ESS']:
        checks[field + '_unchanged'] = close(pair[field + '_fixed'], pair[field + '_original'])
    # Preserve all original four-policy numbers and metadata; only rename the
    # original fourth row's policy to an explicit diagnostic in the new table.
    renamed = old.copy()
    renamed.loc[renamed.applicability_policy.eq('out_of_domain_mass_to_unknown'), 'applicability_policy'] = DIAG
    prior_rows = combined[combined.applicability_policy.ne(POLICY)]
    legacy = renamed.merge(prior_rows, on=KEYS + ['applicability_policy'], suffixes=('_old', '_new'), validate='one_to_one')
    nullsame, equal, maxdiff = {}, {}, {}
    for field in old.columns:
        if field in KEYS + ['applicability_policy']:
            continue
        x, y = legacy[field + '_old'], legacy[field + '_new']
        nullsame[field] = bool(x.isna().equals(y.isna()))
        if pd.api.types.is_numeric_dtype(x.dtype) and not pd.api.types.is_bool_dtype(x.dtype):
            delta = (pd.to_numeric(x) - pd.to_numeric(y)).abs().dropna()
            maxdiff[field] = float(delta.max()) if len(delta) else 0.
            equal[field] = maxdiff[field] < 1e-12
        else:
            equal[field] = bool(x.fillna('<NULL>').astype(str).equals(y.fillna('<NULL>').astype(str)))
    checks['all_243000_legacy_rows_preserved_except_explicit_policy_rename'] = len(legacy) == len(old) == 243000 and all(nullsame.values()) and all(equal.values())
    diag = combined[combined.applicability_policy.eq(DIAG)]
    dp = fixed.merge(diag, on=KEYS, suffixes=('_fixed', '_diagnostic'), validate='one_to_one')
    checks['diagnostic_risk_reincludes_only_outdomain_past'] = close(dp.at_risk_prior_mass_diagnostic, dp.at_risk_prior_mass_fixed + dp.out_of_domain_originally_already_started_mass_fixed)
    checks['diagnostic_unknown_adds_exact_revoked_past'] = close(dp.unresolved_future_prior_mass_diagnostic, dp.unresolved_future_prior_mass_fixed + dp.out_of_domain_originally_already_started_mass_fixed)
    defined = dp.probability_start_lower_fixed.notna() & dp.probability_start_lower_diagnostic.notna()
    checks['additional_history_revocation_bounds_enclose_fixed_bounds'] = bool((dp.loc[defined, 'probability_start_lower_diagnostic'] <= dp.loc[defined, 'probability_start_lower_fixed'] + 1e-12).all() and (dp.loc[defined, 'probability_start_upper_diagnostic'] >= dp.loc[defined, 'probability_start_upper_fixed'] - 1e-12).all())
    mix = fixed[fixed.model_id.eq('mechanism_policy_mixture')]
    tkeys = [x for x in KEYS if x not in ('model_id', 'mechanism_id', 'law_policy')]
    t = mix.merge(transfers, on=tkeys, validate='one_to_one')
    checks['6750_explicit_transfer_rows_match_main_mixture'] = len(t) == len(transfers) == 6750
    for transfer_field, main_field in [('fixed_risk_unknown_mass', 'unresolved_future_prior_mass'),
                                     ('fixed_risk_known_event_mass', 'event_prior_mass'),
                                     ('fixed_risk_known_no_start_mass', 'no_start_prior_mass'),
                                     ('fixed_risk_already_started_mass', 'already_started_prior_mass')]:
        checks[transfer_field + '_matches_main'] = close(t[transfer_field], t[main_field])
    checks['transfer_table_original_past_never_revoked_in_primary'] = transfers.fixed_risk_already_started_mass_transferred_to_unknown.eq(0).all()
    registration = json.loads(paths[3].read_text())
    for p in [SRC, BASE, N / 'PROTOCOL.md', O / 'predictions.csv.gz']:
        registered = next(x for x in registration['inputs'] if x['path'].endswith(str(p.relative_to(R))))
        checks['registered_hash_matches_' + p.name] = registered['sha256'] == rec(p)['sha256']
    checks['old_review_boundary_final_bytes_unchanged'] = rec(paths[-1])['sha256'] == '295890c9eac30af04037be616a47a0b5c09817d5dc75a9f0150f49b1fcb6c406'
    metadata = json.loads(paths[8].read_text())
    checks['summary_distinguishes_primary_and_secondary_policies'] = metadata['primary_policy'] == POLICY and metadata['secondary_history_revocation_diagnostic'] == DIAG
    edges = boundary(functions())
    report = dict(reviewed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  scope='read-only parent source/output audit; writes only new risk_set_revision/review; no physics and no old review modification',
                  artificial_edge_inputs_are_research_data=False, review_script=rec(Path(__file__)), inputs=inputs,
                  boundary_checks=edges, actual_output_checks={k: bool(v) for k, v in checks.items()},
                  legacy_null_patterns_preserved=nullsame, legacy_fields_equal=equal, legacy_maximum_absolute_difference=maxdiff,
                  fixed_rows=len(fixed), combined_rows=len(combined), explicit_transfer_rows=len(transfers),
                  fixed_precise_probability_rows=int(fixed.probability_start_within_horizon.notna().sum()),
                  fixed_upper_min=float(fixed.probability_start_upper.min()), fixed_upper_max=float(fixed.probability_start_upper.max()),
                  diagnostic_upper_min=float(diag.probability_start_upper.min()),
                  maximum_risk_mass_difference=float(abs(pair.at_risk_prior_mass_fixed - pair.at_risk_prior_mass_original).max()),
                  maximum_past_mass_difference=float(abs(pair.already_started_prior_mass_fixed - pair.already_started_prior_mass_original).max()),
                  limitations=['Fixed original history classification is a conditional assumption, not a validation of all previous domain states.',
                               'Future averaged domain flags imply retrospective selection including post-cross continuation, not an operational gate.',
                               'The secondary history-revocation envelope answers a different risk-set question and must not replace the primary fixed-risk comparison.',
                               'Neither zero retained event support nor a numerical probability bound establishes local safety or calibrated risk.'])
    report['passed'] = all(edges.values()) and all(checks.values())
    target = D / 'final_fixed_risk_audit.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': report['passed'], 'boundary_checks': len(edges), 'actual_output_checks': len(checks), 'output': str(target.relative_to(R))}))
    assert report['passed'], report


if __name__ == '__main__':
    main()
