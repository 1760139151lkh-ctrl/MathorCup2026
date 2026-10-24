#!/usr/bin/env python3
"""Strict delivered-role pairing; bulk-release travel never becomes onset truth."""
import argparse
from datetime import datetime,timezone
import hashlib,json,math
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def present(x):return pd.notna(x) and str(x).strip()!=''

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--bundle',required=True);cli.add_argument('--expected-sha256',required=True)
    cli.add_argument('--onsets',default='results/engine_a/analytic_erfc/first_passages.csv');cli.add_argument('--outdir',default='results/arrival/propagation_v1')
    args=cli.parse_args();bp=ROOT/args.bundle;assert bp.resolve().is_relative_to(R/'inputs/q4') and sha(bp)==args.expected_sha256
    bundle=json.loads(bp.read_text());files=[]
    for f in bundle['files']:
        p=Path(f['path']);p=p if p.is_absolute() else ROOT/p
        # Read external cache objects only when named in this delivered bundle.
        assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256'],str(p)
        files.append((f['role'],p))
    targets=[p for role,p in files if role=='target_arrivals'];assert len(targets)==1
    f=pd.read_csv(targets[0]);onset=pd.read_csv(R/args.onsets);rows=[];rejections=[]
    out=(R/args.outdir).resolve();assert out.is_relative_to(R/'results');out.mkdir(parents=True,exist_ok=True)
    context=f.copy();context['absolute_arrival_utc']=None;context['context_role']='conditional_bulk_release_context; not mechanical-onset pairing'
    context.to_csv(out/'propagation_context.csv',index=False)
    for _,raw in f.iterrows():
        r=raw.to_dict()
        for source,target in [('upstream_model_id','parent_model_id'),('upstream_parameter_version','release_parameter_version'),
                              ('upstream_geometry_version','parent_geometry_version'),('initiation_to_release_delay_seconds','mechanical_to_release_delay_seconds')]:
            if not present(r.get(target)) and present(r.get(source)):r[target]=r[source]
        required=['base_scenario_id','parent_model_id','mechanism_id','release_parameter_version','parent_geometry_version']
        missing=[k for k in required if not present(r.get(k))]
        if missing:
            rejections.append(dict(run_id=r.get('run_id'),scenario_id=r['scenario_id'],target_id=r['target_id'],matching_onset_rows=0,
              reason='missing_explicit_parent_lineage',missing_fields=json.dumps(missing)));continue
        s=onset[onset.base_scenario_id.eq(r['base_scenario_id'])]
        for left,right in [('model_id','parent_model_id'),('mechanism_id','mechanism_id'),('parameter_version','release_parameter_version'),('geometry_version','parent_geometry_version')]:s=s[s[left].eq(r[right])]
        if len(s)!=1:
            rejections.append(dict(run_id=r.get('run_id'),scenario_id=r['scenario_id'],target_id=r['target_id'],matching_onset_rows=len(s),reason='unresolved_or_nonunique_exact_base_model_parameter_geometry_lineage'));continue
        s=s.iloc[0];lag=pd.to_numeric(r.get('mechanical_to_release_delay_seconds'),errors='coerce')
        lo=pd.to_numeric(r.get('arrival_bracket_lower_seconds'),errors='coerce');hi=pd.to_numeric(r.get('arrival_bracket_upper_seconds'),errors='coerce')
        if any(pd.notna(x) and (not math.isfinite(float(x)) or x<0) for x in [lag,lo,hi]) or (pd.notna(lo) and pd.notna(hi) and lo>hi):
            rejections.append(dict(run_id=r.get('run_id'),scenario_id=r['scenario_id'],target_id=r['target_id'],matching_onset_rows=1,reason='invalid_delay_or_arrival_bracket'));continue
        lower=pd.to_datetime(s.crossing_lower_utc,utc=True,errors='coerce');upper=pd.to_datetime(s.crossing_upper_utc,utc=True,errors='coerce')
        known=all(pd.notna(x) for x in [lag,lo,hi,lower,upper]) and present(r.get('arrival_definition'))
        # Preserve saved-output arrival brackets instead of an exact hit point.
        al=lower+pd.Timedelta(seconds=float(lag)+float(lo)) if known else None
        au=upper+pd.Timedelta(seconds=float(lag)+float(hi)) if known else None
        rows.append(dict(run_id=r.get('run_id'),scenario_id=r['scenario_id'],base_scenario_id=r['base_scenario_id'],source_scenario_id=s.scenario_id,
            mechanism_model_id=s.model_id,propagation_model_id=r['model_id'],target_id=r['target_id'],geometry_version=r['geometry_version'],parameter_version=r['parameter_version'],
            source_first_passage_status=s.status,mechanical_to_release_delay_seconds=float(lag) if pd.notna(lag) else None,
            bulk_release_arrival_lower_seconds=float(lo) if pd.notna(lo) else None,bulk_release_arrival_upper_seconds=float(hi) if pd.notna(hi) else None,
            arrival_lower_utc=al.isoformat() if al is not None else None,arrival_upper_utc=au.isoformat() if au is not None else None,
            arrival_time_utc=None,arrival_definition=r.get('arrival_definition'),physical_phase='arrival_at_defined_target',
            include_in_arrival_envelope=r.get('include_in_arrival_envelope'),numerical_qualification=r.get('numerical_qualification'),
            arrival_status='conditional_matched_interval_with_explicit_lag' if known else 'bulk_release_relative_only_lag_or_onset_unknown',
            evaluation_stratum='conditional_scenario',event_timing_validated=False,arrival_is_initiation_truth=False))
    pd.DataFrame(rows,columns=list(rows[0]) if rows else ['run_id','scenario_id','target_id','arrival_lower_utc','arrival_upper_utc','arrival_time_utc']).to_csv(out/'conditional_arrivals.csv',index=False)
    pd.DataFrame(rejections).to_csv(out/'rejected_pairings.csv',index=False)
    report=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),status='strict_delivered_role_pairing_executed',bundle_version=bundle['bundle_version'],bundle_sha256=sha(bp),
       delivered_files_verified=len(files),target_rows=len(f),unique_pairs=len(rows),rejected_pairs=len(rejections),absolute_interval_pairs=sum(r['arrival_lower_utc'] is not None for r in rows),
       checks={'every_target_retained_as_pair_or_rejection':len(rows)+len(rejections)==len(f),'no_absolute_point_arrival_inferred':all(r['arrival_time_utc'] is None for r in rows)},
       limitations=['Bulk release is a different physical origin from first mechanical initiation; lag not assumed zero',
         'No approximate scenario string matching or Cartesian sampling','Saved-output first hit is an interval bracket, not exact arrival',
         'Q4 partial envelope flag does not certify numerical accuracy, probability or event-time validation'])
    report['passed']=all(report['checks'].values());(out/'status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    assert report['passed'];print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
