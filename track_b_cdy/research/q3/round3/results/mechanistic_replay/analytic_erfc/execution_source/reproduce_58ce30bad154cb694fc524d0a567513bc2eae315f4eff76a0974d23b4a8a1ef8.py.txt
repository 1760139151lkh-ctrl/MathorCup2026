#!/usr/bin/env python3
"""Recompute into a fresh child directory while preserving released bytes."""
import argparse,json,types
from datetime import datetime,timezone
from pathlib import Path

SOURCE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir',required=True,help='Fresh directory inside analytic_erfc; workspace-relative or absolute')
args=parser.parse_args()
target=Path(args.output_dir).resolve()
assert target.is_relative_to(SOURCE) and target!=SOURCE and not target.exists()
target.mkdir(parents=True)
replay=types.ModuleType('analytic_reproduction');replay.__file__=str(SOURCE/'replay.py')
exec(compile((SOURCE/'replay.py').read_text(),str(SOURCE/'replay.py'),'exec'),replay.__dict__)
replay.HERE=target;replay.main()
post=types.ModuleType('analytic_reproduction_postprocess');post.__file__=str(SOURCE/'postprocess.py')
exec(compile((SOURCE/'postprocess.py').read_text(),str(SOURCE/'postprocess.py'),'exec'),post.__dict__)
post.HERE=target;post.main()
summary=json.loads((target/'summary.json').read_text())
launcher=Path(__file__).resolve()
for path,label in [(launcher,'reproduction_launcher'),(SOURCE/'postprocess.py','independent_postprocess')]:
    snapshot=target/'execution_source'/(label+'_'+replay.sha(path)+'.py.txt')
    snapshot.write_bytes(path.read_bytes())
    summary['inputs'].append(dict(path=str(snapshot.relative_to(replay.ROOT)),bytes=snapshot.stat().st_size,sha256=replay.sha(snapshot)))
summary['actual_command']='track_b/.venv/bin/python '+str(launcher.relative_to(replay.ROOT))+' --output-dir '+str(target.relative_to(replay.ROOT))
replay.fd.dump(target/'summary.json',summary)
replay.fd.audit_exports(target)
files=[p for p in target.rglob('*') if p.is_file() and p.name not in ['delivery_index.json','run.stdout.log']]
replay.fd.dump(target/'delivery_index.json',dict(experiment_id=replay.EXPERIMENT,generated_at_utc=replay.fd.stamp(datetime.now(timezone.utc)),
  upstream_bundle_sha256=replay.BUNDLE_HASH,prior_FD_delivery_index_sha256=replay.FD_INDEX_HASH,
  files=[dict(path=str(p.relative_to(replay.ROOT)),bytes=p.stat().st_size,sha256=replay.sha(p)) for p in sorted(files)]))
print(json.dumps(dict(status='reproduction_complete',output=str(target),delivery_index_sha256=replay.sha(target/'delivery_index.json'))))
