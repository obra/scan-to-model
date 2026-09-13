"""Finite multi-view geometry diagnostics.

This module solves the least-squares point nearest to a set of calibrated
viewing rays.  It reports conditioning and residuals so callers can judge
whether a result is useful; it does not decide whether geometry is accepted.
"""

import numpy as np


def solve_rays(origins, directions):
    """Solve the point nearest to finite 3-D rays and report diagnostics.

    ``origins`` and ``directions`` are matching ``N x 3`` finite arrays.
    Directions are normalized internally.  Along-ray distances are signed,
    so a negative value remains visible instead of being silently clipped.
    """
    origins = np.asarray(origins, dtype=float)
    directions = np.asarray(directions, dtype=float)
    if origins.ndim != 2 or origins.shape[1] != 3 or directions.shape != origins.shape:
        raise ValueError("origins and directions must be matching Nx3 arrays")
    if len(origins) < 2 or not np.isfinite(origins).all() or not np.isfinite(directions).all():
        raise ValueError("at least two finite rays are required")

    lengths = np.linalg.norm(directions, axis=1)
    if np.any(lengths == 0):
        raise ValueError("ray directions must be nonzero")
    directions = directions / lengths[:, None]

    projection = np.eye(3)[None, :, :] - directions[:, :, None] * directions[:, None, :]
    matrix = projection.sum(axis=0)
    vector = np.einsum("nij,nj->ni", projection, origins).sum(axis=0)
    point, _, rank, singular = np.linalg.lstsq(matrix, vector, rcond=None)
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else float("inf")

    along = np.einsum("ni,ni->n", point - origins, directions)
    closest = origins + along[:, None] * directions
    residuals = np.linalg.norm(point - closest, axis=1)
    return {
        "point": point,
        "directions_unit": directions,
        "along_ray_distances_m": along,
        "perpendicular_residuals_m": residuals,
        "rank": int(rank),
        "singular_values": singular,
        "condition_number": condition,
        "status": "ok" if rank == 3 else "degenerate",
    }
