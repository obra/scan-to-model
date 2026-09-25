"""Inspect, texture, render and export a declared Blender delivery candidate."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delivery_contract import digest, require, write_json


DRAWABLE = {"MESH", "CURVE", "SURFACE", "FONT", "META"}


def property_value(value):
    if isinstance(value, dict):
        return {key: property_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [property_value(item) for item in value]
    if hasattr(value, "to_dict"):
        return {key: property_value(item) for key, item in value.to_dict().items()}
    if hasattr(value, "to_list"):
        return value.to_list()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def native_state():
    result = {}
    for obj in bpy.data.objects:
        row = {"type": obj.type, "matrix": [list(row) for row in obj.matrix_world],
               "parent": obj.parent.name if obj.parent else None,
               "properties": {key: property_value(value) for key, value in obj.items()},
               "color": list(obj.color)}
        if obj.type == "MESH":
            row["vertices"] = [list(vertex.co) for vertex in obj.data.vertices]
            row["faces"] = [list(face.vertices) for face in obj.data.polygons]
        result[obj.name] = row
    return result


def verify_state(before):
    current = native_state()
    for name, expected in before.items():
        require(name in current, f"native object was lost: {name}")
        actual = current[name]
        for key, value in expected.items():
            if key == "properties":
                require(all(actual[key].get(prop) == content for prop, content in value.items()),
                        f"source properties changed: {name}")
            else:
                require(actual[key] == value, f"native {key} changed: {name}")


def context(job):
    scene = bpy.data.scenes[job["scene"]] if job.get("scene") else bpy.context.scene
    if bpy.context.window:
        bpy.context.window.scene = scene
        if job.get("view_layer"):
            bpy.context.window.view_layer = scene.view_layers[job["view_layer"]]
    layer = bpy.context.view_layer
    expected = {row["name"] for row in job["objects"]}
    excluded = {row["name"] for row in job.get("excluded_objects", [])}
    actual = {obj.name for obj in scene.objects if obj.type in DRAWABLE}
    require(actual == expected | excluded, f"drawable scope differs: missing {sorted((expected|excluded)-actual)}, undeclared {sorted(actual-expected-excluded)}")
    require(not any(obj.instance_type != "NONE" for obj in scene.objects), "realize instances before delivery")
    layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    members = {obj.original.name for obj in graph.objects}
    require(expected <= members, "declared objects are excluded from the chosen evaluated view layer")
    for name in expected:
        obj = scene.objects[name]
        require(not obj.hide_render, f"declared object is hidden for rendering: {name}")
        parent = next((collection for collection in obj.users_collection if not collection.hide_render), None)
        require(parent is not None, f"declared object has no renderable collection: {name}")
    return scene, layer, graph


def inspect(job):
    scene, layer, graph = context(job)
    objects = []
    for record in job["objects"]:
        obj = scene.objects[record["name"]]
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            require(mesh is not None and len(mesh.vertices), f"empty drawable object: {obj.name}")
            mesh.calc_loop_triangles()
            objects.append({"id": record["id"], "name": obj.name, "type": obj.type,
                            "vertices": [list(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices],
                            "faces": [list(face.vertices) for face in mesh.polygons],
                            "triangles": [{"face": tri.polygon_index, "vertices": list(tri.vertices)} for tri in mesh.loop_triangles],
                            "modifiers": [modifier.type for modifier in obj.modifiers],
                            "properties": {key: property_value(value) for key, value in obj.items() if not key.startswith("_")}})
        finally:
            evaluated.to_mesh_clear()
    views = []
    for record in job.get("views", []):
        camera = scene.objects.get(record["camera"])
        require(camera is not None and camera.type == "CAMERA", f"camera not found: {record['camera']}")
        require(camera.data.type == "PERSP", "browser delivery currently requires perspective cameras")
        location = camera.matrix_world.translation
        forward = camera.matrix_world.to_quaternion() @ Vector([0, 0, -1])
        views.append({**record, "position": list(location), "target": list(location + forward*3),
                      "fov": math.degrees(camera.data.angle_y), "matrix": [list(row) for row in camera.matrix_world]})
    return {"objects": objects, "views": views, "scene": scene.name, "view_layer": layer.name}


def source_images():
    result = {}
    for image in bpy.data.images:
        if image.type in {"RENDER_RESULT", "COMPOSITING"}:
            continue
        if not image.packed_file:
            image.pack()
        require(image.packed_file is not None, f"image could not be packed: {image.name}")
        image.use_fake_user = True
        result[image.name] = hashlib.sha256(bytes(image.packed_file.data)).hexdigest()
    return result


def load_image(path, name):
    image = bpy.data.images.get(name)
    if image is not None:
        require(image.packed_file is not None and hashlib.sha256(bytes(image.packed_file.data)).hexdigest() == digest(path),
                f"image identity collision: {name}")
        return image
    image = bpy.data.images.load(str(Path(path).resolve()), check_existing=False)
    image.name = name
    image.pack()
    image.use_fake_user = True
    return image


def linear_color(color):
    rgb = np.asarray(color, dtype=float) / 255
    return (*np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055)/1.055)**2.4), 1)


def apply(job, appearance, output):
    context(job)
    before = native_state()
    original_images = source_images()
    image = load_image(appearance["atlas"]["path"], "STM atlas " + appearance["atlas"]["sha256"][:16]) if appearance["atlas"] else None
    materials = {}
    for ident, record in appearance["materials"].items():
        material = bpy.data.materials.new("STM " + ident)
        material.use_nodes = True
        material["appearance_method"] = record["method"]
        material["appearance_basis"] = record["basis"]
        material["source_ids"] = json.dumps(record.get("sources", []))
        material["appearance_status"] = "tentative" if record["method"] != "matched-color" else "source-guided"
        material.diffuse_color = linear_color(record["color"])
        shader = material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = material.diffuse_color
        for key, socket, default in [("roughness", "Roughness", .6), ("metallic", "Metallic", 0), ("transmission", "Transmission Weight", 0)]:
            shader.inputs[socket].default_value = record.get(key, default)
        if record["method"] in {"photo-projection", "repeated-photo"}:
            require(image is not None, "photo material has no atlas")
            texture = material.node_tree.nodes.new("ShaderNodeTexImage")
            texture.image = image
            texture.interpolation = "Linear"
            uv = material.node_tree.nodes.new("ShaderNodeUVMap")
            uv.uv_map = "STM photo UV"
            material.node_tree.links.new(uv.outputs["UV"], texture.inputs["Vector"])
            material.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
        materials[ident] = material
    faces = {(row["object"], row["face"]): row for row in appearance["faces"]}
    assignments = []
    for record in job["objects"]:
        obj = bpy.data.objects[record["name"]]
        for key, value in {"stm_id": record["id"], "stm_room": record["room"], "stm_level": record["level"],
                           "stm_role": record["role"], "stm_geometry_status": job["intent"]["geometry_status"]}.items():
            require(key not in obj or obj[key] == value, f"identity property differs: {obj.name}.{key}")
            obj[key] = value
        ident = record.get("material")
        if ident is None:
            continue
        require(obj.type == "MESH", "appearance assignments currently require mesh objects")
        obj.data = obj.data.copy()
        obj.data.materials.append(materials[ident])
        index = len(obj.data.materials) - 1
        uv_layer = obj.data.uv_layers.get("STM photo UV") or obj.data.uv_layers.new(name="STM photo UV")
        obj.data.uv_layers.active = uv_layer
        uv_layer.active_render = True
        for polygon in obj.data.polygons:
            polygon.material_index = index
            face = faces.get((record["id"], polygon.index))
            if face:
                require(len(face["uv"]) == len(polygon.loop_indices), "UV topology differs from source geometry")
                for loop, uv in zip(polygon.loop_indices, face["uv"]):
                    uv_layer.data[loop].uv = uv
        assignments.append({"object": record["id"], "name": obj.name, "material": materials[ident].name,
                            "method": appearance["materials"][ident]["method"]})
    used = {source for row in job["objects"] for source in row.get("sources", [])}
    used.update(source for row in job.get("materials", []) for source in row.get("sources", []))
    for source in job.get("sources", []):
        if source["id"] in used:
            load_image(source["image"], "STM source " + source["id"])
    scene = bpy.context.scene
    for fill in appearance.get("lights", []):
        name = "STM fill " + fill["id"]
        require(name not in bpy.data.objects, f"presentation light already exists: {name}")
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.color, data.size = fill["energy"], fill["color"], fill["size"]
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = fill["position"]
        light["appearance_status"] = "inferred presentation light"
    world = job.get("lighting", {}).get("world")
    if world:
        scene.world = bpy.data.worlds.new("STM presentation world")
        scene.world.use_nodes = True
        background = scene.world.node_tree.nodes["Background"]
        background.inputs["Color"].default_value = (*world["color"], 1)
        background.inputs["Strength"].default_value = world["strength"]
    for name, value in [("STM delivery.json", job), ("STM appearance.json", appearance)]:
        text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        text.clear()
        text.write(json.dumps(value, indent=2))
    verify_state(before)
    images = source_images()
    require(all(images.get(name) == sha for name, sha in original_images.items()), "original packed image changed")
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "candidate.blend"), compress=True, check_existing=False)
    write_json(output / "native.json", {"model_sha256": digest(output / "candidate.blend"), "original_state": before,
                                       "images": images, "assignments": assignments, "original_images": original_images})


def readback(job, appearance, native):
    verify_state(native["original_state"])
    require(source_images() == native["images"], "saved packed image bytes differ")
    objects = {row["id"]: bpy.data.objects[row["name"]] for row in job["objects"]}
    for row in native["assignments"]:
        obj = objects[row["object"]]
        for polygon in obj.data.polygons:
            require(obj.data.materials[polygon.material_index].name == row["material"], "saved material assignment differs")
        material = bpy.data.materials[row["material"]]
        if row["method"] in {"photo-projection", "repeated-photo"}:
            shader = material.node_tree.nodes.get("Principled BSDF")
            links = list(shader.inputs["Base Color"].links)
            require(len(links) == 1 and links[0].from_node.type == "TEX_IMAGE", "atlas is not connected to active base color")
            require(hashlib.sha256(bytes(links[0].from_node.image.packed_file.data)).hexdigest() == appearance["atlas"]["sha256"],
                    "wrong image bound to active material")
    for row in appearance["faces"]:
        obj = objects[row["object"]]
        polygon = obj.data.polygons[row["face"]]
        actual = [list(obj.data.uv_layers["STM photo UV"].data[index].uv) for index in polygon.loop_indices]
        require(np.allclose(actual, row["uv"], atol=1e-6), "saved face UV differs")
    return {"passed": True, "model_sha256": digest(bpy.data.filepath), "objects": len(objects),
            "packed_images": len(native["images"]), "geometry_and_source_properties_preserved": True,
            "materials_images_and_uv_verified": True}


def render(job, output, preview):
    scene, layer, _ = context(job)
    for other in scene.view_layers:
        other.use = other == layer
    for record in job.get("excluded_objects", []):
        scene.objects[record["name"]].hide_render = True
    layer.use_pass_object_index = layer.use_pass_material_index = True
    object_ids = {}
    for index, record in enumerate(job["objects"], 1):
        scene.objects[record["name"]].pass_index = index
        object_ids[str(index)] = record["id"]
    material_ids = {}
    for index, material in enumerate(bpy.data.materials, 1):
        material.pass_index = index
        material_ids[str(index)] = material.name
    settings = job.get("renderer", {})
    scene.render.engine = "CYCLES"
    scene.cycles.samples = min(4, settings.get("samples", 32)) if preview else settings.get("samples", 32)
    scene.cycles.use_denoising = settings.get("denoise", True)
    width, height = settings.get("width", 1024), settings.get("height", 768)
    scale = min(1, 320/max(width, height)) if preview else 1
    scene.render.resolution_x, scene.render.resolution_y = round(width*scale), round(height*scale)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.use_nodes = True
    scene.node_tree.nodes.clear()
    layers = scene.node_tree.nodes.new("CompositorNodeRLayers")
    layers.layer = layer.name
    composite = scene.node_tree.nodes.new("CompositorNodeComposite")
    scene.node_tree.links.new(layers.outputs["Image"], composite.inputs["Image"])
    passes = scene.node_tree.nodes.new("CompositorNodeOutputFile")
    passes.format.file_format, passes.format.color_depth = "OPEN_EXR", "32"
    passes.file_slots.clear()
    for name, socket in [("object", "IndexOB"), ("material", "IndexMA")]:
        passes.file_slots.new(name)
        scene.node_tree.links.new(layers.outputs[socket], passes.inputs[name])
    rows = []
    for view in job.get("views", []):
        folder = output / view["id"]
        folder.mkdir()
        scene.camera = scene.objects[view["camera"]]
        passes.base_path = str(folder)
        scene.render.filepath = str(folder / "view.png")
        scene.frame_set(1)
        bpy.ops.render.render(write_still=True)
        raster = {}
        for kind in ["object", "material"]:
            file = folder / (kind + "0001.exr")
            image = bpy.data.images.load(str(file), check_existing=False)
            pixels = np.empty(len(image.pixels), dtype=np.float32)
            image.pixels.foreach_get(pixels)
            channels = pixels.reshape(image.size[1], image.size[0], 4)[::-1, :, :3]
            ids = np.rint(channels[:, :, 0]).astype(np.int32)
            require(np.allclose(channels, ids[:, :, None], atol=1e-5), "nonintegral raster IDs")
            raster[kind] = ids
            bpy.data.images.remove(image)
            file.unlink()
        np.savez_compressed(folder / "raster.npz", **raster)
        record = {"id": view["id"], "camera": view["camera"], "camera_matrix": [list(row) for row in scene.camera.matrix_world],
                  "model_sha256": digest(bpy.data.filepath), "resolution": [scene.render.resolution_x, scene.render.resolution_y],
                  "object_ids": object_ids, "material_ids": material_ids,
                  "image_sha256": digest(folder / "view.png"), "raster_sha256": digest(folder / "raster.npz")}
        write_json(folder / "render.json", record)
        rows.append(record)
    write_json(output / "renders.json", rows)


def web_vector(value):
    return [float(value[0]), float(value[2]), float(-value[1])]


def export(job, output):
    scene, _, _ = context(job)
    bpy.ops.object.select_all(action="DESELECT")
    for row in job["objects"]:
        obj = scene.objects[row["name"]]
        obj.hide_set(False)
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(output / "model.glb"), export_format="GLB", use_selection=True,
                             export_extras=True, export_animations=False, export_cameras=False,
                             export_lights=False, export_apply=True)
    snapshot = inspect(job)
    vertices = np.asarray([point for row in snapshot["objects"] for point in row["vertices"]])
    low, high = vertices.min(0), vertices.max(0)
    center, extent = (low+high)/2, max(float(np.linalg.norm(high-low)), 1)
    views = [{"id": "exterior", "title": "Whole model", "position": web_vector(center + [extent, -extent, extent*.7]),
              "target": web_vector(center), "fov": 50}]
    views.extend({"id": row["id"], "title": row.get("title", row["id"]), "position": web_vector(row["position"]),
                  "target": web_vector(row["target"]), "fov": row["fov"]} for row in snapshot["views"])
    levels = sorted({row["level"] for row in job["objects"] if row["role"] not in {"roof", "ceiling"}})
    write_json(output / "model.json", {"title": job["title"], "viewpoints": views, "levels": levels,
                                      "object_count": len(job["objects"]), "extent": extent,
                                      "geometry_status": job["intent"]["geometry_status"],
                                      "metric_status": job["intent"]["metric_status"],
                                      "objects": [{key: row[key] for key in ["id", "level", "role"]} for row in job["objects"]],
                                      "lights": [{"position": web_vector(obj.location)} for obj in scene.objects
                                                 if obj.type == "LIGHT" and obj.get("appearance_status") == "inferred presentation light"],
                                      "appearance_methods": sorted({row["method"] for row in job.get("materials", [])})})


def probe(job, output):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = job.get("renderer", {}).get("denoise", True)
    scene.render.resolution_x = scene.render.resolution_y = 8
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output / "probe.png")
    bpy.ops.render.render(write_still=True)
    write_json(output / "capabilities.json", {"blender_version": bpy.app.version_string, "engine": "CYCLES",
                                              "denoise": scene.cycles.use_denoising, "render_succeeded": True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["inspect", "probe", "apply", "readback", "preview", "render", "export"], required=True)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--appearance", type=Path)
    parser.add_argument("--native", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.output.mkdir(parents=True, exist_ok=False)
    job = json.loads(args.job.read_text())
    appearance = json.loads(args.appearance.read_text()) if args.appearance else None
    if args.phase == "inspect":
        write_json(args.output / "scene.json", inspect(job))
    elif args.phase == "probe":
        probe(job, args.output)
    elif args.phase == "apply":
        apply(job, appearance, args.output)
    elif args.phase == "readback":
        write_json(args.output / "checks.json", readback(job, appearance, json.loads(args.native.read_text())))
    elif args.phase in {"preview", "render"}:
        render(job, args.output, args.phase == "preview")
    elif args.phase == "export":
        export(job, args.output)


if __name__ == "__main__":
    main()
