#!/usr/bin/env python3
"""Read-only source/PDF QA; writes only reports beneath paper/qa."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess

from build_evidence import build as build_evidence, digest
from build_references import bibitems, citations, expanded_tex, tex_files, uncomment

PAPER = Path(__file__).resolve().parents[1]
REPO = PAPER.parents[1]
FORBIDDEN = ["尚未验证", "未达到", "未实现", "资格未接受", "未通过", "尚不满足", "不能声称", "门禁", "未完成"]
HISTORY_BASE = "eecf07db7873b3c2c63275fa0b419867d8bdd3b2"
PROTECTED_ROOTS = ["00_资料索引.txt", "01_比赛规范", "02_提交模板", "03_A赛道", "04_B赛道", "DeepSeek_A",
                   "track_b/research", "track_b/data", "track_b/audit", "track_b/config", "track_b/scripts",
                   "track_b/requirements-lock.txt", "track_b/requirements.in"]


def history_integrity(repo: Path, baseline: str) -> dict:
    """Compare protected material to the paper baseline, including working edits."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    result = {"baseline_commit": baseline, "protected_roots": PROTECTED_ROOTS,
              "changed_protected_paths": [], "untracked_protected_paths": [], "branches": [], "issues": []}
    if git("cat-file", "-e", baseline + "^{commit}").returncode:
        result["issues"].append("paper baseline commit unavailable")
        result["passed"] = False
        return result
    diff = git("diff", "--name-only", "-z", "--no-renames", baseline, "--", *PROTECTED_ROOTS)
    untracked = git("ls-files", "--others", "--exclude-standard", "-z", "--", *PROTECTED_ROOTS)
    result["changed_protected_paths"] = [v for v in diff.stdout.split("\0") if v]
    result["untracked_protected_paths"] = [v for v in untracked.stdout.split("\0") if v]
    if diff.returncode or untracked.returncode:
        result["issues"].append("git integrity comparison error")
    if result["changed_protected_paths"] or result["untracked_protected_paths"]:
        result["issues"].append("protected research or original material changed")
    registry = repo / "track_b/audit/stage4/round3/workspaces.json"
    if registry.exists():
        for record in json.loads(registry.read_text(encoding="utf-8")).get("workspaces", []):
            ref, expected = record["git_branch"], record["source_commit"]
            resolved = git("rev-parse", "--verify", "refs/heads/" + ref)
            actual = resolved.stdout.strip()
            branch = {"branch": ref, "expected_source_commit": expected, "actual_commit": actual,
                      "passed": resolved.returncode == 0 and actual == expected}
            result["branches"].append(branch)
            if not branch["passed"]:
                result["issues"].append(f"historical R3 branch moved or missing: {ref}")
    result["passed"] = not result["issues"]
    return result


def group(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise ValueError("expected brace group")
    level = 0
    for i in range(start, len(text)):
        if text[i] == "{" and (i == 0 or text[i - 1] != "\\"):
            level += 1
        if text[i] == "}" and (i == 0 or text[i - 1] != "\\"):
            level -= 1
            if level == 0:
                return text[start + 1:i], i + 1
    raise ValueError("unclosed brace group")


def last_main_page(aux: Path) -> int | None:
    if not aux.exists():
        return None
    text = aux.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\\newlabel\{LastMainPage\}\s*", text)
    if not match:
        return None
    value, _ = group(text, match.end())
    _, end = group(value, 0)
    page, _ = group(value, end)
    return int(page) if page.isdigit() else None


def check_pdf(pdf: Path, aux: Path) -> dict:
    result = {"path": pdf.name, "exists": pdf.exists(), "last_main_page": last_main_page(aux),
              "checks": [], "issues": []}
    def add(name, passed, detail):
        result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            result["issues"].append(name)
    add("body_page_limit", result["last_main_page"] is not None and 1 <= result["last_main_page"] <= 30,
        {"LastMainPage": result["last_main_page"], "limit": 30})
    if not pdf.exists():
        result["issues"].append("PDF missing")
        return result
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf)
        pages = [page.extract_text() or "" for page in reader.pages]
        result.update(page_count=len(pages), sha256=digest(pdf))
        first = re.sub(r"\s+", "", pages[0]) if pages else ""
        second = re.sub(r"\s+", "", pages[1]) if len(pages) > 1 else ""
        add("first_page_abstract_keywords", "摘要" in first and "关键词" in first, "abstract and keywords on physical page 1")
        add("second_page_contents", "目录" in second, "contents on physical page 2")
        author = str((reader.metadata or {}).get("/Author", "")).strip()
        add("anonymous_pdf_author", not author, {"Author": author})
        body_count = result["last_main_page"] or 0
        body_pages = pages[2:2 + body_count]
        # Footer extraction may reorder glyphs; a page number token in the final
        # 120 characters is a conservative automatic check, plus render QA.
        footer = []
        for i, page_text in enumerate(body_pages, 1):
            ok = bool(re.search(rf"(?<!\d){i}(?!\d)", page_text[-120:]))
            footer.append({"body_page": i, "footer_token_present": ok})
        add("body_footer_page_numbers", len(footer) == body_count and all(r["footer_token_present"] for r in footer), footer)
        identifiers = []
        patterns = {"email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                    "local_user_path": r"/Users/[A-Za-z0-9_.-]+(?:/|\b)",
                    "local_username": r"(?i)maxchen",
                    "identity_field": r"(?:参赛队号|参赛队员|指导教师|作者姓名|所属学校)\s*[:：]\s*\S+"}
        for number, text in enumerate(pages, 1):
            for name, pattern in patterns.items():
                for match in re.finditer(pattern, text):
                    identifiers.append({"page": number, "kind": name, "text": match.group(0)})
        add("anonymous_entire_pdf", not identifiers, identifiers)
        prose_hits = [{"page": number, "phrase": phrase} for number, text in enumerate(pages[:2 + body_count], 1)
                      for phrase in FORBIDDEN if phrase in re.sub(r"\s+", "", text)]
        add("positive_results_wording", not prose_hits, prose_hits)
    except (ImportError, OSError, ValueError, KeyError) as exc:
        result["issues"].append(f"PDF inspection error: {exc}")
    return result


