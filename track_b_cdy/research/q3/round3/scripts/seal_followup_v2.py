#!/usr/bin/env python3
"""Seal fixed-risk applicability and mapped-Q4 followup, preserving old packets."""
from datetime import datetime,timezone
from pathlib import Path
import json,subprocess,sys
from finalize import sha,record,write,verify_records
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]
N=R/'results/applicability_sensitivity/risk_set_revision';P=R/'results/arrival/propagation_v2';O=R/'results/followup_v2'
Q=R/'inputs/q4/bundle_q4-r3-propagation-v2/bundle.json'
QHASH='9fec7f2083ab43f81b19da2c1cca3cef9b2ad0b5db36441495162412d1e8dda4'
LEGACY={'input_manifest_sha256':'90e31f97eae5f2d668c71f7401500c0b16ca5eebf09e3509ca5777ab6644a8bb',
        'output_manifest_sha256':'8814c76aee4d6db85d35c80050d9f4f9798fac1838d927deac440bcd9b4e55d3',
        'bundle_sha256':'c96e82632b461d913831eec2b736c318ead8a180f950735ccc4aa48eb082c157'}
def main():
    O.mkdir(parents=True,exist_ok=True);assert sha(Q)==QHASH
    qb=json.loads(Q.read_text());shared=[]
    for f in qb['files']:
        p=Path(f['path']);p=p if p.is_absolute() else ROOT/p
        verify_records([dict(path=str(p),bytes=f['bytes'],sha256=f['sha256'])]);shared.append(record(p))
    original=R/'workspace_verification.json';saved=original.read_bytes()
    try:
        done=subprocess.run([sys.executable,str(ROOT/'track_b/scripts/stage4_workspace.py'),'verify','--round','round3','--question','q3','--expected-root',str(ROOT),'--expected-base','904d7257b899b9f71d1ac9e0eab7479e459eab52'],cwd=ROOT,capture_output=True,text=True)
        (O/'workspace_check.log').write_text(done.stdout+done.stderr);check=json.loads(original.read_text());write(O/'workspace_verification.json',check);assert done.returncode==0 and check['passed']
    finally:original.write_bytes(saved)
    old=subprocess.run([sys.executable,str(R/'scripts/finalize.py'),'--verify-only'],cwd=ROOT,capture_output=True,text=True)
    (O/'original_packet_verification.log').write_text(old.stdout+old.stderr);assert old.returncode==0
    v1=R/'results/applicability_sensitivity'
    legacy_packet=v1/'PACKET_VALIDATION_V1.json';legacy=json.loads(legacy_packet.read_text());assert legacy['passed']
    legacy_paths=[(v1/'INPUT_MANIFEST.json','input_manifest_sha256'),(v1/'OUTPUT_MANIFEST.json','output_manifest_sha256'),(R/'exports/applicability_bundle_v1.json','bundle_sha256')]
    for p,key in legacy_paths:assert sha(p)==legacy[key]==LEGACY[key],str(p)
    for name in ['INPUT_MANIFEST.json','OUTPUT_MANIFEST.json']:verify_records(json.loads((v1/name).read_text())['files'])
    fixed=json.loads((N/'aggregation_validation.json').read_text());prop=json.loads((P/'validation.json').read_text());review=json.loads((N/'review/final_fixed_risk_audit.json').read_text())
    review_inputs=[]
    for f in review['inputs']:
        p=Path(f['path']);p=p if p.is_absolute() else R/p
        row=dict(path=str(p),bytes=f['bytes'],sha256=f['sha256']);verify_records([row]);review_inputs.append(row)
    for name in ['input_index','output_index']:
        index=P/(name+'.json');assert sha(index)==prop[name+'_sha256'],str(index)
        verify_records(json.loads(index.read_text())['files'])
    for directory in [N,P]:
        qa=json.loads((directory/'figure_review.json').read_text())
        for f in qa['figures']:
            p=Path(f['path']);p=p if p.is_absolute() else ROOT/p
            assert f['actually_opened'] and sha(p)==f['sha256'],str(p)
    registration=json.loads((N/'input_registration.json').read_text());verify_records(registration['inputs'])
    now=datetime.now(timezone.utc).isoformat()
    inputs=registration['inputs']+shared+review_inputs+[record(Q),record(R/'exports/research_bundle.json'),record(legacy_packet)]+[record(p) for p,key in legacy_paths]
    write(O/'input_manifest.json',dict(generated_at_utc=now,files=inputs,base_research_commit='bb9258d791a6e9735c28528ff4408c7434c3d149',
        scientific_scope='Fixed original history risk primary; history revocation separately named; mapped Q4 quality-unqualified conditional outputs',physics_rerun=False))
    app=R/'exports/applicability_bundle_v2.json'
    named=[(p,p.name) for p in sorted(N.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.log']
    named.extend([(R/'APPLICABILITY_FIXED_RISK.md','primary_interpretation_update'),(v1/'crossing_support_audit.csv','all342_original_crossings'),(v1/'p0149_parameter_audit.csv','independent_stress_audit')])
    write(app,dict(bundle_version='q3-r3-strength-applicability-v2-fixed-history-risk',producer_question='q3',created_at_utc=now,
      input_version={'original_research_commit':'bb9258d791a6e9735c28528ff4408c7434c3d149','legacy_applicability_v1_sha256':sha(R/'exports/applicability_bundle_v1.json')},
      files=[dict(record(p),role=role) for p,role in named],
      primary_policy='fixed_history_risk_out_of_domain_to_unknown',secondary_diagnostic='revoke_out_of_domain_history_classification_diagnostic',
      limitations=['All domain filtering is retrospective, including future and post-cross states','Original at-risk and already-started masses remain fixed in primary contrast',
       'Renormalized zero support is not safety; no empirical probability or95 guarantee','Old packets retained; v1 sealing script retired because case-insensitive filename collision was repaired with distinct-word packet validation']))
    join=R/'exports/propagation_join_bundle_v2.json'
    write(join,dict(bundle_version='q3-r3-q4mapped-join-v2',producer_question='q3',created_at_utc=now,input_bundle_sha256=QHASH,
      files=[dict(record(p),role=p.name) for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.log'],
      limitations=['Legitimate parent lineage may pass despite unqualified propagation quality','No qualified arrival envelope or probability',
       'Unknown mechanical-to-bulk-release delay leaves absolute arrival null','No-start parent stays if-released counterfactual','Raster-derived distance is conditional, not validated warning effectiveness']))
    combined=R/'exports/r3_followup_bundle_v2.json'
    write(combined,dict(bundle_version='q3-r3-followup-v2',producer_question='q3',created_at_utc=now,
      files=[dict(record(p),role=role) for p,role in [(app,'fixed_risk_applicability'),(join,'Q4_mapped_lineage_and_quality_negative_result'),(O/'input_manifest.json','approved_increment_inputs'),(R/'R3_FOLLOWUP_HANDOFF.md','increment_handoff')]],
      original_packets_unchanged=True,physical_simulations_rerun=False,local_truth_events_added=0,empirical_coverage=None))
    scripts=[R/'scripts'/n for n in ['applicability_fixed_risk.py','plot_fixed_risk.py','join_propagation_v2.py','seal_followup_v2.py']]
    paths=[p for d in [N,P,O,R/'inputs/q4/bundle_q4-r3-propagation-v2'] for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['output_manifest.json','packet_validation.json']]
    paths += scripts+[R/'APPLICABILITY_FIXED_RISK.md',R/'R3_FOLLOWUP_HANDOFF.md',app,join,combined]
    write(O/'output_manifest.json',dict(generated_at_utc=now,files=[record(p) for p in sorted(set(paths))],excluded={'output_manifest.json':'self-reference','packet_validation.json':'avoid circular hash dependency','__pycache__':'transient interpreter bytes'}))
    checks=dict(fixed_risk_distribution_checks=fixed['passed'],fixed_risk_independent_review=review['passed'],mapped_lineage_and_quality_gates=prop['passed'],
      standard_five_checks=check['passed'],original_packet_hashes_preserved=old.returncode==0,legacy_applicability_v1_registered_bytes_preserved=all(sha(p)==LEGACY[key] for p,key in legacy_paths),Q4_39_approved_roles_verified=len(qb['files'])==39,
      fixed_review_bound_inputs_verified=True,mapped_adapter_input_output_indices_verified=True,new_figures_actually_opened=True)
    assert all(checks.values())
    write(O/'packet_validation.json',dict(generated_at_utc=now,checks=checks,passed=True,input_manifest_sha256=sha(O/'input_manifest.json'),output_manifest_sha256=sha(O/'output_manifest.json'),
      bundle_sha256=sha(combined),local_truth_events=0,empirical_coverage=None,physics_rerun=False))
    print(json.dumps(dict(passed=True,followup_bundle_sha256=sha(combined),applicability_bundle_v2_sha256=sha(app),propagation_join_bundle_v2_sha256=sha(join),output_manifest_sha256=sha(O/'output_manifest.json'))))
if __name__=='__main__':main()
