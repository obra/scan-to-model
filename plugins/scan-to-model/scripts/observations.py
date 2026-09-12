"""Create source-photo SVG evidence sheets from native pixel annotations."""

import argparse
import base64
import copy
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, UnidentifiedImageError

from pixel_inspection import (
    COORDINATE_CONTEXT_MAGNIFICATION, COORDINATE_CONTEXT_RADIUS_PX,
    COORDINATE_DETAIL_MAGNIFICATION, COORDINATE_DETAIL_RADIUS_PX,
    coordinate_inspection_bytes, display_crop_pixel_edges, display_dimensions,
    display_pixel_center, format_number, native_pixel_center,
)


SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
ORIENTATIONS = {"raw", "upright90cw"}
ENDPOINT_KINDS = {
    "visible physical termination",
    "occlusion",
    "image boundary",
    "annotation boundary",
    "unknown",
}
IMAGE_FORMATS = {
    ".jpeg": ("JPEG", "image/jpeg"),
    ".jpg": ("JPEG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
}
REVIEW_SCALE = "1 SVG unit per displayed source pixel"


def _svg(tag):
    return f"{{{SVG_NAMESPACE}}}{tag}"


def _digest(data):
    return sha256(data).hexdigest()


def _identifier(value, label):
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must match {ID_PATTERN.pattern}")
    return value


def _validate_xml_text(value, label):
    for character in value:
        codepoint = ord(character)
        if (
            codepoint in (0x09, 0x0A, 0x0D)
            or 0x20 <= codepoint <= 0xD7FF
            or 0xE000 <= codepoint <= 0xFFFD
            or 0x10000 <= codepoint <= 0x10FFFF
        ):
            continue
        raise ValueError(f"{label} contains a character XML 1.0 cannot represent")


def _record_list(spec, name, nonempty=False):
    rows = spec.get(name)
    if not isinstance(rows, list) or (nonempty and not rows):
        qualifier = "a nonempty" if nonempty else "a"
        raise ValueError(f"{name} must be {qualifier} list")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"Every {name} entry must be an object")
    return rows


def _unique_ids(rows, label):
    identifiers = set()
    for row in rows:
        identifier = _identifier(row.get("id"), f"{label} id")
        if identifier in identifiers:
            raise ValueError(f"Duplicate {label} id: {identifier}")
        identifiers.add(identifier)
    return identifiers


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _load_spec(data):
    try:
        spec = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Specification must be valid UTF-8 JSON") from error
    if not isinstance(spec, dict):
        raise ValueError("Specification must be an object")
    return spec


def _read_image(source, index, spec_root):
    source_id = source["id"]
    declared_path = source.get("path")
    if not isinstance(declared_path, str) or not declared_path:
        raise ValueError(f"Source {source_id} needs a nonempty path")
    source_path = Path(declared_path)
    suffix = source_path.suffix.lower()
    if suffix not in IMAGE_FORMATS:
        raise ValueError(f"Source {source_id} must be a JPEG or PNG path")
    try:
        if not source_path.is_absolute():
            source_path = spec_root / source_path
        resolved_path = source_path.resolve(strict=True)
    except (FileNotFoundError, OSError) as error:
        raise ValueError(f"Source {source_id} does not resolve to a readable file") from error
    if not resolved_path.is_file():
        raise ValueError(f"Source {source_id} must resolve to a file")

    source_bytes = resolved_path.read_bytes()
    source_hash = _digest(source_bytes)
    declared_hash = source.get("sha256")
    if declared_hash is not None:
        if not isinstance(declared_hash, str) or re.fullmatch(r"[0-9a-fA-F]{64}", declared_hash) is None:
            raise ValueError(f"Source {source_id} sha256 must be 64 hexadecimal characters")
        if declared_hash.lower() != source_hash:
            raise ValueError(f"Source {source_id} sha256 does not match its exact bytes")

    expected_format, media_type = IMAGE_FORMATS[suffix]
    try:
        with Image.open(BytesIO(source_bytes)) as image:
            image.verify()
        with Image.open(BytesIO(source_bytes)) as image:
            image.load()
            width, height = image.size
            decoded_format = image.format
            exif_orientation = image.getexif().get(274, 1)
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise ValueError(f"Source {source_id} is not a decodable JPEG or PNG") from error
    if decoded_format != expected_format:
        raise ValueError(f"Source {source_id} extension does not match its decoded format")
    if width <= 0 or height <= 0:
        raise ValueError(f"Source {source_id} has invalid decoded dimensions")
    if exif_orientation not in (None, 1):
        raise ValueError(
            f"Source {source_id} has EXIF orientation {exif_orientation}; normalize the contract explicitly"
        )
    orientation = source.get("orientation")
    if orientation not in ORIENTATIONS:
        raise ValueError(f"Source {source_id} orientation must be raw or upright90cw")
    return {
        "input_index": index,
        "id": source_id,
        "declared_path": declared_path,
        "path": resolved_path,
        "bytes": source_bytes,
        "sha256": source_hash,
        "media_type": media_type,
        "width": width,
        "height": height,
        "orientation": orientation,
    }


