"""Create a public, synthetic two-room delivery fixture inside Blender."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

import bpy
from mathutils import Vector
import numpy as np


def png(path, pixels):
    pixels = np.asarray(pixels, dtype=np.uint8)
    height, width, _ = pixels.shape
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))
    data = b"".join(b"\0" + row.tobytes() for row in pixels)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(data)) + chunk(b"IEND", b""))


def gray_png(path, pixels, bits=8):
    height, width = pixels.shape
    pixels = pixels.astype(">u2" if bits == 16 else "u1")
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bits, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(b"\0" + row.tobytes() for row in pixels))) + chunk(b"IEND", b""))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=["clean", "overlap", "blocked"], default="clean")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    objects = []

    def face(ident, points, room, role, material):
        mesh = bpy.data.meshes.new(ident)
        mesh.from_pydata(points, [], [list(range(len(points)))])
        mesh.update()
        obj = bpy.data.objects.new(ident, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj["source_ids"] = ["synthetic-photo"]
        obj["status"] = "tentative"
        obj["evidence_class"] = "inferred"
        objects.append({"id": ident, "name": ident, "room": room, "level": "ground", "role": role,
                        "sources": ["synthetic-photo"], "material": material})
        return obj

    face("floor-a", [[0, 0, 0], [3, 0, 0], [3, 4, 0], [0, 4, 0]], "studio", "floor", "grain")
    face("floor-b", [[3, 0, 0], [6, 0, 0], [6, 4, 0], [3, 4, 0]], "washroom", "floor", "paint")
    face("ceiling-a", [[0, 0, 2.5], [0, 4, 2.5], [3, 4, 3.2], [3, 0, 3.2]], "studio", "ceiling", "paint")
    face("ceiling-b", [[3, 0, 3.2], [3, 4, 3.2], [6, 4, 3.2], [6, 0, 3.2]], "washroom", "ceiling", "paint")
    face("back-a", [[0, 4, 0], [3, 4, 0], [3, 4, 3.2], [0, 4, 2.5]], "studio", "wall", "paint")
    face("back-b", [[3, 4, 0], [6, 4, 0], [6, 4, 3.2], [3, 4, 3.2]], "washroom", "wall", "paint")
    face("front-a", [[0, 0, 0], [0, 0, 2.5], [3, 0, 3.2], [3, 0, 0]], "studio", "wall", "paint")
    face("front-b", [[3, 0, 0], [3, 0, 3.2], [6, 0, 3.2], [6, 0, 0]], "washroom", "wall", "paint")
    face("left", [[0, 0, 0], [0, 4, 0], [0, 4, 2.5], [0, 0, 2.5]], "studio", "wall", "paint")
    face("right", [[6, 0, 0], [6, 0, 3.2], [6, 4, 3.2], [6, 4, 0]], "washroom", "wall", "paint")
    for ident, y0, y1, z0, z1 in [("partition-front", 0, 1.3, 0, 3.2), ("partition-back", 2.5, 4, 0, 3.2),
                                 ("partition-header", 1.3, 2.5, 2.2, 3.2)]:
        face(ident, [[3, y0, z0], [3, y1, z0], [3, y1, z1], [3, y0, z1]], "studio", "wall", "paint")
    door = [[3.04, 1.3, .03], [3.04, 2.5, .03], [3.04, 2.5, 2.2], [3.04, 1.3, 2.2]] if args.case == "blocked" else [
        [3.04, 2.55, .03], [4.24, 2.55, .03], [4.24, 2.55, 2.2], [3.04, 2.55, 2.2]]
    face("door", door, "washroom", "door", "paint")
    face("poster", [[.5, 3.98, .8], [2.5, 3.98, .8], [2.5, 3.98, 1.8], [.5, 3.98, 1.8]], "studio", "finish", "projection")
    face("mirror", [[4.2, 3.98, 1], [5.8, 3.98, 1], [5.8, 3.98, 2.3], [4.2, 3.98, 2.3]], "washroom", "mirror", "mirror")
    face("glass", [[4.5, 3.1, .4], [5.5, 3.1, .4], [5.5, 3.1, 1.2], [4.5, 3.1, 1.2]], "washroom", "glazing", "glass")
    if args.case == "overlap":
        face("duplicate-poster", [[.7, 3.98, .9], [2.2, 3.98, .9], [2.2, 3.98, 1.7], [.7, 3.98, 1.7]], "studio", "trim", "paint")

    def camera(name, position, target):
        obj = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        bpy.context.scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z", "Y").to_euler()
        obj.data.lens = 24
        obj.data.clip_start = .02
        return obj

    first = camera("Studio camera", [1.5, .5, 1.45], [1.5, 3.6, 1.3])
    camera("Washroom camera", [5, .5, 1.5], [5, 3.9, 1.5])
    camera("Doorway camera", [2.8, 1.9, 1.2], [5, 1.9, 1.2])
    bpy.context.scene.camera = first
    yy, xx = np.indices((128, 192))
    rgb = np.stack([90 + 50*((xx//12+yy//12) % 2), 130 + xx//4, 80 + yy//4], axis=-1)
    png(root / "photo.png", rgb)
    grain = np.stack([145 + 25*np.sin(xx/3), 95 + 15*np.sin(xx/3), 45 + 8*np.sin(xx/3)], axis=-1)
    png(root / "grain.png", grain)
    png(root / "unused.png", np.full((8, 8, 3), 33))
    gray_png(root / "depth.png", np.full((128, 192), 1980), 16)
    gray_png(root / "confidence.png", np.full((128, 192), 255))
    mask = np.full((128, 192), 255)
    mask[:, 80:90] = 0
    gray_png(root / "mask.png", mask)
    original = bpy.data.images.load(str(root / "photo.png"))
    original.name = "Original synthetic evidence"
    original.pack()
    original.use_fake_user = True
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "input.blend"), compress=True, check_existing=False)
    source = {"id": "synthetic-photo", "image": "photo.png", "depth": "depth.png", "confidence": "confidence.png", "mask": "mask.png",
              "camera": {"width": 192, "height": 128, "fx": 96, "fy": 96, "cx": 96, "cy": 64},
              "camera_to_world": [[1, 0, 0, 1.5], [0, 0, -1, 2], [0, 1, 0, 1.3], [0, 0, 0, 1]]}
    for key in ["image", "depth", "confidence", "mask"]:
        source[key+"_sha256"] = sha(root / source[key])
    sources = [source, {"id": "grain", "image": "grain.png", "image_sha256": sha(root / "grain.png")},
               {"id": "unused", "image": "unused.png", "image_sha256": sha(root / "unused.png")}]
    materials = [
        {"id": "paint", "method": "matched-color", "sources": ["synthetic-photo"], "color": [216, 215, 205], "basis": "Synthetic pale finish"},
        {"id": "grain", "method": "repeated-photo", "sources": ["grain"], "color": [150, 100, 55], "basis": "Synthetic sample; placement inferred",
         "sample": {"source": "grain", "quad": [[0, 0], [191, 0], [191, 127], [0, 127]]},
         "mapping": {"origin": [0, 0, 0], "u": [1, 0, 0], "v": [0, 1, 0], "size_m": [1, 1]}, "detail_contrast": .25},
        {"id": "projection", "method": "photo-projection", "sources": ["synthetic-photo"], "color": [160, 160, 140], "basis": "Synthetic calibrated opaque target"},
        {"id": "mirror", "method": "inferred", "color": [240, 240, 240], "metallic": 1, "roughness": .02, "basis": "Synthetic mirror, no projection of reflected scenery"},
        {"id": "glass", "method": "inferred", "color": [240, 250, 250], "transmission": 1, "roughness": .05, "basis": "Synthetic clear screen"}]
    views = [{"id": "studio", "title": "Studio", "camera": "Studio camera", "required_objects": ["floor-a", "poster"]},
             {"id": "washroom", "title": "Washroom", "camera": "Washroom camera", "required_objects": ["floor-b", "mirror"]}]
    if args.case == "blocked":
        views.append({"id": "doorway", "camera": "Doorway camera", "required_objects": ["floor-b"]})
    job = {"schema_version": 1, "title": "Synthetic two-room house", "model": "input.blend", "model_sha256": sha(root / "input.blend"),
           "deliverables": ["native", "glb", "stills", "viewer", "sources"],
           "intent": {"basis": "Exercise rendered delivery using invented, public test data", "interpolation_authorized": True,
                      "geometry_status": "tentative", "metric_status": "Synthetic fixture, not a surveyed house"},
           "objects": objects, "materials": materials, "sources": sources, "views": views,
           "renderer": {"width": 320, "height": 240, "samples": 12, "denoise": True},
           "texture": {"density": 64, "minimum_density": 16, "max_size": 512},
           "lighting": {"world": {"color": [.7, .8, 1], "strength": .5}, "fills": [
               {"id": "studio", "xy": [1.5, 2], "floor_z": 0, "ceiling_objects": ["ceiling-a"], "size": 1, "energy": 180, "color": [1, .94, .85]},
               {"id": "washroom", "xy": [4.8, 1.8], "floor_z": 0, "ceiling_objects": ["ceiling-b"], "size": 1, "energy": 180, "color": [1, .94, .85]}]}}
    (root / "job.json").write_text(json.dumps(job, indent=2) + "\n")


if __name__ == "__main__":
    main()
