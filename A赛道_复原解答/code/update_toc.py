# -*- coding: utf-8 -*-
"""从已生成的 PDF 中提取各级标题所在页码，写入 paper/toc_pages.json。

原理：目录页码 = PDF 物理页号 − 正文起始偏移。正文第一页（页脚显示 1）的物理页号由
“一、问题重述与分析”所在页确定；之后逐条在正文页里搜索标题文本（去掉所有空白后匹配）。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels as L
import build_paper as B

sys.stdout.reconfigure(encoding="utf-8")
PAPER = L.PAPER
PDF = PAPER / "A赛道论文_啤酒风味复原版.pdf"
TOC_JSON = PAPER / "toc_pages.json"


def pdf_pages(pdf: Path):
    """调用 pdf-text 提取分页文本。"""
    proc = subprocess.run(f'pdf-text "{pdf}"', shell=True, capture_output=True,
                          text=True, encoding="utf-8", errors="ignore")
    out = proc.stdout
    parts = re.split(r"===== PAGE (\d+) OF \d+ =====", out)
    pages = {}
    for i in range(1, len(parts), 2):
        pages[int(parts[i])] = parts[i + 1]
    return pages


def norm(s):
    return re.sub(r"\s+", "", s)


def main():
    pages = pdf_pages(PDF)
    entries = B.collect_toc_entries()
    first_title = entries[0][1]
    toc_page = None
    for num in sorted(pages):
        if "目录" in norm(pages[num]):
            toc_page = num
            break
    if toc_page is None:
        raise SystemExit("找不到目录页")
    body_start = toc_page + 1
    if norm(first_title) not in norm(pages[body_start]):
        # 兜底：向后找第一页真正包含标题的页
        for num in sorted(pages):
            if num > toc_page and norm(first_title) in norm(pages[num]):
                body_start = num
                break
    offset = body_start - 1
    mapping = {}
    for level, title in entries:
        nt = norm(title)
        for num in sorted(pages):
            if num < body_start:
                continue
            if nt in norm(pages[num]):
                mapping[title] = num - offset
                break
        else:
            print("未找到标题:", title)
    TOC_JSON.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"body_start(pdf)={body_start}, offset={offset}, 条目={len(mapping)}/{len(entries)}")
    for level, title in entries[:6]:
        print(level, title, "->", mapping.get(title))


if __name__ == "__main__":
    main()
