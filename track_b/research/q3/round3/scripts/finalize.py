#!/usr/bin/env python3
"""Bind completed research files and actual cache bytes; no scientific adoption."""
import argparse
from datetime import datetime,timezone
import hashlib,importlib.metadata,json,platform,sys
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]
CACHE=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q3')
BASE='904d7257b899b9f71d1ac9e0eab7479e459eab52'
FROZEN='fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53'
EXCLUDE={'results/output_manifest.json','results/validation.json'}
POSITIVE_C=['future_information_cutoff_rejected','physical_groups_disjoint_per_outer_fold','at_most_one_event_per_physical_group','risk_intervals_positive','no_event_after_risk_end','no_synthetic_rows_added','all_sources_real_observations_or_labels','probability_normalization_and_bounds']

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def record(p):return dict(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),bytes=p.stat().st_size,sha256=sha(p))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def load(p):return json.loads(p.read_text())
def walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values():yield from walk(v)
    elif isinstance(obj,list):
        for v in obj:yield from walk(v)
def verify_records(rows):
    for f in rows:
        p=Path(f['path']);p=p if p.is_absolute() else ROOT/p
        assert p.is_file() and p.stat().st_size==f['bytes'] and sha(p)==f['sha256'],str(p)
def valid_files():
    return [p for p in sorted(R.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='.DS_Store']

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--verify-only',action='store_true');cli.add_argument('--data-only',action='store_true');a=cli.parse_args()
    if a.verify_only:
        for n in ['input_manifest.json','cache_manifest.json','output_manifest.json']:
            verify_records(load(R/'results'/n)['files'])
        v=load(R/'results/validation.json')
        for n,h in v['manifest_sha256'].items():assert sha(R/'results'/n)==h,n
        assert v['passed'];print(json.dumps({'passed':True,'mode':'offline_hash_verification','scientific_coverage_claim':False}));return
    now=datetime.now(timezone.utc).isoformat()
    source=[]
    for p in sorted((R/'results').glob('*sources.json')):
        obj=load(p);rows=obj if isinstance(obj,list) else obj['sources']
        for row in rows:source.append(dict(register_path=str(p.relative_to(R)),**row))
        if isinstance(obj,dict):
            for row in obj.get('acquisition_failures',[]):source.append(dict(register_path=str(p.relative_to(R)),register_section='acquisition_failures',**row))
    source.append(dict(register_path='results/phase_evidence/phase_review.json',**load(R/'results/phase_evidence/phase_review.json')['source']))
    for s in source:
        raw=s.get('cache_path',s.get('path'))
        if raw and s.get('sha256') and s.get('bytes') is not None:
            p=Path(raw);p=p if p.is_absolute() else ROOT/p
            assert p.is_relative_to(ROOT) or p.is_relative_to(CACHE),'Unapproved source path '+str(p)
            verify_records([dict(path=str(p),bytes=s['bytes'],sha256=s['sha256'])])
    write(R/'results/source_register.json',dict(generated_at_utc=now,sources=source,count=len(source),
        scope='Actual per-source reading and requests; failed/metadata-only entries retain their original roles. No historical availability inferred.'))
    caches={}
    for p in sorted((R/'results').rglob('*.json')):
        if p.name in {'cache_manifest.json','output_manifest.json','input_manifest.json','validation.json','source_register.json'}:continue
        for obj in walk(load(p)):
            raw=obj.get('cache_path',obj.get('path'))
            if not isinstance(raw,str) or not obj.get('sha256') or obj.get('bytes') is None:continue
            q=Path(raw)
            if not q.is_absolute() or not q.is_relative_to(CACHE):continue
            row=dict(path=str(q),bytes=obj['bytes'],sha256=obj['sha256'])
            if str(q) in caches:assert caches[str(q)]==row,'Conflicting cache declarations '+str(q)
            caches[str(q)]=row
    verify_records(caches.values())
    write(R/'results/cache_manifest.json',dict(generated_at_utc=now,cache_ownership='q3_only',files=list(caches.values()),
        scope='Every q3 cache byte object declared by source and result JSON. Content-addressed predictions retain all raw rows; no large raw caches added to Git.'))
    indices=[R/'results/engine_b/prediction_cache.json',R/'results/engine_b/censored_challenge.json',*sorted((R/'results/engine_c').rglob('prediction_cache.json'))]
    write(R/'results/raw_prediction_index.json',dict(generated_at_utc=now,indices=[dict(index=record(p),contents=load(p)) for p in indices],
        A_predictions=[record(p) for p in sorted((R/'results/mechanistic_replay').rglob('predictions.csv.gz'))],
        A_parameter_results=[record(p) for p in sorted((R/'results/mechanistic_replay').rglob('parameter_first_passages.parquet'))],
        root_projection_scope='Primary A reference uniform prior plus exactly matched no-age B/C anchors; other priors and full rolling rows retained by these exact indices'))
    protocols=['EXPERIMENT_PROTOCOL.md','EXPERIMENT_AMENDMENT_CENSOR.md','COMMON_ANCHOR_PROTOCOL.md','MECHANISTIC_REPLAY.md']
    inputs=[p for p in valid_files() if p.parts[len(R.parts)] in {'inputs','sources','config'} or str(p.relative_to(R)) in protocols]
    from verify_interfaces import EXPECTED
    approved_shared={}
    for name,expected in EXPECTED.items():
        bp=R/name;assert sha(bp)==expected
        for f in load(bp)['files']:
            p=Path(f['path'])
            if p.is_absolute():approved_shared[str(p)]=dict(path=str(p),bytes=f['bytes'],sha256=f['sha256'])
    verify_records(approved_shared.values())
    frozen=ROOT/'track_b/audit/stage4/round3/baseline_manifest.json';assert sha(frozen)==FROZEN
    write(R/'results/input_manifest.json',dict(generated_at_utc=now,baseline_commit=BASE,baseline_manifest_sha256=FROZEN,
        files=[record(p) for p in inputs]+[record(frozen)]+list(approved_shared.values()),cache_manifest_sha256=sha(R/'results/cache_manifest.json'),
        shared_cache_scope='Only exact absolute files named in advisor-approved bundle roles; read-only hash verification, no copying or active upstream tree traversal',
        note='Delivered role paths only; upstream_path metadata is never an executable input. Scientific input versions remain separate.'))
    write(R/'results/runtime_environment.json',dict(generated_at_utc=now,python=sys.version,executable=sys.executable,platform=platform.platform(),
        packages=sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()],key=lambda x:x['name'].lower()),
        experiment_seed=20261024,additional_dependencies_installed=False))
    if a.data_only:
        print(json.dumps({'passed':True,'scope':'source_input_cache_preflight_only','source_records':len(source),'cache_objects':len(caches),'final_packet_complete':False}));return
    checks={};validation_inputs=[]
    names=['results/interface_adoption.json','results/numerical_benchmark/checks.json','results/weather/validation.json',
           'results/weather_replay/summary.json','results/engine_a/run_summary.json','results/engine_a/v2/run_summary.json',
           'results/engine_a/analytic_erfc/run_summary.json','results/engine_a/version_comparison.json',
           'results/engine_b/validation.json','results/engine_c/final_packet_validation.json',
           'results/common_anchors_no_age/validation.json','results/common_anchors_record_age_challenge/validation.json',
           'results/integration_summary.json','results/waveform/validation.json',
           'results/workspace_entry_verification.json','results/workspace_exit_verification.json']
    names += [str(p.relative_to(R)) for p in sorted((R/'results/mechanistic_replay').rglob('validation.json'))]
    names += [str(p.relative_to(R)) for p in sorted((R/'results/mechanistic_replay').rglob('postprocess_audit.json'))]
    names += [str(p.relative_to(R)) for p in sorted((R/'results/arrival').rglob('status.json')) if p.parent.name!='arrival']
    for n in names:
        p=R/n;d=load(p)
        if 'passed' in d:ok=d['passed']
        elif 'checks' in d:
            cc=d['checks'];ok=all(cc.values()) if isinstance(cc,dict) else all(x['passed'] for x in cc)
        else:raise ValueError('Unknown validation schema '+n)
        checks[n]=bool(ok);validation_inputs.append(record(p))
    for p in sorted((R/'results/engine_c').rglob('validation_checks.json')):
        d=load(p);checks[str(p.relative_to(R))]=bool(all(d[k] for k in POSITIVE_C) and not d['conformal_guarantee_claimed'] and not d['rolling_issues_independent_sample_claimed'])
        validation_inputs.append(record(p))
    qa=load(R/'results/figure_review.json')
    for x in qa['figures']:
        q=ROOT/x['path'];assert sha(q)==x['sha256'] and x['actually_opened'],str(q)
    checks['final_figure_bytes_actually_reviewed']=True
    checks['source_and_cache_declared_hashes_verified']=True
    common=pd.read_csv(R/'results/common_anchors_no_age/predictions.csv')
    checks['common_252_rows_14_physical_cases']=len(common)==252 and common.event_group.nunique()==14
    checks['C_primary_no_record_age']=load(R/'results/engine_c/no_record_age/summary.json')['feature_specification']=='no_record_age_main'
    assert all(checks.values()),{k:v for k,v in checks.items() if not v}
    bundle_files=[('results/predictions.csv','primary_prediction_projection'),('results/evaluation.csv','stratified_external_evaluation'),
      ('results/paired_model_comparison.csv','exact_matched_probability_opportunities'),('results/fold_membership.csv','physical_group_folds'),
      ('results/interval_comparison.csv','model_conditional_intervals_and_conformal_support_audit'),('results/prior_sensitivity.csv','explicit_assumption_sensitivity'),
      ('results/raw_prediction_index.json','all_engine_raw_prediction_indices'),('results/input_manifest.json','inputs_and_approved_shared_cache'),
      ('results/cache_manifest.json','q3_cache_byte_objects'),('results/source_register.json','source_reads_and_failed_requests'),
      ('results/figure_review.json','actual_final_figure_review'),('MODEL_COMPARISON.md','competition_results_and_recommendation'),
      ('EVIDENCE_REVIEW.md','evidence_and_transfer_limits'),('PAPER_OUTLINE.md','paper_methods_results_discussion'),
      ('REQUIREMENTS_MAP.md','question_requirement_result_limits'),('REPRODUCE.md','actual_reproduction_commands'),('HANDOFF.md','scope_and_next_interface')]
    write(R/'exports/research_bundle.json',dict(bundle_version='q3-r3-research-v1',producer_question='q3',created_at_utc=now,
        input_version={'baseline_commit':BASE,'baseline_manifest_sha256':FROZEN},files=[dict(record(R/n),role=role) for n,role in bundle_files],
        primary_A='analytic_erfc_linear_thermal_reference',primary_C='no_record_age_main',
        local_first_mechanical_truth_accepted=False,local_coverage=None,
        limitations=['Stratified conditional scenarios and external terminal-collapse benchmarks, not a validated local95 forecast',
          'Raw complete prediction caches remain separate and exactly hash-bound','Q4 generic v1 lacks Q2 mapping; mapped later versions require an explicit adapter',
          'Final technical validation and output manifest are bound separately by the containing Git commit to avoid a hash cycle']))
    exclusions={**{x:'Avoid manifest/validation circular self reference' for x in EXCLUDE},
        '__pycache__/, *.pyc':'Interpreter transient bytes', '.DS_Store':'OS metadata'}
    outputs=[record(p) for p in valid_files() if str(p.relative_to(R)) not in EXCLUDE]
    write(R/'results/output_manifest.json',dict(generated_at_utc=now,files=outputs,excluded=exclusions,
        commit_binding='This manifest and validation are bound by their containing Git commit; do not write the commit hash back into its own files.'))
    write(R/'results/validation.json',dict(generated_at_utc=now,passed=True,validation_scope='Technical provenance, input gates, numerical implementation, grouping and reproducibility; scientific adoption remains pending',
        checks=checks,validation_inputs=validation_inputs,manifest_sha256={n:sha(R/'results'/n) for n in ['input_manifest.json','cache_manifest.json','source_register.json','output_manifest.json']},
        local_independent_first_mechanical_truth_events=0,local_empirical_coverage=None,
        external_main_groups={'failures':13,'right_censored':1},
        unresolved_scientific_limits=['No historical first availability certification','External terminal collapse differs from local first mechanical initiation',
         'Source curation and case selection limit prospective transfer','FD full design has10/2048 margin-target failures; grid differences are not probabilistic bounds',
         'Discrete A event support is one physical design; zero-width CI is not precise truth','Mechanical-to-bulk-release lag unknown; no absolute arrival inferred']))
    print(json.dumps({'passed':True,'checks':len(checks),'source_records':len(source),'cache_objects':len(caches),'manifest_output_files':len(outputs)}))

if __name__=='__main__':main()
