"""Read an explicitly declared Blender membership without saving or rendering."""

import hashlib
import json
import math
import os
from pathlib import Path


CONVERTIBLE_TYPES = {"MESH", "CURVE", "SURFACE", "FONT", "META"}
REQUIRED_MEMBERSHIP_KEYS = {"room_id", "model_sha256", "groups", "counts"}


def sha256(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def validate_membership(path):
    path = Path(path)
    membership = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(membership, dict) or set(membership) != REQUIRED_MEMBERSHIP_KEYS:
        raise ValueError("membership must contain exactly room_id, model_sha256, groups, and counts")
    if not isinstance(membership["room_id"], str) or not membership["room_id"]:
        raise ValueError("membership room_id must be a nonempty string")
    model_sha = membership["model_sha256"]
    if not isinstance(model_sha, str) or len(model_sha) != 64:
        raise ValueError("membership model_sha256 must be a SHA-256 hex string")
    try:
        int(model_sha, 16)
    except ValueError as error:
        raise ValueError("membership model_sha256 must be a SHA-256 hex string") from error
    groups = membership["groups"]
    if not isinstance(groups, dict) or not groups:
        raise ValueError("membership groups must be a nonempty object")
    targets = []
    group_by_name = {}
    for group_name, group in groups.items():
        if not isinstance(group_name, str) or not group or not isinstance(group, dict) or set(group) != {"target_names"}:
            raise ValueError("each membership group must contain only target_names")
        names = group["target_names"]
        if not isinstance(names, list) or not names or not all(isinstance(name, str) and name for name in names):
            raise ValueError("group target_names must be a nonempty list of names")
        for name in names:
            if name in group_by_name:
                raise ValueError(f"duplicate membership target name: {name}")
            group_by_name[name] = group_name
            targets.append(name)
    counts = membership["counts"]
    if not isinstance(counts, dict) or set(counts) != {"total_native_targets"}:
        raise ValueError("membership counts must contain only total_native_targets")
    total = counts["total_native_targets"]
    if isinstance(total, bool) or not isinstance(total, int) or total != len(targets):
        raise ValueError("membership total_native_targets does not match unique target names")
    return membership, targets, group_by_name


def validate_model_hash(path, expected):
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"model SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def _scalar(value, bpy):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numeric property")
        return value
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace")
    if isinstance(value, bpy.types.ID):
        return {"name": value.name, "library": value.library.filepath if value.library else None}
    if isinstance(value, dict):
        return {str(key): _scalar(item, bpy) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_scalar(item, bpy) for item in value]
    try:
        return [_scalar(item, bpy) for item in value]
    except TypeError:
        return str(value)


def _properties(owner, bpy):
    try:
        return {str(key): _scalar(value, bpy) for key, value in owner.items()}
    except (AttributeError, TypeError):
        return {}


def _matrix(value):
    return [[float(value[row][column]) for column in range(4)] for row in range(4)]


def _vector(value):
    return [float(component) for component in value]


def _rna_settings(owner, bpy):
    result = {}
    if owner is None or not hasattr(owner, "bl_rna"):
        return result
    for prop in owner.bl_rna.properties:
        if prop.identifier == "rna_type" or prop.is_readonly:
            continue
        try:
            result[prop.identifier] = _scalar(getattr(owner, prop.identifier), bpy)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            continue
    return result


def _curve_controls(data):
    if data is None:
        return None
    result = {"dimensions": str(data.dimensions), "resolution_u": int(data.resolution_u),
              "resolution_v": int(data.resolution_v), "bevel_depth": float(data.bevel_depth),
              "bevel_resolution": int(data.bevel_resolution), "splines": []}
    for spline in data.splines:
        item = {"type": str(spline.type), "use_cyclic_u": bool(spline.use_cyclic_u),
                "resolution_u": int(spline.resolution_u), "points": [], "bezier_points": []}
        for point in spline.points:
            item["points"].append({"co": _vector(point.co), "radius": float(point.radius),
                                    "tilt": float(point.tilt), "weight": float(point.weight)})
        for point in spline.bezier_points:
            item["bezier_points"].append({"co": _vector(point.co),
                                           "handle_left": _vector(point.handle_left),
                                           "handle_right": _vector(point.handle_right),
                                           "handle_left_type": str(point.handle_left_type),
                                           "handle_right_type": str(point.handle_right_type),
                                           "radius": float(point.radius), "tilt": float(point.tilt)})
        result["splines"].append(item)
    return result


