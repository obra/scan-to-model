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


def coplanar_boundary_records(polygons, tolerance=1e-7, line_tolerance=None):
    """Return outer segments with the input-piece owner for each segment.

    Shared edges are removed when two pieces use geometrically corresponding
    endpoints within ``tolerance``. The helper rejects non-coplanar pieces and
    edges used by more than two pieces rather than hiding uncertain topology
    with a hull or union operation. Plane consistency allows one micron of
    point distance for float32 evaluation noise; ``line_tolerance`` limits
    supporting-line distance and defaults to ``tolerance``.
    """
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError):
        raise ValueError('boundary tolerance must be finite and positive')
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('boundary tolerance must be finite and positive')
    if line_tolerance is None:
        line_tolerance = tolerance
    try:
        line_tolerance = float(line_tolerance)
    except (TypeError, ValueError):
        raise ValueError('boundary line tolerance must be finite and positive')
    if not np.isfinite(line_tolerance) or line_tolerance <= 0:
        raise ValueError('boundary line tolerance must be finite and positive')

    pieces = [(piece_index, np.asarray(piece, float))
              for piece_index, piece in enumerate(polygons) if len(piece) >= 2]
    if not pieces:
        return []
    if not all(np.isfinite(piece).all() for _, piece in pieces):
        raise ValueError('coplanar boundary pieces must be finite')
    polygon_pieces = [piece for _, piece in pieces if len(piece) >= 3]
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
    for _, piece in pieces:
        if len(piece) == 2 and np.max(np.abs((piece - reference_point) @ reference_normal)) > PLANE_DISTANCE_TOLERANCE:
            raise ValueError('line boundary piece is not on the selected plane')

    raw_edges = []
    for piece_index, piece in pieces:
        if len(piece) == 2:
            edges = [(piece[0], piece[1])]
        else:
            edges = zip(piece, np.vstack((piece[1:], piece[:1])))
        for start, end in edges:
            if np.linalg.norm(end - start) <= tolerance:
                continue
            raw_edges.append((piece_index, np.asarray(start), np.asarray(end)))
    if not raw_edges:
        return []

    edge_starts = np.asarray([edge[1] for edge in raw_edges])
    edge_ends = np.asarray([edge[2] for edge in raw_edges])
    candidate_points = np.vstack((edge_starts, edge_ends))
    candidate_owners = np.asarray([edge[0] for edge in raw_edges] * 2)
    candidate_count = len(raw_edges)
    segment_groups = []
    endpoint_buckets = {}

    def bucket(point):
        return tuple(np.floor(point / tolerance).astype(np.int64))

    def candidate_group_ids(point):
        cell = bucket(point)
        result = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    result.update(endpoint_buckets.get(
                        (cell[0] + dx, cell[1] + dy, cell[2] + dz), ()))
        return result

    def matching_group_ids(segment):
        start, end = segment
        candidates = candidate_group_ids(start) & candidate_group_ids(end)
        matches = []
        for group_id in candidates:
            group = segment_groups[group_id]
            for _, prior in group:
                same = max(np.linalg.norm(start - prior[0]),
                           np.linalg.norm(end - prior[1]))
                reverse = max(np.linalg.norm(start - prior[1]),
                              np.linalg.norm(end - prior[0]))
                prior_delta = prior[1] - prior[0]
                prior_length = np.linalg.norm(prior_delta)
                line_error = np.linalg.norm(
                    np.cross(segment - prior[0], prior_delta), axis=1).max() / prior_length
                if min(same, reverse) <= tolerance and line_error <= line_tolerance:
                    matches.append(group_id)
                    break
        return matches

    def remember_group(group_id, segment):
        for point in segment:
            endpoint_buckets.setdefault(bucket(point), set()).add(group_id)

    for edge_index, (piece_index, start, end) in enumerate(raw_edges):
        delta = end - start
        length_squared = delta @ delta
        split = [0.0, 1.0]
        lower = np.minimum(start, end) - tolerance
        upper = np.maximum(start, end) + tolerance
        valid = (np.all((candidate_points >= lower) & (candidate_points <= upper), axis=1) &
                 (candidate_owners != piece_index))
        valid[edge_index] = False
        valid[candidate_count + edge_index] = False
        candidate_points_for_edge = candidate_points[valid]
        if len(candidate_points_for_edge) > 0:
            parameters = ((candidate_points_for_edge - start) @ delta) / length_squared
            nearest = start + parameters[:, None] * delta
            candidate_valid = ((parameters >= -tolerance) & (parameters <= 1.0 + tolerance) &
                               (np.linalg.norm(candidate_points_for_edge - nearest, axis=1) <= tolerance))
            for parameter, point in zip(parameters[candidate_valid],
                                        candidate_points_for_edge[candidate_valid]):
                if np.linalg.norm(point - start) <= tolerance:
                    split.append(0.0)
                elif np.linalg.norm(point - end) <= tolerance:
                    split.append(1.0)
                else:
                    split.append(float(np.clip(parameter, 0.0, 1.0)))
        split = sorted(set(round(value, 12) for value in split))
        for first, second in zip(split, split[1:]):
            sub_start, sub_end = start + first * delta, start + second * delta
            segment = np.asarray([sub_start, sub_end])
            if np.linalg.norm(sub_end - sub_start) <= tolerance:
                continue
            matches = matching_group_ids(segment)
            if len(matches) > 1:
                raise ValueError('selected coplanar pieces contain a non-manifold edge')
            if matches:
                group = segment_groups[matches[0]]
                group.append((raw_edges[edge_index][0], segment))
                if len(group) > 2:
                    raise ValueError('selected coplanar pieces contain a non-manifold edge')
            else:
                group_id = len(segment_groups)
                segment_groups.append([(raw_edges[edge_index][0], segment)])
                remember_group(group_id, segment)

    boundary = []
    for records in segment_groups:
        owners = {owner for owner, _ in records}
        if len(records) > 2 or len(owners) != len(records):
            raise ValueError('selected coplanar pieces contain a non-manifold edge')
        if len(records) == 1:
            boundary.append(records[0])
    return boundary


def coplanar_boundary_segments(polygons, tolerance=1e-7, line_tolerance=None):
    """Return only outer edges of selected coplanar polygon pieces."""
    return [segment for _, segment in coplanar_boundary_records(
        polygons, tolerance, line_tolerance)]
