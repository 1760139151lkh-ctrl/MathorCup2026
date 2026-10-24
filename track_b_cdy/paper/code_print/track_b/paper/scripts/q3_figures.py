#!/usr/bin/env python3
"""Paper-only redraw from frozen Q3 results; no model fitting or simulation."""
import os
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'track_b/paper'
R = ROOT / 'track_b/research/q3/round3'
OUT = PAPER / 'figures/q3'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(OUT / '.mpl-cache'))
os.environ.setdefault('MPL_IGNORE_SYSTEM_FONTS', '1')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.text import Text
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

font_file=Path(subprocess.check_output(['fc-match','-f','%{file}','SimSun'],text=True).strip())
font_manager.fontManager.addfont(str(font_file))
font_name=font_manager.FontProperties(fname=str(font_file)).get_name()
from matplotlib.ft2font import FT2Font
assert FT2Font(str(font_file)).get_char_index(ord('预'))>0,'Install a Chinese font before rendering'
plt.rcParams.update({'font.family':['DejaVu Sans'],'font.size':9.5,
                     'axes.unicode_minus':False,'pdf.fonttype':42,'ps.fonttype':42,
                     'axes.spines.top':False,'axes.spines.right':False,
                     'axes.labelsize':10,'legend.fontsize':8.5,'xtick.labelsize':9,'ytick.labelsize':9})
BLUE, ORANGE, GRAY = '#286988', '#BD6C42', '#6B747B'
inputs = []


