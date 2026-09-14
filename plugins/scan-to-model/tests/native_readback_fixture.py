"""Create a tiny Blender file exercising declared native membership."""

import argparse
import sys
import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", required=True)
    try:
        separator = sys.argv.index("--")
    except ValueError:
        separator = len(sys.argv)
    args = parser.parse_args(sys.argv[separator + 1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    room = bpy.data.collections.new("Fixture room")
    excluded = bpy.data.collections.new("Fixture excluded")
    scene.collection.children.link(room)
    scene.collection.children.link(excluded)
    parent = bpy.data.objects.new("Fixture parent", None)
    parent.location = Vector((2.0, 3.0, 4.0))
    room.objects.link(parent)

    mesh_data = bpy.data.meshes.new("Fixture mesh data")
    mesh_data.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    mesh = bpy.data.objects.new("Fixture mesh", mesh_data)
    room.objects.link(mesh)
    mesh.parent = parent
    mesh.hide_viewport = True
    mesh.hide_render = True

    cube_data = bpy.data.meshes.new("Fixture beveled cube data")
    cube_data.from_pydata([
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ], [], [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (4, 7, 3, 0),
    ])
    cube = bpy.data.objects.new("Fixture beveled cube", cube_data)
    room.objects.link(cube)
    bevel = cube.modifiers.new("Fixture bevel", "BEVEL")
    bevel.width = 0.1
    bevel.segments = 2

    curve_data = bpy.data.curves.new("Fixture curve data", "CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = 0.05
    spline = curve_data.splines.new("POLY")
    spline.points.add(1)
    spline.points[0].co = (0, 0, 0, 1)
    spline.points[1].co = (0, 0, 1, 1)
    curve = bpy.data.objects.new("Fixture curve", curve_data)
    room.objects.link(curve)
    curve.parent = parent

    empty_mesh_data = bpy.data.meshes.new("Fixture empty mesh data")
    empty_mesh = bpy.data.objects.new("Fixture empty mesh", empty_mesh_data)
    room.objects.link(empty_mesh)

    excluded_data = bpy.data.meshes.new("Fixture excluded mesh data")
    excluded_data.from_pydata([(0, 0, 0), (0, 1, 0), (0, 0, 1)], [], [(0, 1, 2)])
    excluded_mesh = bpy.data.objects.new("Fixture excluded mesh", excluded_data)
    excluded.objects.link(excluded_mesh)
    bpy.context.view_layer.layer_collection.children[excluded.name].exclude = True
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)


if __name__ == "__main__":
    main()
