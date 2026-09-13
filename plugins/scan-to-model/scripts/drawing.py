"""Pure NumPy geometry helpers for bounded architectural drawings."""

import numpy as np


EPS = 2e-5
PLANE_DISTANCE_TOLERANCE = 1e-6


def classify_selected_geometry(vertices_world, polygons, face_indices):
    """Classify exact point collapse in the selected world-space polygon vertices."""
    vertex_indices = sorted({
        int(vertex_index)
        for face_index in face_indices
        for vertex_index in polygons[int(face_index)]
    })
    if not vertex_indices:
        return {'finite': True, 'unique_point_count': 0,
                'all_vertices_coincident': False, 'vertex_indices': []}
    points = np.asarray(vertices_world, float)[vertex_indices]
    finite = bool(np.isfinite(points).all())
    unique_point_count = int(len(np.unique(points, axis=0))) if finite else 0
    return {
        'finite': finite,
        'unique_point_count': unique_point_count,
        'all_vertices_coincident': finite and unique_point_count == 1,
        'vertex_indices': vertex_indices,
    }


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


def coplanar_boundary_segments(polygons, tolerance=1e-7):
    """Return only outer edges of selected coplanar polygon pieces.

    Shared edges are removed exactly when two pieces use them.  The helper
    rejects non-coplanar pieces and edges used by more than two pieces rather
    than hiding uncertain topology with a hull or union operation.
    Plane consistency allows one micron of point distance for float32
    evaluation noise; edge matching continues to use ``tolerance``.
    """
    pieces = [np.asarray(p, float) for p in polygons if len(p) >= 2]
    if not pieces:
        return []
    if not all(np.isfinite(piece).all() for piece in pieces):
        raise ValueError('coplanar boundary pieces must be finite')
    polygon_pieces = [piece for piece in pieces if len(piece) >= 3]
    if not polygon_pieces:
        raise ValueError('line-only boundary pieces have no established plane')
    for piece in polygon_pieces:
        centered = piece - piece.mean(axis=0)
        if np.linalg.matrix_rank(centered) < 2:
            raise ValueError('coplanar boundary pieces must be non-degenerate')
    polygon_points = np.vstack(polygon_pieces)
    reference_point = polygon_points.mean(axis=0)
    _, _, singular_vectors = np.linalg.svd(polygon_points - reference_point, full_matrices=False)
    reference_normal = singular_vectors[-1]
    if np.max(np.abs((polygon_points - reference_point) @ reference_normal)) > PLANE_DISTANCE_TOLERANCE:
        raise ValueError('coplanar boundary pieces must share one plane')
    for piece in pieces:
        if len(piece) == 2 and np.max(np.abs((piece - reference_point) @ reference_normal)) > PLANE_DISTANCE_TOLERANCE:
            raise ValueError('line boundary piece is not on the selected plane')
    raw_edges = []
    for piece_index, piece in enumerate(pieces):
        if len(piece) == 2:
            edges = [(piece[0], piece[1])]
        else:
            edges = zip(piece, np.vstack((piece[1:], piece[:1])))
        for start, end in edges:
            if np.linalg.norm(end - start) <= tolerance:
                continue
            raw_edges.append((piece_index, np.asarray(start), np.asarray(end)))
    edge_starts = np.asarray([edge[1] for edge in raw_edges])
    edge_ends = np.asarray([edge[2] for edge in raw_edges])
    candidate_points = np.vstack((edge_starts, edge_ends))
    candidate_count = len(raw_edges)
    edge_records = {}
    for edge_index, (piece_index, start, end) in enumerate(raw_edges):
        delta = end - start
        length_squared = delta @ delta
        split = [0.0, 1.0]
        extension = tolerance * (np.abs(delta) + 1.0)
        lower = np.minimum(start, end) - extension
        upper = np.maximum(start, end) + extension
        valid = np.all((candidate_points >= lower) & (candidate_points <= upper), axis=1)
        valid[edge_index] = False
        valid[candidate_count + edge_index] = False
        candidate_points_for_edge = candidate_points[valid]
        if len(candidate_points_for_edge) > 0:
            parameters = ((candidate_points_for_edge - start) @ delta) / length_squared
            nearest = start + parameters[:, None] * delta
            candidate_valid = ((parameters >= -tolerance) & (parameters <= 1.0 + tolerance) &
                               (np.linalg.norm(candidate_points_for_edge - nearest, axis=1) <= tolerance))
            split.extend(np.clip(parameters[candidate_valid], 0.0, 1.0).tolist())
        split = sorted(set(round(value, 12) for value in split))
        for first, second in zip(split, split[1:]):
            sub_start, sub_end = start + first * delta, start + second * delta
            key_points = tuple(sorted((tuple(np.round(sub_start, 7)), tuple(np.round(sub_end, 7)))))
            edge_records.setdefault(key_points, []).append((piece_index, np.asarray([sub_start, sub_end])))
    boundary = []
    for key, records in edge_records.items():
        owners = {owner for owner, _ in records}
        if len(records) > 2 or len(owners) != len(records):
            raise ValueError('selected coplanar pieces contain a non-manifold edge')
        if len(records) == 1:
            boundary.append(records[0][1])
    return boundary
