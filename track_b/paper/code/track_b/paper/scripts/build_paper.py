#!/usr/bin/env python3
"""Rebuild the paper from existing frozen research results. AI-assisted: OpenAI Codex / GPT-6 family, OpenAI, 2026-10-24."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys
PAPER=Path(__file__).resolve().parents[1]
REPO=PAPER.parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--render',action='store_true')
args=parser.parse_args()
def run(command,cwd=REPO,log=None):
    if log:
        with log.open('w') as f:r=subprocess.run(command,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        if r.returncode:
            print(log.read_text(errors='replace')[-5000:])
            raise SystemExit(r.returncode)
    else:subprocess.run(command,cwd=cwd,check=True)
for script,tail in [('build_supplement_tables.py',[]),('build_evidence.py',['--require-all']),('build_references.py',[]),('build_program_appendix.py',[])]:
    run([sys.executable,'-B',str(PAPER/'scripts'/script),*tail])
latexmk=shutil.which('latexmk')
if not latexmk:raise SystemExit('latexmk / XeLaTeX required')
for stem,sub in [('main','main'),('ai_details','ai')]:
    work=PAPER/'build'/sub;work.mkdir(parents=True,exist_ok=True)
    run([latexmk,'-xelatex','-interaction=nonstopmode','-halt-on-error',f'-outdir=build/{sub}',f'{stem}.tex'],cwd=PAPER,log=work/'latexmk_console.log')
run([sys.executable,'-B',str(PAPER/'scripts/verify_paper.py'),'--pdf',str(PAPER/'build/main/main.pdf')])
output=PAPER/'output';output.mkdir(exist_ok=True)
shutil.copyfile(PAPER/'build/main/main.pdf',output/'赛道B论文初稿.pdf')
shutil.copyfile(PAPER/'build/ai/ai_details.pdf',output/'AI工具使用详情说明.pdf')
if args.render:
    run([sys.executable,'-B',str(PAPER/'scripts/render_qa.py'),'--pdf',str(PAPER/'build/main/main.pdf'),'--tag','main','--dpi','70'])
    run([sys.executable,'-B',str(PAPER/'scripts/render_qa.py'),'--pdf',str(PAPER/'build/ai/ai_details.pdf'),'--tag','ai','--dpi','100'])
print(json.dumps({'paper':str(output/'赛道B论文初稿.pdf'),'ai_details':str(output/'AI工具使用详情说明.pdf'),'model_rerun':False},ensure_ascii=False))
