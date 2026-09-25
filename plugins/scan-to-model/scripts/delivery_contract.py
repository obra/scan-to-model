"""Validate requested model outputs and resolve immutable project inputs."""

import hashlib
import json
from pathlib import Path
import re

import numpy as np


OUTPUTS = {"native", "glb", "stills", "viewer", "sources"}
METHODS = {"matched-color", "photo-projection", "repeated-photo", "inferred"}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def numbers(value, shape, label):
    result = np.asarray(value, dtype=float)
    require(result.shape == shape and np.isfinite(result).all(), f"invalid {label}")
    return result


def register(rows, label):
    require(isinstance(rows, list), f"{label} must be a list")
    result = {}
    for row in rows:
        ident = row.get("id", "")
        require(isinstance(ident, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", ident),
                f"invalid {label} id: {ident!r}")
        require(ident not in result, f"duplicate {label} id: {ident}")
        result[ident] = row
    return result


def validate(job):
    require(job.get("schema_version") == 1, "delivery schema_version must be 1")
    require(isinstance(job.get("title"), str) and job["title"].strip(), "title is required")
    requested = job.get("deliverables", [])
    require(isinstance(requested, list) and requested and len(set(requested)) == len(requested)
            and set(requested) <= OUTPUTS, "invalid requested deliverables")
    intent = job.get("intent", {})
    require(isinstance(intent.get("interpolation_authorized"), bool), "record interpolation authorization")
    require(isinstance(intent.get("basis"), str) and intent["basis"].strip(), "record the user's requested outcome")
    require(intent.get("geometry_status") in {"tentative", "accepted"}, "record geometry status")
    require(isinstance(intent.get("metric_status"), str) and intent["metric_status"].strip(), "record metric limits")
    objects = register(job.get("objects", []), "object")
    require(objects, "declare the complete drawable object scope")
    names = [row.get("name") for row in objects.values()]
    require(all(isinstance(name, str) and name for name in names) and len(set(names)) == len(names),
            "object names must be nonempty and unique")
    sources = register(job.get("sources", []), "source")
    materials = register(job.get("materials", []), "material")
    views = register(job.get("views", []), "view")
    require("exterior" not in views, "view id exterior is reserved for the complete-model overview")
    require(views or not (set(requested) & {"stills", "viewer"}), "stills/viewer require named views")
    for row in objects.values():
        require(row.get("material") is None or row["material"] in materials, "unknown object material")
        require(set(row.get("sources", [])) <= sources.keys(), "unknown object source")
        require(row.get("room") and row.get("level") and row.get("role"), "object room, level and role are required")
    for material in materials.values():
        method = material.get("method")
        require(method in METHODS, "unknown appearance method")
        rgb = numbers(material.get("color"), (3,), "sRGB color")
        require(((0 <= rgb) & (rgb <= 255)).all(), "color must be sRGB 0..255")
        require(isinstance(material.get("basis"), str) and material["basis"].strip(), "material basis is required")
        refs = material.get("sources", [])
        require(isinstance(refs, list) and set(refs) <= sources.keys(), "unknown material source")
        require(method == "inferred" or refs, "source-derived appearance requires source identities")
        require(intent["interpolation_authorized"] or method == "matched-color",
                "projection gaps, repetition and inferred finishes require authorized interpolation")
        for key, default in [("roughness", .6), ("metallic", 0), ("transmission", 0)]:
            value = material.get(key, default)
            require(isinstance(value, (int, float)) and 0 <= value <= 1, f"invalid {key}")
        if method == "repeated-photo":
            sample = material.get("sample", {})
            require(sample.get("source") in refs, "repeated sample must identify a material source")
            numbers(sample.get("quad"), (4, 2), "sample pixel quadrilateral")
            mapping = material.get("mapping", {})
            numbers(mapping.get("origin"), (3,), "mapping origin")
            axes = numbers([mapping.get("u"), mapping.get("v")], (2, 3), "mapping axes")
            require(np.allclose(axes @ axes.T, np.eye(2), atol=1e-6), "mapping axes must be orthonormal")
            require((numbers(mapping.get("size_m"), (2,), "sample size") > 0).all(), "sample size must be positive")
        if method == "photo-projection":
            for ident in refs:
                source = sources[ident]
                require("depth" in source and "confidence" in source, "projection requires depth and confidence")
                camera = source.get("camera", {})
                values = numbers([camera.get(k) for k in ["width", "height", "fx", "fy", "cx", "cy"]], (6,), "intrinsics")
                require((values[:4] > 0).all(), "invalid intrinsics")
                matrix = numbers(source.get("camera_to_world"), (4, 4), "camera pose")
                require(np.allclose(matrix[3], [0, 0, 0, 1]) and
                        np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-5) and
                        np.linalg.det(matrix[:3, :3]) > .999, "camera pose must be rigid")
                require(source.get("depth_scale", .001) > 0, "depth_scale must be positive")
            require(material.get("depth_tolerance_m", .1) > 0, "depth tolerance must be positive")
        if "detail_contrast" in material:
            require(0 <= material["detail_contrast"] <= 1, "detail_contrast must be 0..1")
    for view in views.values():
        require(view.get("camera"), "view requires a native camera")
        required = view.get("required_objects", [])
        require(required and set(required) <= objects.keys(), "view requires known subjects")
        require(view.get("minimum_pixels", 64) > 0, "view pixel threshold must be positive")
    renderer = job.get("renderer", {})
    require(renderer.get("engine", "CYCLES") == "CYCLES", "delivery renderer currently supports CYCLES")
    for key, default in [("width", 1024), ("height", 768), ("samples", 32)]:
        require(isinstance(renderer.get(key, default), int) and renderer.get(key, default) > 0, f"invalid renderer {key}")
    require(isinstance(renderer.get("denoise", True), bool), "denoise must be boolean")
    texture = job.get("texture", {})
    maximum = texture.get("max_size", 2048)
    require(isinstance(maximum, int) and 32 <= maximum <= 16384, "invalid atlas size")
    require(0 < texture.get("minimum_density", 16) <= texture.get("density", 128), "invalid texture density")
    if job.get("lighting"):
        require(intent["interpolation_authorized"], "presentation lighting requires authorized inference")
        world = job["lighting"].get("world")
        if world:
            require(((0 <= numbers(world.get("color"), (3,), "world color")) &
                    (numbers(world.get("color"), (3,), "world color") <= 1)).all(), "world color must be 0..1")
            require(world.get("strength", -1) >= 0, "invalid world strength")
        fills = register(job["lighting"].get("fills", []), "fill")
        for fill in fills.values():
            numbers(fill.get("xy"), (2,), "fill position")
            numbers([fill.get("floor_z"), fill.get("size"), fill.get("energy"), fill.get("clearance", .2)], (4,), "fill dimensions")
            color = numbers(fill.get("color"), (3,), "fill color")
            require(((0 <= color) & (color <= 1)).all() and fill["size"] > 0 and fill["energy"] > 0 and fill.get("clearance", .2) > 0,
                    "invalid fill light")
            require(fill.get("ceiling_objects") and set(fill["ceiling_objects"]) <= objects.keys(), "unknown fill ceiling")
    excluded = job.get("excluded_objects", [])
    require(isinstance(excluded, list) and all(row.get("name") and row.get("reason") for row in excluded), "name and explain excluded objects")
    excluded_names = [row["name"] for row in excluded]
    require(len(set(excluded_names)) == len(excluded_names) and not (set(excluded_names) & set(names)), "duplicate or conflicting excluded objects")
    return job


def load_job(path):
    path = Path(path).resolve(strict=True)
    job = validate(json.loads(path.read_text()))
    inputs = {"job": {"path": str(path), "sha256": digest(path)}}

    def resolve(record, key, label):
        value = record.get(key)
        require(isinstance(value, str) and value, f"missing {label} path")
        file = (path.parent / value).resolve(strict=True)
        require(file.is_file(), f"not a file: {label}")
        sha = digest(file)
        expected = record.get(key + "_sha256")
        require(isinstance(expected, str) and sha == expected, f"input hash mismatch: {label}")
        record[key] = str(file)
        inputs[label] = {"path": str(file), "sha256": sha}

    resolve(job, "model", "model")
    for source in job.get("sources", []):
        for key in ["image", "depth", "confidence", "mask"]:
            if key == "image" or key in source:
                resolve(source, key, source["id"] + "/" + key)
    return job, inputs


def check_inputs(inputs):
    for ident, row in inputs.items():
        require(digest(row["path"]) == row["sha256"], f"input changed: {ident}")
