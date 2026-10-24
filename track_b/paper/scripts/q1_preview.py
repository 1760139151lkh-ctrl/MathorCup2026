#!/usr/bin/env python3
"""Compile an isolated QA preview using the unchanged common document setup.

The wrapper and compiler products are QA outputs, not manuscript sources.
Production integration uses sections/q1.tex in the common main.tex.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "track_b/paper"
OUT = PAPER / "figures/q1/qa"
OUT.mkdir(parents=True, exist_ok=True)
main = (PAPER / "main.tex").read_text()
header = next(line for line in main.splitlines() if line.startswith(r"\documentclass"))
wrapper = OUT / "q1_preview.tex"
wrapper.write_text(header + "\n" + r"""
\input{track_b/paper/preamble.tex}
\graphicspath{{track_b/paper/}}
\begin{document}
\input{track_b/paper/sections/q1.tex}
\clearpage
\begin{thebibliography}{9}
\input{track_b/paper/evidence/q1_references.tex}
\end{thebibliography}
\end{document}
""".lstrip())
xelatex = shutil.which("xelatex")
if not xelatex:
    installed = Path.home() / ".local/texlive/texlive/2026/bin/universal-darwin/xelatex"
    if installed.is_file():
        xelatex = str(installed)
if not xelatex:
    sys.exit("xelatex unavailable; manuscript sources retained")
env = os.environ.copy()
env["SOURCE_DATE_EPOCH"] = "1792800000"
for _ in range(2):
    result = subprocess.run([xelatex, "-interaction=nonstopmode", "-halt-on-error",
                             f"-output-directory={OUT.relative_to(ROOT)}", str(wrapper.relative_to(ROOT))],
                            cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        print(result.stdout[-10000:])
        sys.exit(result.returncode)
log = (OUT / "q1_preview.log").read_text(errors="replace")
flags = [line for line in log.splitlines() if re.search(r"Overfull|undefined|Missing character|LaTeX Warning", line)]
print("\n".join(flags) if flags else "No overfull boxes, undefined references, missing characters, or LaTeX warnings")
print(next((line for line in log.splitlines() if line.startswith("Output written on")), "Compile completed"))
pdftoppm = shutil.which("pdftoppm")
if not pdftoppm:
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm"
    if bundled.is_file():
        pdftoppm = str(bundled)
if pdftoppm:
    subprocess.run([pdftoppm, "-r", "120", "-png", str(OUT / "q1_preview.pdf"), str(OUT / "q1_preview")],
                   cwd=ROOT, check=True)
print("CJK character count:", len(re.findall(r"[\u4e00-\u9fff]", (PAPER / "sections/q1.tex").read_text())))
