#!/usr/bin/env python3
"""Matched-opportunity external comparisons, with interval-label ambiguity."""
import os
from pathlib import Path
os.environ.setdefault('MPL_IGNORE_SYSTEM_FONTS','1')
os.environ.setdefault('MPLCONFIGDIR','/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/plot_runtime')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
R=Path(__file__).resolve().parents[1]
LABEL={'B_IV':'Inverse velocity','B_SS':'State space',
 'linear_dynamic_hazard_no_record_age_raw':'Linear hazard, raw',
 'linear_dynamic_hazard_no_record_age_crossfit_calibrated':'Linear hazard, calibrated',
 'nonlinear_rbf_hazard_no_record_age_raw':'RBF hazard, raw',
 'nonlinear_rbf_hazard_no_record_age_crossfit_calibrated':'RBF hazard, calibrated'}

def main():
    out=R/'figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':160})
    pair=pd.read_csv(R/'results/common_anchors_no_age/paired_valid_scores.csv')
    reference='nonlinear_rbf_hazard_no_record_age_raw'
    selected=pair[(pair.model_two==reference)&pair.model_one.isin(['B_IV','B_SS','linear_dynamic_hazard_no_record_age_raw'])]
    fig,axs=plt.subplots(1,2,figsize=(11,4.4),layout='constrained',sharex=True)
    for ax,H in zip(axs,[48,72]):
        f=selected[selected.horizon_hours==H].reset_index(drop=True)
        for i,r in f.iterrows():
            ax.plot([r.brier_one,r.brier_two],[i,i],c='.65',lw=2)
            ax.scatter(r.brier_one,i,c='#b86936',s=48,label='Named comparator' if i==0 else None,zorder=3)
            ax.scatter(r.brier_two,i,c='#17677c',s=48,label='RBF hazard, raw' if i==0 else None,zorder=3)
            ax.text(.62,i,f'n={int(r.same_known_probability_groups)}\n+{int(r.positive_groups)} / −{int(r.negative_groups)}',va='center',fontsize=8)
        ax.set_yticks(range(len(f)),[LABEL[m] for m in f.model_one]);ax.invert_yaxis();ax.set_xlim(-.015,.73)
        ax.set_title(f'{H} h: same valid cases within each pair',loc='left',fontweight='bold');ax.set_xlabel('Brier score; lower is better');ax.grid(axis='x',alpha=.2)
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=2,fontsize=9)
    fig.suptitle('External terminal-collapse benchmark: different pairs can have different subsets\n14 physical cases retained overall; no local first-motion validation',fontsize=12,fontweight='bold')
    fig.savefig(out/'paired_external_scores.png');plt.close(fig)
    ev=pd.read_csv(R/'results/common_anchors_no_age/evaluation.csv');ev=ev[ev.horizon_hours==72].copy()
    order=['B_IV','B_SS',*sorted(x for x in LABEL if x.startswith('linear')),reference,'nonlinear_rbf_hazard_no_record_age_crossfit_calibrated']
    ev=ev.set_index('model_id').loc[order].reset_index()
    fig,ax=plt.subplots(figsize=(10,4.6),layout='constrained')
    for i,r in ev.iterrows():
        ax.plot([r.coverage_full_including_no_interval,r.coverage_intersects_including_no_interval],[i,i],lw=5,c='#8eb5ba',solid_capstyle='round')
        ax.scatter([r.coverage_full_including_no_interval,r.coverage_intersects_including_no_interval],[i,i],s=30,c='#17677c',zorder=3)
        ax.text(1.025,i,f'{int(r.issued_interval_event_groups)}/{int(r.known_event_groups)} intervals\n{int(r.abstain_groups)}/14 abstain',va='center',fontsize=8)
    ax.set_yticks(range(len(ev)),[LABEL[m] for m in ev.model_id]);ax.invert_yaxis();ax.set_xlim(-.03,1.32)
    ax.set_xticks([0,.25,.5,.75,1]);ax.set_xlabel('Full containment ≤ actual coverage ≤ label intersection')
    ax.set_title('72 h interval-label coverage bounds: 7 known positive cases\nNo issued interval counts as uncovered; this does not establish 95% coverage',loc='left',fontweight='bold')
    ax.grid(axis='x',alpha=.2);fig.savefig(out/'interval_coverage_bounds.png');plt.close(fig)
    print('Two matched-comparison figures written; actual visual inspection required')

if __name__=='__main__':main()