def _validate_coordinates(marks, source, observation_id):
    mark_type = marks.get("type")
    if mark_type not in {"point", "polyline", "polygon"}:
        raise ValueError(f"Observation {observation_id} has an unsupported mark type")
    if not isinstance(marks.get("meaning"), str) or not marks["meaning"].strip():
        raise ValueError(f"Observation {observation_id} needs a nonempty mark meaning")
    coordinates = marks.get("coordinates")
    minimum = {"point": 1, "polyline": 2, "polygon": 3}[mark_type]
    if not isinstance(coordinates, list) or len(coordinates) < minimum:
        raise ValueError(f"Observation {observation_id} has too few {mark_type} coordinates")
    if mark_type == "point" and len(coordinates) != 1:
        raise ValueError(f"Observation {observation_id} point must have exactly one coordinate")
    validated = []
    for point in coordinates:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(type(value) not in (int, float) for value in point)
            or not all(math.isfinite(value) for value in point)
        ):
            raise ValueError(f"Observation {observation_id} coordinates must be finite numeric pairs")
        u, v = point
        if not (0 <= u <= source["width"] - 1 and 0 <= v <= source["height"] - 1):
            raise ValueError(f"Observation {observation_id} coordinate is outside native pixel centers")
        validated.append(copy.deepcopy(point))
    return mark_type, validated


def _validate_endpoints(observation, mark_type, coordinate_count):
    observation_id = observation["id"]
    endpoints = observation.get("endpoints")
    if not isinstance(endpoints, list) or not all(isinstance(row, dict) for row in endpoints):
        raise ValueError(f"Observation {observation_id} endpoints must be a list of objects")
    if mark_type != "polyline":
        if endpoints:
            raise ValueError(f"Observation {observation_id} only uses endpoints for a polyline")
        return
    if len(endpoints) != 2 or {row.get("index") for row in endpoints} != {0, -1}:
        raise ValueError(f"Observation {observation_id} needs endpoint records at indices 0 and -1")
    for endpoint in endpoints:
        if endpoint.get("kind") not in ENDPOINT_KINDS:
            raise ValueError(f"Observation {observation_id} has an unsupported endpoint kind")
        if not isinstance(endpoint.get("basis"), str) or not endpoint["basis"].strip():
            raise ValueError(f"Observation {observation_id} endpoint needs a nonempty basis")
    if coordinate_count < 2:
        raise ValueError(f"Observation {observation_id} polyline needs two distinct endpoints")


