#!/usr/bin/env python3
"""Render every selected PDF page and contact sheets. AI-assisted: OpenAI Codex / GPT-6 family, OpenAI, 2026-10-24."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
from PIL import Image,ImageOps,ImageDraw
PAPER=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--pdf',type=Path,required=True)
parser.add_argument('--tag',required=True)
parser.add_argument('--dpi',type=int,default=85)
parser.add_argument('--first-page',type=int,default=1)
parser.add_argument('--last-page',type=int)
args=parser.parse_args()
pdf=args.pdf.resolve()
pages=PAPER/'qa/pages'/args.tag
sheets=PAPER/'qa/contact_sheets'
pages.mkdir(parents=True,exist_ok=True);sheets.mkdir(parents=True,exist_ok=True)
for old in pages.glob('page-*.png'):old.unlink()
for old in sheets.glob(args.tag+'-*.jpg'):old.unlink()
tool=shutil.which('pdftoppm')
if not tool:raise SystemExit('pdftoppm is required for rendering')
cmd=[tool,'-r',str(args.dpi),'-f',str(args.first_page)]
if args.last_page:cmd+=['-l',str(args.last_page)]
cmd+=['-png',str(pdf),str(pages/'page')]
subprocess.run(cmd,check=True)
images=sorted(pages.glob('page-*.png'))
contacts=[]
for start in range(0,len(images),12):
    group=images[start:start+12]
    canvas=Image.new('RGB',(1080,1560),'#d8d8d8')
    draw=ImageDraw.Draw(canvas)
    for j,fp in enumerate(group):
        im=Image.open(fp).convert('RGB')
        im.thumbnail((340,480))
        x=(j%3)*360+10;y=(j//3)*390+23
        im.thumbnail((340,360))
        canvas.paste(im,(x+(340-im.width)//2,y))
        draw.text((x,y-17),args.tag+' / '+fp.stem,fill='black')
    out=sheets/f'{args.tag}-{start//12+1:03d}.jpg'
    canvas.save(out,quality=88)
    contacts.append(str(out.relative_to(PAPER)))
report={'pdf':str(pdf.relative_to(PAPER)),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'dpi':args.dpi,'first_page':args.first_page,'last_page_requested':args.last_page,'page_images':len(images),'contact_sheets':contacts,'review_status':'rendered_for_visual_inspection'}
(PAPER/'qa'/f'render_{args.tag}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
