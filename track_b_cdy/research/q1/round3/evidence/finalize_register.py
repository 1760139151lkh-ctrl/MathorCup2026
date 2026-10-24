#!/usr/bin/env python3
"""Build a semantic source register from saved public HTTP evidence, offline."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
records = json.loads((ROOT / "evidence/access_log.json").read_text())
annotations = {
    "target_tpdc": {
        "product_version": None,
        "product_version_status": "target processing version unknown; HTTP Last-Modified belongs to front-end shell",
        "actual_read_scope": "Entire 1927-byte frontend HTML inspected; no target dataset body obtained; web tool direct opening also failed.",
        "evidence_status": "frontend_shell_only",
        "adoption_status": "reject_as_dataset_body_or_processing_provenance",
        "supports": ["Target publication entry point and failure to acquire detailed body"],
        "cannot_support": ["FLUX QC 1-9 mapping", "hour-label support interval", "software/correction-chain version", "sensor height"]
    },
    "waternet_target": {
        "product_version": "WaterNet Version 2026-09-12; metadata record Dataset 1.3",
        "product_version_status": "visible webpage/record labels, not established measurement processing version",
        "actual_read_scope": "Full rendered record text read: abstract (Chinese and English), spatial description, time/QC/missing declarations, citations, download links and footer. No new CSV or archive downloaded.",
        "evidence_status": "same_title_publisher_mirror_metadata",
        "adoption_status": "metadata_declaration_with_unverified_local_version_equivalence",
        "supports": ["Regional station at 28.86N 85.29E, altitude 4140 m, approximate straight-line distance to port 65 km", "meteorological heights 1/2/4/10/20 m and soil depths 0.1/0.2/0.4/0.8/1.6 m", "UTC+8 and hourly resolution declarations", "regional background and explicit local-trigger representativeness limitations"],
        "cannot_support": ["datum or location/elevation uncertainty", "station-to-failure-source distance", "FLUX sensor height/footprint", "full remote FLUX 1-9 code dictionary", "start/end/center convention", "local correction-chain provenance", "historical operational availability"]
    },
    "related_essd": {
        "product_version": "ESSD 18, 1147-1164, published 2026-02-10; DOI 10.5194/essd-18-1147-2026",
        "product_version_status": "version of cited paper, not target data processing version",
        "actual_read_scope": "Abstract, sections 2.1/2.2/4 and targeted station/processing paragraphs; Table 1 caption only, not table XLSX or supplement; no claim of full-article review.",
        "evidence_status": "related_primary_paper_different_data_DOI",
        "adoption_status": "related_method_context_only",
        "supports": ["Related regional network and processing discussion explicitly belongs to paper data DOI 302428"],
        "cannot_support": ["Proven mapping to target DOI 303600 or local CSV", "transfer of QC codes, sensor height, parameters or software version", "cause of amb_e_sat constant segment"]
    },
    "ledoitwolf_official": {
        "product_version": "scikit-learn 1.9.1 documentation (stable page at retrieval)",
        "product_version_status": "documentation snapshot; no inference about experiment-installed version",
        "actual_read_scope": "Title/version, estimator parameters/attributes, Notes covariance formula, cited reference, fit and Mahalanobis documentation; no linked full research paper or examples executed.",
        "evidence_status": "official_method_documentation",
        "adoption_status": "method_formula_only_pending_actual_implementation",
        "supports": ["LedoitWolf shrinkage form and centering behavior"],
        "cannot_support": ["that study implemented automatic Ledoit-Wolf coefficient", "sampling independence or weather-process validity", "causal interpretation of conditional ranking", "independent event validation"]
    }
}
for record in records:
    record.update(annotations[record["source_id"]])
    saved = ROOT / record["path"]
    data = saved.read_bytes()
    assert len(data) == record["bytes"]
    assert hashlib.sha256(data).hexdigest() == record["sha256"]
    record["hash_checked"] = True

register = {
    "schema_version": "q1-r3-evidence-v1",
    "round": "round3", "producer_question": "q1", "data_role": "exploration",
    "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "input_version": {"common_baseline_commit": "904d7257b899b9f71d1ac9e0eab7479e459eab52", "manifest_sha256": "fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53"},
    "records": records,
    "total_saved_response_bytes": sum(r["bytes"] for r in records),
    "scope": "Four bounded public HTML responses; no new meteorological CSV, archive, registration or contact",
    "self_entry_excluded": True,
    "inherited_round2_evidence": "Frozen round2 SEMANTICS_REVIEW and source_register remain unchanged; old evidence cited without pretending it was fetched anew.",
    "limitations": ["Target QC/correction/hour-boundary provenance remains unknown", "Regional station is not a verified source-area forcing", "HTTP success does not establish semantic usability or historical availability"]
}
out = ROOT / "source_register.json"
out.write_text(json.dumps(register, ensure_ascii=False, indent=2)+"\n")
for path in [out, ROOT / "EVIDENCE_REVIEW.md", ROOT / "evidence/access_log.json"]:
    data = path.read_bytes()
    print(json.dumps({"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}))
