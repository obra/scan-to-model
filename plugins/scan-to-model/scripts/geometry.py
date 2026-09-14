"""Small pure-Python helpers for explicit planar manufactured geometry."""

from __future__ import annotations

from math import hypot, isfinite


def _basis(tangent, normal):
    tangent = tuple(float(value) for value in tangent)
    normal = tuple(float(value) for value in normal)
    if len(tangent) != 2 or len(normal) != 2:
        raise ValueError("Planar basis vectors must have two components")
    if not all(isfinite(value) for value in tangent + normal):
        raise ValueError("Planar basis vectors must be finite")
    tangent_length = hypot(*tangent)
    normal_length = hypot(*normal)
    if abs(tangent_length - 1.0) > 1e-9 or abs(normal_length - 1.0) > 1e-9:
        raise ValueError("Planar basis vectors must be unit length")
    if abs(tangent[0] * normal[0] + tangent[1] * normal[1]) > 1e-9:
        raise ValueError("Planar basis vectors must be perpendicular")
    if hypot(normal[0] + tangent[1], normal[1] - tangent[0]) > 1e-9:
        raise ValueError("Planar basis vectors have the wrong handedness")
    return tangent, normal


def _bounds(bounds, name):
    values = tuple(float(value) for value in bounds)
    if len(values) != 2 or not all(isfinite(value) for value in values):
        raise ValueError(f"{name} must contain two finite values")
    if values[1] <= values[0]:
        raise ValueError(f"{name} must be increasing")
    return values


def plane_point(tangent, normal, plane_constant, u, z, depth=0.0):
    """Map local tangent/Z/depth coordinates onto an outward-facing plane."""
    tangent, normal = _basis(tangent, normal)
    plane_constant = float(plane_constant)
    u, z, depth = float(u), float(z), float(depth)
    if not all(isfinite(value) for value in (plane_constant, u, z, depth)):
        raise ValueError("Plane point coordinates must be finite")
    return (
        tangent[0] * u + normal[0] * (plane_constant + depth),
        tangent[1] * u + normal[1] * (plane_constant + depth),
        z,
    )


def panel_quad(tangent, normal, plane_constant, u_bounds, z_bounds, depth=0.0):
    """Return one front-facing planar quad and metre-space UV coordinates."""
    u0, u1 = _bounds(u_bounds, "u_bounds")
    z0, z1 = _bounds(z_bounds, "z_bounds")
    vertices = [
        plane_point(tangent, normal, plane_constant, u0, z0, depth),
        plane_point(tangent, normal, plane_constant, u0, z1, depth),
        plane_point(tangent, normal, plane_constant, u1, z1, depth),
        plane_point(tangent, normal, plane_constant, u1, z0, depth),
    ]
    return {
        "vertices": vertices,
        "faces": [[0, 1, 2, 3]],
        "uv_coordinates": [[u0, z0, 0], [u0, z1, 0], [u1, z1, 0], [u1, z0, 0]],
    }


def solid_bar(tangent, normal, plane_constant, u_bounds, z_bounds, depth):
    """Return a positive-volume rectangular bar extruded outward from a plane."""
    u0, u1 = _bounds(u_bounds, "u_bounds")
    z0, z1 = _bounds(z_bounds, "z_bounds")
    depth = float(depth)
    if not isfinite(depth) or depth <= 0.0:
        raise ValueError("depth must be positive and finite")
    base = panel_quad(tangent, normal, plane_constant, (u0, u1), (z0, z1), 0.0)
    front = panel_quad(tangent, normal, plane_constant, (u0, u1), (z0, z1), depth)
    vertices = base["vertices"] + front["vertices"]
    faces = [
        [0, 3, 2, 1],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [3, 7, 6, 2],
        [1, 2, 6, 5],
        [0, 4, 7, 3],
    ]
    tangent, normal = _basis(tangent, normal)
    return {
        "vertices": vertices,
        "faces": faces,
        "uv_coordinates": base["uv_coordinates"] + front["uv_coordinates"],
        "front_normal": (normal[0], normal[1], 0.0),
        "volume": (u1 - u0) * (z1 - z0) * depth,
        "u_bounds": (u0, u1),
        "z_bounds": (z0, z1),
    }


def aperture_bars(aperture_u, aperture_z, width, outer_u, outer_z):
    """Return four non-overlapping rectangular bar bounds and their true outer margins."""
    aperture_lo, aperture_hi = _bounds(aperture_u, "aperture_u")
    sill, head = _bounds(aperture_z, "aperture_z")
    outer_lo, outer_hi = _bounds(outer_u, "outer_u")
    outer_sill, outer_head = _bounds(outer_z, "outer_z")
    width = float(width)
    if not isfinite(width) or width <= 0.0:
        raise ValueError("width must be positive and finite")
    left_margin = aperture_lo - outer_lo
    right_margin = outer_hi - aperture_hi
    if left_margin < width or right_margin < width:
        raise ValueError("Aperture casing does not have the required outer margin")
    sill_margin = sill - outer_sill
    head_margin = outer_head - head
    if sill_margin < width or head_margin < width:
        raise ValueError("Aperture casing does not have the required outer margin")
    return [
        {"id": "left", "u_bounds": (aperture_lo - width, aperture_lo), "z_bounds": (sill, head), "margin_m": left_margin},
        {"id": "right", "u_bounds": (aperture_hi, aperture_hi + width), "z_bounds": (sill, head), "margin_m": right_margin},
        {"id": "sill", "u_bounds": (aperture_lo - width, aperture_hi + width), "z_bounds": (sill - width, sill), "margin_m": sill_margin},
        {"id": "head", "u_bounds": (aperture_lo - width, aperture_hi + width), "z_bounds": (head, head + width), "margin_m": head_margin},
    ]
