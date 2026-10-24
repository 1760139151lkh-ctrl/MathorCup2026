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
R=Path(__file__).resolve().parents[1];O=R/'results/applicability_sensitivity/risk_set_revision'
def main():
    f=pd.read_csv(O/'five_policy_predictions.csv.gz',low_memory=False)
    use=f[(f.model_id=='mechanism_policy_mixture')&(f.horizon_hours==72)&(f.probability_prior=='uniform_design_assumption')&
       (f.forecast_input_mode=='assumed_latency')&(f.space_object=='aoi_unweighted_mean')&(f.assumed_latency_hours==0)]
    groups={k:g.sort_values('issue_time') for k,g in use.groupby('applicability_policy')}
    original=groups['original_design'];fixed=groups['fixed_history_risk_out_of_domain_to_unknown'];diag=groups['revoke_out_of_domain_history_classification_diagnostic']
    fig,ax=plt.subplots(1,3,figsize=(13,4.3),layout='constrained')
    clock=pd.to_datetime(original.issue_time,utc=True)
    ax[0].plot(clock,100*original.probability_start_within_horizon,c='#a55e36',label='Original discrete design')
    strict=groups['all_observed_states_in_experiment_domain'];ax[0].plot(pd.to_datetime(strict.issue_time,utc=True),100*strict.probability_start_within_horizon,c='#17677c',ls='--',label='Strict-subset renormalization')
    ax[0].set_title('Identified design mass only\nSubset zero does not mean safety',loc='left',fontsize=11,fontweight='bold');ax[0].set_ylabel('Start mass (%)');ax[0].legend(fontsize=8)
    t=pd.to_datetime(fixed.issue_time,utc=True)
    ax[1].fill_between(t,100*fixed.probability_start_lower,100*fixed.probability_start_upper,color='#8fb8c1',alpha=.7,label='Primary: original risk fixed')
    ax[1].plot(t,100*fixed.probability_start_upper,c='#17677c',lw=1.6)
    ax[1].plot(pd.to_datetime(diag.issue_time,utc=True),100*diag.probability_start_upper,c='#a55e36',ls='--',label='Extra: revoke outside-domain history')
    ax[1].set_ylim(0,102);ax[1].set_ylabel('Possible start-mass bounds (%)');ax[1].set_title('Same-risk primary comparison\nSeparate history-revocation diagnostic',loc='left',fontsize=11,fontweight='bold');ax[1].legend(fontsize=7,loc='upper right')
    ax[2].plot(t,fixed.at_risk_prior_mass,c='#17677c',label='Original = fixed-risk primary')
    ax[2].plot(pd.to_datetime(diag.issue_time,utc=True),diag.at_risk_prior_mass,c='#a55e36',ls='--',label='Possible risk if history revoked')
    ax[2].set_title('Risk-set denominator is explicit\nPrimary retains original past mass',loc='left',fontsize=11,fontweight='bold');ax[2].set_ylabel('Original-prior risk mass');ax[2].set_ylim(0,1.03);ax[2].legend(fontsize=7,loc='lower left')
    for a in ax:
        a.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=4));a.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M',tz='UTC'))
        a.set_xlabel('Issue time (UTC)');a.grid(alpha=.2);a.spines[['top','right']].set_visible(False)
    fig.suptitle('72 h mixture / uniform assumed prior / AOI / zero assumed latency\nRetrospective fitted-strength-domain diagnosis; no local risk calibration or safety claim',fontsize=12,fontweight='bold')
    fig.savefig(O/'fixed_risk_comparison.png',dpi=160);plt.close(fig);print('Generated fixed-risk figure; actual review required')
if __name__=='__main__':main()
