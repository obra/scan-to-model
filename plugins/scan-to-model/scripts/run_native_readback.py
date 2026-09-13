"""Launch a strict declared-membership Blender native readback."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import native_readback


RUNTIME_HELPER = Path(__file__).with_name("blender_runtime.py")
WORKER = Path(__file__).with_name("native_readback.py")


def digest(path):
    return native_readback.sha256(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blend = args.blend.resolve(strict=True)
    membership_path = args.membership.resolve(strict=True)
    blender = args.blender.resolve(strict=True)
    if not blender.is_file() or not os.access(blender, os.X_OK):
        raise ValueError(f"--blender must be an executable file: {blender}")
    membership, _, _ = native_readback.validate_membership(membership_path)
    before_model = digest(blend)
    source_launcher = Path(__file__).resolve(strict=True)
    before_launcher = digest(source_launcher)
    if before_model != membership["model_sha256"]:
        raise ValueError(f"model SHA-256 mismatch: expected {membership['model_sha256']}, got {before_model}")
    if not RUNTIME_HELPER.is_file():
        raise ValueError(f"missing runtime helper: {RUNTIME_HELPER}")
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output must be a new directory: {output}")
    output.mkdir(parents=True)
    runtime = output / "runtime-01"
    temporary = runtime / "tmp"
    runtime.mkdir()
    temporary.mkdir()
    frozen_membership = runtime / "membership.json"
    frozen_worker = runtime / "native_readback.py"
    frozen_runtime = runtime / "blender_runtime.py"
    frozen_launcher = runtime / "run_native_readback.py"
    shutil.copyfile(membership_path, frozen_membership)
    shutil.copyfile(WORKER, frozen_worker)
    shutil.copyfile(RUNTIME_HELPER, frozen_runtime)
    shutil.copyfile(source_launcher, frozen_launcher)
    frozen = {"membership": digest(frozen_membership), "producer": digest(frozen_worker),
              "runtime": digest(frozen_runtime), "launcher": digest(frozen_launcher)}
    environment = os.environ.copy()
    environment.update({
        "SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT": str(runtime),
        "TMPDIR": str(temporary),
        "SCAN_TO_MODEL_NATIVE_OUTPUT": str(output),
        "SCAN_TO_MODEL_NATIVE_MEMBERSHIP": str(frozen_membership),
    })
    command = [str(blender), "-b", "--disable-autoexec", "--threads", "2",
               "--python-exit-code", "1", "--python", str(frozen_runtime),
               str(blend), "--python", str(frozen_worker)]
    controlled_environment = {key: environment[key] for key in (
        "SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT", "TMPDIR", "SCAN_TO_MODEL_NATIVE_OUTPUT",
        "SCAN_TO_MODEL_NATIVE_MEMBERSHIP")}
    preflight = {"status": "frozen_before_process", "argv": command,
                 "environment_overrides": controlled_environment,
                 "inherited_environment_passed": True,
                 "blend": {"path": str(blend), "sha256": before_model},
                 "membership": {"path": str(frozen_membership), "sha256": frozen["membership"]},
                 "producer": {"path": str(frozen_worker), "sha256": frozen["producer"]},
                 "runtime": {"path": str(frozen_runtime), "sha256": frozen["runtime"]},
                 "launcher": {"path": str(frozen_launcher), "sha256": frozen["launcher"]},
                 "source_launcher_sha256": before_launcher,
                 "no_save": True, "no_render": True}
    (output / "preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")
    process = subprocess.run(command, cwd=output, env=environment, capture_output=True, text=True)
    (output / "stdout.log").write_text(process.stdout)
    (output / "stderr.log").write_text(process.stderr)
    after_model = digest(blend)
    after_launcher = digest(source_launcher)
    after_frozen = {key: digest(path) for key, path in (
        ("membership", frozen_membership), ("producer", frozen_worker),
        ("runtime", frozen_runtime), ("launcher", frozen_launcher))}
    readback = output / "native-readback.json"
    readback_contract = False
    if readback.is_file():
        try:
            data = json.loads(readback.read_text(encoding="utf-8"))
            expected_count = membership["counts"]["total_native_targets"]
            readback_contract = (
                data.get("schema_version") == 4
                and data.get("model_sha256") == before_model
                and data.get("membership_sha256") == frozen["membership"]
                and data.get("room_id") == membership["room_id"]
                and data.get("requested_target_count") == expected_count
                and data.get("target_count") == expected_count
                and [row.get("name") for row in data.get("objects", [])] == [
                    name for group in membership["groups"].values() for name in group["target_names"]]
                and data.get("groups") == {
                    group: {"target_count": len(spec["target_names"]),
                            "target_names": spec["target_names"]}
                    for group, spec in membership["groups"].items()}
                and not data.get("missing_names")
                and not data.get("unavailable_from_evaluated_depsgraph")
                and not data.get("unsupported_types")
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            readback_contract = False
    output_files = [output / name for name in ("preflight.json", "stdout.log", "stderr.log", "native-readback.json") if (output / name).is_file()]
    checks = {"model_unchanged": after_model == before_model,
              "membership_unchanged": after_frozen["membership"] == frozen["membership"],
              "producer_unchanged": after_frozen["producer"] == frozen["producer"],
              "runtime_unchanged": after_frozen["runtime"] == frozen["runtime"],
              "launcher_unchanged": after_frozen["launcher"] == frozen["launcher"],
              "source_launcher_unchanged": after_launcher == before_launcher,
              "readback_present": readback.is_file(),
              "readback_contract": readback_contract}
    status = "pass" if process.returncode == 0 and all(checks.values()) else "fail"
    receipt = {"status": status, "returncode": process.returncode, "argv": command,
               "environment_overrides": controlled_environment,
               "inherited_environment_passed": True,
               "blender_stdout": "stdout.log", "blender_stderr": "stderr.log",
               "before": {"model_sha256": before_model, **frozen},
               "after": {"model_sha256": after_model, "source_launcher_sha256": after_launcher,
                         **after_frozen}, "checks": checks,
               "output_hashes": {path.name: digest(path) for path in output_files},
               "no_save": True, "no_render": True}
    (output / "launch-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "returncode": process.returncode, "output": str(output)}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"native readback refused: {error}", file=sys.stderr)
        raise SystemExit(2)
