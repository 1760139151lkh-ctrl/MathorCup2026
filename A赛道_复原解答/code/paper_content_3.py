# -*- coding: utf-8 -*-
"""论文内容（三）：第五章 问题 3、第六章、第七章、参考文献、AI 声明、附录。"""
from docx.shared import Cm
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels as L

R = L.RESULTS

# ---------------------------------------------------------------- 动态表格数据
def portrait_table():
    gen = pd.read_csv(R / "Q3_三类生成样本平均感官画像.csv").set_index("style")
    real = pd.read_csv(R / "Q3_真实风格平均感官画像_D04尺度.csv").set_index("style")
    dims = ["alcohol", "body", "overall", "A_esters_all", "bitternes",
            "acidity", "lactic", "X4vg", "diacetyl", "stale_hops"]
    head = ["样本", "酒精感", "酒体", "总体", "酯香", "苦度", "酸度", "乳酸", "4-VG", "双乙酰", "陈酒花"]
    rows = []
    for sty in ["Tripel", "Kriek", "Lambic"]:
        rows.append([f"生成 {sty}"] + [f"{gen.loc[sty, d]:.2f}" for d in dims])
        rows.append([f"真实 {sty}"] + [f"{real.loc[sty, d]:.2f}" for d in dims])
    return head, rows

def transfer_critical_table():
    crit = pd.read_csv(R / "Q3_迁移_缺陷化合物对照.csv")
    crit4 = crit[crit["criterion"].isin(["V004", "V039", "V021", "V109"])].copy()
    name = {"V004": "DMS（17.25 µg/L）", "V039": "双乙酰（0.29925 mg/L）",
            "V021": "4-VG（0.206333 mg/L）", "V109": "反-2-壬烯醛（0.35）"}
    rows = []
    for v in ["V004", "V039", "V021", "V109"]:
        g = crit4[crit4["criterion"] == v]
        ratio = g["after_ratio"].values
        rows.append([name[v], f"{ratio.mean():.3f}", f"{ratio.max():.3f}",
                     int((ratio > 1).sum()),
                     "迁移后=迁移前" if (g["after_native"].values == g["source_native"].values).all()
                     else "迁移后≤迁移前"])
    return ["缺陷化合物（阈值）", "阈值倍数均值", "阈值倍数最大值", "超阈值对象数", "逐对象判定"], rows

def transfer_safety_table():
    k = pd.read_csv(R / "Q3_迁移_陈酒花味Y38安全对照.csv")
    g = k[k["branch"] == "observed_guard_original_D01_model_source"].copy()
    rows = []
    for _, r in g.iterrows():
        rows.append([str(int(r["source_object"])), f"{r['before_Y38_D04']:.3f}", f"{r['after_Y38_D04']:.3f}",
                     f"{r['continuous_delta_after_minus_before']:.3f}",
                     f"{int(r['A_before'])}→{int(r['A_after'])}", f"{int(r['B_before'])}→{int(r['B_after'])}"])
    return ["源对象", "迁移前 Y38 预测", "迁移后 Y38 预测", "连续变化", "协议 A 等级", "协议 B 等级"], rows

def appendix_top3():
    top = pd.read_csv(R / "Q2_Top3关键化合物_汇总.csv")
    rows = []
    for _, r in top.iterrows():
        def fmt(k):
            return f"{r[f'top{k}_compound']}（{r[f'top{k}_freq']:.2f}）"
        rows.append([r["target"], r["target_name"], fmt(1), fmt(2), fmt(3)])
    return ["目标", "感官维度", "第 1 名（频率）", "第 2 名（频率）", "第 3 名（频率）"], rows


