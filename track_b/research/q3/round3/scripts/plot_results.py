#!/usr/bin/env python3
"""Standalone scientific figures; source data and limitations remain explicit."""
from pathlib import Path
import os
R=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR','/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/plot_runtime')
os.environ.setdefault('MPL_IGNORE_SYSTEM_FONTS','1')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

def main():
    out=R/'figures';out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    f=pd.read_csv(R/'inputs/weather/gfs_hourly_summary.csv');f=f[f.space_object.eq('aoi_unweighted_mean')]
    f.valid_time=pd.to_datetime(f.valid_time,utc=True)
    fig,ax=plt.subplots(2,1,figsize=(10,6.4),sharex=True,layout='constrained')
    for ref,g in f.groupby('forecast_reference_time',sort=True):
        g=g.sort_values('valid_time');label=ref.replace('2026-','').replace('T',' ').replace(':00:00Z','Z')
        ax[0].plot(g.valid_time,g.temperature_2m_C,label=label,lw=1.7)
        ax[1].plot(g.valid_time,g.precipitation_cumulative_mm,lw=1.7)
    proxy=pd.Timestamp('2026-08-26T02:52:10Z')
    for a in ax:a.axvline(proxy,c='.35',ls='--',lw=1);a.grid(alpha=.2)
    ax[0].set_ylabel('2 m temperature (°C)');ax[1].set_ylabel('Cumulative precipitation\nfrom each initialization (mm)')
    ax[0].legend(title='Forecast initialization (UTC)',ncol=3,fontsize=8,loc='upper left')
    ax[0].set_title('Archived GFS: three actual hourly forecast trajectories\nAOI 85–86°E, 28–29°N; historical first availability unknown',loc='left',fontweight='bold')
    ax[1].xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M',tz='UTC'));ax[1].set_xlabel('Valid time (UTC); dashed line = catalogue proxy, not accepted mechanical onset')
    fig.savefig(out/'weather_forecast_trajectories.png');plt.close(fig)
    path=R/'results/engine_a/scenario_ranges.csv'
    if path.exists():
        f=pd.read_csv(path);f=f.sort_values(['mechanism_id','model_id'])
        fig,ax=plt.subplots(figsize=(9,max(3,len(f)*.5)),layout='constrained')
        y=np.arange(len(f));left=f.left_censored_count.to_numpy();cross=f.finite_crossing_count.to_numpy();never=f.never_cross_count.to_numpy();un=f.unresolved_count.to_numpy()
        acc=np.zeros(len(f))
        for vals,label,color in [(left,'Already unstable / left censored','#a4a9ad'),(cross,'Resolved crossing','#256f89'),(never,'No crossing during observed path','#5b9263'),(un,'Unresolved / gap','#dcaa57')]:
            ax.barh(y,vals,left=acc,label=label,color=color);acc+=vals
        ax.set_yticks(y,[f'{x.model_id} / {x.forecast_input_mode}' for x in f.itertuples()]);ax.set_xlabel('Scenario trajectories; no empirical event count')
        ax.set_title('Q2 supplied trajectories: first-passage status retained',loc='left',fontweight='bold')
        handles,labels=ax.get_legend_handles_labels();fig.legend(handles,labels,fontsize=8,loc='outside lower center',ncol=2)
        fig.savefig(out/'mechanism_first_passage_status.png');plt.close(fig)
    print('figures written; visual inspection required before final manifest')

if __name__=='__main__':main()
