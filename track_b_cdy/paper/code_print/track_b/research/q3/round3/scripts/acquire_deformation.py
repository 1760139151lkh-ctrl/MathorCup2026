#!/usr/bin/env python3
"""Bounded public source acquisition + offline canonical deformation extraction.
Raw original archives stay in the Q3-owned cache. No upstream code is executed.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,io,json,re,subprocess,urllib.request,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
R=Path(__file__).resolve().parents[1]
CACHE=Path('<LOCAL_HOME>/Documents/MathorCup/research_cache/round3/q3/deformation')
OUT=R/'inputs/deformation'
UTC=dt.timezone.utc
PFTF_COMMIT='63a83e2da5c7a9c37382eef68be1b44963cd0af3'
URLS={
 'PFTF_real_collection.zip':'https://dataserv.ub.tum.de/public.php/dav/files/m1688868/?accept=zip',
 'brienz_tps.xlsx':'https://research-collection.ethz.ch/server/api/core/bitstreams/af4072e8-e0a4-4446-bedf-f90aad4c8783/content',
 'brienz_readme.pdf':'https://research-collection.ethz.ch/server/api/core/bitstreams/fb26c12d-b285-4288-ab55-07c153954101/content',
 'eth_item.json':'https://research-collection.ethz.ch/server/api/core/items/71f80c84-731a-4486-a529-47f3ef0b37dd',
 'brienz_primary_article.html':'https://link.springer.com/article/10.1007/s10346-024-02380-z',
 'veslemannen_primary_article.html':'https://link.springer.com/article/10.1007/s10346-020-01609-x',
 'Veslemannen_ESM6.txt':'https://static-content.springer.com/esm/art%3A10.1007%2Fs10346-020-01609-x/MediaObjects/10346_2020_1609_MOESM6_ESM.txt',
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def fetch(name,url):
 p=CACHE/name
 if p.exists():return
 start=dt.datetime.now(UTC).isoformat()
 try:
  r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Q3 academic reproduction/1.0'}),timeout=90)
  b=r.read();p.write_bytes(b)
  j={'url':url,'requested_at_utc':start,'retrieved_at_utc':dt.datetime.now(UTC).isoformat(),'status':r.status,'bytes':len(b),'sha256':sha(p),'headers':{k:v for k,v in r.headers.items() if k.lower() not in ('set-cookie','cookie')},'path':str(p)}
 except Exception as e:j={'url':url,'requested_at_utc':start,'error':str(e)}
 dump(CACHE/(name+'.request.json'),j)
def text(b):
 try:return b.decode('utf-8-sig')
 except UnicodeDecodeError:return b.decode('cp1252')
def parse_dates(s,fmt=None):
 return pd.to_datetime(s,format=fmt or 'mixed',errors='coerce',dayfirst=bool(fmt and fmt.startswith('%d')))
def clean_pairs(times,values):
 a=pd.DataFrame({'t':times,'v':pd.to_numeric(values,errors='coerce')}).dropna()
 return a.groupby('t',as_index=False).v.median().sort_values('t')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--collect',action='store_true');args=ap.parse_args();CACHE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 if args.collect:
  for n,u in URLS.items():fetch(n,u)
  p=CACHE/'PFTF_63a83e2'
  if not p.exists():
   subprocess.run(['git','init',str(p)],check=True)
   subprocess.run(['git','-C',str(p),'remote','add','origin','https://gitlab.com/inverse-velocity/PFTF.git'],check=True)
   subprocess.run(['git','-C',str(p),'fetch','--depth','1','origin',PFTF_COMMIT],check=True)
   subprocess.run(['git','-C',str(p),'checkout','--detach','FETCH_HEAD'],check=True)
  assert subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()==PFTF_COMMIT
 z=zipfile.ZipFile(CACHE/'PFTF_real_collection.zip')
 checksum=[]
 for line in z.read('m1688868/checksums.sha512').decode().splitlines():
  h,n=line.split(' *',1);member='m1688868/'+n.replace('\\','/');ok=hashlib.sha512(z.read(member)).hexdigest()==h;checksum.append({'member':member,'sha512':h,'matches':ok});assert ok
 dump(OUT/'publisher_checksum_verification.json',checksum)
 metas=[];series=[];exclusions=[]
 # Deterministic, preregistered channel choices; no outcome-based best-sensor selection.
 choices={'Agoyama':'cm','Arvigo':'POT5_3','Galterengraben':'TJM1','Grabengufer_inclinometer':'inclinometer_north','Hogarth':'J1','Kagemori':'1_mm','La_Saxe':'B4','Nevis-Bluff':'1_hor_m','Ohto':'mm','Preonzo_extensometers':'ext1_mm','Ryan_Call_slope2':'cm','Weissmiess_radar':'mean'}
 unitmap={'Agoyama':'cm','Arvigo':'mm','Galterengraben':'mm','Grabengufer_inclinometer':'degree','Hogarth':'foot','Kagemori':'mm','La_Saxe':'m','Nevis-Bluff':'m','Ohto':'mm','Preonzo_extensometers':'mm','Ryan_Call_slope2':'cm','Weissmiess_radar':'mm'}
 for member in z.namelist():
  if '/data/' not in member or not member.endswith('.csv'):continue
  stem=Path(member).stem;s=text(z.read(member));lines=s.splitlines();meta={'file':member,'sha256':hashlib.sha256(z.read(member)).hexdigest(),'metadata_lines_1_7':lines[:7],'read_scope':'full CSV; one preregistered channel used; pre-label only; max trailing 180 days retained'};metas.append(meta)
  if stem not in choices:
   exclusions.append({'file':member,'reason':{'Vaiont':'failure header 1963-02-01 conflicts with series until 1963-10-08; not silently corrected','Grabengufer_gnss':'header metres inconsistent with latitude/longitude-looking e,n values; inclino chosen instead','Preonzo_reflectors':'same Preonzo physical event; extensometer chosen a priori','Weissmiess_camera':'velocity mPixel/day; radar velocity chosen instead','Veslemannen':'linked ESM6 acquired separately; see supplemental record'}.get(stem,'not selected')});continue
  d=pd.read_csv(io.StringIO('\n'.join(lines[7:])))
  failure=dt.datetime.fromisoformat(lines[5].split(': ',1)[1].strip());date_only=len(lines[5].split(': ',1)[1].strip())==10
  group=lines[0].split(': ',1)[1].strip().replace(' ','_');col=choices[stem];kind='velocity' if stem=='Weissmiess_radar' else 'displacement';explicit_utc=d.columns[0]=='UTC Time'
  if stem=='La_Saxe':
   d=d[d.TargetName==col];a=clean_pairs(parse_dates(d.Epoch,'%d/%m/%Y %H.%M.%S'),d.SlopeDistance)
  else:a=clean_pairs(parse_dates(d.iloc[:,0]),d[col])
  lo=failure if date_only else failure-dt.timedelta(seconds=30);hi=failure+dt.timedelta(days=1) if date_only else failure+dt.timedelta(seconds=30)
  # Drop the whole coarse-labelled failure day to avoid using post-failure measurements.
  a=a[(a.t<lo)&(a.t>=lo-dt.timedelta(days=180))]
  if len(a)<10:exclusions.append({'file':member,'reason':'less than 10 valid pre-label measurements'});continue
  add_series(series,a,stem+'__'+col,group,unitmap[stem],kind,lo,hi,lines[5],member,explicit_utc,'curator_failure_day_interval' if date_only else 'curator_minute_label_resolution_interval',meta)
 # Direct journal supplement: raw file units not labelled; primary paper describes LOS mm.
 if (CACHE/'Veslemannen_ESM6.txt').exists():
  d=pd.read_csv(CACHE/'Veslemannen_ESM6.txt',sep='\t');a=clean_pairs(parse_dates(d.Time,'%d.%m.%y %H:%M'),d.Pts_01);failure=dt.datetime(2019,9,5,19);lo=failure-dt.timedelta(minutes=1);hi=failure+dt.timedelta(minutes=1);a=a[(a.t<lo)&(a.t>=lo-dt.timedelta(days=180))]
  add_series(series,a,'Veslemannen__Pts_01','Veslemannen','mm','displacement',lo,hi,'2019-09-05 19:00 curator; primary paper 20:58 local; alignment not independently proven','Veslemannen_ESM6.txt',False,'curator_minute_label_with_clock_alignment_unknown',{'metadata_lines_1_7':['LOS cumulative displacement; primary DOI10.1007/s10346-020-01609-x; mm units primary description/figure magnitude; source no timezone'],'read_scope':'Time + Pts_01; whole file read; trailing 180d pre-label; coherence caveat final hours'})
 # Brienz fixed reflectors 715 and 719; all same physical event. Extract raw distance, no derived averaged velocity.
 brienz=extract_brienz()
 for col in ('CH','CV'):
  a=clean_pairs([dt.datetime.strptime(x['A'],'%d.%m.%Y %H:%M:%S') for x in brienz if col in x],[x[col] for x in brienz if col in x]);lo=dt.datetime(2023,6,15,23,26);hi=dt.datetime(2023,6,15,23,41);a=a[a.t<lo]
  add_series(series,a,'Brienz__'+('715' if col=='CH' else '719'),'Brienz_Insel','mm','displacement',lo,hi,'main collapse interval23:26–23:41 local on 2023-06-15 from Loew et al DOI10.1007/s10346-024-02380-z','brienz_tps.xlsx Ark1 '+col,False,'documented_main_collapse_interval',{'metadata_lines_1_7':['raw corrected slope distance [mm]; datetime timezone unspecified in workbook; local wall clock alignment assumed only for external benchmark'],'read_scope':'Ark1 A/CH/CV; Jan1–June15 2023, prior to label; full sheet streamed'})
 obs=[];registry=[]
 for e in series:
  a=e.pop('observations');obs.extend(a);registry.append(e)
 pd.DataFrame(obs).to_csv(OUT/'observations.csv',index=False,float_format='%.12g')
 pd.DataFrame(registry).to_csv(OUT/'site_registry.csv',index=False,float_format='%.12g')
 dump(OUT/'metadata_audit.json',{'sources':metas,'exclusions':exclusions,'selection':'fixed named channels recorded in code; not performance selected; multi-sensor Brienz grouped; original archives retained','external_failure_phase':'published terminal/main catastrophic collapse, not first onset of any slow mechanical motion','timestamp_policy':'naive source clocks retained; only explicit UTC columns receive UTC, label-clock equivalence remains curator assumption; no fabricated UTC epoch','label_resolution':'minute brackets are display precision only, unknown physical/proxy bias separate; day labels entire source day','post_failure_rule':'strict before label lower; raw later measurements retained only in archive','max_trailing_days':180})
 sources=[]
 for name,url in URLS.items():
  p=CACHE/name
  if not p.exists():continue
  log=next((q for q in (CACHE/(name+'.request.json'),CACHE/(name.replace('.txt','')+'.request.json')) if q.exists()),None);j=json.loads(log.read_text()) if log else {}
  sources.append({'canonical_url_or_product_id':url,'product_version':'PFTF real archive DOI10.14459/2023mp1688868' if name.startswith('PFTF_real') else ('Loew2024 DOI10.3929/ethz-b-000670494' if name in ('brienz_tps.xlsx','brienz_readme.pdf','eth_item.json') else ('Loew2024 primary article' if name=='brienz_primary_article.html' else 'Kristensen2021 primary/ESM6')),'retrieved_at_utc':j.get('retrieved_at_utc'),'actual_read_scope':{'PFTF_real_collection.zip':'all17data-file metadata and publisher checksums; selected 12 channels; raw whole archive','brienz_tps.xlsx':'Ark1 A,CH,CV values and header; full worksheet stream, selected2023period','brienz_readme.pdf':'full README,2pages textual','eth_item.json':'full metadata and license','Veslemannen_ESM6.txt':'Time/Pts_01 series; whole text','brienz_primary_article.html':'monitoring methods and main collapse23:26–23:41 local, sensor-loss times','veslemannen_primary_article.html':'GBInSAR methods/phase wrapping and terminal collapse20:58 local, no clock equivalence assertion'}.get(name),'bytes':p.stat().st_size,'sha256':sha(p),'cache_path':str(p),'license':'CC-BY4.0 curator collection' if name.startswith('PFTF_real') else ('CC-BY-NC4.0 ETH item' if name in ('brienz_tps.xlsx','brienz_readme.pdf','eth_item.json') else 'journal CC-BY4.0 article; ESM source attributed'),'data_role':'external_transfer','available_time_or_unknown':None,'request_log':str(log) if log else None})
 repo=CACHE/'PFTF_63a83e2'
 for n in ('README.md','LICENSE','displ_data.Rda'):
  p=repo/n
  if p.exists():sources.append({'canonical_url_or_product_id':'https://gitlab.com/inverse-velocity/PFTF/-/blob/'+PFTF_COMMIT+'/'+n,'product_version':PFTF_COMMIT,'retrieved_at_utc':dt.datetime.fromtimestamp(p.stat().st_mtime,UTC).isoformat(),'retrieval_clock_note':'filesystem receipt metadata, not historical release availability','actual_read_scope':('full README methods/instructions/demo/license claim read' if n=='README.md' else ('license title and first25lines inspected; full bytes hashed; not full legal-text analysis' if n=='LICENSE' else 'full bytes hashed only; artificial demo from README, not decoded or fitted')),'bytes':p.stat().st_size,'sha256':sha(p),'cache_path':str(p),'data_role':'method_review_only','available_time_or_unknown':None})
 for n,u,scope in [('data_landing.html','https://mediatum.ub.tum.de/1688868','full landing; data download link and CC-BY4.0 license inspected'),('datacite.json','https://api.datacite.org/dois/10.14459/2023mp1688868','full metadata, DOI title/description/canonicalURL'),('eth_bitstreams.json','https://research-collection.ethz.ch/server/api/core/bundles/60d7e8a5-8251-492e-81e5-f3f8a38f9442/bitstreams','full original-bundle list, only TPS and README fetched'),('tum_download_landing.html','https://dataserv.ub.tum.de/index.php/s/m1688868','public-share metadata and advertised public ZIP link read')]:
  q=CACHE/n
  if q.exists():sources.append({'canonical_url_or_product_id':u,'product_version':'retrieved2026-10-24','retrieved_at_utc':dt.datetime.fromtimestamp(q.stat().st_mtime,UTC).isoformat(),'retrieval_clock_note':'filesystem write/receipt time from this acquisition; no historical availability inference','actual_read_scope':scope,'bytes':q.stat().st_size,'sha256':sha(q),'cache_path':str(q),'data_role':'source_and_license_audit','available_time_or_unknown':None})
 dump(R/'results/deformation_sources.json',{'sources':sources,'acquisition_failures':[{'url':'https://mediatum.ub.tum.de/1688868','status':'several timeout attempts; unbounded initial DOI request eventually successful; switched official dataserv link'},{'url':'https://www.research-collection.ethz.ch/server/api/core/items/71f80c84-731a-4486-a529-47f3ef0b37dd/bundles','status':'HTTP429; lawful non-www official host succeeded'}],'PFTF_demo':'artificial Rda explicitly excluded from empirical denominator','PFTF_license_conflict':'README GPL3-or-later; LICENSE AGPL3 text, no upstream code copied/executed','historical_availability':'retrieval now does not establish original real-time sensor data availability','group_count':len(set(x['event_group'] for x in registry)),'sensor_count':len(registry),'observation_count':len(obs)})
 print(json.dumps({'groups':len(set(x['event_group'] for x in registry)),'sensors':len(registry),'observations':len(obs)}))
def add_series(out,a,sid,group,unit,kind,lo,hi,label,source,utc,labkind,meta):
 a=a.sort_values('t');origin=a.t.iloc[0].to_pydatetime();t=np.array([(x.to_pydatetime()-origin).total_seconds()/3600 for x in a.t]);v=a.v.to_numpy(float);rawv=v.copy()
 if kind=='velocity':v=np.r_[0,np.cumsum((v[1:]+v[:-1])/2*np.diff(t)/24)]
 # All displacements remain signed original/causal-integrated, orientation handled with past-only information by models.
 observations=[{'site_id':sid,'event_group':group,'time_relative_hours':float(x),'time_utc':stamp.to_pydatetime().replace(tzinfo=UTC).isoformat() if utc else None,'source_timestamp':stamp.isoformat(),'displacement':float(y),'unit':unit,'raw_velocity_per_day':float(rv) if kind=='velocity' else None,'observed':True,'variable_kind':kind,'value_derivation':'causal_trapezoid_velocity_integration' if kind=='velocity' else 'raw_source_scalar'} for x,y,rv,stamp in zip(t,v,rawv,a.t)]
 low=(lo-origin).total_seconds()/3600;high=(hi-origin).total_seconds()/3600
 out.append({'site_id':sid,'event_group':group,'time_origin_source_clock':origin.isoformat(),'time_origin_utc':origin.replace(tzinfo=UTC).isoformat() if utc else None,'start_hours':0,'end_hours':float(t[-1]),'last_observation_hours':float(t[-1]),'followup_end_hours':high,'failure_time_hours':(low+high)/2,'failure_lower_hours':low,'failure_upper_hours':high,'failure_time_utc':((lo+(hi-lo)/2).replace(tzinfo=UTC).isoformat() if utc else None),'event_observed':True,'censoring_verified':False,'risk_status':'interval_labelled_failure','label_kind':labkind,'label_source':'https://doi.org/10.14459/2023mp1688868 / '+source if not sid.startswith('Brienz') else 'https://doi.org/10.1007/s10346-024-02380-z','label_original':label,'label_semantics':'published terminal/main catastrophic failure; not first mechanical movement initiation','unit':unit,'raw_velocity_unit':('mm/day' if kind=='velocity' else None),'derived_displacement_unit':unit,'primary_evaluation_eligible':group!='Veslemannen','evaluation_exclusion_reason':('curator19:00 vs primary20:58local clock alignment unresolved; minute bracket is not physical uncertainty' if group=='Veslemannen' else None),'variable_kind':kind,'median_cadence_hours':float(np.median(np.diff(t))),'n_observations':len(a),'data_role':'external_transfer','clock_alignment':'explicit UTC observation header; curator label same-clock assumption' if utc else 'source naive; UTC unknown; curator same-clock assumption','sensor_selection':'fixed before fitting; no best-sensor outcome selection','observations':observations})
def extract_brienz():
 p=CACHE/'brienz_selected_raw.json'
 if p.exists():return json.loads(p.read_text())
 import xml.etree.ElementTree as E
 z=zipfile.ZipFile(CACHE/'brienz_tps.xlsx');ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}';ss=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))];out=[]
 for _,x in E.iterparse(z.open('xl/worksheets/sheet1.xml'),events=('end',)):
  if x.tag!=ns+'row':continue
  row={}
  for c in x:
   val=c.find(ns+'v');col=''.join(k for k in c.get('r','') if k.isalpha())
   if val is not None and col in ('A','CH','CV'):row[col]=ss[int(val.text)] if c.get('t')=='s' else val.text
  try:d=dt.datetime.strptime(row.get('A',''),'%d.%m.%Y %H:%M:%S')
  except ValueError:d=None
  if d and dt.datetime(2023,1,1)<=d<=dt.datetime(2023,6,16):out.append(row)
  x.clear()
 dump(p,out);return out
if __name__=='__main__':main()
