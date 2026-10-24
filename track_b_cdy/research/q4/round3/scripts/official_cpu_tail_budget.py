#!/usr/bin/env python3
"""After every required case has started, share <=6 CPU quota among its tail containers."""
from pathlib import Path
import datetime, hashlib, json, subprocess, time
from official_catalogue import registered_cases, applicability, EXCLUDED, PENDING, DIAGNOSTIC

P = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29'
OUT = P / 'results/official_scheduling_cpu_tail_receipts_08.json'
state = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'authority': 'parent/root explicit tail redistribution instruction',
         'scope': 'HostConfig CPU quota only; no restart/OMPenv/input/physics/execution metadata changes',
         'total_nano_cpu_budget': 6000000000, 'per_container_max_nano_cpus': 3000000000,
         'protocol': 'config/official_cpu_tail_budget_protocol_08.json', 'actions': []}

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def save():
    OUT.write_text(json.dumps(state, indent=2) + '\n')

def closed(item):
    f = Path(item['case']).parent
    e, log = f / 'execution.json', f / 'run.log'
    return e.exists() and log.exists() and json.loads(e.read_text()).get('log_sha256') == hashlib.sha256(log.read_bytes()).hexdigest()

while True:
    decisions = applicability()
    items = [x for x in registered_cases() if decisions.get(x['run_id'], {}).get('decision', 'required') not in EXCLUDED | PENDING]
    unfinished = [x for x in items if not closed(x)]
    pending = [x['run_id'] for x in unfinished if not (Path(x['case']).parent / 'run.log').exists()]
    ids = subprocess.check_output(['docker', 'ps', '-q', '--filter', 'ancestor=' + IMAGE]).decode().split()
    active = []
    known = {x['run_id'] for x in items}
    for cid in ids:
        r = subprocess.run(['docker', 'inspect', cid], capture_output=True, text=True)
        if r.returncode:
            continue
        d = json.loads(r.stdout)[0]
        wd = d['Config']['WorkingDir']
        rid = wd.rsplit('/', 1)[-1]
        if wd.startswith('/work/runs/') and rid in known:
            active.append({'container_id': d['Id'], 'run_id': rid,
                           'nano_cpus': d['HostConfig']['NanoCpus'],
                           'omp_env': [x for x in d['Config']['Env'] if x.startswith('OMP_NUM_THREADS=')]})
    active_ids = {x['run_id'] for x in active}
    # A just-created run.log does not prove its container exists yet.  Hold
    # quotas unless every unclosed case is represented by an active container.
    missing = sorted({x['run_id'] for x in unfinished} - active_ids)
    eligible = not pending and not missing
    state['latest_observation'] = {'utc': now(), 'pending_run_ids': pending,
        'unfinished_run_ids': [x['run_id'] for x in unfinished], 'active_containers': active,
        'unclosed_without_active_container': missing, 'tail_redistribution_eligible': eligible}
    if eligible and active:
        target = min(3000000000, 6000000000 // len(active))
        assert target * len(active) <= 6000000000
        for record in active:
            if record['nano_cpus'] == target:
                continue
            action = {'started_utc': now(), 'container_id': record['container_id'],
                      'run_id': record['run_id'], 'active_count_at_decision': len(active),
                      'before_nano_cpus': record['nano_cpus'], 'requested_nano_cpus': target,
                      'omp_env_preserved': record['omp_env'], 'pending_run_count': 0,
                      'command': ['docker', 'update', '--cpus', format(target / 1e9, '.9f'), record['container_id']]}
            state['actions'].append(action); save()
            update = subprocess.run(action['command'], capture_output=True, text=True)
            action.update({'finished_utc': now(), 'returncode': update.returncode,
                           'stdout': update.stdout.strip(), 'stderr': update.stderr.strip()})
            if not update.returncode:
                result = subprocess.run(['docker', 'inspect', record['container_id']], capture_output=True, text=True)
                if not result.returncode:
                    action['after_nano_cpus'] = json.loads(result.stdout)[0]['HostConfig']['NanoCpus']
                    assert action['after_nano_cpus'] == target
            save(); print(json.dumps(action), flush=True)
    save()
    if not unfinished and not active:
        state['finished_utc'] = now(); state['all_registered_required_and_diagnostic_closed'] = True; save(); break
    time.sleep(30)
