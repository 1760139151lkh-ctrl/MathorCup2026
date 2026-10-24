#!/usr/bin/env python3
"""Bounded R2 evidence capture; no refresh or additional dataset downloads.

This is separate from the offline analysis. AI assistance: OpenAI Codex 2026-10-24.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

R2 = Path(__file__).resolve().parents[1]
REQUESTS = [
    ('essd_2026_article.html', 'https://essd.copernicus.org/articles/18/1147/2026/', 2000000,
     'Published 2026-02-10, DOI 10.5194/essd-18-1147-2026',
     'Abstract, sections 2.1/2.2/4 and targeted processing/data-DOI passages; supplements not read',
     'Related-method evidence only; binds dataset 302428, not target 303600'),
    ('aas_doi_response.html', 'https://doi.org/10.1007/s00376-026-6282-3', 500000,
     'DOI cited by target WaterNet metadata; processing version unverified',
     'Access attempt only; if blocked or frontend shell, no article-body reading claimed',
     'No target-data processing claim from an inaccessible article')
]


def main():
    out = R2 / 'sources'; out.mkdir(parents=True, exist_ok=True)
    receipt = out / 'capture_log.json'
    if receipt.exists():
        records = json.loads(receipt.read_text())
        for r in records:
            if r.get('path'):
                body = (R2 / r['path']).read_bytes()
                assert hashlib.sha256(body).hexdigest() == r['sha256']
                if r.get('article_body_reading_verified'):
                    assert all(token in body for token in (b'EddyPro', b'302428', b'10.5194/essd-18-1147-2026'))
        print(json.dumps({'cache_verified': True, 'requests': len(records)}))
        return
    records = []
    for name, url, limit, version, scope, restriction in REQUESTS:
        r = {'url': url, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
             'version': version, 'reading_scope': scope, 'adoption_boundary': restriction,
             'maximum_bytes': limit}
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'MathorCup-Q1-R2-evidence/1.0'})
            with urllib.request.urlopen(req, timeout=20) as stream:
                body = stream.read(limit + 1)
                r.update(http_status=stream.status, final_url=stream.url, content_type=stream.headers.get('Content-Type'))
            if len(body) > limit:
                raise ValueError('Bounded body limit exceeded; no further download')
            (out / name).write_bytes(body)
            r.update(path=f'sources/{name}', bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                     response_saved=True, article_body_reading_verified=name.startswith('essd_') and
                     all(token in body for token in (b'EddyPro', b'302428', b'10.5194/essd-18-1147-2026')))
        except urllib.error.HTTPError as exc:
            # Keep a small returned error body as access evidence, not an article.
            body = exc.read(min(limit, 100000))
            (out / name).write_bytes(body)
            r.update(http_status=exc.code, error=str(exc), path=f'sources/{name}', bytes=len(body),
                     sha256=hashlib.sha256(body).hexdigest(), response_saved=True,
                     article_body_reading_verified=False)
        except Exception as exc:
            r.update(error=f'{type(exc).__name__}: {exc}', response_saved=False, article_body_reading_verified=False)
        records.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    receipt.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
