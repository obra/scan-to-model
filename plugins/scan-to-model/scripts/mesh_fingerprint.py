"""Fingerprints for the supported coordinate and polygon buffers."""

import hashlib
import math
import struct


def _digest(values, code):
    payload = struct.pack('<' + code * len(values), *values)
    return hashlib.sha256(payload).hexdigest()


def geometry_fingerprints(vertices, polygons):
    """Return Blender-compatible hashes for explicit vertices and polygon order."""
    try:
        coordinates = [tuple(float(value) for value in vertex) for vertex in vertices]
    except (TypeError, ValueError):
        raise ValueError('vertices must contain finite three-component points') from None
    if any(len(vertex) != 3 or not all(math.isfinite(value) for value in vertex)
           for vertex in coordinates):
        raise ValueError('vertices must contain finite three-component points')

    try:
        faces = [tuple(index for index in polygon) for polygon in polygons]
    except (TypeError, ValueError):
        raise ValueError('polygons must contain valid indices') from None
    for face in faces:
        if len(face) < 3 or len(set(face)) != len(face):
            raise ValueError('polygons must contain valid indices')
        if any(isinstance(index, bool) or not isinstance(index, int)
               or index < 0 or index >= len(coordinates) for index in face):
            raise ValueError('polygons must contain valid indices')

    corners = [index for face in faces for index in face]
    starts = []
    offset = 0
    for face in faces:
        starts.append(offset)
        offset += len(face)
    return {
        'coordinates': _digest([value for vertex in coordinates for value in vertex], 'f'),
        'corners': _digest(corners, 'i'),
        'face_starts': _digest(starts, 'i'),
        'face_sizes': _digest([len(face) for face in faces], 'i'),
    }