def verify(paper: Path, repo: Path, pdf: Path | None, history_base: str = HISTORY_BASE) -> dict:
    checks, issues = [], []
    def add(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            issues.append(name)
    files = tex_files(paper)
    source = expanded_tex(paper)
    add("main_tex_exists", (paper / "main.tex").is_file(), "main.tex")
    missing_inputs = []
    missing_figures = []
    prose_hits = []
    for path in files:
        text = uncomment(path.read_text(encoding="utf-8"))
        for match in re.finditer(r"\\(?:input|include)\s*\{([^}]+)\}", text):
            name = match.group(1)
            target = paper / (name if Path(name).suffix else name + ".tex")
            if not target.is_file():
                missing_inputs.append({"file": str(path.relative_to(paper)), "input": name})
        for match in re.finditer(r"\\includegraphics\*?(?:\s*\[[^\]]*\])?\s*\{([^}]+)\}", text):
            name = match.group(1)
            target = paper / name
            exists = target.is_file() if target.suffix else any(target.with_suffix(s).is_file() for s in (".pdf", ".png", ".jpg", ".jpeg"))
            if not exists:
                missing_figures.append({"file": str(path.relative_to(paper)), "figure": name})
        if "appendices" not in path.parts and path.name not in ("preamble.tex", "references.tex"):
            for phrase in FORBIDDEN:
                if phrase in text:
                    prose_hits.append({"file": str(path.relative_to(paper)), "phrase": phrase})
    add("all_tex_inputs_exist", not missing_inputs, missing_inputs)
    add("all_figures_exist", not missing_figures, missing_figures)
    labels = re.findall(r"\\label\s*\{([^}]+)\}", source)
    duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
    refs = re.findall(r"\\(?:ref|eqref|autoref|pageref|cref|Cref)\*?\s*\{([^}]+)\}", source)
    missing_labels = sorted({key.strip() for ref in refs for key in ref.split(",")} - set(labels))
    add("unique_labels", not duplicate_labels, duplicate_labels)
    add("all_label_references_resolve", not missing_labels, missing_labels)
    keys = citations(source)
    bib = bibitems(paper / "references.tex") if (paper / "references.tex").exists() else []
    bibkeys = [key for key, _ in bib]
    add("all_citations_resolve", not (set(keys) - set(bibkeys)), sorted(set(keys) - set(bibkeys)))
    add("bibliography_first_citation_order", bibkeys == keys, {"citations": keys, "bibliography": bibkeys})
    add("positive_results_source_wording", not prose_hits, prose_hits)
    _, evidence_report = build_evidence(paper, repo)
    add("source_evidence_hashes", evidence_report["passed"], {k: evidence_report[k] for k in ("claim_count", "source_count", "issues", "chapters_pending")})
    add("four_chapter_evidence", not evidence_report["chapters_pending"], evidence_report["chapters_pending"])
    history = history_integrity(repo, history_base)
    add("historical_research_integrity", history["passed"], history)
    manifest_path = paper / "evidence/program_manifest.json"
    program_checks = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for record in manifest.get("programs", []):
            target = paper / record["portable_path"]
            display = paper / record.get("display_path", record["portable_path"])
            passed = target.is_file() and digest(target) == record["sha256"]
            display_passed = display.is_file() and digest(display) == record.get("display_sha256", record["sha256"])
            program_checks.append({"path": record["portable_path"], "display_path": str(display.relative_to(paper)),
                                   "original_passed": passed, "display_passed": display_passed,
                                   "passed": passed and display_passed})
    add("portable_original_program_hashes", bool(program_checks) and all(r["passed"] for r in program_checks), program_checks)
    aux = (pdf.with_suffix(".aux") if pdf else paper / "main.aux")
    log = aux.with_suffix(".log")
    if log.exists():
        text = log.read_text(encoding="utf-8", errors="replace")
        warnings = [line for line in text.splitlines() if ("undefined" in line.lower() or "multiply defined" in line.lower()) and "warning" in line.lower()]
        add("resolved_latex_references", not warnings, warnings)
        overflow = re.findall(r"Overfull \\[hv]box[^\n]*", text)
        add("no_overfull_boxes", not overflow, overflow)
    else:
        add("latex_log_exists", False, str(log))
    pdf_report = check_pdf(pdf or paper / "main.pdf", aux)
    add("pdf_content_checks", not pdf_report["issues"], pdf_report)
    return {"schema_version": 1, "passed": not issues, "check_count": len(checks),
            "passed_count": sum(r["passed"] for r in checks), "checks": checks, "issues": issues,
            "visual_review": "Automatic checks complement page-by-page rendered inspection; mathematical applicability is reviewed through chapter evidence and handoffs."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, default=PAPER)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--pdf", type=Path, help="compiled PDF, default paper/main.pdf; aux/log expected alongside")
    parser.add_argument("--history-base", default=HISTORY_BASE, help="paper common baseline for protected research/material comparison")
    args = parser.parse_args()
    paper, repo = args.paper.resolve(), args.repo.resolve()
    report = verify(paper, repo, args.pdf.resolve() if args.pdf else None, args.history_base)
    (paper / "qa").mkdir(parents=True, exist_ok=True)
    (paper / "qa/paper_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "check_count", "passed_count", "issues")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
