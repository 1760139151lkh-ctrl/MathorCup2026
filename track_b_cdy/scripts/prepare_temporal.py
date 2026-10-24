#!/usr/bin/env python3
"""Non-destructive Track B temporal standardization; no imputation or modelling.

AI assistance: Codex / OpenAI, 2026-10-23 (America/New_York user date).
Exact model/version unavailable to this script; team must complete disclosure.
Raw input bytes and numeric values are retained; strict QC0 is an explicit view,
not an assertion of physical validity, local representativeness, or real-time use.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pyarrow


SCRIPT_VERSION = "stage3-e03-v1"
QC_CODES = [0, 1, 2, 4, 8, 9]
UNIT_LABELS = {
    "m/s": "m s-1", "degree": "degree", "degree C": "degC",
    "deg C": "degC", "%": "%", "hPa": "hPa", "kPa": "kPa",
    "mm": "mm", "W/m2": "W m-2", "m3/m3": "m3 m-3",
    "g/m3": "g m-3", "m2/s2": "m2 s-2", "m": "m",
}
ROLE_LABELS = {
    "WS": "wind speed", "WD": "wind direction", "Ta": "air temperature",
    "RH": "relative humidity", "Pressure": "pressure", "Precip": "precipitation",
    "soilT": "soil temperature", "VWC": "volumetric water content", "G": "soil heat flux",
    "Ux": "wind x component", "Uy": "wind y component", "Uz": "wind z component",
    "T_SONIC": "sonic temperature", "amb_e": "ambient vapour pressure symbol",
    "amb_e_sat": "ambient saturation vapour pressure symbol", "e": "vapour pressure symbol",
    "e_sat": "saturation vapour pressure symbol", "e_probe": "probe vapour pressure symbol",
    "e_sat_probe": "probe saturation vapour pressure symbol", "H2O_probe": "probe water vapour density symbol",
    "PA": "pressure symbol", "VPD": "vapour pressure deficit symbol",
    "H2O_density": "water vapour density symbol", "FC_mass": "mass flux symbol; species/method pending",
    "LE": "latent heat flux symbol", "H": "sensible heat flux symbol", "TAU": "stress symbol",
    "USTAR": "friction velocity symbol", "TSTAR": "temperature scale symbol",
    "TKE": "turbulent kinetic energy symbol", "FETCH_MAX": "maximum fetch symbol",
    "FETCH_90": "90 percent fetch symbol", "FETCH_55": "55 percent fetch symbol",
    "FETCH_40": "40 percent fetch symbol", "Rsd": "downwelling shortwave radiation symbol",
    "Rsu": "upwelling shortwave radiation symbol", "Rld": "downwelling longwave radiation symbol",
    "Rlu": "upwelling longwave radiation symbol",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def iso(value):
    return None if pd.isna(value) else pd.Timestamp(value).isoformat()


def parse_hourly_times(raw):
    return pd.to_datetime(raw, format="mixed", errors="raise")


def describe_variable(kind, column, qc_column, config):
    symbol, raw_unit = re.fullmatch(r"(.+)\(([^()]*)\)", column).groups()
    height_match = re.fullmatch(r"(WS|WD|Ta|RH)_([0-9.]+)m", symbol)
    depth_match = re.fullmatch(r"(soilT|VWC|G)_([0-9.]+)m", symbol)
    base = height_match.group(1) if height_match else depth_match.group(1) if depth_match else symbol
    return {
        "variable_id": f"{kind}__{symbol}", "kind": kind, "raw_column": column,
        "raw_unit_label": raw_unit, "unit_label_standardized": UNIT_LABELS.get(raw_unit),
        "unit_conversion_performed": False,
        "unit_status": "header label retained; standardized text only" if raw_unit in UNIT_LABELS else "ambiguous slash/product notation; no canonical unit assigned",
        "description": ROLE_LABELS.get(base, "uninterpreted source symbol"),
        "description_status": "column-symbol interpretation only; sensor/method/sign conventions not independently verified",
        "height_m": float(height_match.group(2)) if height_match else None,
        "height_status": "explicit in column header; surface/reference not independently verified" if height_match else "not specified in column header",
        "depth_m": float(depth_match.group(2)) if depth_match else None,
        "depth_status": "explicit in column header; depth datum not independently verified" if depth_match else "not specified in column header",
        "qc_raw_column": qc_column,
        "qc_link_rule": config["hourly"]["qc_link_rule"] if qc_column else "no adjacent QC column; unknown",
        "strict_view_rule": "finite and not sentinel and QC=0" if qc_column else "always missing: QC unknown",
        "missing_sentinel": config["hourly"]["missing_sentinel"],
        "timestamp_timezone_status": config["hourly"]["timezone_status"],
        "timestamp_label_semantics": config["hourly"]["timestamp_label_semantics"],
        "available_time": None, "available_time_status": "not supplied; cannot establish historical operational availability",
        "temporal_integration_interval": None,
        "interval_status": "precipitation accumulation boundary specifically unresolved" if base == "Precip" else "unverified; hourly labels alone do not establish integration interval",
        "station_id": config["hourly"]["station"]["id"],
    }


def numeric_state(raw, sentinel):
    numeric = pd.to_numeric(raw, errors="coerce").astype("float64")
    finite = pd.Series(np.isfinite(numeric.to_numpy()), index=raw.index)
    sentinel_mask = numeric.eq(sentinel) & finite
    return numeric, finite, sentinel_mask, finite & ~sentinel_mask


def process_hourly(root, out, config):
    raw_dir = root / config["hourly"]["directory"]
    frames, provenance, dictionary, summary_rows, text_missing_tables = {}, {}, [], [], []
    qcs, masks = {}, {name: {} for name in ["is_finite_numeric", "is_missing_sentinel", "is_text_missing", "is_numeric_present", "qc_unknown", "strict_qc0_accepted"] + [f"qc_{code}" for code in QC_CODES]}
    schema_by_kind, input_counts = {}, []
    reference_times = None
    source_timezone = config["hourly"]["source_timezone_assumption"]
    display_timezone = config["hourly"]["display_timezone"]
    event_day = config["scenario_event_date_source_clock"]
    for kind in config["hourly"]["kinds"]:
        yearly, origins = [], []
        paths = sorted(raw_dir.glob(f"{kind}_*.csv"))
        if not paths:
            raise ValueError(f"No input files for {kind}")
        for path in paths:
            data = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
            if kind in schema_by_kind and list(data.columns) != schema_by_kind[kind]:
                raise ValueError(f"Column schema drift: {path}")
            schema_by_kind[kind] = list(data.columns)
            times = parse_hourly_times(data["Timestamp"])
            if times.isna().any() or times.duplicated().any() or not times.is_monotonic_increasing:
                raise ValueError(f"Invalid time axis: {path}")
            yearly.append(data)
            origins.append(pd.DataFrame({f"{kind}__source_file": str(path.relative_to(root)), f"{kind}__source_row_1based": np.arange(len(data)) + 2, f"{kind}__source_time_text": data["Timestamp"]}))
            input_counts.append({"file": str(path.relative_to(root)), "kind": kind, "source_rows": len(data), "measurement_columns": sum(c != "Timestamp" and not c.startswith("QC_") for c in data.columns)})
        data = pd.concat(yearly, ignore_index=True)
        times = parse_hourly_times(data["Timestamp"])
        if reference_times is None:
            reference_times = times
        elif not reference_times.equals(times):
            raise ValueError(f"Time axis mismatch for {kind}; no implicit alignment performed")
        origins = pd.concat(origins, ignore_index=True)
        provenance.update({column: origins[column] for column in origins})
        source_dates = times.dt.strftime("%Y-%m-%d")
        event = source_dates.eq(event_day)
        for position, column in enumerate(data.columns):
            if column == "Timestamp" or column.startswith("QC_"):
                continue
            qc_column = data.columns[position + 1] if position + 1 < len(data.columns) and data.columns[position + 1].startswith("QC_") else None
            entry = describe_variable(kind, column, qc_column, config)
            dictionary.append(entry)
            var_id = entry["variable_id"]
            numeric, finite, sentinel, present = numeric_state(data[column], config["hourly"]["missing_sentinel"])
            # A failed parse is never silently discarded: source row/column remain retrievable.
            text_missing = data[column].isin(config["hourly"]["missing_text_tokens"])
            malformed = ~finite & ~text_missing
            if malformed.any():
                raise ValueError(f"Non-finite or unparseable raw value requires explicit handling: {kind}/{column}")
            if text_missing.any():
                text_missing_tables.append(pd.DataFrame({"hour_index": np.flatnonzero(text_missing), "variable_id": var_id, "raw_token": data.loc[text_missing, column].to_numpy()}))
            frames[var_id] = numeric
            masks["is_finite_numeric"][var_id] = finite
            masks["is_missing_sentinel"][var_id] = sentinel
            masks["is_text_missing"][var_id] = text_missing
            masks["is_numeric_present"][var_id] = present
            if qc_column:
                qcs[var_id] = data[qc_column]
                qc_numeric = pd.to_numeric(data[qc_column], errors="coerce")
            else:
                qc_numeric = pd.Series(np.nan, index=data.index)
            for code in QC_CODES:
                masks[f"qc_{code}"][var_id] = qc_numeric.eq(code)
            unknown = ~qc_numeric.isin(QC_CODES)
            strict = present & qc_numeric.isin(config["hourly"]["strict_allowed_qc_codes"])
            masks["qc_unknown"][var_id] = unknown
            masks["strict_qc0_accepted"][var_id] = strict
            row = {"variable_id": var_id, "kind": kind, "raw_column": column, "qc_raw_column": qc_column, "rows": len(data), "finite_numeric": int(finite.sum()), "missing_sentinel": int(sentinel.sum()), "text_missing": int(text_missing.sum()), "numeric_present": int(present.sum()), "strict_qc0_accepted": int(strict.sum()), "qc_unknown": int(unknown.sum()), "event_day_rows": int(event.sum()), "event_day_numeric_present": int((event & present).sum()), "event_day_strict_qc0": int((event & strict).sum()), "first_numeric_present_source_clock": iso(times[present].min()), "last_numeric_present_source_clock": iso(times[present].max())}
            row.update({f"qc_{code}": int(qc_numeric.eq(code).sum()) for code in QC_CODES})
            summary_rows.append(row)
    if reference_times.duplicated().any() or not np.all(np.diff(reference_times.array.asi8) == 3_600_000_000_000):
        raise ValueError("Combined full calendar-hour grid has duplicates or gaps")
    localized = reference_times.dt.tz_localize(source_timezone)
    time_table = pd.DataFrame({"hour_index": np.arange(len(reference_times)), "time_utc": localized.dt.tz_convert("UTC"), "time_utc_plus8": localized.dt.tz_convert(display_timezone), "time_source_naive": reference_times, "source_timezone_assumed": "UTC+8"})
    values = pd.DataFrame(frames)
    mask_frames = {name: pd.DataFrame(columns) for name, columns in masks.items()}
    values.to_parquet(out / "hourly_raw_numeric.parquet", index=False, compression="zstd")
    text_table = pd.concat(text_missing_tables, ignore_index=True) if text_missing_tables else pd.DataFrame(columns=["hour_index", "variable_id", "raw_token"])
    text_table.to_parquet(out / "hourly_raw_text_missing.parquet", index=False, compression="zstd")
    pd.DataFrame(qcs).to_parquet(out / "hourly_raw_qc.parquet", index=False, compression="zstd")
    time_table.to_parquet(out / "hourly_time_axis.parquet", index=False, compression="zstd")
    pd.DataFrame(provenance).to_parquet(out / "hourly_provenance.parquet", index=False, compression="zstd")
    for name, frame in mask_frames.items():
        frame.to_parquet(out / f"hourly_mask_{name}.parquet", index=False, compression="zstd")
    values.where(mask_frames["strict_qc0_accepted"]).to_parquet(out / "hourly_strict_qc0.parquet", index=False, compression="zstd")
    pd.DataFrame(summary_rows).to_csv(out / "hourly_quality_summary.csv", index=False)
    pd.DataFrame(input_counts).to_csv(out / "hourly_processing_counts.csv", index=False)
    return dictionary, {"rows_full_time_grid": len(values), "measurement_columns": len(values.columns), "raw_qc_columns": len(qcs), "first_time_source": iso(reference_times.min()), "last_time_source": iso(reference_times.max()), "total_measurement_cells": int(values.size), "numeric_present_cells": int(mask_frames["is_numeric_present"].to_numpy().sum()), "missing_sentinel_cells": int(mask_frames["is_missing_sentinel"].to_numpy().sum()), "text_missing_cells": len(text_table), "text_missing_tokens": {str(key): int(value) for key, value in text_table.raw_token.value_counts().items()}, "strict_qc0_cells": int(mask_frames["strict_qc0_accepted"].to_numpy().sum()), "qc_unknown_cells": int(mask_frames["qc_unknown"].to_numpy().sum()), "physical_rejections": 0, "imputed_cells": 0, "resampled_rows": 0, "dropped_rows": 0, "unit_conversions": 0, "source_files": len(input_counts)}


def process_daily(root, out, config):
    tables, counts, counties = [], [], None
    for path in sorted((root / config["daily"]["directory"]).glob("*.xlsx")):
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            for sheet in workbook.sheet_names:
                data = pd.read_excel(workbook, sheet_name=sheet)
                names = [column for column in data.columns if column != "时间"]
                if counties is None:
                    counties = names
                elif counties != names:
                    raise ValueError(f"County-column drift in {path}/{sheet}")
                dates = pd.to_datetime(data["时间"], errors="raise")
                base = pd.DataFrame({"source_date_label": dates.dt.strftime("%Y-%m-%d"), "source_file": str(path.relative_to(root)), "source_sheet": sheet, "source_row_1based": np.arange(len(data)) + 2})
                for name in counties:
                    numeric = pd.to_numeric(data[name], errors="raise")
                    if not np.isfinite(numeric.to_numpy()).all():
                        raise ValueError(f"Non-finite daily values require explicit policy: {path}/{name}")
                    base[name] = numeric
                tables.append(base)
                counts.append({"file": str(path.relative_to(root)), "sheet": sheet, "source_rows": len(data), "county_columns": len(counties), "numeric_cells": len(data) * len(counties)})
    values = pd.concat(tables, ignore_index=True)
    if values.source_date_label.duplicated().any():
        raise ValueError("Duplicate daily date labels; not merged")
    values.to_parquet(out / "daily_county_raw.parquet", index=False, compression="zstd")
    pd.DataFrame(counts).to_csv(out / "daily_processing_counts.csv", index=False)
    dictionary = [{"variable_id": f"daily_county_temperature__{name}", "raw_column": name, "spatial_support": "county aggregation, method not supplied", "station_id": None, **config["daily"]} for name in counties]
    return dictionary, {"source_workbook_sheets": len(counts), "rows": len(values), "county_columns": len(counties), "numeric_cells": len(values) * len(counties), "first_source_date_label": values.source_date_label.min(), "last_source_date_label": values.source_date_label.max(), "candidate_sentinel_occurrences": int(values[counties].eq(config["daily"]["candidate_sentinel_for_audit_only"]).to_numpy().sum()), "unit_conversions": 0, "imputed_cells": 0, "timezone_assigned": False, "joined_to_hourly_station": False}


def independent_verify(root, out, config, dictionary, input_manifest):
    """Reload outputs; cross-check raw CSV with stdlib and XLSX with openpyxl.

    This deliberately does not reuse the pandas numeric-state helper or summary.
    """
    values = pd.read_parquet(out / "hourly_raw_numeric.parquet")
    strict = pd.read_parquet(out / "hourly_strict_qc0.parquet")
    times = pd.read_parquet(out / "hourly_time_axis.parquet")
    masks = {name: pd.read_parquet(out / f"hourly_mask_{name}.parquet") for name in ["is_finite_numeric", "is_missing_sentinel", "is_text_missing", "is_numeric_present", "qc_unknown", "strict_qc0_accepted"] + [f"qc_{code}" for code in QC_CODES]}
    quality = pd.read_csv(out / "hourly_quality_summary.csv").set_index("variable_id")
    raw_counts, raw_event = defaultdict(Counter), defaultdict(Counter)
    stored_values = {column: values[column].to_numpy() for column in values}
    stored_qc = pd.read_parquet(out / "hourly_raw_qc.parquet")
    stored_qc_values = {column: stored_qc[column].to_numpy() for column in stored_qc}
    text_missing = pd.read_parquet(out / "hourly_raw_text_missing.parquet")
    text_lookup = {(var, int(index)): token for index, var, token in text_missing.itertuples(index=False, name=None)}
    raw_positions = Counter()
    numeric_value_mismatches, qc_value_mismatches, text_value_mismatches = 0, 0, 0
    by_kind = defaultdict(list)
    for item in dictionary:
        by_kind[item["kind"]].append(item)
    for path in sorted((root / config["hourly"]["directory"]).glob("*.csv")):
        kind = path.name.split("_")[0]
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                position = raw_positions[kind]
                date_text = row["Timestamp"].split(" ")[0].replace("/", "-")
                date_parts = [int(part) for part in date_text.split("-")]
                is_event = f"{date_parts[0]:04}-{date_parts[1]:02}-{date_parts[2]:02}" == config["scenario_event_date_source_clock"]
                for item in by_kind[kind]:
                    var = item["variable_id"]
                    number = float(row[item["raw_column"]]) if row[item["raw_column"]].strip() else float("nan")
                    stored_number = stored_values[var][position]
                    numeric_value_mismatches += int(not (number == stored_number or (math.isnan(number) and math.isnan(stored_number))))
                    if item["qc_raw_column"]:
                        qc_value_mismatches += int(row[item["qc_raw_column"]] != stored_qc_values[var][position])
                    present = math.isfinite(number) and number != config["hourly"]["missing_sentinel"]
                    count = raw_counts[var]
                    count["rows"] += 1
                    count["finite_numeric"] += int(math.isfinite(number))
                    count["missing_sentinel"] += int(number == config["hourly"]["missing_sentinel"])
                    count["text_missing"] += int(row[item["raw_column"]] in config["hourly"]["missing_text_tokens"])
                    if row[item["raw_column"]] in config["hourly"]["missing_text_tokens"]:
                        text_value_mismatches += int(text_lookup.get((var, position)) != row[item["raw_column"]])
                    count["numeric_present"] += int(present)
                    qc = float(row[item["qc_raw_column"]]) if item["qc_raw_column"] and row[item["qc_raw_column"]].strip() else float("nan")
                    count[f"qc_{int(qc)}" if qc in QC_CODES else "qc_unknown"] += 1
                    count["strict_qc0_accepted"] += int(present and qc == 0)
                    if is_event:
                        raw_event[var]["event_day_rows"] += 1
                        raw_event[var]["event_day_numeric_present"] += int(present)
                        raw_event[var]["event_day_strict_qc0"] += int(present and qc == 0)
                raw_positions[kind] += 1
    checks = []
    def check(name, passed, detail):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
    keys = ["rows", "finite_numeric", "missing_sentinel", "text_missing", "numeric_present", "strict_qc0_accepted", "qc_unknown"] + [f"qc_{code}" for code in QC_CODES]
    mismatch = [{"variable_id": var, "field": key, "raw": counts[key], "output": int(quality.loc[var, key])} for var, counts in raw_counts.items() for key in keys if counts[key] != int(quality.loc[var, key])]
    event_mismatch = [{"variable_id": var, "field": key} for var, counts in raw_event.items() for key, value in counts.items() if value != int(quality.loc[var, key])]
    check("stdlib_raw_qc_numeric_counts_match_summary", not mismatch, {"variables": len(raw_counts), "fields_per_variable": len(keys), "mismatches": mismatch})
    check("stdlib_raw_numeric_values_match_every_output_cell", numeric_value_mismatches == 0, {"cells": int(values.size), "mismatches": numeric_value_mismatches})
    check("stdlib_raw_qc_strings_match_every_output_cell", qc_value_mismatches == 0, {"cells": int(stored_qc.size), "mismatches": qc_value_mismatches})
    check("qc_categories_partition_every_hourly_cell", np.all(sum(masks[f"qc_{code}"].to_numpy(dtype=np.uint8) for code in QC_CODES) + masks["qc_unknown"].to_numpy(dtype=np.uint8) == 1), {"cells": int(values.size)})
    check("numeric_presence_equals_finite_minus_sentinel", masks["is_numeric_present"].equals(masks["is_finite_numeric"] & ~masks["is_missing_sentinel"]), {"sentinel": config["hourly"]["missing_sentinel"]})
    check("numeric_and_text_missing_states_partition_all_cells", (masks["is_finite_numeric"] ^ masks["is_text_missing"]).to_numpy().all(), "non-finite tokens are explicitly retained; unknown malformed values fail processing")
    check("text_missing_lexical_records_match_mask", text_value_mismatches == 0 and len(text_missing) == int(masks["is_text_missing"].to_numpy().sum()) and text_missing.raw_token.isin(config["hourly"]["missing_text_tokens"]).all() and not text_missing.duplicated(["hour_index", "variable_id"]).any(), {"records": len(text_missing), "exact_raw_token_mismatches": text_value_mismatches})
    check("strict_mask_equals_present_and_qc0", masks["strict_qc0_accepted"].equals(masks["is_numeric_present"] & masks["qc_0"]), "strict allowance is QC0 only")
    check("strict_values_equal_retained_raw_values", strict.equals(values.where(masks["strict_qc0_accepted"])), "all retained numeric values are unchanged")
    check("no_missing_sentinel_in_strict_view", not strict.eq(config["hourly"]["missing_sentinel"]).any().any(), "full-table check")
    check("unknown_qc_never_enters_strict", not (masks["qc_unknown"] & strict.notna()).any().any(), {"no_qc_variables": sum(item["qc_raw_column"] is None for item in dictionary)})
    check("timezone_round_trip", times.time_utc.dt.tz_convert(config["hourly"]["source_timezone_assumption"]).dt.tz_localize(None).equals(times.time_source_naive), "UTC+8 is a recorded metadata assumption, not newly proven")
    check("display_clock_is_fixed_utc_plus8", times.time_utc_plus8.dt.tz_localize(None).equals(times.time_source_naive), "no host-local timezone used")
    check("all_artifacts_keep_full_hourly_shape", all(frame.shape == values.shape for frame in [strict, *masks.values()]) and len(times) == len(values), {"rows": len(values), "variables": len(values.columns)})
    check("event_calendar_day_counts_match_raw", not event_mismatch and all(counts["event_day_rows"] == 24 for counts in raw_event.values()), {"variables": len(raw_event), "date": config["scenario_event_date_source_clock"], "mismatches": event_mismatch})
    daily = pd.read_parquet(out / "daily_county_raw.parquet")
    daily_values_match, daily_total = True, 0
    for path in sorted((root / config["daily"]["directory"]).glob("*.xlsx")):
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=False)
        for sheet in workbook:
            rows = sheet.iter_rows(values_only=True)
            header = next(rows)
            source = daily[(daily.source_file == str(path.relative_to(root))) & (daily.source_sheet == sheet.title)]
            for raw, (_, stored) in zip(rows, source.iterrows(), strict=True):
                daily_values_match &= raw[0].strftime("%Y-%m-%d") == stored.source_date_label
                for column, value in zip(header[1:], raw[1:]):
                    daily_values_match &= float(value) == float(stored[column])
                    daily_total += 1
        workbook.close()
    check("daily_original_numeric_values_and_dates_unchanged", daily_values_match, {"cells": daily_total, "reader": "openpyxl independent of pandas read_excel"})
    check("input_hashes_unchanged_after_processing", all(sha256(root / item["file"]) == item["sha256"] for item in input_manifest), {"files": len(input_manifest)})
    old_audit = root / "track_b/audit/temporal/summary.json"
    if old_audit.exists():
        previous = json.loads(old_audit.read_text())
        check("phase2_independent_audit_grid_agreement", len(values) == previous["hourly"]["MET"]["rows"] and len(values.columns) == sum(len(item["measurement_columns"]) for item in previous["hourly"].values()) and len(daily) == previous["daily"]["rows"], "compare full hourly grid, variable total, daily row total with earlier audit")
    report = {"verification_version": SCRIPT_VERSION, "passed": all(item["passed"] for item in checks), "check_count": len(checks), "checks": checks, "scope_limit": "does not verify metadata mirror equivalence, physical plausibility, historical availability, daily semantics, or model fitness"}
    dump_json(out / "verification.json", report)
    if not report["passed"]:
        raise AssertionError("Temporal verification failed; inspect verification.json")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    config_path = (args.config or root / "track_b/config/temporal_policy.json").resolve()
    out = (args.out or root / "track_b/data/processed/temporal").resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for section in ["hourly", "daily"]:
        raw_directory = (root / config[section]["directory"]).resolve()
        if out == raw_directory or raw_directory in out.parents:
            raise ValueError("Outputs must not be written inside raw directories")
    if config["hourly"]["strict_allowed_qc_codes"] != [0]:
        raise ValueError("This named strict_qc0 view requires exactly QC0; create a separately named policy for alternatives")
    out.mkdir(parents=True, exist_ok=True)
    inputs = sorted(path for section in ["hourly", "daily"] for path in (root / config[section]["directory"]).iterdir() if path.is_file() and not path.name.startswith("."))
    manifest = [{"file": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path), "role": "processed_numeric_input" if path.suffix.lower() in [".csv", ".xlsx"] else "context_input_not_parsed"} for path in inputs]
    dump_json(out / "input_manifest.json", manifest)
    hourly_dictionary, hourly_counts = process_hourly(root, out, config)
    daily_dictionary, daily_counts = process_daily(root, out, config)
    dictionary = {"schema_version": "1.0.0", "hourly": hourly_dictionary, "daily": daily_dictionary, "time_axis": config["hourly"], "row_alignment_rule": "hourly files share identical full time axis; all hourly tables use zero-based row number (hour_index) as key to hourly_time_axis.parquet; daily is separate", "raw_numeric_definition": "numeric source values including 9999.9, unconverted; NaN/NAN tokens separately retained in hourly_raw_text_missing.parquet; other lexical formatting is recoverable from hashed original input and provenance", "known_start_difference": {"metadata_claimed": config["hourly"]["metadata_claimed_start"], "local_first_non_sentinel": "2021-04-23T11:00:00", "action": "both retained; no crop to metadata start"}}
    dump_json(out / "data_dictionary.json", dictionary)
    verification = independent_verify(root, out, config, hourly_dictionary, manifest)
    summary = {"schema_version": "1.0.0", "script_version": SCRIPT_VERSION, "script_sha256": sha256(Path(__file__)), "config_sha256": sha256(config_path), "config_path": str(config_path.relative_to(root)) if config_path.is_relative_to(root) else str(config_path), "generated_at_utc": datetime.now(timezone.utc).isoformat(), "date_user_local": config["date_user_local"], "runtime": {"executable": sys.executable, "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "pyarrow": pyarrow.__version__, "openpyxl": openpyxl.__version__}, "input_files_hashed": len(manifest), "hourly": hourly_counts, "daily": daily_counts, "verification_passed": verification["passed"], "verification_check_count": verification["check_count"], "ai_assistance": config["ai_assistance"], "limitations": ["UTC+8 is a metadata-mirror assumption; local-file equivalence not verified", "hourly timestamp integration interval and precipitation accumulation boundary unknown", "QC0 does not prove physical plausibility or source-region representativeness", "Precip and FLUX lack QC and are excluded from strict view", "daily unit/day boundary/timezone/spatial aggregation unknown; raw-only county table", "available_time unknown; no operational forecast eligibility established", "no imputation, resampling, cropping, physical filtering, unit conversion or model fitting"]}
    dump_json(out / "quality_summary.json", summary)
    products = [{"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)} for path in sorted(out.iterdir()) if path.is_file() and path.name != "output_manifest.json"]
    dump_json(out / "output_manifest.json", products)
    print(json.dumps({"output": str(out), "hourly": hourly_counts, "daily": daily_counts, "verification_passed": verification["passed"], "verification_checks": verification["check_count"], "output_bytes": sum(item["bytes"] for item in products)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
