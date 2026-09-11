"""Exercise render visibility changes over a nested Blender collection."""

import argparse
import json
from pathlib import Path
import sys

import bpy


RENDERABLE_TYPES = {"CURVE", "FONT", "MESH", "SURFACE"}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    args.output = args.output.expanduser().resolve()
    try:
        args.output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f"output already exists: {args.output}")
    return args


def find_layer_collection(node, collection):
    if node.collection == collection:
        return node
    for child in node.children:
        found = find_layer_collection(child, collection)
        if found is not None:
            return found
    return None


def build_fixture():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_scene = bpy.context.scene
    root = bpy.data.collections.new("Render set")
    source_scene.collection.children.link(root)
    groups = []
    for group_index in range(11):
        group = bpy.data.collections.new(f"Group {group_index:02d}")
        root.children.link(group)
        groups.append(group)
        object_collection = group
        if group_index == 4:
            object_collection = bpy.data.collections.new("Nested group")
            group.children.link(object_collection)
        for object_index in range(34):
            mesh = bpy.data.meshes.new(
                f"Mesh {group_index:02d}-{object_index:02d}"
            )
            mesh.from_pydata(
                [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)]
            )
            obj = bpy.data.objects.new(
                f"Object {group_index:02d}-{object_index:02d}", mesh
            )
            obj.hide_render = object_index == 0
            object_collection.objects.link(obj)
    curve = bpy.data.curves.new("Curve data", "CURVE")
    root.objects.link(bpy.data.objects.new("Curve", curve))
    for index in range(5):
        camera = bpy.data.cameras.new(f"Camera data {index}")
        root.objects.link(bpy.data.objects.new(f"Camera {index}", camera))
    for index in range(4):
        light = bpy.data.lights.new(f"Light data {index}", "POINT")
        root.objects.link(bpy.data.objects.new(f"Light {index}", light))

    render_scene = bpy.data.scenes.new("Disposable render scene")
    render_scene.collection.children.link(root)
    render_scene.render.engine = "BLENDER_WORKBENCH"
    render_scene.render.use_compositing = False
    render_scene.render.use_sequencer = False
    bpy.context.window.scene = render_scene
    view_layer = render_scene.view_layers[0]
    excluded = find_layer_collection(view_layer.layer_collection, groups[7])
    assert excluded is not None
    excluded.exclude = True
    return root, view_layer


def main():
    args = parse_args()
    root, view_layer = build_fixture()
    render_objects = tuple(root.all_objects)
    assert len(render_objects) == 384
    original_hides = {obj.name: obj.hide_render for obj in render_objects}
    views = []
    try:
        for view_index in range(14):
            included = {
                obj.name
                for index, obj in enumerate(render_objects)
                if obj.type in RENDERABLE_TYPES
                and (index + view_index) % 3 == 0
                and not original_hides[obj.name]
                and obj.visible_get(view_layer=view_layer)
            }
            requested_hides = {
                obj.name: original_hides[obj.name] or obj.name not in included
                for obj in render_objects
            }

            for obj in render_objects:
                obj.hide_render = requested_hides[obj.name]

            view_layer.update()
            actual_hides = {obj.name: obj.hide_render for obj in render_objects}
            selected_visible = {
                obj.name
                for obj in render_objects
                if obj.type in RENDERABLE_TYPES
                and not obj.hide_render
                and obj.visible_get(view_layer=view_layer)
            }
            assert actual_hides == requested_hides
            assert selected_visible == included
            views.append(
                {"requested": len(included), "selected": len(selected_visible)}
            )
    finally:
        for obj in render_objects:
            obj.hide_render = original_hides[obj.name]
        view_layer.update()
        restored_hides = {obj.name: obj.hide_render for obj in render_objects}
        assert restored_hides == original_hides

    result = {
        "collection_objects": len(render_objects),
        "originally_hidden": sum(original_hides.values()),
        "views": views,
        "visibility_matches": all(
            view["requested"] == view["selected"] for view in views
        ),
        "restored": True,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    (args.output / "result.json").write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
