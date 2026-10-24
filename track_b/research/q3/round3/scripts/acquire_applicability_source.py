#!/usr/bin/env python3
"""Save one primary-source applicability statement; no claim of full review."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
import hashlib,json
R=Path(__file__).resolve().parents[1];O=R/'results/applicability_sensitivity'
C=Path('/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/applicability')
URL='https://tc.copernicus.org/articles/12/3333/2018/'
def main():
    C.mkdir(parents=True,exist_ok=True);p=C/'mamot2018_article.html';log=C/'mamot2018_article.request.json'
    if not p.exists():
        start=datetime.now(timezone.utc).isoformat()
        with urlopen(Request(URL,headers={'User-Agent':'MathorCup-Q3-research'}),timeout=60) as response:
            raw=response.read();headers=dict(response.headers);status=response.status
        p.write_bytes(raw);log.write_text(json.dumps(dict(url=URL,request_started_at_utc=start,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),http_status=status,response_headers=headers),indent=2)+'\n')
    d=json.loads(log.read_text());text=p.read_text()
    assert '100 to 800' in text and '100 to 400' in text
    source=dict(canonical_url_or_product_id=URL,product_version='DOI10.5194/tc-12-3333-2018; published2018-10-17',
       retrieved_at_utc=d['retrieved_at_utc'],cache_path=str(p),request_log=str(log),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
       actual_read_scope='Abstract and stated fitted-criterion applicability declaration only; distinguishes full tests100–800kPa/-10..-.5C from criterion100–400kPa/-8..-.5C; not a new full-paper methods audit',
       data_role='published_constitutive_applicability_reference',available_time=None,license='CC-BY4.0 publisher page')
    (O/'source_register.json').write_text(json.dumps({'sources':[source],'no_local_material_certification':True},indent=2,ensure_ascii=False)+'\n');print(json.dumps({'bytes':source['bytes'],'sha256':source['sha256']}))
if __name__=='__main__':main()
