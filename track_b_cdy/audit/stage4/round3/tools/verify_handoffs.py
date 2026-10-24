#!/usr/bin/env python3
"""Verify R3 versioned handoffs without interpreting scientific adoption.

Default reads producer/consumer worktrees; --integrated also checks main copies.
Only --report writes JSON inside the main R3 audit. --self-test uses temporary
fixtures. AI assistance: Codex, 2026-10-24.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[5]
AUDIT_REL = Path("track_b/audit/stage4/round3")
SHA = re.compile(r"[0-9a-f]{64}\Z")
_HASH_CACHE = {}


class Incomplete(Exception):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    path = Path(path).resolve()
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _HASH_CACHE:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                h.update(block)
        _HASH_CACHE[key] = h.hexdigest()
    return _HASH_CACHE[key]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inside(path, parent):
    return Path(path).resolve().is_relative_to(Path(parent).resolve())


def packet(question):
    require(question in {"q1", "q2", "q3", "q4"}, f"Unknown question: {question}")
    return Path(f"track_b/research/{question}/round3")


def resolve(name, root, scope, cache, absolute=False):
    require(isinstance(name, str) and name, "Missing/non-string path")
    value = Path(name)
    require(".." not in value.parts, f"Parent traversal forbidden: {name}")
    if value.is_absolute():
        require(absolute and inside(value, cache), f"Absolute path outside R3 cache: {name}")
        return value.resolve()
    target = (Path(root) / value).resolve()
    require(inside(target, Path(root) / scope), f"Repository path outside allowed packet scope: {name}")
    return target


def existing(path, integrated):
    if not path.is_file():
        if integrated:
            raise Incomplete(f"Integrated file missing: {path}")
        raise FileNotFoundError(f"Declared worktree/cache file missing: {path}")


def rows(value):
    require(isinstance(value, list), "files must be a list")
    names = set()
    for row in value:
        require(isinstance(row, dict), "File entry must be an object")
        name = row.get("path")
        require(isinstance(name, str) and name and name not in names, "Missing/duplicate file path")
        require(type(row.get("bytes")) is int and row["bytes"] >= 0, f"Invalid bytes: {name}")
        require(isinstance(row.get("sha256"), str) and SHA.fullmatch(row["sha256"]), f"Invalid SHA256: {name}")
        require(isinstance(row.get("role"), str) and row["role"], f"Missing role: {name}")
        names.add(name)
    return value


def check_file(path, entry, integrated):
    # A missing shared cache is an actual missing input, never just unintegrated Git.
    existing(path, integrated and not Path(entry["path"]).is_absolute())
    require(path.stat().st_size == entry["bytes"], f"Size mismatch: {path}")
    require(digest(path) == entry["sha256"], f"SHA256 mismatch: {path}")


def baseline(value, registry):
    require(isinstance(value, dict), "input_version must expose baseline identifiers")
    aliases = [(("baseline_commit", "common_baseline_commit"), registry["common_baseline_commit"]),
               (("manifest_sha256", "baseline_manifest_sha256"), registry["baseline_manifest_sha256"])]
    for keys, expected in aliases:
        present = [value[k] for k in keys if k in value]
        require(present and all(x == expected for x in present), f"Missing/conflicting baseline identifier: {keys}")


def verify_delivery(entry, producer_root, consumer_root, registry, integrated=False):
    producer, consumer = entry["producer"], entry["consumer"]
    pscope, cscope = packet(producer), packet(consumer) / "inputs"
    require(producer != consumer, "Self-delivery is not a cross-question handoff")
    cache = Path(registry["cache_root"]).resolve()
    source_path = resolve(entry["upstream_path"], producer_root, pscope, cache)
    delivered_path = resolve(entry["delivered_bundle_path"], consumer_root, cscope, cache)
    original_copy = resolve(str(Path(entry["delivered_bundle_path"]).parent / "upstream_bundle.json"),
                            consumer_root, cscope, cache)
    require(source_path != delivered_path and original_copy != delivered_path,
            "Bundle paths alias one another")
    for path in (source_path, delivered_path, original_copy):
        existing(path, integrated)
    require(digest(source_path) == entry["upstream_bundle_sha256"], f"Source bundle version changed: {source_path}")
    require(digest(delivered_path) == entry["delivered_bundle_sha256"], f"Delivered bundle changed: {delivered_path}")
    require(original_copy.read_bytes() == source_path.read_bytes(), f"Copied upstream bytes changed: {original_copy}")
    source, delivered = read(source_path), read(delivered_path)
    for value in (source, delivered):
        require(value.get("bundle_version") == entry["bundle_version"], "Bundle version mismatch")
        require(value.get("producer_question") == producer, "Bundle producer mismatch")
        baseline(value.get("input_version"), registry)
    a = {k: v for k, v in source.items() if k != "files"}
    b = {k: v for k, v in delivered.items() if k not in {"files", "advisor_review"}}
    require(a == b, "Consumer modified source bundle metadata beyond files/advisor_review")
    source_rows = rows(source.get("files"))
    delivered_rows = rows(delivered.get("files"))
    ledger_rows = rows(entry.get("files"))
    require(source_rows, "An empty file list is not a completed handoff")
    require(len(source_rows) == len(delivered_rows), "Source/delivery file counts differ")
    require(ledger_rows == delivered_rows, "Ledger files differ from delivered bundle files")
    source_by_name = {r["path"]: r for r in source_rows}
    seen_source, seen_targets = set(), set()
    forbidden = {source_path.resolve(), delivered_path.resolve(), original_copy.resolve()}
    total_bytes = 0
    for target_row in delivered_rows:
        name = target_row["path"]
        absolute = Path(name).is_absolute()
        origin = target_row.get("upstream_path", name if absolute else None)
        require(origin in source_by_name and origin not in seen_source, f"Missing/duplicate source mapping: {name}")
        source_row = source_by_name[origin]
        source_file = resolve(origin, producer_root, pscope, cache, absolute=True)
        target_file = resolve(name, consumer_root, cscope, cache, absolute=True)
        require(source_file not in forbidden and target_file not in forbidden, "Self-containing bundle/file declaration")
        require(target_file not in seen_targets, f"Duplicate resolved destination: {target_file}")
        require(Path(origin).is_absolute() == absolute, "Cache reference must remain the same absolute file")
        if absolute:
            require(origin == name and source_file == target_file, "Cache reference was relocated or copied silently")
        for field in ("bytes", "sha256", "role"):
            require(target_row[field] == source_row[field], f"Source/delivery {field} mismatch: {name}")
        # Additional source provenance fields must survive the path remapping.
        for key, value in source_row.items():
            if key != "path":
                require(target_row.get(key) == value, f"Source file metadata changed: {key}: {name}")
        check_file(source_file, source_row, integrated)
        check_file(target_file, target_row, integrated)
        seen_source.add(origin)
        seen_targets.add(target_file)
        total_bytes += source_row["bytes"]
    require(seen_source == set(source_by_name), "Not all source files were delivered")
    return {"producer": producer, "consumer": consumer, "bundle_version": entry["bundle_version"],
            "upstream_path": entry["upstream_path"], "upstream_bundle_sha256": digest(source_path),
            "delivered_bundle_path": entry["delivered_bundle_path"],
            "delivered_bundle_sha256": digest(delivered_path), "files": len(source_rows),
            "referenced_bytes": total_bytes, "original_upstream_bytes_preserved": True}


def review(root=ROOT, integrated=False):
    root = Path(root).resolve()
    audit = root / AUDIT_REL
    ledger, registry = read(audit / "handoffs.json"), read(audit / "workspaces.json")
    require(ledger.get("round") == registry.get("round") == "round3", "Wrong ledger/registry round")
    require(Path(registry["cache_root"]).resolve() == (root.parent / "research_cache/round3").resolve(),
            "Registry cache is outside the agreed research_cache/round3 location")
    workspaces = {w["question"]: Path(w["execution_root"]).resolve() for w in registry["workspaces"]}
    require(len(workspaces) == 4 and set(workspaces) == {"q1", "q2", "q3", "q4"}, "Four unique workspaces required")
    deliveries = ledger.get("deliveries")
    require(isinstance(deliveries, list), "deliveries must be a list")
    checks, seen = [], set()
    for index, entry in enumerate(deliveries):
        identity = (entry["producer"], entry["consumer"], entry["bundle_version"], entry["upstream_path"])
        require(identity not in seen, f"Duplicate ledger delivery: {identity}")
        seen.add(identity)
        for layer in (["worktrees", "integrated"] if integrated else ["worktrees"]):
            try:
                evidence = verify_delivery(entry,
                    root if layer == "integrated" else workspaces[entry["producer"]],
                    root if layer == "integrated" else workspaces[entry["consumer"]],
                    registry, integrated=layer == "integrated")
                checks.append({"delivery_index": index, "layer": layer, "status": "passed", "evidence": evidence})
            except Incomplete as exc:
                checks.append({"delivery_index": index, "layer": layer, "status": "incomplete", "error": str(exc)})
            except Exception as exc:
                checks.append({"delivery_index": index, "layer": layer, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    statuses = [c["status"] for c in checks]
    status = "failed" if "failed" in statuses else "incomplete" if "incomplete" in statuses else "passed"
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "round": "round3",
            "integrated": integrated, "status": status, "passed": status == "passed",
            "delivery_count": len(deliveries), "checks": checks, "tool_version": VERSION,
            "tool_sha256": digest(Path(__file__)), "ledger_sha256": digest(audit / "handoffs.json"),
            "workspace_registry_sha256": digest(audit / "workspaces.json"),
            "scope": "Versioned bundle bytes, baseline, file mapping and hashes only; review_note is not machine-validated scientific adoption."}


def self_test():
    import tempfile
    import unittest

    class HandoffTests(unittest.TestCase):
        def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            self.base = Path(self.temp.name)
            self.p, self.c = self.base / "p", self.base / "c"
            self.cache = self.base / "cache/round3"
            self.src = self.p / packet("q1") / "exports/bundle.json"
            self.dst = self.c / packet("q2") / "inputs/q1/v1/bundle.json"
            self.src.parent.mkdir(parents=True); self.dst.parent.mkdir(parents=True)
            self.file = self.src.with_name("data.bin"); self.file.write_bytes(b"source")
            self.cfile = self.dst.with_name("data.bin"); self.cfile.write_bytes(b"source")
            self.registry = {"cache_root": str(self.cache), "common_baseline_commit": "baseline",
                             "baseline_manifest_sha256": "1" * 64}
            row = {"path": str(self.file.relative_to(self.p)), "bytes": 6, "sha256": digest(self.file), "role": "fixture"}
            self.source = {"bundle_version": "v1", "producer_question": "q1",
                "input_version": {"baseline_commit": "baseline", "manifest_sha256": "1" * 64}, "files": [row]}
            self.delivered = {**self.source, "files": [{**row, "path": str(self.cfile.relative_to(self.c)), "upstream_path": row["path"]}], "advisor_review": {"note": "scenario"}}
            self.entry = {"producer": "q1", "consumer": "q2", "bundle_version": "v1",
                "upstream_path": str(self.src.relative_to(self.p)), "delivered_bundle_path": str(self.dst.relative_to(self.c))}
            self.save()

        def save(self):
            self.src.write_text(json.dumps(self.source)); self.dst.write_text(json.dumps(self.delivered))
            self.dst.with_name("upstream_bundle.json").write_bytes(self.src.read_bytes())
            self.entry.update(upstream_bundle_sha256=digest(self.src), delivered_bundle_sha256=digest(self.dst), files=self.delivered["files"])

        def verify(self, integrated=False):
            return verify_delivery(self.entry, self.p, self.c, self.registry, integrated)

        def test_valid_and_modified_bundle(self):
            self.assertEqual(self.verify()["files"], 1)
            self.src.write_bytes(self.src.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "Source bundle version changed"):
                self.verify()

        def test_escape_and_self_entry(self):
            self.delivered["files"][0]["path"] = "track_b/research/q3/round3/inputs/out.bin"
            self.save()
            with self.assertRaisesRegex(ValueError, "outside allowed packet"):
                self.verify()
            self.delivered["files"][0]["path"] = self.entry["delivered_bundle_path"]
            self.save()
            with self.assertRaisesRegex(ValueError, "Self-containing"):
                self.verify()

        def test_missing_integrated_and_cache_identity(self):
            self.cfile.unlink()
            with self.assertRaises(FileNotFoundError):
                self.verify()
            with self.assertRaises(Incomplete):
                self.verify(integrated=True)
            cached = self.cache / "q1/tile.bin"; cached.parent.mkdir(parents=True); cached.write_bytes(b"cached" * 300_000)
            row = {"path": str(cached), "bytes": cached.stat().st_size, "sha256": digest(cached), "role": "cache"}
            self.source["files"] = [row]; self.delivered["files"] = [row.copy()]; self.save()
            self.assertEqual(self.verify()["referenced_bytes"], cached.stat().st_size)
            self.delivered["files"][0]["path"] = str(self.base / "outside.bin"); self.save()
            with self.assertRaises(ValueError):
                self.verify()

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HandoffTests))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integrated", action="store_true")
    parser.add_argument("--report", help="JSON path inside the main R3 audit")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    report = None
    if args.report:
        report = Path(args.report)
        report = (ROOT / report if not report.is_absolute() else report).resolve()
        audit = (ROOT / AUDIT_REL).resolve()
        require(inside(report, audit) and report.suffix == ".json" and not inside(report, audit / "tools"), "Report must be JSON inside the main R3 audit, outside tools")
        require(report not in [audit / n for n in ("handoffs.json", "workspaces.json", "baseline_manifest.json", "history_preservation.json", "interface_review.json")], "Refusing to overwrite audit inputs")
    result = review(ROOT, args.integrated)
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "delivery_count": result["delivery_count"],
                      "checks": len(result["checks"]), "report": str(report) if report else None,
                      "issues": [c for c in result["checks"] if c["status"] != "passed"]}, ensure_ascii=False))
    return 0 if result["passed"] else 2 if result["status"] == "incomplete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
