"""Fit independently sized ordered rectangles in a declared common 2-D frame."""

import argparse
import copy
import json
from pathlib import Path

import numpy as np


def finite_array(value, shape, label):
    array = np.asarray(value)
    if array.shape != shape or array.dtype.kind not in "iuf":
        raise ValueError(f"{label} must be a numeric array of shape {shape}")
    array = array.astype(float)
    if not np.isfinite(array).all():
        raise ValueError(f"{label} must be finite")
    return array


def fit_rectangles(spec):
    """Return a JSON-compatible candidate; see references/manufactured-shapes.md."""
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            return _fit_rectangles(spec)
    except (TypeError, KeyError, OverflowError, FloatingPointError) as error:
        raise ValueError("Malformed specification or numerically unsupported coordinates") from error


def _fit_rectangles(spec):
    if not isinstance(spec, dict):
        raise ValueError("Specification must be an object")
    # Preserve arbitrary JSON evidence metadata without interpreting its truth.
    json.dumps(spec, allow_nan=False)
    for key in ("frame_id", "units"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    frame = spec["frame"]
    if not isinstance(frame, dict):
        raise ValueError("frame must be an object")
    origin = finite_array(frame["origin"], (2,), "origin")
    u = finite_array(frame["u_axis"], (2,), "u_axis")
    if not np.isclose(np.linalg.norm(u), 1, rtol=0, atol=1e-12):
        raise ValueError("u_axis must be a unit vector")
    u = u / np.linalg.norm(u)
    fit_orientation = spec.get("fit_orientation", False)
    if not isinstance(fit_orientation, bool):
        raise ValueError("fit_orientation must be boolean")
    rows = spec["rectangles"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("At least one rectangle is required")
    identifiers = set()
    controls = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError("Each rectangle needs a nonempty string id")
        if row["id"] in identifiers:
            raise ValueError("Duplicate rectangle id")
        identifiers.add(row["id"])
        points = finite_array(row["controls"], (4, 2), "controls")
        edges = np.roll(points, -1, axis=0) - points
        scale = np.max(np.abs(edges))
        if scale == 0:
            raise ValueError("Degenerate controls")
        edges = edges / scale
        following = np.roll(edges, -1, axis=0)
        turns = edges[:, 0]*following[:, 1] - edges[:, 1]*following[:, 0]
        if np.any(turns <= 1e-12):
            raise ValueError("Controls must form a nondegenerate convex counterclockwise quadrilateral")
        controls.append(points - origin)
    controls = np.asarray(controls)
    centers = controls.mean(axis=1)
    centered = controls - centers[:, None, :]
    signs = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    if fit_orientation:
        # Eliminating each center and side length leaves a 2x2 eigenproblem.
        normalized = centered / np.max(np.abs(centered))
        horizontal = np.einsum("nki,k->ni", normalized, signs[:, 0]) / 4
        vertical = np.einsum("nki,k->ni", normalized, signs[:, 1]) / 4
        vertical_for_u = np.column_stack((vertical[:, 1], -vertical[:, 0]))
        matrix = horizontal.T @ horizontal + vertical_for_u.T @ vertical_for_u
        values, vectors = np.linalg.eigh(matrix)
        if values[1] - values[0] <= 1e-12 * values[1]:
            raise ValueError("Controls do not resolve a common orientation")
        fitted_u = vectors[:, 1]
        u = fitted_u if fitted_u @ u >= 0 else -fitted_u
    v = np.array([-u[1], u[0]])
    axes = np.column_stack((u, v))
    result_rows = []
    for row, points, center, offsets in zip(rows, controls, centers, centered):
        half_size = np.sum((offsets @ axes) * signs, axis=0) / 4
        if np.any(half_size <= 1e-12 * np.max(np.abs(offsets))):
            raise ValueError("Corner ordering must give positive width and height in the common frame")
        fitted = center + (signs * half_size) @ axes.T
        residuals = fitted - points
        local_center = center @ axes
        result_rows.append({
            "id": row["id"], "controls": copy.deepcopy(row["controls"]),
            "corners": (fitted + origin).tolist(),
            "local_bounds": [list(local_center-half_size), list(local_center+half_size)],
            "width": float(2*half_size[0]), "height": float(2*half_size[1]),
            "residuals": residuals.tolist(),
            "errors": np.hypot(residuals[:, 0], residuals[:, 1]).tolist(),
        })
    result = {
        "input": copy.deepcopy(spec),
        "frame": {"origin": origin.tolist(), "u_axis": u.tolist(), "v_axis": v.tolist()},
        "orientation_fitted": fit_orientation,
        "rectangles": result_rows,
        "status": "candidate; shape constraints do not establish scale, placement or shared axes",
    }
    json.dumps(result, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.spec.resolve() or (
        args.output.exists() and args.output.samefile(args.spec)
    ):
        raise ValueError("Output must not overwrite the input specification")
    result = fit_rectangles(json.loads(args.spec.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
