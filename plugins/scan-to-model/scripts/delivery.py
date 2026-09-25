"""Prepare, review and package requested model deliverables without changing source geometry."""

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys

import numpy as np

import appearance
from delivery_contract import check_inputs, digest, load_job, require, write_json
from delivery_runtime import run_worker
from glb_delivery import check_glb
from mesh_quality import review_meshes


SCRIPTS = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def worker(blender, root, phase, *, blend=None, appearance_file=None, native=None):
    executable = shutil.which(str(blender))
    require(executable is not None, "Blender executable not found")
    executable_sha = digest(executable)
    accepted = root / "runs/inspect/receipt.json"
    if phase != "inspect" and accepted.exists():
        require(executable_sha == read(accepted)["blender_sha256"], "Blender build differs from the prepared producer")
    inputs = {str(path): digest(path) for path in [root / "job.json", SCRIPTS / "blender_delivery.py",
                                                 SCRIPTS / "delivery_contract.py", SCRIPTS / "blender_runtime.py"]}
    for path in [blend, appearance_file, native]:
        if path:
            inputs[str(path)] = digest(path)
    cached = root / (phase + "-receipt.json")
    if cached.exists():
        receipt = read(cached)
        require(receipt["inputs"] == inputs and receipt["blender_sha256"] == executable_sha,
                "prepared inputs or producer changed; use a new preparation directory")
        require(all(digest(root / phase / name) == sha for name, sha in receipt["outputs"].items()),
                "cached worker output changed")
        return receipt
    arguments = ["--phase", phase, "--job", root / "job.json", "--output", root / phase]
    if appearance_file:
        arguments += ["--appearance", appearance_file]
    if native:
        arguments += ["--native", native]
    receipt = run_worker(blender, SCRIPTS / "blender_delivery.py", arguments, root / "runs" / phase,
                         blend=blend, helpers=[SCRIPTS / "delivery_contract.py"])
    result = {"inputs": inputs, "blender_sha256": executable_sha,
              "outputs": {path.relative_to(root / phase).as_posix(): digest(path)
                          for path in sorted((root / phase).rglob("*")) if path.is_file()}}
    write_json(cached, result)
    return receipt


def audit_rasters(directory, job, assignments=()):
    directory = Path(directory)
    results = []
    assigned = {row["object"]: row["material"] for row in assignments}
    for view in job.get("views", []):
        folder = directory / view["id"]
        record = read(folder / "render.json")
        require(digest(folder / "view.png") == record["image_sha256"] and
                digest(folder / "raster.npz") == record["raster_sha256"], "render outputs changed")
        counts = {}
        with np.load(folder / "raster.npz", allow_pickle=False) as passes:
            for kind in ["object", "material"]:
                ids = passes[kind]
                require(list(ids.shape[::-1]) == record["resolution"], "raster resolution differs")
                found = dict(zip(*np.unique(ids, return_counts=True)))
                register = record[kind + "_ids"]
                require(all(index == 0 or str(index) in register for index in found), "raster has undeclared identity")
                counts[kind] = {register[str(index)]: int(count) for index, count in found.items() if index}
            material_pixels = {}
            for ident in view["required_objects"]:
                if ident in assigned:
                    object_index = next(int(index) for index, value in record["object_ids"].items() if value == ident)
                    material_index = next(int(index) for index, value in record["material_ids"].items() if value == assigned[ident])
                    material_pixels[ident] = int(((passes["object"] == object_index) & (passes["material"] == material_index)).sum())
        minimum = view.get("minimum_pixels", 64)
        missing = [ident for ident in view["required_objects"] if counts["object"].get(ident, 0) < minimum
                   or (ident in material_pixels and material_pixels[ident] < minimum)]
        result = {"id": view["id"], "passed": not missing, "missing_subjects": missing,
                  "minimum_pixels": minimum, "actual_raster_pixels": counts,
                  "object_material_pixels": material_pixels,
                  "image_sha256": record["image_sha256"], "model_sha256": record["model_sha256"]}
        write_json(folder / "coverage.json", result)
        results.append(result)
    write_json(directory / "coverage.json", results)
    return results


def review_template(model_sha, views):
    return {"model_sha256": model_sha, "geometry": {"finding": "pending", "note": ""},
            "views": [{"id": view["id"], "image_sha256": view["image_sha256"], "finding": "pending", "note": ""} for view in views]}


def validate_review(review, model_sha, views):
    require(review.get("model_sha256") == model_sha, "visual review belongs to a different model")
    geometry = review.get("geometry", {})
    require(geometry.get("finding") == "pass" and isinstance(geometry.get("note"), str) and geometry["note"].strip(),
            "record source/geometry review before delivery")
    rows = review.get("views", [])
    expected = {row["id"]: row for row in views}
    require(len(rows) == len(expected) and {row["id"] for row in rows} == expected.keys(), "review every requested image")
    for row in rows:
        require(row.get("finding") == "pass" and isinstance(row.get("note"), str) and row["note"].strip(), "visual review is incomplete")
        require(row.get("image_sha256") == expected[row["id"]]["image_sha256"], "reviewed image changed")
        require(expected[row["id"]]["passed"], "a required subject is occluded or outside the frame")


