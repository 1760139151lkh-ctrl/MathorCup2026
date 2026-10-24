#!/usr/bin/env python3
"""Verify paper-level evidence, numbering, numerical transcriptions and scope."""
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
P = ROOT/'track_b/paper'
checks = []

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(name):
    return json.loads((P/'evidence'/name).read_text())

def check(name, condition, detail=None):
    checks.append({'name':name, 'passed':bool(condition), 'detail':detail})

def bound(entry):
    path=Path(entry['path']);path=path if path.is_absolute() else ROOT/path
    return path.is_file() and sha(path)==entry['sha256']

def owned(path):
    prefix='track_b/paper/'
    if not path.startswith(prefix):return False
    path=path[len(prefix):]
    return path in ['sections/q4.tex','tasks/q4_HANDOFF.md'] or path.startswith(('figures/q4/','scripts/q4_','evidence/q4_'))

def main():
    tex=(P/'sections/q4.tex').read_text(); refs=(P/'evidence/q4_references.tex').read_text()
    labels=re.findall(r'\\label\{([^}]+)\}',tex)
    cites={key for item in re.findall(r'\\cite\{([^}]+)\}',tex) for key in item.split(',')}
    bib=re.findall(r'\\bibitem\{([^}]+)\}',refs)
    check('all_labels_and_cites_q4_namespace',all(x.startswith('q4-') for x in labels+list(cites)))
    check('unique_labels_and_citation_keys',len(labels)==len(set(labels)) and len(bib)==len(set(bib)))
    check('all_and_only_five_actual_references',cites==set(bib) and len(bib)==5)
    check('section_uses_shared_macros',tex.count('\\AIcredit')==1 and '\\documentclass' not in tex and '\\usepackage' not in tex)
    count=sum('\u4e00'<=c<='\u9fff' for c in tex)
    check('requested_chinese_text_density',2500<=count<=3500,count)
    check('two_figures_three_tables_three_equations',tex.count('\\begin{figure}')==2 and tex.count('\\begin{table}')==3 and tex.count('\\begin{equation}')==3)
    check('no_placeholders_or_repeated_audit_phrases',not any(x in tex for x in ['待核','TODO','尚未验证','未达到','未实现','资格未接受']))
    claims=read('q4_claims.json')
    required={'claim_id','statement','value','unit','source_files','model_id','scenario_id','scope','paper_anchor'}
    check('claim_schema_unique_ids_and_actual_anchors',all(required<=c.keys() and c['paper_anchor'] in labels for c in claims) and len({c['claim_id'] for c in claims})==len(claims),len(claims))
    sources=[f for c in claims for f in c['source_files']]
    check('claim_sources_repo_relative',all(not Path(f['path']).is_absolute() for f in sources))
    check('all_claim_source_bytes_match',all(bound(f) for f in sources),len({f['path'] for f in sources}))
    catalogue=read('q4_code_files.json')
    code=catalogue['self_authored_files']+catalogue['paper_plotting_files']
    check('self_authored_code_and_plot_hashes',all(bound(f) and not f['is_third_party_solver_source'] for f in code))
    numeric=read('q4_numeric_review.json');plot=read('q4_plot_manifest.json')
    check('native_arrays_readonly_byte_bindings',all(bound(f) for f in numeric['array_sources']),len(numeric['array_sources']))
    check('figure_files_hash_bindings',all(bound(f) for f in plot['outputs']))
    stage=next(c for c in claims if c['claim_id']=='q4-main-process-stage-frames')['value']
    check('actual_process_times_and_areas',all(abs(a['actual_saved_seconds']-b['actual_time_s'])<1e-9 and abs(a['instant_wet_area_hge0p1_m2']/1e6-b['wet_planar_area_km2'])<1e-9 for a,b in zip(stage,plot['main_process_frames'])) and len(stage)==len(plot['main_process_frames'])==4)
    mapping=next(c for c in claims if c['claim_id']=='q4-q2-seven-runs-four-designs')['value']['designs']
    check('seven_runs_four_designs_49_targets_zero_free_water',len(mapping)==7 and len({x['base_scenario_id'] for x in mapping})==4 and sum(len(x['target_responses']) for x in mapping)==49 and all(x['free_water_volume_fraction']==0 for x in mapping))
    rows=[('ST全源面／120 m','q2full_q2r3_p0036_S_T_linear__geomv2_120m__sf0'),('ST全源面／60 m','q2full_q2r3_p0036_S_T_linear__geomv2_60m__sf0'),('D-Claw扩域／120 m','dclaw_ref_extended120'),('复合固水／120 m','composite_RI_water_120__sf0')]
    matches=[]
    for label,rid in rows:
        data=numeric['runs'][rid]['within_requested_horizon']
        expected='&'+f"{data['maximum_saved_depth_m']:.3f}&{data['maximum_saved_horizontal_speed_hge0p1_m_s']:.3f}&{data['cumulative_saved_footprint_hge0p1_m2']/1e6:.4f}"+'&'
        line=next(line for line in tex.splitlines() if line.split('&',1)[0].strip()==label)
        matches.append(expected in line)
    check('representative_table_transcription',all(matches),matches)
    check('relative_release_unknown_and_zero_local_event_meanings',plot['time_origin']=='given bulk release' and plot['initiation_to_release_delay_seconds'] is None and plot['independent_local_event_validation_count']==0 and plot['physical_model_runs_added']==0)
    log=(P/'figures/q4/preview/q4_compile_pass2.txt').read_text()
    check('xelatex_no_overflow_or_unresolved_references','Output written on' in log and not re.search(r'Overfull|undefined|LaTeX Error|fontspec Error',log))
    qa=read('q4_visual_review.json')
    check('final_actual_visual_review',qa['status']=='final_actual_image_review' and all(x['actual_opened'] and bound(x) for x in qa['pages']) and bound(qa['preview_pdf']) and all(bound(x) for x in qa['figure_reviews']))
    check('preview_body_and_reference_density',qa['body_page_count']==4 and qa['references_preview_page_count']==1 and len(qa['pages'])==5)
    files=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).splitlines()+subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    check('only_owned_paper_files_changed',all(owned(path) for path in files),[path for path in files if not owned(path)])
    for path in sorted((P/'scripts').glob('q4_*.py')):
        ast.parse(path.read_text())
    check('python_sources_parse',True)
    output={'schema_version':'q4-paper-validation-v1','validated_at_utc':datetime.now(timezone.utc).isoformat(),'passed':all(c['passed'] for c in checks),'checks':checks,'check_count':len(checks),'chinese_character_count':count,'physical_model_runs_added':0,'human_scientific_scope':'Paper transcriptions and artifacts checked against frozen study; original relative release/scenario meaning retained.','file_bindings':[{'path':str(path.relative_to(ROOT)),'sha256':sha(path)} for path in [P/'sections/q4.tex',P/'evidence/q4_claims.json',P/'evidence/q4_code_files.json',P/'evidence/q4_references.tex',P/'evidence/q4_plot_manifest.json',P/'evidence/q4_visual_review.json',P/'tasks/q4_HANDOFF.md',Path(__file__)]]}
    (P/'evidence/q4_validation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':output['passed'],'checks':len(checks),'failed':[c for c in checks if not c['passed']]},ensure_ascii=False))
    raise SystemExit(0 if output['passed'] else 1)

if __name__=='__main__':main()
