#!/usr/bin/env python3
"""Copy adopted original programs and build a portable complete-source appendix."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from build_evidence import repository_path, write_json

PAPER = Path(__file__).resolve().parents[1]
REPO = PAPER.parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def anonymize_paths(data: bytes) -> tuple[bytes, int]:
    """Display-only path prefix substitution; original bytes stay available."""
    text = data.decode("utf-8")
    text, count = re.subn(r"/Users/[A-Za-z0-9_.-]+(?=/|\b)", "<LOCAL_HOME>", text)
    return text.encode("utf-8"), count


def escape(text) -> str:
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, c) for c in str(text))


def normalize_entry(value) -> dict:
    if isinstance(value, str):
        return {"path": value}
    if not isinstance(value, dict):
        raise ValueError("program entry must be path or object")
    return {**value, "path": value.get("path", value.get("repo_path", value.get("file", value.get("source_path"))))}


def entries(path: Path) -> tuple[list, list]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, []
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected list or object")
    original = []
    for key in ("code_files", "files", "programs", "self_authored"):
        if isinstance(data.get(key), list):
            original = data[key]
            break
    third_party = data.get("third_party", data.get("third_party_solvers", []))
    if isinstance(third_party, dict):
        third_party = [{"name": k, **v} if isinstance(v, dict) else {"name": k, "version": v}
                       for k, v in third_party.items()]
    return original, third_party


def build(paper: Path, repo: Path) -> tuple[str, dict]:
    records, third_party, issues, seen = [], [], [], {}
    listings = sorted((paper / "evidence").glob("q[1-4]_code_files.json"))
    if (paper / "evidence/common_code_files.json").exists():
        listings.append(paper / "evidence/common_code_files.json")
    for listing in listings:
        chapter = listing.name.split("_")[0]
        try:
            programs, third = entries(listing)
            third_party.extend({"chapter": chapter, **(r if isinstance(r, dict) else {"name": str(r)})} for r in third)
            for item in programs:
                entry = normalize_entry(item)
                if entry.get("type", entry.get("kind", "")) in ("third_party", "external", "solver"):
                    third_party.append({"chapter": chapter, **entry})
                    continue
                name = entry["path"]
                source = repository_path(repo, name)
                if not source.is_file():
                    raise ValueError(f"missing program: {name}")
                if name.startswith("track_b/paper/code/") or name.startswith("track_b/paper/appendices/"):
                    raise ValueError(f"generated code/appendix cannot source itself: {name}")
                data = source.read_bytes()
                data.decode("utf-8")  # Complete source appendix must be text.
                actual = digest(data)
                display, substitutions = anonymize_paths(data)
                expected = entry.get("sha256")
                if expected and expected != actual:
                    raise ValueError(f"program hash mismatch: {name}")
                if name in seen:
                    seen[name]["chapters"].append(chapter)
                    continue
                record = {"source_path": name, "portable_path": "code/" + name,
                          "display_path": "code_print/" + name, "display_sha256": digest(display),
                          "path_anonymization_count": substitutions,
                          "sha256": actual, "bytes": len(data), "lines": len(data.splitlines()),
                          "chapters": [chapter], "title": entry.get("title", entry.get("description", source.name))}
                seen[name] = record
                records.append(record)
        except (ValueError, OSError, TypeError, UnicodeError) as exc:
            issues.append(f"{listing.name}: {exc}")
    if not listings:
        issues.append("no q1–q4 code lists found")
    report = {"schema_version": 1, "passed": not issues, "sources": [str(p.relative_to(paper)) for p in listings],
              "program_count": len(records), "source_lines": sum(r["lines"] for r in records),
              "programs": records, "third_party": third_party, "issues": issues,
              "copy_policy": "Full UTF-8 original sources copied byte-for-byte; third-party solvers indexed by declared version/configuration only.",
              "display_copy_policy": "Only /Users/[A-Za-z0-9_.-]+ path prefixes are replaced with <LOCAL_HOME>; equations, parameters and program logic are otherwise unchanged. Original portable copies preserve exact source bytes."}
    chunks = ["% Generated by scripts/build_program_appendix.py.\n",
              r"\section{论文采用的自编程序}" + "\n",
              "本附录按采用清单列出完整自编源码。完整原程序在配套工程的\\texttt{code/}中按原字节保存；本附录的显示副本仅将本机用户目录前缀替换为\\texttt{<LOCAL\\_HOME>}，公式、参数和程序逻辑保持原样。源码行号与折行便于核查；第三方求解器以版本和配置索引。\n",
              r"\begin{longtable}{p{0.07\textwidth}p{0.72\textwidth}r}" + "\n",
              r"\toprule 序号 & 程序与用途 & 行数\\\midrule\endhead" + "\n"]
    for i, record in enumerate(records, 1):
        title = escape(record["title"])
        chunks.append(f"{i} & {title} & {record['lines']}\\\\\n")
    chunks.append(r"\bottomrule\end{longtable}" + "\n")
    if third_party:
        chunks.extend([r"\subsection*{第三方框架版本索引}" + "\n", r"\begin{itemize}" + "\n"])
        for record in third_party:
            text = "; ".join(f"{k}: {v}" for k, v in record.items() if k != "chapter")
            chunks.append(r"\item " + escape(f"{record.get('chapter', '')} — {text}") + "\n")
        chunks.append(r"\end{itemize}" + "\n")
    for i, record in enumerate(records, 1):
        chunks.append(r"\clearpage" + "\n")
        chunks.append(r"\subsection*{" + f"程序{i}：" + escape(record["title"]) + "}\n")
        chunks.append(r"\noindent 来源：\nolinkurl{" + record["source_path"] + "}\\\\\n")
        chunks.append(r"\noindent SHA256：\texttt{" + record["sha256"][:32] + r"}\allowbreak\texttt{" + record["sha256"][32:] + "}\\\\\n")
        # Direct VerbatimInput keeps copied source exact and does not rely on a path
        # relative to appendices/. Compilation always takes place at paper root.
        chunks.append(r"\VerbatimInput[breaklines=true,breakanywhere=true,numbers=left,numbersep=5pt,fontsize=\footnotesize,tabsize=4]{" + record["display_path"] + "}\n")
    return "".join(chunks), report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", type=Path, default=PAPER)
    parser.add_argument("--repo", type=Path, default=REPO)
    args = parser.parse_args()
    paper, repo = args.paper.resolve(), args.repo.resolve()
    text, report = build(paper, repo)
    write_json(paper / "qa/programs_check.json", report)
    if report["passed"]:
        for record in report["programs"]:
            target = paper / record["portable_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / record["source_path"], target)
            display_target = paper / record["display_path"]
            display_target.parent.mkdir(parents=True, exist_ok=True)
            display_target.write_bytes(anonymize_paths(target.read_bytes())[0])
        write_json(paper / "evidence/program_manifest.json", report)
        (paper / "appendices").mkdir(parents=True, exist_ok=True)
        (paper / "appendices/programs.tex").write_text(text, encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "program_count", "source_lines", "issues")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