BLOCKS = [
    # ================================================================ 第五章
    ("h1", "五、问题 3：风味与“风味指纹”生成"),
    ("h2", "5.1 问题分析"),
    ("p", "问题 3 有两个任务：一是“给定风格，生成像样的化合物谱，并给出感官画像”；二是“把 Pils/Lager 的化合物谱迁移成 Tripel 风格，同时保证缺陷化合物不恶化”。"
          "数据里有 22 个风格，但样本很不均衡：Tripel 28 个、Pils/Lager 11 个、Kriek 10 个、Lambic 11 个，最少的 Faro 只有 3 个。"
          "231 维特征对每个风格只有几个到二十几个样本，直接训练一个深的生成网络（例如 CVAE）很容易过拟合，而且不可解释。"
          "因此本文选择“先把数据结构弄清楚、再逐步加约束”的路线。"),
    ("p", "这一问需要同时满足三类要求，必须分开检查：（1）分布像不像：生成样本的统计特征应与目标风格的真实样本接近；"
          "（2）结构对不对：生成的 231 维必须满足 2.5 节复原出的 5 条派生关系，不能 231 个坐标各自独立采样；"
          "（3）缺陷安不安全：迁移后 4 个缺陷化合物与陈酒花味不能比源样品更差。"
          "任何单一指标（哪怕很漂亮）都不能替代另外两类检查。"),
    ("h2", "5.2 类别条件高斯 copula 基线"),
    ("p", "第一版生成器采用“秩-高斯 + 类别条件高斯 copula”。它的想法很像“先把每个变量换成它在自己这一列里的名次，"
          "再把名次映射到标准正态”，于是不同量纲的化合物可以放在同一个相关结构里；然后按风格估计均值与共享协方差，采样后再逆变换回原刻度。具体地："),
    ("p", "（1）用经验分位数把每一列 x_j 变成标准正态分数 z_j = Φ⁻¹(F̂_j(x_j))，其中 F̂_j 是训练数据的经验分布函数[25]；"
          "（2）对每个风格 c，类均值向全局均值收缩，避免只有 3 个样本的风格“把均值拉飞”："),
    ("eq", "μ̃_c = [ n_c / (n_c + 5) ] · μ_c + [ 5 / (n_c + 5) ] · μ_global", "5-1"),
    ("p", "例如 Kriek 有 10 个样本，权重为 10/15≈0.67；Tripel 有 28 个，权重为 28/33≈0.85。5 是预先给定、容易解释的伪计数，不是从数据里“调”出来的最优值。"
          "（3）残差 r = z − μ̃_c 的 231×231 协方差用 Ledoit–Wolf 收缩估计[26]："),
    ("eq", "Σ̂ = (1 − λ)·S + λ·v̄·I", "5-2"),
    ("p", "其中 S 是样本协方差，v̄ 是各坐标方差的平均，λ 由训练数据估计（本次收缩系数 0.1438）。231 维、每类只有几个样本时，"
          "分别估计每类协方差不可靠，因此各类共享同一个残差协方差，这是“用偏差换方差”的建模选择。"
          "（4）采样时先抽标准正态 ε，再计算 z_new = μ̃_c + Lε（L 是 Σ̂ 的 Cholesky 因子），最后用逆经验分布变换回原刻度。"
          "另外用概率主成分分析（PPCA）做低参数对照[27]：它只保留 5 或 10 个主方向，再给每个方向加噪声。"),
    ("p", "为客观比较，本文做 5 次按风格分层的 70%/30% 划分（175 训练/75 留出），每次重新拟合生成器，"
          "再用三种分布距离比较生成样本与留出样本：能量距离、高斯核 MMD²、秩空间高斯负对数似然[28,29]。"
          "表 14 的结果说明“没有单一赢家”：按能量距离，条件模型（27.77）优于全局模型（29.89）与两个 PPCA（29.21/28.87）；"
          "但按秩空间 NLL，全局模型（397.02）反而优于条件模型（417.06）。原因是 NLL 奖励“把方差估小”，而条件均值本身有估计误差，"
          "小样本下条件模型的方差估计偏紧。我们把这种“指标之间打架”如实报告，而不是只挑一个指标宣布胜利；本文也没有实际训练更深的 CVAE[30,31]：每个风格只有 3–28 个样本，网络参数远多于样本量，容易过拟合且不可解释。"),
    ("table", "表 14  231 维基线生成模型的留出比较（5 次划分、22 类等权平均）",
     ["方法", "能量距离（越低越好）", "MMD²（越低越好）", "秩空间 NLL（越低越好）"],
     [["条件高斯 copula（类均值收缩）", "27.770", "0.3127", "417.06"],
      ["全局高斯 copula", "29.893", "0.3460", "397.02"],
      ["条件 PPCA（5 维）", "29.212", "0.3348", "437.88"],
      ["条件 PPCA（10 维）", "28.871", "0.3296", "435.27"]],
     [Cm(6.0), Cm(3.4), Cm(3.0), Cm(3.4)], 9),
    ("h2", "5.3 结构一致的生成：226 个基础量 + 5 个派生量"),
    ("p", "第一版生成器有一个致命问题：它把 231 个坐标一起生成，虽然统计上“像”，但不能保证 5 条派生关系成立。"
          "我们检查了第一版生成样本在 5 个派生量上的记录尺度偏差，中位数达到 0.07–0.36，最大达到 2.07——这在化学上是不可接受的，"
          "因为派生量本应由基础量唯一决定。于是第二版改为“只生成 226 个基础量，再按 2.5 节的公式重算 5 个派生量”。"
          "具体流程是："),
    ("list", ["• 基础量：226 列 = 231 列去掉 5 个派生列；其中 V001–V036 用 8.xlsx 的原生参照值（保留真实的 0、负值与缺失），其余列保持 1.csv 观测刻度；",
              "• 生成：用类别条件的高斯 copula 生成 226 维基础量；",
              "• 重算：按式 (2-3)–(2-7) 计算 5 个派生量，若任一派生聚合非正或非有限，则拒绝该候选并重采样（绝不取绝对值或截断成小数来“凑”等式）；",
              "• 回写：按已验证的对数规则把 231 列映射回 1.csv 的记录刻度，再送入问题 1 的评分器得到 50 维感官画像。"]),
    ("p", "第二个问题是“零原子”。很多化合物在部分风格里大量为 0（例如 4-VG 在 Tripel 中 23/28 为 0，二硫化碳在 Lambic 中约 82% 为 0）。"
          "如果先用总体经验分布、再让类均值去平移，条件分布的零概率会被压得过大：第一版生成中 Tripel 的 4-VG 100/100 全为 0，"
          "而真实是 23/28≈0.82；Kriek 的二硫化碳零率 0.92，真实 0.60。原因是“总体逆 CDF 把一大段概率压到同一个零原子”。"
          "修正办法是直接规定每个类、每个变量的经验分布，并让它向总体分布收缩："),
    ("eq", "F̃_jc(x) = [ n_jc / (n_jc + 5) ] · F̂_jc(x) + [ 5 / (n_jc + 5) ] · F̂_j0(x)", "5-3"),
    ("p", "其中 n_jc 是第 c 类第 j 列的有效观测数（缺失格不参与计数），F̂_jc 是类内经验分布，F̂_j0 是总体经验分布。"
          "这样零原子的概率就是“类内零值权重与总体零值权重按比例混合”，不会再被均值平移随意压成 1。采样时先在标准正态空间估计共享相关矩阵 R，"
          "再抽 Z~N(0,R)、U=Φ(Z)，最后用带权阶梯逆 CDF 逐列取训练值——这保证零与负值“不会被插值跨过”。"),
    ("p", "在这一结构下，300 个候选（Tripel/Kriek/Lambic 各 100）的零率与真实类内零率明显接近：Tripel 的 4-VG 从 1.00 修到 0.87（真实 0.82），"
          "Kriek 的二硫化碳从 0.92 修到 0.69（真实 0.60），Lambic 的二硫化碳从 0.98 修到 0.85（真实 0.82）。"
          "留出比较也更好：结构一致 + 类条件经验边际的生成器在能量距离上达到 22.47（条件高斯 27.25、全局 29.65），"
          "MMD² 为 0.233（0.308/0.345），是所有方案里最好的。需要说明：由于分布含离散原子，它没有连续高斯似然，NLL 一栏不适用。"),
    ("table", "表 15  零/负值原子修复前后的类内零率对照（括号内为真实参考值）",
     ["风格", "修复前的零率（生成）", "修复后的零率（生成）", "真实类内零率"],
     [["Tripel：4-VG", "1.00", "0.87", "0.82"],
      ["Tripel：二硫化碳", "0.99", "0.92", "0.89"],
      ["Kriek：二硫化碳", "0.92", "0.69", "0.60"],
      ["Kriek：4-VG", "0.99", "0.94", "1.00"],
      ["Lambic：二硫化碳", "0.98", "0.85", "0.82"],
      ["Lambic：4-VG", "0.94", "0.79", "0.91"]],
     [Cm(4.4), Cm(3.6), Cm(3.6), Cm(3.2)], 9),
    ("fig", "fig09_Q3模型比较.png",
     "图 10  生成模型留出比较。类条件经验边际 copula 在能量距离与 MMD 上最好；"
     "含离散原子的分布无法直接计算连续高斯 NLL，故 NLL 栏留空。", 15.2),
    ("fig", "fig12_Q3零原子.png",
     "图 11  零原子修复。(a) 四个含零原子特征的零率：生成 vs 真实（对角线表示完全一致）；"
     "(b) 4-VG 的生成值集中在记录尺度下限 −2.0132，对应原生“非正值”。", 15.2),
    ("p", "从 300 个候选中，我们还按“5 个派生聚合都落在该类真实观测范围内”筛选了代表性样本：Tripel 100 个中 66 个通过、Kriek 20 个、Lambic 21 个，"
          "每类取 3 个共 9 个代表。代表样本的作用是展示“在该类历史数据范围内”的合理配方，不是声称它们是真实的新啤酒；"
          "筛选后的分布已不同于未筛生成器，因此留出指标只对未筛生成器成立。"),
    ("h2", "5.4 生成样本的感官画像"),
    ("p", "把生成化合物谱送入问题 1 的评分器，就得到 50 维感官画像。表 16 对比三个风格“生成均值”与“真实风格均值”："
          "Tripel 呈现高酒精、高酯香、低酸、低苦的画像；Kriek 与 Lambic 呈现高酸、高乳酸/乙酸、低苦、低酒精的画像。"
          "数值上，生成画像与真实风格均值在 50 个维度上的相关系数分别为 Tripel 0.88、Kriek 0.96、Lambic 0.97，"
          "平均绝对差分别为 0.06、0.19、0.12 个 D04 单位。生成值整体比真实值“保守”（幅度偏小），这与小样本生成模型向均值收缩的预期一致。"),
    ("table", "表 16  生成风格均值与真实风格均值的感官画像对比（D04 单位）", *portrait_table(),
     [Cm(2.6)] + [Cm(1.32)] * 10, 8),
    ("p", "为了进一步检验“生成的谱是否真的像某一风格”，我们额外训练了三个二分类逻辑回归（Tripel vs 其余、Kriek vs 其余、Lambic vs 其余），"
          "用 5 折交叉验证评估：AUC 分别为 0.851、0.998、0.981，说明这三个风格在化学上是可以被区分的。"
          "把生成样本送入这三个分类器，Tripel/Kriek/Lambic 各自被判为对应风格的平均概率为 0.735/0.726/0.718，"
          "而被判为其他风格的概率大多低于 0.10。这个“风格保真度”检验独立于分布距离，从判别角度支持生成样本确实落在目标风格附近。"),
    ("fig", "fig10_Q3感官画像.png",
     "图 12  生成样本的感官画像。(a) 16 个关键维度的风格均值：Tripel 高酒精、高酯香、低酸；"
     "Kriek/Lambic 高酸、高乳酸/乙酸、低苦；生成值与真实值同向但幅度更保守。"
     "(b) 50 维散点，三个风格的生成—真实相关系数分别为 0.88、0.96、0.97。", 15.4),
    ("h2", "5.5 跨风格迁移：Pils/Lager → Tripel"),
    ("p", "跨风格迁移可以理解为“在保持源样品骨架的前提下，把它朝目标风格的方向推”。第一步给出一个“提议方向”：把 Pils/Lager 的类均值平移到 Tripel 的类均值："),
    ("eq", "x^prop = x^src + ( μ_Tripel − μ_Pils/Lager )", "5-4"),
    ("p", "但直接平移很可能让缺陷化合物升高。于是第二步求一个离提议不远、同时满足约束的点：4 个缺陷化合物的原生值不超过源对象，"
          "5 个派生聚合为正，且评分器预测的陈酒花味 Y38 不高于源对象。用加权平方距离衡量“改动大小”："),
    ("eq", "min_x  ½ Σ_j [ (x_j − x_j^prop) / s_j ]²   s.t.  x_j^C ≤ x_j^C,src；x^Y38 预测不高于源；派生聚合 > 0", "5-5"),
    ("p", "其中 s_j 是该列 90% 分位与 10% 分位之差，用来把不同量纲的坐标放在同一把尺子上。求解用 SLSQP（序列二次规划），"
          "并且优化器报告“成功”不算数——必须把保存后的 CSV 重新读入、重新计算 5 个派生量与评分，逐项核对约束。"),
    ("p", "在核对中我们发现一个很重要的问题：如果把“迁移前”的基线只设成“模型对源样品的预测”，有 5 个对象的迁移后预测虽然低于模型预测，"
          "却高于源样品在 4.csv 里的真实观测值（例如 object 124：真实观测 Y38≈−0.355，模型预测 0.025，迁移后 −0.070，看上去降了，其实比真实观测高 0.28）。"
          "这说明“自己跟自己比”会掩盖问题。我们把上界加强为三重最小："),
    ("eq", "cap_i = min{ ŷ38(源 D01 原值), ŷ38(源原生重表达值), z_i^obs(源样品观测值) }", "5-6"),
    ("p", "优化时把上界再收紧 10⁻⁶（只为吸收 CSV 序列化误差），最终判定用保存后重读的值、且不允许正容差。"
          "此外还有两个技术细节：（1）对 226 维中的 44 个“临界坐标 + 派生父变量 + 基础参数”做固定，剩下 182 个自由坐标；"
          "在这 182 维上评分器是分段线性的，因此可以解析地写出一个带盒约束的二次规划解："),
    ("eq", "x(m) = clip( p − m·s²∘β, low, high )，  β'x(m) ≤ rhs", "5-7"),
    ("p", "其中 m≥0 是乘子，β 是评分器在该子空间上的斜率；β'x(m) 关于 m 单调不增，因此只需二分一个标量 m 就能找到既满足评分约束、"
          "又离提议最近的解。这个子问题有全局最优证明（固定 182 维、线性约束、严格凸目标），但它不等于完整 226 维迁移的全局最优。"
          "（2）评分器在缩尾箱外是“平的”，同一个裁剪输入可以对应多个原值；我们在不改变任何 50 维预测的前提下，把箱外坐标拉回箱边，"
          "改善与原值的接近程度，并明确标注“等输入修复点不是原 QP 解”。"),
    ("p", "最终结果（11 个 Pils/Lager 源对象）：44 个缺陷约束全部通过（11 对象×4 化合物），11 个 Y38 连续预测全部下降（最大上升为 0），"
          "在协议 A/B 下 11/11 等级不升高；到 Tripel 类中心的距离 11/11 缩短；没有对象退回源点。"
          "object 124 的 QP 解乘子 m=15.61，加权目标 2.43，182 个自由坐标中有 27 个贴到边界，实际评分与仿射近似的最大偏差 2.8×10⁻¹⁶。"
          "表 17 汇总四项缺陷的“阈值倍数”，表 18 给出每个对象的 Y38 与协议等级变化。"),
    ("table", "表 17  四项缺陷化合物在迁移前后的阈值倍数（11 个源对象）", *transfer_critical_table(),
     [Cm(4.6), Cm(2.8), Cm(2.8), Cm(2.6), Cm(2.6)], 9),
    ("table", "表 18  跨风格迁移的感官安全对照（观测源守卫分支）", *transfer_safety_table(),
     [Cm(1.8), Cm(2.8), Cm(2.8), Cm(2.2), Cm(2.8), Cm(2.8)], 9),
    ("p", "从“像不像 Tripel”的角度再看一次：独立分类器给出 11 个源对象被判为 Tripel 的平均概率从 2.4% 升到 39.1%，其中 10 个对象上升；"
          "唯一的例外是 object 28（0.121→0.109），它的源样品本身已经比较接近 Tripel，约束把改动拉回了原地。"
          "这与“到 Tripel 类中心距离全部缩短”的结论一致，但两者都不是“真实风格保真度”的证明——迁移后的啤酒没有被真正酿造和品评。"),
    ("fig", "fig11_Q3迁移.png",
     "图 13  跨风格迁移。(a) 四项缺陷化合物的原生值相对阈值倍数：迁移后保持源对象的数值（红=超过阈值）；"
     "(b) 陈酒花味 Y38 连续预测逐对象下降；(c) 独立监督分类器判为 Tripel 的概率由平均 2.4% 升至 39.1%，10/11 个对象上升。", 15.6),
    ("h2", "5.6 “缺陷不恶化”到底能保证什么"),
    ("p", "上面的结果是“在模型预测这个代理上不恶化”。它离“真实 K 不恶化”还有多远？可以用一个精确的数学结论划出边界。"
          "设源样品的某个缺陷量为 S，目标风格的真实分布为 R，迁移后的分布为 Q。要求“每个源对象都不升高”意味着 Q 在随机序意义下不优于 S，"
          "即对任意阈值 t，迁移后超过 t 的概率不超过源："),
    ("eq", "F_Q(t) ≥ F_S(t)  对一切 t 成立（F 为累积分布函数）", "5-8"),
    ("p", "而一维 Wasserstein-1 距离是两个累积分布函数之间的面积：W₁(Q,R) = ∫|F_Q−F_R|dt。由于 F_Q≥F_S，在 F_S>F_R 的地方必然有 |F_Q−F_R| ≥ F_S−F_R，"
          "于是得到一条与生成模型无关的下界[32]："),
    ("eq", "W₁(Q,R) ≥ ∫ [ F_S(t) − F_R(t) ]₊ dt", "5-9"),
    ("p", "也就是说，只要源风格与目标风格的尾部比例不同，“逐对象不恶化”就必然与“完整匹配目标分布”冲突，差距由这条面积下界给出。"
          "对本题的 4 个缺陷化合物，按原生阈值归一化后的下界分别为：DMS 1.78、双乙酰 1.47、4-VG 0.024、反-2-壬烯醛 1.17；"
          "最大正尾差分别为 0.714、0.445、0.088、0.549。这解释了为什么“完美迁移成 Tripel 分布”与“每个源对象缺陷都不升高”不能同时做到——"
          "这不是模型不够好，而是两个要求本身在数学上互相排斥。"),
    ("p", "还有两个必须写清楚的边界。第一，真实 K（陈酒花味的原始 0–6 等级）不可识别：协议 A/B 本身对同一批预测给出不同的 K 分布，"
          "迁移后的真实等级更没有被观测。第二，“均值不升高”不等于“尾部风险不降低”：例如迁移前 K 恒为 1（均值 1、达到 2 的概率 0），"
          "迁移后以 0.7 概率为 0、0.3 概率为 3（均值 0.9、达到 2 的概率 0.3），均值下降了，但临界风险反而上升。"
          "因此本文只承诺“同一固定协议下连续预测与工作等级不升高”，并把真实 K 的安全标记为“不可识别”，不把它包装成“已验证安全”。"),
    ("h2", "5.7 小结"),
    ("p", "问题 3 的交付物包括：三个风格各 100 条结构一致的化合物谱、对应 50 维感官画像、9 个范围兼容的代表样本、"
          "11 个 Pils/Lager→Tripel 迁移配方及其逐项安全对照、以及一条关于“安全与目标分布不可兼得”的严格下界。"
          "方法上最重要的经验是：先修代数结构（5 条派生关系），再修边际分布（零原子），最后才谈距离与约束；"
          "顺序反过来，就会像第一版模型那样“看起来很像、内部却不自洽”。"),

    # ================================================================ 第六章
    ("h1", "六、模型评价与推广"),
    ("h2", "6.1 模型优点"),
    ("p", "（1）数据核验扎实、验证方式保守。所有“题面陷阱”（对齐键、对数底数、零点地板、相关类型、文件尺寸、空模板）都逐项核验并用可复核的数字报告；"
          "问题 1 使用嵌套交叉验证，把“选模型”放进评估框架，同时报告随机、整风格留组与重复编号留组三种协议，以及共形区间与联合覆盖。"),
    ("p", "（2）结论强度与证据匹配。对 Top-3 名单，给出 bootstrap 入选频率、方法间 Jaccard、模块级频率与阈值敏感性；"
          "对 0–6 等级，明确“不可识别”并用双协议对照；对迁移安全，区分“模型预测不恶化”与“真实 K 不恶化”。"),
    ("p", "（3）生成模型结构自洽、全流程可复现。先生成 226 个基础量、再按复原公式计算派生量，使 231 维向量内部一致；"
          "零/负值原子用类条件收缩经验分布显式建模；随机种子、参数网格、算法细节与结果文件一一对应，论文数字可追溯到具体结果表。"),
    ("h2", "6.2 局限性与改进方向"),
    ("p", "（1）模型容量。问题 1 的主模型是线性的 PLS/岭回归；在 250 个样本、231 个高度相关特征下这是稳健的选择，但可能漏掉非线性与交互。"
          "如果样本量增大，可以尝试带稀疏约束的树模型或多任务网络，并用同样的嵌套验证公平比较。"),
    ("p", "（2）标签识别性。4.csv 是逐品评员 z 化后的连续值，原始 0–6 等级不可唯一还原。本文用公开协议给出工作等级，"
          "但这不能替代真实的评分卡数据。若能在数据收集阶段记录每位品评员的原始整数打分，就能真正校准序数模型，并评估等级准确率[17]。"),
    ("p", "（3）关联不等于因果。问题 2 的 Top-3 是关联排序，不是化学贡献度；共变网络也不能区分“原因”与“伴随现象”。"
          "要论证因果，需要设计加标实验（在真实啤酒中按预测添加化合物再品评），原始研究[1]正是这样验证的。"),
    ("p", "（4）生成与迁移的样本量。每个风格只有 3–28 个样本，生成模型学到的是“类内分布的一个收缩估计”，"
          "不能保证覆盖真实酿造中所有可能的配方；迁移后的“安全”也只在模型预测与固定协议下成立。"
          "若能把生成配方真正酿造并做感官评价，才能形成闭环验证。"),
    ("p", "（5）缺失与异常。虽然额外缺失实验显示模型退化是渐进的，但本文只用中位数/KNN 填补，没有对缺失机制建模，"
          "也没有做多重插补的不确定性传播；如果缺失比例显著上升，需要重新评估。"),
    ("h2", "6.3 应用推广"),
    ("p", "本文的框架可以直接用于啤酒厂的质量控制与风味设计：给定一批原料与发酵条件测得的化学谱，先用问题 1 的模型预测感官画像，"
          "再用问题 2 的 Top-3 与模块找到“要动哪一组化合物”，最后用问题 3 的结构一致生成与约束迁移给出候选配方，并检查缺陷指标。"
          "同样的“多通道测量 + 人工评分 + 约束生成”框架也可以迁移到其他发酵食品（葡萄酒、清酒、酱油）或一般工业配方问题："
          "核心步骤都是“先核验刻度与缺失 → 再做可解释的关联/预测 → 最后用结构约束与安全边界生成候选”。"),

    # ================================================================ 第七章
    ("h1", "七、结论与建议"),
    ("p", "本文围绕 250 款比利时商品啤酒的 231 项化学测量与 50 个感官维度，完成了数据核验、感官评分、关联解释、条件生成与跨风格迁移五项工作。主要结论如下："),
    ("list", ["（1）数据核验：1.csv 的 37 个参数列是 log10 记录值，非正原生值被“最小正值一半”替代；2.csv/5.csv/6.csv 均为 Spearman 相关矩阵；"
              "231 个特征中只有 73 个缺失，但删行会损失 25.2% 样本；5 个派生量可由基础量精确重建（残差约 10⁻¹⁰），其本质是热量换算与四类气味活度加和。",
              "（2）感官评分：PLS（10 主成分）在嵌套交叉验证下 50 维平均 R²=0.217、MAE=0.354（均值基线 0.417）；整风格留组时 R²=0.157；"
              "90% 共形区间的边际覆盖率为 90.1%，但 50 维联合覆盖仅 84%。按协议 A 给出 250×50 的 0–6 工作等级并填制 3.xlsx；"
              "协议 A/B 的逐格一致率只有 23.4%，说明绝对等级依赖分级口径，原始 0–6 等级不可唯一还原。",
              "（3）关联解释：|ρ|≥0.6 的共变网络有 266 条边、19 个非单点模块、模块度 0.745；模块的化学来源与酿酒常识一致（酒花萜类、酵母酯/醇、麦芽呋喃）。"
              "Top-3 中酸度—pH、苦度—异α-酸、酒精感—乙醇、碳酸感—CO₂、4-VG—4-乙烯基愈创木酚等对应关系化学上成立；"
              "但 200 次 bootstrap 下入选频率中位数仅 0.41、方法间平均 Jaccard 仅 0.27，说明“具体名单”高度不稳定，必须与稳定性一起使用。",
              "（4）生成：结构一致（226 基础 + 5 派生）的类条件经验边际 copula 在留出比较中能量距离 22.47、MMD² 0.233，优于全局模型与高斯条件模型；"
              "三个风格各生成 100 条化合物谱与 50 维感官画像，画像与真实风格均值的相关系数为 0.88/0.96/0.97；独立分类器对生成样本的风格判定概率约 0.72–0.74。",
              "（5）迁移：11 个 Pils/Lager→Tripel 迁移样本的四项缺陷与陈酒花味 Y38 全部逐对象不升高，监督分类器判为 Tripel 的平均概率由 2.4% 升至 39.1%；"
              "但一维 Wasserstein 下界（DMS 1.78、双乙酰 1.47、4-VG 0.024、反-2-壬烯醛 1.17）说明“逐对象不恶化”与“完整匹配目标分布”不可兼得，"
              "真实 K 的绝对等级仍不可识别。"]),
    ("p", "基于以上结论，给出三条建议。第一，数据层面：如果希望得到“真实 0–6 等级”，应在品评环节保留每名品评员的原始整数打分与个人校准记录，"
          "而不是只保留 z 化后的均值；对痕量缺陷化合物（DMS、双乙酰、4-VG、反-2-壬烯醛）应报告检测限与缺失机制，因为它们的阈值效应最容易被缺失与对数地板扭曲。"),
    ("p", "第二，建模层面：在 250 个样品、231 个高度相关特征的规模下，线性多输出模型已经能拿到大部分可解释信号；"
          "报告结果时应同时给出折外指标、不确定性区间与不同验证协议下的表现，避免用一个平均 R² 掩盖 50 个维度之间的巨大差异。"),
    ("p", "第三，应用层面：生成/迁移模型可以用于“给出候选配方并筛选缺陷风险”，但不能替代真实酿造与品评；"
          "在工业落地时，应把本文的“模型内安全约束”与“真实阈值检测”串联起来，形成“生成候选—实验室验证—反馈更新”的闭环。"),

    # ================================================================ 参考文献
    ("h1", "参考文献"),
    ("ref", "[1] Schreurs M, Piampongsant S, Roncoroni M, et al. Predicting and improving complex beer flavor through machine learning. Nature Communications, 15: 2368, 2024."),
    ("ref", "[2] Meilgaard M C. Flavor chemistry of beer. Part II: Flavor and threshold of 239 aroma volatiles. Master Brewers Association of the Americas Technical Quarterly, 12(3): 107–117, 1975."),
    ("ref", "[3] Verstrepen K J, Van Laere S D M, Vanderhaegen B M P, et al. Flavor-active esters: adding fruitiness to beer. Journal of Bioscience and Bioengineering, 96(2): 110–118, 2003."),
    ("ref", "[4] Dzialo M C, Park R, Steensels J, et al. Physiology, ecology and industrial applications of aroma formation in yeast. FEMS Microbiology Reviews, 41(Supp_1): S95–S128, 2017."),
    ("ref", "[5] Takoi K, Itoga Y, Koie K, et al. The contribution of geraniol metabolism to the citrus flavour of beer: synergy of geraniol and β-citronellol under coexistence with excess linalool. Journal of the Institute of Brewing, 116(3): 251–260, 2010."),
    ("ref", "[6] Bossaert S, Crauwels S, De Rouck G, et al. The power of sour — a review: old traditions, new opportunities. BrewingScience, 72: 78–88, 2019."),
    ("ref", "[7] Lusk L T, Kay S B, Porubcan A, et al. Key olfactory cues for beer oxidation. Journal of the American Society of Brewing Chemists, 70(4): 257–261, 2012."),
    ("ref", "[8] Rubin D B. Inference and missing data. Biometrika, 63(3): 581–592, 1976."),
    ("ref", "[9] Box G E P, Cox D R. An analysis of transformations. Journal of the Royal Statistical Society: Series B, 26(2): 211–252, 1964."),
    ("ref", "[10] Spearman C. The proof and measurement of association between two things. American Journal of Psychology, 15(1): 72–101, 1904."),
    ("ref", "[11] Hoerl A E, Kennard R W. Ridge regression: biased estimation for nonorthogonal problems. Technometrics, 12(1): 55–67, 1970."),
    ("ref", "[12] Wold S, Martens H, Wold H. The multivariate calibration problem in chemistry solved by the PLS method. In: Matrix Pencils, Lecture Notes in Mathematics 973. Berlin: Springer, 286–293, 1983."),
    ("ref", "[13] Cawley G C, Talbot N L C. On over-fitting in model selection and subsequent selection bias in performance evaluation. Journal of Machine Learning Research, 11: 2079–2107, 2010."),
    ("ref", "[14] Lei J, G'Sell M, Rinaldo A, et al. Distribution-free predictive inference for regression. Journal of the American Statistical Association, 113(523): 1094–1111, 2018."),
    ("ref", "[15] Angelopoulos A N, Bates S. Conformal prediction: a gentle introduction. Foundations and Trends in Machine Learning, 16(4): 494–591, 2023."),
    ("ref", "[16] NumPy Developers. numpy.quantile and numpy.searchsorted documentation. https://numpy.org/doc/stable/reference/generated/numpy.quantile.html, 访问时间 2026-10-26."),
    ("ref", "[17] Rennie J D M, Srebro N. Loss functions for preference levels: regression with discrete ordered labels. In: Proceedings of the IJCAI Multidisciplinary Workshop on Advances in Preference Handling, 180–186, 2005."),
    ("ref", "[18] Manski C F. Partial Identification of Probability Distributions. New York: Springer, 2003."),
    ("ref", "[19] Blondel V D, Guillaume J-L, Lambiotte R, et al. Fast unfolding of communities in large networks. Journal of Statistical Mechanics: Theory and Experiment, 2008(10): P10008, 2008."),
    ("ref", "[20] Fortunato S, Barthélemy M. Resolution limit in community detection. Proceedings of the National Academy of Sciences, 104(1): 36–41, 2007."),
    ("ref", "[21] Meinshausen N, Bühlmann P. Stability selection. Journal of the Royal Statistical Society: Series B, 72(4): 417–473, 2010."),
    ("ref", "[22] Oladokun O, Tarrega A, Mendez-Sevillano S, et al. The impact of hop bitter acid and polyphenol profiles on the perceived bitterness of beer. Food Chemistry, 205: 212–220, 2016."),
    ("ref", "[23] Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and powerful approach to multiple testing. Journal of the Royal Statistical Society: Series B, 57(1): 289–300, 1995."),
    ("ref", "[24] MacKinnon J G. Thirty years of heteroskedasticity-robust inference. In: Recent Advances and Future Directions in Causality, Prediction, and Specification Analysis. New York: Springer, 437–461, 2012."),
    ("ref", "[25] Liu H, Lafferty J, Wasserman L. The nonparanormal: semiparametric estimation of high dimensional undirected graphs. Journal of Machine Learning Research, 10: 2295–2328, 2009."),
    ("ref", "[26] Ledoit O, Wolf M. A well-conditioned estimator for large-dimensional covariance matrices. Journal of Multivariate Analysis, 88(2): 365–411, 2004."),
    ("ref", "[27] Tipping M E, Bishop C M. Probabilistic principal component analysis. Journal of the Royal Statistical Society: Series B, 61(3): 611–622, 1999."),
    ("ref", "[28] Székely G J, Rizzo M L. Energy statistics: a class of statistics based on distances. Journal of Statistical Planning and Inference, 143(8): 1249–1272, 2013."),
    ("ref", "[29] Gretton A, Borgwardt K M, Rasch M J, et al. A kernel two-sample test. Journal of Machine Learning Research, 13: 723–773, 2012."),
    ("ref", "[30] Kingma D P, Welling M. Auto-encoding variational Bayes. In: International Conference on Learning Representations (ICLR), 2014."),
    ("ref", "[31] Sohn K, Lee H, Yan X. Learning structured output representation using deep conditional generative models. In: Advances in Neural Information Processing Systems 28, 3483–3491, 2015."),
    ("ref", "[32] Vallender S S. Calculation of the Wasserstein distance between probability distributions on the line. Theory of Probability and Its Applications, 18(4): 784–786, 1974."),
    ("ref", "[33] DeepSeek. DeepSeek-V3.2, 深度求索（DeepSeek）, 使用日期 2026-10-26."),

    # ================================================================ AI 声明
    ("h1", "AI 工具使用声明"),
    ("p", "本参赛队在竞赛过程中使用了 DeepSeek（DeepSeek-V3.2，深度求索）[33] 作为辅助工具，使用日期为 2026-10-26。具体使用情况如下："),
    ("list", ["（1）部分论文段落的文字组织与润色：在参赛队给出建模思路、结果数值与结论要点后，DeepSeek 协助把其中一部分段落整理为更通顺的书面表达；"
              "文中所有数值、公式与结论均由参赛队从实际计算结果中核对与修改后确定。",
              "（2）代码调试与文档整理：辅助检查绘图脚本与论文排版脚本的语法问题，协助整理支撑材料的文件说明与目录结构。"]),
    ("p", "核心的建模思路、算法设计、参数选择、数据处理、结果分析与结论由参赛队独立完成。参赛队对所有 AI 工具参与生成的内容逐项核验与修改，并对其正确性负责。"
          "更详细的使用目的、交互记录、采纳内容与人工修改情况，见支撑材料中的《AI 工具使用详情说明.pdf》。"),

    # ================================================================ 附录
    ("h1", "附录 A  核心代码（节选）"),
    ("p", "完整的可复现代码见支撑材料 code/ 目录（本论文所有数字均由这些脚本生成）。以下仅摘录关键步骤的 Python 实现，便于读者核对算理。"),
    ("h3", "A.1 训练折内的预处理（中位数填补 → 1%/99% 缩尾 → 标准化）"),
    ("code", """class RobustPreprocessor(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.median_ = np.nan_to_num(np.nanmedian(X, axis=0), nan=0.0)
        filled = np.where(np.isnan(X), self.median_, X)
        self.low_, self.high_ = np.quantile(filled, [0.01, 0.99], axis=0)
        clipped = np.clip(filled, self.low_, self.high_)
        self.mean_ = clipped.mean(axis=0)
        self.scale_ = clipped.std(axis=0, ddof=0)
        self.scale_[self.scale_ <= 1e-12] = 1.0
        return self
    def transform(self, X):
        X = np.asarray(X, dtype=float)
        filled = np.where(np.isnan(X), self.median_, X)
        clipped = np.clip(filled, self.low_, self.high_)
        return (clipped - self.mean_) / self.scale_"""),
    ("h3", "A.2 两层交叉验证选模（外层 5 折、内层 3 折）"),
    ("code", """CANDIDATES = ([("ridge", a) for a in (0.1, 1, 10, 100, 1000)] +
              [("pls", k) for k in (2, 5, 10, 20)])

def make_model(family, param):
    reg = Ridge(alpha=param) if family == "ridge" else PLSRegression(n_components=int(param))
    return TransformedTargetRegressor(
        regressor=Pipeline([("prep", RobustPreprocessor()), ("reg", reg)]),
        transformer=StandardScaler())

def inner_select(X_tr, Y_tr, seed):
    best = None
    kf = KFold(3, shuffle=True, random_state=seed)
    for family, param in CANDIDATES:
        errs = []
        for tr, va in kf.split(X_tr):
            m = make_model(family, param).fit(X_tr[tr], Y_tr[tr])
            pred = m.predict(X_tr[va])
            sd = Y_tr[tr].std(axis=0, ddof=0) + 1e-12
            errs.append(np.mean(((Y_tr[va] - pred) / sd) ** 2))
        score = np.mean(errs)
        if best is None or score < best[0]:
            best = (score, family, param)
    return best[1], best[2]"""),
    ("h3", "A.3 0–6 工作等级：协议 A 与协议 B"),
    ("code", """def protocol_A(scores, mu, sd, slope=1.0):
    raw = 3.0 + slope * (scores - mu) / sd
    return np.clip(np.floor(raw + 0.5), 0, 6).astype(int)

def protocol_B(scores, Y_train):
    cuts = np.quantile(Y_train, np.arange(1, 7) / 7, axis=0, method="linear")
    return np.column_stack([
        np.searchsorted(cuts[:, j], scores[:, j], side="right")
        for j in range(scores.shape[1])])"""),
    ("h3", "A.4 共表达网络、模块度与 Borda 聚合"),
    ("code", """rho = pd.read_csv("2.csv", index_col=0).values          # 已核验为 Spearman
A = np.where(np.abs(rho) >= 0.6, np.abs(rho), 0.0)
np.fill_diagonal(A, 0.0)
G = nx.from_numpy_array(A)
comms = nx.community.louvain_communities(G, weight="weight", seed=20261026)
Q = nx.community.modularity(G, comms, weight="weight")

def borda_top3(scores_by_method, n_features=231):
    ranks = [rankdata(-s, axis=0, method="average") for s in scores_by_method]
    mean_rank = np.mean(ranks, axis=0)                # 231 x 50
    order = np.argsort(mean_rank, axis=0, kind="stable")
    return order[:3, :].T                             # 每个目标 3 个变量"""),
    ("h3", "A.5 结构一致的类条件生成（226 基础量 + 5 派生量）"),
    ("code", """# 1) 生成 226 个基础量（类条件收缩经验边际 + 共享相关矩阵的 copula）
Z = rng.standard_normal((n, 226)) @ factor.T          # factor 来自共享相关阵 R
U = norm.cdf(Z)
X_base = np.column_stack([inverse_weighted_cdf(j, g, U[:, j])
                          for j in range(226)])
# 2) 由基础量按复原公式计算 5 个派生聚合（原生尺度）
agg = candidate_derived_from_native(X_base)
if not np.all(np.isfinite(agg)) or np.any(agg <= 0):
    continue                                           # 拒绝并重采样，不截断
# 3) 按已核验的对数规则映射回 1.csv 记录刻度，再交给评分器
X_record = native_to_recorded(X_base, agg, floors)"""),
    ("h3", "A.6 观测源守卫下的受约束迁移（182 维精确二次规划）"),
    ("code", """# 固定 44 个坐标（C 坐标 + 派生父变量 + 基础参数），其余 182 个为自由坐标
def qp_free_coords(p, beta, s, low, high, rhs):
    x = lambda m: np.clip(p - m * s**2 * beta, low, high)
    if beta @ x(0.0) <= rhs:                           # 无需压缩评分
        return x(0.0), 0.0
    right = 1.0
    while beta @ x(right) > rhs and right < 1e60:      # 倍增找括号
        right *= 2.0
    lo, hi = 0.0, right
    for _ in range(75):                                # 二分乘子
        mid = 0.5 * (lo + hi)
        if beta @ x(mid) <= rhs: hi = mid
        else: lo = mid
    return x(hi), hi

# 迁移后必须用保存并重读的 CSV 重新计算 5 个派生量与 50 维评分，
# 判定 after <= cap（cap = min{原值预测, 重表达预测, 观测值}），不允许正容差。"""),

    ("h1", "附录 B  50 个感官维度的 Top-3 关键化合物（完整表）"),
    ("p", "括号内为 200 次 bootstrap 下该化合物进入 Top-3 的入选频率。频率低不代表不重要，而是说明“换一袋样品后这个席位容易被替换”。"),
    ("table", "表 B-1  50 个感官维度的 Top-3 关键化合物", *appendix_top3(),
     [Cm(1.3), Cm(3.2), Cm(3.6), Cm(3.6), Cm(3.6)], 7.5),

    ("fig", "fig08b_Q2_top3_full.png",
     "图 B-1  50 个感官维度的 Top-3 关键化合物与 200 次 bootstrap 入选频率（完整版；正文图 9 为代表性维度缩略版）。", 19.0),

    ("h1", "附录 C  支撑材料清单"),
    ("p", "支撑材料目录 A赛道_复原解答/ 的组织如下："),
    ("table", "表 C-1  支撑材料清单",
     ["路径", "内容"],
     [["paper/A赛道论文_啤酒风味复原版.pdf", "本论文提交版 PDF"],
      ["paper/AI工具使用详情说明.pdf", "竞赛规定的 AI 工具使用详情说明"],
      ["results/Q1_评分表_官方3xlsx格式.xlsx", "问题 1 最终答案：按官方 3.xlsx 格式填写的 12 张评分卡与 summary"],
      ["results/Q1_连续评分预测_*.csv", "问题 1 的 250×50 连续预测（全拟合与折外）"],
      ["results/Q1_0-6分级_协议A/协议B_*.csv", "问题 1 的 0–6 工作等级矩阵（两种协议、全拟合与折外）"],
      ["results/Q2_Top3关键化合物_汇总.csv", "问题 2 的 50×3 Top-3 关键化合物及稳定性指标"],
      ["results/Q2_网络节点与模块.csv、Q2_共变模块构成.csv", "共变网络节点、边与模块的化学构成"],
      ["results/Q3_生成化合物谱_*.csv", "Tripel/Kriek/Lambic 各 100 条结构一致的化合物谱"],
      ["results/Q3_生成感官画像_D04尺度.csv", "300 条生成样本的 50 维感官画像"],
      ["results/Q3_跨风格迁移_*.csv、Q3_迁移_*.csv", "11 个 Pils/Lager→Tripel 迁移配方与缺陷/感官安全对照"],
      ["code/", "复原、补充分析、绘图、评分卡、公式与论文排版脚本"],
      ["code/full_pipeline_project/", "脱敏版完整计算工程（12 个脚本 + 8 个数据文件；运行 run_all.py 复现问题 1–3）"],
      ["code/_impl_spec.md", "完整计算工程的逐脚本实现规格说明（参数、种子、公式、限制）"],
      ["README.md", "结果文件与代码的逐项说明"]],
     [Cm(7.0), Cm(8.2)], 8.5),
    ("p", "说明：原始附件 1–8 未做任何修改；所有处理结果、图、表均由 code/ 下脚本重新生成。"
          "若需复核，可按 README.md 的顺序运行脚本；随机种子为 20261026，在不同 BLAS/线程配置下末位数字可能有微小差异。"),
]