def lights(job, scene):
    meshes = {row["id"]: row for row in scene["objects"]}
    result = []
    for fill in job.get("lighting", {}).get("fills", []):
        x, y = fill["xy"]
        height = appearance.ceiling_height_at([meshes[ident] for ident in fill["ceiling_objects"]], x, y, fill["floor_z"])
        require(height is not None, f"no ceiling above light: {fill['id']}")
        z = height - fill.get("clearance", .2)
        require(z > fill["floor_z"], "fill light would be below the floor")
        result.append({"id": fill["id"], "position": [x, y, z], "size": fill["size"],
                       "energy": fill["energy"], "color": fill["color"], "status": "inferred"})
    return result


def prepare(args):
    job, inputs = load_job(args.job)
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "job.json", job)
    write_json(root / "inputs.json", inputs)
    worker(args.blender, root, "inspect", blend=job["model"])
    scene = read(root / "inspect/scene.json")
    quality = review_meshes(scene["objects"])
    write_json(root / "mesh-quality.json", quality)
    require(quality["passed"], f"fix the candidate's mesh findings before appearance; see {root / 'mesh-quality.json'}")
    if job.get("views"):
        worker(args.blender, root, "probe")
    textures = appearance.bake(job, scene, root / "appearance")
    textures["lights"] = lights(job, scene)
    write_json(root / "appearance.json", textures)
    worker(args.blender, root, "apply", blend=job["model"], appearance_file=root / "appearance.json")
    model = root / "apply/candidate.blend"
    worker(args.blender, root, "readback", blend=model, appearance_file=root / "appearance.json", native=root / "apply/native.json")
    if job.get("views"):
        worker(args.blender, root, "preview", blend=model)
        coverage = audit_rasters(root / "preview", job, read(root / "apply/native.json")["assignments"])
    else:
        coverage = []
    check_inputs(inputs)
    prepared = {"schema_version": 1, "model_sha256": digest(model), "job_sha256": digest(root / "job.json"),
                "appearance_sha256": digest(root / "appearance.json"), "scene_sha256": digest(root / "inspect/scene.json"),
                "native_sha256": digest(root / "apply/native.json"), "coverage": coverage,
                "requested_deliverables": job["deliverables"], "status": "needs_preview_review"}
    write_json(root / "prepared.json", prepared)
    write_json(root / "review-template.json", review_template(prepared["model_sha256"], coverage))
    write_json(root / "state.json", {"geometry": "preserved; metric status: " + job["intent"]["metric_status"],
                                     "mesh_checks": "pass", "appearance": "prepared",
                                     "appearance_methods": dict(Counter(row["method"] for row in job.get("materials", []))),
                                     "views": "needs_review", "delivery": "pending"})
    return {"status": prepared["status"], "preview_coverage_passed": all(row["passed"] for row in coverage), "output": str(root)}


def validate_prepared(root):
    prepared = read(root / "prepared.json")
    for file, key in [("job.json", "job_sha256"), ("appearance.json", "appearance_sha256"),
                      ("inspect/scene.json", "scene_sha256"), ("apply/native.json", "native_sha256"),
                      ("apply/candidate.blend", "model_sha256")]:
        require(digest(root / file) == prepared[key], f"prepared artifact changed: {file}")
    check_inputs(read(root / "inputs.json"))
    textures = read(root / "appearance.json")
    if textures["atlas"]:
        require(digest(textures["atlas"]["path"]) == textures["atlas"]["sha256"], "atlas changed after review")
    job = read(root / "job.json")
    coverage = audit_rasters(root / "preview", job, read(root / "apply/native.json")["assignments"]) if job.get("views") else []
    require(coverage == prepared["coverage"], "preview coverage changed")
    return job, prepared, textures


def copy_sources(job, output):
    used = {ident for row in job["objects"] for ident in row.get("sources", [])}
    used.update(ident for row in job.get("materials", []) for ident in row.get("sources", []))
    records = []
    for source in job.get("sources", []):
        if source["id"] not in used:
            continue
        record = dict(source)
        folder = output / "sources" / source["id"]
        folder.mkdir(parents=True)
        for key in ["image", "depth", "confidence", "mask"]:
            if key in source:
                destination = folder / (key + Path(source[key]).suffix)
                shutil.copyfile(source[key], destination)
                record[key] = destination.relative_to(output).as_posix()
        records.append(record)
    write_json(output / "sources.json", records)


