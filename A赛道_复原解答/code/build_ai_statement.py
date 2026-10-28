# -*- coding: utf-8 -*-
"""生成竞赛要求的《AI 工具使用详情说明》（DOCX + PDF）。"""
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels as L

sys.stdout.reconfigure(encoding="utf-8")
PAPER = L.PAPER

DOC = [
    ("title", "AI 工具使用详情说明"),
    ("sub", "2026 年 MathorCup 数学应用挑战赛——大数据竞赛 · 赛道 A"),
    ("sub", "作品：基于数据核验、共变网络与约束生成的啤酒感官评分与风味指纹研究"),
    ("h", "一、所用 AI 工具名称与版本"),
    ("table", [["工具名称", "版本 / 型号", "开发机构", "使用日期", "使用方式"],
               ["DeepSeek", "DeepSeek-V3.2", "深度求索（DeepSeek）", "2026-10-26", "对话式辅助（网页/客户端）"]]),
    ("p", "说明：除上述工具外，参赛队未使用其他生成式 AI 工具；数据分析、绘图与排版使用 Python（NumPy、pandas、"
          "scikit-learn、NetworkX、Matplotlib、python-docx）与 LibreOffice 等常规软件，这些软件不属于 AI 生成工具。"),

    ("h", "二、使用目的与应用环节"),
    ("p", "AI 工具在本作品中只作为辅助手段，具体用于以下两个环节："),
    ("p", "1. 部分论文段落的文字组织与润色。在参赛队已经完成建模、计算并确定每个数值之后，把其中一部分段落的要点交给 DeepSeek，"
          "请它协助整理为更通顺、更符合论文语体的表达。涉及的内容包括问题背景的科普性表述、部分方法段落的过渡句、以及结论部分的归纳措辞。"
          "所有数值、公式、结论与判断均由参赛队核对后确定；AI 没有参与结果的计算与解释。"),
    ("p", "2. 代码调试与文档整理。使用 AI 辅助检查绘图脚本与论文排版脚本中的语法错误、字体设置问题，"
          "并协助整理支撑材料的目录说明。核心算法（缺失填补、嵌套交叉验证、共形预测、共变网络、Borda 聚合、"
          "条件 copula 生成、结构约束生成、跨风格迁移的约束优化等）由参赛队独立设计、实现与调试。"),
    ("p", "3. 未使用 AI 的环节：原始数据核验、缺失与标度判断、模型选择与交叉验证、结果计算、图表生成、结论提炼、"
          "参考文献筛选与正文定稿，均由参赛队独立完成。"),

    ("h", "三、关键交互记录（摘要）"),
    ("p", "（1）提示词示例：“下面这段文字是我对问题 1 技术路线的说明，请在不改变任何数值和结论的前提下，"
          "把它改写成更通顺的论文语言：……（附参赛队原始段落）”。"),
    ("p", "回复摘要：DeepSeek 给出了 2–3 个改写版本与若干连接词建议。参赛队采纳了其中一段关于“两段式任务拆分”的措辞，"
          "并自行补充了“不冒充原始标签”的限定语。"),
    ("p", "（2）提示词示例：“这段 Python 绘图代码在导出的 PDF 里中文字体变成方框，请指出可能的原因和最小修改方案：……”。"),
    ("p", "回复摘要：DeepSeek 建议显式设置 matplotlib 的 font.sans-serif 与 axes.unicode_minus。参赛队据此修改并实际重新出图确认。"),
    ("p", "（3）提示词示例：“请检查这段论文目录生成脚本为什么页码与正文对不上：……”。"),
    ("p", "回复摘要：DeepSeek 指出目录页码需要由“正文起始物理页”计算偏移量，并建议在 PDF 渲染后回填。"
          "参赛队据此实现了“先渲染、再提取标题页码、再重建文档”的流程，并经过两轮渲染核对页码一致。"),
    ("p", "（4）提示词示例：“帮我把下面这段结论压缩到 120 字以内，保留全部关键数字：……”。"),
    ("p", "回复摘要：DeepSeek 给出了压缩版本；参赛队核对了数字，并自行改写了其中一处因果表述，避免把关联写成因果。"),

    ("h", "四、采纳内容与人工修改情况"),
    ("p", "1. 文字层面：AI 建议的措辞被部分采纳，主要涉及段落衔接、同义表达与语序调整；参赛队对每一处采纳内容都做了人工修改，"
          "包括统一术语（如“共变网络”“工作等级”“协议 A/B”）、补充限定条件、删除过度断言，并逐句核对数值与图表编号。"),
    ("p", "2. 代码层面：AI 指出的字体设置与目录页码问题被采纳；参赛队在实际环境中运行验证后才写入最终脚本，"
          "没有直接使用未经运行验证的代码。"),
    ("p", "3. 内容层面：AI 未参与数据核验结论、模型选择、参数设定、结果计算与解释。论文中所有数值均可在支撑材料的结果文件中找到对应项，"
          "所有图表均由参赛队脚本从数据重新生成。"),
    ("p", "4. 未采纳内容：AI 曾建议使用更复杂的生成模型（如直接训练 CVAE），参赛队评估后认为每类样本只有 3–28 个，"
          "容易过拟合且不可解释，因此未采纳，并在论文 5.2 节说明了原因；AI 曾建议把“不可识别”的讨论简化，"
          "参赛队认为这是本题的重要结论，予以保留并加强。"),

    ("h", "五、责任声明"),
    ("p", "参赛队对论文的全部内容负责，包括使用 AI 工具辅助生成或修改的部分。参赛队已逐项核验 AI 参与内容的正确性、"
          "数值一致性与学术规范性；如仍有错误，责任由参赛队承担。"),
    ("p", "本说明与论文正文末尾的“AI 工具使用声明”一致，并作为支撑材料提交。"),
]

def set_font(run, cn="宋体", en="Times New Roman", size=11, bold=False):
    run.font.name = en
    run.font.size = Pt(size)
    run.bold = bold
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), cn)
    rFonts.set(qn("w:ascii"), en)
    rFonts.set(qn("w:hAnsi"), en)


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.4); sec.bottom_margin = Cm(2.4)
    sec.left_margin = Cm(2.6); sec.right_margin = Cm(2.6)
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"; st.font.size = Pt(11)
    st.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
    st.paragraph_format.line_spacing = 1.4
    st.paragraph_format.space_after = Pt(0)

    for kind, *rest in DOC:
        if kind == "title":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6); p.paragraph_format.space_after = Pt(4)
            r = p.add_run(rest[0]); set_font(r, cn="黑体", size=18, bold=True)
        elif kind == "sub":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(rest[0]); set_font(r, size=11)
        elif kind == "h":
            p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(3); p.paragraph_format.keep_with_next = True
            r = p.add_run(rest[0]); set_font(r, cn="黑体", size=13, bold=True)
        elif kind == "p":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Pt(22)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(rest[0]); set_font(r, size=11)
        elif kind == "table":
            rows = rest[0]
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            table.style = "Table Grid"
            table.alignment = 1
            for i, row in enumerate(rows):
                for j, val in enumerate(row):
                    cell = table.cell(i, j)
                    p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = p.add_run(str(val)); set_font(r, size=10, bold=(i == 0))
        elif kind == "pagebreak":
            pass

    out = PAPER / "AI工具使用详情说明.docx"
    doc.save(out)
    print("saved", out)


if __name__ == "__main__":
    build()
