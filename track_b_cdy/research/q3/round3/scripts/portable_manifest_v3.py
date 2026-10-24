#!/usr/bin/env python3
"""Create or verify a metadata-only portable view of the frozen v2 input list."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
ROOT = R.parents[3]
OUT = R / 'results/followup_v3'
BUNDLE = R / 'exports/portable_manifest_bundle_v3.json'
SOURCE = R / 'results/followup_v2/input_manifest.json'
PRODUCER_ROOT = Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q3')
OWN = Path('track_b/research/q3/round3')
Q4 = R / 'inputs/q4/bundle_q4-r3-propagation-v2/bundle.json'
Q4_SHA = '9fec7f2083ab43f81b19da2c1cca3cef9b2ad0b5db36441495162412d1e8dda4'
SOURCE_SHA = '91d1dc933de07b435a625c4177252229785f3e58f5949c481301fdd5949816df'
FROZEN = {
    'results/applicability_sensitivity/INPUT_MANIFEST.json': '90e31f97eae5f2d668c71f7401500c0b16ca5eebf09e3509ca5777ab6644a8bb',
    'results/applicability_sensitivity/OUTPUT_MANIFEST.json': '8814c76aee4d6db85d35c80050d9f4f9798fac1838d927deac440bcd9b4e55d3',
    'results/followup_v2/input_manifest.json': SOURCE_SHA,
    'results/followup_v2/output_manifest.json': '300e93c840fda449ef541b50aeac45c949288d880312c3fe201e64d7ef890837',
    'exports/applicability_bundle_v1.json': 'c96e82632b461d913831eec2b736c318ead8a180f950735ccc4aa48eb082c157',
    'exports/applicability_bundle_v2.json': 'ac45bb5b437ccaab983f2bb95322aff69a4c0bb5dd1f1d122245f248c3120738',
    'exports/propagation_join_bundle_v2.json': '851e79c8655a4eeabc22a31e820326115ba4330ef9c755b0de233a71b1ae70eb',
    'exports/r3_followup_bundle_v2.json': 'b134d88deadd2f2a5f92e954881dc3c38349a787ae41348e2245b7026fbdbb96',
    'exports/research_bundle.json': 'fec1e69d761c04fea4c67e5379ce2b518b5e22aa301b253d01828987eef03019',
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def record(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path))


def normalize(row, approved):
    result = deepcopy(row)
    p = Path(row['path'])
    if p.is_absolute() and p.is_relative_to(PRODUCER_ROOT):
        relative = p.relative_to(PRODUCER_ROOT)
        assert relative.is_relative_to(OWN), str(relative)
        result['path'] = str(relative)
    elif p.is_absolute():
        assert row['path'] in approved, 'Unapproved external reference'
        assert (row['bytes'], row['sha256']) == approved[row['path']]
    p = Path(result['path'])
    assert '..' not in p.parts
    target = p if p.is_absolute() else ROOT / p
    assert target.is_file() and target.stat().st_size == row['bytes']
    assert sha(target) == row['sha256'], result['path']
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--verify-only', action='store_true')
    args = cli.parse_args()
    assert sha(SOURCE) == SOURCE_SHA and sha(Q4) == Q4_SHA
    approved = {f['path']: (f['bytes'], f['sha256']) for f in read(Q4)['files'] if Path(f['path']).is_absolute()}
    original = read(SOURCE)
    normalized = [normalize(row, approved) for row in original['files']]
    changed = [i for i, (old, new) in enumerate(zip(original['files'], normalized)) if old != new]
    assert len(normalized) == 62 and changed == list(range(45, 56))
    for old, new in zip(original['files'], normalized):
        assert {k: v for k, v in old.items() if k != 'path'} == {k: v for k, v in new.items() if k != 'path'}
    frozen = []
    for name, expected in FROZEN.items():
        p = R / name
        assert sha(p) == expected, name
        frozen.append(record(p))
    checks = dict(source_v2_manifest_hash_pinned=True,all_62_rows_kept_in_original_order=True,
                  exactly_11_owned_repo_paths_normalized=True,all_other_row_fields_unchanged=True,
                  duplicate_rows_retained=True,all_62_target_hashes_and_sizes_verified=True,
                  only_7_exact_approved_cache_paths_remain_absolute=True,frozen_v1_v2_manifests_and_exports_unchanged=True)
    assert sum(Path(row['path']).is_absolute() for row in normalized) == 7
    assert len({(row['path'], row['bytes'], row['sha256']) for row in normalized}) == 58
    if not args.verify_only:
        OUT.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        portable = deepcopy(original)
        portable['files'] = normalized
        portable.update(manifest_version='q3-r3-followup-input-v3-portable-metadata',normalized_at_utc=now,
                        source_manifest=record(SOURCE),metadata_only=True,
                        normalization_scope='Only row paths under the exact producer Q3 repository root are made repository-relative; approved cache paths, row order, duplicates, bytes, hashes and scientific metadata are unchanged.')
        write(OUT / 'input_manifest.json', portable)
        write(OUT / 'normalization_report.json', dict(generated_at_utc=now,metadata_only=True,source_manifest=record(SOURCE),
              normalized_row_count=62,changed_path_row_count=11,relative_path_rows=55,approved_absolute_cache_rows=7,
              path_changes=[dict(source_row_index_0based=i,normalized_path=normalized[i]['path'],bytes=normalized[i]['bytes'],sha256=normalized[i]['sha256'],operation='strip exact producer repository prefix') for i in changed],
              row_order_and_duplicates_preserved=True,normalization_scope='Repository path representation only; no science or payload byte changes',
              frozen_v1_v2_records=frozen,checks=checks,passed=True))
        write(BUNDLE,dict(bundle_version='q3-r3-portable-manifest-v3-metadata-only',producer_question='q3',created_at_utc=now,
              files=[dict(record(p),role=role) for p,role in [(OUT/'input_manifest.json','portable_input_manifest'),(OUT/'normalization_report.json','normalization_and_frozen_byte_audit'),(OUT/'README.md','scope_and_verification'),(Path(__file__).resolve(),'portable_metadata_verifier')]],
              metadata_only=True,normalizes_input_manifest_sha256=SOURCE_SHA,preserved_v2_research_bundle_sha256=FROZEN['exports/r3_followup_bundle_v2.json'],
              scientific_results_changed=False,physics_rerun=False,qualified_arrival_rows=0,arrival_probability_rows=0,empirical_coverage=None))
        write(OUT/'validation.json',dict(generated_at_utc=now,checks=checks,passed=True,input_manifest_sha256=sha(OUT/'input_manifest.json'),
              normalization_report_sha256=sha(OUT/'normalization_report.json'),bundle_sha256=sha(BUNDLE),metadata_only=True))
    portable = read(OUT/'input_manifest.json')
    assert portable['files'] == normalized
    for key, value in original.items():
        if key != 'files':
            assert portable[key] == value, key
    report = read(OUT/'normalization_report.json')
    assert report['passed'] and report['checks'] == checks and report['frozen_v1_v2_records'] == frozen
    validation = read(OUT/'validation.json')
    assert validation['passed'] and validation['checks'] == checks
    for key, p in [('input_manifest_sha256',OUT/'input_manifest.json'),('normalization_report_sha256',OUT/'normalization_report.json'),('bundle_sha256',BUNDLE)]:
        assert validation[key] == sha(p), key
    for row in read(BUNDLE)['files']:
        p = ROOT / row['path']
        assert not Path(row['path']).is_absolute() and p.stat().st_size == row['bytes'] and sha(p) == row['sha256']
    print(json.dumps(dict(passed=True,mode='verify_only' if args.verify_only else 'metadata_only_build',rows=62,normalized_paths=11,
                         approved_absolute_cache_paths=7,input_manifest_sha256=sha(OUT/'input_manifest.json'),bundle_sha256=sha(BUNDLE))))


if __name__ == '__main__':
    main()
