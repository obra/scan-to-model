"""Exercise scratch-candidate promotion with real Blender file references."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import bpy


EXPECTED_UNPACKED_PIXELS = (1.0, 0.0, 0.0, 1.0) * 4


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--save-mode",
        choices=("default", "preserve-final-paths"),
        required=True,
        help="Use Blender's default relative remap or preserve source-relative paths.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory that will retain the synthetic scene and result.",
    )
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    args.output = args.output.expanduser().resolve()
    try:
        args.output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f"output already exists: {args.output}")
    return args


def create_png(path, color):
    image = bpy.data.images.new(path.stem, width=2, height=2)
    image.pixels = color * 4
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def packed_sha256(image):
    packed = image.packed_file
    if packed is None:
        raise AssertionError(f"{image.name} lost its packed payload")
    return hashlib.sha256(bytes(packed.data)).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_state(image, target_directory=None):
    state = {
        "stored": image.filepath,
        "resolved": str(Path(bpy.path.abspath(image.filepath)).resolve()),
        "packed": image.packed_file is not None,
    }
    if target_directory is not None:
        state["resolved_from_target"] = str(
            Path(
                bpy.path.abspath(image.filepath, start=str(target_directory))
            ).resolve()
        )
    return state


def read_unpacked_pixels(image):
    try:
        image.reload()
        pixels = tuple(image.pixels[:])
    except RuntimeError as error:
        return {"readable": False, "error": str(error)}
    expected = EXPECTED_UNPACKED_PIXELS
    return {
        "readable": tuple(image.size) == (2, 2)
        and len(pixels) == len(expected)
        and all(abs(actual - wanted) < 1e-6 for actual, wanted in zip(pixels, expected)),
        "size": list(image.size),
        "pixels": list(pixels),
    }


def run(save_mode, root):
    model_dir = root / "project" / "model"
    asset_dir = root / "project" / "assets"
    scratch_dir = root / "scratch"
    for directory in (model_dir, asset_dir, scratch_dir):
        directory.mkdir(parents=True)

    unpacked_path = asset_dir / "surface-unpacked.png"
    packed_path = asset_dir / "surface-packed.png"
    create_png(unpacked_path, (1.0, 0.0, 0.0, 1.0))
    create_png(packed_path, (0.0, 1.0, 0.0, 1.0))
    source_hashes_before = {
        path.name: file_sha256(path) for path in (unpacked_path, packed_path)
    }

    bpy.ops.wm.read_factory_settings(use_empty=True)
    unpacked = bpy.data.images.load(str(unpacked_path))
    packed = bpy.data.images.load(str(packed_path))
    unpacked.name = "Unpacked source"
    packed.name = "Packed source"
    packed.pack()
    for image in (unpacked, packed):
        image.use_fake_user = True
        image.filepath = f"//../assets/{Path(image.filepath).name}"
    expected_packed_hash = packed_sha256(packed)

    source_path = model_dir / "source.blend"
    candidate_path = scratch_dir / "candidate.blend"
    final_path = model_dir / "promoted.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source_path), relative_remap=False)

    if save_mode == "default":
        bpy.ops.wm.save_as_mainfile(filepath=str(candidate_path))
    else:
        bpy.ops.wm.save_as_mainfile(filepath=str(candidate_path), relative_remap=False)

    bpy.ops.wm.open_mainfile(filepath=str(candidate_path))
    candidate = {
        image.name: image_state(image, final_path.parent)
        for image in (
            bpy.data.images["Unpacked source"],
            bpy.data.images["Packed source"],
        )
    }
    candidate_packed_bytes_preserved = (
        packed_sha256(bpy.data.images["Packed source"]) == expected_packed_hash
    )
    candidate_blend_hash = file_sha256(candidate_path)
    shutil.copyfile(candidate_path, final_path)
    copied_blend_hash = file_sha256(final_path)
    bpy.ops.wm.open_mainfile(filepath=str(final_path))

    promoted = {
        name: image_state(bpy.data.images[name])
        for name in ("Unpacked source", "Packed source")
    }
    expected = {
        "Unpacked source": str(unpacked_path.resolve()),
        "Packed source": str(packed_path.resolve()),
    }
    unpacked_read = read_unpacked_pixels(bpy.data.images["Unpacked source"])
    packed_bytes_preserved = (
        packed_sha256(bpy.data.images["Packed source"]) == expected_packed_hash
    )
    source_hashes_after = {
        path.name: file_sha256(path) for path in (unpacked_path, packed_path)
    }

    failures = []
    for name, expected_path in expected.items():
        if candidate[name]["resolved_from_target"] != expected_path:
            failures.append(
                f"{name} resolves from the target directory to "
                f"{candidate[name]['resolved_from_target']}, expected {expected_path}"
            )
        if promoted[name]["resolved"] != expected_path:
            failures.append(
                f"{name} resolves to {promoted[name]['resolved']}, expected {expected_path}"
            )
    if not unpacked_read["readable"]:
        failures.append("reopened unpacked source pixels do not match the fixture")
    if not candidate_packed_bytes_preserved:
        failures.append("packed image bytes changed when reopening the candidate")
    if candidate_blend_hash != copied_blend_hash:
        failures.append("promoted blend bytes differ from the candidate")
    if not packed_bytes_preserved:
        failures.append("packed image bytes changed during candidate promotion")
    if source_hashes_after != source_hashes_before:
        failures.append("source image bytes changed during candidate promotion")

    result = {
        "save_mode": save_mode,
        "paths": {
            "source": str(source_path),
            "candidate": str(candidate_path),
            "promoted": str(final_path),
        },
        "candidate": candidate,
        "promoted": promoted,
        "expected": expected,
        "unpacked_read": unpacked_read,
        "source_hashes_before": source_hashes_before,
        "source_hashes_after": source_hashes_after,
        "source_hashes_unchanged": source_hashes_after == source_hashes_before,
        "candidate_packed_bytes_preserved": candidate_packed_bytes_preserved,
        "copied_blend_bytes_identical": candidate_blend_hash == copied_blend_hash,
        "packed_bytes_preserved": packed_bytes_preserved,
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
    run(arguments.save_mode, arguments.output)