def record(p):
    return {'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}


def load(relative):
    p = R / relative
    if p not in inputs:
        inputs.append(p)
    return pd.read_csv(p)


def save(fig, name):
    for artist in fig.findobj(match=Text):
        artist.set_fontproperties(font_manager.FontProperties(fname=str(font_file),size=artist.get_fontsize()))
    fig.savefig(OUT/name, bbox_inches='tight', pad_inches=.045)
    plt.close(fig)


def main():
    (PAPER/'evidence').mkdir(parents=True,exist_ok=True)
    fixed = load('results/applicability_sensitivity/risk_set_revision/fixed_history_risk_predictions.csv.gz')
    selected = fixed[(fixed.model_id=='mechanism_policy_mixture') &
                     (fixed.probability_prior=='uniform_design_assumption') &
                     (fixed.forecast_input_mode=='assumed_latency') &
                     (fixed.space_object=='aoi_unweighted_mean') &
                     (fixed.assumed_latency_hours==0) & (fixed.horizon_hours==72)].sort_values('issue_time')
    assert len(selected)==75 and selected.probability_start_within_horizon.isna().all()
    assert selected.probability_start_lower.eq(0).all()
    pairs = load('results/common_anchors_no_age/paired_valid_scores.csv')
    model_c = 'nonlinear_rbf_hazard_no_record_age_raw'
    paired = pairs[(pairs.model_one=='B_SS') & (pairs.model_two==model_c)].sort_values('horizon_hours')
    assert list(paired.horizon_hours)==[24,48,72]
    assert list(paired.same_known_probability_groups)==[5,8,8]
    fig, ax = plt.subplots(1,2,figsize=(6.65,2.25),gridspec_kw={'width_ratios':[1.1,1]})
    fig.subplots_adjust(wspace=.38)
    t = pd.to_datetime(selected.issue_time)
    lo,hi = selected.probability_start_lower.to_numpy()*100,selected.probability_start_upper.to_numpy()*100
    ax[0].fill_between(t,lo,hi,color=BLUE,alpha=.23,label='启动质量信息界')
    ax[0].plot(t,hi,color=BLUE,lw=1.5)
    ax[0].plot(t,lo,color=BLUE,lw=.8)
    ax[0].set_ylim(-1,104)
    ax[0].set_ylabel('条件启动概率界 / %')
    ax[0].set_xlabel('发布时刻（UTC）')
    ax[0].xaxis.set_major_locator(mdates.DayLocator())
    ax[0].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax[0].set_title('(a) 72 h：固定历史风险集',fontsize=10,pad=7)
    ax[0].legend(loc='upper right',frameon=False)
    x = np.arange(3);width=.31
    ax[1].bar(x-width/2,paired.brier_one,width,color=BLUE,label='状态空间 SS')
    ax[1].bar(x+width/2,paired.brier_two,width,color=ORANGE,label='无年龄 RBF')
    ax[1].set_xticks(x,['24 h\n(n=5)','48 h\n(n=8)','72 h\n(n=8)'])
    ax[1].set_ylabel('同机会 Brier 分数')
    ax[1].set_xlabel('预测时域')
    ax[1].set_ylim(0,.425)
    ax[1].legend(loc='upper left',frameon=False)
    ax[1].set_title('(b) 外部病例分组配对',fontsize=10,pad=7)
    for a in ax:
        a.grid(axis='y',color='#D9DEE2',alpha=.65,lw=.5);a.set_axisbelow(True)
    save(fig,'q3_information_scores.pdf')

    joined = load('results/final_propagation_v4/conditional_arrivals_49.csv')
    footprint = pd.concat([load('results/arrival/propagation_v2/depth_footprint_diagnostics.csv'),
                           load('results/arrival/propagation_v3/depth_footprint_diagnostics.csv'),
                           load('results/arrival/compact_delta_v1/depth_footprint_diagnostics.csv')],ignore_index=True)
    f = footprint[(footprint.scope=='saved_outputs_through_requested_horizon') & (footprint.threshold_depth_m==.1)]
    junction = joined[joined.target_id=='paper_junction'].copy()
    assert len(junction)==len(f)==7
    ids = ['q2map60_q2r3_p0000_S_linear__sf0','q2full_q2r3_p0000_S_linear__geomv2_60m__sf0',
           'q2map60_q2r3_p0036_S_T_linear__sf0','q2full_q2r3_p0036_S_T_linear__geomv2_120m__sf0',
           'q2full_q2r3_p0036_S_T_linear__geomv2_60m__sf0','q2map60_q2r3_p0072_S_H_linear__sf0',
           'q2map60_q2r3_p0255_S_T_H_linear__sf0']
    junction = junction.set_index('run_id').loc[ids].reset_index()
    f = f.set_index('run_id').loc[ids].reset_index()
    names = ['S 紧凑 60 m','S 全源面 60 m','ST 紧凑 60 m','ST 全源面 120 m',
             'ST 全源面 60 m','SH 紧凑 60 m','STH 紧凑 60 m']
    compact = [not rid.startswith('q2full_') for rid in ids]
    fig,ax = plt.subplots(1,2,figsize=(6.65,2.5),gridspec_kw={'width_ratios':[1.34,1]})
    fig.subplots_adjust(wspace=.45)
    for j,row in enumerate(junction.itertuples()):
        color=ORANGE if compact[j] else BLUE
        lower=row.diagnostic_bulk_release_arrival_lower_seconds
        upper=row.diagnostic_bulk_release_arrival_upper_seconds
        if np.isfinite(lower) and np.isfinite(upper):
            middle=(lower+upper)/2
            ax[0].errorbar(middle,j,xerr=[[middle-lower],[upper-middle]],fmt='o',ms=4.3,
                           color=color,mfc='white' if row.if_released_propagation else color,capsize=3,lw=1.2)
        else:
            ax[0].text(1060,j,'保存帧未命中',va='center',fontsize=8.5,color=GRAY)
    ax[0].set_yticks(range(7),names)
    ax[0].invert_yaxis();ax[0].set_ylim(6.6,-.6)
    ax[0].set_xlim(0,1810);ax[0].set_xticks([0,600,1200,1800])
    ax[0].set_xlabel('距给定整体释放的时延 / s')
    ax[0].set_title('(a) 汇流点保存帧首达括号',fontsize=10,pad=8)
    ax[0].grid(axis='x',color='#D9DEE2',lw=.5)
    offsets=[(5,6),(-40,0),(-12,9),(-34,7),(-40,-3),(-32,10),(8,-13)]
    short=['S','S','ST','ST120','ST60','SH','STH']
    for j,row in enumerate(f.itertuples()):
        color=ORANGE if compact[j] else BLUE
        dx=row.maximum_affected_cell_centre_distance_from_release_support_m/1000
        area=row.affected_plan_area_m2/1e6
        ax[1].scatter(dx,area,s=30,color=color,marker='o' if compact[j] else 's',zorder=3)
        ax[1].annotate(short[j],(dx,area),xytext=offsets[j],textcoords='offset points',fontsize=8.5,color=color)
    ax[1].set_xlabel('距释放栅格支撑的最远距离 / km')
    ax[1].set_ylabel('阈值足迹面积 / km$^2$')
    ax[1].set_xlim(4.8,12.3);ax[1].set_ylim(0,26)
    ax[1].set_title('(b) h≥0.1 m，保存帧≤1800 s',fontsize=10,pad=8)
    ax[1].legend(handles=[Line2D([0],[0],marker='o',color=ORANGE,lw=0,label='紧凑源'),
                          Line2D([0],[0],marker='s',color=BLUE,lw=0,label='全源面')],loc='upper left',frameon=False)
    ax[1].grid(color='#D9DEE2',lw=.5);ax[1].set_axisbelow(True)
    save(fig,'q3_release_response.pdf')
    data={'description':'All numeric plot inputs are projected from frozen research outputs; no fitting or dynamics rerun.',
          'source_files':[record(p) for p in inputs],
          'information_bound_selection':{'model_id':'mechanism_policy_mixture','probability_prior':'uniform_design_assumption',
              'forecast_input_mode':'assumed_latency','space_object':'aoi_unweighted_mean','assumed_latency_hours':0,'horizon_hours':72},
          'information_bounds':selected[['issue_time','probability_start_lower','probability_start_upper','at_risk_prior_mass','unresolved_future_prior_mass']].to_dict('records'),
          'paired_scores':paired.to_dict('records'),
          'release_response':junction.where(pd.notna(junction),None).to_dict('records'),
          'footprints':f.to_dict('records'),'figures':[record(OUT/n) for n in ['q3_information_scores.pdf','q3_release_response.pdf']]}
    # pandas float columns retain NaN after where(None); JSON uses a standard null projection.
    data=json.loads(json.dumps(data,default=str).replace('NaN','null'))
    (PAPER/'evidence/q3_figure_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    main()
