#!/usr/bin/env python3
"""Explicit base-scenario pairing across three complete mechanism versions."""
from datetime import datetime,timezone
from pathlib import Path
import json,os
os.environ.setdefault('MPL_IGNORE_SYSTEM_FONTS','1')
os.environ.setdefault('MPLCONFIGDIR','/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/plot_runtime')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
R=Path(__file__).resolve().parents[1]

def main():
    paths={'FD_0.5m':R/'results/engine_a/first_passages.csv','FD_0.125m':R/'results/engine_a/v2/first_passages.csv',
           'analytic_erfc':R/'results/engine_a/analytic_erfc/first_passages.csv'}
    dfs={k:pd.read_csv(p) for k,p in paths.items()};rows=[];summaries=[]
    for v,f in dfs.items():assert len(f)==2048 and not f.base_scenario_id.duplicated().any(),v
    for one,two in [('FD_0.5m','FD_0.125m'),('FD_0.5m','analytic_erfc'),('FD_0.125m','analytic_erfc')]:
        pair=dfs[one].merge(dfs[two],on=['base_scenario_id','mechanism_id','law_policy'],suffixes=('_one','_two'),validate='one_to_one')
        assert len(pair)==2048
        t1=pd.to_datetime(pair.crossing_point_utc_one,utc=True,format='mixed');t2=pd.to_datetime(pair.crossing_point_utc_two,utc=True,format='mixed')
        pair['onset_one_minus_two_hours']=(t1-t2).dt.total_seconds()/3600
        pair['classification_agrees']=pair.status_one==pair.status_two;pair['version_one']=one;pair['version_two']=two
        rows.append(pair)
        summaries.append(dict(version_one=one,version_two=two,paired_scenarios=len(pair),classification_agreement_count=int(pair.classification_agrees.sum()),
          finite_onset_pairs=int(pair.onset_one_minus_two_hours.notna().sum()),maximum_absolute_onset_difference_hours=float(pair.onset_one_minus_two_hours.abs().max()),
          interpretation='Observed numerical differences under same conditional parameters; neither rigorous error bound nor probability interval'))
    full=pd.concat(rows,ignore_index=True);full.to_csv(R/'results/engine_a/version_pairs.csv',index=False)
    result=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),comparisons=summaries,
      checks={'all_versions_same_2048_unique_base_scenarios':True,'all_categories_retained':all(s['classification_agreement_count']==2048 for s in summaries)},
      local_truth_events=0,passed=all(s['classification_agreement_count']==2048 for s in summaries))
    (R/'results/engine_a/version_comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
    for version,color,marker in [('FD_0.5m','#b96835','o'),('FD_0.125m','#18697e','x')]:
        f=full[(full.version_one==version)&(full.version_two=='analytic_erfc')].dropna(subset=['onset_one_minus_two_hours'])
        elapsed=(pd.to_datetime(f.crossing_point_utc_two,utc=True,format='mixed')-pd.Timestamp('2026-06-01T00:00:00Z')).dt.total_seconds()/86400
        ax.scatter(elapsed,f.onset_one_minus_two_hours,label=f'{version}: {len(f)} finite pairs',c=color,marker=marker,s=24,alpha=.7)
    ax.axhline(0,c='.4',lw=1);ax.set_xlabel('Analytic thermal-reference first-passage day since 2026-06-01')
    ax.set_ylabel('FD minus analytic onset (h)');ax.set_title('Same 2048 designs, explicit base-scenario pairing\n137 finite pairs; 248 left-censored and 1663 no-cross cases retained in tables',loc='left',fontweight='bold')
    ax.legend(fontsize=9);ax.grid(alpha=.2);fig.savefig(R/'figures/first_passage_numerical_comparison.png');plt.close(fig)
    print(json.dumps(result))

if __name__=='__main__':main()
