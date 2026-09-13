"""Tests for explicit selected-artifact binding verification."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
VERIFY = SCRIPTS / "verify_artifact_bindings.py"
sys.path.insert(0, str(SCRIPTS))
import artifact_bindings  # noqa: E402
sys.path.pop(0)


class ArtifactBindingTests(unittest.TestCase):
    def binding_file(self, root, bindings):
        path = root / "bindings.json"
        path.write_text(json.dumps({"bindings": bindings}, indent=2) + "\n")
        return path

    def test_valid_binding_reports_verified_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "current.json"
            artifact.write_bytes(b"current")
            binding = {"path": "current.json", "sha256": hashlib.sha256(b"current").hexdigest(), "bytes": 7}
            report = artifact_bindings.verify(self.binding_file(root, [binding]), root)
            self.assertTrue(report["valid"])
            self.assertEqual(report["verified"][0]["path"], "current.json")

    def test_hash_mismatch_identifies_selected_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "old.json"
            artifact.write_bytes(b"old")
            binding = {"path": "old.json", "sha256": hashlib.sha256(b"new").hexdigest()}
            report = artifact_bindings.verify(self.binding_file(root, [binding]), root)
            self.assertFalse(report["valid"])
            self.assertEqual(report["mismatches"][0]["reason"], "sha256_mismatch")

    def test_missing_file_is_structured_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = artifact_bindings.verify(self.binding_file(root, [{"path": "missing", "sha256": "0" * 64}]), root)
            self.assertFalse(report["valid"])
            self.assertEqual(report["mismatches"][0]["reason"], "missing")

    def test_size_mismatch_is_structured_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact"
            artifact.write_bytes(b"1234")
            report = artifact_bindings.verify(self.binding_file(root, [{"path": "artifact", "sha256": hashlib.sha256(b"1234").hexdigest(), "bytes": 5}]), root)
            self.assertFalse(report["valid"])
            self.assertEqual(report["mismatches"][0]["reason"], "bytes_mismatch")

    def test_explicit_absolute_path_is_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = Path(temporary).parent / (Path(temporary).name + "-external")
            artifact.write_bytes(b"external")
            binding = {"path": str(artifact), "sha256": hashlib.sha256(b"external").hexdigest()}
            report = artifact_bindings.verify(self.binding_file(root, [binding]), root)
            self.assertTrue(report["valid"])

    def test_cli_refuses_existing_output_without_changing_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binding = self.binding_file(root, [])
            output = root / "report.json"
            original = b"accepted report\n"
            output.write_bytes(original)
            result = subprocess.run([sys.executable, "-B", str(VERIFY), "--root", str(root), "--bindings", str(binding), "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), original)
            self.assertIn("output_exists", result.stdout)

    def test_cli_writes_report_and_returns_nonzero_for_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binding = self.binding_file(root, [{"path": "missing", "sha256": "0" * 64}])
            output = root / "report.json"
            result = subprocess.run([sys.executable, "-B", str(VERIFY), "--root", str(root), "--bindings", str(binding), "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(output.read_text())["valid"], False)


if __name__ == "__main__":
    unittest.main()