def _parent_chain(obj):
    result = []
    parent = obj.parent
    while parent:
        result.append(parent.name)
        parent = parent.parent
    return result


def _object_row(obj, evaluated, depsgraph, deps_names, group, bpy, original_visibility):
    mesh = evaluated.to_mesh()
    try:
        local = [_vector(vertex.co) for vertex in mesh.vertices]
        world = [_vector(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices]
        polygons = [[int(index) for index in polygon.vertices] for polygon in mesh.polygons]
        mesh.calc_loop_triangles()
        triangles = [{"vertex_indices": [int(index) for index in triangle.vertices],
                      "polygon_index": int(triangle.polygon_index)}
                     for triangle in mesh.loop_triangles]
        normal_matrix = evaluated.matrix_world.to_3x3().inverted().transposed()
        normals = []
        for polygon in mesh.polygons:
            normal = normal_matrix @ polygon.normal
            normal.normalize()
            normals.append(_vector(normal))
        bounds = None
        if world:
            bounds = {"min_world_m": [min(point[index] for point in world) for index in range(3)],
                      "max_world_m": [max(point[index] for point in world) for index in range(3)]}
        return {
            "name": obj.name, "scope_group": group, "source_kind": obj.type,
            "data_name": obj.data.name if getattr(obj, "data", None) else None,
            "curve_source_geometry": _curve_controls(obj.data) if obj.type == "CURVE" else None,
            "collections": sorted(collection.name for collection in obj.users_collection),
            "parent_chain": _parent_chain(obj), "parent_type": str(obj.parent_type),
            "parent_inverse_matrix": _matrix(obj.matrix_parent_inverse),
            "matrix_world_original": _matrix(obj.matrix_world),
            "matrix_world_evaluated": _matrix(evaluated.matrix_world),
            "vertices_local_m": local, "vertices_world_m": world, "bounds_world_m": bounds,
            "polygons": polygons, "polygon_normals_world": normals, "loop_triangles": triangles,
            "custom_properties": _properties(obj, bpy),
            "data_custom_properties": _properties(obj.data, bpy) if getattr(obj, "data", None) else {},
            "materials": [{"slot": index, "name": slot.material.name if slot.material else None,
                           "library": slot.material.library.filepath if slot.material and slot.material.library else None}
                          for index, slot in enumerate(obj.material_slots)],
            "modifiers": [{"name": modifier.name, "type": modifier.type,
                           "settings": _rna_settings(modifier, bpy),
                           "custom_properties": _properties(modifier, bpy)} for modifier in obj.modifiers],
            "constraints": [{"name": constraint.name, "type": constraint.type,
                             "settings": _rna_settings(constraint, bpy),
                             "custom_properties": _properties(constraint, bpy)} for constraint in obj.constraints],
            "visibility": {**original_visibility, "hide_get_temporary_layer": bool(obj.hide_get())},
            "animation_data_present": obj.animation_data is not None,
            "shape_keys_present": bool(getattr(obj.data, "shape_keys", None)) if getattr(obj, "data", None) else False,
            "guard": {"present_in_depsgraph": evaluated.name in deps_names,
                       "is_evaluated": evaluated.is_evaluated,
                       "original_identity_matches": evaluated.original is obj,
                       "depsgraph_identity": id(depsgraph),
                       "temporary_layer": "native readback | all-visible temporary"},
        }
    finally:
        evaluated.to_mesh_clear()


def _unexclude(layer_collection):
    layer_collection.exclude = False
    for child in layer_collection.children:
        _unexclude(child)


def main():
    import bpy

    output = Path(os.environ["SCAN_TO_MODEL_NATIVE_OUTPUT"])
    membership_path = Path(os.environ["SCAN_TO_MODEL_NATIVE_MEMBERSHIP"])
    membership, targets, group_by_name = validate_membership(membership_path)
    model_sha = validate_model_hash(bpy.data.filepath, membership["model_sha256"])
    scene = bpy.context.scene
    original_layer = bpy.context.view_layer.name
    layer_name = "native readback | all-visible temporary"
    if layer_name in scene.view_layers:
        raise RuntimeError("temporary view layer already exists")
    layer = scene.view_layers.new(layer_name)
    original_visibility = {}
    changed_visibility = {}

    def restore_visibility():
        for name, visibility in changed_visibility.items():
            obj = bpy.data.objects.get(name)
            if obj is not None:
                obj.hide_viewport = visibility["hide_viewport"]
        for name, visibility in changed_visibility.items():
            obj = bpy.data.objects.get(name)
            if obj is None or obj.hide_viewport != visibility["hide_viewport"]:
                raise RuntimeError("declared object visibility restoration failed: " + name)
        return True

    try:
        _unexclude(layer.layer_collection)
        declared_objects = {}
        missing = []
        unsupported = []
        for name in targets:
            obj = bpy.data.objects.get(name)
            if obj is None:
                missing.append(name)
                continue
            if obj.type not in CONVERTIBLE_TYPES:
                unsupported.append({"name": name, "type": obj.type})
                continue
            original_visibility[name] = {"hide_viewport": bool(obj.hide_viewport),
                                         "hide_render": bool(obj.hide_render)}
            declared_objects[name] = obj
            if obj.hide_viewport:
                changed_visibility[name] = original_visibility[name]
                obj.hide_viewport = False
        if missing or unsupported:
            raise RuntimeError(json.dumps({"missing": missing, "unavailable": [],
                                           "unsupported": unsupported}, sort_keys=True))
        if bpy.context.window is not None:
            bpy.context.window.view_layer = layer
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        deps_names = {item.name for item in depsgraph.objects}
        rows = []
        unavailable = []
        for name in targets:
            obj = declared_objects[name]
            evaluated = obj.evaluated_get(depsgraph)
            if evaluated is None or evaluated.name not in deps_names:
                unavailable.append(name)
                continue
            if evaluated.original is not obj:
                raise RuntimeError("evaluated/original identity mismatch: " + name)
            rows.append(_object_row(obj, evaluated, depsgraph, deps_names, group_by_name[name], bpy,
                                    original_visibility[name]))
        if missing or unavailable or unsupported:
            raise RuntimeError(json.dumps({"missing": missing, "unavailable": unavailable, "unsupported": unsupported}, sort_keys=True))
        result = {
            "schema_version": 4, "status": "read_only_declared_native_membership",
            "blend_path": bpy.data.filepath, "model_sha256": model_sha,
            "membership_path": str(membership_path), "membership_sha256": sha256(membership_path),
            "room_id": membership["room_id"], "scene": scene.name,
            "original_view_layer": original_layer, "temporary_review_view_layer": layer_name,
            "groups": {group: {"target_count": len(data["target_names"]), "target_names": data["target_names"]}
                        for group, data in membership["groups"].items()},
            "requested_target_names": targets, "requested_target_count": len(targets),
            "target_count": len(rows), "missing_names": missing,
            "unavailable_from_evaluated_depsgraph": unavailable, "unsupported_types": unsupported,
            "depsgraph_object_count": len(deps_names), "all_visible_guard": True, "objects": rows,
            "temporary_visibility_overrides": [
                {"name": name, **visibility, "restored_after_capture": False}
                for name, visibility in changed_visibility.items()],
            "no_save": True, "no_render": True,
            "triangulation": {"method": "Blender evaluated mesh.calc_loop_triangles()",
                              "polygon_index_retained": True},
        }
    finally:
        restore_visibility()
        scene.view_layers.remove(layer)
    for override in result["temporary_visibility_overrides"]:
        override["restored_after_capture"] = True
    output.mkdir(parents=True, exist_ok=True)
    (output / "native-readback.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "requested": len(targets), "captured": len(rows),
                      "depsgraph_objects": len(deps_names)}))


if __name__ == "__main__":
    main()
