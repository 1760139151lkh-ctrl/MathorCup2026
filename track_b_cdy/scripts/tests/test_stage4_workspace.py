"""Round isolation checks use disposable Git repositories, never project inputs."""
from contextlib import redirect_stdout
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'stage4_workspace', Path(__file__).resolve().parents[1] / 'stage4_workspace.py')
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


class WorkspaceRoundTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        for attribute, value in (
                ('ROOT', self.root),
                ('MANIFEST', self.root / 'track_b/audit/stage4/baseline_manifest.json')):
            replacement = patch.object(workspace, attribute, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Round isolation test')
        self.git('config', 'user.email', 'round-test@example.invalid')
        fixtures = {
            '04_B赛道/source.txt': 'original input\n',
            'track_b/data/processed/input.txt': 'prepared input\n',
            'track_b/scripts/shared.py': '# shared script\n',
            'track_b/config/shared.json': '{}\n',
            'track_b/requirements-lock.txt': 'example==1\n',
            'track_b/audit/stage3/check.json': '{}\n',
            'track_b/audit/stage4/baseline_manifest.json': '{"old": true}\n',
            'track_b/audit/stage4/workspaces.json': '{}\n',
            'track_b/audit/stage4/round2/baseline_manifest.json': '{"old": true}\n',
            'track_b/audit/stage4/round3/baseline_manifest.json': '{"old": true}\n',
            'track_b/research/AGENTS.md': 'research contract\n',
            'track_b/research/q1/results/round1.json': '{"round": 1}\n',
            'track_b/research/q1/workspace_verification.json': '{"historical": true}\n',
            'track_b/research/q2/results/round1.json': '{"round": 1}\n',
            'track_b/research/q1/round2/existing.json': '{"round": 2}\n',
            'track_b/research/q2/round2/existing.json': '{"round": 2}\n',
            'track_b/research/q1/round3/existing.json': '{"round": 3}\n',
            'track_b/research/q2/round3/existing.json': '{"round": 3}\n',
            # Deliberately tracked to exercise exclusion even if ignores change.
            'track_b/research/q1/.cache/old.txt': 'cache\n',
        }
        for name, content in fixtures.items():
            self.write(name, content)
        self.commit('fixture preparation')
        self.preparation = self.git('rev-parse', 'HEAD')

    def git(self, *arguments):
        return subprocess.check_output(
            ['git', '-C', str(self.root), *arguments], text=True).strip()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def commit(self, message):
        self.git('add', '--all')
        self.git('commit', '-qm', message)

    def snapshot(self, round_name=None):
        with redirect_stdout(io.StringIO()):
            if round_name is None:
                workspace.snapshot(self.preparation)
            else:
                workspace.snapshot(self.preparation, round_name)
        return json.loads(workspace.manifest_path(round_name or 'round1').read_text())

    def published(self, round_name='round2'):
        self.snapshot(round_name)
        self.commit('publish manifest')
        return self.git('rev-parse', 'HEAD')

    def run_verify(self, round_name=None, **overrides):
        arguments = dict(question='q1', expected_root=str(self.root),
                         expected_base=self.git('rev-parse', 'HEAD'), pristine=False)
        if round_name is not None:
            arguments['round'] = round_name
        arguments.update(overrides)
        output = io.StringIO()
        with patch.object(workspace, 'environment', return_value={'fixture': True}), \
                patch.object(workspace, 'formats', return_value={'fixture': True}), \
                redirect_stdout(output):
            status = workspace.verify(argparse.Namespace(**arguments))
        return status, json.loads(output.getvalue())

    def test_round1_default_manifest_and_function_compatibility(self):
        result = self.snapshot()
        self.assertEqual(result['contract_version'], 'stage4-r1-v1')
        self.assertEqual(workspace.manifest_path(), workspace.MANIFEST)
        self.assertFalse(any(item['path'].startswith('track_b/research/') for item in result['files']))
        integrity = workspace.input_integrity()
        self.assertEqual(integrity['file_count'], result['file_count'])

    def test_round1_default_responsibility_retains_full_question_directory(self):
        self.write('track_b/research/q1/new.txt', 'allowed\n')
        self.write('track_b/research/q1/round2/new.txt', 'also previously allowed\n')
        result = workspace.responsibility('q1', self.preparation)
        self.assertEqual(result['allowed_directory'], 'track_b/research/q1/')
        self.assertEqual(len(result['changed_paths']), 2)

    def test_round2_snapshot_freezes_round1_but_never_itself_or_round2_outputs(self):
        historical = workspace.MANIFEST.read_bytes()
        result = self.snapshot('round2')
        self.assertEqual(result['contract_version'], 'stage4-r2-v1')
        paths = {item['path'] for item in result['files']}
        self.assertIn('track_b/research/q1/results/round1.json', paths)
        self.assertIn('track_b/research/q2/results/round1.json', paths)
        self.assertIn('track_b/research/q1/workspace_verification.json', paths)
        self.assertFalse(any('/round2/' in name or '/.cache/' in name for name in paths))
        self.assertFalse(any(name.startswith('track_b/audit/stage4/') for name in paths))
        self.assertEqual(workspace.MANIFEST.read_bytes(), historical)
        # Repeated snapshots still exclude an already-present manifest.
        self.assertEqual(self.snapshot('round2')['files'], result['files'])
        self.assertEqual(workspace.input_integrity('round2')['file_count'], len(paths))

    def test_snapshot_rejects_working_input_drift_from_git_blob(self):
        self.write('track_b/research/q1/results/round1.json', '{"round": 9}\n')
        with self.assertRaisesRegex(ValueError, 'differs from preparation commit'):
            self.snapshot('round2')

    def test_integrity_detects_frozen_round1_input_drift(self):
        self.snapshot('round2')
        self.write('track_b/research/q1/results/round1.json', '{"round": 9}\n')
        with self.assertRaisesRegex(ValueError, 'Frozen input mismatch'):
            workspace.input_integrity('round2')

    def test_integrity_checks_manifest_git_blob_against_preparation_commit(self):
        self.snapshot('round2')
        name = 'track_b/research/q1/results/round1.json'
        changed = self.write(name, '{"round": 9}\n').read_bytes()
        manifest = workspace.manifest_path('round2')
        value = json.loads(manifest.read_text())
        entry = next(item for item in value['files'] if item['path'] == name)
        entry.update(bytes=len(changed), sha256=hashlib.sha256(changed).hexdigest(),
                     git_blob=self.git('hash-object', name))
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'Frozen input mismatch'):
            workspace.input_integrity('round2')

    def test_integrity_rejects_wrong_round_contract(self):
        self.snapshot('round2')
        path = workspace.manifest_path('round2')
        value = json.loads(path.read_text())
        value['contract_version'] = 'stage4-r1-v1'
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'contract version'):
            workspace.input_integrity('round2')

    def test_round2_responsibility_accepts_only_own_round2_changes(self):
        self.write('track_b/research/q1/round2/new.txt', 'new work\n')
        self.commit('own round2 change')
        self.write('track_b/research/q1/round2/untracked.txt', 'untracked work\n')
        result = workspace.responsibility('q1', self.preparation, 'round2')
        self.assertEqual(result['allowed_directory'], 'track_b/research/q1/round2/')
        self.assertEqual(len(result['changed_paths']), 2)

    def test_round2_rejects_round1_edits(self):
        self.write('track_b/research/q1/results/round1.json', '{}\n')
        with self.assertRaisesRegex(ValueError, 'outside assigned folder'):
            workspace.responsibility('q1', self.preparation, 'round2')

    def test_round2_rejects_other_question_edits(self):
        self.write('track_b/research/q2/round2/existing.json', '{}\n')
        with self.assertRaisesRegex(ValueError, 'outside assigned folder'):
            workspace.responsibility('q1', self.preparation, 'round2')

    def test_round2_rename_cannot_hide_removal_of_frozen_round1_file(self):
        self.git('config', 'diff.renames', 'true')
        self.git('mv', 'track_b/research/q1/results/round1.json',
                 'track_b/research/q1/round2/moved.json')
        self.commit('move frozen input')
        with self.assertRaisesRegex(ValueError, 'outside assigned folder'):
            workspace.responsibility('q1', self.preparation, 'round2')

    def test_round2_verify_writes_new_report_and_preserves_old_report(self):
        base = self.published()
        historical = (self.root / 'track_b/research/q1/workspace_verification.json').read_bytes()
        status, result = self.run_verify('round2', expected_base=base, pristine=True)
        self.assertEqual(status, 0)
        report = self.root / 'track_b/research/q1/round2/workspace_verification.json'
        self.assertEqual(result['report'], str(report))
        self.assertEqual(json.loads(report.read_text())['round'], 'round2')
        self.assertEqual((self.root / 'track_b/research/q1/workspace_verification.json').read_bytes(), historical)

    def test_round1_verify_old_namespace_and_report_are_compatible(self):
        self.published('round1')
        status, result = self.run_verify()
        self.assertEqual(status, 0)
        self.assertEqual(result['report'], str(self.root / 'track_b/research/q1/workspace_verification.json'))

    def test_failed_integrity_still_writes_only_assigned_round2_report(self):
        self.published()
        self.write('track_b/data/processed/input.txt', 'drift\n')
        status, result = self.run_verify('round2')
        self.assertEqual(status, 1)
        self.assertFalse(result['passed'])
        self.assertEqual(result['report'], str(self.root / 'track_b/research/q1/round2/workspace_verification.json'))

    def test_wrong_workspace_root_never_writes_a_report(self):
        historical = (self.root / 'track_b/research/q1/workspace_verification.json').read_bytes()
        status, result = self.run_verify('round2', expected_root=str(self.root / 'wrong'))
        self.assertEqual(status, 1)
        self.assertIsNone(result['report'])
        self.assertFalse((self.root / 'track_b/research/q1/round2/workspace_verification.json').exists())
        self.assertEqual((self.root / 'track_b/research/q1/workspace_verification.json').read_bytes(), historical)

    def test_invalid_question_cannot_escape_report_directory(self):
        status, result = self.run_verify('round2', question='../q2')
        self.assertEqual(status, 1)
        self.assertIsNone(result['report'])

    def test_symlink_to_other_question_cannot_redirect_failure_report(self):
        report = self.root / 'track_b/research/q1/round2/workspace_verification.json'
        other = self.root / 'track_b/research/q2/round2/protected.json'
        self.write(str(other.relative_to(self.root)), 'keep\n')
        report.symlink_to(other)
        status, result = self.run_verify('round2')
        self.assertEqual(status, 1)
        self.assertIsNone(result['report'])
        self.assertEqual(other.read_text(), 'keep\n')

    def test_cli_snapshot_round_argument_defaults_and_explicit_selection(self):
        for arguments, expected_round in (([], 'round1'), (['--round', 'round2'], 'round2'),
                                          (['--round', 'round3'], 'round3')):
            with self.subTest(round=expected_round), \
                    patch('sys.argv', ['stage4_workspace.py', 'snapshot', '--preparation-commit', 'HEAD', *arguments]), \
                    patch.object(workspace, 'snapshot') as operation:
                self.assertEqual(workspace.main(), 0)
                operation.assert_called_once_with('HEAD', expected_round)

    def test_cli_verify_round2_selection(self):
        arguments = ['stage4_workspace.py', 'verify', '--question', 'q3',
                     '--round', 'round2', '--expected-root', str(self.root),
                     '--expected-base', self.preparation]
        with patch('sys.argv', arguments), patch.object(workspace, 'verify', return_value=0) as operation:
            self.assertEqual(workspace.main(), 0)
        self.assertEqual(getattr(operation.call_args.args[0], 'round'), 'round2')

    def test_round3_paths_select_new_manifest_and_question_directory(self):
        self.assertEqual(workspace.manifest_path('round3'),
                         self.root / 'track_b/audit/stage4/round3/baseline_manifest.json')
        self.assertEqual(workspace.question_directory('q4', 'round3'),
                         self.root / 'track_b/research/q4/round3')

    def test_round3_snapshot_freezes_prior_research_without_overwriting_old_manifests(self):
        old_manifests = {name: workspace.manifest_path(name).read_bytes()
                         for name in ('round1', 'round2')}
        result = self.snapshot('round3')
        self.assertEqual(result['contract_version'], 'stage4-r3-v1')
        paths = {item['path'] for item in result['files']}
        for name in ('q1/results/round1.json', 'q2/results/round1.json',
                     'q1/round2/existing.json', 'q2/round2/existing.json',
                     'q1/workspace_verification.json'):
            self.assertIn('track_b/research/' + name, paths)
        self.assertFalse(any('/round3/' in name or '/.cache/' in name for name in paths))
        self.assertFalse(any(name.startswith('track_b/audit/stage4/') for name in paths))
        self.assertEqual(self.snapshot('round3')['files'], result['files'])
        self.assertEqual(workspace.input_integrity('round3')['file_count'], len(paths))
        for name, historical in old_manifests.items():
            self.assertEqual(workspace.manifest_path(name).read_bytes(), historical)

    def test_round3_snapshot_excludes_tracked_caches_and_environments_from_prior_rounds(self):
        for component in ('__pycache__', '.cache', '.pytest_cache', '.venv',
                          'venv', '.tox', '.mypy_cache', '.ruff_cache'):
            self.write(f'track_b/research/q1/round2/{component}/tracked.txt', 'not input\n')
        self.commit('tracked cache fixture')
        self.preparation = self.git('rev-parse', 'HEAD')
        result = self.snapshot('round3')
        self.assertFalse(any(item['path'].endswith('/tracked.txt') for item in result['files']))

    def test_round3_integrity_detects_frozen_round2_input_drift(self):
        self.snapshot('round3')
        self.write('track_b/research/q2/round2/existing.json', '{"round": 9}\n')
        with self.assertRaisesRegex(ValueError, 'Frozen input mismatch'):
            workspace.input_integrity('round3')

    def test_round3_snapshot_rejects_round2_working_drift_from_preparation_commit(self):
        self.write('track_b/research/q1/round2/existing.json', '{"round": 9}\n')
        with self.assertRaisesRegex(ValueError, 'differs from preparation commit'):
            self.snapshot('round3')

    def test_round3_responsibility_accepts_only_own_round3_changes(self):
        self.write('track_b/research/q1/round3/new.txt', 'new work\n')
        self.commit('own round3 change')
        self.write('track_b/research/q1/round3/untracked.txt', 'untracked work\n')
        result = workspace.responsibility('q1', self.preparation, 'round3')
        self.assertEqual(result['allowed_directory'], 'track_b/research/q1/round3/')
        self.assertEqual(len(result['changed_paths']), 2)

    def test_round3_rejects_round1_edits(self):
        self.write('track_b/research/q1/results/round1.json', '{}\n')
        with self.assertRaisesRegex(ValueError, 'outside assigned folder'):
            workspace.responsibility('q1', self.preparation, 'round3')

    def test_round3_rejects_round2_edits(self):
        self.write('track_b/research/q1/round2/existing.json', '{}\n')
        with self.assertRaisesRegex(ValueError, 'outside assigned folder'):
            workspace.responsibility('q1', self.preparation, 'round3')

    def test_round3_rejects_other_question_edits(self):
        self.write('track_b/research/q2/round3/existing.json', '{}\n')
        with self.assertRaisesRegex(ValueError, 'outside assigned folder'):
            workspace.responsibility('q1', self.preparation, 'round3')

    def test_round3_verify_writes_new_report_preserving_both_prior_reports(self):
        self.write('track_b/research/q1/round2/workspace_verification.json',
                   '{"historical_round": 2}\n')
        self.commit('prior round2 verification fixture')
        self.preparation = self.git('rev-parse', 'HEAD')
        base = self.published('round3')
        reports = [self.root / 'track_b/research/q1' / name for name in
                   ('workspace_verification.json', 'round2/workspace_verification.json')]
        old_reports = [path.read_bytes() for path in reports]
        status, result = self.run_verify('round3', expected_base=base, pristine=True)
        self.assertEqual(status, 0)
        report = self.root / 'track_b/research/q1/round3/workspace_verification.json'
        self.assertEqual(result['report'], str(report))
        self.assertEqual(json.loads(report.read_text())['round'], 'round3')
        self.assertEqual([path.read_bytes() for path in reports], old_reports)

    def test_cli_verify_round3_selection(self):
        arguments = ['stage4_workspace.py', 'verify', '--question', 'q4',
                     '--round', 'round3', '--expected-root', str(self.root),
                     '--expected-base', self.preparation]
        with patch('sys.argv', arguments), patch.object(workspace, 'verify', return_value=0) as operation:
            self.assertEqual(workspace.main(), 0)
        self.assertEqual(getattr(operation.call_args.args[0], 'round'), 'round3')


if __name__ == '__main__':
    unittest.main()
