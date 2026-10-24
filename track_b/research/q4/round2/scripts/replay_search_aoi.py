#!/usr/bin/env python3
"""Reproduce the adopted AOI in a new output directory, preserving early bytes."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[5]
R=ROOT/'track_b/research/q4/round2'


def main():
    if len(sys.argv)!=2:
        raise SystemExit('Supply a NEW output directory inside this question round2, e.g. results/replay_check')
    destination=(R/sys.argv[1]).resolve()
    if not destination.is_relative_to(R) or destination.exists():
        raise SystemExit('Output must be new and inside q4/round2; existing adopted artifacts are never overwritten')
    (destination/'config').mkdir(parents=True)
    (destination/'results').mkdir()
    shutil.copy2(R/'config/map_digitisation.json',destination/'config/map_digitisation.json')
    for name in ('workspace_binding.json','workspace_verification.json'):
        shutil.copy2(R/name,destination/name)
    source=R/'scripts/build_search_aoi.py'
    spec=importlib.util.spec_from_file_location('original_search_builder',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.R=destination
    module.main()
    original=(R/'results/search_aoi.geojson').read_bytes()
    reproduced=(destination/'results/search_aoi.geojson').read_bytes()
    assert original==reproduced,'Reproduced geometry differs from the adopted early AOI'
    report={'adopted_geometry_bytes_reproduced':True,'early_artifacts_modified':False,
            'reproduction_directory':str(destination.relative_to(R)),
            'evidence_timestamp_note':'Reproduced evidence has a new generation time and is not a new approval or replacement of the early evidence.'}
    (destination/'replay_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
