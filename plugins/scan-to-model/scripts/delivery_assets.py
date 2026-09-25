"""Assemble reusable local viewer and still-tour assets without private project constants."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from delivery_contract import digest, require, write_json


ASSETS = Path(__file__).resolve().parents[1] / "assets" / "viewer"


def build_pages(job, output, prepared, *, viewer, stills):
    if viewer:
        names = ["index.html", "viewer.js", "viewer.css", "controls.js", "build.mjs", "package.json", "package-lock.json", "THREE-LICENSE.txt"]
        metadata = json.loads((output / "model.json").read_text())
        metadata.update(native_available="native" in job["deliverables"], stills_available=stills)
        inputs = {"assets": {name: digest(ASSETS / name) for name in names},
                  "model_sha256": digest(output / "model.glb"), "metadata": metadata}
        identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        build = prepared / "viewer-build" / identity
        receipt = build / "viewer-build.json"
        if receipt.exists():
            record = json.loads(receipt.read_text())
            require(record["inputs"] == inputs and all(digest(build / name) == sha for name, sha in record["outputs"].items()),
                    "cached viewer build changed")
        else:
            build.mkdir(parents=True, exist_ok=True)
            for name in names:
                shutil.copyfile(ASSETS / name, build / name)
            shutil.copyfile(output / "model.glb", build / "model.glb")
            write_json(build / "model.json", metadata)
            with (build / "build.log").open("a") as log:
                subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=build, stdout=log, stderr=log, check=True)
                subprocess.run(["npm", "run", "build"], cwd=build, stdout=log, stderr=log, check=True)
            outputs = [*names, "model.json", *[file.name for file in build.glob("viewer.bundle.js*")]]
            record = {"inputs": inputs, "outputs": {name: digest(build / name) for name in outputs}}
            write_json(receipt, record)
        for name in [*record["outputs"], receipt.name]:
            shutil.copyfile(build / name, output / name)
    if stills:
        slides = [{"id": view["id"], "title": view.get("title", view["id"]), "caption": view.get("caption", ""),
                   "image": "stills/" + view["id"] + "/view.png"} for view in job["views"]]
        data = {"title": job["title"], "viewer": viewer, "slides": slides,
                "limits": f"Geometry: {job['intent']['geometry_status']}. {job['intent']['metric_status']}. Appearance and lighting may include recorded inference."}
        (output / "tour-data.js").write_text("window.MODEL_TOUR = " + json.dumps(data, indent=2) + ";\n")
        for name in ["tour.html", "tour.js", "tour.css"]:
            shutil.copyfile(ASSETS / name, output / name)
