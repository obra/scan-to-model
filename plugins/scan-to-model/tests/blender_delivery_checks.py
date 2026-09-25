"""Exercise native delivery rejection contracts against an actual saved fixture."""

import argparse
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_delivery import context, readback
from delivery_contract import write_json


def rejects(function):
    try:
        function()
    except ValueError:
        return
    raise AssertionError("invalid native state was accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["job", "appearance", "native", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    job, appearance, native = [json.loads(file.read_text()) for file in [args.job, args.appearance, args.native]]
    readback(job, appearance, native)
    image = bpy.data.images["STM source synthetic-photo"]
    image.unpack(method="USE_ORIGINAL")
    assert not image.packed_file
    rejects(lambda: readback(job, appearance, native))
    assert not image.packed_file, "readback repaired the defect instead of reporting it"
    image.pack()
    readback(job, appearance, native)

    scene = bpy.context.scene
    scene.unit_settings.scale_length = .01
    rejects(lambda: context(job))
    scene.unit_settings.scale_length = 1

    material = bpy.data.materials["STM projection"]
    output = next(node for node in material.node_tree.nodes if node.type == "OUTPUT_MATERIAL" and node.is_active_output)
    material.node_tree.links.remove(output.inputs["Surface"].links[0])
    rejects(lambda: readback(job, appearance, native))

    parent, child = [bpy.data.collections.new(name) for name in ["Hidden parent", "Visible child"]]
    scene.collection.children.link(parent)
    parent.children.link(child)
    obj = scene.objects["floor-a"]
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    child.objects.link(obj)
    parent.hide_render = True
    rejects(lambda: context(job))
    write_json(args.output, {"unpacked_image_rejected_without_repair": True,
                            "nonmetre_scene_rejected": True, "disconnected_shader_rejected": True,
                            "hidden_collection_ancestry_rejected": True})


if __name__ == "__main__":
    main()
