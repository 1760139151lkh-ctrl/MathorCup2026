"""Freeze pre-increment tracked bytes without modifying earlier research artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    existing = HERE / "baseline_bindings.json"
    if existing.exists():
        binding = json.loads(existing.read_text())
        for row in binding["files"]:
            path = ROOT / row["path"]
            assert path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], row["path"]
        print(json.dumps({"existing_frozen_baseline_verified": len(binding["files"])}))
        return
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode().split("\0")
    rows = []
    for rel in tracked:
        if not rel or rel.startswith("track_b/research/q2/round3/lab_strength/"):
            continue
        path = ROOT / rel
        rows.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha(path)})
    out = {
        "increment_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "scope": "Every pre-existing tracked file; increment subtree excluded",
        "files": rows,
        "files_count": len(rows),
        "protocol_sha256": sha(HERE / "PROTOCOL.md"),
    }
    (HERE / "baseline_bindings.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"files": len(rows), "base": out["increment_base_commit"]}))


if __name__ == "__main__":
    main()
