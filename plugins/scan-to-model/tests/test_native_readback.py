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
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "scripts" / "native_readback.py"
LAUNCHER = ROOT / "scripts" / "run_native_readback.py"
FIXTURE = Path(__file__).with_name("native_readback_fixture.py")
SPEC = importlib.util.spec_from_file_location("native_readback", NATIVE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
LAUNCHER_SPEC = importlib.util.spec_from_file_location("run_native_readback", LAUNCHER)
LAUNCHER_MODULE = importlib.util.module_from_spec(LAUNCHER_SPEC)
sys.path.insert(0, str(ROOT / "scripts"))
LAUNCHER_SPEC.loader.exec_module(LAUNCHER_MODULE)
sys.path.pop(0)


class MappingLike:
    """Small stand-in for Blender's mapping-like IDPropertyGroup."""

    def __init__(self, values):
        self.values = values

    def items(self):
        return self.values.items()

    def __iter__(self):
        return iter(self.values)


class FakeBpy:
    class types:
        ID = type("ID", (), {})


class NativeReadbackTests(unittest.TestCase):
    def test_blender_command_uses_factory_startup_and_two_threads(self):
        command = LAUNCHER_MODULE.blender_command(
            Path("/opt/blender"), Path("scene.blend"), Path("runtime.py"), Path("worker.py"))
        self.assertEqual(command, [
            "/opt/blender", "-b", "--factory-startup", "--disable-autoexec", "--threads", "2",
            "--python-exit-code", "1", "--python", "runtime.py", "scene.blend",
            "--python", "worker.py"])

    def test_prepare_runtime_freezes_bootstrap_and_returns_isolated_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            membership = root / "membership.json"
            worker = root / "worker.py"
            runtime_helper = root / "runtime.py"
            launcher = root / "launcher.py"
            membership.write_text("membership")
            worker.write_text("worker")
            runtime_helper.write_text("runtime")
            launcher.write_text("launcher")
            output = root / "readback"
            with patch.dict(os.environ, {"SCAN_TO_MODEL_TEST_SENTINEL": "inherited"}):
                prepared = LAUNCHER_MODULE.prepare_runtime(
                    output, membership, source_launcher=launcher, worker=worker,
                    runtime_helper=runtime_helper)
            runtime = output / "runtime-01"
            self.assertEqual(prepared["runtime"], runtime)
            self.assertTrue((runtime / "tmp").is_dir())
            self.assertEqual((runtime / "membership.json").read_text(), "membership")
            self.assertEqual((runtime / "native_readback.py").read_text(), "worker")
            self.assertEqual((runtime / "blender_runtime.py").read_text(), "runtime")
            self.assertEqual((runtime / "run_native_readback.py").read_text(), "launcher")
            self.assertEqual(prepared["environment"]["TMPDIR"], str(runtime / "tmp"))
            self.assertEqual(prepared["environment"]["SCAN_TO_MODEL_TEST_SENTINEL"], "inherited")
            self.assertEqual(set(prepared["environment_overrides"]), {
                "SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT", "TMPDIR",
                "SCAN_TO_MODEL_NATIVE_OUTPUT", "SCAN_TO_MODEL_NATIVE_MEMBERSHIP"})
            self.assertEqual(prepared["environment_overrides"]["SCAN_TO_MODEL_NATIVE_OUTPUT"], str(output))

    def membership(self, model_sha):
        return {"room_id": "fixture-room", "model_sha256": model_sha,
                "groups": {"architecture": {"target_names": ["Fixture mesh", "Fixture beveled cube", "Fixture excluded mesh"]},
                            "services": {"target_names": ["Fixture curve"]},
                            "empty": {"target_names": ["Fixture empty mesh"]}},
                "counts": {"total_native_targets": 5}}

    def write_membership(self, directory, data):
        path = directory / "membership.json"
        path.write_text(json.dumps(data, indent=2) + "\n")
        return path

    def write_fake_blender(self, directory, version_returncode=0):
        path = directory / "fake-blender.py"
        script = r"""#!/usr/bin/env python3
import hashlib
import json
import os
import sys
from pathlib import Path

log = Path(os.environ["FAKE_BLENDER_LOG"])
with log.open("ab") as stream:
    stream.write((" ".join(sys.argv[1:]) + "\n").encode())
if sys.argv[1:] == ["--version"]:
    sys.stdout.buffer.write(b"Blender fake version\n")
    sys.stderr.buffer.write(b"version diagnostic \xff\n")
    raise SystemExit(__VERSION_EXIT__)
if "-b" in sys.argv:
    membership_path = Path(os.environ["SCAN_TO_MODEL_NATIVE_MEMBERSHIP"])
    membership = json.loads(membership_path.read_text())
    names = [name for group in membership["groups"].values() for name in group["target_names"]]
    readback = {
        "schema_version": 4,
        "model_sha256": membership["model_sha256"],
        "membership_sha256": hashlib.sha256(membership_path.read_bytes()).hexdigest(),
        "room_id": membership["room_id"],
        "requested_target_count": len(names),
        "target_count": len(names),
        "objects": [{"name": name} for name in names],
        "groups": {
            group: {"target_count": len(spec["target_names"]),
                    "target_names": spec["target_names"]}
            for group, spec in membership["groups"].items()
        },
        "missing_names": [],
        "unavailable_from_evaluated_depsgraph": [],
        "unsupported_types": [],
    }
    Path(os.environ["SCAN_TO_MODEL_NATIVE_OUTPUT"]).joinpath(
        "native-readback.json").write_text(json.dumps(readback))
    raise SystemExit(0)
raise SystemExit(99)
"""
        path.write_text(script.replace("__VERSION_EXIT__", str(version_returncode)))
        path.chmod(0o755)
        return path

    def run_fake_blender(self, root, version_returncode=0):
        model = root / "model.blend"
        model.write_bytes(b"fake blend")
        model_sha = hashlib.sha256(model.read_bytes()).hexdigest()
        membership = self.write_membership(root, self.membership(model_sha))
        blender = self.write_fake_blender(root, version_returncode=version_returncode)
        log = root / "blender-calls.log"
        output = root / "readback"
        environment = os.environ.copy()
        environment["FAKE_BLENDER_LOG"] = str(log)
        result = subprocess.run(
            [sys.executable, "-B", str(LAUNCHER), "--blender", str(blender),
             "--blend", str(model), "--membership", str(membership), "--output", str(output)],
            env=environment, capture_output=True, text=True)
        return result, output, log

    def test_version_probe_precedes_model_launch_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, output, log = self.run_fake_blender(Path(temporary))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(log.read_text().splitlines()[0], "--version")
            self.assertIn("-b", log.read_text().splitlines()[1].split())
            self.assertEqual((output / "blender-version.stdout").read_bytes(), b"Blender fake version\n")
            self.assertEqual((output / "blender-version.stderr").read_bytes(), b"version diagnostic \xff\n")
            preflight = json.loads((output / "preflight.json").read_text())
            receipt = json.loads((output / "launch-receipt.json").read_text())
            for record in (preflight, receipt):
                self.assertEqual(record["blender"]["version"]["returncode"], 0)
                self.assertEqual(record["blender"]["version"]["stdout"]["bytes"], 21)
                self.assertEqual(record["blender"]["version"]["stderr"]["bytes"], 21)
                self.assertEqual(record["blender"]["path"], str(Path(temporary) / "fake-blender.py"))

    def test_failed_version_probe_prevents_model_launch_and_keeps_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, output, log = self.run_fake_blender(Path(temporary), version_returncode=7)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertEqual(log.read_text().splitlines(), ["--version"])
            self.assertEqual((output / "blender-version.stdout").read_bytes(), b"Blender fake version\n")
            self.assertEqual((output / "blender-version.stderr").read_bytes(), b"version diagnostic \xff\n")
            preflight = json.loads((output / "preflight.json").read_text())
            receipt = json.loads((output / "launch-receipt.json").read_text())
            self.assertEqual(preflight["blender"]["version"]["returncode"], 7)
            self.assertEqual(receipt["status"], "fail")
            self.assertEqual(receipt["failure_stage"], "blender_version")

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

    def test_scalar_preserves_nested_mapping_properties(self):
        properties = MappingLike({
            "path": "/tmp/candidate.blend",
            "sha256": "abc123",
            "attempt": 2,
            "nested": MappingLike({"verified": True}),
        })
        self.assertEqual(MODULE._scalar(properties, FakeBpy), {
            "path": "/tmp/candidate.blend",
            "sha256": "abc123",
            "attempt": 2,
            "nested": {"verified": True},
        })

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
            self.assertEqual(readback["target_count"], 5)
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
            beveled = rows["Fixture beveled cube"]
            self.assertEqual(beveled["guard"]["original_mesh_vertex_count"], 8)
            self.assertEqual(beveled["guard"]["original_mesh_polygon_count"], 6)
            self.assertGreater(beveled["guard"]["evaluated_mesh_vertex_count"], 8)
            self.assertGreater(beveled["guard"]["evaluated_mesh_polygon_count"], 6)
            self.assertEqual(beveled["modifiers"][0]["type"], "BEVEL")
            self.assertIsNone(rows["Fixture curve"]["guard"]["original_mesh_vertex_count"])
            self.assertIsNone(rows["Fixture curve"]["guard"]["original_mesh_polygon_count"])
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
