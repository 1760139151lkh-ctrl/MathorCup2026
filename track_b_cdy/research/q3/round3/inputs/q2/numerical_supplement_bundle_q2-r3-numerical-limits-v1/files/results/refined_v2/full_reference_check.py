"""Supplemental full256-grid convergence audit; immutable mechanism v2 untouched.

Stored with the addendum to preserve the already hash-bound reproduction script.
No measurements, calibration, probabilities, network or other worktree access.
"""
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
ROOT = BASE.parents[3]
OUT = BASE / "results/refined_v2"
sys.path.insert(0, str(BASE / "scripts"))
from mechanism_engine import simulate, thermal_transfer, classify_trajectory
from run_experiments import parameter_design, scenario_id

EXPECTED_BUNDLE_SHA = "dc53a9f805e96ff32b2c1fd064b0b7b33d90034e7d2c987f42403ae70bfcb093"
EXPECTED_ENGINE_SHA = "bb6636d2d3f463c894cdc6bc1df9c7fd0f93f9b7a6f9aa6e8233113630afe14e"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound_members(bundle_path):
    bundle = json.loads(bundle_path.read_text())
    for item in bundle["files"]:
        path = ROOT / item["path"]
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"]
    return bundle


def emit(path, raw):
    raw = raw.encode() if isinstance(raw, str) else raw
    if path.exists():
        assert path.read_bytes() == raw, "do not mutate a prior addendum version"
    else:
        path.write_bytes(raw)


def extrema(frame, column):
    good = frame[column].dropna()
    if not len(good):
        return None
    row = frame.loc[good.idxmax()]
    return dict(value=float(row[column]), base_scenario_id=row.base_scenario_id,
                parameter_set_id=row.parameter_set_id, mechanism_id=row.mechanism_id,
                law_policy=row.law_policy)


