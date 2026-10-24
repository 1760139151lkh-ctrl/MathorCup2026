#!/usr/bin/env python3
"""Compile the Q3 fragment with the shared read-only preamble, without editing main.tex."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'track_b/paper'
QA = PAPER / 'figures/q3/.qa'


def main():
    QA.mkdir(parents=True, exist_ok=True)
    wrapper = QA / 'q3_preview.tex'
    wrapper.write_text(r'''\documentclass[UTF8,a4paper,zihao=-4,fontset=none]{ctexart}
\input{preamble}
\begin{document}
\input{sections/q3}
\label{q3:preview-end}
\clearpage
\begin{thebibliography}{99}
\input{evidence/q3_references}
\end{thebibliography}
\end{document}
''')
    binary = shutil.which('xelatex')
    if not binary:
        candidate = Path.home()/'.local/texlive/texlive/2026/bin/universal-darwin/xelatex'
        if candidate.is_file():
            binary = str(candidate)
    if not binary:
        raise SystemExit('XeLaTeX is required; install a TeX distribution with ctex and the shared preamble packages.')
    command = [binary, '-interaction=nonstopmode', '-halt-on-error',
               '-output-directory=figures/q3/.qa', '-jobname=q3_preview',
               'figures/q3/.qa/q3_preview.tex']
    for _ in range(2):
        result = subprocess.run(command, cwd=PAPER, capture_output=True, text=True)
        (QA/'q3_compile_stdout.txt').write_text(result.stdout+result.stderr)
        if result.returncode:
            print(result.stdout[-6000:])
            raise SystemExit(result.returncode)
    destination = PAPER/'figures/q3/q3_section_preview.pdf'
    shutil.copyfile(QA/'q3_preview.pdf', destination)
    print(destination.relative_to(ROOT))


if __name__ == '__main__':
    main()
