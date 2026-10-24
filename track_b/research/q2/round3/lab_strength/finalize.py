"""Finalize an evidence-only increment; never mutate earlier R3 artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
R3 = HERE.parent
PREFIX = HERE.relative_to(ROOT).as_posix() + "/"
EXPECTED_BASE = "a4a034eb3a93ae93d9ffb3852a0d7e13eabd2231"
BUNDLES = (
    "mechanism_bundle.json", "release_bundle.json", "release_bundle_v2.json", "mechanism_bundle_v2.json",
    "numerical_supplement_bundle.json", "composition_bundle.json", "analytic_thermal_bundle.json",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def entry(path, role):
    path = Path(path)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path), "role": role}


def verify_record(row):
    path = ROOT / row["path"]
    assert path.resolve().is_relative_to(ROOT), row["path"]
    assert path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], row["path"]


def run():
    checks = []
    def check(name, evidence):
        checks.append({"name": name, "passed": True, "evidence": evidence})

    assert ROOT == Path("/Users/maxchen/Documents/MathorCup/worktrees/track-b-q2")
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == "codex/track-b-q2-r3"
    subprocess.run(["git", "merge-base", "--is-ancestor", EXPECTED_BASE, "HEAD"], cwd=ROOT, check=True)
    baseline = read(HERE / "baseline_bindings.json")
    assert baseline["increment_base_commit"] == EXPECTED_BASE and baseline["files_count"] == 1104
    for row in baseline["files"]:
        verify_record(row)
    check("all_pre_increment_tracked_bytes_unchanged", len(baseline["files"]))

    previous_manifest = read(R3 / "output_manifest.json")
    assert previous_manifest["file_count"] == 220
    for row in previous_manifest["files"]:
        verify_record(row)
    check("original_220_R3_output_artifacts_unchanged", 220)
    preserved = []
    for name in BUNDLES:
        path = R3 / "exports" / name
        bundle = read(path)
        for row in bundle["files"]:
            verify_record(row)
        preserved.append(entry(path, "earlier_core_bundle_read_only"))
    check("seven_earlier_bundles_and_all_bound_members_unchanged", preserved)

    changed = set()
    for cmd in (["git", "diff", "--name-only", "-z", EXPECTED_BASE, "HEAD"], ["git", "diff", "--name-only", "-z", "HEAD"], ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        changed.update(x for x in subprocess.check_output(cmd, cwd=ROOT).decode().split("\0") if x)
    assert all(path.startswith(PREFIX) for path in changed), sorted(changed)
    check("all_new_writes_within_lab_strength_only", len(changed))
    workspace = read(HERE / "workspace_verification.json")
    assert workspace["passed"] and len(workspace["checks"]) == 5 and all(x["passed"] for x in workspace["checks"])
    assert workspace["increment_report_redirect"]["actual_report"] == str(HERE / "workspace_verification.json")
    check("original_five_workspace_checks_with_safe_report_redirect", [x["name"] for x in workspace["checks"]])

    audit = read(HERE / "audit/results/input_record.json")
    source = {"path": audit["source_zip_path"], "bytes": audit["source_zip_bytes"], "sha256": audit["source_zip_sha256"]}
    verify_record(source)
    with zipfile.ZipFile(ROOT / source["path"]) as archive:
        for row in audit["workbook_members"]:
            body = archive.read(row["member"])
            assert len(body) == row["bytes"] and hashlib.sha256(body).hexdigest() == row["sha256"]
    check("original_zip_and_two_complete_xlsx_member_hashes", audit)
    for manifest_name in ("audit/results/output_index.json", "literature/literature_output_manifest.json"):
        manifest = read(HERE / manifest_name)
        for row in manifest.get("files", manifest.get("output_files", [])):
            verify_record(row)
    check("canonical_and_literature_subpacket_manifests", ["25 audit members", "28 literature members"])

    observations = pd.read_csv(HERE / "audit/results/observations.csv")
    summaries = pd.read_csv(HERE / "audit/results/coefficient_strata.csv")
    assert len(observations) == 141 and len(summaries) == 14 and observations.observation_id.is_unique
    assert observations.independent_landslide_events.sum() == 0
    assert observations.physical_specimen_id.isna().all()
    assert np.isfinite(observations[["temperature_at_failure_c", "normal_stress_at_failure_kpa", "peak_shear_kpa"]]).all().all()
    check("complete_observations_units_identity_and_zero_local_events", {"tests": 141, "derived_strata": 14, "physical_UID": "unknown"})

    review = read(HERE / "independent_review/review.json")
    assert review["outcome"] == "pass" and len(review["checks"]) == 17 and all(c["passed"] for c in review["checks"])
    for row in review["bindings"]:
        verify_record(row)
    check("independent_17_numerical_checks_current_bindings", entry(HERE / "independent_review/review.json", "independent_review"))

    config = read(HERE / "model/results/run_config.json")
    assert config["code_sha256"] == sha(HERE / "model/competition.py")
    assert config["data_sha256"] == sha(HERE / "audit/results/observations.csv")
    assert config["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    assert config["protocol_amendment_sha256"] == sha(HERE / "PROTOCOL_AMENDMENT.md")
    assert baseline["protocol_sha256"] == config["protocol_sha256"]
    check("pre_fit_protocol_inputs_and_code_bound", config)
    summary = read(HERE / "model/results/run_summary.json")
    assert summary["new_fits"] == 32 and summary["fixed_author_references"] == 4
    assert summary["holdout_fits"] == 576 and summary["holdout_predictions"] == 8796
    assert summary["bootstrap_attempts"] == 32000 and summary["bootstrap_usable"] == 31994 and summary["bootstrap_failed_rank_or_nonfinite"] == 6
    assert summary["models_not_automatically_selected"] and not summary["local_models_modified"]
    check("full_competition_holdout_and_uncertainty_completed", summary)

    folds = pd.read_csv(HERE / "model/results/holdout_folds.csv")
    assert (folds.status != "full_rank").sum() == 6
    assert not (folds.model == "author_eq6").any()
    author_summary = read(HERE / "model/author_results/run_summary.json")
    assert author_summary["stage2_fits"] == 84
    check("published_reference_not_mixed_with_CV_and_rank_failures_visible", {"rank_failed_folds": 6, "published_CV_folds": 0, "author_stage2_descriptive_fits": 84})

    visual = read(HERE / "visual_review.json")
    assert len(visual["files"]) == 5 and visual["actual_review_performed"]
    for row in visual["files"]:
        verify_record(row)
    assert len(list((HERE / "figures").glob("*.png"))) == 5 and len(list((HERE / "figures").glob("*.pdf"))) == 5
    check("five_final_pngs_actually_viewed_current_hashes", visual)

    old_input_version = previous_manifest["input_version"]
    sources = [
        (R3 / "sources/strength/mamot2018_supplement.zip", "Read only ZIP; only two XLSX data members fully parsed in this increment"),
        (R3 / "sources/strength/mamot2018_article.pdf", "Literature reviewer opened listed source pages; exact scope in literature_input_audit"),
        (R3 / "sources/strength/mamot2018_supplement.pdf", "Literature reviewer opened listed source pages; exact scope in literature_input_audit"),
        (R3 / "sources/strength/mamot2018_article_extracted.txt", "Read methods and evidence sections; no new acquisition"),
        (R3 / "sources/strength/mamot2018_supplement_extracted.txt", "Read test matrix, units and source context"),
        (R3 / "sources/strength/source_register.json", "Original acquisition provenance retained; new XLSX reading scope in this increment"),
        (ROOT / "track_b/requirements-lock.txt", "Original exact environment lock unchanged"),
        (ROOT / "track_b/audit/stage4/round3/baseline_manifest.json", "Original shared input baseline unchanged"),
        (R3 / "output_manifest.json", "Original 220 artifacts retained"),
    ]
    inputs = {
        "input_version": {**old_input_version, "increment_base_commit": EXPECTED_BASE},
        "files": [entry(p, role) for p, role in sources],
        "zip_members": audit["workbook_members"],
        "separate_derived_inputs": [entry(HERE / "audit/results/observations.csv", "141 source rows normalized with cell provenance"), entry(HERE / "audit/results/coefficient_strata.csv", "14 author-derived summaries, never extra tests")],
        "earlier_core_bundles_read_only": preserved, "self_entry": False,
    }
    save("input_manifest.json", inputs)
    result_index = {
        "version": "q2-r3-lab-strength-evidence-v1", "producer_question": "q2", "event_id": None,
        "event_id_null_reason": "External laboratory test series, not additional local disaster chains",
        "physical_phase": "external_laboratory_peak_shear_failure", "time_utc": None,
        "time_uncertainty": {"status": "not_a_local_event_clock", "test_durations": "source seconds retained; no conversion to local onset"},
        "space_object": {"id": "external_Wetterstein_limestone_rock_ice_laboratory", "crs": None, "reason": "laboratory specimens, not mapped local source geometry"},
        "variable_semantics": {"temperature": "measured rock temperature at failure °C", "sigma": "area-corrected laboratory normal stress kPa", "tau": "peak shear stress kPa", "grouping": "nominal classes; actual columns used for fitting", "qc_policy": "all141 rows; no deletion or imputation; 14 summaries not double counted"},
        "available_time": None, "available_time_note": "Article public2018-10-17; cached2026 acquisition exists; no historical operational availability claim",
        "forecast_reference_time": None, "issue_time": None, "valid_time": None,
        "data_role": "exploration", "laboratory_roles": ["calibration", "group_holdout_evaluation", "source_reproduction"],
        "input_version": inputs["input_version"], "evidence_status": "external_laboratory_not_locally_validated",
        "independent_local_events": 0, "models_or_probabilities_updated": False,
        "entrypoints": ["REPORT.md", "REPRODUCE.md", "audit/results/audit_report.json", "model/results/decision_summary.json", "independent_review/REVIEW.md"],
        "important_limits": ["unknown physical specimen UID and eight recurring labels", "published Eq6 same-table reference is descriptive", "selected warm source relations use different temperature layers", "no automatic effective-stress transfer", "conditional mean intervals not event probabilities or verified95percent coverage"],
    }
    save("result_index.json", result_index)
    save("validation.json", {"passed": True, "check_groups": len(checks), "checks": checks,
                             "scope": "Integrity, source audit and implementation verification; not model adoption or local-event validation",
                             "unresolved_scientific_limits": result_index["important_limits"]})
    excluded = {"output_manifest.json", "bundle.json", "HANDOFF.md"}
    files = [path for path in HERE.rglob("*") if path.is_file() and path.name not in excluded and "__pycache__" not in path.parts and path.suffix != ".pyc" and path.name != ".DS_Store"]
    manifest = {"version": "q2-r3-lab-strength-outputs-v1", "input_version": inputs["input_version"], "files": [entry(path, "lab_strength_increment_artifact") for path in sorted(files)],
                "file_count": len(files), "excluded": ["self", "bundle.json hashes this manifest", "HANDOFF.md bound by Git", "Python cache"], "self_entry": False}
    save("output_manifest.json", manifest)
    bundle = {**result_index, "bundle_version": "q2-r3-lab-strength-v1", "release_role": "evidence_increment_no_existing_model_replacement",
              "files": [entry(HERE / name, name) for name in ("input_manifest.json", "output_manifest.json", "result_index.json", "validation.json", "REPORT.md", "REPRODUCE.md")],
              "member_resolution": "output_manifest lists all remaining lab_strength payload files by repository-relative paths; no self entry",
              "earlier_seven_bundles_unchanged": preserved}
    save("bundle.json", bundle)
    for row in manifest["files"] + bundle["files"]:
        verify_record(row)
    print(json.dumps({"passed": True, "check_groups": len(checks), "new_output_files": len(files), "previous_artifacts_verified": 220,
                      "bundle_sha256": sha(HERE / "bundle.json"), "output_manifest_sha256": sha(HERE / "output_manifest.json")}, ensure_ascii=False))


if __name__ == "__main__":
    run()
