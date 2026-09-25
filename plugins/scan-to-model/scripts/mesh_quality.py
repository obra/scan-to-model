"""Find degenerate faces, inconsistent winding and coplanar surface overlaps."""

from collections import defaultdict

import numpy as np


def cross2(a, b):
    return a[0]*b[1] - a[1]*b[0]


def overlap_area(first, second):
    """Clip two counterclockwise triangles in their common plane."""
    polygon = [point.copy() for point in first]
    for a, b in zip(second, np.roll(second, -1, axis=0)):
        clipped = []
        for start, end in zip(polygon, polygon[1:] + polygon[:1]):
            ds, de = cross2(b-a, start-a), cross2(b-a, end-a)
            if ds >= 0:
                clipped.append(start)
            if (ds >= 0) != (de >= 0):
                clipped.append(start + ds / (ds-de) * (end-start))
        polygon = clipped
        if len(polygon) < 3:
            return 0.
    return abs(sum(cross2(a, b) for a, b in zip(polygon, polygon[1:] + polygon[:1]))) / 2


def review_meshes(meshes, tolerance=1e-5):
    findings, groups = [], defaultdict(list)
    for mesh in meshes:
        vertices = np.asarray(mesh["vertices"], dtype=float)
        if not np.isfinite(vertices).all():
            findings.append({"kind": "nonfinite_vertices", "object": mesh["id"]})
            continue
        edges = defaultdict(list)
        for index, face in enumerate(mesh["faces"]):
            for a, b in zip(face, face[1:] + face[:1]):
                edges[tuple(sorted([a, b]))].append((a, b))
            polygon = vertices[face]
            normal = sum((np.cross(a-polygon[0], b-polygon[0]) for a, b in zip(polygon[1:-1], polygon[2:])), np.zeros(3))
            if np.linalg.norm(normal) <= tolerance**2:
                findings.append({"kind": "degenerate_face", "object": mesh["id"], "face": index})
        wrong = [list(edge) for edge, uses in edges.items()
                 if len(uses) > 2 or (len(uses) == 2 and uses[0] == uses[1])]
        if wrong:
            findings.append({"kind": "inconsistent_winding_or_nonmanifold", "object": mesh["id"], "edges": wrong})
        volume = 0.
        for triangle in mesh["triangles"]:
            points = vertices[triangle["vertices"]]
            volume += float(np.dot(points[0], np.cross(points[1], points[2]))) / 6
            normal = np.cross(points[1]-points[0], points[2]-points[0])
            length = np.linalg.norm(normal)
            if length <= tolerance**2:
                continue
            normal /= length
            if normal[np.argmax(np.abs(normal))] < 0:
                normal = -normal
                points = points[::-1]
            # Angular bins screen candidates; distance and actual overlap decide findings.
            key = tuple(np.round(normal, 4))
            groups[key].append({"object": mesh["id"], "face": triangle["face"],
                                "points": points, "normal": normal, "low": points.min(0), "high": points.max(0)})
        if edges and all(len(uses) == 2 for uses in edges.values()) and volume < -tolerance**3:
            findings.append({"kind": "inverted_closed_mesh", "object": mesh["id"]})
    overlaps = defaultdict(float)
    for triangles in groups.values():
        active = []
        for current in sorted(triangles, key=lambda row: row["low"][0]):
            active = [previous for previous in active if previous["high"][0] >= current["low"][0] - tolerance]
            for previous in active:
                if (current["object"], current["face"]) == (previous["object"], previous["face"]):
                    continue
                if np.any(previous["high"] < current["low"] - tolerance) or np.any(current["high"] < previous["low"] - tolerance):
                    continue
                origin, normal = current["points"][0], current["normal"]
                if np.max(np.abs((previous["points"] - origin) @ normal)) > tolerance:
                    continue
                u = current["points"][1] - origin
                u /= np.linalg.norm(u)
                basis = np.array([u, np.cross(normal, u)])
                first, second = (current["points"] - origin) @ basis.T, (previous["points"] - origin) @ basis.T
                if cross2(second[1]-second[0], second[2]-second[0]) < 0:
                    second = second[::-1]
                area = overlap_area(first, second)
                if area > tolerance**2:
                    pair = tuple(sorted([(current["object"], current["face"]), (previous["object"], previous["face"])]))
                    overlaps[pair] += area
            active.append(current)
    findings.extend({"kind": "coplanar_overlap", "surfaces": [list(surface) for surface in pair],
                     "area_m2": area} for pair, area in sorted(overlaps.items()))
    return {"passed": not findings, "tolerance_m": tolerance, "findings": findings,
            "scope": "Degeneracy, edge winding, closed-mesh orientation and coplanar triangle overlap. Open architectural surfaces are allowed. This does not establish physical accuracy or detect every self-intersection."}
