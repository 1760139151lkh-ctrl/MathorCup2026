#!/usr/bin/env python3
"""Small, unauthenticated official-source event/remote-sensing audit.

No model fitting, credentials, registration, bulk scenes, or requester-pays access.
Every network response is bounded, saved and hashed. The WorldCover crop uses
four (normally) HTTP-range TIFF blocks rather than downloading its whole tile.
Use the project .venv; --verify-only performs no network requests.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "track_b/data/external/event_remote"
AOI = [85.5053, 28.2691, 85.5501, 28.3069]
CATALOG_AOI = [85.0, 27.8, 86.0, 28.8]
INTERVAL = "2026-08-01T00:00:00Z/2026-09-11T00:00:00Z"
EVENT_TIME = "2026-08-26T02:52:10+00:00"
USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us7000tbwb&format=geojson"
JMS = "https://jms.imde.ac.cn/article/doi/10.1007/s11629-026-1482-y"
JMS_PDF = "https://jms.imde.ac.cn/en/article/pdf/preview/10.1007/s11629-026-1482-y.pdf"
CHINESE_PAPER = "https://zgdzzhyfzxb.com/article/doi/10.16031/j.cghc.202610008?viewType=HTML"
WORLD = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N27E084_Map.tif"
LABELS = {0: "NoData", 10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up", 60: "Bare/sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies", 90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def iso_epoch(value):
    return datetime.fromtimestamp(float(value) / 1000, timezone.utc).isoformat() if value is not None else None


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Collector:
    def __init__(self, run_dir):
        self.run_dir = run_dir
        self.records = []
        self.session = requests.Session()
        # Explicitly do not load ~/.netrc or environment credentials/proxies.
        self.session.trust_env = False
        self.session.headers["User-Agent"] = "MathorCup-stage3-data-audit/1.0"

    def fetch(self, name, url, *, headers=None, max_bytes=3_000_000):
        path = self.run_dir / "raw" / name
        rec = {"name": name, "requested_url": url, "request_headers": headers or {}, "retrieved_at_utc": utc_now(), "max_bytes": max_bytes}
        data = b""
        try:
            with self.session.get(url, headers=headers, timeout=(10, 25), stream=True, allow_redirects=True) as response:
                rec.update({"http_status": response.status_code, "final_url": response.url,
                            "redirects": [{"status": r.status_code, "url": r.url} for r in response.history],
                            "response_headers": {k: response.headers[k] for k in ("Content-Type", "Content-Length", "Content-Range", "Last-Modified", "ETag", "Date") if k in response.headers}})
                for chunk in response.iter_content(65536):
                    if len(data) + len(chunk) > max_bytes:
                        rec["body_truncated_by_limit"] = True
                        data += chunk[:max_bytes - len(data)]
                        break
                    data += chunk
                rec["successful_status"] = 200 <= response.status_code < 300
        except requests.RequestException as exc:
            rec.update({"error_type": type(exc).__name__, "error": str(exc), "successful_status": False})
        rec.update({"saved_bytes": len(data), "sha256": sha(data), "body_path": str(path.relative_to(OUT))})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.records.append(rec)
        save_json(self.run_dir / "http_requests.json", self.records)
        return data, rec

    def get_json(self, name, url, **kwargs):
        data, rec = self.fetch(name, url, **kwargs)
        try:
            value = json.loads(data)
            if not rec.get("successful_status") or "error" in value:
                return None
            return value
        except (ValueError, TypeError):
            return None


def stac_url(endpoint, collection):
    return endpoint + "/search?" + urllib.parse.urlencode({"collections": collection, "bbox": ",".join(map(str, AOI)), "datetime": INTERVAL, "limit": 100})


def scene_record(feature, provider):
    prop = feature["properties"]
    return {"provider": provider, "collection": feature.get("collection"), "item_id": feature["id"],
            "datetime": prop.get("datetime"), "start_datetime": prop.get("start_datetime"), "end_datetime": prop.get("end_datetime"),
            "platform": prop.get("platform"), "processing_level": prop.get("processing:level", prop.get("landsat:correction")),
            "processing_datetime": prop.get("processing:datetime"), "processing_version": prop.get("processing:version"),
            "cloud_cover_scene_or_tile_percent": prop.get("eo:cloud_cover"), "published": prop.get("published"),
            "created": prop.get("created"), "updated": prop.get("updated"),
            "available_time_verified": None, "publication_caveat": "Published/created are current catalogue metadata, not independently archived evidence of historical operational availability.",
            "bbox": feature.get("bbox"), "geometry": feature.get("geometry"),
            "orbit_state": prop.get("sat:orbit_state"), "relative_orbit": prop.get("sat:relative_orbit"),
            "sar_polarizations": prop.get("sar:polarizations"),
            "assets": {k: {p: a.get(p) for p in ("href", "type", "roles", "file:size", "file:checksum", "auth:refs", "alternate") if p in a} for k, a in feature.get("assets", {}).items()},
            "self_url": next((l["href"] for l in feature.get("links", []) if l.get("rel") == "self"), None),
            "aoi_role": "Unconfirmed NC test footprint; not a verified source polygon.",
            "aoi_clear_fraction": None, "pixel_visibility_verified": False}


def choose_scenes(scenes):
    selected = {}
    event = datetime.fromisoformat(EVENT_TIME)
    for provider in sorted({s["provider"] for s in scenes}):
        group = [s for s in scenes if s["provider"] == provider and s["datetime"]]
        for side, condition in (("before", lambda t: t < event), ("after", lambda t: t >= event)):
            subset = [s for s in group if condition(datetime.fromisoformat(s["datetime"].replace("Z", "+00:00")))]
            if not subset:
                continue
            nearest = min(subset, key=lambda s: abs((datetime.fromisoformat(s["datetime"].replace("Z", "+00:00")) - event).total_seconds()))
            selected.setdefault(nearest["item_id"], {"scene": nearest, "selection_reasons": []})["selection_reasons"].append(side + "_nearest_acquisition")
            cloudy = [s for s in subset if s["cloud_cover_scene_or_tile_percent"] is not None]
            if cloudy:
                clear = min(cloudy, key=lambda s: s["cloud_cover_scene_or_tile_percent"])
                selected.setdefault(clear["item_id"], {"scene": clear, "selection_reasons": []})["selection_reasons"].append(side + "_minimum_catalogue_cloud_cover_not_AOI_visibility")
    return list(selected.values())


def collect_events(collector):
    event = collector.get_json("usgs_event.json", USGS)
    ledger = []
    problem_files = list((ROOT / "04_B赛道/00_赛题").glob("*.pdf"))
    problem = problem_files[0] if len(problem_files) == 1 else None
    common = {"event_id": "B20260826_Chhochen", "independent_event_group": "B20260826_Chhochen", "retrieved_at_utc": utc_now(), "discovered_by_this_audit_at_utc": utc_now(), "event_first_discovery_time_verified": None, "approved_training_label": False}
    ledger.append({**common, "evidence_id": "problem_1030", "physical_stage": "problem_statement_background_time_unspecified_stage", "source_kind": "local_problem_statement", "source_path": str(problem.relative_to(ROOT)) if problem else None, "source_sha256": sha(problem.read_bytes()) if problem else None,
                   "source_time_text": "2026年8月26日10时30分", "event_time_utc": "2026-08-26T02:30:00+00:00", "time_zone_assumption": "Asia/Shanghai (UTC+8), per task protocol; source time has no uncertainty", "time_uncertainty_seconds": None, "source_publication_time": None, "source_discovered_at_utc": None, "available_time_verified": None, "coordinates": None, "coordinate_precision": "not supplied", "label_role": "retain_competition_reference; do_not_silently_replace"})
    if event:
        props = event["properties"]
        origin = props.get("products", {}).get("origin", [{}])[0]
        qml_href = origin.get("contents", {}).get("quakeml.xml", {}).get("url")
        qml = None
        uncertainties = {}
        if qml_href:
            qml, qrec = collector.fetch("usgs_origin_quakeml.xml", qml_href, max_bytes=100_000)
            if qrec.get("successful_status"):
                qroot = ET.fromstring(qml)
                ns = {"q": "http://quakeml.org/xmlns/bed/1.2"}
                org = qroot.find(".//q:origin", ns)
                for key, query in {"origin_time_uncertainty_seconds": "q:time/q:uncertainty", "origin_time_confidence_level_percent": "q:time/q:confidenceLevel", "horizontal_uncertainty_m": "q:originUncertainty/q:horizontalUncertainty", "origin_uncertainty_confidence_level_percent": "q:originUncertainty/q:confidenceLevel", "latitude_uncertainty_degrees": "q:latitude/q:uncertainty", "longitude_uncertainty_degrees": "q:longitude/q:uncertainty", "origin_creation_time_utc": "q:creationInfo/q:creationTime"}.items():
                    el = org.find(query, ns) if org is not None else None
                    uncertainties[key] = el.text if el is not None else None
        ledger.append({**common, "evidence_id": "usgs_current_reviewed_origin", "physical_stage": "catalogue_seismic_reference_not_mechanical_initiation_proof", "source_kind": "official_USGS_ComCat_and_QuakeML", "source_url": USGS, "source_time_text": origin.get("properties", {}).get("eventtime"), "event_time_utc": iso_epoch(props["time"]), "coordinates_lon_lat_depth_km": event["geometry"]["coordinates"],
                       "event_type": props.get("type"), "magnitude": props.get("mag"), "magnitude_type": props.get("magType"), "status": props.get("status"),
                       "source_product_updated_time_utc": iso_epoch(origin.get("updateTime")), "source_publication_time": None, "source_discovered_at_utc": None, "available_time_verified": None, "current_metadata_pre_event_eligible": False,
                       **uncertainties, "label_role": "retrospective_reference_with_proxy_and_90pct_catalogue_uncertainty; not_a_95pct_forecast_interval", "coordinate_precision": "13.39 km horizontal uncertainty in current QuakeML; not a source geometry"})
        for product in props.get("products", {}).get("general-text", []):
            raw = product.get("contents", {}).get("", {}).get("bytes", "")
            ledger.append({**common, "evidence_id": "usgs_post_event_key_points", "physical_stage": "post_event_classification_revision", "source_kind": "official_USGS_product_embedded_text", "source_url": USGS,
                           "source_product_updated_time_utc": iso_epoch(product.get("updateTime")), "source_time_text": re.sub("<[^>]+>", " ", raw).strip(), "event_time_utc": None, "available_time_verified": None, "current_metadata_pre_event_eligible": False,
                           "label_role": "USGS reports initial earthquake classification was revised to glacial collapse/debris flow; not an antecedent tectonic trigger"})
    article_html, hrec = collector.fetch("jms_article.html", JMS, max_bytes=1_000_000)
    article = {}
    match = re.search(rb"var article_meta_data='([^']+)'", article_html)
    if match:
        article = json.loads(base64.b64decode(match.group(1)))
    paper, prec = collector.fetch("jms_uncorrected_proof.pdf", JMS_PDF, max_bytes=2_000_000)
    reading = {"download_success": paper.startswith(b"%PDF") and prec.get("successful_status"), "source_url": JMS_PDF, "sha256": sha(paper), "bytes": len(paper), "reading_scope": "Relevant full pages 5-13, 28-31 plus Fig.1/Fig.2 rendered and visually inspected; parameter/method derivations not independently verified.",
               "cms_metadata_selected": {k: article.get(k) for k in ("doi", "articleNo", "pdfAccess", "htmlAccess", "preprintDate", "receivedDate", "acceptedDate", "lastUpdateTime", "releaseProgress")},
               "cms_epoch_dates_utc": {k: iso_epoch(article.get(k)) for k in ("preprintDate", "receivedDate", "acceptedDate", "lastUpdateTime")},
               "original_data_access": "PDF p31 says study datasets available from corresponding author upon reasonable request; no author was contacted.",
               "historical_availability_caveat": "CMS date fields/current release label are post-event; they are not an archive proving first public availability."}
    if reading["download_success"]:
        (OUT / "jms_2026_uncorrected_proof.pdf").write_bytes(paper)
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(paper))
        reading["pages"] = len(reader.pages)
        reading["page_text_presence_checks"] = {}
        # Check the precise strings that back the ledger, not the model equations.
        for page, strings in {9: ["10:51:50", "10:52:20"], 10: ["10:54:00"], 11: ["10:59:50"], 31: ["reasonable request"]}.items():
            text = reader.pages[page - 1].extract_text()
            reading["page_text_presence_checks"][str(page)] = {s: s in text for s in strings}
        stages = [("jms_initiation", "mechanical_movement_onset_reconstruction", "10:51:50", "2026-08-26T02:51:50+00:00", 9),
                  ("jms_first_impact", "first_impact_onto_detached_glacier_reconstruction", "10:52:20", "2026-08-26T02:52:20+00:00", 9),
                  ("jms_confluence_impact", "Guoba_Xiaqu_confluence_impact_and_transition", "10:54:00", "2026-08-26T02:54:00+00:00", 10),
                  ("jms_port_arrival", "Gyirong_Port_approximate_reported_arrival", "10:59:50", "2026-08-26T02:59:50+00:00", 11)]
        for evid, stage, raw_time, instant, page in stages:
            ledger.append({**common, "evidence_id": evid, "physical_stage": stage, "source_kind": "original_research_uncorrected_proof_retrospective_reconstruction", "source_url": JMS_PDF, "source_pdf_page": page, "source_figure": "Fig.2; waveform attributed to Yang et al. 2026", "source_time_text": "approximately " + raw_time + " BJT",
                           "event_time_utc": instant, "time_zone": "Asia/Shanghai UTC+8", "time_uncertainty_seconds": None, "source_publication_time_cms_text": article.get("releaseProgress", {}).get("lastReleaseTime"), "publication_time_zone": "not stated in CMS text", "source_publication_epoch_utc": iso_epoch(article.get("lastUpdateTime")), "source_discovered_at_utc": None, "available_time_verified": None, "current_metadata_pre_event_eligible": False,
                           "coordinates": None, "coordinate_precision": "Map Fig.1 shows setting/source outline but no machine-readable coordinate table read; do not geolocate from image by eye.", "label_role": "candidate_reconstruction_constraint_only; original_waveform_and_arrival_report_not_obtained; same_event_not_independent_validation"})
    save_json(collector.run_dir / "paper_reading.json", reading)
    # Supplemental original-research lead: metadata is directly re-fetched, while
    # the two time claims below were manually read in publisher search extracts.
    # They are intentionally not represented as fully audited HTML/PDF text.
    chinese_html, chinese_rec = collector.fetch("chinese_primary_article.html", CHINESE_PAPER, max_bytes=1_000_000)
    chinese_meta = {}
    chinese_match = re.search(rb"var article_meta_data='([^']+)'", chinese_html)
    if chinese_match:
        chinese_meta = json.loads(base64.b64decode(chinese_match.group(1)))
    supplemental = {"source_url": CHINESE_PAPER, "doi": "10.16031/j.cghc.202610008", "authors": "殷跃平等", "title": "尼泊尔蓝塘里壤峰‘8·26’冰岩崩致吉隆泥石流灾难研究", "direct_html_http_status": chinese_rec.get("http_status"),
        "direct_reading_scope": "Publisher metadata and abstract. Full HTML is dynamically loaded and was not retrieved/checked in this audit.",
        "browser_search_reading_scope": "Official publisher search extracts: main onset preliminarily inferred using wave speed and epicentral distance; main body reaches the port at approximately 11:00:00. Search extracts only, not verified original waveform/video.",
        "browser_search_queries": ['"中尼边境" "8·26" "演化特征" 2026', '"Dynamic Processes and Formation Mechanisms" "August 26" 2026 Yang'],
        "cms_metadata_selected": {k: chinese_meta.get(k) for k in ("doi", "preprintDate", "lastUpdateTime", "releaseProgress", "htmlAccess", "pdfAccess")},
        "evidence_tier": "candidate_original_publisher_extract; human_fulltext_review_required", "approved_training_label": False}
    save_json(OUT / "supplemental_original_source.json", supplemental)
    for evid, stage, raw_time, instant in [("yin_main_onset_extract", "main_initiation_preliminary_inference", "10:52:07", "2026-08-26T02:52:07+00:00"), ("yin_port_arrival_extract", "main_body_port_arrival_approximate", "11:00:00", "2026-08-26T03:00:00+00:00")]:
        ledger.append({**common, "evidence_id": evid, "physical_stage": stage, "source_kind": "original_publisher_browser_search_excerpt_only", "source_url": CHINESE_PAPER, "source_time_text": raw_time + " BJT", "event_time_utc": instant,
            "time_uncertainty_seconds": None, "source_publication_time_cms_text": chinese_meta.get("releaseProgress", {}).get("lastReleaseTime"), "publication_time_zone": "not stated in CMS text", "source_discovered_at_utc": None, "available_time_verified": None, "current_metadata_pre_event_eligible": False, "coordinates": None,
            "fulltext_verified": False, "direct_html_time_string_present": raw_time.encode() in chinese_html, "label_role": "candidate_cross_source_comparison_only; do_not_average_or_treat_as_independent_event; fulltext_and_original_measurement_unverified"})
    save_json(OUT / "event_evidence_ledger.json", {"generated_at_utc": utc_now(), "policy": "Rows are evidence claims, not independent events; null means unverified. 90% catalogue error is not the question's 95% future-event interval.", "records": ledger,
        "unresolved": ["Problem 10:30 versus reconstructed onset and catalogue reference remains unresolved; keep all source values.", "Raw, clock-calibrated source waveform and original port-arrival video/hydrology report are not obtained.", "Verified failure/target polygons and target arrival criterion remain undefined.", "Historical discovery time and actual pre-event data availability are unknown; retrieval time is not availability."]})
    return reading


def collect_scenes(collector):
    sources = [("CDSE_Sentinel2_L2A", "https://stac.dataspace.copernicus.eu/v1", "sentinel-2-l2a"),
               ("CDSE_Sentinel1_GRD", "https://stac.dataspace.copernicus.eu/v1", "sentinel-1-grd"),
               ("USGS_Landsat_C2_L2_SR", "https://landsatlook.usgs.gov/stac-server", "landsat-c2l2-sr")]
    scenes = []
    query_summary = []
    for provider, endpoint, collection in sources:
        result = collector.get_json(provider + ".json", stac_url(endpoint, collection))
        if result:
            features = list(result.get("features", []))
            page, seen_pages = 1, set()
            while True:
                next_link = next((l.get("href") for l in result.get("links", []) if l.get("rel") == "next"), None)
                if not next_link:
                    break
                if not next_link.startswith(endpoint + "/") or next_link in seen_pages or page >= 10:
                    raise RuntimeError("Unexpected, cyclic or excessive STAC pagination.")
                seen_pages.add(next_link)
                page += 1
                result = collector.get_json(provider + "_page_%02d.json" % page, next_link)
                if result is None:
                    raise RuntimeError("STAC continuation failed; cannot call the search complete.")
                features.extend(result.get("features", []))
            query_summary.append({"provider": provider, "number_returned": len(features), "number_matched_last_page": result.get("numberMatched"), "pages_read": page, "next_page_present": False})
            scenes += [scene_record(f, provider) for f in features]
        else:
            query_summary.append({"provider": provider, "query_failed": True})
    selected = choose_scenes(scenes)
    save_json(OUT / "scene_inventory.json", {"generated_at_utc": utc_now(), "bbox": AOI, "bbox_role": "NC data footprint pipeline test; not confirmed event source", "datetime_interval": INTERVAL,
        "query_summary": query_summary, "records": scenes, "selected_candidates": [{"item_id": v["scene"]["item_id"], "selection_reasons": v["selection_reasons"]} for v in selected],
        "limitations": ["Scene/tile cloud cover is not AOI clear-sky visibility.", "Intersecting item footprint is not proof all AOI pixels are valid.", "Published/created/updated/current metadata are not independently archived historical access evidence.", "S1 GRD has no optical cloud cover; speckle, layover, shadow and orbit alignment require separate checks."]})
    fields = ["provider", "item_id", "datetime", "processing_level", "cloud_cover_scene_or_tile_percent", "published", "created", "updated", "available_time_verified", "self_url"]
    with (OUT / "scene_candidates.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields + ["selection_reasons"])
        writer.writeheader()
        for candidate in selected:
            row = {k: candidate["scene"].get(k) for k in fields}
            row["selection_reasons"] = ";".join(candidate["selection_reasons"])
            writer.writerow(row)
    # Actual anonymous access tests; HTTP 200 HTML is explicitly not an image.
    cdse = next((s for s in scenes if "20260824T044659" in s["item_id"]), None)
    landsat = next((s for s in scenes if "20260826" in s["item_id"] and "141040" in s["item_id"]), None)
    access = []
    if cdse:
        asset = cdse["assets"].get("B04_10m", {})
        href = asset.get("alternate", {}).get("https", {}).get("href")
        if href:
            data, rec = collector.fetch("cdse_anonymous_asset_probe.bin", href, headers={"Range": "bytes=0-1023"}, max_bytes=2048)
            access.append({"provider": cdse["provider"], "item_id": cdse["item_id"], "asset": "B04_10m", "http_status": rec.get("http_status"), "data_obtained": rec.get("http_status") in (200, 206) and not data.lstrip().startswith(b"<"), "restriction": "Catalogue asset advertises OIDC/S3 authentication; no login or credentials used."})
    if landsat:
        href = landsat["assets"]["thumbnail"]["href"]
        data, rec = collector.fetch("landsat_anonymous_thumbnail_probe.bin", href, max_bytes=100_000)
        access.append({"provider": landsat["provider"], "item_id": landsat["item_id"], "asset": "thumbnail", "http_status": rec.get("http_status"), "final_url": rec.get("final_url"), "data_obtained": data.startswith(b"\xff\xd8\xff"), "restriction": "Redirect to USGS ERS login is not a downloaded satellite image. Requester-pays S3 alternative not attempted."})
    save_json(OUT / "asset_access_tests.json", access)
    return query_summary, len(scenes)


def collect_historical_candidates(collector):
    tables = []
    queries = []
    for typ in ("Points", "Polygons"):
        base = "https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_" + typ + "/FeatureServer/0"
        params = {"where": "1=1", "geometry": ",".join(map(str, CATALOG_AOI)), "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true", "f": "json", "resultRecordCount": 200}
        source = base + "/query?" + urllib.parse.urlencode(params)
        result = collector.get_json("nasa_COOLR_Reports_" + typ + ".json", source, max_bytes=2_000_000)
        if not result:
            queries.append({"geometry_type": typ, "query_failed": True})
            continue
        if result.get("exceededTransferLimit"):
            raise RuntimeError("COOLR result transfer limit reached; need pagination.")
        rows = []
        for feature in result.get("features", []):
            a = feature["attributes"]
            row = {"catalogue": "NASA_COOLR_Reports_" + typ, "catalogue_query_url": source, **a,
                   "geometry": feature.get("geometry"), "catalogue_event_date_epoch_as_utc": iso_epoch(a.get("event_date")),
                   "submitted_date_epoch_as_utc": iso_epoch(a.get("submitted_date")), "last_edited_date_epoch_as_utc": iso_epoch(a.get("last_edited_date")),
                   "event_time_zone_verified": None, "raw_primary_source_reviewed": False, "approved_training_label": False,
                   "review_status": "Candidate only. NASA is catalogue publisher; underlying media/personal sources are not automatically primary observation evidence.",
                   "available_time_verified": None, "physical_mechanism_compatible_with_ice_rock_cascade": None}
            rows.append(row)
        tables += rows
        queries.append({"geometry_type": typ, "number_returned": len(rows), "transfer_limit_exceeded": False})
    save_json(OUT / "historical_candidates.json", {"generated_at_utc": utc_now(), "bbox": CATALOG_AOI, "query_summary": queries, "candidate_rows": len(tables), "accepted_independent_training_events": 0,
        "policy": "Candidates are not accepted labels; mechanism, original source, timezone, duplicate hazard-chain grouping and reporting completeness must be reviewed. Non-reports are not negative labels.", "records": tables})
    return queries


def worldcover_crop(collector):
    """Read only required classic-TIFF Deflate blocks, then write a small GeoTIFF.

    The assertions deliberately reject unknown encodings, rather than silently
    interpreting another TIFF layout. No interpolation or classification occurs.
    """
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    header, rec = collector.fetch("worldcover_tiff_header.bin", WORLD, headers={"Range": "bytes=0-65535"}, max_bytes=65536)
    if rec.get("http_status") != 206 or not header.startswith(b"II*\x00"):
        raise RuntimeError("WorldCover endpoint did not provide the expected bounded classic TIFF range.")
    ifd = struct.unpack_from("<I", header, 4)[0]
    count = struct.unpack_from("<H", header, ifd)[0]
    tags = {}
    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 12: 8}
    fmts = {1: "B", 3: "H", 4: "I", 12: "d"}
    for idx in range(count):
        offset = ifd + 2 + idx * 12
        tag, dtype, length, value = struct.unpack_from("<HHII", header, offset)
        size = sizes[dtype] * length
        start = offset + 8 if size <= 4 else value
        assert start + size <= len(header), "TIFF tag payload outside bounded header; expand deliberately if needed."
        tags[tag] = header[start:start + size] if dtype == 2 else struct.unpack_from("<" + fmts[dtype] * length, header, start)
    assert tags[258] == (8,) and tags[259] == (8,) and tags[277] == (1,) and tags[317] == (1,)
    width, height = tags[256][0], tags[257][0]
    tw, th = tags[322][0], tags[323][0]
    scale, tie = tags[33550], tags[33922]
    dx, dy = scale[:2]
    west, north = tie[3], tie[4]
    assert abs(west - 84) < 1e-8 and abs(north - 30) < 1e-8 and width == height == 36000
    c0, c1 = math.floor((AOI[0] - west) / dx), math.ceil((AOI[2] - west) / dx)
    r0, r1 = math.floor((north - AOI[3]) / dy), math.ceil((north - AOI[1]) / dy)
    crop = np.zeros((r1 - r0, c1 - c0), dtype=np.uint8)
    block_info = []
    ncol = math.ceil(width / tw)
    for br in range(r0 // th, (r1 - 1) // th + 1):
        for bc in range(c0 // tw, (c1 - 1) // tw + 1):
            bi = br * ncol + bc
            offset, size = tags[324][bi], tags[325][bi]
            compressed, block_rec = collector.fetch("worldcover_block_%04d.bin" % bi, WORLD, headers={"Range": f"bytes={offset}-{offset + size - 1}"}, max_bytes=size)
            if block_rec.get("http_status") != 206 or len(compressed) != size:
                raise RuntimeError("A WorldCover range block was incomplete.")
            raw = zlib.decompress(compressed)
            assert len(raw) == tw * th
            block = np.frombuffer(raw, dtype=np.uint8).reshape(th, tw)
            rr0, rr1 = max(r0, br * th), min(r1, (br + 1) * th)
            cc0, cc1 = max(c0, bc * tw), min(c1, (bc + 1) * tw)
            crop[rr0-r0:rr1-r0, cc0-c0:cc1-c0] = block[rr0-br*th:rr1-br*th, cc0-bc*tw:cc1-bc*tw]
            block_info.append({"block_index": bi, "offset": offset, "compressed_bytes": size})
    transform = from_origin(west + c0 * dx, north - r0 * dy, dx, dy)
    target = OUT / "worldcover_2021_v200_test_aoi.tif"
    with rasterio.open(target, "w", driver="GTiff", height=crop.shape[0], width=crop.shape[1], count=1, dtype="uint8", crs="EPSG:4326", transform=transform, nodata=0, compress="deflate") as dest:
        dest.write(crop, 1)
        dest.update_tags(source_url=WORLD, source_year="2021", algorithm_version="v200", aoi_role="NC pipeline test; source area not confirmed", resampling="none; source-grid aligned crop")
        palette = tags.get(320)
        if palette:
            dest.write_colormap(1, {i: (int(palette[i] / 257), int(palette[256+i] / 257), int(palette[512+i] / 257), 255 if i else 0) for i in range(256)})
    with rasterio.open(target) as check:
        back = check.read(1)
        assert np.array_equal(back, crop)
        counts = Counter(map(int, crop.ravel()))
        details = {"source_url": WORLD, "source_product": "ESA WorldCover 2021 v200 N27E084 Map", "source_year": 2021, "algorithm_version": "v200", "source_full_object_bytes": int(rec["response_headers"]["Content-Range"].split("/")[-1]), "source_last_modified": rec["response_headers"].get("Last-Modified"),
                   "source_crs": "EPSG:4326", "source_shape": [height, width], "source_pixel_degrees": [dx, dy], "requested_bounds_w_s_e_n": AOI,
                   "actual_pixel_aligned_bounds_w_s_e_n": list(check.bounds), "crop_shape": list(crop.shape), "crop_dtype": "uint8", "nodata": check.nodata,
                   "class_counts": [{"code": k, "label": LABELS.get(k, "UNKNOWN"), "pixels": v} for k, v in sorted(counts.items())], "valid_pixels": int((crop != 0).sum()), "valid_fraction": float((crop != 0).mean()),
                   "downloaded_source_range_bytes": 65536 + sum(x["compressed_bytes"] for x in block_info), "range_blocks": block_info, "crop_file": str(target.relative_to(OUT)), "crop_bytes": target.stat().st_size, "crop_sha256": sha(target.read_bytes()),
                   "readback_equal": True, "reprojection_performed": False, "resampling": "none; future category alignment must use nearest-neighbor", "suitable_role": "Historical spatial background and cross-border data pipeline test; not 2026 land-cover observation, source proof or independent glacier validation."}
    save_json(OUT / "worldcover_crop_summary.json", details)
    return details


def make_manifest():
    excluded = {"manifest.json"}
    records = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name not in excluded:
            records.append({"path": str(path.relative_to(OUT)), "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())})
    save_json(OUT / "manifest.json", {"generated_at_utc": utc_now(), "files": records})


def verify_only():
    manifest = json.loads((OUT / "manifest.json").read_text())
    errors = []
    for item in manifest["files"]:
        path = OUT / item["path"]
        if not path.exists() or path.stat().st_size != item["bytes"] or sha(path.read_bytes()) != item["sha256"]:
            errors.append(item["path"])
    print(json.dumps({"manifest_files_checked": len(manifest["files"]), "errors": errors}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--skip-worldcover", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify_only()
        return
    run_dir = OUT / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    collector = Collector(run_dir)
    reading = collect_events(collector)
    scene_queries, scene_count = collect_scenes(collector)
    historical_queries = collect_historical_candidates(collector)
    worldcover = None
    worldcover_error = None
    if not args.skip_worldcover:
        try:
            worldcover = worldcover_crop(collector)
        except Exception as exc:
            worldcover_error = {"error_type": type(exc).__name__, "error": str(exc)}
            save_json(run_dir / "worldcover_error.json", worldcover_error)
    summary = {"generated_at_utc": utc_now(), "run_directory": str(run_dir.relative_to(OUT)), "aoi_bounds": AOI, "aoi_role": "Unconfirmed NC footprint, pipeline test only", "scene_count": scene_count, "scene_queries": scene_queries, "historical_queries": historical_queries, "accepted_independent_historical_training_events": 0, "jms_pdf_downloaded": reading["download_success"], "jms_pages": reading.get("pages"), "worldcover_crop_success": worldcover is not None, "worldcover_error": worldcover_error,
               "network_responses": len(collector.records), "saved_response_body_bytes": sum(r["saved_bytes"] for r in collector.records), "http_failures": [{"name": r["name"], "status": r.get("http_status"), "error": r.get("error")} for r in collector.records if not r.get("successful_status")],
               "ai_assistance": "AI assisted source discovery, bounded API retrieval, provenance registry and data pipeline verification. No fitted model, causal inference, threshold, hazard forecast or accepted training catalogue generated. Human team must review adopted evidence and cite sources.", "original_files_modified": False, "account_registration_or_payment": False, "credentials_used": False}
    save_json(OUT / "summary.json", summary)
    make_manifest()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
