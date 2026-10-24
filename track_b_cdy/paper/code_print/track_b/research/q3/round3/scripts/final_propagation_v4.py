#!/usr/bin/env python3
"""Join seven already executed conditional cases; seal a portable unique index."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import seal_fullmask_v3 as full

R, ROOT = full.R, full.ROOT
read, write, sha, record = full.read, full.write, full.sha, full.record
BASE = 'c6200b95db074775cc1cb24b163e3caef29f5cd2'
START = '0d5326d6e3428df4d714d8101c41c7c925eca0ef'
O = R / 'results/final_propagation_v4'
D = R / 'results/arrival/compact_delta_v1'
BUNDLE = R / 'exports/final_propagation_join_bundle_v4.json'
PACKETS = [
    ('compact_v2', R/'inputs/q4/bundle_q4-r3-propagation-v2/bundle.json', '9fec7f2083ab43f81b19da2c1cca3cef9b2ad0b5db36441495162412d1e8dda4',39),
    ('fullmask_v3',full.Q,full.QPIN,66),
    ('compact_delta_v1',R/'inputs/q4/bundle_q4-r3-compact-delta-v1/bundle.json','044a9a08ce09e8b2b5470a6a4351942fb08054e52e9728e2bb4d51a2295841ac',48),
]
DELTA_PRODUCER = '28c67deb49d694e992c005365cf19c73d1db31a89126f64dbe8b6973adba61cb'
SOURCES = [
    ('compact_v2','compact_geometry_v1',R/'results/arrival/propagation_v2',14),
    ('fullmask_v3','fullmask_geometry_v2',full.P,21),
    ('compact_delta_v1','compact_geometry_v1',D,14),
]


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def csv_write(path, data):
    names = list(dict.fromkeys(k for row in data for k in row))
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=names)
        writer.writeheader()
        writer.writerows(data)


def flag(value):
    return str(value).lower() == 'true'


def joint_rows():
    combined, inventory, source_records = [], [], []
    for name, geometry, directory, count in SOURCES:
        source = directory/'conditional_arrivals.csv'
        data = rows(source)
        assert len(data) == count
        assert all('join_source' not in row and 'source_geometry_family' not in row for row in data)
        source_records.append(dict(record(source),join_source=name,source_rows=count))
        combined.extend(dict(row,join_source=name,source_geometry_family=geometry) for row in data)
        byrun = {}
        for row in data:
            byrun.setdefault(row['run_id'],[]).append(row)
        for run_id, records in byrun.items():
            assert len(records) == 7 and len({x['target_id'] for x in records}) == 7
            keys = ['base_scenario_id','mechanism_id','original_upstream_model_id','analytic_onset_model_id','source_first_passage_status',
                    'source_evaluation_onset_status','original_evaluation_window_onset_status','analytic_evaluation_window_onset_status',
                    'source_history_risk_at_evaluation_start','evaluation_window_first_unstable_is_new_start','if_released_propagation',
                    'conditional_onset_lower_utc','conditional_onset_upper_utc','conditional_onset_interpolated_point_utc']
            for key in keys:
                assert len({x.get(key,'') for x in records}) == 1, (run_id,key)
            inventory.append(dict(join_source=name,source_geometry_family=geometry,run_id=run_id,
                                  **{key:records[0].get(key,'') for key in keys},target_records=7,
                                  independent_local_validation_events=0,probability_weight='',qualified_for_prediction=False,
                                  include_in_arrival_envelope=False,initiation_to_release_delay_seconds=''))
    assert len(combined) == 49 and len(inventory) == 7
    assert len({x['run_id'] for x in inventory}) == 7
    assert len({x['base_scenario_id'] for x in inventory}) == 4
    assert {x['mechanism_id'] for x in inventory} == {'S','S_T','S_H','S_T_H'}
    for row in combined:
        for key,value in row.items():
            if key.startswith(('absolute_arrival_','qualified_arrival_')) or key in ['arrival_probability','probability_weight','initiation_to_release_delay_seconds']:
                assert value == '', (row['run_id'],key,value)
        assert not flag(row['include_in_arrival_envelope']) and not flag(row['scientifically_qualified_for_prediction'])
        assert not flag(row['mass_conservation_qualified'])
        assert int(row['independent_local_validation_events']) == 0
        if row['source_first_passage_status'] == 'no_cross_observed_complete':
            assert flag(row['if_released_propagation']) and row['conditional_onset_lower_utc'] == ''
        if row['base_scenario_id'] == 'q2r3-p0255-S_T_H-linear':
            assert row['source_first_passage_status'] == 'point_crossing_linear_between_samples'
            assert row['source_evaluation_onset_status'] == 'left_censored_already_unstable'
            assert not flag(row['evaluation_window_first_unstable_is_new_start'])
    return combined,inventory,source_records


def snapshot():
    raw = subprocess.check_output(['git','ls-tree','-rz',BASE,'--',str(R.relative_to(ROOT))],cwd=ROOT)
    result = []
    for part in raw.split(b'\0'):
        if not part:
            continue
        head,path = part.decode().split('\t',1)
        _,kind,oid = head.split()
        p = ROOT/path
        data = p.read_bytes()
        assert kind == 'blob' and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == oid,path
        result.append(dict(record(p),git_blob_oid=oid))
    assert len(result) == 740
    return dict(source_commit=BASE,original_increment_base=START,files=result,
                scope='All prior Q3 round3 bytes including the newly frozen fullmask-v3 packet; no producer Git object is required for verification')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--verify-only',action='store_true')
    args = cli.parse_args()
    packets,approved = [],{}
    for name,path,pin,count in PACKETS:
        assert sha(path) == pin
        packet = read(path)
        assert len(packet['files']) == count
        packets.append((name,path,pin,packet))
        for f in packet['files']:
            if Path(f['path']).is_absolute():
                value = (f['bytes'],f['sha256'])
                assert f['path'] not in approved or approved[f['path']] == value
                approved[f['path']] = value
    assert len(approved) == 23
    for _,_,_,packet in packets:
        for f in packet['files']:
            full.target(f,approved)
    assert sha(PACKETS[-1][1].parent/'upstream_bundle.json') == DELTA_PRODUCER
    full_run = subprocess.run([sys.executable,str(R/'scripts/seal_fullmask_v3.py'),'--verify-only'],cwd=ROOT,capture_output=True,text=True)
    assert full_run.returncode == 0,full_run.stdout+full_run.stderr
    for _,_,directory,_ in SOURCES:
        validation = read(directory/'validation.json')
        assert validation['passed']
        for name in ['input_index','output_index']:
            index = directory/(name+'.json')
            assert sha(index) == validation[name+'_sha256']
            for f in read(index)['files']:
                full.target(f,approved)
    review = read(D/'review/final_review.json')
    assert review['passed']
    for f in review['inputs']:
        full.canonical(f,approved)
    qa = read(D/'figure_review.json')
    assert qa['passed'] and qa['figures']
    for f in qa['figures']:
        assert f['actually_opened'] and not Path(f['path']).is_absolute() and sha(ROOT/f['path']) == f['sha256']
    combined,inventory,source_records = joint_rows()
    if not args.verify_only:
        O.mkdir(parents=True,exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        write(O/'frozen_prior_files.json',snapshot())
        (O/'fullmask_v3_verification.log').write_text(full_run.stdout+full_run.stderr)
        csv_write(O/'conditional_arrivals_49.csv',combined)
        csv_write(O/'mapped_runs_7.csv',inventory)
        write(O/'summary.json',dict(generated_at_utc=now,mapped_runs=7,mechanical_designs=4,run_target_records=49,
              mechanisms=['S','S_T','S_H','S_T_H'],source_tables=source_records,independent_local_validation_events=0,
              probability_weights=None,qualified_arrival_rows=0,absolute_arrival_rows=0,arrival_probability_rows=0,
              selected_cases_are_2048_weighted_ensemble=False,initiation_to_release_lag='unknown',empirical_coverage=None,
              scientific_adoption='pending_team_review',physical_solver_rerun=False))
        merged = {}
        registration_count = 0

        def add(f,origin):
            nonlocal registration_count
            item = full.canonical(f,approved)
            key = item['path']
            if key not in merged:
                merged[key] = {k:item[k] for k in ['path','bytes','sha256']}
                merged[key].update(roles=[],registrations=[])
            entry = merged[key]
            assert (entry['bytes'],entry['sha256']) == (item['bytes'],item['sha256'])
            for role in item.get('roles',[item.get('role',origin.get('role','registered dependency'))]):
                if role not in entry['roles']:
                    entry['roles'].append(role)
            entry['registrations'].append(origin)
            registration_count += 1

        for name,path,pin,packet in packets:
            for i,f in enumerate(packet['files']):
                add(f,dict(bundle=str(path.relative_to(ROOT)),bundle_sha256=pin,row_index_0based=i))
            add(record(path),dict(source=name,role='pinned consumer packet'))
        indices=[full.O/'input_manifest.json',D/'input_index.json',D/'review/final_review.json',
                 SOURCES[0][2]/'input_index.json']
        for index in indices:
            data = read(index)
            for i,f in enumerate(data.get('files',data.get('inputs',[]))):
                add(f,dict(index=str(index.relative_to(ROOT)),index_sha256=sha(index),row_index_0based=i))
        for p in [D/'validation.json',D/'input_index.json',D/'output_index.json',D/'review/final_review.json',
                  full.O/'packet_validation.json',full.O/'output_manifest.json',R/'exports/fullmask_propagation_join_bundle_v3.json',
                  SOURCES[0][2]/'validation.json',SOURCES[0][2]/'output_index.json',Path(__file__).resolve(),
                  PACKETS[-1][1].parent/'upstream_bundle.json',*[directory/'conditional_arrivals.csv' for _,_,directory,_ in SOURCES]]:
            add(record(p),dict(source='final integration',role='exact frozen or reviewed source'))
        inputs=list(merged.values())
        write(O/'input_manifest.json',dict(generated_at_utc=now,files=inputs,unique_file_count=len(inputs),registration_count=registration_count,
              duplicate_registration_count=registration_count-len(inputs),approved_unique_cache_files=23,
              normalization_scope='Repository-relative paths; exact cache allowlist only. Merge canonical path with identical bytes/SHA; preserve all roles and index/bundle row provenance. Never extract historical source_path/upstream_path as a new read.',
              source_base_commit=BASE,original_increment_base=START,physics_rerun=False))
        bundle_files=[p for p in sorted(D.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.log']
        bundle_files += [O/'conditional_arrivals_49.csv',O/'mapped_runs_7.csv',O/'summary.json',O/'input_manifest.json',O/'frozen_prior_files.json',R/'FINAL_PROPAGATION_HANDOFF.md',R/'exports/fullmask_propagation_join_bundle_v3.json']
        write(BUNDLE,dict(bundle_version='q3-r3-final-propagation-v4',producer_question='q3',created_at_utc=now,
              files=[dict(record(p),role=str(p.relative_to(R))) for p in bundle_files],source_base_commit=BASE,original_increment_base=START,
              mapped_runs=7,mechanical_designs=4,run_target_records=49,local_truth_events_added=0,empirical_coverage=None,
              physics_rerun=False,accepted_arrival_envelope_runs=[],arrival_probability=None,absolute_arrival=None,
              limitations=['Selected mapped runs are not independent events or the2048-weighted forecast ensemble',
                          'Unknown initiation-to-bulk-release delay; qualified arrivals and probabilities remain null',
                          'Global mechanical crossing and evaluation-window left censoring are separate states',
                          'No forced join of general Q4 scenarios without a Q2 parent identity']))
        exclude={O/'output_manifest.json',O/'packet_validation.json'}
        directories=[D,O,PACKETS[-1][1].parent]
        paths=[p for folder in directories for p in folder.rglob('*') if p.is_file() and p not in exclude and '__pycache__' not in p.parts]
        paths += [BUNDLE,R/'FINAL_PROPAGATION_HANDOFF.md',R/'scripts/join_compact_delta_v1.py',Path(__file__).resolve()]
        paths += [full.target(f,approved) for f in read(full.O/'output_manifest.json')['files']]
        paths += [full.O/'output_manifest.json',full.O/'packet_validation.json']
        write(O/'output_manifest.json',dict(generated_at_utc=now,original_increment_base=START,frozen_fullmask_commit=BASE,
              files=[record(p) for p in sorted(set(paths))],scope='Complete additions since original increment base, including immutable fullmask outputs plus compact delta and final metadata',
              excluded={'output_manifest.json':'self reference','packet_validation.json':'avoid cycle','__pycache__':'transient bytecode'}))
        checks=dict(all_153_approved_registrations_verified=True,seven_runs_four_designs_49_rows=True,all_source_columns_retained=True,
              no_qualified_arrival_absolute_or_probability=True,delta_consumer_checks=read(D/'validation.json')['passed'],delta_independent_review=review['passed'],
              fullmask_packet_offline_verification=True,prior_740_tracked_files_preserved=True,unique_portable_master_inputs=True,delta_final_figure_opened=True)
        write(O/'packet_validation.json',dict(generated_at_utc=now,passed=all(checks.values()),checks=checks,input_manifest_sha256=sha(O/'input_manifest.json'),
              output_manifest_sha256=sha(O/'output_manifest.json'),frozen_prior_manifest_sha256=sha(O/'frozen_prior_files.json'),bundle_sha256=sha(BUNDLE),
              source_base_commit=BASE,original_increment_base=START,physics_rerun=False))
    packet = read(O/'packet_validation.json')
    assert packet['passed'] and all(packet['checks'].values())
    for key,p in [('input_manifest_sha256',O/'input_manifest.json'),('output_manifest_sha256',O/'output_manifest.json'),('frozen_prior_manifest_sha256',O/'frozen_prior_files.json'),('bundle_sha256',BUNDLE)]:
        assert sha(p) == packet[key]
    for path in [O/'input_manifest.json',O/'output_manifest.json',O/'frozen_prior_files.json',BUNDLE]:
        full.check_unique(read(path)['files'],approved)
    projected=rows(O/'conditional_arrivals_49.csv')
    assert len(projected) == len(combined)
    for source,actual in zip(combined,projected):
        assert all(actual[key] == value for key,value in source.items())
    assert rows(O/'mapped_runs_7.csv') == [{key:str(value) for key,value in row.items()} for row in inventory]
    master=read(O/'input_manifest.json')
    assert master['unique_file_count'] == len(master['files'])
    assert master['registration_count'] == sum(len(f['registrations']) for f in master['files'])
    print(full.json.dumps(dict(passed=True,mode='verify_only' if args.verify_only else 'seal_final_increment',mapped_runs=7,mechanical_designs=4,target_rows=49,
               unique_inputs=len(master['files']),input_manifest_sha256=sha(O/'input_manifest.json'),output_manifest_sha256=sha(O/'output_manifest.json'),bundle_sha256=sha(BUNDLE))))


if __name__ == '__main__':
    main()
