"""Tests for strict native-membership validation and the Blender fixture."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "scripts" / "native_readback.py"
LAUNCHER = ROOT / "scripts" / "run_native_readback.py"
FIXTURE = Path(__file__).with_name("native_readback_fixture.py")
SPEC = importlib.util.spec_from_file_location("native_readback", NATIVE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeReadbackTests(unittest.TestCase):
    def membership(self, model_sha):
        return {"room_id": "fixture-room", "model_sha256": model_sha,
                "groups": {"architecture": {"target_names": ["Fixture mesh", "Fixture excluded mesh"]},
                            "services": {"target_names": ["Fixture curve"]},
                            "empty": {"target_names": ["Fixture empty mesh"]}},
                "counts": {"total_native_targets": 4}}

    def write_membership(self, directory, data):
        path = directory / "membership.json"
        path.write_text(json.dumps(data, indent=2) + "\n")
        return path

    def test_strict_membership_rejects_duplicate_and_missing_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = self.membership("0" * 64)
            duplicate = json.loads(json.dumps(valid))
            duplicate["groups"]["services"]["target_names"] = ["Fixture mesh"]
            duplicate["counts"]["total_native_targets"] = 3
            with self.assertRaisesRegex(ValueError, "duplicate"):
                MODULE.validate_membership(self.write_membership(root, duplicate))
            missing = json.loads(json.dumps(valid))
            missing["groups"]["empty"]["target_names"] = [""]
            with self.assertRaisesRegex(ValueError, "nonempty"):
                MODULE.validate_membership(self.write_membership(root, missing))

    def test_model_hash_guard_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary) / "model.blend"
            model.write_bytes(b"fixture")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                MODULE.validate_model_hash(model, "0" * 64)

    @unittest.skipUnless(os.environ.get("SCAN_TO_MODEL_BLENDER"), "set SCAN_TO_MODEL_BLENDER for Blender integration")
    def test_actual_blender_readback_includes_excluded_parented_curve_and_empty_mesh(self):
        blender = Path(os.environ["SCAN_TO_MODEL_BLENDER"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blend = root / "fixture.blend"
            subprocess.run([str(blender), "-b", "--python-exit-code", "1", "--python", str(FIXTURE), "--", "--blend", str(blend)], check=True, capture_output=True, text=True)
            model_sha = hashlib.sha256(blend.read_bytes()).hexdigest()
            membership = self.write_membership(root, self.membership(model_sha))
            output = root / "readback"
            launch_environment = os.environ.copy()
            launch_environment["SCAN_TO_MODEL_TEST_SECRET_SENTINEL"] = "must-not-be-persisted"
            result = subprocess.run([sys.executable, "-B", str(LAUNCHER), "--blender", str(blender), "--blend", str(blend), "--membership", str(membership), "--output", str(output)], env=launch_environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            readback = json.loads((output / "native-readback.json").read_text())
            self.assertEqual(readback["target_count"], 4)
            rows = {row["name"]: row for row in readback["objects"]}
            self.assertEqual(rows["Fixture empty mesh"]["vertices_local_m"], [])
            self.assertEqual(rows["Fixture empty mesh"]["polygons"], [])
            self.assertIsNone(rows["Fixture empty mesh"]["bounds_world_m"])
            self.assertEqual(rows["Fixture mesh"]["parent_chain"], ["Fixture parent"])
            self.assertEqual(rows["Fixture mesh"]["vertices_world_m"][0], [2.0, 3.0, 4.0])
            self.assertEqual(rows["Fixture mesh"]["visibility"]["hide_viewport"], True)
            self.assertEqual(rows["Fixture mesh"]["visibility"]["hide_render"], True)
            self.assertEqual(readback["temporary_visibility_overrides"], [{
                "name": "Fixture mesh", "hide_viewport": True, "hide_render": True,
                "restored_after_capture": True,
            }])
            self.assertIn("Fixture excluded", rows["Fixture excluded mesh"]["collections"])
            self.assertGreater(len(rows["Fixture curve"]["vertices_world_m"]), 0)
            self.assertGreater(len(rows["Fixture curve"]["polygons"]), 0)
            for row in rows.values():
                self.assertTrue(row["guard"]["present_in_depsgraph"])
                self.assertTrue(row["guard"]["is_evaluated"])
                self.assertTrue(row["guard"]["original_identity_matches"])
            receipt = json.loads((output / "launch-receipt.json").read_text())
            self.assertEqual(receipt["status"], "pass")
            self.assertTrue(all(receipt["checks"].values()))
            self.assertEqual(receipt["before"]["model_sha256"], model_sha)
            self.assertEqual(hashlib.sha256(blend.read_bytes()).hexdigest(), model_sha)
            self.assertNotIn("SCAN_TO_MODEL_TEST_SECRET_SENTINEL", receipt["environment_overrides"])
            self.assertEqual(set(receipt["environment_overrides"]), {
                "SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT", "TMPDIR",
                "SCAN_TO_MODEL_NATIVE_OUTPUT", "SCAN_TO_MODEL_NATIVE_MEMBERSHIP"})

            missing = self.membership(model_sha)
            missing["groups"]["architecture"]["target_names"][0] = "Fixture absent"
            missing_output = root / "missing-target"
            missing_membership = root / "missing-membership.json"
            missing_membership.write_text(json.dumps(missing, indent=2) + "\n")
            missing_result = subprocess.run([sys.executable, "-B", str(LAUNCHER), "--blender", str(blender), "--blend", str(blend), "--membership", str(missing_membership), "--output", str(missing_output)], capture_output=True, text=True)
            self.assertEqual(missing_result.returncode, 1, missing_result.stderr + missing_result.stdout)
            self.assertEqual(json.loads((missing_output / "launch-receipt.json").read_text())["status"], "fail")

            nonconvertible = self.membership(model_sha)
            nonconvertible["groups"]["architecture"]["target_names"][0] = "Fixture parent"
            nonconvertible_membership = root / "nonconvertible-membership.json"
            nonconvertible_membership.write_text(json.dumps(nonconvertible, indent=2) + "\n")
            nonconvertible_result = subprocess.run([sys.executable, "-B", str(LAUNCHER), "--blender", str(blender), "--blend", str(blend), "--membership", str(nonconvertible_membership), "--output", str(root / "nonconvertible-target")], capture_output=True, text=True)
            self.assertEqual(nonconvertible_result.returncode, 1, nonconvertible_result.stderr + nonconvertible_result.stdout)


if __name__ == "__main__":
    unittest.main()
