"""Small Blender-only helpers for explicit world-space mesh geometry."""

import math

from mathutils import Vector


def _validated_geometry(vertices, faces):
    try:
        points = [tuple(float(value) for value in point) for point in vertices]
    except (TypeError, ValueError):
        raise ValueError('world vertices must be finite three-component points') from None
    if not points or any(len(point) != 3 or not all(math.isfinite(value) for value in point)
                          for point in points):
        raise ValueError('world vertices must be finite three-component points')

    try:
        polygons = [tuple(index for index in face) for face in faces]
    except (TypeError, ValueError):
        raise ValueError('faces must contain at least three valid vertex indices') from None
    if not polygons:
        raise ValueError('faces must contain at least three valid vertex indices')
    for polygon in polygons:
        if len(polygon) < 3 or len(set(polygon)) != len(polygon):
            raise ValueError('faces must contain at least three valid vertex indices')
        if any(isinstance(index, bool) or not isinstance(index, int)
               or index < 0 or index >= len(points) for index in polygon):
            raise ValueError('faces must contain at least three valid vertex indices')
    return points, polygons


def replace_world_mesh(obj, vertices, faces):
    """Replace editable mesh geometry from world-space vertices and ordered faces."""
    if obj.type != 'MESH':
        raise ValueError('target object must be a mesh')
    points, polygons = _validated_geometry(vertices, faces)
    try:
        inverse = obj.matrix_world.inverted()
    except (ValueError, RuntimeError):
        raise ValueError('target object world transform must be invertible') from None
    local = [tuple(inverse @ Vector(point)) for point in points]
    mesh = obj.data
    mesh.clear_geometry()
    mesh.from_pydata(local, [], polygons)
    mesh.update()

    actual_world = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
    if any((actual - Vector(expected)).length > 4e-6
           for actual, expected in zip(actual_world, points)):
        raise RuntimeError('replaced mesh world vertices do not match input')
    actual_faces = [tuple(polygon.vertices) for polygon in mesh.polygons]
    if actual_faces != polygons:
        raise RuntimeError('replaced mesh face order does not match input')
