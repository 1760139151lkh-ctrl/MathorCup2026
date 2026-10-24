#!/usr/bin/env python3
"""Verify the Q2 paper delivery and hash its files; never run research models."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "track_b/paper"
BASE = "eecf07db7873b3c2c63275fa0b419867d8bdd3b2"
FONT_FIX = "bbc7b5a2027a81ce358353061a0f305322a2c184"
MANIFEST = PAPER / "evidence/q2_delivery_manifest.json"
HANDOFF = PAPER / "tasks/q2_HANDOFF.md"
checks = []


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def check(name, condition):
    checks.append({"check": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((PAPER / name).read_text())


def own(path):
    return (path == "track_b/paper/sections/q2.tex"
            or path == "track_b/paper/tasks/q2_HANDOFF.md"
            or path.startswith("track_b/paper/figures/q2/")
            or path.startswith("track_b/paper/scripts/q2_")
            or path.startswith("track_b/paper/evidence/q2_"))


def verify_records(value):
    """Check each explicit path/hash record, including nested figure metadata."""
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            path = Path(value["path"])
            check("relative_source_" + str(path), not path.is_absolute() and ".." not in path.parts)
            file = ROOT / path
            check("source_hash_" + str(path), file.is_file() and digest(file) == value["sha256"])
        for item in value.values():
            verify_records(item)
    elif isinstance(value, list):
        for item in value:
            verify_records(item)


def main():
    check("execution_root", Path(git("rev-parse", "--show-toplevel")).resolve() == ROOT)
    check("paper_branch", git("branch", "--show-current") == "codex/track-b-q2-paper")
    for commit in (BASE, FONT_FIX):
        check("ancestor_" + commit, subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT).returncode == 0)
    changed = set(git("diff", "--name-only", "HEAD").splitlines())
    untracked = set(git("ls-files", "--others", "--exclude-standard").splitlines())
    check("only_q2_paper_working_changes", all(own(path) for path in changed | untracked))
    check("research_tree_unchanged", not git("diff", "HEAD", "--", "track_b/research"))

    section = PAPER / "sections/q2.tex"
    tex = section.read_text()
    count = len(re.findall("[\u3400-\u9fff]", tex))
    check("cjk_length", 2500 <= count <= 3500)
    for env, expected in (("figure", 3), ("table", 3), ("equation", 7)):
        check(env + "_count", tex.count(r"\begin{" + env + "}") == expected)
    labels = re.findall(r"\\label\{([^}]+)\}", tex)
    cites = set(key for group in re.findall(r"\\cite\{([^}]+)\}", tex) for key in group.split(","))
    check("unique_q2_labels", len(labels) == len(set(labels)) and all(x.startswith("q2:") for x in labels))
    check("q2_citation_prefixes", len(cites) == 3 and all(x.startswith("q2-") for x in cites))
    check("shared_AI_credit", tex.rstrip().endswith(r"\AIcredit"))
    check("section_without_preamble", not any(x in tex for x in (r"\documentclass", r"\newcommand", r"\usepackage")))
    check("results_led_style", not any(x in tex for x in ("尚未验证", "未达到", "未实现", "资格未接受")))

    claims = read("evidence/q2_claims.json")
    required = {"claim_id", "statement", "value", "unit", "source_files", "model_id", "scenario_id", "scope", "paper_anchor"}
    check("claims_22_complete", len(claims) == 22 and all(required <= set(x) and x["source_files"] for x in claims))
    check("unique_claim_ids", len({x["claim_id"] for x in claims}) == 22)
    check("claims_anchor_to_section", all(x["paper_anchor"] in labels for x in claims))
    codes = read("evidence/q2_code_files.json")
    check("adopted_code_7", len(codes["files"]) == 7)
    refs = (PAPER / "evidence/q2_references.tex").read_text()
    check("three_actual_references", set(re.findall(r"\\bibitem\{([^}]+)\}", refs)) == cites)

    numeric = read("evidence/q2_numeric_audit.json")
    check("numeric_122_passed", len(numeric["checks"]) == 122 and all(x["passed"] for x in numeric["checks"]))
    review = numeric["paper_review"]
    check("manual_prose_current", review["manual_prose_snapshot_matches"] is True and not review["style_warnings"])
    check("numeric_script_current", numeric["review_script_sha256"] == digest(PAPER / "scripts/q2_review_paper.py"))
    check("numeric_section_current", any(x["path"] == "track_b/paper/sections/q2.tex" and x["sha256"] == digest(section) for x in numeric["source_files"]))
    check("independent_local_events_preserved", numeric["independent_local_events"] == 0)
    figures = read("figures/q2/q2_figure_sources.json")
    figure_review = read("figures/q2/q2_visual_review.json")
    check("three_figures_reviewed", len(figures["figures"]) == 3 and figure_review["all3_final_pdf_renders_actually_opened"])
    check("figure_metadata_current", figure_review["figure_sources_sha256"] == digest(PAPER / "figures/q2/q2_figure_sources.json"))
    for value in (claims, codes, numeric, figures, figure_review, read("evidence/q2_reference_audit.json")):
        verify_records(value)

    layout = read("evidence/q2_layout_check.json")
    check("layout_compiled_5_plus_1", layout["compile_success"] and layout["body_pages"] == 5 and layout["preview_total_pages_including_local_references"] == 6)
    check("layout_no_warnings", layout["warnings"] == [])
    check("layout_section_current", layout["section_sha256"] == digest(section) and layout["cjk_character_count"] == count)
    check("layout_preamble_current", layout["preamble_sha256"] == digest(PAPER / "preamble.tex"))
    check("layout_preview_preamble_current", layout["preview_preamble_sha256"] == digest(PAPER / "scripts/q2_preview_preamble.tex"))
    check("layout_pdf_current", layout["preview_sha256"] == digest(PAPER / "figures/q2/preview/q2_preview.pdf"))
    pages = read("evidence/q2_layout_visual_review.json")
    check("all_six_final_pages_reviewed", pages["overall_passed"] and len(pages["pages"]) == 6 and all(x["actually_opened"] and x["legible"] and x["no_clipping"] and x["no_overlap"] for x in pages["pages"]))
    verify_records(pages)
    check("handoff_present", HANDOFF.is_file())

    files = []
    for path in sorted(PAPER.rglob("*")):
        rel = str(path.relative_to(ROOT))
        if not path.is_file() or not own(rel) or path in (MANIFEST, HANDOFF):
            continue
        if "__pycache__" in path.parts or path.suffix in (".aux", ".log", ".out", ".toc", ".xdv"):
            continue
        check("no_compiler_stdout", path.name != "q2_compile_stdout.txt")
        files.append({"path": rel, "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest = {
        "schema_version": "q2-paper-delivery-v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True, "checks": checks, "paper_baseline_commit": BASE,
        "public_font_fix_commit": FONT_FIX, "head_before_delivery": git("rev-parse", "HEAD"),
        "section_cjk_characters": count, "body_pages": 5, "claims": 22,
        "independent_numeric_checks": 122, "scientific_figures": 3, "tables": 3,
        "shared_preamble_read_only_sha256": digest(PAPER / "preamble.tex"),
        "files": files,
        "excluded_from_hash_list": [str(MANIFEST.relative_to(ROOT)), str(HANDOFF.relative_to(ROOT))],
        "scope": "Q2 paper only; no research model execution, new calibration, push or shared paper edits",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": True, "checks": len(checks), "delivery_files": len(files), "manifest": str(MANIFEST.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
