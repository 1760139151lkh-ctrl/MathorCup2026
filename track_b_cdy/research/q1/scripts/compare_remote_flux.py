#!/usr/bin/env python3
"""Compare the bounded 2026 remote sample to the competition FLUX attachment.

No quality labels are migrated. Header mapping and matched timestamps are explicit.
AI assistance: OpenAI Codex, 2026-10-24.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
Q = ROOT / 'track_b/research/q1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if ROOT != Path('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q1') or Path(sys.prefix).resolve() != (ROOT / 'track_b/.venv').resolve():
        raise RuntimeError('Use the assigned Q1 worktree environment')
    if not json.loads((Q / 'workspace_verification.json').read_text())['passed']:
        raise RuntimeError('Advisor environment readiness has not passed')
    import numpy as np
    import pandas as pd

    local_path = ROOT / '04_B赛道/01_逐小时地气观测（2021-2026）/FLUX_Gyirong_2026.csv'
    remote_path = Q / 'sources/waternet_flux_2026.csv'
    expected_remote_hash = 'f2497ab03d3898c5e0a5fd879e8acf9a56a00e0afafb4b677d86e39bc6b3c4f0'
    assert sha(remote_path) == expected_remote_hash
    initial_local_hash = sha(local_path)
    local = pd.read_csv(local_path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    remote = pd.read_csv(remote_path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    for frame in (local, remote):
        frame['parsed_timestamp'] = pd.to_datetime(frame['Timestamp'], format='mixed', errors='raise')
        assert not frame['parsed_timestamp'].duplicated().any(), 'Duplicate timestamps forbid row mapping'
    local = local.set_index('parsed_timestamp').sort_index()
    remote = remote.set_index('parsed_timestamp').sort_index()
    common = local.index.intersection(remote.index)
    rows = []
    fixed_window = (common >= pd.Timestamp('2026-08-19T10:30:00')) & (common < pd.Timestamp('2026-08-26T10:30:00'))
    for header in local.columns:
        if header == 'Timestamp':
            continue
        remote_header = header.rsplit('(', 1)[0].strip()
        if remote_header not in remote:
            rows.append({'local_column': header, 'remote_column': remote_header, 'mapped': False})
            continue
        atext, btext = local.loc[common, header], remote.loc[common, remote_header]
        a = pd.to_numeric(atext, errors='coerce').to_numpy(dtype=float)
        b = pd.to_numeric(btext, errors='coerce').to_numpy(dtype=float)
        avalid = np.isfinite(a) & (a != 9999.9)
        bvalid = np.isfinite(b) & (b != 9999.9)
        pair = avalid & bvalid
        equal = (a == b) | (np.isnan(a) & np.isnan(b))
        local_only_present = avalid & ~bvalid
        remote_only_present = bvalid & ~avalid
        mismatch_clock = common[avalid != bvalid]
        rows.append({'local_column': header, 'remote_column': remote_header, 'mapped': True,
            'shared_timestamp_labels': len(common), 'local_numeric_present': int(avalid.sum()),
            'remote_numeric_present': int(bvalid.sum()), 'presence_mask_disagreements': int((avalid != bvalid).sum()),
            'local_only_numeric_present': int(local_only_present.sum()),
            'remote_only_numeric_present': int(remote_only_present.sum()),
            'first_presence_disagreement_source_clock': mismatch_clock.min().isoformat() if len(mismatch_clock) else None,
            'last_presence_disagreement_source_clock': mismatch_clock.max().isoformat() if len(mismatch_clock) else None,
            'fixed168h_local_numeric_present': int(avalid[fixed_window].sum()),
            'fixed168h_remote_numeric_present': int(bvalid[fixed_window].sum()),
            'fixed168h_presence_disagreements': int((avalid[fixed_window] != bvalid[fixed_window]).sum()),
            'joint_numeric_present': int(pair.sum()), 'exact_numeric_mismatches_on_present_pairs': int((a[pair] != b[pair]).sum()),
            'maximum_absolute_difference_on_present_pairs': float(np.max(np.abs(a[pair]-b[pair]))) if pair.any() else None,
            'raw_numeric_or_nan_disagreements': int((~equal).sum()),
            'local_unrecognized_numeric_tokens': sorted(set(atext[np.isnan(a) & ~atext.isin(['', 'NaN', 'NAN', 'nan'])])),
            'remote_unrecognized_numeric_tokens': sorted(set(btext[np.isnan(b) & ~btext.isin(['', 'NaN', 'NAN', 'nan'])]))})
    mapping = {'FC_QC': 'FC_mass', 'LE_QC': 'LE', 'H_QC': 'H', 'TAU_QC': 'TAU'}
    qc_records = []
    raw_tokens_by_field = {}
    for qc_column, variable in mapping.items():
        raw_tokens_by_field[qc_column] = sorted(set(remote[qc_column]))
        for role, select in [('all_remote_labels', np.ones(len(remote), dtype=bool)),
                             ('fixed_168h_reference_label_window', (remote.index >= pd.Timestamp('2026-08-19T10:30:00')) & (remote.index < pd.Timestamp('2026-08-26T10:30:00')))]:
            counts = remote.loc[select, qc_column].value_counts(dropna=False)
            for token, count in counts.items():
                qc_records.append({'qc_column': qc_column, 'candidate_variable': variable, 'selection': role,
                    'raw_qc_token': token, 'labels': int(count),
                    'qc_meaning_independently_verified': False, 'labels_transferred_to_public_data': 0})
    results = Q / 'results'; results.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(results / 'remote_flux_column_comparison.csv', index=False)
    pd.DataFrame(qc_records).to_csv(results / 'remote_flux_candidate_qc_tokens.csv', index=False)
    matched = all(r.get('mapped') and r['presence_mask_disagreements'] == 0 and r['exact_numeric_mismatches_on_present_pairs'] == 0 and r['raw_numeric_or_nan_disagreements'] == 0 for r in rows)
    summary = {'comparison_version': 'q1-r1-remote-flux-v1',
        'local_file': str(local_path.relative_to(ROOT)), 'local_sha256': initial_local_hash,
        'remote_file': str(remote_path.relative_to(Q)), 'remote_sha256': expected_remote_hash,
        'byte_identical': initial_local_hash == expected_remote_hash,
        'local_rows': len(local), 'remote_rows': len(remote), 'common_timestamp_labels': len(common),
        'local_only_labels': len(local.index.difference(remote.index)),
        'remote_only_labels': len(remote.index.difference(local.index)),
        'local_measurement_columns': len(rows), 'all_mapped_columns_exact_on_common_labels': matched,
        'timestamp_match_scope': 'naive source-clock labels only; timezone and interval semantics are not proved by matching',
        'extra_remote_columns': sorted(set(remote.columns) - {'Timestamp'} - {r['remote_column'] for r in rows}),
        'candidate_quality_columns': mapping, 'qc_semantics_accepted': False,
        'raw_candidate_qc_tokens_by_field': raw_tokens_by_field,
        'shared_met_qc_codes_for_comparison_only': [0, 1, 2, 4, 8, 9],
        'candidate_qc_tokens_cannot_inherit_met_code_meanings': True,
        'public_input_changed': sha(local_path) != initial_local_hash,
        'public_quality_labels_transferred': 0,
        'adoption_status': 'proposal_only; advisor/team must review mapping, quality-code origin and historical availability',
        'data_role': 'exploration', 'context_ref': 'context.json'}
    assert not summary['public_input_changed']
    (results / 'remote_flux_comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
