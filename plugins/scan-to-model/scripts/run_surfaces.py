"""Run native surface sampling with a frozen, self-contained helper closure."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_NAMES = ("surfaces.py", "polycam.py", "pixel_inspection.py")


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def resolve_capture(value, spec_parent):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("capture must be a nonempty path")
    path = Path(value).expanduser()
    return str((path if path.is_absolute() else spec_parent / path).resolve())


def resolved_spec(spec, spec_parent):
    result = copy.deepcopy(spec)
    if "capture" in result:
        result["capture"] = resolve_capture(result["capture"], spec_parent)
    for patch in result.get("patches", []):
        if "capture" in patch:
            patch["capture"] = resolve_capture(patch["capture"], spec_parent)
    return result


def output_manifest(output):
    entries = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"run-receipt.json", "output-manifest.json"}:
            entries.append({"path": str(path.relative_to(output)),
                            "bytes": path.stat().st_size, "sha256": digest(path)})
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pixel-inspections", action="store_true")
    args = parser.parse_args()
    spec_path = args.spec.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output must be a new directory: {output}")
    original = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(original, dict) or not isinstance(original.get("patches"), list):
        raise ValueError("spec must contain a patches list")
    output.mkdir(parents=True)
    runtime = output / "runtime"
    measurements = output / "measurements"
    runtime.mkdir()
    temporary = runtime / "tmp"
    matplotlib_config = runtime / "matplotlib"
    temporary.mkdir()
    matplotlib_config.mkdir()
    frozen_spec = runtime / "original-spec.json"
    resolved = runtime / "resolved-spec.json"
    shutil.copyfile(spec_path, frozen_spec)
    resolved.write_text(json.dumps(resolved_spec(original, spec_path.parent), indent=2) + "\n")
    helpers = {}
    for name in HELPER_NAMES:
        target = runtime / name
        shutil.copyfile(SCRIPT_DIR / name, target)
        helpers[name] = {"path": str(target), "sha256": digest(target)}
    launcher = runtime / "run_surfaces.py"
    source_launcher = SCRIPT_DIR / "run_surfaces.py"
    source_launcher_sha256 = digest(source_launcher)
    shutil.copyfile(source_launcher, launcher)
    launcher_binding = {"path": str(launcher), "sha256": digest(launcher)}
    command = [sys.executable, "-B", str(runtime / "surfaces.py"), "--spec", str(resolved),
               "--output", str(measurements)]
    if args.pixel_inspections:
        command.append("--pixel-inspections")
    environment = os.environ.copy()
    environment.update({"PYTHONPATH": str(runtime), "PYTHONDONTWRITEBYTECODE": "1",
                        "TMPDIR": str(temporary), "MPLCONFIGDIR": str(matplotlib_config)})
    controlled_environment = {key: environment[key] for key in
                              ("PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "TMPDIR", "MPLCONFIGDIR")}
    preflight = {"status": "frozen_before_process", "argv": command, "cwd": str(output),
                 "python": sys.executable, "original_spec": {"path": str(spec_path), "sha256": digest(spec_path)},
                 "frozen_original_spec": {"path": str(frozen_spec), "sha256": digest(frozen_spec)},
                 "resolved_spec": {"path": str(resolved), "sha256": digest(resolved)},
                 "helpers": helpers, "launcher": launcher_binding,
                 "source_launcher": {"path": str(source_launcher), "sha256": source_launcher_sha256},
                 "environment_overrides": controlled_environment,
                 "pixel_inspections": args.pixel_inspections}
    (output / "preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")
    process = subprocess.run(command, cwd=output, env=environment, capture_output=True, text=True)
    (output / "stdout.log").write_text(process.stdout)
    (output / "stderr.log").write_text(process.stderr)
    manifest = output_manifest(output)
    (output / "output-manifest.json").write_text(json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n")
    receipt = {"status": "pass" if process.returncode == 0 else "fail", "returncode": process.returncode,
               "argv": command, "cwd": str(output), "python": sys.executable,
               "original_spec": {"path": str(spec_path), "sha256": preflight["original_spec"]["sha256"]},
               "frozen_original_spec": {"path": str(frozen_spec), "sha256": digest(frozen_spec)},
               "resolved_spec": {"path": str(resolved), "sha256": digest(resolved)},
               "helpers": helpers, "launcher": launcher_binding,
               "source_launcher": {"path": str(source_launcher), "sha256": source_launcher_sha256,
                                   "unchanged": digest(source_launcher) == source_launcher_sha256},
               "environment_overrides": controlled_environment,
               "original_spec_unchanged": digest(spec_path) == preflight["original_spec"]["sha256"],
               "pixel_inspections": args.pixel_inspections,
               "stdout": "stdout.log", "stderr": "stderr.log", "output_manifest": "output-manifest.json",
               "output_files": manifest}
    (output / "run-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "returncode": process.returncode, "output": str(output)}))
    return 0 if process.returncode == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"surface run refused: {error}", file=sys.stderr)
        raise SystemExit(2)
