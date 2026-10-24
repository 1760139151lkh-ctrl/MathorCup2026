#!/usr/bin/env python3
"""Replay frozen reduced-model code into NEW packet/cache directories only."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys

R = Path(__file__).resolve().parents[1]
CACHE_ROOT = Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/replays')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='NEW relative directory inside this round3')
    parser.add_argument('--cache-name', required=True, help='NEW one-component q4/replays cache name')
    parser.add_argument('--mode', choices=['all', '1d', '2d', 'benchmarks'], default='all')
    parser.add_argument('--select', default='all')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    destination = (R/args.output).resolve()
    assert destination.is_relative_to(R) and not destination.exists()
    assert Path(args.cache_name).name == args.cache_name and args.cache_name not in ['', '.', '..']
    cache = CACHE_ROOT/args.cache_name
    assert not cache.exists()
    cache.mkdir(parents=True)
    for sub in ['results', 'config', 'figures']:
        (destination/sub).mkdir(parents=True, exist_ok=True)
    inputs = ['results/spatial_inputs_60m.npz', 'results/spatial_inputs_120m.npz',
              'results/spatial_paths.csv', 'config/additional_target_protocol_v2.json',
              'config/reduced_protocol.json', 'config/reduced_environment.json',
              'config/reduced_environment.lock', 'config/reduced_protocol_amendment01.json']
    copied = []
    for rel in inputs:
        source, target = R/rel, destination/rel
        shutil.copy2(source, target)
        assert sha(source) == sha(target)
        copied.append({'source': str(source), 'copy': str(target), 'sha256': sha(source)})
    # Reproduce the exact read-time schema used by the frozen 170-row target table.
    source = R/'results/spatial_targets_v2_initial.csv'
    target = destination/'results/spatial_targets_v2.csv'
    shutil.copy2(source, target)
    assert sha(target) == '96202126426c50fdebe5d72ddf74bd443f531a77c77db094d0c8fe739dc86b98'
    copied.append({'source': str(source), 'copy': str(target), 'sha256': sha(source)})
    record = {'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
              'source_code_unchanged': True, 'original_output_paths_untouched': True,
              'packet_destination': str(destination), 'cache_destination': str(cache),
              'copied_inputs': copied, 'mode': args.mode, 'select': args.select,
              'source_code_sha256': {name: sha(R/'scripts'/name) for name in
                                     ['reduced_solver.py', 'reduced_region.py', 'reduced_benchmarks.py', 'reduced_report.py']},
              'prepare_only': args.prepare_only, 'scientific_execution_complete': False}
    log = destination/'replay_record.json'
    log.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    if args.prepare_only:
        print(json.dumps({'prepared_only': True, 'inputs_verified': len(copied), 'original_outputs_untouched': True}))
        return
    os.environ['NUMBA_CACHE_DIR'] = str(cache/'numba_cache')
    sys.path.insert(0, str(R/'scripts'))
    if args.mode == 'benchmarks':
        module = importlib.import_module('reduced_benchmarks')
        module.R = destination
        module.main()
    else:
        module = importlib.import_module('reduced_region')
        module.R, module.C = destination, cache/'regional'
        sys.argv = [str(R/'scripts/reduced_region.py'), '--mode', args.mode, '--select', args.select]
        module.main()
        # The report can run on selected subsets; no original file is overwritten.
        module = importlib.import_module('reduced_report')
        module.R = destination
        module.main()
    record['scientific_execution_complete'] = True
    record['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    log.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'replay_completed': True, 'packet': str(destination), 'cache': str(cache)}))


if __name__ == '__main__':
    main()
