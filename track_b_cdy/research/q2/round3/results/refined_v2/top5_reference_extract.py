"""No new solves: requested top5 distinct-parameter onset sensitivity extract."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_same(path, data):
    data = data.encode() if isinstance(data, str) else data
    if path.exists():
        assert path.read_bytes() == data
    else:
        path.write_bytes(data)


def interval(status, elapsed, origin):
    """Recover the native adjacent1h bracket of a first-cross interpolation.

    ceil(t)-1..ceil(t) includes exact-zero roots at the right bracket endpoint;
    never/unknown/initially unstable remain distinct and do not acquire t=0.
    """
    if str(status).startswith("left_censored"):
        return None, 0., None, origin.isoformat()
    if status != "interval_crossing" or not np.isfinite(elapsed):
        return None, None, None, None
    upper = float(math.ceil(elapsed))
    lower = max(0., upper-1.)
    return lower, upper, (origin+pd.Timedelta(hours=lower)).isoformat(), (origin+pd.Timedelta(hours=upper)).isoformat()


def run():
    bundle = BASE / "exports/mechanism_bundle_v2.json"
    bundle_sha = sha(bundle)
    assert bundle_sha == "dc53a9f805e96ff32b2c1fd064b0b7b33d90034e7d2c987f42403ae70bfcb093"
    pairs = pd.read_csv(OUT / "paired_v1_v2.csv")
    all_ref = pd.read_csv(OUT / "full_reference_checks.csv")
    ranking = (pairs.assign(abs_change=pairs.onset_elapsed_hours_delta.abs())
               .groupby("parameter_set_id_v2").abs_change.max().dropna()
               .sort_values(ascending=False).head(5))
    selected = list(ranking.index)
    result = all_ref[all_ref.parameter_set_id.isin(selected)].copy()
    result = result.merge(pairs[["base_scenario_id", "onset_status_v1", "onset_elapsed_hours_v1", "onset_elapsed_hours_v2", "onset_elapsed_hours_delta"]],
                          on="base_scenario_id", validate="one_to_one")
    assert len(result) == 40
    result["selection_parameter_v1_to_v2_max_abs_onset_shift_h"] = result.parameter_set_id.map(ranking)
    result["selection_rule"] = "top5 distinct parameter IDs ranked by max absolute finite v1(0.5m)-v2(0.125m) onset change; no new simulation"
    cfg = json.loads((OUT / "config.json").read_text())
    origin = pd.Timestamp(cfg["start_utc"])
    for prefix, status_col, elapsed_col in [("coarse_v1", "onset_status_v1", "onset_elapsed_hours_v1"),
                                            ("main_v2", "main_onset_status", "main_onset_elapsed_hours"),
                                            ("reference", "reference_onset_status", "reference_onset_elapsed_hours")]:
        bounds = pd.DataFrame([interval(row[status_col], row[elapsed_col], origin) for _, row in result.iterrows()],
                              columns=[f"{prefix}_crossing_lower_h", f"{prefix}_crossing_upper_h", f"{prefix}_crossing_lower_utc", f"{prefix}_crossing_upper_utc"], index=result.index)
        result = pd.concat([result, bounds], axis=1)
    result["branch_comparison_scope"] = "whole trajectory mismatch at -0.5C for thaw challenger; continuous law has no strength branch switch"
    result = result.sort_values(["selection_parameter_v1_to_v2_max_abs_onset_shift_h", "parameter_set_id", "law_policy", "mechanism_id"], ascending=[False, True, True, True])
    csv_path = OUT / "top5_onset_reference_checks.csv"
    write_same(csv_path, result.to_csv(index=False, lineterminator="\n"))
    finite = result.abs_onset_time_difference_hours.notna()
    maximum = result.loc[result.abs_onset_time_difference_hours.idxmax()]
    all_finite = all_ref.abs_onset_time_difference_hours.notna()
    finite_max = all_ref.loc[all_ref.abs_onset_time_difference_hours.idxmax()]
    report = dict(addendum_version="q2r3-top5-onset-reference-v1", evaluation_stratum="numerical_benchmark",
                  selection_rule="max absolute finite v1-to-v2 onset change within distinct parameter point, descending top5; include all4 mechanisms x2 policies",
                  selected_parameter_ranking=[dict(parameter_set_id=key, max_v1_v2_time_shift_h=float(value)) for key, value in ranking.items()],
                  rows=len(result), finite_main_reference_onset_pairs=int(finite.sum()),
                  no_finite_pair_count=int((~finite).sum()),
                  main_status_counts=result.main_onset_status.value_counts().to_dict(),
                  reference_status_counts=result.reference_onset_status.value_counts().to_dict(),
                  category_changes=int((~result.onset_category_same).sum()),
                  max_main_reference_onset_shift_h=float(maximum.abs_onset_time_difference_hours),
                  max_main_reference_onset_shift_base_scenario_id=maximum.base_scenario_id,
                  max_abs_margin_difference=float(result.max_abs_margin_difference.max()),
                  branch_mismatch_hours=int(result.strength_branch_mismatch_hours.sum()),
                  full256_finite_pairs=int(all_finite.sum()), full256_rows=len(all_ref),
                  full256_max_onset_shift_h=float(finite_max.abs_onset_time_difference_hours),
                  full256_max_onset_shift_base_scenario_id=finite_max.base_scenario_id,
                  full256_main_status_counts=all_ref.main_onset_status.value_counts().to_dict(),
                  source_full_reference_csv_sha256=sha(OUT / "full_reference_checks.csv"),
                  source_paired_v1_v2_csv_sha256=sha(OUT / "paired_v1_v2.csv"),
                  result_csv_sha256=sha(csv_path), script_sha256=sha(Path(__file__).resolve()),
                  mechanism_v2_bundle_sha256=bundle_sha, v2_members_unmodified=True,
                  native_time_origin_utc=origin.isoformat(), native_state_dt_hours=1.,
                  interval_semantics="adjacent model-hour crossing bracket; left-censored has only upper0, never/missing have no finite initiation; not observed onset interval",
                  branch_semantics="whole-run -0.5C switch mismatch count, not a direct observed phase transition or a claim of branch identity specifically at onset",
                  independent_observed_events=0,
                  reproduction_command="track_b/.venv/bin/python track_b/research/q2/round3/results/refined_v2/top5_reference_extract.py",
                  limitations=["This extract runs no new model solves and uses the already completed full256 paired reference audit.",
                               "Finite-time denominator includes only both-grid interval_crossing, never left-censored/no-start trajectories.",
                               "Cross-grid numerical timing difference is not a statistical confidence interval or forecast coverage.",
                               "Same crossing category does not establish precise initiation time; shallow near-threshold trajectories can switch which forcing episode first crosses."])
    assert sha(bundle) == bundle_sha
    write_same(OUT / "top5_onset_reference_summary.json", json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({key:report[key] for key in ["selected_parameter_ranking", "rows", "finite_main_reference_onset_pairs", "max_main_reference_onset_shift_h", "category_changes", "branch_mismatch_hours", "full256_finite_pairs"]}))


if __name__ == "__main__":
    run()
