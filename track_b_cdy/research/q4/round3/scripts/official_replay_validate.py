#!/usr/bin/env python3
"""Validate every saved-control replay plan without running any native solver."""
from pathlib import Path
import datetime, hashlib, json, subprocess, sys

P = Path(__file__).resolve().parents[1]
C = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official')
INDEX = P / 'results/official_native_control_index.json'
SCRIPT = P / 'scripts/official_replay_native.py'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

rows = []
for record in json.loads(INDEX.read_text())['runs']:
    out = C / 'replays' / ('validation_only_' + record['run_id'])
    assert not out.exists()
    cmd = [sys.executable, str(SCRIPT), '--run-id', record['run_id'], '--output-dir', str(out)]
    plan = json.loads(subprocess.check_output(cmd))
    subprocess.run(['bash', '-n'], input=plan['command'][-1].encode(), check=True)
    assert not out.exists() and not plan['executed']
    rows.append({'run_id': record['run_id'], 'description_command': cmd,
                 'inputs_and_control_hashes_verified': True, 'shell_syntax_checked': True,
                 'output_directory_not_created': True, 'native_replay_executed': False,
                 'fixed_addon': plan['resourcefix_readonly_addon_used'],
                 'readonly_evidence_mounts': plan['readonly_evidence_mounts']})
output = {'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'control_index_sha256': sha(INDEX), 'replay_script_sha256': sha(SCRIPT),
          'checked_run_count': len(rows), 'checks': rows,
          'scope': 'plan/identity/input/control hashes and shell syntax only; no extra native solver run',
          'regression': 'ravaflow mount and script use actual top-level run_grass.sh, not archived attempts or stale expanded parameter paths',
          'physics_accuracy_or_replay_execution_qualified': False}
(P / 'results/official_replay_validation.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({'plans_checked': len(rows), 'native_replays_executed': 0}))
