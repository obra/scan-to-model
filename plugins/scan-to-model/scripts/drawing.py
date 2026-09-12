"""Pure NumPy geometry helpers for bounded architectural drawings."""

import numpy as np


EPS = 2e-5


def project(p, right, up):
    """Project 3-D points onto the declared drawing right/up basis."""
    p = np.asarray(p, float)
    return np.column_stack((p @ np.asarray(right, float), p @ np.asarray(up, float)))


def clipped(p, axis, value, keep_below):
    """Clip a closed polygon against one coordinate half-space."""
    out = []
    for a, b in zip(p, np.vstack((p[1:], p[:1]))):
        da = a[axis] - value
        db = b[axis] - value
        ia = da <= EPS if keep_below else da >= -EPS
        ib = db <= EPS if keep_below else db >= -EPS
        if ia:
            out.append(a)
        if ia != ib and abs(da - db) > 1e-12:
            out.append(a + da / (da - db) * (b - a))
    return np.asarray(out, float)


def intersect_face(p, axis, value):
    """Return cut points for a convex planar polygon boundary.

    The boundary walk and deduplication produce one cut interval for a convex
    face. Callers must provide a convex planar polygon; a concave face can have
    multiple disjoint cut intervals that this compact result does not model.
    """
    vals = p[:, axis] - value
    out = []
    for a, b, va, vb in zip(p, np.vstack((p[1:], p[:1])), vals, np.r_[vals[1:], vals[:1]]):
        if abs(va) <= EPS:
            out.append(a)
        if va * vb < -EPS * EPS:
            t = va / (va - vb)
            out.append(a + t * (b - a))
    unique = []
    for point in out:
        if not any(np.linalg.norm(point - prior) < 1e-7 for prior in unique):
            unique.append(point)
    return unique


def line_segments(p, closed=True):
    """Return the boundary segments of a polygon or a two-point segment."""
    if len(p) < 2:
        return []
    if len(p) == 2:
        return [p]
    return [np.array([a, b]) for a, b in zip(p, np.vstack((p[1:], p[:1])))] if closed else []
