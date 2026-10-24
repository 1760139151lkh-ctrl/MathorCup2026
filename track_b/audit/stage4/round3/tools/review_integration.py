#!/usr/bin/env python3
"""Read-only R3 integration audit; only --report writes inside the main R3 audit.

This checks provenance/integrity, not scientific model acceptance. AI: Codex,
2026-10-24. Historical R2 manifests are compared as bytes, never rerun against
the legitimately upgraded shared helper in this baseline.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[5]
AUDIT_REL = Path("track_b/audit/stage4/round3")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class Incomplete(Exception):
    """A final deliverable or final registry field has not yet been supplied."""


_HASH_CACHE = {}


def digest(path):
    path = Path(path).resolve()
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _HASH_CACHE:
        value = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                value.update(block)
        _HASH_CACHE[key] = value.hexdigest()
    return _HASH_CACHE[key]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def inside(path, parent):
    return path.resolve().is_relative_to(parent.resolve())


def file_rows(value):
    """Only two unambiguous schemas: [...], or an object with files: [...]."""
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and isinstance(value.get("files"), list):
        require(not any(k in value for k in ("entries", "artifacts")),
                "Ambiguous file-list schema: files plus entries/artifacts")
        rows = value["files"]
    else:
        raise ValueError("Expected top-level list or object with files list")
    for row in rows:
        require(isinstance(row, dict), "File entry must be an object")
        require(isinstance(row.get("path"), str) and row["path"], "Missing path")
        require(type(row.get("bytes")) is int and row["bytes"] >= 0,
                "bytes must be a nonnegative integer")
        require(isinstance(row.get("sha256"), str) and SHA.fullmatch(row["sha256"]),
                "Expected lowercase SHA256")
    return rows


def cache_roots(cache, question, workspace=None, output=False):
    cache = Path(cache).resolve()
    result = [cache / question]
    if not output:
        result.append(cache / "runtime")
        for value in (workspace or {}).get("accepted_cache_roots", []):
            path = Path(value)
            require(path.is_absolute() and inside(path, cache),
                    f"Accepted cache root outside R3 cache: {value}")
            require(path.resolve() != cache, "Cannot whitelist the entire R3 cache")
            result.append(path.resolve())
    return result


def resolve_entry(name, root, packet, allowed_cache, *, output=False, bundle=False):
    value = Path(name)
    require(".." not in value.parts, f"Parent traversal forbidden: {name}")
    if value.is_absolute():
        target = value.resolve()
        # Absolute names are reserved for immutable caches, never arbitrary local files.
        require(any(inside(target, base) for base in allowed_cache),
                f"Absolute reference outside approved cache roots: {name}")
        require(target.is_file(), f"Missing cache file: {name}")
        return target
    choices = [root / value] if bundle else [root / value, packet / value]
    choices = list(dict.fromkeys(p.resolve() for p in choices if p.is_file()))
    require(len(choices) == 1, f"Ambiguous or missing file reference: {name}")
    target = choices[0]
    require(inside(target, root), f"Reference escapes repository: {name}")
    if output or bundle:
        require(inside(target, packet), f"Output/export outside own R3 packet: {name}")
    return target


def manifest_check(root, packet, path, allowed_cache, *, output=False, bundle=False):
    root, packet, path = Path(root), Path(packet), Path(path)
    rows = file_rows(read(path))
    seen = set()
    total = 0
    for row in rows:
        target = resolve_entry(row["path"], root, packet, allowed_cache,
                               output=output, bundle=bundle)
        require(target != path.resolve(), f"Self-entry in {path}: {row['path']}")
        require(target not in seen, f"Duplicate resolved file: {row['path']}")
        require(target.stat().st_size == row["bytes"], f"Size mismatch: {target}")
        require(digest(target) == row["sha256"], f"SHA256 mismatch: {target}")
        seen.add(target)
        total += row["bytes"]
    return {"path": str(path.relative_to(root)), "file_count": len(rows),
            "referenced_bytes": total, "sha256": digest(path), "all_entries_match": True}


def bundle_check(root, packet, path, allowed_cache, question, contract):
    value = read(path)
    for name in contract["bundles"]["required"]:
        require(name in value, f"Missing bundle field {name}: {path}")
    require(value["producer_question"] == question, f"Wrong bundle producer: {path}")
    require(bool(value["bundle_version"]) and value["input_version"] is not None,
            f"Unversioned bundle: {path}")
    strata = value["evaluation_stratum"]
    strata = strata if isinstance(strata, list) else [strata]
    require(strata and all(v in contract["evaluation_strata"] for v in strata),
            f"Unknown evaluation stratum: {strata}")
    require(isinstance(value["limitations"], (str, list, dict)), "Invalid limitations field")
    for row in file_rows(value):
        require(isinstance(row.get("role"), str) and row["role"], "Bundle file missing role")
    return manifest_check(root, packet, path, allowed_cache, bundle=True)


def protected_check(root, value):
    rows = file_rows(value)
    require(value.get("file_count", len(rows)) == len(rows), "Protected count mismatch")
    for row in rows:
        name = Path(row["path"])
        require(not name.is_absolute() and ".." not in name.parts, "Invalid protected path")
        path = (root / name).resolve()
        require(inside(path, root) and path.is_file(), f"Missing protected file: {path}")
        require(path.stat().st_size == row["bytes"] and digest(path) == row["sha256"],
                f"Protected file changed: {path}")
    return {"root": str(root), "files": len(rows), "all_unchanged": True}


def find_manifest(root, packet, name, workspace):
    configured = workspace.get(name.removesuffix(".json") + "_path")
    if configured:
        path = root / configured
        require(inside(path, packet), f"Configured manifest outside packet: {path}")
        candidates = [path] if path.is_file() else []
    else:
        candidates = [p for p in (packet / name, packet / "results" / name) if p.is_file()]
    if not candidates:
        raise Incomplete(f"Missing {name} in {packet}")
    require(len(candidates) == 1, f"Ambiguous manifest location: {candidates}")
    return candidates[0]


def blob(root, ref, name):
    proc = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", f"{ref}:{name}"],
                          text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def final_workspace(root, item, registry, contract):
    needed = ("source_commit", "integration_commit", "git_branch", "previous_branch",
              "previous_source_commit", "execution_root")
    missing = [k for k in needed if not item.get(k)]
    if missing:
        raise Incomplete(f"{item['question']}: missing final registry fields {missing}")
    source_root = Path(item["execution_root"]).resolve()
    question = item["question"]
    packet_rel = Path(f"track_b/research/{question}/round3")
    source, integrated = item["source_commit"], item["integration_commit"]
    require(git(source_root, "status", "--porcelain") == "", f"Dirty source tree: {source_root}")
    require(git(source_root, "rev-parse", "HEAD") == source, "Source HEAD mismatch")
    require(git(source_root, "branch", "--show-current") == item["git_branch"], "Branch mismatch")
    require(git(source_root, "rev-parse", item["previous_branch"]) == item["previous_source_commit"],
            "Previous round branch moved")
    subprocess.run(["git", "-C", str(source_root), "merge-base", "--is-ancestor",
                    registry["common_baseline_commit"], source], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", integrated, "HEAD"],
                   check=True, capture_output=True)
    changed = git(source_root, "diff", "--no-renames", "--name-only",
                  registry["common_baseline_commit"], source).splitlines()
    require(changed and all(p.startswith(packet_rel.as_posix() + "/") for p in changed),
            f"Source commit changes outside own R3 packet: {changed}")
    integration_changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r",
                              integrated).splitlines()
    require(integration_changed and all(p.startswith(packet_rel.as_posix() + "/")
                                        for p in integration_changed),
            "Integration commit crosses packet ownership")
    for name in changed:
        require(blob(source_root, source, name) == blob(root, integrated, name),
                f"Source/integration blob mismatch: {name}")
        a, b = source_root / name, root / name
        require(a.is_file() == b.is_file(), f"Integrated path existence mismatch: {name}")
        if a.is_file():
            require(digest(a) == digest(b), f"Integrated current bytes differ: {name}")
    reports = read(source_root / packet_rel / "workspace_verification.json")
    require(reports.get("passed") is True and reports.get("round") == "round3"
            and reports.get("question") == question, "Invalid exit verification")
    require(len(reports.get("checks", [])) == 5
            and all(c.get("passed") is True for c in reports["checks"]),
            "Five exit checks not all passed")
    manifests = {}
    for name in ("input_manifest.json", "output_manifest.json"):
        output = name.startswith("output")
        allowed = cache_roots(contract["cache_root"], question, item, output=output)
        results = []
        for checkout in (source_root, root):
            packet = checkout / packet_rel
            path = find_manifest(checkout, packet, name, item)
            results.append(manifest_check(checkout, packet, path, allowed, output=output))
        require(results[0] == results[1], f"Source/main manifest disagreement: {name}")
        manifests[name] = results[1]
    output = manifests["output_manifest.json"]
    if "output_files_verified" in item:
        require(output["file_count"] == item["output_files_verified"], "Output count disagreement")
    if "final_output_manifest_sha256" in item:
        require(output["sha256"] == item["final_output_manifest_sha256"], "Output manifest hash disagreement")
    return {"root": str(source_root), "source_commit": source, "integration_commit": integrated,
            "changed_paths_verified_in_main": len(changed), "clean": True,
            "five_exit_checks_passed": True, "manifests": manifests}


def review(root, mode):
    root = Path(root).resolve()
    audit = root / AUDIT_REL
    registry = read(audit / "workspaces.json")
    contract = read(root / "track_b/config/stage4_round3_contract.json")
    checks = []

    def check(name, action):
        try:
            checks.append({"name": name, "status": "passed", "evidence": action()})
        except Incomplete as exc:
            checks.append({"name": name, "status": "incomplete", "error": str(exc)})
        except Exception as exc:
            checks.append({"name": name, "status": "failed",
                           "error": f"{type(exc).__name__}: {exc}"})

    def frozen():
        path = audit / "baseline_manifest.json"
        value = read(path)
        require(len(file_rows(value)) == registry["baseline_manifest_file_count"], "Baseline count mismatch")
        require(digest(path) == registry["baseline_manifest_sha256"], "Baseline manifest hash mismatch")
        require(value["preparation_commit"] == registry["preparation_commit"], "Preparation ref mismatch")
        roots = [root] + [Path(w["execution_root"]) for w in registry["workspaces"]]
        evidence = []
        for checkout in roots:
            require(digest(checkout / AUDIT_REL / "baseline_manifest.json") == digest(path),
                    f"Baseline manifest differs in {checkout}")
            evidence.append(protected_check(checkout, value))
        return {"manifest_sha256": digest(path), "checkouts": evidence}

    check("round3_frozen_inputs_all_checkouts", frozen)
    history = read(audit / "history_preservation.json")
    for checkout in [root] + [Path(w["execution_root"]) for w in registry["workspaces"]]:
        check("historical_bytes:" + str(checkout), lambda c=checkout: protected_check(c, history))
    for item in registry["workspaces"]:
        q = item["question"]
        if mode == "final":
            check(q + ":final_source_and_integration", lambda w=item: final_workspace(root, w, registry, contract))
        for checkout in dict.fromkeys([root, Path(item["execution_root"]).resolve()]):
            packet = checkout / f"track_b/research/{q}/round3"
            for name in contract["bundles"][q]:
                path = packet / name
                if path.is_file():
                    check(q + ":bundle:" + str(path),
                          lambda c=checkout, p=packet, f=path, w=item: bundle_check(
                              c, p, f, cache_roots(contract["cache_root"], w["question"], w, output=True),
                              w["question"], contract))
                elif mode == "final":
                    check(q + ":bundle:" + str(path),
                          lambda p=path: (_ for _ in ()).throw(Incomplete(f"Missing export bundle: {p}")))

    def links():
        docs = [root / "track_b/docs/18_stage4_round3_workflow.md"]
        if mode == "final":
            docs.append(root / "track_b/docs/19_stage4_round3_review.md")
        count = 0
        for path in docs:
            if not path.is_file():
                raise Incomplete(f"Missing review/workflow document: {path}")
            for value in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                value = value.strip("<>").split("#", 1)[0]
                if not value or re.match(r"^[a-zA-Z][\w+.-]*:", value):
                    continue
                require((path.parent / value).resolve().exists(), f"Broken local link in {path}: {value}")
                count += 1
        return {"documents": len(docs), "local_links": count}

    check("workflow_and_final_review_links", links)
    statuses = [c["status"] for c in checks]
    status = "failed" if "failed" in statuses else "incomplete" if "incomplete" in statuses else "passed"
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "round": "round3",
            "mode": mode, "status": status, "passed": status == "passed", "checks": checks,
            "review_tool_version": VERSION, "review_tool_sha256": digest(Path(__file__)),
            "scope": "Frozen inputs, historical bytes, source scope, manifests and exports; handoff adoption and scientific conclusions require advisor review.",
            "human_scientific_adoption": "pending"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("setup", "final"), default="final")
    parser.add_argument("--report", required=True, help="JSON output, restricted to the main R3 audit directory")
    args = parser.parse_args()
    report = Path(args.report)
    if not report.is_absolute():
        report = ROOT / report
    report = report.resolve()
    audit = (ROOT / AUDIT_REL).resolve()
    require(inside(report, audit) and report.suffix == ".json", "--report must be a JSON path inside the main R3 audit")
    protected = [audit / "baseline_manifest.json", audit / "history_preservation.json", audit / "workspaces.json"]
    require(report not in protected and not inside(report, audit / "tools"), "Refusing to overwrite audit inputs/tool files")
    result = review(ROOT, args.mode)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "passed": result["passed"],
                      "checks": len(result["checks"]), "report": str(report),
                      "issues": [c for c in result["checks"] if c["status"] != "passed"]}, ensure_ascii=False))
    return 0 if result["passed"] else 2 if result["status"] == "incomplete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
