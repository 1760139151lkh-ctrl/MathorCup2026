# -*- coding: utf-8 -*-
"""51_toc_pages.py —— 从生成的 PDF 中抽取各级标题所在页码，写入 paper/toc_pages.json
页码口径：正文第 1 页 = PDF 第 3 页（第 1 页题目/摘要，第 2 页目录）。"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import pymupdf

PDF = os.path.join(WORK, 'paper', 'A赛道论文_DeepSeek队.pdf')
TOC_JSON = os.path.join(WORK, 'paper', 'toc_pages.json')

TOC_ITEMS = [
    '一、问题重述与分析', '1.1 问题背景', '1.2 数据说明', '1.3 三个任务的建模思路',
    '二、数据核验与预处理', '2.1 数据完整性与一致性核验', '2.2 变换底数与量纲核验',
    '2.3 缺失值与异常值处理', '2.4 感官标签的 z 化性质与 0–6 等级反演', '2.5 特征变换与建模空间',
    '三、问题 1：数据缺失条件下的感官评分', '3.1 建模框架', '3.2 模型比较与交叉验证',
    '3.3 缺失鲁棒性分析', '3.4 0–6 分级评分结果', '3.5 结果分析与讨论',
    '四、问题 2：化合物–风味分析', '4.1 化合物共表达图构建', '4.2 多方法重要性度量与秩聚合',
    '4.3 各感官维度的 Top-3 关键化合物', '4.4 稳定性分析', '4.5 化学合理性论证',
    '五、问题 3：风味与"风味指纹"生成', '5.1 可逆特征空间与生成模型', '5.2 生成质量评价体系',
    '5.3 三风格化合物谱与感官画像', '5.4 跨风格迁移：Pils/Lager → Tripel',
    '5.5 缺陷化合物控制与结果讨论',
    '六、模型评价与推广', '6.1 模型优点', '6.2 局限性与改进方向', '6.3 应用推广',
    '七、结论与建议', '参考文献', '附录 A  软件环境、运行命令与核心代码',
    '附录 B  补充结果表',
]


def norm(s):
    return re.sub(r'\s+', '', s).replace('－', '-').replace('–', '-')


doc = pymupdf.open(PDF)
pages = [norm(doc[i].get_text()) for i in range(doc.page_count)]
# 定位正文起始页（第一个出现"一、问题重述与分析"且不是目录页的页）
body_start = None
for i in range(2, len(pages)):
    if norm('一、问题重述与分析') in pages[i]:
        body_start = i
        break
assert body_start is not None, '未找到正文起始页'
print('body starts at PDF page', body_start + 1, '(printed page 1)')

toc = {}
for title in TOC_ITEMS:
    t = norm(title)
    found = None
    for i in range(body_start, len(pages)):
        if t in pages[i]:
            found = i
            break
    if found is None:
        # 回退：按去掉编号后的核心词搜索
        core = norm(re.sub(r'^[0-9.一二三四五六七]+[、.]?', '', title))
        for i in range(body_start, len(pages)):
            if core and core in pages[i]:
                found = i
                break
    if found is not None:
        toc[title] = found - body_start + 1
    else:
        toc[title] = ''
        print('WARN: not found:', title)

json.dump(toc, open(TOC_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(json.dumps(toc, ensure_ascii=False, indent=1))
print('total pages:', doc.page_count, 'body pages:', doc.page_count - body_start)