def _validate_spec(spec, spec_root):
    try:
        json.dumps(spec, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("Specification must contain finite JSON values") from error
    sources = _record_list(spec, "sources", nonempty=True)
    observations = _record_list(spec, "observations")
    features = _record_list(spec, "features")
    source_ids = _unique_ids(sources, "source")
    observation_ids = _unique_ids(observations, "observation")
    _unique_ids(features, "feature")

    loaded_sources = []
    resolved_paths = set()
    for index, source in enumerate(sources):
        loaded = _read_image(source, index, spec_root)
        if loaded["path"] in resolved_paths:
            raise ValueError("Each source path must identify a different file")
        resolved_paths.add(loaded["path"])
        loaded_sources.append(loaded)
    source_by_id = {source["id"]: source for source in loaded_sources}

    annotations = []
    for observation in observations:
        observation_id = observation["id"]
        source_id = observation.get("source_id")
        if source_id not in source_ids:
            raise ValueError(f"Observation {observation_id} references an unknown source")
        if not isinstance(observation.get("qualification"), dict):
            raise ValueError(f"Observation {observation_id} qualification must be an object")
        label = observation.get("label", observation_id)
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"Observation {observation_id} label must be a nonempty string")
        _validate_xml_text(label, f"Observation {observation_id} label")
        marks = observation.get("marks")
        if not isinstance(marks, dict):
            raise ValueError(f"Observation {observation_id} marks must be an object")
        source = source_by_id[source_id]
        mark_type, native = _validate_coordinates(marks, source, observation_id)
        _validate_endpoints(observation, mark_type, len(native))
        display = [display_pixel_center(point, source) for point in native]
        round_trip = [native_pixel_center(point, source) for point in display]
        if any(
            not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12)
            for actual_point, expected_point in zip(round_trip, native)
            for actual, expected in zip(actual_point, expected_point)
        ):
            raise ValueError(f"Observation {observation_id} coordinate transform did not round trip")
        annotations.append({
            "id": observation_id,
            "label": label,
            "source_id": source_id,
            "type": mark_type,
            "native_coordinates": native,
            "display_coordinates": display,
            "coordinate_round_trip_verified": True,
        })

    for feature in features:
        feature_id = feature["id"]
        references = feature.get("observation_ids")
        if not isinstance(references, list) or not references:
            raise ValueError(f"Feature {feature_id} needs observation_ids")
        if not all(isinstance(value, str) for value in references) or len(references) != len(set(references)):
            raise ValueError(f"Feature {feature_id} observation_ids must be unique strings")
        if any(reference not in observation_ids for reference in references):
            raise ValueError(f"Feature {feature_id} references an unknown observation")
        if not isinstance(feature.get("qualification"), dict):
            raise ValueError(f"Feature {feature_id} qualification must be an object")
    return loaded_sources, annotations


def _sheet_bytes(source, annotations, bounds=None, title=None, draw_labels=True):
    display_width, display_height = display_dimensions(source)
    if bounds is None:
        bounds = [0, 0, display_width, display_height]
    left, top, right, bottom = bounds
    width, height = right - left, bottom - top
    title = title or f"Annotations for {source['id']}"
    root = ET.Element(_svg("svg"), {
        "viewBox": f"{left} {top} {width} {height}",
        "width": str(width),
        "height": str(height),
        "role": "img",
        "aria-label": title,
    })
    ET.SubElement(root, _svg("title")).text = title
    image_attributes = {
        "x": "0",
        "y": "0",
        "width": str(source["width"]),
        "height": str(source["height"]),
        "preserveAspectRatio": "none",
        "href": (
            f"data:{source['media_type']};base64,"
            + base64.b64encode(source["bytes"]).decode("ascii")
        ),
    }
    if source["orientation"] == "upright90cw":
        image_attributes["transform"] = f"matrix(0 1 -1 0 {source['height']} 0)"
    ET.SubElement(root, _svg("image"), image_attributes)

    group = ET.SubElement(root, _svg("g"), {
        "fill": "none",
        "stroke": "#ff2d20",
        "stroke-width": "2",
        "vector-effect": "non-scaling-stroke",
    })
    for annotation in annotations:
        displayed_edges = [[point[0] + 0.5, point[1] + 0.5]
                           for point in annotation["display_coordinates"]]
        common = {"data-observation-id": annotation["id"]}
        if annotation["type"] == "point":
            x, y = displayed_edges[0]
            ET.SubElement(group, _svg("circle"), {
                **common, "cx": format_number(x), "cy": format_number(y), "r": "4",
            })
        else:
            points = " ".join(f"{format_number(x)},{format_number(y)}" for x, y in displayed_edges)
            tag = "polyline" if annotation["type"] == "polyline" else "polygon"
            ET.SubElement(group, _svg(tag), {**common, "points": points})
        if draw_labels:
            x, y = displayed_edges[0]
            label_on_right = x <= left + width / 2
            label_attributes = {
                "x": format_number(x),
                "y": format_number(y),
                "dx": "6" if label_on_right else "-6",
                "dy": "14" if y <= top + height / 2 else "-6",
                "text-anchor": "start" if label_on_right else "end",
                "font-family": "sans-serif",
                "font-size": "14",
            }
            outline = ET.SubElement(group, _svg("text"), {
                **label_attributes,
                "fill": "#000000",
                "stroke": "#000000",
                "stroke-width": "3",
                "stroke-linejoin": "round",
                "aria-hidden": "true",
            })
            outline.text = annotation["label"]
            foreground = ET.SubElement(group, _svg("text"), {
                **label_attributes,
                "fill": "#ffffff",
                "stroke": "none",
                "data-observation-id": annotation["id"],
            })
            foreground.text = annotation["label"]
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def _display_image(source):
    with Image.open(BytesIO(source["bytes"])) as image:
        displayed = image.convert("RGBA")
    if source["orientation"] == "upright90cw":
        displayed = displayed.transpose(Image.Transpose.ROTATE_270)
    return displayed


