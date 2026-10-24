"""Offline, bounded evidence-table reproduction; never execute downloaded code."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import h5netcdf

ROOT = Path(__file__).resolve().parents[5]
PACKET = ROOT / "track_b/research/q2/round2"
SOURCES = PACKET / "sources"
RESULT = PACKET / "results/velocity_definition_chain.csv"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    binding = json.loads((PACKET / "workspace_binding.json").read_text())
    assert ROOT == Path(binding["execution_root"]).resolve()
    baseline = ROOT / binding["manifest"]
    assert digest(baseline) == binding["manifest_sha256"]
    registry = json.loads((SOURCES / "velocity_source_register.json").read_text())
    for source in registry["sources"]:
        assert digest(ROOT / source["saved_path"]) == source["sha256"]
    for source in registry["local_inputs_used"]:
        assert digest(ROOT / source["path"]) == source["sha256"]

    nc = next((ROOT / "04_B赛道/04_冰川地形、冰厚及表面速度").glob("*.nc"))
    with h5netcdf.File(nc, "r") as ds:
        assert set(ds.dimensions) == {"x", "y"}
        assert ds.attrs["velocity_source"] == "ITS_LIVE v2.1"
        assert ds.attrs["velocity_resampling"] == "bilinear to the 30 m reference grid"
        for variable in ("vx", "vy", "v"):
            assert ds.variables[variable].attrs["units"] == "meter/year"
        for variable in ("vx", "vy"):
            assert "2014-2024" in ds.variables[variable].attrs["description"]
            assert "January 1, 2018" in ds.variables[variable].attrs["description"]
    code = (SOURCES / "velocity_itslive_composite.py").read_text()
    assert "default=str(list(range(2014, 2025)))" in code
    assert "default='2018/01/01'" in code
    assert "v = np.sqrt(vx0**2 + vy0**2)" in code
    assert "offset = np.average(v[valid], weights=w_v)" in code
    qa = json.loads((ROOT / "track_b/data/processed/spatial/pipeline_report.json").read_text())
    for variable in ("vx", "vy", "v"):
        assert qa["netcdf"]["variable_decode_checks"][variable]["raw_and_decoded_equal_nan"] is True
    residual = json.loads((ROOT / "track_b/research/q2/results/input_check.json").read_text())["velocity_arithmetic_consistency"]

    input_version = {
        "baseline_commit": binding["common_baseline_commit"],
        "baseline_manifest_sha256": binding["manifest_sha256"],
        "local_nc_sha256": digest(nc),
        "official_source_code_commit": "8a39afbd8279d94c4b1d3e7b99b722527f66a85c",
        "source_register_sha256": digest(SOURCES / "velocity_source_register.json"),
    }
    shared = {
        "input_version": input_version,
        "event_id": "B20260826_Chhochen",
        "physical_phase": "background",
        "time_utc": None,
        "time_uncertainty": None,
        "space_object": {
            "id": "NC_parameter_domain_not_failure_geometry",
            "crs": "EPSG:32645",
            "resolution_m": 30,
            "positional_uncertainty": None,
            "velocity_vector_frame_verified": False,
        },
        "variable_semantics": {
            "units": "meter/year for stored velocities and seasonal amplitudes",
            "qc_policy": "raw preserved; finite is not quality acceptance; provenance unresolved",
            "statistical_period_local_claim": [2014, 2024],
            "statistical_intercept_date_local_claim": "2018-01-01",
            "accumulation_window": None,
            "transformations_this_review": "none; metadata and source-text inspection only",
        },
        "available_time": None,
        "forecast_reference_time": None,
        "issue_time": None,
        "valid_time": None,
        "data_role": "exploration",
        "null_reason": "Not a dated event observation/forecast; original availability, positional error and cell-wise uncertainty unverified.",
    }
    # Statements below are manually reviewed evidence summaries. The checks above
    # bind them to local inputs and exact source snapshots, without recomputing
    # the first-round table or importing upstream production modules.
    entries = [
        ("V01", "local_nc_definition", "local_fact", "adoptable_with_explicit_role", "vx/vy are declared climatological 2014-2024, weighted line fit to annual components at 2018-01-01; units meter/year; no time dimension", "local_nc attributes; audit/spatial/netcdf.json", "Metadata declaration does not authenticate source object or event state", "Use only as declared historical background"),
        ("V02", "local_nc_v_definition", "local_fact", "adoptable_with_explicit_role", "Stored v declares hypotenuse of vx/vy at the climatological intercept; v_amp declares seasonal amplitude along mean flow", "local_nc attributes", "Stored v does not pass first-round arithmetic identity screen", "Retain all original fields separately"),
        ("V03", "official_composite_defaults", "external_source", "adoptable_with_explicit_role", "Pinned NASA/JPL code defaults to 2014..2024 and intercept 2018/01/01", "velocity_itslive_composite.py:3485-3496", "Current code snapshot is not the local file's established production version", "Use as official definition context, not local execution provenance"),
        ("V04", "official_component_statistics", "external_source", "adoptable_with_explicit_role", "Annual component estimates selected by climatology years are weighted-line-fit into offsets; magnitude is sqrt(vx0**2+vy0**2) after component fitting", "velocity_itslive_composite.py:1012-1028,1222-1315", "Composite stage only; subsequent mosaic/reprojection and local preprocessing not established", "Reject interpretation as simple arithmetic mean of scalar annual speeds"),
        ("V05", "official_fit_fallback", "external_source", "adoptable_with_explicit_role", "Pinned code falls back to weighted mean of available component estimates with trend NaN if valid observations do not bracket intercept", "velocity_itslive_composite.py:1408-1489", "Local annual estimates/errors/counts/trends absent; cell-wise branch unknown", "Do not promise every local cell has a well-supported linear trend fit"),
        ("V06", "local_to_official_name_mapping", "inference", "unknown_with_evidence_and_next_action", "Local vx/vy/v climatological descriptions agree semantically with upstream vx0/vy0/v0; field rename is not proven", "velocity_itslive_mosaics_types.py:102-176; local_nc attributes", "Missing exact original object and maker script", "Request original object metadata and field mapping log"),
        ("V07", "nsidc_version_boundary", "external_source", "adoptable_with_explicit_role", "NSIDC v2 guide published/updated July 2025 documents 2014-2022 climatology, 2018 intercept and 120m products", "velocity_nsidc_v2_userguide.pdf Table 2; Sections 1,2.2,7", "Guide is not proof of locally declared v2.1 / 2014-2024 release", "Retain version distinction"),
        ("V08", "nsidc_legacy_code_boundary", "external_source", "adoptable_with_explicit_role", "Pinned NSIDC conversion script still hardcodes static period 2014-2022; cannot certify a 2014-2024 local object", "velocity_nsidc_mosaics_v2.py:80-89,461-471", "NSIDC delivery branch differs from composite defaults", "Do not merge version labels based on name similarity"),
        ("V09", "local_bilinear_claim", "local_fact", "adoptable_with_explicit_role", "NC global attribute says bilinear to the 30m reference grid", "local_nc velocity_resampling", "Original object/native grid/coordinate rotation/masking/magnitude order absent", "Call 30m target spacing, not native 30m monitoring resolution"),
        ("V10", "local_maker_chain_search", "local_fact", "unknown_with_evidence_and_next_action", "Supplied velocity folder contains only one NC; no maker script or native-object URL in supplied documents and shared scripts", "repository supplied-B filename inventory; source_documentation.json; local_nc attributes", "Conclusion limited to delivered repository materials", "Find exact native object ID and creation log before attributing residual cause"),
        ("V11", "stage3_read_chain", "local_fact", "adoptable_with_explicit_role", "prepare_spatial reads/sorts supplied NC; QA confirms raw/decoded equality for vx/vy/v; exports NC DEM/mask and resamples separate DEM, not velocity", "scripts/prepare_spatial.py:272-326; pipeline_report.json netcdf.variable_decode_checks", "Stage3 provenance cannot reconstruct supplier's NC creation", "Exclude stage3 velocity resampling as cause"),
        ("V12", "first_round_residual", "local_fact", "adoptable_with_explicit_role", json.dumps(residual, ensure_ascii=False, sort_keys=True), "research/q2/results/input_check.json velocity_arithmetic_consistency; not recomputed", "Arithmetic tolerance is not physical uncertainty or a trigger threshold", "Retain stored v/vx/vy and discrepancy flag"),
        ("V13", "residual_cause", "unverified", "unknown_with_evidence_and_next_action", "Magnitude/interpolation noncommutativity or averaging/mosaic order remain hypotheses; no local creation evidence proves any cause", "local maker chain missing; official code describes only identifiable upstream stages", "Cannot apportion discrepancy to interpolation, statistics, rotation or other processing", "Inspect exact creation order and a few matched native cells; no automatic correction"),
        ("V14", "vector_coordinate_frame", "unverified", "unknown_with_evidence_and_next_action", "NC spatial geometry is EPSG32645; original velocity CRS and actual component rotation into target frame are not recorded", "local_nc spatial_ref; velocity_nsidc_v2_userguide.pdf Section 2.2.2", "Map grid CRS alone does not authenticate velocity-vector basis", "Q4 must not accept vx/vy as event initial direction without rotation provenance"),
        ("V15", "event_dynamic_use", "inference", "excluded_with_reason", "Existing climatological fields and seasonal amplitudes do not supply 2026 acceleration, mechanical initiation time or release initial velocity", "local_nc no time dimension; background declarations", "No event-time velocity sequence, verified release polygon or event calibration", "Q4 initial velocity remains scenario/unknown pending separate evidence"),
        ("V16", "minimum_followup", "candidate", "unknown_with_evidence_and_next_action", "Need exact native object URL/version/hash, maker script or parameter log, native/target CRS and rotation, statistics/mosaic/magnitude/resampling order, nodata/error/count conventions", "missing-local-chain findings; verified official definitions", "No new dataset download or author contact executed", "Obtain minimal metadata and bounded matched cells only in a later authorized task"),
    ]
    fields = list(shared) + ["evidence_id", "chain_step", "evidence_status", "outcome", "finding", "source_locator", "limitation", "next_action"]
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    with RESULT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for ident, step, status, outcome, finding, source, limitation, action in entries:
            row = dict(shared)
            row.update(evidence_id=ident, chain_step=step, evidence_status=status, outcome=outcome, finding=finding, source_locator=source, limitation=limitation, next_action=action)
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) or v is None else v for k, v in row.items()})
    print(json.dumps({"offline_checks_passed": True, "rows": len(entries), "output": str(RESULT.relative_to(ROOT)), "sha256": digest(RESULT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
