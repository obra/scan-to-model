"""Assemble reusable local viewer and still-tour assets without private project constants."""

import json
from pathlib import Path
import shutil
import subprocess

from delivery_contract import write_json


ASSETS = Path(__file__).resolve().parents[1] / "assets" / "viewer"


def build_pages(job, output, prepared, *, viewer, stills):
    if viewer:
        build = prepared / "viewer-build"
        build.mkdir(exist_ok=False)
        for name in ["index.html", "viewer.js", "viewer.css", "controls.js", "build.mjs", "package.json", "package-lock.json", "THREE-LICENSE.txt"]:
            shutil.copyfile(ASSETS / name, build / name)
        shutil.copyfile(output / "model.glb", build / "model.glb")
        metadata = json.loads((output / "model.json").read_text())
        metadata.update(native_available="native" in job["deliverables"], stills_available=stills)
        write_json(build / "model.json", metadata)
        with (build / "build.log").open("w") as log:
            subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=build, stdout=log, stderr=log, check=True)
            subprocess.run(["npm", "run", "build"], cwd=build, stdout=log, stderr=log, check=True)
        for file in build.iterdir():
            if file.is_file() and file.name not in {"model.glb", "build.log"}:
                shutil.copyfile(file, output / file.name)
    if stills:
        slides = [{"id": view["id"], "title": view.get("title", view["id"]), "caption": view.get("caption", ""),
                   "image": "stills/" + view["id"] + "/view.png"} for view in job["views"]]
        data = {"title": job["title"], "viewer": viewer, "slides": slides,
                "limits": f"Geometry: {job['intent']['geometry_status']}. {job['intent']['metric_status']}. Appearance and lighting may include recorded inference."}
        (output / "tour-data.js").write_text("window.MODEL_TOUR = " + json.dumps(data, indent=2) + ";\n")
        for name in ["tour.html", "tour.js", "tour.css"]:
            shutil.copyfile(ASSETS / name, output / name)
