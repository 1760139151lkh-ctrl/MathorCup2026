#!/usr/bin/env python3
"""Verify advisor-delivered file-role mappings, never upstream active paths."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parents[1];ROOT=R.parents[3]
EXPECTED={
'inputs/q4/propagation_handoff_v1_q4-r3-propagation-v1-metadata-handoff/bundle.json':'ca2687f43fbca865fea8556435c9765ccc429fed4bf3f05dd5df8f79deb2fda0',
'inputs/q2/analytic_thermal_bundle_q2-r3-analytic-erfc-thermal-v1/bundle.json':'05e8b885198a3011e316472f562ba92480788cb04c6ab9bebfb3e04dbd3660ca',
'inputs/q1/feature_bundle_q1-r3-feature-v1/bundle.json':'edd817989c3bdb5b21953e31d2a2ebcc7c637eedb414a1c86495e02210d3eaa9',
'inputs/q2/mechanism_bundle_q2-r3-mechanism-v1/bundle.json':'65758b85d934267e883616eb2a56924e5b52d818e10b6f3eaa08bf934e54ce3a',
'inputs/q2/mechanism_bundle_v2_q2-r3-mechanism-thermal-refinement-v2/bundle.json':'12eb0b329acede54face734b145cf33a8bfc5d329f6231b5a110c52ddec618c9',
'inputs/q2/numerical_supplement_bundle_q2-r3-numerical-limits-v1/bundle.json':'8ad708b3867ac35421ac1e3aa035969c52136e5bed1c845b190e9223fcad1b5b',
'inputs/q2/composition_bundle_q2-r3-literature-composition-v1/bundle.json':'0837c492726e78b2fd7b945e64731ee989ce141ec4cb817c3a0abff8cb12fdf9',
'inputs/q2/release_bundle_v2_q2-r3-release-v2-spatial-copdem-v1/bundle.json':'0b273b1b5eb7d65b9b9ab9731c9dceeef73f1c5f396fc743c97a7fdd206dc4f9',
'inputs/q4/bundle_q4-r3-spatial-copdem-v1-frozen-export/bundle.json':'b6c02508acbe7bf131a0414ef7a90cafef2c5580597e2bc3b6f990e6892c4955'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    records=[]
    for n,h in EXPECTED.items():
        p=R/n;b=json.loads(p.read_text());assert sha(p)==h
        for f in b['files']:
            q=Path(f['path']);q=q if q.is_absolute() else ROOT/q
            assert q.stat().st_size==f['bytes'] and sha(q)==f['sha256']
        records.append(dict(bundle_version=b['bundle_version'],path=str(p.relative_to(ROOT)),sha256=h,verified_files=len(b['files']),adoption=b.get('advisor_review')))
        if b['producer_question']=='q1':
            paths={f['role']:ROOT/f['path'] for f in b['files'] if not Path(f['path']).is_absolute()}
            definitions=pd.read_csv(paths['feature_definitions'])
            definitions.head(0).to_csv(R/'results/q1_feature_schema.csv',index=False)
            records[-1]['actual_read_scope']='All feature definition rows and family map; support metadata only, no ranking or source representation adoption'
            family=pd.read_csv(paths['all_input_variables_selection_and_exclusion']);records[-1]['feature_definition_rows']=len(definitions);records[-1]['variable_map_rows']=len(family)
    v1=R/'exports/event_bundle.json';assert sha(v1)=='075b149214b5c9a8827af45af221ee6ee6b6428090e6d9337afb1943698d2faf'
    assert sha(R/'exports/event_bundle_v2_external.json')=='359f1e9868a1a63125296fd43e37ea22928815396a76d529669f8332baa8bbde'
    phase=R/'exports/phase_evidence_bundle_v3.json';assert sha(phase)=='db5f1b6c1f4c04a7233b8b964e18dfa90b45c061a24009247aeef562cbe98898'
    for bpath in [v1,R/'exports/event_bundle_v2_external.json',phase]:
        b=json.loads(bpath.read_text())
        for f in b['files']:
            p=Path(f['path']);p=p if p.is_absolute() else ROOT/p
            assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256']
    result=dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),passed=True,interfaces=records,original_event_v1_unchanged=True,external_event_v2_unchanged=True,phase_v3_is_candidate_only=not json.loads(phase.read_text())['approved_first_mechanical_truth'])
    (R/'results/interface_adoption.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':True,'bundles':len(records),'event_versions':2,'phase_evidence_versions':1}))

if __name__=='__main__':main()
