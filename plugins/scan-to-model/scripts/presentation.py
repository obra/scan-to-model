"""Validate a saved architectural presentation contract and rendered sample receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from PIL import Image


SCHEMA_VERSION = 1
PRESENTATION_MODES = {"first-person-walkthrough", "cutaway-orbit"}
OBJECT_DISPOSITIONS = {"current-eligible", "retired", "excluded-source"}
SUPPORTED_RENDER_ENGINES = {"BLENDER_EEVEE", "CYCLES"}
FINDING_STATUSES = {"pass", "fail", "not-applicable"}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _load_json(path, label):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {label}: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _records(value, label, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise ValueError(f"{label} must be {qualifier}")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{label} entries must be objects")
    return value


def _string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _sha256(value, label):
    value = _string(value, label)
    if not SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA256")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _integer(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer of at least {minimum}")
    return value


def _string_list(value, label, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise ValueError(f"{label} must be {qualifier}")
    values = [_string(item, f"{label} entry") for item in value]
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicates")
    return values


def _indexed(records, label):
    result = {}
    for item in records:
        item_id = _string(item.get("id"), f"{label} ID")
        if item_id in result:
            raise ValueError(f"duplicate {label} ID: {item_id}")
        result[item_id] = item
    return result


def _material_overrides(value, eligible, label):
    overrides = []
    for index, item in enumerate(_records(value, label, allow_empty=True)):
        item_label = f"{label} entry {index}"
        object_id = _string(item.get("object_id"), f"{item_label} object_id")
        if object_id not in eligible:
            raise ValueError(f"{item_label} must reference a current-eligible object")
        overrides.append({
            "object_id": object_id,
            "original_material_id": _string(
                item.get("original_material_id"), f"{item_label} original_material_id",
            ),
            "render_material_id": _string(
                item.get("render_material_id"), f"{item_label} render_material_id",
            ),
            "intent": _string(item.get("intent"), f"{item_label} intent"),
        })
    if len({tuple(item.values()) for item in overrides}) != len(overrides):
        raise ValueError(f"{label} must not contain duplicates")
    return overrides


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_file(root, relative_value, label):
    relative = Path(_string(relative_value, label))
    if relative.is_absolute():
        raise ValueError(f"{label} must be relative")
    root = root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} escapes its receipt directory") from error
    if not path.is_file():
        raise ValueError(f"missing {label}: {path}")
    return path


def _exact_ids(actual, expected, label):
    actual_ids = set(_string_list(actual, label, allow_empty=True))
    if actual_ids != expected:
        missing = sorted(expected - actual_ids)
        extra = sorted(actual_ids - expected)
        raise ValueError(f"{label} differ; missing={missing}, extra={extra}")
    return actual_ids


def _validate_run(receipt):
    run = _mapping(receipt.get("run"), "run")
    command = _string_list(run.get("command"), "run command")
    _sha256(run.get("model_sha256"), "run model_sha256")
    _sha256(run.get("script_sha256"), "run script_sha256")
    _string(run.get("blender_version"), "run blender_version")
    return command


def _validate_contract(contract):
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"contract schema_version must be {SCHEMA_VERSION}")
    presentation = _mapping(contract.get("presentation"), "presentation")
    mode = _string(presentation.get("mode"), "presentation mode")
    if mode not in PRESENTATION_MODES:
        raise ValueError(f"unknown presentation mode: {mode}")

    eye_height = _mapping(presentation.get("eye_height_m"), "presentation eye_height_m")
    minimum_eye_height = _number(eye_height.get("minimum"), "minimum eye height")
    maximum_eye_height = _number(eye_height.get("maximum"), "maximum eye height")
    if minimum_eye_height > maximum_eye_height:
        raise ValueError("minimum eye height exceeds maximum eye height")

    object_records = _records(presentation.get("objects"), "presentation objects")
    objects = _indexed(object_records, "presentation object")
    dispositions = {}
    for object_id, item in objects.items():
        disposition = _string(item.get("disposition"), f"object {object_id} disposition")
        if disposition not in OBJECT_DISPOSITIONS:
            raise ValueError(f"object {object_id} has unknown disposition: {disposition}")
        dispositions[object_id] = disposition
    objects_by_disposition = {
        disposition: {object_id for object_id, value in dispositions.items() if value == disposition}
        for disposition in OBJECT_DISPOSITIONS
    }
    if not objects_by_disposition["current-eligible"]:
        raise ValueError("presentation must declare at least one current-eligible object")
    eligible = objects_by_disposition["current-eligible"]

    renderer = _mapping(presentation.get("renderer"), "presentation renderer")
    allowed_engines = set(_string_list(renderer.get("allowed_engines"), "allowed renderer engines"))
    if not allowed_engines <= SUPPORTED_RENDER_ENGINES:
        raise ValueError(
            "allowed renderer engines must contain only BLENDER_EEVEE or CYCLES"
        )
    material_mode = _string(renderer.get("material_mode"), "required material mode")
    if material_mode != "materials-and-textures":
        raise ValueError("presentation material mode must be materials-and-textures")
    required_materials = set(_string_list(
        renderer.get("required_material_ids"), "required material IDs",
    ))
    required_images = set(_string_list(
        renderer.get("required_image_ids"), "required image IDs",
    ))
    material_overrides = _material_overrides(
        renderer.get("material_overrides"), eligible, "presentation material overrides",
    )
    unverified_render_materials = {
        item["render_material_id"] for item in material_overrides
    } - required_materials
    if unverified_render_materials:
        raise ValueError(
            "render material overrides must be listed in required material IDs: "
            f"{sorted(unverified_render_materials)}"
        )

    feature_records = _records(
        presentation.get("required_features"), "required presentation features",
    )
    features = _indexed(feature_records, "required feature")
    for feature_id, feature in features.items():
        object_ids = set(_string_list(
            feature.get("object_ids"),
            f"required feature {feature_id} current-eligible object IDs",
        ))
        if not object_ids or not object_ids <= eligible:
            invalid = sorted(object_ids - eligible)
            raise ValueError(
                f"required feature {feature_id} has no valid current-eligible object set; "
                f"invalid={invalid}"
            )
        feature["_object_ids"] = object_ids
        feature["_view_intents"] = set(_string_list(
            feature.get("view_intents"), f"required feature {feature_id} view intents",
        ))
        feature["_finding_id"] = _string(
            feature.get("finding_id"), f"required feature {feature_id} finding ID",
        )
        feature["_minimum_visible_pixels"] = _integer(
            feature.get("minimum_visible_pixels"),
            f"required feature {feature_id} minimum_visible_pixels",
            minimum=1,
        )
        minimum_area = _number(
            feature.get("minimum_projected_area_px2"),
            f"required feature {feature_id} minimum_projected_area_px2",
        )
        if minimum_area <= 0:
            raise ValueError(
                f"required feature {feature_id} minimum_projected_area_px2 must be positive"
            )
        feature["_minimum_projected_area_px2"] = minimum_area

    return {
        "mode": mode,
        "minimum_eye_height": minimum_eye_height,
        "maximum_eye_height": maximum_eye_height,
        "objects_by_disposition": objects_by_disposition,
        "allowed_engines": allowed_engines,
        "material_mode": material_mode,
        "required_materials": required_materials,
        "required_images": required_images,
        "material_overrides": material_overrides,
        "features": features,
    }


def _validate_shots(receipt, contract_values):
    shot_records = _records(receipt.get("shots"), "presentation shots")
    shots = _indexed(shot_records, "shot")
    for shot_id, shot in shots.items():
        for field in ("intent", "scene_id", "view_layer_id", "camera_id", "floor_reference_id"):
            _string(shot.get(field), f"shot {shot_id} {field}")
        eye_height = _number(shot.get("eye_height_m"), f"shot {shot_id} eye height")
        if contract_values["mode"] == "first-person-walkthrough" and not (
            contract_values["minimum_eye_height"]
            <= eye_height
            <= contract_values["maximum_eye_height"]
        ):
            raise ValueError(f"shot {shot_id} eye height is outside the contract range")
        shot["_eye_height_m"] = eye_height

    transitions = _records(receipt.get("transitions"), "shot transitions", allow_empty=True)
    expected_pairs = list(zip(shot_records, shot_records[1:]))
    if len(transitions) != len(expected_pairs):
        raise ValueError("shot transitions must connect every adjacent route shot")
    for transition, (left, right) in zip(transitions, expected_pairs):
        if (
            transition.get("from_shot_id") != left["id"]
            or transition.get("to_shot_id") != right["id"]
        ):
            raise ValueError("shot transitions must follow route order")
        if transition.get("type") != "cut":
            raise ValueError("architectural presentation routes require cut transitions")
    return shots


def _validate_frame(frame_id, frame, coverage_root, shots, eligible, contract_values):
    shot_id = _string(frame.get("shot_id"), f"sample frame {frame_id} shot_id")
    if shot_id not in shots:
        raise ValueError(f"sample frame {frame_id} references unknown shot: {shot_id}")
    _integer(frame.get("frame_index"), f"sample frame {frame_id} frame_index")
    sample_path = _resolved_file(
        coverage_root, frame.get("file"), f"sample frame {frame_id} file",
    )
    expected_bytes = _integer(frame.get("bytes"), f"sample frame {frame_id} bytes", minimum=1)
    if sample_path.stat().st_size != expected_bytes:
        raise ValueError(f"sample frame {frame_id} size does not match its receipt")
    expected_sha256 = _sha256(frame.get("sha256"), f"sample frame {frame_id} SHA256")
    if _digest(sample_path) != expected_sha256:
        raise ValueError(f"sample frame {frame_id} SHA256 does not match its receipt")
    try:
        with Image.open(sample_path) as image:
            image.load()
            if image.width < 1 or image.height < 1:
                raise ValueError(f"sample frame {frame_id} has empty image dimensions")
    except (OSError, ValueError) as error:
        raise ValueError(f"sample frame {frame_id} is not a complete decodable image") from error

    camera_elevation = _number(
        frame.get("camera_elevation_m"), f"sample frame {frame_id} camera elevation",
    )
    floor_elevation = _number(
        frame.get("floor_elevation_m"), f"sample frame {frame_id} floor elevation",
    )
    eye_height = _number(frame.get("eye_height_m"), f"sample frame {frame_id} eye height")
    if not math.isclose(camera_elevation - floor_elevation, eye_height, abs_tol=1e-6):
        raise ValueError(f"sample frame {frame_id} eye height is not floor-relative")
    if not math.isclose(eye_height, shots[shot_id]["_eye_height_m"], abs_tol=1e-6):
        raise ValueError(f"sample frame {frame_id} eye height differs from its shot")
    if contract_values["mode"] == "first-person-walkthrough" and not (
        contract_values["minimum_eye_height"]
        <= eye_height
        <= contract_values["maximum_eye_height"]
    ):
        raise ValueError(f"sample frame {frame_id} eye height is outside the contract range")

    visible_ids = set(_string_list(
        frame.get("visible_object_ids"), f"sample frame {frame_id} visible object IDs",
        allow_empty=True,
    ))
    invalid_visible = visible_ids - eligible
    if invalid_visible:
        raise ValueError(
            f"sample frame {frame_id} reports non-eligible visible objects: "
            f"{sorted(invalid_visible)}"
        )
    material_ids = set(_string_list(
        frame.get("material_ids"), f"sample frame {frame_id} material IDs",
        allow_empty=True,
    ))
    image_ids = set(_string_list(
        frame.get("image_ids"), f"sample frame {frame_id} image IDs", allow_empty=True,
    ))

    visibility_records = _records(
        frame.get("object_visibility"), f"sample frame {frame_id} object visibility",
        allow_empty=True,
    )
    visibility = {}
    for item in visibility_records:
        object_id = _string(item.get("object_id"), f"sample frame {frame_id} object ID")
        if object_id in visibility:
            raise ValueError(f"sample frame {frame_id} repeats object visibility: {object_id}")
        if object_id not in eligible:
            raise ValueError(
                f"sample frame {frame_id} has visibility for non-eligible object: {object_id}"
            )
        bounds = item.get("projected_bounds_px")
        if not isinstance(bounds, list) or len(bounds) != 4:
            raise ValueError(
                f"sample frame {frame_id} object {object_id} projected bounds must have four values"
            )
        bounds = [_number(value, f"sample frame {frame_id} projected bound") for value in bounds]
        if bounds[2] < bounds[0] or bounds[3] < bounds[1]:
            raise ValueError(f"sample frame {frame_id} object {object_id} has inverted bounds")
        visible_pixels = _integer(
            item.get("visible_pixels"),
            f"sample frame {frame_id} object {object_id} visible_pixels",
        )
        projected_area = _number(
            item.get("projected_area_px2"),
            f"sample frame {frame_id} object {object_id} projected_area_px2",
        )
        if projected_area < 0:
            raise ValueError(
                f"sample frame {frame_id} object {object_id} projected_area_px2 must be nonnegative"
            )
        visibility[object_id] = {
            "visible_pixels": visible_pixels,
            "projected_area_px2": projected_area,
        }
    measured_visible = {
        object_id for object_id, values in visibility.items() if values["visible_pixels"] > 0
    }
    if visible_ids != measured_visible:
        raise ValueError(
            f"sample frame {frame_id} visible object IDs disagree with object visibility"
        )

    findings = _mapping(frame.get("findings"), f"sample frame {frame_id} findings")
    for finding_id, status in findings.items():
        _string(finding_id, f"sample frame {frame_id} finding ID")
        if status not in FINDING_STATUSES:
            raise ValueError(f"sample frame {frame_id} finding {finding_id} has invalid status")
    return {
        "id": frame_id,
        "shot_id": shot_id,
        "intent": shots[shot_id]["intent"],
        "materials": material_ids,
        "images": image_ids,
        "visibility": visibility,
        "findings": findings,
    }


def validate_presentation(contract_path, receipt_path):
    """Validate reported presentation evidence against a saved explicit contract."""
    contract_path = Path(contract_path).resolve()
    receipt_path = Path(receipt_path).resolve()
    contract = _load_json(contract_path, "presentation contract")
    receipt = _load_json(receipt_path, "presentation receipt")
    contract_values = _validate_contract(contract)

    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"receipt schema_version must be {SCHEMA_VERSION}")
    expected_contract_sha256 = _sha256(
        receipt.get("contract_sha256"), "receipt contract_sha256",
    )
    contract_sha256 = _digest(contract_path)
    if expected_contract_sha256 != contract_sha256:
        raise ValueError("receipt contract_sha256 does not match the contract")
    _validate_run(receipt)

    receipt_mode = _string(receipt.get("presentation_mode"), "receipt presentation mode")
    if receipt_mode != contract_values["mode"]:
        raise ValueError(
            f"receipt presentation mode {receipt_mode} does not match "
            f"contract mode {contract_values['mode']}"
        )
    renderer = _mapping(receipt.get("renderer"), "receipt renderer")
    engine = _string(renderer.get("engine"), "receipt renderer engine")
    if engine not in contract_values["allowed_engines"]:
        raise ValueError(f"receipt renderer engine is not allowed: {engine}")
    material_mode = _string(renderer.get("material_mode"), "receipt material mode")
    if material_mode != contract_values["material_mode"]:
        raise ValueError(
            f"receipt material mode {material_mode} does not match "
            f"{contract_values['material_mode']}"
        )
    material_overrides = _material_overrides(
        renderer.get("material_overrides"),
        contract_values["objects_by_disposition"]["current-eligible"],
        "receipt material overrides",
    )
    if material_overrides != contract_values["material_overrides"]:
        raise ValueError("receipt material overrides do not match the presentation contract")

    scene_audit = _mapping(receipt.get("scene_audit"), "scene audit")
    _string(scene_audit.get("method"), "scene audit method")
    dispositions = contract_values["objects_by_disposition"]
    eligible = dispositions["current-eligible"]
    _exact_ids(
        scene_audit.get("current_eligible_object_ids"), eligible,
        "scene audit current-eligible object IDs",
    )
    _exact_ids(scene_audit.get("included_object_ids"), eligible, "scene audit included object IDs")
    _exact_ids(
        scene_audit.get("retired_object_ids"), dispositions["retired"],
        "scene audit retired object IDs",
    )
    _exact_ids(
        scene_audit.get("excluded_source_object_ids"), dispositions["excluded-source"],
        "scene audit excluded-source object IDs",
    )

    shots = _validate_shots(receipt, contract_values)
    coverage_reference = _mapping(receipt.get("coverage_file"), "coverage file")
    coverage_path = _resolved_file(
        receipt_path.parent, coverage_reference.get("path"), "coverage file path",
    )
    coverage_sha256 = _digest(coverage_path)
    if coverage_sha256 != _sha256(coverage_reference.get("sha256"), "coverage file SHA256"):
        raise ValueError("coverage file SHA256 does not match its receipt")
    coverage = _load_json(coverage_path, "presentation coverage")
    if coverage.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"coverage schema_version must be {SCHEMA_VERSION}")
    method = _mapping(coverage.get("method"), "coverage method")
    method_name = _string(method.get("name"), "coverage method name")
    if method.get("visible_pixels") != "raster-count":
        raise ValueError("coverage visible_pixels method must be raster-count")
    _string(method.get("projected_area"), "coverage projected_area method")

    frame_records = _records(coverage.get("sample_frames"), "sample frames")
    indexed_frames = _indexed(frame_records, "sample frame")
    frames = [
        _validate_frame(
            frame_id, frame, coverage_path.parent, shots, eligible, contract_values,
        )
        for frame_id, frame in indexed_frames.items()
    ]
    sampled_shots = {frame["shot_id"] for frame in frames}
    if sampled_shots != set(shots):
        raise ValueError(
            f"sample frame coverage does not include every shot; "
            f"missing={sorted(set(shots) - sampled_shots)}"
        )

    material_ids = set().union(*(frame["materials"] for frame in frames))
    missing_materials = contract_values["required_materials"] - material_ids
    if missing_materials:
        raise ValueError(f"sample frames omit required material IDs: {sorted(missing_materials)}")
    image_ids = set().union(*(frame["images"] for frame in frames))
    missing_images = contract_values["required_images"] - image_ids
    if missing_images:
        raise ValueError(f"sample frames omit required image IDs: {sorted(missing_images)}")

    shot_intents = {shot["intent"] for shot in shots.values()}
    for feature_id, feature in contract_values["features"].items():
        missing_intents = feature["_view_intents"] - shot_intents
        if missing_intents:
            raise ValueError(
                f"required feature {feature_id} has no route shots for view intents: "
                f"{sorted(missing_intents)}"
            )
        for object_id in feature["_object_ids"]:
            for intent in feature["_view_intents"]:
                matching = [
                    frame for frame in frames
                    if frame["intent"] == intent
                    and frame["findings"].get(feature["_finding_id"]) == "pass"
                    and object_id in frame["visibility"]
                    and frame["visibility"][object_id]["visible_pixels"]
                    >= feature["_minimum_visible_pixels"]
                    and frame["visibility"][object_id]["projected_area_px2"]
                    >= feature["_minimum_projected_area_px2"]
                ]
                if not matching:
                    raise ValueError(
                        f"required feature {feature_id} lacks passing reported coverage for "
                        f"object {object_id} under view intent {intent}"
                    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "presentation_mode": receipt_mode,
        "contract_sha256": contract_sha256,
        "receipt_sha256": _digest(receipt_path),
        "coverage_sha256": coverage_sha256,
        "coverage_method": method_name,
        "eligible_objects": len(eligible),
        "retired_objects": len(dispositions["retired"]),
        "excluded_source_objects": len(dispositions["excluded-source"]),
        "shots": len(shots),
        "required_features": len(contract_values["features"]),
        "sample_frames": len(frames),
        "interpretation": (
            "Reported scene, projection, occlusion, material, image and inspection evidence "
            "matches the saved contract; actual rendered appearance still requires review."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate reported architectural presentation evidence",
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.output.exists():
            raise ValueError(f"output already exists: {arguments.output}")
        result = validate_presentation(arguments.contract, arguments.receipt)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        arguments.output.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"presentation validation failed: {error}\n")
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
