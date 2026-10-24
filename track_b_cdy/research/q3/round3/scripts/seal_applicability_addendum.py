#!/usr/bin/env python3
"""Seal only the new applicability increment; preserve the original packet."""
from datetime import datetime,timezone
from pathlib import Path
import json,subprocess,sys
from finalize import sha,record,write,verify_records
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3];O=R/'results/applicability_sensitivity'
NEW_SCRIPTS=['applicability_sensitivity.py','applicability_mass_audit.py','plot_applicability.py','acquire_applicability_source.py','seal_applicability_addendum.py']
def main():
    original=R/'workspace_verification.json';saved=original.read_bytes();oldhash=sha(original)
    command=[sys.executable,str(ROOT/'track_b/scripts/stage4_workspace.py'),'verify','--round','round3','--question','q3','--expected-root',str(ROOT),'--expected-base','904d7257b899b9f71d1ac9e0eab7479e459eab52']
    try:
        done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        (O/'workspace_check.log').write_text(done.stdout+done.stderr)
        check=json.loads(original.read_text());write(O/'workspace_verification.json',check)
        assert done.returncode==0 and check['passed']
    finally:original.write_bytes(saved)
    assert sha(original)==oldhash
    verified=subprocess.run([sys.executable,str(R/'scripts/finalize.py'),'--verify-only'],cwd=ROOT,capture_output=True,text=True)
    (O/'original_packet_verification.log').write_text(verified.stdout+verified.stderr);assert verified.returncode==0
    registration=json.loads((O/'input_registration.json').read_text());binding=json.loads((O/'protocol_snapshot_binding.json').read_text())
    inputs=[]
    for f in registration['inputs']:
        p=ROOT/f['path']
        if p==O/'PROTOCOL.md':
            p=ROOT/binding['snapshot_path'];assert sha(p)==f['sha256']
        else:assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256'],str(p)
        inputs.append(record(p))
    sources=json.loads((O/'source_register.json').read_text())['sources']
    for f in sources:verify_records([dict(path=f['cache_path'],bytes=f['bytes'],sha256=f['sha256'])])
    inputs.extend(dict(path=f['cache_path'],bytes=f['bytes'],sha256=f['sha256']) for f in sources)
    inputs.extend(record(p) for p in [R/'exports/research_bundle.json',R/'results/output_manifest.json',O/'input_registration.json',O/'PROTOCOL.md'])
    now=datetime.now(timezone.utc).isoformat()
    write(O/'INPUT_MANIFEST.json',dict(generated_at_utc=now,base_research_commit='bb9258d791a6e9735c28528ff4408c7434c3d149',files=inputs,
      execution_protocol_note='Source terminology/history wording clarified after registration; exact executed protocol snapshot verifies registered hash; no weight-rule change',physics_rerun=False))
    aggregation=json.loads((O/'validation.json').read_text());mass=json.loads((O/'mass_audit_validation.json').read_text());qa=json.loads((O/'figure_review.json').read_text())
    for f in qa['figures']:assert f['actually_opened'] and sha(ROOT/f['path'])==f['sha256']
    independent=json.loads((O/'review_boundary/final_readonly_audit.json').read_text())
    checks=dict(aggregation_checks=aggregation['passed'],explicit_mixture_and_unknown_mass_audit=mass['passed'],independent_readonly_boundary_and_full_output_review=independent['passed'],
       standard_five_checks=check['passed'],original_packet_all_hashes_preserved=verified.returncode==0,registered_inputs_or_exact_protocol_snapshot_verified=True,
       primary_source_cache_hash_verified=True,final_figure_actually_opened=True)
    assert all(checks.values())
    named=[('predictions.csv.gz','all_four_policy_distributions'),('crossing_support_audit.csv','all_342_actual_crossings'),
      ('parameter_weight_audit.parquet','all_1536000_original_rows_and_weights'),('comparison_summary.csv','policy_prior_horizon_summary'),
      ('mixture_mechanism_masses.csv.gz','original_and_new_mixture_mechanism_masses'),('conservative_mass_transfers.csv.gz','event_no_start_past_unknown_transfers'),
      ('p0149_parameter_audit.csv','independent_stress_calculation'),('summary.json','aggregation_findings'),('RESULTS.md','interpretation_and_reproduction'),
      ('PROTOCOL.md','posthoc_design_and_amendments'),('source_register.json','primary_literature_read_scope'),('INPUT_MANIFEST.json','actual_increment_inputs'),
      ('validation.json','distribution_implementation_checks'),('mass_audit_validation.json','mixture_mass_checks'),('workspace_verification.json','increment_five_checks'),
      ('review_boundary/final_readonly_audit.json','independent_full_distribution_and_mass_review'),('review_boundary/REVIEW.md','independent_review_interpretation'),
      ('figure_review.json','actual_visual_review'),('applicability_comparison.png','applicability_and_conservative_bound_figure')]
    bundle=R/'exports/applicability_bundle_v1.json'
    write(bundle,dict(bundle_version='q3-r3-strength-applicability-v1',producer_question='q3',created_at_utc=now,
      input_version={'research_commit':'bb9258d791a6e9735c28528ff4408c7434c3d149','original_research_bundle_sha256':sha(R/'exports/research_bundle.json')},
      files=[dict(record(O/n),role=role) for n,role in named],
      interpretation_update='Original nonzero future-onset support entirely relies on fitted-strength-law extrapolation; original computations retained',
      limitations=['Posthoc numerical applicability sensitivity, not a certified local-material or operational filter',
       'In-domain renormalized zero start mass is not physical safety; out-of-domain mass is separately retained as unknown',
       'Criterion applicability100–400kPa differs from full experiment stress range100–800kPa',
       'Future observed-domain fraction includes post-cross continuation; historical material validity not fully established',
       'No physics re-integration, local truth or empirical95 validation added']))
    paths=[p for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['OUTPUT_MANIFEST.json','VALIDATION.json']]
    paths += [R/'scripts'/n for n in NEW_SCRIPTS]+[R/'APPLICABILITY_ADDENDUM.md',bundle]
    write(O/'OUTPUT_MANIFEST.json',dict(generated_at_utc=now,files=[record(p) for p in sorted(paths)],
      excluded={'OUTPUT_MANIFEST.json':'self-reference','VALIDATION.json':'avoid circular hash dependency','__pycache__':'transient interpreter output'},
      original_packet_unchanged=True))
    write(O/'VALIDATION.json',dict(generated_at_utc=now,checks=checks,passed=all(checks.values()),
      aggregation_check_count=len(aggregation['checks']),mass_audit_check_count=len(mass['checks']),standard_workspace_check_count=len(check['checks']),
      input_manifest_sha256=sha(O/'INPUT_MANIFEST.json'),output_manifest_sha256=sha(O/'OUTPUT_MANIFEST.json'),bundle_sha256=sha(bundle),
      original_research_commit='bb9258d791a6e9735c28528ff4408c7434c3d149',physics_rerun=False,local_truth_events=0,empirical_coverage=None))
    print(json.dumps({'passed':True,'bundle_sha256':sha(bundle),'output_manifest_sha256':sha(O/'OUTPUT_MANIFEST.json'),'output_files':len(paths),'original_packet_preserved':True}))
if __name__=='__main__':main()
