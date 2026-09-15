"""Tests for structured and human-readable completion-plan actions."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plan_actions.py"


class PlanActionsTests(unittest.TestCase):
    def write_inputs(self, root, actions, document):
        backlog = root / "backlog.json"
        backlog.write_text(json.dumps({
            "schema_version": 1,
            "packages": [{"id": package_id, "next_action": action}
                          for package_id, action in actions.items()],
        }) + "\n")
        work_packages = root / "work-packages.md"
        work_packages.write_text(document)
        return backlog, work_packages

    def run_plan_actions(self, backlog, work_packages, *extra):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--backlog", str(backlog),
             "--work-packages", str(work_packages), *extra],
            capture_output=True, text=True)

    def test_validate_reports_structured_and_human_action_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backlog, work_packages = self.write_inputs(
                root, {"A": "Do A", "B": "Do B"},
                "## A: Alpha\n\n**Next action:** Wrong A\n\n"
                "**Completion gate:** Keep this text.\n\n"
                "## B: Beta\n\n**Next action:** Do B\n")
            result = self.run_plan_actions(backlog, work_packages)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("action mismatch for A", result.stderr)

    def test_sync_replaces_only_action_text_and_validate_accepts_multiline_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_suffix = "\n**Completion gate:** Preserve this exact text.\n\nTail.\n"
            backlog, work_packages = self.write_inputs(
                root, {"A": "First line\nSecond line", "B": "Do B"},
                "Preamble.\n\n## A: Alpha\n\n**Next action:** Old A\n" +
                original_suffix + "\n## B: Beta\n\n**Next action:** Do B\n")
            result = self.run_plan_actions(backlog, work_packages, "--sync")
            self.assertEqual(result.returncode, 0, result.stderr)
            updated = work_packages.read_text()
            self.assertIn("Preamble.\n\n", updated)
            self.assertIn("**Next action:** First line\nSecond line\n", updated)
            self.assertIn(original_suffix, updated)
            self.assertIn("## B: Beta\n\n**Next action:** Do B\n", updated)
            validated = self.run_plan_actions(backlog, work_packages)
            self.assertEqual(validated.returncode, 0, validated.stderr)

    def test_sync_multiline_eof_action_preserves_missing_final_newline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backlog, work_packages = self.write_inputs(
                root, {"A": "First line\nSecond line"},
                "## A: Alpha\n\n**Next action:** Old A")
            result = self.run_plan_actions(backlog, work_packages, "--sync")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(work_packages.read_bytes(),
                             b"## A: Alpha\n\n**Next action:** First line\nSecond line")
            validated = self.run_plan_actions(backlog, work_packages)
            self.assertEqual(validated.returncode, 0, validated.stderr)

    def test_sync_existing_multiline_eof_action_preserves_missing_final_newline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backlog, work_packages = self.write_inputs(
                root, {"A": "First line\nSecond line"},
                "## A: Alpha\n\n**Next action:** Old first\nOld second")
            result = self.run_plan_actions(backlog, work_packages, "--sync")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(work_packages.read_bytes(),
                             b"## A: Alpha\n\n**Next action:** First line\nSecond line")
            validated = self.run_plan_actions(backlog, work_packages)
            self.assertEqual(validated.returncode, 0, validated.stderr)

    def test_validate_rejects_missing_or_duplicate_headings_and_action_slots(self):
        cases = [
            ("missing package heading", "## A: Alpha\n\n**Next action:** Do A\n",
             "missing package heading: B"),
            ("duplicate package heading", "## A: Alpha\n\n**Next action:** Do A\n\n"
             "## A: Again\n\n**Next action:** Do A\n\n## B: Beta\n\n"
             "**Next action:** Do B\n", "duplicate package heading: A"),
            ("missing action slot", "## A: Alpha\n\n**Completion gate:** Gate.\n\n"
             "## B: Beta\n\n**Next action:** Do B\n", "missing Next action slot: A"),
            ("duplicate action slot", "## A: Alpha\n\n**Next action:** Do A\n\n"
             "**Next action:** Again\n\n## B: Beta\n\n**Next action:** Do B\n",
             "duplicate Next action slot: A"),
        ]
        for label, document, expected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                backlog, work_packages = self.write_inputs(
                    root, {"A": "Do A", "B": "Do B"}, document)
                before = work_packages.read_bytes()
                result = self.run_plan_actions(backlog, work_packages, "--sync")
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)
                self.assertEqual(work_packages.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
