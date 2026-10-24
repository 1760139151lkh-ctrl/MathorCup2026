#!/usr/bin/env python3
"""Merge chapter evidence and verify immutable repository source hashes.

No model is run.  Explicit ``checks`` permit JSON-pointer or CSV-cell numerical
checks; other values remain author assertions linked to hash-verified sources.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


PAPER = Path(__file__).resolve().parents[1]
REPO = PAPER.parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_record(value) -> dict:
    if isinstance(value, str):
        return {"path": value, "sha256": None}
    if not isinstance(value, dict):
        raise ValueError("source_files entries must be paths or objects")
    return {**value, "path": value.get("path", value.get("repo_path", value.get("file", value.get("source_path")))),
            "sha256": value.get("sha256", value.get("hash", value.get("sha")))}


def repository_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name:
        raise ValueError("empty source path")
    if Path(name).is_absolute():
        raise ValueError(f"repository-relative path required: {name}")
    resolved = (root / name).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"source escapes repository: {name}")
    return resolved


def read_claims(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("claims", "evidence", "records"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"{path.name}: expected a list or a claims list")


def pointer(data, expr: str):
    if expr in ("", "/"):
        return data
    if not expr.startswith("/"):
        raise ValueError("JSON pointer must begin with /")
    for part in expr[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def equal(actual, expected, rtol: float, atol: float) -> bool:
    if isinstance(expected, bool) or expected is None:
        return actual == expected
    if isinstance(expected, (int, float)):
        try:
            return math.isclose(float(actual), expected, rel_tol=rtol, abs_tol=atol)
        except (TypeError, ValueError):
            return False
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            equal(a, b, rtol, atol) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and equal(actual[k], v, rtol, atol)
                                                for k, v in expected.items())
    return str(actual) == str(expected)


def check_value(check: dict, root: Path, known_sources: set[str]) -> dict:
    record = dict(check)
    try:
        name = check.get("source_path", check.get("path"))
        if name not in known_sources:
            raise ValueError("numeric check source must occur in claim source_files")
        path = repository_path(root, name)
        if "json_pointer" in check:
            actual = pointer(json.loads(path.read_text(encoding="utf-8")), check["json_pointer"])
        elif "column" in check:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter=check.get("delimiter", "\t" if path.suffix == ".tsv" else ",")))
            where = check.get("where", {})
            matches = [row for row in rows if all(str(row.get(k)) == str(v) for k, v in where.items())]
            if "row" in check:
                matches = [matches[int(check["row"])]]
            if len(matches) != 1:
                raise ValueError(f"CSV selector selected {len(matches)} rows; exactly one required")
            actual = matches[0][check["column"]]
        else:
            raise ValueError("numeric check requires json_pointer or column")
        if "expected" not in check:
            raise ValueError("numeric check requires explicit expected value")
        record["actual"] = actual
        record["passed"] = equal(actual, check["expected"], float(check.get("rtol", 1e-8)), float(check.get("atol", 1e-12)))
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        record.update(passed=False, error=str(exc))
    return record


def build(paper: Path, root: Path) -> tuple[dict, dict]:
    claims, issues, source_checks, value_checks, files = [], [], {}, [], []
    seen_ids = set()
    input_paths = sorted((paper / "evidence").glob("q[1-4]_claims.json"))
    for shared_name in ("common_claims.json", "public_claims.json"):
        if (paper / "evidence" / shared_name).exists():
            input_paths.append(paper / "evidence" / shared_name)
    for path in input_paths:
        files.append(str(path.relative_to(paper)))
        try:
            rows = read_claims(path)
        except (OSError, ValueError) as exc:
            issues.append(str(exc))
            continue
        for i, original in enumerate(rows):
            if not isinstance(original, dict):
                issues.append(f"{path.name}[{i}] is not an object")
                continue
            row = dict(original)
            claim_id = row.get("claim_id", row.get("id"))
            if not claim_id or claim_id in seen_ids:
                issues.append(f"missing or duplicate claim_id: {claim_id!r} in {path.name}")
            seen_ids.add(claim_id)
            row["claim_id"] = claim_id
            row["chapter_evidence"] = str(path.relative_to(paper))
            raw_sources = row.get("source_files", row.get("sources", []))
            if isinstance(raw_sources, dict):
                raw_sources = [raw_sources] if any(k in raw_sources for k in ("path", "repo_path", "file", "source_path")) else [
                    {"path": k, "sha256": v} for k, v in raw_sources.items()]
            normalized, names = [], set()
            if not raw_sources:
                issues.append(f"{claim_id}: no source_files")
            for raw in raw_sources:
                try:
                    source = source_record(raw)
                    name, expected = source["path"], source["sha256"]
                    source_path = repository_path(root, name)
                    if source_path in (paper / "evidence/claim_index.json", paper / "qa/evidence_check.json"):
                        raise ValueError("generated evidence index/report cannot be its own input source")
                    actual = digest(source_path)
                    passed = isinstance(expected, str) and expected.lower() == actual
                    key = (name, expected)
                    source_checks[key] = {"path": name, "expected_sha256": expected, "actual_sha256": actual, "passed": passed}
                    if not passed:
                        issues.append(f"{claim_id}: missing or mismatching source hash: {name}")
                    normalized.append({**source, "sha256": expected, "verified": passed})
                    names.add(name)
                except (ValueError, OSError, TypeError) as exc:
                    issues.append(f"{claim_id}: {exc}")
            row["source_files"] = normalized
            checks = [check_value(c, root, names) for c in row.get("checks", [])]
            for check in checks:
                value_checks.append({"claim_id": claim_id, **check})
                if not check["passed"]:
                    issues.append(f"{claim_id}: explicit value check failed")
            row["value_verification"] = "explicit_source_value_checks" if checks else "source_hash_verified_author_value_mapping"
            row["checks"] = checks
            claims.append(row)
    if not files:
        issues.append("no q1–q4 chapter claim files found")
    chapters = {Path(p).name.split("_")[0] for p in files if Path(p).name.startswith("q")}
    missing = sorted({"q1", "q2", "q3", "q4"} - chapters)
    report = {
        "schema_version": 1, "passed": not issues, "input_files": files,
        "chapters_present": sorted(chapters), "chapters_pending": missing,
        "claim_count": len(claims), "source_count": len(source_checks),
        "explicit_value_check_count": len(value_checks),
        "author_value_mapping_count": sum(not r["checks"] for r in claims),
        "value_check_meaning": "Only explicit checks compare source values automatically; source hashes alone establish provenance, not numeric agreement.",
        "source_checks": sorted(source_checks.values(), key=lambda x: (x["path"], str(x["expected_sha256"]))),
        "value_checks": value_checks, "issues": issues,
    }
    index = {"schema_version": 1, "repository_root": "../..", "claims": claims}
    return index, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, default=PAPER)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--require-all", action="store_true", help="fail if a chapter has not delivered its evidence")
    args = parser.parse_args()
    paper, root = args.paper.resolve(), args.repo.resolve()
    index, report = build(paper, root)
    if args.require_all and report["chapters_pending"]:
        report["issues"].append("missing chapters: " + ", ".join(report["chapters_pending"]))
        report["passed"] = False
    write_json(paper / "evidence/claim_index.json", index)
    write_json(paper / "qa/evidence_check.json", report)
    print(json.dumps({k: report[k] for k in ("passed", "claim_count", "source_count", "explicit_value_check_count", "chapters_pending", "issues")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
