#!/usr/bin/env python3
"""All matched-followup weather state contrasts; no event-probability claim."""
from pathlib import Path
import os
os.environ.setdefault('MPL_IGNORE_SYSTEM_FONTS','1')
os.environ.setdefault('MPLCONFIGDIR','/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/plot_runtime')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parents[1]
def main():
    f=pd.read_csv(R/'results/mechanistic_replay/analytic_erfc/equal_followup_weather_state_contrasts.csv')
    assert len(f)==96
    order=['S','S_T','S_H','S_T_H'];labels=['Structure','+ thermal','+ water','+ both']
    fields=[('maximum_interface_temperature_weather_vs_ideal_difference_c','Max |interface temperature difference| (°C)'),
            ('maximum_final_margin_weather_vs_ideal_difference','Max |stability margin difference|'),
            ('maximum_pressure_weather_vs_ideal_difference_kpa','Max |pressure difference| (kPa)')]
    fig,axs=plt.subplots(1,3,figsize=(11.5,4.1),layout='constrained')
    for ax,(field,label) in zip(axs,fields):
        for i,m in enumerate(order):
            vals=f.loc[f.mechanism_id.eq(m),field].to_numpy(float)
            ax.bar(i,float(np.median(vals)),color='#9bbfc5',width=.6,zorder=1)
            ax.scatter(np.full(len(vals),i)+np.linspace(-.16,.16,len(vals)),vals,c='#17677c',s=11,alpha=.6,zorder=2)
        ax.set_xticks(range(4),labels,rotation=20,ha='right');ax.set_ylabel(label);ax.grid(axis='y',alpha=.2)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Actual GFS replacement changes modeled states, even when crossing probabilities agree\n96 same-followup mechanism contrasts; dots = matched summaries, bars = medians; conditional scenarios',fontsize=11,fontweight='bold')
    fig.savefig(R/'figures/weather_state_contrasts.png',dpi=160);plt.close(fig)
    print('Weather state-contrast figure written; visual inspection required')
if __name__=='__main__':main()
