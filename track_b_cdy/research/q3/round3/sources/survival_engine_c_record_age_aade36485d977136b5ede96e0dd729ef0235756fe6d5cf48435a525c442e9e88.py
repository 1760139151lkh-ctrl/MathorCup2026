#!/usr/bin/env python3
"""Causal landmark survival competition on independently grouped real series.

No fabricated failures/nonfailures.  Poisson piecewise-exponential likelihood
contains the actual at-risk duration and one event at most per physical group.
All preprocessing, regularization selection and cross-fit rate calibration use
the outer training groups only.  Forecast covariates are frozen at issue time.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

ROUND = Path(__file__).resolve().parents[1]
ROOT = ROUND.parents[3]
OUT = ROUND / "results/engine_c"
FEATURES = ["log_relative_velocity", "log_recent_velocity_ratio", "log_monitoring_age_hours"]
MODELS = ["linear_dynamic_hazard", "nonlinear_rbf_hazard"]
PENALTIES = [0.1, 1.0, 10.0]
SEED = 20261024
MAX_NODES = 512
ANCHORS_ONLY = False


def minimize_newton(objective, init):
    beta = init.copy()
    success, message = False, "iteration_limit"
    for iteration in range(80):
        loss, grad, hess = objective(beta)
        if np.max(np.abs(grad)) < 1e-7:
            success, message = True, "gradient_converged"
            break
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hess + np.eye(len(beta)) * 1e-8, grad, rcond=None)[0]
        scale = 1.
        while scale > 1e-8:
            trial = beta - scale * step
            if objective(trial)[0] <= loss - 1e-4 * scale * float(grad @ step):
                break
            scale *= .5
        beta = trial
        if np.max(np.abs(scale * step)) < 1e-7:
            success, message = True, "step_converged"
            break
    return SimpleNamespace(x=beta, success=success, message=message, iterations=iteration + 1)


def golden_scalar(objective, low=-6., high=6.):
    ratio = (math.sqrt(5.) - 1.) / 2
    a, b = high - ratio * (high - low), low + ratio * (high - low)
    fa, fb = objective(a), objective(b)
    for _ in range(55):
        if fa < fb:
            high, b, fb = b, a, fa
            a = high - ratio * (high - low); fa = objective(a)
        else:
            low, a, fa = a, b, fb
            b = low + ratio * (high - low); fb = objective(b)
    return (low + high) / 2


def prepare_stampa():
    """Canonicalize the fixed public Stampa pre-collapse monitoring record."""
    sources = json.loads((ROUND / "results/survival_sources.json").read_text())
    source = next(r for r in sources if "/data/stampa.csv" in r["canonical_url"] and r.get("status") == 200)
    raw = Path(source["path"])
    if hashlib.sha256(raw.read_bytes()).hexdigest() != "c11d1589f6ffe7971577844481792837bb58826fd2fc33d04a483e222c774ba5":
        raise RuntimeError("fixed Stampa data hash mismatch")
    data = pd.read_csv(raw)
    dates = pd.to_datetime(data.time)
    t = (dates - dates.iloc[0]).dt.total_seconds() / 3600
    dest = ROUND / "inputs/survival"
    dest.mkdir(parents=True, exist_ok=True)
    # One fixed target sensor.  Base is another part of the same physical chain,
    # not a second independent unfailed site.
    observations = pd.DataFrame({"site_id": "stampa_block4a", "event_group": "Stampa_rocksection4a",
                                 "time_relative_hours": t, "time_utc": "", "displacement": data.block4a,
                                 "unit": "source_displacement_unit_not_explicit_in_CSV_dimensionless_features_only",
                                 "observed": data.block4a.notna(), "source_date": data.time})
    observations.to_csv(dest / "stampa_observations.csv", index=False)
    pd.DataFrame([{"site_id": "stampa_block4a", "event_group": "Stampa_rocksection4a", "start_hours": float(t.min()),
                   "end_hours": float(t.max()), "followup_end_hours": float(t.max()),
                   "failure_time_hours": None, "failure_lower_hours": None, "failure_upper_hours": None,
                   "event_observed": False, "censoring_verified": True,
                   "risk_status": "external_catastrophic_collapse_at_risk_already_slow_moving",
                   "physical_phase": "catastrophic_collapse_external_not_first_mechanical_motion",
                   "label_source": "https://www.nature.com/articles/s41598-026-48268-x",
                   "label_semantics": "right_censored_at_last_record_2022-11-27; article_documents_two_stage_collapse_July2023; no_exact_failure_time_assigned",
                   "time_origin": str(dates.iloc[0].date()), "time_zone": "unknown_calendar_dates_only"}]).to_csv(dest / "stampa_site_registry.csv", index=False)
    jsave(OUT / "stampa_audit.json", {
        "physical_groups": 1, "selected_sensor": "Block4a", "same_chain_sensor_not_independent": "Base",
        "daily_rows": len(data), "finite_block4a_rows": int(data.block4a.notna().sum()),
        "first_date": str(dates.min().date()), "last_date": str(dates.max().date()),
        "relative_span_hours": float(t.max()), "source_csv_sha256": source["sha256"],
        "catastrophic_failure_not_within_record": "article documents collapse in July2023, after November2022 record end",
        "first_mechanical_initiation": "already moving; label not supplied; external collapse phase only",
        "data_licence": "repository MIT software licence does not independently establish third_party_measurement_data_licence",
        "weather_columns": "retained only in raw cache; not survival predictors; soil_moisture and infiltration are HBV-model outputs",
    })


def jsave(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def truth(value):
    return str(value).strip().lower() in {"true", "1", "1.0", "yes"}


def finite(value):
    try:
        v = float(value)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def causal_features(t, d, j):
    """Only indices <= j.  Dimensionless velocities avoid sensor-unit mixing."""
    if j < 5:
        return None
    # Fixed finite past window avoids quadratic memory/runtime on high-frequency
    # records.  No future-fitted smoothing or whole-series scale is used.
    tt, dd = t[max(0, j - 63):j + 1], d[max(0, j - 63):j + 1]
    velocity = np.diff(dd) / np.diff(tt)
    recent = abs(float(np.polyfit(tt[-6:] - tt[-1], dd[-6:], 1)[0]))
    baseline = float(np.median(np.abs(velocity)))
    previous = float(np.median(np.abs(velocity[-11:-5]))) if len(velocity) >= 11 else baseline
    eps = max(baseline * 1e-6, 1e-12)
    return np.array([
        np.clip(np.log((recent + eps) / (baseline + eps)), -12, 12),
        np.clip(np.log((recent + eps) / (previous + eps)), -12, 12),
        np.log1p(max(t[j] - t[0], 0)),
    ])


def load_data(obs_path, reg_path, administrative_fraction=None, supplement_obs=None, supplement_reg=None):
    obs, registry = pd.read_csv(obs_path), pd.read_csv(reg_path)
    if supplement_obs is not None:
        obs = pd.concat([obs, pd.read_csv(supplement_obs)], ignore_index=True)
        registry = pd.concat([registry, pd.read_csv(supplement_reg)], ignore_index=True)
    required = {"site_id", "event_group", "time_relative_hours", "displacement"}
    if not required <= set(obs):
        raise ValueError(f"observations missing {required - set(obs)}")
    selected, audit, intervals = {}, [], []
    for group, rows in registry.groupby("event_group", sort=True):
        # Fixed lexical sensor, independent of event timing or model performance.
        candidates = sorted(rows.site_id.astype(str).unique())
        site = candidates[0]
        r = rows[rows.site_id.astype(str) == site].iloc[0]
        s = obs[obs.site_id.astype(str) == site].copy()
        if "observed" in s:
            s = s[s.observed.map(truth)]
        s["time_relative_hours"] = pd.to_numeric(s.time_relative_hours, errors="coerce")
        s["displacement"] = pd.to_numeric(s.displacement, errors="coerce")
        s = s.dropna(subset=["time_relative_hours", "displacement"])
        s = s.sort_values("time_relative_hours").drop_duplicates("time_relative_hours")
        t, d = s.time_relative_hours.to_numpy(float), s.displacement.to_numpy(float)
        a = {"event_group": str(group), "selected_site_id": site, "candidate_sensors": candidates,
             "selection": "lexicographic_sensor_predefined_not_best_forecast", "observations": len(t)}
        if str(group) == "Veslemannen" or ("primary_evaluation_eligible" in r and not truth(r.get("primary_evaluation_eligible")) and pd.notna(r.get("primary_evaluation_eligible"))):
            a.update(status="excluded", reason="unresolved_curator_clock_alignment_primary_evaluation_ineligible")
            audit.append(a)
            continue
        if len(t) < 7:
            a.update(status="excluded", reason="fewer_than_7_finite_unique_observations")
            audit.append(a)
            continue
        fail = finite(r.get("failure_time_hours"))
        lower = finite(r.get("failure_lower_hours"))
        upper = finite(r.get("failure_upper_hours"))
        lower = lower if lower is not None else fail
        upper = upper if upper is not None else fail
        event = truth(r.get("event_observed", False))
        registry_end = finite(r.get("end_hours"))
        followup = finite(r.get("followup_end_hours"))
        end = followup if followup is not None else (registry_end if registry_end is not None else t[-1])
        # 'event_observed' alone cannot silently extend monitored follow-up.
        if event and (lower is None or upper is None):
            a.update(status="excluded", reason="event_true_without_failure_time")
            audit.append(a)
            continue
        if lower is not None and lower <= t[0]:
            a.update(status="excluded", reason="left_censored_or_already_unstable_at_first_observation")
            audit.append(a)
            continue
        event_in_followup = bool(event and lower is not None and upper is not None and upper <= end + 1e-8)
        original_event_in_followup = event_in_followup
        if event_in_followup:
            end = upper
        label = str(r.get("label_semantics", "unspecified"))
        status = str(r.get("risk_status", ""))
        if status in {"left_censored", "already_unstable", "outcome_unknown", "not_at_risk"}:
            a.update(status="excluded", reason=status, label_semantics=label)
            audit.append(a)
            continue
        if not event_in_followup and not truth(r.get("censoring_verified", False)):
            a.update(status="excluded", reason="no_verified_event_or_censor_followup", label_semantics=label)
            audit.append(a)
            continue
        if administrative_fraction is not None:
            # Preregistered retrospective censoring view of real observations.
            # The record end is for experiment selection only, never a feature.
            administrative_end = float(t[0] + administrative_fraction * (t[-1] - t[0]))
            keep = t <= administrative_end
            t, d = t[keep], d[keep]
            if len(t) < 7:
                a.update(status="excluded", reason="fewer_than_7_observations_after_administrative_censor")
                audit.append(a)
                continue
            end, event_in_followup, event, fail = administrative_end, False, False, None
            lower, upper = None, None
            r = r.copy()
            r["censoring_verified"] = True
            label += ";administrative_censoring_simulation_not_new_nonfailure"
        if event_in_followup:
            # Observations inside an uncertain failure-label interval must not
            # become confidently pre-event predictor observations.
            keep = t <= lower
            t, d = t[keep], d[keep]
            if len(t) < 7:
                a.update(status="excluded", reason="insufficient_unambiguously_prefailure_observations")
                audit.append(a)
                continue
        t0 = t[5]
        if end <= t0:
            a.update(status="excluded", reason="no_exposure_after_causal_feature_warmup")
            audit.append(a)
            continue
        # Interval left endpoints use the last genuinely observed state.
        risk_stop = lower if event_in_followup else end
        edges = sorted(set([float(v) for v in t[5:] if v < risk_stop] + [float(risk_stop)]))
        original_edges_count = len(edges)
        if len(edges) > MAX_NODES + 1:
            edge_indices = np.unique(np.linspace(0, len(edges) - 1, MAX_NODES + 1).round().astype(int))
            edges = [edges[k] for k in edge_indices]
        rows_c = []
        for left, right in zip(edges[:-1], edges[1:]):
            j = int(np.searchsorted(t, left, side="right") - 1)
            x = causal_features(t, d, j)
            if x is None or right <= left:
                continue
            record = {"event_group": str(group), "site_id": site, "start_hours": left,
                      "end_hours": right, "exposure_hours": right - left,
                      "event": int(event_in_followup and upper == lower and abs(right - end) < 1e-7),
                      "event_kind": "exact" if event_in_followup and upper == lower and abs(right - end) < 1e-7 else "survival",
                      "last_observation_hours": float(t[j]),
                      "observation_age_hours": left - float(t[j])}
            record.update(zip(FEATURES, x))
            rows_c.append(record)
        if event_in_followup and upper > lower:
            j = int(np.searchsorted(t, lower, side="right") - 1)
            x = causal_features(t, d, j)
            record = {"event_group": str(group), "site_id": site, "start_hours": float(lower),
                      "end_hours": float(upper), "exposure_hours": float(upper - lower),
                      "event": 1, "event_kind": "interval", "last_observation_hours": float(t[j]),
                      "observation_age_hours": float(lower - t[j])}
            record.update(zip(FEATURES, x)); rows_c.append(record)
        if not rows_c:
            a.update(status="excluded", reason="empty_at_risk_intervals")
            audit.append(a)
            continue
        selected[str(group)] = dict(site=site, t=t, d=d, end=float(end), event=event_in_followup,
                                    fail=fail, lower=lower, upper=upper, issue_end=float(risk_stop),
                                    original_event=original_event_in_followup,
                                    time_origin_utc=r.get("time_origin_utc") if pd.notna(r.get("time_origin_utc")) else None,
                                    start=float(t0), label_semantics=label)
        intervals.extend(rows_c)
        a.update(status="accepted", feature_start_hours=float(t0), followup_end_hours=float(end),
                 event_observed_in_followup=event_in_followup,
                 censoring_verified=truth(r.get("censoring_verified", False)),
                 sensor_last_observation_hours=float(t[-1]),
                 monitored_model_exposure_hours=float(end - t0), label_semantics=label)
        a.update(failure_lower_hours=lower, failure_upper_hours=upper,
                 guaranteed_survival_exposure_hours=float(risk_stop - t0),
                 interval_label_likelihood_width_hours=float(upper - lower) if event_in_followup else 0.)
        a.update(original_risk_edge_count=original_edges_count, retained_risk_edge_count=len(edges),
                 max_survival_intervals=MAX_NODES, original_event_in_followup=original_event_in_followup)
        audit.append(a)
    return selected, pd.DataFrame(intervals), audit


class Hazard:
    def __init__(self, model, penalty):
        self.model, self.penalty = model, penalty

    def basis(self, x):
        z = np.clip((x - self.center) / self.scale, -6, 6)
        parts = [np.ones((len(z), 1)), z]
        if self.model == "nonlinear_rbf_hazard":
            parts.extend([np.exp(-0.5 * (z - k) ** 2) for k in (-1., 0., 1.)])
            parts.extend([(z[:, 0] * z[:, 1])[:, None]])
        return np.column_stack(parts)

    def fit(self, frame):
        x = frame[FEATURES].to_numpy(float)
        self.center = np.median(x, axis=0)
        self.scale = np.maximum(np.quantile(x, .75, axis=0) - np.quantile(x, .25, axis=0), .25)
        a = self.basis(x)
        exposure, y = frame.exposure_hours.to_numpy(float), frame.event.to_numpy(float)
        is_interval = frame.event_kind.to_numpy() == "interval"
        init = np.zeros(a.shape[1])
        init[0] = math.log((sum(y) + .5) / (sum(exposure) + 1.0))
        # Fixed weak intercept prior prevents all-censored degenerate estimates.
        prior_intercept = init[0]
        def objective(beta):
            eta = np.clip(a @ beta, -35, 20)
            expectation = exposure * np.exp(eta)
            reg = np.r_[.001, np.repeat(self.penalty, len(beta) - 1)]
            delta = beta.copy(); delta[0] -= prior_intercept
            losses = expectation - y * eta
            gradient_eta = expectation - y
            hessian_eta = expectation.copy()
            mu = expectation[is_interval]
            losses[is_interval] = -np.log(-np.expm1(-mu))
            derivative, curvature = np.zeros(len(mu)), np.zeros(len(mu))
            small, middle = mu < 1e-4, (mu >= 1e-4) & (mu < 50.)
            derivative[small] = -1 + mu[small] / 2 - mu[small] ** 2 / 12
            curvature[small] = mu[small] / 2 - mu[small] ** 2 / 6
            ratio = mu[middle] / np.expm1(mu[middle])
            derivative[middle] = -ratio
            curvature[middle] = -ratio + ratio ** 2 * np.exp(mu[middle])
            gradient_eta[is_interval], hessian_eta[is_interval] = derivative, np.maximum(curvature, 0.)
            loss = np.sum(losses) + .5 * np.sum(reg * delta ** 2)
            grad = a.T @ gradient_eta + reg * delta
            hess = a.T @ (hessian_eta[:, None] * a) + np.diag(reg)
            return loss, grad, hess
        fit = minimize_newton(objective, init)
        self.beta, self.success = fit.x, bool(fit.success)
        self.message = str(fit.message)
        return self

    def predict(self, x):
        return np.exp(np.clip(self.basis(np.asarray(x)) @ self.beta, -35, 20))


def score(model, frame):
    hazard = model.predict(frame[FEATURES].to_numpy(float))
    tmp = frame[["event_group", "event", "exposure_hours"]].copy()
    tmp["nll"] = likelihood_terms(hazard, frame)
    # Each physical group contributes equally to hyperparameter ranking.
    return float(tmp.groupby("event_group").nll.sum().mean())


def likelihood_terms(hazard, frame):
    mu = hazard * frame.exposure_hours.to_numpy(float)
    terms = mu - frame.event.to_numpy(float) * np.log(hazard)
    is_interval = frame.event_kind.to_numpy() == "interval"
    terms[is_interval] = -np.log(-np.expm1(-mu[is_interval]))
    return terms


def tune(frame, model):
    groups = sorted(frame.event_group.unique())
    if len(groups) < 4:
        return 1.0, [], "fixed_pre_registered_penalty_insufficient_inner_groups"
    table = []
    for penalty in PENALTIES:
        losses = []
        for held in groups:
            fit = Hazard(model, penalty).fit(frame[frame.event_group != held])
            losses.append(score(fit, frame[frame.event_group == held]))
        table.append({"penalty": penalty, "mean_inner_group_nll": float(np.mean(losses))})
    best = min(table, key=lambda row: (row["mean_inner_group_nll"], -row["penalty"]))["penalty"]
    return best, table, "inner_leave_one_physical_group_out"


def crossfit_scale(frame, model, penalty):
    groups = sorted(frame.event_group.unique())
    if len(groups) < 3:
        return 1., None, "no_calibration_insufficient_training_groups"
    expected, events, oof = 0., 0., []
    for held in groups:
        fit = Hazard(model, penalty).fit(frame[frame.event_group != held])
        target = frame[frame.event_group == held]
        hazard = fit.predict(target[FEATURES].to_numpy(float))
        expected += float(np.sum(hazard * target.exposure_hours))
        events += float(target.event.sum())
        oof.append((hazard, target))
    # Out-of-training-group predictions, still not an independent calibration set.
    def objective(gamma):
        scale = math.exp(float(gamma))
        return sum(float(likelihood_terms(h * scale, f).sum()) for h, f in oof) + .05 * float(gamma) ** 2
    gamma = golden_scalar(objective)
    return math.exp(gamma), {"events": events, "expected_events_before_scaling": expected, "optimizer_success": True}, "training_side_crossfit_likelihood_rate_scale_no_independent_coverage_guarantee"


def issue_grid(s):
    # Entire observed risk span.  Native rows retain short/high frequency scales.
    native = s["t"][(s["t"] >= s["start"]) & (s["t"] < s["issue_end"])]
    hourly = np.arange(math.ceil(s["start"]), math.ceil(s["issue_end"]), 1.)
    values = sorted(set(float(x) for x in np.r_[native, hourly] if x < s["issue_end"]))
    native_set = set(float(x) for x in native)
    if ANCHORS_ONLY:
        keep = set()
        step = float(np.median(np.diff(s["t"])))
        for h in [24., 48., 72., step, step * 3, step * 7]:
            candidates = [v for v in values if v <= s["end"] - h]
            if candidates:
                keep.add(candidates[-1])
        values = sorted(keep)
    return [(v, "native_and_hourly" if v in native_set and abs(v - round(v)) < 1e-9 else "native" if v in native_set else "hourly") for v in values]


def conditional_quantile(hazard, horizon, q):
    p = -math.expm1(-hazard * horizon)
    return -math.log1p(-q * p) / hazard


def censor_km(frame):
    follow = frame.groupby("event_group").agg(start=("start_hours", "min"), end=("end_hours", "max"), event=("event", "max"))
    durations = (follow.end - follow.start).to_numpy(float)
    censored = (1 - follow.event).to_numpy(int)
    table, survival = [], 1.
    for tm in sorted(set(durations)):
        at_risk = int(np.sum(durations >= tm))
        dc = int(np.sum((durations == tm) & (censored == 1)))
        survival *= 1 - dc / at_risk
        table.append((float(tm), float(survival)))
    def g(value, left=False):
        valid = [surv for tm, surv in table if tm < value or (not left and tm <= value)]
        return valid[-1] if valid else 1.
    return g


def main():
    global OUT, MAX_NODES, ANCHORS_ONLY
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", type=Path, default=ROUND / "inputs/deformation/observations.csv")
    parser.add_argument("--registry", type=Path, default=ROUND / "inputs/deformation/site_registry.csv")
    parser.add_argument("--supplement-observations", type=Path, default=ROUND / "inputs/survival/stampa_observations.csv")
    parser.add_argument("--supplement-registry", type=Path, default=ROUND / "inputs/survival/stampa_site_registry.csv")
    parser.add_argument("--administrative-censor-fraction", type=float, choices=[.5, .75])
    parser.add_argument("--prepare-stampa", action="store_true", help="offline fixed-source canonicalization only")
    parser.add_argument("--max-nodes", type=int, choices=[512, 1024], default=512)
    parser.add_argument("--anchors-only", action="store_true", help="fixed anchors only for preregistered 1024-grid sensitivity")
    args = parser.parse_args()
    if ROOT != Path("/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3"):
        raise RuntimeError("wrong execution root")
    if not (ROUND / "EXPERIMENT_PROTOCOL.md").exists():
        raise RuntimeError("experiment must be registered before computation")
    if args.prepare_stampa:
        OUT.mkdir(parents=True, exist_ok=True)
        prepare_stampa()
        return
    MAX_NODES, ANCHORS_ONLY = args.max_nodes, args.anchors_only
    if args.administrative_censor_fraction is not None:
        if not (ROUND / "EXPERIMENT_AMENDMENT_CENSOR.md").exists():
            raise RuntimeError("administrative censor amendment must be registered")
        OUT = OUT / f"administrative_censor_{args.administrative_censor_fraction:g}"
    if MAX_NODES != 512:
        OUT = OUT / f"nodes_{MAX_NODES}"
    OUT.mkdir(parents=True, exist_ok=True)
    use_supplement = args.supplement_observations.exists() and args.supplement_registry.exists()
    selected, intervals, audit = load_data(args.observations, args.registry, args.administrative_censor_fraction,
                                         args.supplement_observations if use_supplement else None,
                                         args.supplement_registry if use_supplement else None)
    jsave(OUT / "exposure_audit.json", audit)
    if intervals.empty or len(selected) < 2:
        jsave(OUT / "execution_status.json", {"status": "no_supervised_competition", "reason": "fewer_than_2_verified_groups", "audited_groups": len(audit), "accepted_groups": len(selected)})
        return
    intervals.to_csv(OUT / "risk_intervals.csv", index=False)
    cache = Path("/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/survival")
    cache.mkdir(parents=True, exist_ok=True)
    run_fingerprint = hashlib.sha256((hashlib.sha256(args.observations.read_bytes()).hexdigest() +
                       hashlib.sha256(args.registry.read_bytes()).hexdigest() +
                       hashlib.sha256(Path(__file__).read_bytes()).hexdigest() + str(args)).encode()).hexdigest()
    prediction_path = cache / f"engine_c_{run_fingerprint[:16]}.partial.csv.gz"
    folds, fits, checks = [], [], []
    prediction_count = 0
    with prediction_path.open("wb") as binary, gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0) as compressed, io.TextIOWrapper(compressed, newline="") as stream:
        writer = None
        for held, s in selected.items():
            train = intervals[intervals.event_group != held]
            test = intervals[intervals.event_group == held]
            train_groups = sorted(train.event_group.unique())
            for group in selected:
                folds.append({"fold_id": f"C_LOSO_{held}", "event_group": group, "site_id": selected[group]["site"], "role": "validation" if group == held else "training_hyperparameter_crossfit_calibration"})
            g = censor_km(train)
            median_step = float(np.median(np.diff(s["t"])))
            horizons = [(float(h), "common_hours") for h in (24, 48, 72)]
            horizons += [(median_step * n, f"native_{n}_median_steps") for n in (1, 3, 7)]
            for model_name in MODELS:
                penalty, tuning, tuning_status = tune(train, model_name)
                fit = Hazard(model_name, penalty).fit(train)
                scale, cal_counts, cal_status = crossfit_scale(train, model_name, penalty)
                n_cal = len(train_groups)
                conformal_rank = math.ceil((n_cal + 1) * .95)
                fits.append({"fold_id": f"C_LOSO_{held}", "held_group": held, "model_id": model_name, "training_groups": train_groups,
                             "selected_penalty": penalty, "tuning": tuning, "tuning_status": tuning_status,
                             "center": fit.center.tolist(), "scale": fit.scale.tolist(), "coefficients": fit.beta.tolist(),
                             "optimizer_success": fit.success, "optimizer_message": fit.message,
                             "heldout_survival_nll_raw": score(fit, test),
                             "training_failure_groups": int(train.groupby("event_group").event.max().sum()),
                             "test_failure_groups": int(test.event.sum()),
                             "test_exposure_hours": float(test.exposure_hours.sum()),
                             "rate_calibration_scale": scale, "calibration_counts": cal_counts, "calibration_status": cal_status,
                             "conformal_calibration_groups_upper_bound": n_cal, "conformal_95_rank": conformal_rank,
                             "conformal_95_status": "unbounded_insufficient_groups" if conformal_rank > n_cal else "not_run_no_independent_calibration_set"})
                for issue, grid_role in issue_grid(s):
                    j = int(np.searchsorted(s["t"], issue, side="right") - 1)
                    x = causal_features(s["t"], s["d"], j)
                    raw = float(fit.predict(x[None, :])[0])
                    for calibrated in (False, True):
                        hazard = raw * scale if calibrated else raw
                        for horizon, horizon_role in horizons:
                            p = -math.expm1(-hazard * horizon)
                            lo, med, hi = [conditional_quantile(hazard, horizon, q) for q in (.025, .5, .975)]
                            failure_in_horizon = bool(s["event"] and s["upper"] <= issue + horizon)
                            known_negative = bool(issue + horizon < s["lower"]) if s["event"] else bool(issue + horizon <= s["end"])
                            known = failure_in_horizon or known_negative
                            y = int(failure_in_horizon) if known else None
                            event_lower_offset = s["lower"] - issue if s["event"] else None
                            event_upper_offset = s["upper"] - issue if s["event"] else None
                            event_offset = event_lower_offset if s["event"] and s["lower"] == s["upper"] else None
                            cutoff = float(s["t"][j])
                            origin_utc = s.get("time_origin_utc")
                            if origin_utc:
                                origin = datetime.fromisoformat(str(origin_utc).replace("Z", "+00:00"))
                                issue_utc = (origin + timedelta(hours=issue)).astimezone(timezone.utc).isoformat()
                                cutoff_utc = (origin + timedelta(hours=cutoff)).astimezone(timezone.utc).isoformat()
                            else:
                                issue_utc, cutoff_utc = "", ""
                            elapsed = issue - s["start"]
                            at_issue = g(elapsed, left=True)
                            denominator = g(event_upper_offset + elapsed, left=True) if failure_in_horizon else g(elapsed + horizon)
                            ipcw = at_issue / denominator if known and denominator > 1e-12 else None
                            row = {"engine": "C", "model_id": model_name + ("_crossfit_calibrated" if calibrated else "_raw"),
                                   "mechanism_id": "empirical_causal_deformation_hazard",
                                   "experiment_id": "C_LOSO_survival_competition",
                                   "scenario_id": "C_real_" + held + ("_administrative_" + str(args.administrative_censor_fraction) if args.administrative_censor_fraction is not None else ""),
                                   "geometry_version": "external_sensor_series_no_spatial_geometry",
                                   "parameter_version": f"C_LOSO_{held}_penalty_{penalty:g}",
                                   "fold_id": f"C_LOSO_{held}", "event_group": held, "site_id": s["site"],
                                   "issue_time_utc": issue_utc, "information_cutoff_utc": cutoff_utc, "issue_relative_hours": issue,
                                   "information_cutoff_relative_hours": cutoff, "observation_age_hours": issue - cutoff,
                                   "issue_grid_role": grid_role, "horizon_hours": horizon, "horizon_role": horizon_role,
                                   "hazard_per_hour": hazard, "probability_start_within_horizon": p,
                                   "probability_no_start_within_horizon": 1 - p,
                                   "conditional_median_offset_hours": med, "conditional_lower95_offset_hours": lo,
                                   "conditional_upper95_offset_hours": hi, "conditional_interval_level": .95,
                                   "interval_semantics": "model_internal_given_failure_within_horizon_frozen_covariates",
                                   "event_within_horizon": y, "outcome_known": known,
                                   "failure_offset_hours": event_offset,
                                   "failure_lower_offset_hours": event_lower_offset, "failure_upper_offset_hours": event_upper_offset,
                                   "followup_remaining_hours": s["end"] - issue,
                                   "right_censored": not s["event"], "ipcw_weight_training_censor_km": ipcw,
                                   "brier_known_outcome": (p - y) ** 2 if known else None,
                                   "logloss_known_outcome": -(y * math.log(max(p, 1e-15)) + (1 - y) * math.log(max(1 - p, 1e-15))) if known else None,
                                   "brier_lower_bound": (p - y) ** 2 if known else min(p * p, (1 - p) ** 2),
                                   "brier_upper_bound": (p - y) ** 2 if known else max(p * p, (1 - p) ** 2),
                                   "conditional_interval_covers": lo <= event_lower_offset and event_upper_offset <= hi if failure_in_horizon else None,
                                   "conditional_interval_overlaps": lo <= event_upper_offset and event_lower_offset <= hi if failure_in_horizon else None,
                                   "conditional_interval_width_hours": hi - lo,
                                   "evaluation_stratum": "conditional_scenario" if args.administrative_censor_fraction is not None else "external_transfer",
                                   "administrative_censor_fraction": args.administrative_censor_fraction,
                                   "data_role": "site_heldout_validation",
                                   "sampling_scope": "conditional_on_source_case_selection_not_population_risk",
                                   "observation_available_time": "unknown_retrospective_external_benchmark",
                                   "label_semantics": s["label_semantics"],
                                   "input_version": "stage4-r3-real-deformation-canonical"}
                            if writer is None:
                                writer = csv.DictWriter(stream, fieldnames=list(row))
                                writer.writeheader()
                            writer.writerow(row)
                            prediction_count += 1
                            if cutoff > issue + 1e-9 or not (-1e-12 <= p <= 1 + 1e-12):
                                checks.append({"issue": issue, "cutoff": cutoff, "p": p})
            print(f"completed held group {held}: train={len(train_groups)} groups", flush=True)
    pd.DataFrame(folds).to_csv(OUT / "fold_membership.csv", index=False)
    jsave(OUT / "fit_details.json", fits)
    summarize(prediction_path, selected, intervals, prediction_count, checks, args)
    digest = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    immutable_path = cache / f"engine_c_predictions_{digest}.csv.gz"
    if immutable_path.exists():
        if hashlib.sha256(immutable_path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("cache hash collision or corruption")
        prediction_path.unlink()
    else:
        prediction_path.rename(immutable_path)
    jsave(OUT / "prediction_cache.json", {"path": str(immutable_path), "bytes": immutable_path.stat().st_size,
           "sha256": digest, "role": "all_raw_C_predictions_gzip_CSV_no_rows_dropped", "rows": prediction_count,
           "max_nodes": MAX_NODES, "anchors_only": ANCHORS_ONLY})
    plot_and_grid_comparison()


def plot_and_grid_comparison():
    table = OUT / "anchor_evaluation.csv"
    if table.exists():
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        df = pd.read_csv(table)
        fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4), layout="constrained")
        colors = {"linear_dynamic_hazard": "#007f7b", "nonlinear_rbf_hazard": "#d26a30"}
        for model, group in df.groupby("model_id"):
            base = model.replace("_raw", "").replace("_crossfit_calibrated", "")
            label = ("Linear" if base.startswith("linear") else "Nonlinear RBF") + (" + cross-fit scale" if "calibrated" in model else " raw")
            g = group.sort_values("horizon_hours")
            style = "--" if "calibrated" in model else "-"
            axes[0].plot(g.horizon_hours, g.brier, style, marker="o", color=colors[base], label=label)
            axes[1].plot(g.horizon_hours, g.conditional_coverage, style, marker="o", color=colors[base])
            axes[1].fill_between(g.horizon_hours, g.conditional_coverage, g.conditional_overlap, color=colors[base], alpha=.08)
        axes[0].set_ylabel("Brier score, observable outcomes")
        axes[1].set_ylabel("Full-label inclusion / overlap bound")
        for ax in axes:
            ax.set_xlabel("Forecast horizon (hours)")
            ax.set_xticks([24, 48, 72]); ax.grid(alpha=.2)
        axes[1].set_ylim(-.03, 1.03)
        axes[0].legend(fontsize=8)
        fig.suptitle("C: held-out physical sites; retrospective fixed anchors\nExternal terminal-collapse target; no 95% coverage guarantee", fontsize=11)
        fig.savefig(OUT / "comparison.png", dpi=160)
        plt.close(fig)
    if MAX_NODES == 1024:
        parent = OUT.parent
        coarse, fine = parent / "fit_details.json", OUT / "fit_details.json"
        if coarse.exists() and fine.exists():
            a, b = pd.DataFrame(json.loads(coarse.read_text())), pd.DataFrame(json.loads(fine.read_text()))
            merged = a[["held_group", "model_id", "heldout_survival_nll_raw"]].merge(
                b[["held_group", "model_id", "heldout_survival_nll_raw"]], on=["held_group", "model_id"], suffixes=("_512", "_1024"))
            merged["nll_1024_minus_512"] = merged.heldout_survival_nll_raw_1024 - merged.heldout_survival_nll_raw_512
            merged.to_csv(OUT / "grid_likelihood_sensitivity.csv", index=False)
        if table.exists() and (parent / "anchor_evaluation.csv").exists():
            a, b = pd.read_csv(parent / "anchor_evaluation.csv"), pd.read_csv(table)
            cols = ["model_id", "horizon_hours", "brier", "conditional_coverage", "conditional_overlap"]
            merged = a[cols].merge(b[cols], on=["model_id", "horizon_hours"], suffixes=("_512", "_1024"))
            for field in ["brier", "conditional_coverage", "conditional_overlap"]:
                merged[field + "_1024_minus_512"] = merged[field + "_1024"] - merged[field + "_512"]
            merged.to_csv(OUT / "grid_anchor_sensitivity.csv", index=False)


def summarize(path, selected, intervals, count, checks, args):
    # Chunked aggregation retains all raw forecasts without expanding memory.
    grouped, anchors = {}, {}
    group_cols = ["model_id", "event_group", "horizon_role", "horizon_hours"]
    for chunk in pd.read_csv(path, chunksize=100000):
        for key, df in chunk[chunk.horizon_role == "common_hours"].groupby(group_cols, sort=False):
            target = selected[key[1]]["end"] - float(key[3])
            eligible = df[df.issue_relative_hours <= target]
            if len(eligible):
                row = eligible.loc[eligible.issue_relative_hours.idxmax()].to_dict()
                if key not in anchors or row["issue_relative_hours"] > anchors[key]["issue_relative_hours"]:
                    anchors[key] = row
        for key, df in chunk.groupby(group_cols, dropna=False, sort=False):
            rec = grouped.setdefault(key, {"prediction_rows": 0, "known_outcomes": 0, "event_positive_rows": 0,
                                          "brier_sum": 0., "logloss_sum": 0., "brier_lower_sum": 0., "brier_upper_sum": 0.,
                                          "conditional_coverage_count": 0., "conditional_coverage_rows": 0,
                                          "conditional_overlap_count": 0.,
                                          "width_sum": 0., "ipcw_sum": 0., "ipcw_brier_sum": 0., "ipcw_rows": 0})
            known = df.brier_known_outcome.notna()
            coverage = df.conditional_interval_covers.map(lambda v: truth(v) if pd.notna(v) else np.nan)
            overlap = df.conditional_interval_overlaps.map(lambda v: truth(v) if pd.notna(v) else np.nan)
            weights = df.ipcw_weight_training_censor_km
            rec["prediction_rows"] += len(df)
            rec["known_outcomes"] += int(known.sum())
            rec["event_positive_rows"] += int((df.event_within_horizon == 1).sum())
            rec["brier_sum"] += float(df.brier_known_outcome.sum())
            rec["logloss_sum"] += float(df.logloss_known_outcome.sum())
            rec["brier_lower_sum"] += float(df.brier_lower_bound.sum())
            rec["brier_upper_sum"] += float(df.brier_upper_bound.sum())
            rec["conditional_coverage_count"] += float(coverage.sum())
            rec["conditional_overlap_count"] += float(overlap.sum())
            rec["conditional_coverage_rows"] += int(coverage.notna().sum())
            rec["width_sum"] += float(df.conditional_interval_width_hours.sum())
            rec["ipcw_rows"] += int((weights.notna() & known).sum())
            rec["ipcw_sum"] += float(weights[known].sum())
            rec["ipcw_brier_sum"] += float((weights * df.brier_known_outcome).sum())
    rows = []
    for key, r in grouped.items():
        n, nk = r["prediction_rows"], r["known_outcomes"]
        rows.append(dict(zip(group_cols, key)) | r | {
            "brier_observed_outcomes": r["brier_sum"] / nk if nk else None,
            "logloss_observed_outcomes": r["logloss_sum"] / nk if nk else None,
            "brier_all_outcome_lower_bound": r["brier_lower_sum"] / n,
            "brier_all_outcome_upper_bound": r["brier_upper_sum"] / n,
            "conditional_model_interval_coverage_rolling": r["conditional_coverage_count"] / r["conditional_coverage_rows"] if r["conditional_coverage_rows"] else None,
            "conditional_model_interval_overlap_rolling": r["conditional_overlap_count"] / r["conditional_coverage_rows"] if r["conditional_coverage_rows"] else None,
            "conditional_model_interval_mean_width_hours": r["width_sum"] / n,
            "ipcw_brier_mean_over_all_issues": r["ipcw_brier_sum"] / n,
            "ipcw_assumption": "independent_censoring_transportable_from_training_sites_not_verified",
            "independent_site_denominator": 1,
            "observed_failure_denominator": int(selected[key[1]]["event"]),
            "right_censor_denominator": int(not selected[key[1]]["event"]),
        })
    evaluation = pd.DataFrame(rows)
    evaluation.to_csv(OUT / "evaluation_by_site.csv", index=False)
    aggregate = evaluation.groupby(["model_id", "horizon_role", "horizon_hours"], dropna=False).agg(
        independent_sites=("event_group", "nunique"), observed_failure_sites=("observed_failure_denominator", "sum"),
        right_censored_sites=("right_censor_denominator", "sum"), rolling_prediction_rows=("prediction_rows", "sum"),
        equal_site_brier_known=("brier_observed_outcomes", "mean"), equal_site_logloss_known=("logloss_observed_outcomes", "mean"),
        equal_site_brier_lower_bound=("brier_all_outcome_lower_bound", "mean"),
        equal_site_brier_upper_bound=("brier_all_outcome_upper_bound", "mean"),
        equal_site_conditional_coverage=("conditional_model_interval_coverage_rolling", "mean"),
        equal_site_conditional_overlap=("conditional_model_interval_overlap_rolling", "mean"),
        mean_conditional_width_hours=("conditional_model_interval_mean_width_hours", "mean"))
    aggregate.to_csv(OUT / "evaluation.csv")
    anchor = pd.DataFrame(anchors.values())
    if len(anchor):
        anchor["anchor_semantics"] = "latest_issue_at_or_before_followup_end_minus_horizon_retrospective_case_conditioned"
        anchor.to_csv(OUT / "anchor_predictions.csv", index=False)
        anchor["failure_group"] = anchor.event_group.map(lambda k: int(selected[k]["event"]))
        anchor["censor_group"] = 1 - anchor.failure_group
        anchor["coverage_numeric"] = anchor.conditional_interval_covers.map(lambda v: float(truth(v)) if pd.notna(v) else np.nan)
        anchor["overlap_numeric"] = anchor.conditional_interval_overlaps.map(lambda v: float(truth(v)) if pd.notna(v) else np.nan)
        anchor.groupby(["model_id", "horizon_hours"]).agg(
            independent_sites=("event_group", "nunique"), failure_sites=("failure_group", "sum"),
            censored_sites=("censor_group", "sum"), known_outcomes=("brier_known_outcome", "count"),
            brier=("brier_known_outcome", "mean"), logloss=("logloss_known_outcome", "mean"),
            conditional_coverage=("coverage_numeric", "mean"), conditional_coverage_sites=("coverage_numeric", "count"),
            conditional_overlap=("overlap_numeric", "mean"),
            interval_width_hours=("conditional_interval_width_hours", "mean")).to_csv(OUT / "anchor_evaluation.csv")
    input_paths = [args.observations, args.registry, ROUND / "EXPERIMENT_PROTOCOL.md", Path(__file__)]
    if args.supplement_observations.exists() and args.supplement_registry.exists():
        input_paths += [args.supplement_observations, args.supplement_registry]
    if args.administrative_censor_fraction is not None:
        input_paths += [ROUND / "EXPERIMENT_AMENDMENT_CENSOR.md"]
    inputs = [{"path": str(p.resolve()), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in input_paths]
    summary = {"status": "completed", "seed": SEED, "real_physical_groups": len(selected),
               "observed_failure_groups": sum(s["event"] for s in selected.values()),
               "right_censored_groups": sum(not s["event"] for s in selected.values()),
               "administrative_censor_fraction": args.administrative_censor_fraction,
               "numerical_grid_max_nodes": MAX_NODES, "anchors_only": ANCHORS_ONLY,
               "evaluation_stratum": "conditional_scenario" if args.administrative_censor_fraction is not None else "external_transfer",
               "censored_groups_are_new_real_nonfailure_sites": False,
               "monitored_model_exposure_hours": float(intervals.exposure_hours.sum()),
               "guaranteed_survival_exposure_hours": float(intervals[intervals.event_kind != "interval"].exposure_hours.sum()),
               "interval_label_width_hours": float(intervals[intervals.event_kind == "interval"].exposure_hours.sum()),
               "risk_intervals": len(intervals), "raw_prediction_rows": count,
               "model_branches": 4, "future_cutoff_or_probability_violations": checks,
               "inputs": inputs, "utc": "source UTC absent retained native relative clocks",
               "limitations": ["Case-selection conditional probability, not operational population risk",
                               "Rolling rows are dependent; physical group count is the independent denominator",
                               "Frozen-covariate finite-horizon model; no measured main-region initiation truth",
                               "Model-internal conditional 95% interval is not a validated 95% coverage guarantee",
                               "Crossfit scale calibration has no independent calibration-set guarantee",
                               "Censor KM assumes transferable independent censoring; actual assumption unverified",
                               "For interval event labels IPCW censor KM uses upper endpoint as event-removal bound; report score bounds alongside it",
                               "Sensor preprocessing may have used retrospective smoothing in original data",
                               "No event label or verified censor follow-up means excluded from likelihood"]}
    jsave(OUT / "summary.json", summary)
    jsave(OUT / "validation_checks.json", {
        "future_information_cutoff_rejected": len(checks) == 0,
        "physical_groups_disjoint_per_outer_fold": all(held not in set(intervals[intervals.event_group != held].event_group) for held in selected),
        "at_most_one_event_per_physical_group": bool((intervals.groupby("event_group").event.sum() <= 1).all()),
        "risk_intervals_positive": bool((intervals.exposure_hours > 0).all()),
        "no_event_after_risk_end": all(float(intervals[intervals.event_group == group].end_hours.max()) <= s["end"] + 1e-8 for group, s in selected.items()),
        "no_synthetic_rows_added": True,
        "all_sources_real_observations_or_labels": True,
        "probability_normalization_and_bounds": len(checks) == 0,
        "conformal_guarantee_claimed": False,
        "rolling_issues_independent_sample_claimed": False,
    })
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