def generate_evidence(spec_path, output_dir, coordinate_inspections=False):
    """Validate a JSON specification and write a new evidence directory."""
    if not isinstance(coordinate_inspections, bool):
        raise ValueError("coordinate_inspections must be a boolean")
    spec_path = Path(spec_path).resolve(strict=True)
    output_dir = Path(output_dir)
    if os.path.lexists(output_dir):
        raise FileExistsError(f"Output path already exists: {output_dir}")
    spec_root = spec_path.parent.resolve(strict=True)
    spec_before = spec_path.read_bytes()
    spec = _load_spec(spec_before)
    sources, annotations = _validate_spec(spec, spec_root)
    sheets = {}
    source_records = []
    source_by_id = {source["id"]: source for source in sources}
    displayed_sources = (
        {source["id"]: _display_image(source) for source in sources}
        if coordinate_inspections else {}
    )
    for source in sources:
        source_annotations = [row for row in annotations if row["source_id"] == source["id"]]
        sheet_path = f"{source['id']}.svg"
        sheet = _sheet_bytes(source, source_annotations)
        sheets[sheet_path] = sheet
        display_width, display_height = display_dimensions(source)
        source_records.append({
            "input_index": source["input_index"],
            "id": source["id"],
            "declared_path": source["declared_path"],
            "resolved_path": str(source["path"]),
            "media_type": source["media_type"],
            "sha256_before": source["sha256"],
            "sha256_after": None,
            "unchanged": None,
            "native": {
                "width": source["width"],
                "height": source["height"],
                "coordinates": "pixel centers; top-left origin; u right; v down",
            },
            "display": {
                "orientation": source["orientation"],
                "width": display_width,
                "height": display_height,
                "native_to_display": (
                    "(u,v) -> (u,v)" if source["orientation"] == "raw"
                    else f"(u,v) -> ({source['height']}-1-v,u)"
                ),
            },
            "sheet": {"path": sheet_path, "sha256": _digest(sheet)},
        })

    observations_by_id = {row["id"]: row for row in spec["observations"]}
    for annotation in annotations:
        source = source_by_id[annotation["source_id"]]
        assertion_bounds = display_crop_pixel_edges(annotation["display_coordinates"], source)
        review_root = f"review/{annotation['id']}"
        assertion_path = f"{review_root}/assertion.svg"
        assertion_sheet = _sheet_bytes(
            source,
            [annotation],
            assertion_bounds,
            f"Assertion review for {annotation['label']}",
            draw_labels=False,
        )
        sheets[assertion_path] = assertion_sheet
        review = {
            "status": "pending visual review",
            "assertion": {
                "path": assertion_path,
                "sha256": _digest(assertion_sheet),
                "display_bounds": assertion_bounds,
                "scale": REVIEW_SCALE,
            },
            "endpoints": [],
            "coordinate_inspection": None,
        }
        for endpoint in observations_by_id[annotation["id"]]["endpoints"]:
            index = endpoint["index"]
            display_coordinate = annotation["display_coordinates"][index]
            endpoint_bounds = display_crop_pixel_edges([display_coordinate], source)
            suffix = "0" if index == 0 else "last"
            endpoint_path = f"{review_root}/endpoint-{suffix}.svg"
            endpoint_annotation = {
                "id": annotation["id"],
                "label": f"{annotation['label']}: {endpoint['kind']}",
                "source_id": annotation["source_id"],
                "type": "point",
                "display_coordinates": [display_coordinate],
            }
            endpoint_sheet = _sheet_bytes(
                source,
                [endpoint_annotation],
                endpoint_bounds,
                f"Endpoint review for {annotation['label']}: {endpoint['kind']}",
                draw_labels=False,
            )
            sheets[endpoint_path] = endpoint_sheet
            review["endpoints"].append({
                "index": index,
                "kind": endpoint["kind"],
                "basis": endpoint["basis"],
                "path": endpoint_path,
                "sha256": _digest(endpoint_sheet),
                "display_bounds": endpoint_bounds,
                "scale": REVIEW_SCALE,
            })
        if coordinate_inspections:
            inspection_path = f"{review_root}/coordinates.png"
            inspection, coordinates = coordinate_inspection_bytes(
                source, displayed_sources[source["id"]], annotation
            )
            sheets[inspection_path] = inspection
            review["coordinate_inspection"] = {
                "path": inspection_path,
                "sha256": _digest(inspection),
                "media_type": "image/png",
                "resampling": "nearest",
                "context_radius_display_pixels": COORDINATE_CONTEXT_RADIUS_PX,
                "context_magnification": COORDINATE_CONTEXT_MAGNIFICATION,
                "detail_radius_display_pixels": COORDINATE_DETAIL_RADIUS_PX,
                "detail_magnification": COORDINATE_DETAIL_MAGNIFICATION,
                "nearest_pixel_rule": "floor(coordinate + 0.5) in native pixel-center coordinates",
                "coordinates": coordinates,
            }
        annotation["review"] = review

    spec_after = spec_path.read_bytes()
    if spec_after != spec_before:
        raise ValueError("Specification bytes changed during generation")
    for source, record in zip(sources, source_records):
        after = source["path"].read_bytes()
        record["sha256_after"] = _digest(after)
        record["unchanged"] = after == source["bytes"]
        if not record["unchanged"]:
            raise ValueError(f"Source {source['id']} bytes changed during generation")

    record = {
        "schema_version": 3,
        "generator": {
            "script": "scripts/observations.py",
            "coordinate_inspections": coordinate_inspections,
        },
        "input_proof": {
            "sha256_before": _digest(spec_before),
            "sha256_after": _digest(spec_after),
            "unchanged": spec_after == spec_before,
        },
        "input": copy.deepcopy(spec),
        "sources": source_records,
        "annotations": annotations,
        "limits": (
            "Annotation rendering does not recognize features, choose correspondence, estimate depth, "
            "register coordinates or establish feature completeness. Review artifacts remain pending "
            "until a person checks the depicted construction and endpoint meanings."
        ),
    }
    record_bytes = json.dumps(record, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    for name, data in sheets.items():
        destination = output_dir / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (output_dir / "evidence.json").write_bytes(record_bytes)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coordinate-inspections", action="store_true")
    args = parser.parse_args()
    generate_evidence(args.spec, args.output, coordinate_inspections=args.coordinate_inspections)


if __name__ == "__main__":
    main()
