#!/usr/bin/env python3
"""Fetch bounded public evidence; never touches frozen inputs or other rounds."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("target_tpdc", "https://data.tpdc.ac.cn/zh-hans/data/5b09afd1-d11b-4150-a291-50f0484dddf1", "tpdc_target.html"),
    ("waternet_target", "https://gwfnet.net/Metadata/Index/T-2026-08-28-p1f3e5qIqTEyibfPAp3smBeA", "waternet_target.html"),
    ("related_essd", "https://essd.copernicus.org/articles/18/1147/2026/", "related_essd.html"),
    ("ledoitwolf_official", "https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html", "ledoitwolf_official.html"),
]
records = []
for sid, url, filename in SOURCES:
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    record = {"source_id": sid, "canonical_url_or_product_id": url,
              "retrieved_at_utc": stamp, "maximum_bytes": 3000000,
              "data_role": "exploration", "available_time": None,
              "available_time_status": "historical availability of exact fetched bytes unknown"}
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Q1ResearchEvidence/1.0"})
    try:
        response = urllib.request.urlopen(req, timeout=45)
    except urllib.error.HTTPError as exc:
        response = exc
    except Exception as exc:
        record.update(fetch_success=False, error=repr(exc), bytes=0, sha256=None, path=None)
        records.append(record)
        continue
    with response:
        data = response.read(3000001)
        if len(data) > 3000000:
            raise RuntimeError(f"Source exceeds bounded acquisition limit: {sid}")
        path = ROOT / "evidence" / filename
        path.write_bytes(data)
        record.update(http_status=response.code, final_url=response.geturl(),
                      content_type=response.headers.get("Content-Type"),
                      response_date=response.headers.get("Date"),
                      response_last_modified=response.headers.get("Last-Modified"),
                      response_etag=response.headers.get("ETag"),
                      path=str(path.relative_to(ROOT)), bytes=len(data),
                      sha256=hashlib.sha256(data).hexdigest(),
                      fetch_success=200 <= response.code < 300)
    records.append(record)
(ROOT / "evidence" / "access_log.json").write_text(json.dumps(records, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(records, ensure_ascii=False, indent=2))
