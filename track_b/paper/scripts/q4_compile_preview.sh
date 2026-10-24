#!/usr/bin/env bash
# Compile only the Q4 preview using the unchanged shared preamble.
set -euo pipefail
q4_paper_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$q4_paper_dir"
mkdir -p figures/q4/preview
for q4_pass in 1 2; do
  xelatex -interaction=nonstopmode -halt-on-error -output-directory=figures/q4/preview -jobname=q4_preview scripts/q4_preview.tex > "figures/q4/preview/q4_compile_pass${q4_pass}.txt"
done
