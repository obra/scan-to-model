"""Read actual GLB vertices, object identities and embedded material images."""

import hashlib
import json
from collections import Counter
from pathlib import Path
import struct

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from delivery_contract import require


def check_glb(path, scene, job, appearance):
    payload = Path(path).read_bytes()
    require(len(payload) >= 28, "truncated GLB")
    magic, version, length = struct.unpack_from("<4sII", payload)
    require(magic == b"glTF" and version == 2 and length == len(payload), "invalid GLB header")
    size, kind = struct.unpack_from("<II", payload, 12)
    require(kind == 0x4E4F534A, "missing GLB JSON chunk")
    gltf = json.loads(payload[20:20+size])
    length, kind = struct.unpack_from("<II", payload, 20+size)
    require(kind == 0x004E4942, "missing GLB binary chunk")
    binary = payload[28+size:28+size+length]
    require(len(binary) == length and all("uri" not in buffer for buffer in gltf["buffers"]), "external or truncated buffer")
    expected = {row["id"]: row for row in scene["objects"]}
    records = {row["id"]: row for row in job["objects"]}

    def positions(index):
        accessor = gltf["accessors"][index]
        require(accessor["type"] == "VEC3" and accessor["componentType"] == 5126 and "sparse" not in accessor,
                "unsupported position encoding")
        view = gltf["bufferViews"][accessor["bufferView"]]
        return np.ndarray((accessor["count"], 3), dtype="<f4", buffer=binary,
                          offset=view.get("byteOffset", 0) + accessor.get("byteOffset", 0),
                          strides=(view.get("byteStride", 12), 4)).copy()

    def indices(primitive, count):
        require(primitive.get("mode", 4) == 4, "exported primitive is not triangles")
        if "indices" not in primitive:
            return np.arange(count).reshape(-1, 3)
        accessor = gltf["accessors"][primitive["indices"]]
        dtype = {5121: "u1", 5123: "<u2", 5125: "<u4"}.get(accessor["componentType"])
        require(dtype is not None and accessor["type"] == "SCALAR", "unsupported triangle indices")
        view = gltf["bufferViews"][accessor["bufferView"]]
        return np.frombuffer(binary, dtype=dtype, count=accessor["count"],
                             offset=view.get("byteOffset", 0) + accessor.get("byteOffset", 0)).reshape(-1, 3)

    def oriented_triangle(triangle):
        values = tuple(map(int, triangle))
        return min(values, values[1:] + values[:1], values[2:] + values[:2])

    found, object_materials = {}, {}

    def visit(index, parent):
        node = gltf["nodes"][index]
        matrix = np.eye(4)
        if "matrix" in node:
            matrix = np.asarray(node["matrix"]).reshape(4, 4).T
        else:
            matrix[:3, :3] = Rotation.from_quat(node.get("rotation", [0, 0, 0, 1])).as_matrix() @ np.diag(node.get("scale", [1, 1, 1]))
            matrix[:3, 3] = node.get("translation", [0, 0, 0])
        world = parent @ matrix
        if "mesh" in node:
            extras = node.get("extras", {})
            ident = extras.get("stm_id")
            require(ident in expected and ident not in found, "missing or duplicate GLB object identity")
            for key in ["room", "level", "role"]:
                require(extras.get("stm_" + key) == records[ident][key], "GLB object metadata differs")
            for key, value in expected[ident].get("properties", {}).items():
                require(extras.get(key) == value, f"GLB source property differs: {ident}.{key}")
            primitives = gltf["meshes"][node["mesh"]]["primitives"]
            object_materials[ident] = primitives
            native = np.asarray(expected[ident]["vertices"])[:, [0, 2, 1]] * [1, 1, -1]
            tree = cKDTree(native)
            native_labels = tree.query(native)[1]
            actual_triangles = Counter()
            arrays = []
            for primitive in primitives:
                points = positions(primitive["attributes"]["POSITION"])
                points = points @ world[:3, :3].T + world[:3, 3]
                arrays.append(points)
                labels = tree.query(points)[1]
                actual_triangles.update(oriented_triangle(row) for row in labels[indices(primitive, len(points))])
            expected_triangles = Counter(oriented_triangle(native_labels[row["vertices"]]) for row in expected[ident]["triangles"])
            require(actual_triangles == expected_triangles, f"GLB triangles or winding differ: {ident}")
            points = np.vstack(arrays)
            error = max(float(cKDTree(points).query(native)[0].max()), float(cKDTree(native).query(points)[0].max()))
            require(error < 2e-5, f"GLB geometry differs: {ident}, {error} metres")
            found[ident] = error
        for child in node.get("children", []):
            visit(child, world)

    for node in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        visit(node, np.eye(4))
    require(found.keys() == expected.keys(), "GLB does not contain the complete declared model")
    images = []
    for image in gltf.get("images", []):
        require("bufferView" in image and "uri" not in image, "GLB image requires an external request")
        view = gltf["bufferViews"][image["bufferView"]]
        data = binary[view.get("byteOffset", 0):view.get("byteOffset", 0)+view["byteLength"]]
        images.append(hashlib.sha256(data).hexdigest())
    if appearance["atlas"]:
        expected_sha = appearance["atlas"]["sha256"]
        for ident, primitives in object_materials.items():
            assigned = appearance["materials"].get(records[ident].get("material"), {})
            if assigned.get("method") not in {"photo-projection", "repeated-photo"}:
                continue
            for primitive in primitives:
                material = gltf["materials"][primitive["material"]] if "material" in primitive else {}
                texture = material.get("pbrMetallicRoughness", {}).get("baseColorTexture")
                require(texture is not None and images[gltf["textures"][texture["index"]]["source"]] == expected_sha,
                        f"atlas is not bound to an exported photo surface: {ident}")
                require("TEXCOORD_" + str(texture.get("texCoord", 0)) in primitive["attributes"],
                        f"exported photo surface has no texture coordinates: {ident}")
    return {"passed": True, "model_sha256": hashlib.sha256(payload).hexdigest(), "object_count": len(found),
            "max_vertex_error_m": max(found.values()), "embedded_image_hashes": images,
            "external_resources": False, "scope": "Export fidelity; not survey accuracy"}
