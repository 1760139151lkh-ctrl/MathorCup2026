"""Compile only the Q2 section against the unchanged shared preamble.

All generated files stay in the Q2 paper responsibility paths. The main paper
and its bibliography are maintained by the advisor; this is a review wrapper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "track_b/paper"
OUT = PAPER / "figures/q2/preview"
WRAPPER = PAPER / "scripts/q2_preview.tex"
PREVIEW_PREAMBLE = PAPER / "scripts/q2_preview_preamble.tex"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    preamble = (PAPER / "preamble.tex").read_text()
    aliases = {
        r"\setmainfont{TeX Gyre Termes}": r"\setmainfont{texgyretermes-regular.otf}[BoldFont=texgyretermes-bold.otf,ItalicFont=texgyretermes-italic.otf,BoldItalicFont=texgyretermes-bolditalic.otf]",
        r"\setsansfont{TeX Gyre Heros}": r"\setsansfont{texgyreheros-regular.otf}[BoldFont=texgyreheros-bold.otf,ItalicFont=texgyreheros-italic.otf,BoldItalicFont=texgyreheros-bolditalic.otf]",
        r"\setmonofont{DejaVu Sans Mono}[Scale=0.77]": r"\setmonofont{DejaVuSansMono.ttf}[Scale=0.77,BoldFont=DejaVuSansMono-Bold.ttf,ItalicFont=DejaVuSansMono-Oblique.ttf,BoldItalicFont=DejaVuSansMono-BoldOblique.ttf]",
    }
    applied = []
    for family, filename in aliases.items():
        if family in preamble:
            assert preamble.count(family) == 1, family
            preamble = preamble.replace(family, filename)
            applied.append(family)
    PREVIEW_PREAMBLE.write_text("% Q2-only copy; only Latin font-file aliases differ from shared preamble.\n" + preamble)
    WRAPPER.write_text(
        "% Q2-only layout proof, not the integrated paper.\n"
        "\\documentclass[UTF8,a4paper,zihao=-4,fontset=none]{ctexart}\n"
        "\\input{scripts/q2_preview_preamble}\n"
        "\\begin{document}\n\\setcounter{section}{3}\n"
        "\\input{sections/q2}\n\\label{q2:preview-end}\n\\clearpage\n"
        "\\begin{thebibliography}{99}\n\\input{evidence/q2_references}\n"
        "\\end{thebibliography}\n\\end{document}\n"
    )
    executable = shutil.which("xelatex")
    if not executable:
        raise RuntimeError("Existing XeLaTeX executable required; no environment changes")
    command = [executable, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
               "-output-directory=figures/q2/preview", "scripts/q2_preview.tex"]
    for _ in range(2):
        result = subprocess.run(command, cwd=PAPER, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (OUT / "q2_compile_stdout.txt").write_text(result.stdout)
        if result.returncode:
            print(result.stdout[-10000:])
            raise SystemExit(result.returncode)
    log = (OUT / "q2_preview.log").read_text(errors="replace")
    aux = (OUT / "q2_preview.aux").read_text()
    end = re.search(r"\\newlabel\{q2:preview-end\}\{\{[^}]*\}\{(\d+)\}", aux)
    reader = PdfReader(OUT / "q2_preview.pdf")
    warnings = [line for line in log.splitlines() if any(term in line for term in ("Overfull ", "Undefined", "undefined references", "Missing character"))]
    cjk = re.findall("[\u3400-\u9fff]", (PAPER / "sections/q2.tex").read_text())
    output = {
        "compile_success": True, "xelatex": executable, "passes": 2,
        "body_pages": int(end[1]) if end else None, "preview_total_pages_including_local_references": len(reader.pages),
        "cjk_character_count": len(cjk), "warnings": warnings,
        "section_sha256": hashlib.sha256((PAPER / "sections/q2.tex").read_bytes()).hexdigest(),
        "preamble_sha256": hashlib.sha256((PAPER / "preamble.tex").read_bytes()).hexdigest(),
        "preview_preamble_sha256": hashlib.sha256(PREVIEW_PREAMBLE.read_bytes()).hexdigest(),
        "preview_sha256": hashlib.sha256((OUT / "q2_preview.pdf").read_bytes()).hexdigest(),
        "scope": "Q2 section-only layout proof using original shared preamble; same Latin font families resolved by installed TeX OTF/TTF filenames; integrated pagination controlled by advisor",
        "preview_font_resolution": "Use shared font settings; apply equivalent installed-file aliases only if old family-name settings are present. No font installation or shared preamble edits",
        "font_aliases_applied": applied,
    }
    if args.render:
        renderer = shutil.which("pdftoppm")
        if not renderer:
            raise RuntimeError("Existing pdftoppm required")
        subprocess.run([renderer, "-png", "-scale-to", "1600", str(OUT / "q2_preview.pdf"), str(OUT / "q2_page")], check=True)
        output["rendered_pages"] = [str(p.relative_to(ROOT)) for p in sorted(OUT.glob("q2_page-*.png"))]
    (PAPER / "evidence/q2_layout_check.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    # Keep the PDF and reviewed page images; omit reproducible compiler debris.
    for name in ("q2_preview.aux", "q2_preview.log", "q2_preview.out", "q2_preview.toc", "q2_preview.xdv", "q2_compile_stdout.txt"):
        (OUT / name).unlink(missing_ok=True)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
