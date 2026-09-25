"""Run portable Blender workers with one immutable helper copy per revision."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from delivery_contract import digest, require, write_json


SCRIPTS = Path(__file__).resolve().parent


def freeze_helpers(store, files):
    require(len({Path(file).name for file in files}) == len(files), "helper names must be unique")
    files = {Path(file).name: Path(file) for file in files}
    hashes = {name: digest(file) for name, file in sorted(files.items())}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    root = Path(store) / identity
    if root.exists():
        require(all((root / name).is_file() and digest(root / name) == sha for name, sha in hashes.items()),
                "frozen helper bytes changed")
    else:
        root.mkdir(parents=True)
        for name, file in files.items():
            shutil.copyfile(file, root / name)
    return root, hashes


def run_worker(blender, worker, arguments, output, *, blend=None, helpers=()):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    worker = Path(worker).resolve(strict=True)
    executable = shutil.which(str(blender))
    require(executable is not None, "Blender executable not found")
    executable = Path(executable).resolve(strict=True)
    frozen, hashes = freeze_helpers(output.parent / "helpers", [worker, SCRIPTS / "blender_runtime.py", *helpers])
    environment = os.environ.copy()
    for key, folder in [("BLENDER_USER_CONFIG", "config"), ("XDG_CONFIG_HOME", "xdg-config"),
                        ("XDG_CACHE_HOME", "cache"), ("XDG_DATA_HOME", "data"),
                        ("XDG_RUNTIME_DIR", "xdg-runtime"), ("TMPDIR", "tmp")]:
        location = output / folder
        location.mkdir(mode=0o700)
        environment[key] = str(location)
    environment["SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT"] = str(output)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    version = subprocess.check_output([str(executable), "--version"], text=True)
    command = [str(executable), "-b", "--factory-startup", "--disable-autoexec", "--threads", "2",
               "--python-exit-code", "1", "--python", str(frozen / "blender_runtime.py")]
    before = None
    if blend is not None:
        blend = Path(blend).resolve(strict=True)
        before = digest(blend)
        command.append(str(blend))
    command += ["--python", str(frozen / worker.name), "--", *map(str, arguments)]
    receipt = {"blender_version": version, "blender_sha256": digest(executable),
               "helper_revision": frozen.name, "helpers": hashes, "input_model_sha256": before,
               "arguments": list(map(str, arguments)), "status": "running"}
    write_json(output / "receipt.json", receipt)
    try:
        with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
            process = subprocess.run(command, env=environment, cwd=output, stdout=stdout, stderr=stderr)
        unchanged = blend is None or digest(blend) == before
        intact = all(digest(frozen / name) == sha for name, sha in hashes.items())
        receipt.update(returncode=process.returncode, input_unchanged=unchanged, helpers_unchanged=intact,
                       status="pass" if process.returncode == 0 and unchanged and intact else "fail")
        require(receipt["status"] == "pass", f"Blender worker failed; inspect {output / 'stderr.log'} and stdout.log")
    except BaseException:
        receipt["status"] = "fail"
        raise
    finally:
        write_json(output / "receipt.json", receipt)
    return receipt
