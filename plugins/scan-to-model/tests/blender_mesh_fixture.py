"""Exercise replacement of a mesh from explicit world-space geometry."""

from math import isclose
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from blender_mesh import replace_world_mesh


EPSILON = 1e-6


def assert_vector_close(actual, expected):
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert isclose(actual_value, expected_value, abs_tol=EPSILON)


def assert_matrix_close(actual, expected):
    for actual_row, expected_row in zip(actual, expected):
        assert_vector_close(actual_row, expected_row)


def world_vertices(obj):
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def polygon_normals_world(obj):
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    normals = []
    for polygon in obj.data.polygons:
        normal = normal_matrix @ polygon.normal
        normal.normalize()
        normals.append(normal)
    return normals


def assert_mesh_unchanged(obj, vertices, faces, state):
    assert_vector_close([value for vertex in world_vertices(obj) for value in vertex],
                        [value for vertex in vertices for value in vertex])
    assert [list(polygon.vertices) for polygon in obj.data.polygons] == faces
    assert obj.name == state['name']
    assert obj.parent == state['parent']
    assert_matrix_close(obj.matrix_world, state['matrix_world'])
    assert obj.hide_render == state['hide_render']
    assert obj.display_type == state['display_type']
    assert list(obj.data.materials) == state['materials']
    assert [(modifier.name, modifier.type, modifier.width, modifier.segments)
            for modifier in obj.modifiers] == state['modifiers']


def build_fixture():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    collection = bpy.data.collections.new('Mesh replacement fixtures')
    bpy.context.scene.collection.children.link(collection)

    parent = bpy.data.objects.new('Transformed parent', None)
    collection.objects.link(parent)
    parent.location = (2.5, -1.25, 0.75)
    parent.rotation_euler = (0.2, -0.35, 0.4)
    parent.scale = (1.4, 0.8, 1.1)

    mesh = bpy.data.meshes.new('Editable mesh')
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                      (0, 0, 0.2), (1, 0, 0.2), (1, 1, 0.2), (0, 1, 0.2)], [],
                     [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                      (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
    obj = bpy.data.objects.new('World mesh target', mesh)
    collection.objects.link(obj)
    obj.parent = parent
    obj.location = (-0.3, 0.45, 0.2)
    obj.rotation_euler = (-0.15, 0.25, -0.1)
    obj.scale = (0.7, 1.3, 0.9)
    obj.hide_render = True
    obj.display_type = 'WIRE'
    material = bpy.data.materials.new('Fixture material')
    obj.data.materials.append(material)
    modifier = obj.modifiers.new('Fixture bevel', 'BEVEL')
    modifier.width = 0.03
    modifier.segments = 2
    return obj


def main():
    obj = build_fixture()
    original_vertices = world_vertices(obj)
    original_faces = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
                      [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    state = {'name': obj.name, 'parent': obj.parent, 'matrix_world': Matrix(obj.matrix_world),
             'hide_render': obj.hide_render, 'display_type': obj.display_type,
             'materials': list(obj.data.materials),
             'modifiers': [(modifier.name, modifier.type, modifier.width, modifier.segments)
                           for modifier in obj.modifiers]}

    shared = obj.copy()
    shared.name = 'Shared mesh target'
    shared.data = obj.data
    obj.users_collection[0].objects.link(shared)
    shared_state = {'name': shared.name, 'parent': shared.parent,
                    'matrix_world': Matrix(shared.matrix_world), 'hide_render': shared.hide_render,
                    'display_type': shared.display_type, 'materials': list(shared.data.materials),
                    'modifiers': [(modifier.name, modifier.type, modifier.width, modifier.segments)
                                  for modifier in shared.modifiers]}
    try:
        replace_world_mesh(obj, original_vertices, original_faces)
    except ValueError:
        pass
    else:
        raise AssertionError('shared mesh datablock was accepted')
    assert_mesh_unchanged(obj, original_vertices, original_faces, state)
    assert_mesh_unchanged(shared, original_vertices, original_faces, shared_state)
    bpy.data.objects.remove(shared, do_unlink=True)

    for invalid_vertices, invalid_faces in (
            ([(0, 0, 0), (1, 0, 0), (float('nan'), 1, 0)], original_faces),
            (original_vertices, [[0, 1, 9], [0, 2, 3]])):
        try:
            replace_world_mesh(obj, invalid_vertices, invalid_faces)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid world mesh input was accepted')
        assert_mesh_unchanged(obj, original_vertices, original_faces, state)

    finite_matrix = Matrix(obj.matrix_world)
    obj.matrix_world[0][0] = float('nan')
    try:
        replace_world_mesh(obj, original_vertices, original_faces)
    except ValueError:
        pass
    else:
        raise AssertionError('nonfinite world transform was accepted')
    finally:
        obj.matrix_world = finite_matrix
    assert_mesh_unchanged(obj, original_vertices, original_faces, state)

    replacement_vertices = [Vector((3.1, -0.4, 1.7)), Vector((3.8, -0.4, 1.7)),
                            Vector((3.8, 0.2, 1.7)), Vector((3.1, 0.2, 1.7)),
                            Vector((3.1, -0.4, 1.9)), Vector((3.8, -0.4, 1.9)),
                            Vector((3.8, 0.2, 1.9)), Vector((3.1, 0.2, 1.9))]
    replacement_faces = [[0, 1, 5, 4], [4, 5, 6, 7], [0, 3, 2, 1],
                         [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]]
    replace_world_mesh(obj, replacement_vertices, replacement_faces)

    assert len(obj.data.vertices) == 8
    assert_vector_close([value for vertex in world_vertices(obj) for value in vertex],
                        [value for vertex in replacement_vertices for value in vertex])
    assert [list(polygon.vertices) for polygon in obj.data.polygons] == replacement_faces
    for normal, face in zip(polygon_normals_world(obj), replacement_faces):
        expected = ((replacement_vertices[face[1]] - replacement_vertices[face[0]]).cross(
            replacement_vertices[face[2]] - replacement_vertices[face[0]])).normalized()
        assert normal.dot(expected) > 1 - EPSILON
    assert obj.name == state['name']
    assert obj.parent == state['parent']
    assert_matrix_close(obj.matrix_world, state['matrix_world'])
    assert obj.hide_render == state['hide_render']
    assert obj.display_type == state['display_type']
    assert list(obj.data.materials) == state['materials']
    assert [(modifier.name, modifier.type, modifier.width, modifier.segments)
            for modifier in obj.modifiers] == state['modifiers']
    print('blender mesh replacement fixture passed')


if __name__ == '__main__':
    main()
