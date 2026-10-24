#!/usr/bin/env python3
from pathlib import Path
import os
os.environ.setdefault('MPL_IGNORE_SYSTEM_FONTS','1')
os.environ.setdefault('MPLCONFIGDIR','/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/plot_runtime')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
R=Path(__file__).resolve().parents[1];O=R/'results/applicability_sensitivity'
def main():
    f=pd.read_csv(O/'predictions.csv.gz');p=pd.read_csv(O/'p0149_parameter_audit.csv');stress=p.normal_stress_kpa_independent.iloc[0]
    subset=f[(f.model_id=='mechanism_policy_mixture')&(f.horizon_hours==72)&(f.probability_prior=='uniform_design_assumption')&
      (f.forecast_input_mode=='assumed_latency')&(f.space_object=='aoi_unweighted_mean')&(f.assumed_latency_hours==0)].copy()
    fig,ax=plt.subplots(1,3,figsize=(13,4.3),layout='constrained',gridspec_kw={'width_ratios':[1,1.4,1.4]})
    ax[0].axvspan(100,800,color='.88',label='Full tests: 100–800 kPa')
    ax[0].axvspan(100,400,color='#398495',alpha=.5,label='Fitted criterion: 100–400 kPa')
    ax[0].axvline(stress,c='#ac5b32',lw=2,label=f'p0149-S: {stress:.3f} kPa')
    ax[0].set_xlim(0,900);ax[0].set_ylim(0,1);ax[0].set_yticks([]);ax[0].set_xlabel('Effective normal stress (kPa)')
    ax[0].set_title('Unique future-crossing support\nextrapolates the fitted criterion',loc='left',fontsize=11,fontweight='bold')
    ax[0].legend(fontsize=7,loc='lower left')
    styles=[('original_design','Original discrete design','#ac5b32','-'),('all_observed_states_in_experiment_domain','Strict observed-domain subset','#17677c','--'),('observed_domain_fraction_weight','Domain-fraction weights','#6f8262',':')]
    for policy,label,color,style in styles:
        g=subset[subset.applicability_policy==policy].sort_values('issue_time');t=pd.to_datetime(g.issue_time,utc=True)
        ax[1].plot(t,100*g.probability_start_within_horizon,label=label,c=color,ls=style,lw=1.7)
    ax[1].set_title('72 h mixture; only identified rows\nAOI / zero assumed latency / uniform',loc='left',fontsize=11,fontweight='bold')
    ax[1].set_ylabel('Start mass under assumed design (%)');ax[1].legend(fontsize=7,loc='upper right')
    c=subset[subset.applicability_policy=='out_of_domain_mass_to_unknown'].sort_values('issue_time');t=pd.to_datetime(c.issue_time,utc=True)
    ax[2].fill_between(t,100*c.probability_start_lower,100*c.probability_start_upper,color='#8eafb8',alpha=.65,label='Out-of-domain state/outcome unknown')
    ax[2].plot(t,100*c.probability_start_upper,c='#17677c',lw=1);ax[2].set_ylim(0,102)
    ax[2].set_title('Retain original mass; mark unknown\nBroad bounds persist instead of safety',loc='left',fontsize=11,fontweight='bold')
    ax[2].set_ylabel('Possible start-mass bounds (%)');ax[2].legend(fontsize=7,loc='upper right')
    for a in ax[1:]:
        a.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=4))
        a.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M',tz='UTC'))
        a.set_xlabel('Issue time (UTC)');a.grid(alpha=.2)
    for a in ax:a.spines[['top','right']].set_visible(False)
    fig.suptitle('Retrospective numerical applicability sensitivity — no local material or forecast certification',fontsize=12,fontweight='bold')
    fig.savefig(O/'applicability_comparison.png',dpi=160);plt.close(fig);print('Figure generated; actual visual review required')
if __name__=='__main__':main()
