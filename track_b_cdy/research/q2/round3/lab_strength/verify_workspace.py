"""Call the original five-group verifier with only its report redirected.

The original standard command overwrites a previously released report. This
wrapper leaves all pre-increment bytes unchanged and uses the same operations.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
spec = importlib.util.spec_from_file_location("stage4_workspace", ROOT / "track_b/scripts/stage4_workspace.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
original_save = module.save


def redirected_save(path, value):
    assert path == ROOT / "track_b/research/q2/round3/workspace_verification.json"
    value["increment_report_redirect"] = {
        "reason": "Preserve pre-increment report bound by all seven earlier bundles",
        "actual_report": str(HERE / "workspace_verification.json"),
    }
    original_save(HERE / "workspace_verification.json", value)


module.save = redirected_save
args = argparse.Namespace(
    question="q2", round="round3", expected_root=str(ROOT),
    expected_base="904d7257b899b9f71d1ac9e0eab7479e459eab52", pristine=False,
)
code = module.verify(args)
print("Actual increment report: " + str(HERE / "workspace_verification.json"))
raise SystemExit(code)
