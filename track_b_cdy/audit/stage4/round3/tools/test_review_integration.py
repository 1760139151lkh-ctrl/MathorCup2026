"""Targeted integrity/path-policy tests; temporary fixtures, no research runs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("review_integration", Path(__file__).with_name("review_integration.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ManifestPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.packet = self.root / "track_b/research/q1/round3"
        self.packet.mkdir(parents=True)
        self.cache = self.base / "cache/round3"
        (self.cache / "q1").mkdir(parents=True)
        self.allowed = audit.cache_roots(self.cache, "q1", output=True)
        self.manifest = self.packet / "output_manifest.json"

    def row(self, path, name=None):
        data = path.read_bytes()
        return {"path": str(name or path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def write_manifest(self, rows):
        self.manifest.write_text(json.dumps({"files": rows}))

    def check(self):
        return audit.manifest_check(self.root, self.packet, self.manifest, self.allowed, output=True)

    def test_streamed_cache_reference_and_packet_relative_reference(self):
        large = self.cache / "q1/tile.bin"
        large.write_bytes(b"hash fixture\x00" * 400_000)  # > 5 MB; remains outside Git.
        local = self.packet / "result.txt"
        local.write_text("complete")
        self.write_manifest([self.row(large), self.row(local, "result.txt")])
        result = self.check()
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["referenced_bytes"], large.stat().st_size + 8)
        large.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Size mismatch"):
            self.check()

    def test_self_entry_rejected_before_digest(self):
        self.write_manifest([{"path": "output_manifest.json", "bytes": 0, "sha256": "0" * 64}])
        with self.assertRaisesRegex(ValueError, "Self-entry"):
            self.check()

    def test_absolute_outside_and_symlink_escape_rejected(self):
        outside = self.base / "private.bin"
        outside.write_bytes(b"private")
        self.write_manifest([self.row(outside)])
        with self.assertRaisesRegex(ValueError, "outside approved cache"):
            self.check()
        (self.packet / "escape.bin").symlink_to(outside)
        self.write_manifest([self.row(outside, "escape.bin")])
        with self.assertRaisesRegex(ValueError, "escapes repository"):
            self.check()

    def test_foreign_cache_requires_explicit_adoption_and_output_forbids_it(self):
        foreign = self.cache / "q2/v1"
        foreign.mkdir(parents=True)
        item = foreign / "state.csv"
        item.write_text("state")
        self.write_manifest([self.row(item)])
        with self.assertRaisesRegex(ValueError, "outside approved cache"):
            self.check()
        approved = {"accepted_cache_roots": [str(foreign)]}
        result = audit.manifest_check(self.root, self.packet, self.manifest,
                                      audit.cache_roots(self.cache, "q1", approved))
        self.assertEqual(result["file_count"], 1)
        with self.assertRaisesRegex(ValueError, "outside approved cache"):
            audit.manifest_check(self.root, self.packet, self.manifest,
                                 audit.cache_roots(self.cache, "q1", approved, output=True), output=True)

    def test_ambiguous_relative_target_and_multiple_list_schemas_rejected(self):
        (self.root / "same.txt").write_text("root")
        local = self.packet / "same.txt"
        local.write_text("packet")
        self.write_manifest([self.row(local, "same.txt")])
        with self.assertRaisesRegex(ValueError, "Ambiguous or missing"):
            self.check()
        with self.assertRaisesRegex(ValueError, "Ambiguous file-list schema"):
            audit.file_rows({"files": [], "entries": []})
        self.assertEqual(audit.file_rows([]), [])

    def test_parent_traversal_and_duplicate_resolved_reference_rejected(self):
        local = self.packet / "result.txt"
        local.write_text("yes")
        self.write_manifest([self.row(local, "../round3/result.txt")])
        with self.assertRaisesRegex(ValueError, "Parent traversal"):
            self.check()
        self.write_manifest([self.row(local, "result.txt"),
                             self.row(local, "track_b/research/q1/round3/result.txt")])
        with self.assertRaisesRegex(ValueError, "Duplicate resolved"):
            self.check()

    def test_missing_final_fields_are_incomplete(self):
        with self.assertRaisesRegex(audit.Incomplete, "missing final registry fields"):
            audit.final_workspace(self.root, {"question": "q1"}, {}, {})


if __name__ == "__main__":
    unittest.main()
