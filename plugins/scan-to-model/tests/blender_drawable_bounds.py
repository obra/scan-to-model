"""Compare curve object bounds with drawable geometry used for camera framing.

Run in Blender with --output /path/to/review/drawable-bounds. The directory must
be new. --method bound-box demonstrates the false clipping result and fails;
the default evaluated-mesh method checks exact geometry and must pass.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


OBJECT_NAMES = ('Short tube', 'Small face')


def bounds(points):
    return [[min(point[axis] for point in points) for axis in range(3)],
            [max(point[axis] for point in points) for axis in range(3)]]


def framing_points(obj, graph, method):
    """Require graph membership before collecting copied world-space points."""
    evaluated = graph.objects.get(obj.name)
    if evaluated is None or not evaluated.is_evaluated or evaluated.original != obj:
        raise ValueError(f'Object is not evaluated in the selected graph: {obj.name}')
    if method == 'bound-box':
        return [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
    mesh = evaluated.to_mesh()
    try:
        if mesh is None or not mesh.vertices:
            raise ValueError(f'No drawable mesh vertices: {obj.name}')
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def build_fixture(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.name = 'Source scene'
    group = bpy.data.collections.new('Framing fixtures')
    scene.collection.children.link(group)
    curve = bpy.data.curves.new('Short tube geometry', 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = .02
    curve.bevel_resolution = 2
    curve.use_fill_caps = True
    spline = curve.splines.new('POLY')
    spline.points.add(1)
    for point, coordinates in zip(spline.points, [(0, 0, 0, 1), (.4, 0, 0, 1)]):
        point.co = coordinates
    tube = bpy.data.objects.new('Short tube', curve)
    tube.location = (4, 3, 1)
    group.objects.link(tube)
    mesh = bpy.data.meshes.new('Small face geometry')
    mesh.from_pydata([(0, 0, -.02), (.4, 0, -.02), (0, 0, .02)], [], [(0, 1, 2)])
    face = bpy.data.objects.new('Small face', mesh)
    face.location = (4, 3, 1)
    group.objects.link(face)
    camera = bpy.data.objects.new('Framing camera', bpy.data.cameras.new('Framing camera'))
    scene.collection.objects.link(camera)
    camera.location = (4.2, 0, 1)
    camera.rotation_euler = (Vector((4.2, 3, 1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = .8
    scene.camera = camera
    scene.render.resolution_x = 400
    scene.render.resolution_y = 200
    scene.render.resolution_percentage = 100
    scene.view_layers[0].name = 'Included'
    excluded = scene.view_layers.new('Excluded')
    excluded.layer_collection.children[group.name].exclude = True
    bpy.data.scenes.new('Other scene')
    bpy.context.window.view_layer = excluded
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=False)


def activate(source, scope):
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.data.scenes['Other scene' if scope == 'inactive' else 'Source scene']
    bpy.context.window.scene = scene
    if scope == 'inactive':
        bpy.context.window.view_layer = scene.view_layers[0]
    else:
        bpy.context.window.view_layer = scene.view_layers['Excluded' if scope == 'excluded' else 'Included']
    return scene


def check_case(source, radius, method):
    scene = activate(source, 'included')
    tube = bpy.data.objects['Short tube']
    for point in tube.data.splines[0].points:
        point.radius = radius
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    data_counts = (len(bpy.data.meshes), len(bpy.data.curves))
    rows = []
    for name in OBJECT_NAMES:
        obj = bpy.data.objects[name]
        points = framing_points(obj, graph, method)
        actual_bounds = bounds(points)
        expected = ([[4, 3 - .02 * radius, 1 - .02 * radius],
                     [4.4, 3 + .02 * radius, 1 + .02 * radius]]
                    if obj.type == 'CURVE' else [[4, 3, .98], [4.4, 3, 1.02]])
        error = max(abs(a - e) for actual, wanted in zip(actual_bounds, expected)
                    for a, e in zip(actual, wanted))
        projected = [world_to_camera_view(scene, scene.camera, point) for point in points]
        clipped = any(point.x < 0 or point.x > 1 or point.y < 0 or point.y > 1
                      or point.z < scene.camera.data.clip_start or point.z > scene.camera.data.clip_end
                      for point in projected)
        rows.append({'object': name, 'point_count': len(points), 'world_bounds': actual_bounds,
                     'expected_drawable_bounds': expected, 'maximum_bound_error': error,
                     'projected_bounds': bounds(projected), 'clipped': clipped})
    assert (len(bpy.data.meshes), len(bpy.data.curves)) == data_counts
    return {'point_radius': radius, 'scene': scene.name, 'view_layer': bpy.context.view_layer.name,
            'objects': rows, 'temporary_meshes_released': True,
            'passed': all(row['maximum_bound_error'] < 1e-6 and not row['clipped'] for row in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--method', choices=('bound-box', 'evaluated-mesh'), default='evaluated-mesh')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output = args.output.expanduser().resolve()
    try:
        args.output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f'Output already exists: {args.output}')
    source = args.output / 'source.blend'
    build_fixture(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    cases = [check_case(source, radius, args.method) for radius in (.25, 1, 2)]
    rejected_scopes = []
    for scope in ('excluded', 'inactive'):
        activate(source, scope)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        for name in OBJECT_NAMES:
            try:
                framing_points(bpy.data.objects[name], graph, 'evaluated-mesh')
            except ValueError as error:
                rejected_scopes.append({'scope': scope, 'object': name, 'reason': str(error)})
            else:
                raise AssertionError(f'Accepted missing evaluation: {scope}/{name}')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    result = {'blender': bpy.app.version_string, 'method': args.method, 'source_sha256': before,
              'source_unchanged': True, 'cases': cases, 'rejected_scopes': rejected_scopes,
              'passed': all(case['passed'] for case in cases)}
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise AssertionError('Framing points do not match the drawable geometry')


if __name__ == '__main__':
    main()
