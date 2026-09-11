"""Read-only Blender scene inventory and optional camera renders."""
import argparse, hashlib, json, math, os, re, sys, traceback
from array import array
from pathlib import Path

try:
    import bpy
except ImportError:
    bpy = None

SCHEMA_VERSION = 1


def value_snapshot(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numeric value in scene inventory")
        return value
    if isinstance(value, bpy.types.ID):
        return {"name": value.name, "library": value.library.filepath if value.library else None}
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        return {k: value_snapshot(v) for k, v in value.items()}
    if isinstance(value, set):
        return sorted(value)
    return [value_snapshot(v) for v in value]


def tags(owner):
    try:
        items = owner.items()
    except TypeError:
        # Only some Blender structures (including Geometry Nodes modifiers)
        # support custom properties.
        return {}
    return {k: value_snapshot(v) for k, v in items}


def properties(owner, exclude=()):
    """Capture writable scalar/array settings and named datablock references.

    Nested RNA structures and collections require explicit coverage below.
    """
    result = {}
    for prop in owner.bl_rna.properties:
        name = prop.identifier
        if name in exclude or name == "rna_type" or prop.is_readonly:
            continue
        value = getattr(owner, name)
        if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'}:
            result[name] = value_snapshot(value)
        elif prop.type == 'POINTER' and isinstance(value, bpy.types.ID):
            result[name] = value_snapshot(value)
    return result


def buffer_digest(items, field, width, kind='f'):
    values = array(kind, [0]) * (len(items) * width)
    items.foreach_get(field, values)
    if kind == 'f' and not all(math.isfinite(v) for v in values):
        raise ValueError(f"non-finite mesh values in {field}")
    # Blender stores these buffers as 32-bit values; use a fixed byte order.
    if sys.byteorder != 'little':
        values.byteswap()
    return hashlib.sha256(values.tobytes()).hexdigest()


def digest_mesh(mesh):
    buffers = {
        "coordinates": buffer_digest(mesh.vertices, 'co', 3),
        "edges": buffer_digest(mesh.edges, 'vertices', 2, 'i'),
        "corners": buffer_digest(mesh.loops, 'vertex_index', 1, 'i'),
        "face_starts": buffer_digest(mesh.polygons, 'loop_start', 1, 'i'),
        "face_sizes": buffer_digest(mesh.polygons, 'loop_total', 1, 'i'),
        "material_indices": buffer_digest(mesh.polygons, 'material_index', 1, 'i'),
        "smooth_faces": buffer_digest(mesh.polygons, 'use_smooth', 1, 'b'),
    }
    return buffers

def node_tree_snapshot(tree, visited=()):
    if tree is None:
        return None
    if tree.name in visited:
        return {"recursive_reference": tree.name}
    nodes = []
    for node in sorted(tree.nodes, key=lambda x: x.name):
        item = {"name": node.name, "type": node.bl_idname,
                "settings": properties(node, {'location', 'width', 'height', 'label', 'select', 'color', 'use_custom_color', 'hide'}),
                "tags": tags(node)}
        for direction in ('inputs', 'outputs'):
            item[direction] = [{"id": socket.identifier, "name": socket.name,
                                "default": value_snapshot(socket.default_value)}
                               for socket in getattr(node, direction) if hasattr(socket, 'default_value')]
        if hasattr(node, 'color_ramp'):
            ramp = node.color_ramp
            item['color_ramp'] = {"settings": properties(ramp), "elements": [properties(e) for e in ramp.elements]}
        if hasattr(node, 'node_tree') and node.node_tree:
            item['group'] = node_tree_snapshot(node.node_tree, (*visited, tree.name))
        nodes.append(item)
    links = sorted([link.from_node.name, link.from_socket.identifier, link.to_node.name, link.to_socket.identifier, link.is_muted] for link in tree.links)
    return {"name": tree.name, "nodes": nodes, "links": links}


def layer_layout(layer):
    children = list(layer.children)
    order = sorted(range(len(children)), key=lambda index: children[index].name)
    return [(index, layer_layout(children[index])) for index in order]


def layer_snapshot(layer, layout):
    children = layer.children
    return {"name": layer.name, "exclude": layer.exclude, "hide_viewport": layer.hide_viewport,
            "holdout": layer.holdout, "indirect_only": layer.indirect_only,
            "children": [layer_snapshot(children[index], child_layout) for index, child_layout in layout]}


def view_layer_snapshots(scene):
    layout = layer_layout(scene.view_layers[0].layer_collection)
    return [{"name": layer.name, "collections": layer_snapshot(layer.layer_collection, layout),
             "hidden_objects": sorted(obj.name for obj in layer.objects if obj.hide_get(view_layer=layer))}
            for layer in scene.view_layers]


def inventory():
    objects = []
    for obj in sorted(bpy.data.objects, key=lambda x: x.name):
        item = {"name": obj.name, "type": obj.type,
                "matrix_world": value_snapshot(obj.matrix_world),
                "settings": properties(obj, {'active_material', 'active_material_index'}),
                "collections": sorted(c.name for c in obj.users_collection),
                "tags": tags(obj),
                "materials": [{"link": slot.link, "material": value_snapshot(slot.material)} for slot in obj.material_slots],
                "modifiers": [{"type": mod.type, "settings": properties(mod), "tags": tags(mod)} for mod in obj.modifiers],
                "constraints": [{"type": c.type, "settings": properties(c)} for c in obj.constraints]}
        objects.append(item)
    meshes = []
    attribute_fields = {'FLOAT': ('value', 1, 'f'), 'INT': ('value', 1, 'i'), 'BOOLEAN': ('value', 1, 'b'),
                        'FLOAT_VECTOR': ('vector', 3, 'f'), 'FLOAT2': ('vector', 2, 'f'),
                        'FLOAT_COLOR': ('color', 4, 'f'), 'BYTE_COLOR': ('color', 4, 'f')}
    for mesh in sorted(bpy.data.meshes, key=lambda x: x.name):
        attributes = []
        for attribute in sorted(mesh.attributes, key=lambda x: x.name):
            item = {"name": attribute.name, "domain": attribute.domain, "type": attribute.data_type}
            field = attribute_fields.get(attribute.data_type)
            if field:
                item['sha256'] = buffer_digest(attribute.data, *field)
            else:
                item['coverage'] = 'values not captured'
            attributes.append(item)
        meshes.append({"name": mesh.name, "vertices": len(mesh.vertices), "polygons": len(mesh.polygons),
                       "buffers": digest_mesh(mesh), "attributes": attributes, "tags": tags(mesh),
                       "materials": [value_snapshot(m) for m in mesh.materials]})
    materials = [{"name": m.name, "settings": properties(m), "tags": tags(m), "nodes": node_tree_snapshot(m.node_tree)}
                 for m in sorted(bpy.data.materials, key=lambda x: x.name)]
    collections = [{"name": c.name, "settings": properties(c), "tags": tags(c),
                    "objects": sorted(o.name for o in c.objects), "children": sorted(child.name for child in c.children)}
                   for c in sorted(bpy.data.collections, key=lambda x: x.name)]
    scenes = []
    for scene in sorted(bpy.data.scenes, key=lambda x: x.name):
        scenes.append({"name": scene.name, "camera": value_snapshot(scene.camera),
                       "world": value_snapshot(scene.world), "frame": scene.frame_current,
                       "units": properties(scene.unit_settings), "render": properties(scene.render),
                       "view_settings": properties(scene.view_settings), "display_settings": properties(scene.display_settings),
                       "view_layers": view_layer_snapshots(scene)})
    return {"schema_version": SCHEMA_VERSION, "blender_version": bpy.app.version_string,
            "blend": bpy.data.filepath, "objects": objects, "meshes": meshes, "materials": materials,
            "collections": collections, "scenes": scenes,
            "cameras": [{"name": c.name, "settings": properties(c)} for c in sorted(bpy.data.cameras, key=lambda x: x.name)],
            "lights": [{"name": light.name, "settings": properties(light), "nodes": node_tree_snapshot(light.node_tree)}
                       for light in sorted(bpy.data.lights, key=lambda x: x.name)],
            "worlds": [{"name": w.name, "settings": properties(w), "nodes": node_tree_snapshot(w.node_tree)}
                       for w in sorted(bpy.data.worlds, key=lambda x: x.name)],
            "images": [{"name": img.name, "settings": properties(img, {'pixels'}), "colorspace": properties(img.colorspace_settings)}
                       for img in sorted(bpy.data.images, key=lambda x: x.name) if img.type != 'RENDER_RESULT']}


def compare_inventory(old, report):
    if old.get('schema_version') != SCHEMA_VERSION or old.get('blender_version') != report['blender_version']:
        raise ValueError("comparison requires inventories from this helper schema and the same Blender version")
    comparison = {}
    for group in ('objects', 'meshes', 'materials', 'collections', 'scenes', 'cameras', 'lights', 'worlds', 'images'):
        before = {item['name']: item for item in old[group]}
        after = {item['name']: item for item in report[group]}
        comparison[group] = {"added": sorted(set(after) - set(before)), "removed": sorted(set(before) - set(after)),
                             "changed": [name for name in sorted(set(before) & set(after)) if before[name] != after[name]]}
    return comparison


def output_file(directory, filename):
    target = directory / filename
    if target.resolve().parent != directory:
        raise ValueError(f"output file resolves outside output directory: {target}")
    if target.exists() and (not target.is_file() or target.stat().st_nlink > 1):
        raise ValueError(f"output target is not a regular unlinked file: {target}")
    return target


def render_filename(name):
    label = re.sub(r'[^A-Za-z0-9_-]+', '-', name).strip('-')[:64] or 'camera'
    return f"{label}-{hashlib.sha256(name.encode()).hexdigest()[:16]}.png"

def main():
    if bpy is None:
        raise SystemExit("Run this script with Blender's Python")
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); p.add_argument('--camera', action='append', default=[]); p.add_argument('--view-layer'); p.add_argument('--compare')
    a = p.parse_args(argv)
    source = Path(bpy.data.filepath).resolve()
    if not bpy.data.filepath or not source.is_file():
        raise ValueError("open a saved .blend file before running this helper")
    output = Path(a.output).resolve()
    if output == source.parent or output == source:
        raise ValueError("use a review output directory different from the input file's directory")
    output.mkdir(parents=True, exist_ok=True)
    out = output_file(output, 'inventory.json')
    if a.compare and Path(a.compare).resolve() == out.resolve():
        raise ValueError("comparison inventory must be in a different output directory")
    scene = bpy.context.scene
    view_layer = scene.view_layers.get(a.view_layer) if a.view_layer else bpy.context.view_layer
    if view_layer is None:
        raise ValueError(f"missing view layer in active scene: {a.view_layer}")
    cameras = []
    for name in dict.fromkeys(a.camera):
        camera = bpy.context.scene.objects.get(name)
        if camera is None or camera.type != 'CAMERA':
            raise ValueError(f"missing camera in active scene: {name}")
        cameras.append((camera, output_file(output, render_filename(name))))
    report = inventory()
    if a.compare:
        with open(a.compare, encoding='utf-8') as f: old = json.load(f)
        report['compare'] = compare_inventory(old, report)
    report['renders'] = [{"camera": camera.name, "view_layer": view_layer.name, "file": str(path)} for camera, path in cameras]
    # Validate serialization before rendering or writing an inventory.
    serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    original = (scene.camera, scene.render.engine, scene.render.filepath, scene.render.image_settings.file_format,
                scene.render.use_file_extension, scene.render.use_compositing, scene.render.use_sequencer)
    layer_flags = [(layer, layer.use) for layer in scene.view_layers]
    try:
        for camera, path in cameras:
            scene.camera = camera
            scene.render.engine = 'BLENDER_WORKBENCH'
            scene.render.filepath = str(path)
            scene.render.image_settings.file_format = 'PNG'
            scene.render.use_file_extension = True
            # Compositor File Output nodes can write outside the review folder.
            scene.render.use_compositing = False
            scene.render.use_sequencer = False
            for layer, _ in layer_flags:
                layer.use = layer == view_layer
            bpy.ops.render.render(write_still=True, layer=view_layer.name)
            if not path.is_file():
                raise RuntimeError(f"render did not create expected PNG: {path}")
    finally:
        (scene.camera, scene.render.engine, scene.render.filepath, scene.render.image_settings.file_format,
         scene.render.use_file_extension, scene.render.use_compositing, scene.render.use_sequencer) = original
        for layer, enabled in layer_flags:
            layer.use = enabled
    out.write_text(serialized + '\n', encoding='utf-8')
    print(out)

if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if isinstance(exc, SystemExit) and exc.code in (None, 0):
            raise
        traceback.print_exc()
        # Blender otherwise exits successfully on Python errors unless callers
        # remember a separate --python-exit-code option.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