def finish(args):
    root = args.prepared.resolve(strict=True)
    job, prepared, textures = validate_prepared(root)
    review = read(args.review)
    validate_review(review, prepared["model_sha256"], prepared["coverage"])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    requested = set(job["deliverables"])
    model = root / "apply/candidate.blend"
    if "native" in requested:
        shutil.copyfile(model, output / "model.blend")
    coverage = []
    if "stills" in requested:
        worker(args.blender, root, "render", blend=model)
        coverage = audit_rasters(root / "render", job, read(root / "apply/native.json")["assignments"])
        require(all(row["passed"] for row in coverage), "final views do not show all required subjects")
        shutil.copytree(root / "render", output / "stills")
    glb_check = None
    if requested & {"glb", "viewer"}:
        worker(args.blender, root, "export", blend=model)
        glb_check = check_glb(root / "export/model.glb", read(root / "inspect/scene.json"), job, textures)
        shutil.copyfile(root / "export/model.glb", output / "model.glb")
        shutil.copyfile(root / "export/model.json", output / "model.json")
        write_json(output / "glb-checks.json", glb_check)
    if "sources" in requested:
        copy_sources(job, output)
    from delivery_assets import build_pages
    build_pages(job, output, root, viewer="viewer" in requested, stills="stills" in requested)
    write_json(output / "preview-review.json", review)
    write_json(output / "native-checks.json", read(root / "readback/checks.json"))
    write_json(output / "final-review-template.json", review_template(prepared["model_sha256"], coverage))
    manifest = {"schema_version": 1, "title": job["title"], "requested_deliverables": job["deliverables"],
                "intent": job["intent"], "model_sha256": prepared["model_sha256"], "views": coverage,
                "inputs": {ident: row["sha256"] for ident, row in read(root / "inputs.json").items()},
                "appearance_methods": dict(Counter(row["method"] for row in job.get("materials", []))),
                "photo_coverage": [{key: face[key] for key in ["object", "face", "method", "photo_coverage"]} for face in textures["faces"]],
                "artifacts": {path.relative_to(output).as_posix(): digest(path) for path in sorted(output.rglob("*"))
                              if path.is_file() and path.name != "final-review-template.json"},
                "status": "needs_final_review"}
    write_json(output / "delivery.json", manifest)
    state = read(root / "state.json")
    state.update(appearance="reviewed", views="preview reviewed", delivery="packaged; final review is recorded in delivery.json")
    write_json(root / "state.json", state)
    return {"status": manifest["status"], "output": str(output), "objects": len(job["objects"]), "stills": len(coverage)}


def verify(args):
    output = args.output.resolve(strict=True)
    manifest = read(output / "delivery.json")
    for relative, sha in manifest["artifacts"].items():
        file = (output / relative).resolve(strict=True)
        require(file.is_relative_to(output) and digest(file) == sha, f"delivered artifact changed: {relative}")
    review = read(args.review)
    validate_review(review, manifest["model_sha256"], manifest["views"])
    if manifest["status"] == "verified":
        require(digest(output / "delivery-checks.json") == manifest["verification_sha256"], "verification record changed")
        previous = read(output / "delivery-checks.json")
        if previous["final_visual_review"] == review and not args.browser:
            for relative, sha in previous.get("browser", {}).get("screenshots", {}).items():
                require(digest(output / relative) == sha, "verified browser screenshot changed")
            return {"status": "verified", "output": str(output), "reused_unchanged_checks": True}
    checks = {"artifact_hashes_match": True, "final_visual_review": review}
    if "viewer" in manifest["requested_deliverables"]:
        from browser_delivery import check_browser
        checks["browser"] = check_browser(output, args.browser)
    write_json(output / "delivery-checks.json", checks)
    manifest["status"] = "verified"
    manifest["verification_sha256"] = digest(output / "delivery-checks.json")
    write_json(output / "delivery.json", manifest)
    return {"status": "verified", "output": str(output), "requested_deliverables": manifest["requested_deliverables"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparing = commands.add_parser("prepare", help="inspect geometry, prepare materials and render low-cost previews")
    preparing.add_argument("--job", type=Path, required=True)
    preparing.add_argument("--output", type=Path, required=True)
    preparing.add_argument("--blender", required=True)
    finishing = commands.add_parser("finish", help="render and package the visually reviewed candidate")
    finishing.add_argument("--prepared", type=Path, required=True)
    finishing.add_argument("--review", type=Path, required=True)
    finishing.add_argument("--output", type=Path, required=True)
    finishing.add_argument("--blender", required=True)
    checking = commands.add_parser("verify", help="check delivered hashes, final visual review and offline browser behavior")
    checking.add_argument("--output", type=Path, required=True)
    checking.add_argument("--review", type=Path, required=True)
    checking.add_argument("--browser", help="Chrome/Chromium executable; otherwise discover it on PATH")
    args = parser.parse_args()
    try:
        result = {"prepare": prepare, "finish": finish, "verify": verify}[args.command](args)
        print(json.dumps(result))
    except (OSError, ValueError, KeyError) as error:
        print(f"delivery refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
