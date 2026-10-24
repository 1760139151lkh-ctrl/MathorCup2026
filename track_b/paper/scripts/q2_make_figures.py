"""Redraw three compact Chinese publication figures from frozen Q2 results.

No model execution, fitting, new scenarios or research-packet writes. PDF and
300dpi PNG outputs plus provenance/support JSON are confined to figures/q2.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "track_b/paper/figures/q2"
OUT.mkdir(parents=True, exist_ok=True)
# The plotting cache is temporary and remains inside the owned figure folder.
_cache = tempfile.TemporaryDirectory(prefix=".q2_mpl_", dir=OUT)
os.environ["MPLCONFIGDIR"] = _cache.name
for _prior_cache in [Path.home()/'.cache/matplotlib',Path.home()/'.matplotlib']:
    for _cache_file in _prior_cache.glob('fontlist-v*.json'):
        shutil.copy2(_cache_file,Path(_cache.name)/_cache_file.name)

import matplotlib
matplotlib.use("Agg")
from matplotlib import colors, font_manager, ft2font
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RESEARCH = ROOT / "track_b/research/q2/round3"
INPUTS = {
    "mechanism_comparison": RESEARCH / "results/analytic_thermal/model_comparison.csv",
    "critical_head": RESEARCH / "results/critical_relations.csv",
    "joint_sensitivity": RESEARCH / "results/analytic_thermal/joint_sensitivity.csv",
    "laboratory_cv": RESEARCH / "lab_strength/model/results/holdout_summary.csv",
}
FONT = Path("/Users/maxchen/Library/Fonts/PingFang Regular_0.ttf")
COLORS = {"linear_extension": "#325B7B", "thawed_rock_contact": "#B8753B",
          "temperature": "#325B7B", "normal_stress": "#B8753B"}
MECHANISMS = ["S", "S_T", "S_H", "S_T_H"]
MECHANISM_LABELS = ["结构 S", "S+T", "S+H", "S+T+H"]
REPS = [0,36,72,109,145,182,218,255]
PARAMETER_LABELS = {
    "theta_deg":"结构面倾角", "initial_temp_c":"初始界面温度",
    "initial_damage":"初始损伤", "station_source_offset_c":"站点—源区温差",
    "thickness_normal_m":"法向厚度", "interface_depth_m":"界面传热深度",
    "bridge_fraction":"岩桥面积比例", "rock_volume_fraction":"岩石体积分数",
    "bridge_cohesion_kpa":"岩桥黏聚力", "rock_mu":"岩面摩擦系数",
    "melt_mm_deg_day":"融水系数", "storativity":"储水系数",
    "drainage_hours":"排水时间", "diffusivity_m2_s":"热扩散率",
    "damage_exponent":"损伤指数", "rain_multiplier":"降水映射系数",
    "damage_rate_h_inv":"损伤速率", "connected_depth_m":"连通水头上限",
    "drainage_damage_coupling":"损伤—排水耦合",
}


def digest(path, role):
    return {"path":path.relative_to(ROOT).as_posix(),"bytes":path.stat().st_size,
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"role":role}


def configure():
    font_manager.fontManager.addfont(str(FONT))
    # A unique in-memory alias prevents the same family name resolving to the
    # macOS CFF collection, which can produce mismatched CIDFontType2 embedding.
    family='Q2-PingFang-Regular-Static'
    font_manager.fontManager.ttflist.append(font_manager.FontEntry(
        fname=str(FONT),name=family,style='normal',variant='normal',weight='normal',stretch='normal'))
    face=ft2font.FT2Font(str(FONT))
    assert all(face.get_char_index(ord(ch)) for ch in "结构温度水损伤裕阈值")
    matplotlib.rcParams.update({"font.family":family,"font.size":7.5,
        "axes.labelsize":7.5,"axes.titlesize":8.0,"xtick.labelsize":7.0,"ytick.labelsize":7.0,
        "axes.linewidth":.55,"xtick.major.width":.5,"ytick.major.width":.5,
        "xtick.major.size":2.5,"ytick.major.size":2.5,"xtick.major.pad":2.,"ytick.major.pad":2.,
        "axes.unicode_minus":False,"pdf.fonttype":42,"ps.fonttype":42,
        "savefig.dpi":300,"axes.spines.top":False,"axes.spines.right":False,
        "text.color":"#222222","axes.labelcolor":"#222222","axes.edgecolor":"#555555",
        "grid.color":"#DDDDDD","grid.linewidth":.4,"mathtext.fontset":"dejavusans"})
    return family


def save(fig, stem, title):
    fig.savefig(OUT/f"{stem}.pdf",metadata={"Title":title,"Creator":"q2_make_figures.py; frozen analytical results",
        "CreationDate":None,"ModDate":None},dpi=300)
    fig.savefig(OUT/f"{stem}.png",dpi=300)
    plt.close(fig)
    return [digest(OUT/f"{stem}.{ext}","publication_figure" if ext=="pdf" else "300dpi_visual_review") for ext in ["pdf","png"]]


def mechanism_figure(data):
    table=data.copy()
    assert len(table)==8 and (table.n_parameter_sets==256).all()
    assert (table.interval_crossing_n+table.left_censored_n+table.never_crossed_n+table.missing_n==256).all()
    assert (table.left_censored_n==31).all() and (table.missing_n==0).all()
    rows=table[table.law_policy=="linear_extension"].set_index("mechanism_id")
    assert abs(rows.loc['S_T','median_min_margin']-.48529976742120917)<1e-12
    assert abs(rows.loc['S_T_H','median_min_margin']-.4717932586129435)<1e-12
    fig=plt.figure(figsize=(17/2.54,4.5/2.54))
    a=fig.add_axes([.065,.20,.375,.53]);b=fig.add_axes([.57,.20,.395,.53])
    x=np.arange(4);width=.28
    handles=[]
    for k,policy in enumerate(["linear_extension","thawed_rock_contact"]):
        q=table[table.law_policy==policy].set_index('mechanism_id').loc[MECHANISMS]
        xx=x+(k-.5)*width
        bars=a.bar(xx,q.interval_crossing_n,width=width*.9,color=COLORS[policy],alpha=.95)
        for bar,value in zip(bars,q.interval_crossing_n):
            a.text(bar.get_x()+bar.get_width()/2,value+.7,str(int(value)),ha='center',va='bottom',fontsize=7.0)
        median=q.median_min_margin.to_numpy()
        low=median-q.p05_min_margin.to_numpy();high=q.p95_min_margin.to_numpy()-median
        b.errorbar(x+(k-.5)*.08,median,yerr=np.vstack([low,high]),fmt='o' if k==0 else 's',
            ms=3.5 if k==0 else 2.8,elinewidth=.65,capsize=2,color=COLORS[policy],
            markerfacecolor=COLORS[policy] if k==0 else 'white',markeredgewidth=.75,zorder=2+k)
        handles.append(Patch(facecolor=COLORS[policy],label='线性冻结关系' if k==0 else '暖端岩接触对照'))
    a.set(xticks=x,xticklabels=MECHANISM_LABELS,ylim=(0,37),yticks=[0,10,20,30],ylabel='后续越阈数 / 256')
    a.set_title('(a) 共同参数下的四机制竞争',loc='left',pad=7)
    b.axhline(0,color='#666666',ls='--',lw=.65,zorder=1)
    b.set(xticks=x,xticklabels=MECHANISM_LABELS,ylim=(-.66,3.1),yticks=[-.5,0,1,2,3],ylabel='评估期最小稳定裕度')
    b.set_title('(b) 中位数与设计分位范围',loc='left',pad=7)
    for j,val in enumerate(rows.loc[MECHANISMS].median_min_margin):
        b.text(j,val+.18,f'{val:.3f}',ha='center',va='bottom',fontsize=6.5,color=COLORS['linear_extension'])
    a.grid(axis='y',alpha=.65);a.set_axisbelow(True);b.grid(axis='y',alpha=.5);b.set_axisbelow(True)
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.53,1.0),ncol=2,frameon=False,
        handlelength=1.3,columnspacing=2.3,fontsize=7.4)
    outputs=save(fig,'q2_mechanism_comparison','Q2 四机制共同设计的稳定性比较')
    return dict(figure_id='q2-mechanism-comparison',outputs=outputs,size_cm=[17,4.5],
        input_keys=['mechanism_comparison'],selection='All8 rows of final analytic thermal comparison,4 mechanisms x2 policies; no scenario filtering',
        plotted_records=table.to_dict('records'),scientific_layer='conditional_scenario',
        caption_note='解析热参考；每个机制与策略均有256个共同参数设计点，初始已不稳定31个保留为左删失。误差线为5%–95%设计分位，非事件概率或置信区间。')


def critical_sensitivity_figure(critical,sensitivity):
    crit=critical[critical.temperature_c.isin([-6.,-3.,-1.,-.5])].copy()
    pids=[f'q2r3-p{i:04d}' for i in REPS]
    assert len(crit)==32 and set(crit.parameter_set_id)==set(pids)
    sens=sensitivity[(sensitivity.mechanism_id=='S_T_H')&(sensitivity.law_policy=='linear_extension')].copy()
    sens['abs_rho']=sens.spearman_rho.abs()
    sens=sens.sort_values(['abs_rho','parameter'],ascending=[False,True]).head(8)
    assert len(sens)==8 and (sens.n_joint_design==256).all()
    fig=plt.figure(figsize=(17/2.54,5.4/2.54))
    a=fig.add_axes([.085,.215,.37,.64]);cbax=fig.add_axes([.47,.215,.012,.64]);b=fig.add_axes([.715,.215,.255,.64])
    cmap=matplotlib.colormaps['YlGnBu'];norm=colors.Normalize(0,60)
    temperatures=[-6.,-3.,-1.,-.5]
    for i,pid in enumerate(pids):
        for j,t in enumerate(temperatures):
            row=crit[(crit.parameter_set_id==pid)&(crit.temperature_c==t)].iloc[0]
            status=row.root_status
            if status=='positive_pressure_root':
                val=float(row.critical_head_m);fill=cmap(norm(val));hatch=None
                label=f'{val:.1f}'+('＊' if not row.root_reachable_before_capacity else '')
                color='white' if val>34 else '#222222'
            elif status=='dry_already_critical':
                fill='#E6E6E6';hatch=None;label='干态越阈';color='#333333'
            elif status=='no_pressure_only_root':
                fill='white';hatch='///';label='无水压根';color='#333333'
            else:raise ValueError(status)
            a.add_patch(Rectangle((j-.5,i-.5),1,1,facecolor=fill,edgecolor='#CCCCCC',lw=.4,hatch=hatch))
            a.text(j,i,label,ha='center',va='center',fontsize=6.5,color=color,
                bbox=dict(facecolor=fill,edgecolor='none',pad=.1) if hatch else None)
    a.set(xlim=(-.5,3.5),ylim=(7.5,-.5),xticks=range(4),xticklabels=['-6','-3','-1','-0.5'],
          yticks=range(8),yticklabels=[f'p{i:04d}' for i in REPS],xlabel='界面温度 / °C')
    a.tick_params(length=0);a.set_title('(a) 共同初态的临界水头',loc='left',pad=7)
    for spine in a.spines.values():spine.set_visible(False)
    cb=fig.colorbar(ScalarMappable(norm=norm,cmap=cmap),cax=cbax,ticks=[0,20,40,60])
    cb.set_label('临界水头 / m',fontsize=7.0,labelpad=2)
    if cb.solids is not None:cb.solids.set_rasterized(False)
    y=np.arange(len(sens));v=sens.spearman_rho.to_numpy()
    b.barh(y,v,color=[COLORS['linear_extension'] if z<0 else COLORS['thawed_rock_contact'] for z in v],height=.58)
    b.axvline(0,color='#555555',lw=.6)
    b.set(yticks=y,yticklabels=[PARAMETER_LABELS[k] for k in sens.parameter],ylim=(7.7,-.7),
          xlim=(-.66,.43),xticks=[-.6,-.3,0,.3],xlabel=r'Spearman $\rho_s$')
    b.tick_params(axis='y',length=0,pad=3,labelsize=6.9)
    b.grid(axis='x',alpha=.5);b.set_axisbelow(True)
    b.set_title('(b) 耦合模型联合敏感性',loc='left',pad=7)
    for yy,value in zip(y,v):
        b.text(value+.014,yy,f'{value:.2f}',ha='left',va='center',fontsize=6.0,
               color='white' if value<0 else '#222222')
    outputs=save(fig,'q2_critical_head_sensitivity','Q2 临界水头与联合敏感性')
    # NaN encodes no root in the source; serialize as null, never as zero.
    plotted=json.loads(crit.to_json(orient='records'))
    return dict(figure_id='q2-critical-head-sensitivity',outputs=outputs,size_cm=[17,5.4],
        input_keys=['critical_head','joint_sensitivity'],scientific_layer='conditional_scenario',
        selection='Predeclared8 representative parameter indices;4 registered temperature slices within published thermal range; STH linear-policy8largest absolute existing Spearman correlations',
        representative_indices=REPS,critical_records=plotted,sensitivity_records=sens.drop(columns='abs_rho').to_dict('records'),
        root_handling='Negative algebraic roots shown as dry_already_critical, source null roots as no_pressure_only_root, unreachable positive roots retain capacity marker; no root converted to zero',
        caption_note='左图为8个预定代表、给定几何和初始损伤下的条件静力临界水头；＊表示正根超过给定水头容量，灰底为干态已越阈，斜线为无水压单独根。温度范围筛选不代表有效应力、材料和速率均在实验域内。右图为S+T+H线性分支按绝对Spearman相关排序的前8项设计关联，非因果贡献。')


def lab_cv_figure(table):
    order=['mc_linear','mc_temperature_quadratic','mc_stress_quadratic','mc_stress_hinge_400']
    names=['线性温度 MC','温度二次','应力二次','400 kPa 铰链']
    q=table[(table.domain=='warm_all')&(table.weight=='row_ols')&
            table.holdout_scheme.isin(['temperature','normal_stress'])].copy()
    assert len(q)==8 and (q.n==83).all() and (q.missing_prediction_count==0).all()
    fig=plt.figure(figsize=(17/2.54,4.2/2.54));a=fig.add_axes([.18,.27,.77,.55])
    y=np.arange(4);values={}
    for k,scheme in enumerate(['temperature','normal_stress']):
        d=q[q.holdout_scheme==scheme].set_index('model').loc[order]
        vals=d.group_macro_rmse_kpa.to_numpy();values[scheme]=vals
        a.scatter(vals,y+(k-.5)*.23,color=COLORS[scheme],marker='o' if k==0 else 's',s=17,zorder=3,
            label='整温层留出（5组）' if k==0 else '整应力类留出（4组）')
        for yy,val in zip(y+(k-.5)*.23,vals):
            a.text(val+12,yy+(-.15 if k==0 else .15),f'{val:.1f}',va='center',ha='left',fontsize=6.5,color=COLORS[scheme])
    for i in range(4):a.plot([values['temperature'][i],values['normal_stress'][i]],[i-.115,i+.115],color='#BBBBBB',lw=.6,zorder=1)
    a.set(yticks=y,yticklabels=names,ylim=(3.55,-.65),xlim=(0,1170),xticks=[0,200,400,600,800,1000],
          xlabel='留出组等权宏平均 RMSE / kPa')
    a.tick_params(axis='y',length=0,pad=5);a.grid(axis='x',alpha=.6);a.set_axisbelow(True)
    a.spines['left'].set_visible(False)
    fig.legend(*a.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.58,1.0),ncol=2,frameon=False,
        handlelength=1.,columnspacing=2.,fontsize=7.2)
    outputs=save(fig,'q2_lab_grouped_validation','Q2 外部暖温层试验的分组留出比较')
    return dict(figure_id='q2-lab-grouped-validation',outputs=outputs,size_cm=[17,4.2],
        input_keys=['laboratory_cv'],scientific_layer='external_transfer',
        selection='Fixed warm_all domain83tests, row_ols weight, all4candidate model IDs and temperature/normal-stress holdout schemes; group_macro_rmse_kpa, not pooled row RMSE',
        model_order=order,plotted_records=q.to_dict('records'),
        caption_note='外部暖温层的83次试验，名义温度-4至-0.5°C、应力100–800kPa；各模型均为行等权拟合。显示按留出组等权的宏平均RMSE，名义类用于分组、连续实测值用于拟合。外部实验评价不并入本地区独立事件分母。')


def main():
    assert Path.cwd().resolve()==ROOT
    family=configure()
    before={key:digest(path,key) for key,path in INPUTS.items()}
    frames={key:pd.read_csv(path) for key,path in INPUTS.items()}
    figures=[mechanism_figure(frames['mechanism_comparison']),
             critical_sensitivity_figure(frames['critical_head'],frames['joint_sensitivity']),
             lab_cv_figure(frames['laboratory_cv'])]
    for key,path in INPUTS.items():assert digest(path,key)==before[key]
    from pypdf import PdfReader
    pdf_checks=[]
    for fig in figures:
        p=ROOT/fig['outputs'][0]['path'];reader=PdfReader(p)
        assert len(reader.pages)==1
        page=reader.pages[0]
        width,height=float(page.mediabox.width)*2.54/72,float(page.mediabox.height)*2.54/72
        np.testing.assert_allclose([width,height],fig['size_cm'],atol=1e-6)
        fonts=[]
        for ref in page['/Resources']['/Font'].get_object().values():
            font=ref.get_object();embedded=False
            descendants=font.get('/DescendantFonts',[])
            for descendant in descendants:
                descriptor=descendant.get_object().get('/FontDescriptor')
                if descriptor:
                    d=descriptor.get_object();embedded=any(k in d for k in ['/FontFile','/FontFile2','/FontFile3'])
            fonts.append(dict(base_font=str(font.get('/BaseFont')),subtype=str(font.get('/Subtype')),embedded=embedded))
        images=[]
        for name,ref in page['/Resources'].get('/XObject',{}).get_object().items() if '/XObject' in page['/Resources'] else []:
            if ref.get_object().get('/Subtype')=='/Image':images.append(str(name))
        assert not images,'publication plot unexpectedly rasterized'
        assert all(f['embedded'] for f in fonts)
        pdf_checks.append(dict(figure_id=fig['figure_id'],one_page=True,size_cm=[width,height],embedded_fonts=fonts,raster_image_objects=images))
    resolved_font=Path(font_manager.findfont(font_manager.FontProperties(family=family,style='normal',weight='normal')))
    source=dict(schema_version='q2-paper-figures-v1',base_head='eecf07db7873b3c2c63275fa0b419867d8bdd3b2',
        script=digest(Path(__file__),'reproducible_publication_plotting_code'),inputs=list(before.values()),
        figures=figures,font=dict(requested_path=str(FONT),requested_sha256=hashlib.sha256(FONT.read_bytes()).hexdigest(),family=family,
            resolved_path=str(resolved_font),resolved_sha256=hashlib.sha256(resolved_font.read_bytes()).hexdigest()),
        software=dict(python=sys.version,matplotlib=matplotlib.__version__,numpy=np.__version__,pandas=pd.__version__),
        reproduction_command='track_b/.venv/bin/python track_b/paper/scripts/q2_make_figures.py',
        models_reexecuted=0,new_scenarios=0,source_inputs_unchanged=True,pdf_checks=pdf_checks,
        visual_review_status='pending_actual_open; see q2_visual_review.json once reviewed')
    (OUT/'q2_figure_sources.json').write_text(json.dumps(source,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(figures=len(figures),pdf_pages_checked=len(pdf_checks),all_sources_unchanged=True,
        files=[item['path'] for fig in figures for item in fig['outputs']]),ensure_ascii=False))
    _cache.cleanup()


if __name__=='__main__':main()
