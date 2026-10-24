"""Static scientific figures from actual saved R3 numerical results."""
import json,math,argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mechanism_engine import G,resistance
from run_experiments import BASE,CONFIG,parameter_design,take

MODELS=['S','S_T','S_H','S_T_H'];COLORS=['#45657b','#cf8052','#4d978f','#9467a1']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':110,'savefig.dpi':160})


def save(fig,name):
    fig.savefig(BASE/'figures'/name,bbox_inches='tight');plt.close(fig)


def run(refined=False,analytic=False):
    data_dir=BASE/'results/analytic_thermal' if analytic else (BASE/'results/refined_v2' if refined else BASE/'results')
    suffix='_analytic' if analytic else ('_v2' if refined else '')
    version='analytic erfc thermal' if analytic else ('v2, 0.125 m thermal grid' if refined else 'v1, 0.5 m thermal grid')
    outcomes=pd.read_csv(data_dir/'scenario_outcomes.csv');linear=outcomes[outcomes.law_policy=='linear_extension']
    fig,axs=plt.subplots(1,2,figsize=(11,4.1),layout='constrained')
    data=[linear.loc[linear.mechanism_id==m,'min_margin_evaluation'] for m in MODELS]
    b=axs[0].boxplot(data,tick_labels=['S','S+T','S+H','S+T+H'],showfliers=False,patch_artist=True)
    for box,c in zip(b['boxes'],COLORS):box.set_facecolor(c);box.set_alpha(.65)
    axs[0].axhline(0,color='#444444',ls='--',lw=1);axs[0].set_ylabel('Minimum normalized margin, Aug 19–27');axs[0].set_title('Same 256 parameter design points')
    counts=np.array([[int(((linear.mechanism_id==m)&(linear.onset_status==s)).sum()) for m in MODELS] for s in ['never_crossed','interval_crossing','left_censored_already_unstable']])
    bottom=np.zeros(4)
    for vals,label,color in zip(counts,['Never crossed','Crossed after initial state','Initially unstable / left censored'],['#91b7ad','#dba06e','#777b83']):
        axs[1].bar(np.arange(4),vals,bottom=bottom,color=color,label=label)
        for j,v in enumerate(vals):
            if v:axs[1].text(j,bottom[j]+v/2,str(v),ha='center',va='center',fontsize=9)
        bottom+=vals
    axs[1].set_xticks(np.arange(4),['S','S+T','S+H','S+T+H']);axs[1].set_ylabel('Design points (not probability / events)');axs[1].legend(fontsize=8,loc='upper left',bbox_to_anchor=(0,1.18))
    fig.suptitle(f'Conditional mechanism competition — {version}',fontsize=13)
    save(fig,'mechanism_competition'+suffix+'.png')
    tracks=pd.read_parquet(data_dir/'state_trajectories.parquet');rep=109
    a=tracks[(tracks.law_policy=='linear_extension')&tracks.scenario_id.str.startswith(f'q2r3-p{rep:04d}-')].copy()
    a=a[a.time_utc>=pd.Timestamp('2026-08-01',tz='UTC')]
    fig,axs=plt.subplots(4,1,figsize=(10,8),sharex=True,layout='constrained')
    for m,c in zip(MODELS,COLORS):
      q=a[a.mechanism_id==m];t=q.time_utc
      for ax,col in zip(axs,['failure_margin','interface_temp_c','pressure_kpa','damage']):ax.plot(t,q[col],color=c,label=m.replace('_','+'),lw=1.5)
    axs[0].axhline(0,color='black',ls='--',lw=.8);axs[0].legend(ncol=4,fontsize=9)
    for ax,label in zip(axs,['Normalized margin','Joint temperature (°C)','Pressure (kPa)','Cohesion loss D']):ax.set_ylabel(label);ax.grid(alpha=.15)
    axs[-1].set_xlabel('UTC; continuation after criterion crossing is diagnostic only')
    fig.suptitle('Pre-selected p0109 (conditional); '+version,fontsize=12)
    save(fig,'state_evolution'+suffix+'.png')
    response=pd.read_csv(BASE/'results/thermal_response_times.csv')
    fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    t=np.linspace(.1,168,500)
    for depth in [.5,2,5,10]:
      frac=[math.erfc(depth/(2*math.sqrt(1.5e-6*h*3600))) for h in t]
      axs[0].plot(t,frac,label=f'{depth:g} m')
    axs[0].set(xlabel='Hours after surface temperature step',ylabel='Fraction of surface step at depth',ylim=(-.02,1.02),title='Conduction, α=1.5×10⁻⁶ m²/s');axs[0].legend(title='Path depth');axs[0].grid(alpha=.15)
    for tau in [3,24,240]:axs[1].plot(t,1-np.exp(-t/tau),label=f'τ={tau} h')
    axs[1].set(xlabel='Hours after constant water input starts',ylabel='Fraction of unconstrained equilibrium storage',title='Storage / drainage response before capacity');axs[1].legend();axs[1].grid(alpha=.15)
    fig.suptitle('Numerical / analytic response scales, not measured local response',fontsize=12)
    save(fig,'response_timescales.png')
    sens=pd.read_csv(data_dir/('joint_sensitivity.csv' if (refined or analytic) else 'sensitivity.csv'));sens=sens[sens.law_policy=='linear_extension']
    table=sens.pivot(index='parameter',columns='mechanism_id',values='spearman_rho')[MODELS]
    thermal_only={'diffusivity_m2_s','interface_depth_m'}
    hydraulic={'storativity','drainage_hours','connected_depth_m','rain_multiplier','melt_mm_deg_day','drainage_damage_coupling'}
    for m in MODELS:
      inactive=(thermal_only if m in ['S','S_H'] else set()) | (hydraulic if m in ['S','S_T'] else set())
      if m=='S':inactive=inactive|{'station_source_offset_c'}
      for k in inactive:table.loc[k,m]=np.nan
    fig,ax=plt.subplots(figsize=(9,8),layout='constrained');im=ax.imshow(table.to_numpy(),cmap='RdBu_r',vmin=-1,vmax=1,aspect='auto')
    ax.set_yticks(range(len(table)),table.index);ax.set_xticks(range(4),['S','S+T','S+H','S+T+H']);fig.colorbar(im,ax=ax,label='Joint-design Spearman correlation with minimum margin')
    for i in range(len(table)):
      for j in range(4):ax.text(j,i,f'{table.iloc[i,j]:.2f}' if np.isfinite(table.iloc[i,j]) else 'off',ha='center',va='center',color='white' if abs(table.iloc[i,j])>.6 else '#222222',fontsize=8)
    ax.set_title('Design associations; inactive inputs suppressed; '+version)
    save(fig,'joint_sensitivity'+suffix+'.png')
    cfg=json.loads(CONFIG.read_text());p=parameter_design(cfg);pi=take(p,[109]);temps=np.linspace(-6,0,121);heads=np.linspace(0,35,141)
    tt,hh=np.meshgrid(temps,heads);state=resistance(pi,pi['initial_damage'],tt,G*hh)
    fig,ax=plt.subplots(figsize=(8.5,4.8),layout='constrained');im=ax.pcolormesh(temps,heads,state['failure_margin'],cmap='RdBu',vmin=-1,vmax=1.5,shading='auto')
    ax.contour(temps,heads,state['failure_margin'],levels=[0],colors=['black'],linewidths=1.4)
    ax.axvspan(-.5,0,color='#c99d63',alpha=.28,label='Warm extrapolation domain')
    domain_low=max(0,float((state['normal_kpa'][0]-400)/G))
    if domain_low>0:ax.axhspan(0,min(domain_low,35),facecolor='none',edgecolor='#777777',hatch='///',linewidth=0,label='Effective stress > 400 kPa')
    ax.set_ylim(0,35)
    ax.set(xlabel='Joint temperature (°C)',ylabel='Connected pressure head (m)',title='Conditional critical surface at fixed initial damage (p0109)')
    ax.legend(fontsize=8,loc='upper left');fig.colorbar(im,ax=ax,label='Normalized failure margin')
    save(fig,'critical_surface.png')
    if analytic:
      pairs=pd.read_csv(data_dir/'paired_v2_fd0625.csv')
      finite=pairs[pairs.analytic_onset_elapsed_hours.notna()&pairs.fd0625_onset_elapsed_hours.notna()].copy()
      fig,axs=plt.subplots(1,2,figsize=(11,4.4),sharex=True,layout='constrained')
      for mech,c in zip(MODELS,COLORS):
        q=finite[finite.mechanism_id==mech]
        axs[0].scatter(q.analytic_onset_elapsed_hours/24,q.fd0625_onset_elapsed_hours-q.analytic_onset_elapsed_hours,s=15,color=c,alpha=.6,label=mech.replace('_','+'))
        axs[1].scatter(q.analytic_onset_elapsed_hours/24,q.v2_onset_elapsed_hours-q.analytic_onset_elapsed_hours,s=15,color=c,alpha=.6)
      for ax,title in zip(axs,['FD 0.0625 m minus analytic','FD 0.125 m minus analytic']):
        ax.set_title(title);ax.axhline(0,color='black',lw=.7);ax.set_yscale('symlog',linthresh=.01);ax.set_xlabel('Analytic onset: days after Jun 1 UTC');ax.grid(alpha=.15)
      axs[0].set_ylabel('Onset time difference (h); symlog near zero');axs[0].legend(fontsize=8)
      fig.suptitle(f'Thermal numerical comparison: {len(finite)} finite scenario pairs / 2048; no independent events',fontsize=11)
      save(fig,'analytic_thermal_onset_comparison.png')
    print('Created 5 model figures')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refined',action='store_true');parser.add_argument('--analytic',action='store_true');args=parser.parse_args();run(args.refined,args.analytic)
