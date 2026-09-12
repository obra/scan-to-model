"""Exercise explicit object-to-source closure in a reopened Blender file."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy


REGISTRY_TEXT = "synthetic-evidence-registry.json"
SCHEMA = "synthetic-evidence-closure/v1"
VISUAL_IDENTITY_FIELDS = (
    "source_id",
    "collection_id",
    "capture_id",
    "frame_id",
    "variant",
    "sha256",
)
DOCUMENTARY_IDENTITY_FIELDS = ("source_id", "document_id", "locator", "variant")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("missing-original", "complete", "missing-retention"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    args.output = args.output.expanduser().resolve()
    try:
        args.output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f"output already exists: {args.output}")
    return args


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_png(path, color):
    image = bpy.data.images.new(path.stem, width=2, height=2)
    image.pixels = color * 4
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def append_packed_image(path, name, identity):
    image = bpy.data.images.load(str(path))
    image.name = name
    image.pack()
    image.use_fake_user = True
    image.filepath = f"//sources/{path.name}"
    for field in VISUAL_IDENTITY_FIELDS:
        image[f"evidence_{field}"] = identity[field]
    return image


def add_substantive_object(name, object_id, location):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj["evidence_substantive"] = True
    obj["evidence_object_id"] = object_id


def fixture_schema(source_hashes):
    uncertainty = "Invented evidence has no metric calibration."
    original_identity = {
        "source_id": "frame-original",
        "collection_id": "invented-collection",
        "capture_id": "invented-capture",
        "frame_id": "invented-frame",
        "variant": "original",
        "sha256": source_hashes["frame-original.png"],
    }
    upright_identity = {
        **original_identity,
        "source_id": "frame-upright",
        "variant": "qualified-upright",
        "sha256": source_hashes["frame-upright.png"],
    }
    return {
        "schema": SCHEMA,
        "sources": {
            "frame-original": {
                "kind": "original",
                "identity": original_identity,
                "uncertainty": uncertainty,
                "image": "Original evidence",
            },
            "frame-upright": {
                "kind": "qualified-upright",
                "identity": upright_identity,
                "uncertainty": uncertainty,
                "image": "Qualified upright evidence",
                "original_source_id": "frame-original",
            },
            "documentary-note": {
                "kind": "documentary-unlocated",
                "identity": {
                    "source_id": "documentary-note",
                    "document_id": "invented-document",
                    "locator": "unlocated",
                    "variant": "documentary",
                },
                "uncertainty": "The note has no established image or model location.",
            },
        },
        "object_bindings": {
            "modeled-panel": {
                "object_name": "Modeled panel",
                "source_ids": ["frame-upright"],
            },
            "documentary-marker": {
                "object_name": "Documentary marker",
                "source_ids": ["documentary-note"],
            },
        },
    }


def build_fixture(root, mode):
    source_dir = root / "sources"
    source_dir.mkdir()
    original_path = source_dir / "frame-original.png"
    upright_path = source_dir / "frame-upright.png"
    create_png(original_path, (1.0, 0.0, 0.0, 1.0))
    create_png(upright_path, (0.0, 1.0, 0.0, 1.0))
    source_hashes = {
        path.name: file_sha256(path) for path in (original_path, upright_path)
    }
    schema = fixture_schema(source_hashes)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    add_substantive_object("Modeled panel", "modeled-panel", (0, 0, 0))
    add_substantive_object("Documentary marker", "documentary-marker", (2, 0, 0))
    append_packed_image(
        upright_path,
        "Qualified upright evidence",
        schema["sources"]["frame-upright"]["identity"],
    )
    if mode in ("complete", "missing-retention"):
        append_packed_image(
            original_path,
            "Original evidence",
            schema["sources"]["frame-original"]["identity"],
        )
        if mode == "missing-retention":
            # Packing stores the payload; a fake user retains an evidence-only image through save.
            bpy.data.images["Original evidence"].use_fake_user = False
    registry = bpy.data.texts.new(REGISTRY_TEXT)
    registry.write(json.dumps(schema, indent=2, sort_keys=True))

    blend_path = root / "final.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), relative_remap=False)
    return blend_path, source_hashes


def validate_visual_source(source_id, source, sources, checked, failures):
    if source_id in checked:
        return
    checked.add(source_id)
    if not source.get("uncertainty"):
        failures.append(f"{source_id}: visual source has no uncertainty")
    identity = source.get("identity")
    if not isinstance(identity, dict):
        failures.append(f"{source_id}: visual source has no identity object")
        return
    for field in VISUAL_IDENTITY_FIELDS:
        if not identity.get(field):
            failures.append(f"{source_id}: identity is missing {field}")
    if identity.get("source_id") != source_id:
        failures.append(f"{source_id}: identity source_id does not match registry key")

    image_name = source.get("image")
    image = bpy.data.images.get(image_name) if isinstance(image_name, str) else None
    if image is None:
        failures.append(f"{source_id}: declared image is absent from the blend")
    else:
        packed = image.packed_file
        if packed is None:
            failures.append(f"{source_id}: image is not packed")
        elif hashlib.sha256(bytes(packed.data)).hexdigest() != identity.get("sha256"):
            failures.append(f"{source_id}: packed bytes do not match source identity")
        if not image.pixels[:]:
            failures.append(f"{source_id}: packed image pixels cannot be read")
        for field in VISUAL_IDENTITY_FIELDS:
            if image.get(f"evidence_{field}") != identity.get(field):
                failures.append(f"{source_id}: image metadata differs at {field}")

    if source.get("kind") == "qualified-upright":
        original_id = source.get("original_source_id")
        original = sources.get(original_id)
        if not isinstance(original, dict) or original.get("kind") != "original":
            failures.append(f"{source_id}: original source record is missing")
        else:
            validate_visual_source(original_id, original, sources, checked, failures)


def validate_reopened_file():
    failures = []
    text = bpy.data.texts.get(REGISTRY_TEXT)
    if text is None:
        return [f"missing explicit registry text {REGISTRY_TEXT}"], [], []
    try:
        schema = json.loads(text.as_string())
    except json.JSONDecodeError as error:
        return [f"invalid explicit registry JSON: {error}"], [], []
    if schema.get("schema") != SCHEMA:
        failures.append("unexpected evidence registry schema")
    sources = schema.get("sources", {})
    bindings = schema.get("object_bindings", {})
    resolved = []
    checked = set()
    audited_sources = set()

    for obj in bpy.data.objects:
        if not obj.get("evidence_substantive"):
            continue
        object_id = obj.get("evidence_object_id")
        binding = bindings.get(object_id)
        if not isinstance(binding, dict) or binding.get("object_name") != obj.name:
            failures.append(f"{obj.name}: explicit object binding is missing")
            continue
        source_ids = binding.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids:
            failures.append(f"{obj.name}: declared source_ids are missing")
            continue
        for source_id in source_ids:
            source = sources.get(source_id)
            if not isinstance(source, dict) or not source.get("uncertainty"):
                failures.append(f"{obj.name}: unresolved source {source_id}")
                continue
            kind = source.get("kind")
            resolved.append(
                {"object_id": object_id, "source_id": source_id, "kind": kind}
            )
            audited_sources.add(source_id)
            if kind in ("original", "qualified-upright"):
                validate_visual_source(source_id, source, sources, checked, failures)
            elif kind == "documentary-unlocated":
                identity = source.get("identity", {})
                for field in DOCUMENTARY_IDENTITY_FIELDS:
                    if not identity.get(field):
                        failures.append(f"{source_id}: identity is missing {field}")
                if identity.get("source_id") != source_id:
                    failures.append(
                        f"{source_id}: identity source_id does not match registry key"
                    )
                if source.get("image") or identity.get("locator") != "unlocated":
                    failures.append(
                        f"{source_id}: documentary source invents an image binding"
                    )
            else:
                failures.append(f"{source_id}: unsupported source classification {kind}")
    audited_sources.update(checked)
    return failures, resolved, sorted(audited_sources)


def run(mode, root):
    blend_path, source_hashes_before = build_fixture(root, mode)
    naive_all_images_packed = bool(bpy.data.images) and all(
        image.packed_file is not None for image in bpy.data.images
    )
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    failures, resolved, audited_sources = validate_reopened_file()
    source_hashes_after = {
        path.name: file_sha256(path) for path in sorted((root / "sources").iterdir())
    }
    if source_hashes_after != source_hashes_before:
        failures.append("source image bytes changed")
    result = {
        "mode": mode,
        "blend": str(blend_path),
        "naive_all_images_packed": naive_all_images_packed,
        "resolved_bindings": resolved,
        "audited_source_ids": audited_sources,
        "source_hashes_before": source_hashes_before,
        "source_hashes_after": source_hashes_after,
        "passed": not failures,
        "failures": failures,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    (root / "result.json").write_text(rendered + "\n")
    print(rendered)
    if failures:
        raise AssertionError("; ".join(failures))


if __name__ == "__main__":
    arguments = parse_args()
    run(arguments.mode, arguments.output)
