#!/usr/bin/env python3
"""Describe, or replay, saved native controls in a new directory; never overwrite evidence."""
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, subprocess, shlex

P = Path(__file__).resolve().parents[1]
C = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
RT = C.parents[1] / 'runtime'
BASE = 'sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29'
FIXBIN = '45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c'
RAVABIN = '7b1a7b0da5cd7ec858ac5d6c2332e424f95fd78fac760c535dd77de161b28931'
DCLAWBIN = 'e63b50048d871840e0ef42b4b440fcbd7751ddf2c6d7e45fc1e008e6935db3b9'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--execute', action='store_true', help='Without this flag, only describe the verified replay.')
    a = ap.parse_args()
    index = P / 'results/official_native_control_index.json'
    record = next(x for x in json.loads(index.read_text())['runs'] if x['run_id'] == a.run_id)
    source = C / 'runs' / a.run_id
    assert source.resolve().parent == (C / 'runs').resolve()
    assert sha(source / 'execution.json') == record['execution_sha256']
    assert sha(source / 'case.json') == record['case_sha256']
    assert sha(source / 'run.log') == record['log_sha256']
    for control in record['native_input_controls']:
        assert sha(control['path']) == control['sha256']
    case = json.loads((source / 'case.json').read_text())
    for key in ['dem', 'release', 'erodible_bed']:
        if case.get(key):
            assert sha(case[key]) == case[key + '_sha256']
    ex = json.loads((source / 'execution.json').read_text())
    fixed = ex.get('solver_build') == 'explicit_resourcefix_build' or a.run_id.endswith('__resourcefix')
    out = Path(a.output_dir).resolve()
    assert out.is_relative_to((C / 'replays').resolve()), 'Replay output must be in the owned cache/replays directory.'
    if out.exists():
        raise FileExistsError('Replay directory already exists; choose a new directory.')
    # Expanded ravaflow param files can retain an older wrapper path.  Only the
    # actual shell input imports, or DClaw's executed data files, select a mount.
    path_controls = [x for x in record['native_input_controls']
                     if Path(x['path']).parent == source
                     and (Path(x['path']).suffix == '.data' if case['model'] == 'dclaw'
                          else Path(x['path']).name == 'run_grass.sh')]
    early_prefix = any(b'/work/q4/official/' in Path(x['path']).read_bytes() for x in path_controls)
    work_root = '/work/q4/official' if early_prefix else '/work'
    cmd = ['docker', 'run', '--rm', '--cpus', '1', '-e', 'OMP_NUM_THREADS=3',
           '-e', 'CLAW=/opt/clawpack', '-e', 'PYTHONPATH=/opt/clawpack', '-e', 'MPLBACKEND=Agg',
           '-v', str(C) + ':' + work_root + ':ro',
           '-v', str(out) + ':/replay', '-w', '/replay']
    if case['model'] == 'dclaw':
        files = [x for x in record['native_input_controls'] if Path(x['path']).parent == source]
        assert any(Path(x['path']).name == 'xdclaw' and x['sha256'] == DCLAWBIN for x in files)
        script = 'set -e; test "$(sha256sum ./xdclaw | cut -d\" \" -f1)" = ' + DCLAWBIN + '; ./xdclaw'
    else:
        files = [x for x in path_controls if Path(x['path']).name == 'run_grass.sh']
        assert len(files) == 1
        addon = '/resourcefix' if fixed else '/opt/grass-addons'
        cmd += ['-e', 'GRASS_ADDON_BASE=' + addon]
        if fixed:
            cmd += ['-v', str(RT / 'diagnostics/q4_native_asan/derived/release_addon') + ':/resourcefix:ro']
        expected = FIXBIN if fixed else RAVABIN
        # Include GRASS's addon bin in the check before starting a fresh location.
        dem = work_root + '/' + case['dem'].split('/q4/official/', 1)[1]
        script = ('set -e; test "$(sha256sum ' + addon + '/bin/r.avaflow.main | cut -d\" \" -f1)" = '
                  + expected + '; grass --tmp-location ' + shlex.quote(dem) + ' --exec bash /replay/run_grass.sh')
    cmd += [BASE, 'bash', '-lc', script]
    plan = {'run_id': a.run_id, 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_control_index_path': str(index), 'source_control_index_sha256': sha(index),
            'source_execution_sha256': record['execution_sha256'], 'command': cmd,
            'replay_image_id': BASE, 'historical_execution_image_id': ex.get('image_id'),
            'historical_adapter_identity_status': record['historical_adapter_identity_status'],
            'replay_scope': 'native saved controls and inputs; no reconstruction of missing historical Python adapter',
            'readonly_evidence_mounts': [work_root],
            'resourcefix_readonly_addon_used': fixed, 'copied_controls': files,
            'output_dir': str(out), 'executed': a.execute}
    if not a.execute:
        print(json.dumps(plan, indent=2)); return
    out.mkdir(parents=True)
    for control in files:
        shutil.copy2(control['path'], out / Path(control['path']).name)
    (out / 'replay_plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    with (out / 'replay.log').open('w') as log:
        result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    (out / 'replay_result.json').write_text(json.dumps({'returncode': result.returncode,
        'plan_sha256': sha(out / 'replay_plan.json'), 'log_sha256': sha(out / 'replay.log'),
        'execution_success_is_not_accuracy_qualification': True}, indent=2) + '\n')
    raise SystemExit(result.returncode)

if __name__ == '__main__':
    main()