def run():
    assert str(ROOT) == "/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2" and Path.cwd().resolve() == ROOT
    bundle_path = BASE / "exports/mechanism_bundle_v2.json"
    assert sha(bundle_path) == EXPECTED_BUNDLE_SHA
    bundle = bound_members(bundle_path)
    assert sha(BASE / "scripts/mechanism_engine.py") == EXPECTED_ENGINE_SHA
    cfg = json.loads((OUT / "config.json").read_text())
    assert cfg["dz_m"] == .125
    forcing = pd.read_csv(OUT / "forcing_hourly_v2.csv", parse_dates=["time_utc"])
    p = parameter_design(cfg)
    air, rain = forcing.station_air_temp_c.to_numpy(), forcing.precip_assumed_mm_h.to_numpy()
    print("Full reference addendum: main0.125m all256", flush=True)
    main = thermal_transfer(air, p, 1., .125, 40.)
    print("Full reference addendum: reference0.0625m all256", flush=True)
    reference = thermal_transfer(air, p, 1., .0625, 40.)
    trajectories = pd.read_parquet(OUT / "state_trajectories.parquet")
    records = []
    for policy in cfg["policies"]:
        for mechanism in cfg["models"]:
            a = simulate(air, rain, p, mechanism, policy, thermal=main)
            b = simulate(air, rain, p, mechanism, policy, thermal=reference)
            for i in range(256):
                base_id = scenario_id(i, mechanism, policy)
                x, y = a["failure_margin"][:, i], b["failure_margin"][:, i]
                status_a, status_b = classify_trajectory(x), classify_trajectory(y)
                both_cross = status_a["onset_elapsed_hours"] is not None and status_b["onset_elapsed_hours"] is not None
                absolute = np.abs(x-y)
                k = int(absolute.argmax())
                same_branch = (a["interface_temp_c"][:, i] > -.5) == (b["interface_temp_c"][:, i] > -.5)
                records.append(dict(base_scenario_id=base_id, v2_scenario_id=base_id+"__thermal125v2",
                                    parameter_set_id=f"q2r3-p{i:04d}", mechanism_id=mechanism, law_policy=policy,
                                    main_dz_m=.125, reference_dz_m=.0625, state_dt_hours=1.,
                                    max_abs_margin_difference=float(absolute.max()),
                                    max_margin_difference_elapsed_hours=k,
                                    max_margin_difference_time_utc=forcing.time_utc.iloc[k].isoformat(),
                                    final_abs_margin_difference=float(absolute[-1]),
                                    max_abs_interface_temp_difference_c=float(np.abs(a["interface_temp_c"][:, i]-b["interface_temp_c"][:, i]).max()),
                                    strength_branch_mismatch_hours=int((~same_branch).sum()) if policy == "thawed_rock_contact" else 0,
                                    same_strength_branch_max_abs_margin_difference=float(absolute[same_branch].max()) if same_branch.any() else None,
                                    main_onset_status=status_a["onset_status"], reference_onset_status=status_b["onset_status"],
                                    onset_category_same=status_a["onset_status"] == status_b["onset_status"],
                                    main_onset_elapsed_hours=status_a["onset_elapsed_hours"],
                                    reference_onset_elapsed_hours=status_b["onset_elapsed_hours"],
                                    abs_onset_time_difference_hours=abs(status_a["onset_elapsed_hours"]-status_b["onset_elapsed_hours"]) if both_cross else None,
                                    signed_onset_reference_minus_main_hours=status_b["onset_elapsed_hours"]-status_a["onset_elapsed_hours"] if both_cross else None,
                                    evaluation_stratum="numerical_benchmark"))
            for i in np.linspace(0, 255, 8, dtype=int):
                existing = trajectories[trajectories.base_scenario_id == scenario_id(i, mechanism, policy)]
                np.testing.assert_allclose(a["failure_margin"][:, i], existing.failure_margin.to_numpy(), atol=1e-12, rtol=1e-12)
            print(f"Full reference finished {policy} {mechanism}", flush=True)
    frame = pd.DataFrame(records)
    csv_path = OUT / "full_reference_checks.csv"
    emit(csv_path, frame.to_csv(index=False, lineterminator="\n"))
    groups = []
    for (mechanism, policy), group in frame.groupby(["mechanism_id", "law_policy"], sort=False):
        groups.append(dict(mechanism_id=mechanism, law_policy=policy, rows=len(group),
                           max_margin_difference=extrema(group, "max_abs_margin_difference"),
                           max_onset_difference=extrema(group, "abs_onset_time_difference_hours"),
                           category_changes=int((~group.onset_category_same).sum()),
                           margin_0p02_target_failed_n=int((group.max_abs_margin_difference>.02).sum()),
                           branch_mismatch_hours=int(group.strength_branch_mismatch_hours.sum())))
    report = dict(addendum_version="q2r3-full256-reference-audit-v1", evaluation_stratum="numerical_benchmark",
                  mechanism_v2_bundle_sha256=EXPECTED_BUNDLE_SHA, engine_sha256=EXPECTED_ENGINE_SHA,
                  all_17_v2_members_retained=True, main_grid_m=.125, reference_grid_m=.0625,
                  state_dt_hours=1., parameter_sets=256, comparisons=len(frame),
                  independent_observed_events=0, probability_weights=None,
                  time_origin_utc=forcing.time_utc.iloc[0].isoformat(),
                  max_margin_difference=extrema(frame, "max_abs_margin_difference"),
                  max_final_margin_difference=extrema(frame, "final_abs_margin_difference"),
                  max_temperature_difference=extrema(frame, "max_abs_interface_temp_difference_c"),
                  max_onset_difference=extrema(frame, "abs_onset_time_difference_hours"),
                  category_changes=int((~frame.onset_category_same).sum()),
                  categories_equal=int(frame.onset_category_same.sum()),
                  margin_0p02_target_failed_n=int((frame.max_abs_margin_difference>.02).sum()),
                  margin_0p02_target_met=bool((frame.max_abs_margin_difference<=.02).all()),
                  branch_mismatch_hours=int(frame.strength_branch_mismatch_hours.sum()), groups=groups,
                  csv_sha256=sha(csv_path), reproduction_script_sha256=sha(Path(__file__).resolve()),
                  reproduction_command="track_b/.venv/bin/python track_b/research/q2/round3/results/refined_v2/full_reference_check.py",
                  limitations=["All256 paired parameter points, not independent measured events.",
                               "Numerical cross-grid onset differences quantify this conditional discretization only, not empirical forecast coverage or observation timestamp uncertainty.",
                               "0.125m v2 is retained; actual target failures and extremes are reported without changing its already distributed bytes.",
                               "State1h and phenomenological dynamics remain fixed; linear interpolation does not claim measured subhourly initiation precision."])
    bound_members(bundle_path)
    assert sha(bundle_path) == EXPECTED_BUNDLE_SHA
    emit(OUT / "full_reference_summary.json", json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({key:report[key] for key in ["comparisons", "category_changes", "margin_0p02_target_met", "margin_0p02_target_failed_n", "max_margin_difference", "max_onset_difference", "branch_mismatch_hours"]}), flush=True)


if __name__ == "__main__":
    run()
