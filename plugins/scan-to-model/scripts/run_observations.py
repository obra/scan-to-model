"""Run source-photo annotation rendering with a frozen helper closure."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_NAMES = ("observations.py", "pixel_inspection.py", "image_metadata.py")


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coordinate-inspections", action="store_true")
    args = parser.parse_args()
    spec_path = args.spec.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output must be a new directory: {output}")
    runtime = output.parent / f".{output.name}.observation-runtime"
    if runtime.exists():
        raise ValueError(f"runtime must be a new directory: {runtime}")
    runtime.mkdir(parents=True)

    helpers = {}
    for name in HELPER_NAMES:
        source = SCRIPT_DIR / name
        target = runtime / name
        shutil.copyfile(source, target)
        helpers[name] = {"path": str(target), "sha256": digest(target)}
    launcher = runtime / "run_observations.py"
    source_launcher = SCRIPT_DIR / "run_observations.py"
    shutil.copyfile(source_launcher, launcher)
    launcher_binding = {"path": str(launcher), "sha256": digest(launcher)}
    command = [sys.executable, "-B", str(runtime / "observations.py"),
               "--spec", str(spec_path), "--output", str(output)]
    if args.coordinate_inspections:
        command.append("--coordinate-inspections")
    environment = os.environ.copy()
    environment.update({"PYTHONPATH": str(runtime), "PYTHONDONTWRITEBYTECODE": "1"})
    controlled_environment = {
        key: environment[key] for key in ("PYTHONPATH", "PYTHONDONTWRITEBYTECODE")
    }
    preflight = {
        "status": "frozen_before_process",
        "argv": command,
        "cwd": str(output.parent),
        "python": sys.executable,
        "spec": {"path": str(spec_path), "sha256": digest(spec_path)},
        "helpers": helpers,
        "launcher": launcher_binding,
        "source_launcher": {"path": str(source_launcher), "sha256": digest(source_launcher)},
        "environment_overrides": controlled_environment,
        "coordinate_inspections": args.coordinate_inspections,
    }
    (runtime / "preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")
    process = subprocess.run(command, cwd=output.parent, env=environment, capture_output=True, text=True)
    if not output.exists():
        output.mkdir(parents=True)
    (output / "run-stdout.log").write_text(process.stdout)
    (output / "run-stderr.log").write_text(process.stderr)
    receipt = {
        "status": "pass" if process.returncode == 0 else "fail",
        "returncode": process.returncode,
        "argv": command,
        "cwd": str(output.parent),
        "python": sys.executable,
        "spec": preflight["spec"],
        "helpers": helpers,
        "launcher": launcher_binding,
        "source_launcher": {
            "path": str(source_launcher),
            "sha256": preflight["source_launcher"]["sha256"],
            "unchanged": digest(source_launcher) == preflight["source_launcher"]["sha256"],
        },
        "environment_overrides": controlled_environment,
        "coordinate_inspections": args.coordinate_inspections,
        "stdout": "run-stdout.log",
        "stderr": "run-stderr.log",
        "runtime": str(runtime),
    }
    (output / "run-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "returncode": process.returncode,
                      "output": str(output)}))
    return 0 if process.returncode == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"observation run refused: {error}", file=sys.stderr)
        raise SystemExit(2)
