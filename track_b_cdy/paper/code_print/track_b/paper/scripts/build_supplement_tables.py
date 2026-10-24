#!/usr/bin/env python3
"""Build supplemental tables from frozen results. AI-assisted: OpenAI Codex / GPT-6 family, OpenAI, 2026-10-24."""
from pathlib import Path
import csv,json,hashlib
REPO=Path(__file__).resolve().parents[3]
PAPER=REPO/'track_b/paper'
def esc(s):
    return str(s).replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')
def fmt(v):
    return f'{float(v):.5g}'
names={
'theta_deg':('结构面倾角',r'$^\circ$'),
'thickness_normal_m':('法向厚度','m'),
'rock_volume_fraction':('岩体体积分数','1'),
'bridge_fraction':('岩桥承载面积比例','1'),
'bridge_cohesion_kpa':('岩桥有效黏聚力','kPa'),
'rock_mu':('岩面摩擦系数','1'),
'initial_temp_c':('初始裂隙温度',r'$^\circ$C'),
'diffusivity_m2_s':('热扩散率',r'm$^2$/s'),
'interface_depth_m':('热路径深度','m'),
'station_source_offset_c':('站点至源区温度偏移',r'$^\circ$C'),
'storativity':('储水量/水头比','1'),
'drainage_hours':('排水时间常数','h'),
'connected_depth_m':('最大连通水头','m'),
'rain_multiplier':('有效入渗倍率','1'),
'melt_mm_deg_day':('度日融化系数',r'mm/($^\circ$C$\cdot$d)'),
'damage_rate_h_inv':('损伤速率系数',r'h$^{-1}$'),
'damage_exponent':('应力比幂次','1'),
'initial_damage':('初始损伤','1'),
'drainage_damage_coupling':('损伤排水耦合系数','1'),
}
protocol_path='track_b/research/q2/round3/config/experiment_v1.json'
comparison_path='track_b/research/q2/round3/results/analytic_thermal/model_comparison.csv'
d=json.loads((REPO/protocol_path).read_text())
rows=list(csv.DictReader((REPO/comparison_path).open()))
chunks=[r'\subsection{结构水热共同参数设计}\label{app:parameter-table}'+'\n',
'下表给出空间填充设计的19项参数上下限及取样尺度。四机制共享256个参数点，两强度政策形成2048个设计情景；参数设计与概率先验分别登记。实际各参数点见相应参数表。\n',
r'\begingroup\small\begin{longtable}{p{3.8cm}p{2.2cm}rrp{1.6cm}}'+'\n',
r'\caption{共同参数设计范围。}\label{tab:app-parameters}\\'+'\n',
r'\toprule 参数 & 单位 & 下限 & 上限 & 取样尺度\\\midrule\endfirsthead'+'\n',
r'\toprule 参数 & 单位 & 下限 & 上限 & 取样尺度\\\midrule\endhead'+'\n']
for k,v in d['ranges'].items():
    n,u=names[k];chunks.append(f"{n} & {u} & {fmt(v['min'])} & {fmt(v['max'])} & "+('对数' if v['scale']=='log' else '线性')+r'\\'+'\n')
chunks += [r'\bottomrule\end{longtable}\endgroup'+'\n',
r'\subsection{解析热机制分类与裕度补充}'+'\n',
'分类按相应初态与首次过阈定义，在同一设计表内汇总；初始越阈与未来越阈分列。\n',
r'\begin{table}[htbp]\centering\small\caption{最终解析热版本的机制分类与最小稳定裕度中位数。}\label{tab:app-mechanisms}'+'\n',
r'\begin{tabular}{llrrrr}\toprule 机制 & 强度政策 & 未来越阈 & 初始越阈 & 时域内保持 & 裕度中位数\\\midrule'+'\n']
for r in rows:
    policy='线性延伸' if r['law_policy']=='linear_extension' else '暖端岩接触'
    mech=r['mechanism_id'].replace('_', '+')
    chunks.append(f"{mech} & {policy} & {r['interval_crossing_n']} & {r['left_censored_n']} & {r['never_crossed_n']} & {float(r['median_min_margin']):.4f}"+r'\\'+'\n')
chunks += [r'\bottomrule\end{tabular}\end{table}'+'\n']
(PAPER/'appendices/parameter_tables.tex').write_text(''.join(chunks))
record={'generated_from':[{'path':n,'sha256':hashlib.sha256((REPO/n).read_bytes()).hexdigest()} for n in [protocol_path,comparison_path]],'parameter_rows':len(d['ranges']),'mechanism_rows':len(rows),'all_classification_counts_per_row_256':all(sum(int(r[k]) for k in ['interval_crossing_n','left_censored_n','never_crossed_n','missing_n'])==256 for r in rows)}
(PAPER/'qa/supplement_tables_check.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False))
