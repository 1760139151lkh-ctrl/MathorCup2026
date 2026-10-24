#!/usr/bin/env python3
"""Parser/integrity fixtures use temporary directories, never scientific data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import subprocess

import build_evidence as evidence
import build_program_appendix as programs
import build_references as references
import verify_paper


class PaperToolsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mathorcup-paper-tools-")
        self.repo = Path(self.temp.name)
        self.paper = self.repo / "track_b/paper"
        (self.paper / "evidence").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return path

    def test_source_hash_and_explicit_json_check(self):
        source = self.write("research/numbers.json", {"n": 13, "fraction": 3 / 13})
        sha = evidence.digest(source)
        self.write("track_b/paper/evidence/q1_claims.json", {"claims": [{
            "claim_id": "fixture-count", "value": 13,
            "source_files": [{"path": "research/numbers.json", "sha256": sha}],
            "checks": [{"source_path": "research/numbers.json", "json_pointer": "/n", "expected": 13}]}]})
        index, report = evidence.build(self.paper, self.repo)
        self.assertTrue(report["passed"])
        self.assertEqual(report["explicit_value_check_count"], 1)
        self.assertEqual(index["claims"][0]["checks"][0]["actual"], 13)
        source.write_text('{"n": 14}', encoding="utf-8")
        _, report = evidence.build(self.paper, self.repo)
        self.assertFalse(report["passed"])
        self.assertTrue(any("source hash" in issue for issue in report["issues"]))

    def test_csv_selection_requires_one_row(self):
        self.write("research/r.csv", "group,score\na,0.25\nb,0.5\n")
        check = {"source_path": "research/r.csv", "column": "score", "where": {"group": "b"}, "expected": 0.5}
        self.assertTrue(evidence.check_value(check, self.repo, {"research/r.csv"})["passed"])
        check["where"] = {}
        self.assertFalse(evidence.check_value(check, self.repo, {"research/r.csv"})["passed"])

    def test_public_claims_are_explicitly_included_without_generated_index(self):
        source = self.write("research/public.json", '{"count":11}')
        self.write("track_b/paper/evidence/public_claims.json", {"claims": [{
            "claim_id": "public-count", "value": 11,
            "source_files": [{"path": "research/public.json", "sha256": evidence.digest(source)}],
            "checks": [{"source_path": "research/public.json", "json_pointer": "/count", "expected": 11}]}]})
        self.write("track_b/paper/evidence/claim_index.json", {"claims": [{"claim_id": "must-not-be-reimported"}]})
        index, report = evidence.build(self.paper, self.repo)
        self.assertTrue(report["passed"])
        self.assertEqual([r["claim_id"] for r in index["claims"]], ["public-count"])
        self.assertEqual(report["explicit_value_check_count"], 1)
        self.assertEqual(report["input_files"], ["evidence/public_claims.json"])

    def test_first_citation_expands_inputs_at_position(self):
        self.write("track_b/paper/main.tex", r"\cite{common-a}\input{sections/q1}\cite{q1-second}")
        self.write("track_b/paper/sections/q1.tex", r"Text\cite{q1-first,common-a}")
        self.write("track_b/paper/evidence/q1_references.tex", r"\bibitem{q1-second} Second." + "\n" + r"\bibitem{q1-first} First.")
        self.write("track_b/paper/evidence/common_references.tex", r"\bibitem{common-a} Common.")
        text, report = references.build(self.paper)
        self.assertTrue(report["passed"])
        self.assertEqual(report["citation_order"], ["common-a", "q1-first", "q1-second"])
        self.assertLess(text.index("q1-first"), text.index("q1-second"))

    def test_reference_conflict_and_missing_citation_fail(self):
        self.write("track_b/paper/main.tex", r"\cite{same,missing}")
        self.write("track_b/paper/evidence/q1_references.tex", r"\bibitem{same} One.")
        self.write("track_b/paper/evidence/q2_references.tex", r"\bibitem{same} Different.")
        _, report = references.build(self.paper)
        self.assertFalse(report["passed"])
        self.assertEqual(report["missing_keys"], ["missing"])
        self.assertEqual(report["conflicting_keys"], ["same"])

    def test_complete_program_and_third_party_index(self):
        source = self.write("research/real_source.py", '# 中文说明\nprint("a_b%")\nroot="/Users/fixture/research"\n')
        original = source.read_bytes()
        self.write("track_b/paper/evidence/q1_code_files.json", {"code_files": [{"path": "research/real_source.py", "title": "A_B & C%"}],
                   "third_party": [{"name": "External", "version": "1.0"}]})
        text, report = programs.build(self.paper, self.repo)
        self.assertTrue(report["passed"])
        self.assertEqual(report["programs"][0]["sha256"], hashlib.sha256(original).hexdigest())
        self.assertIn(r"A\_B \& C\%", text)
        self.assertIn("code_print/research/real_source.py", text)
        self.assertEqual(report["programs"][0]["path_anonymization_count"], 1)
        display, count = programs.anonymize_paths(original)
        self.assertIn(b"<LOCAL_HOME>/research", display)
        self.assertNotIn(b"/Users/fixture", display)
        self.assertEqual(count, 1)
        self.assertIn("External", text)
        self.assertEqual(source.read_bytes(), original)

    def test_reject_source_escape_and_parse_main_page_label(self):
        with self.assertRaises(ValueError):
            evidence.repository_path(self.repo, "../outside.txt")
        aux = self.write("track_b/paper/main.aux", r"\newlabel{LastMainPage}{{7}{29}{AI声明}{section.7}{}}")
        self.assertEqual(verify_paper.last_main_page(aux), 29)
        aux.write_text(r"\newlabel{Other}{{1}{2}}", encoding="utf-8")
        self.assertIsNone(verify_paper.last_main_page(aux))

    def test_history_protects_research_but_allows_paper_changes(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.repo, text=True, capture_output=True, check=True).stdout.strip()
        git("init", "-q")
        self.write("track_b/research/q1/result.json", '{"count":13}\n')
        self.write("track_b/paper/main.tex", "Draft\n")
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Fixture baseline")
        baseline = git("rev-parse", "HEAD")
        self.write("track_b/paper/main.tex", "Revised draft\n")
        self.assertTrue(verify_paper.history_integrity(self.repo, baseline)["passed"])
        self.write("track_b/research/q1/result.json", '{"count":14}\n')
        report = verify_paper.history_integrity(self.repo, baseline)
        self.assertFalse(report["passed"])
        self.assertEqual(report["changed_protected_paths"], ["track_b/research/q1/result.json"])


if __name__ == "__main__":
    unittest.main()
