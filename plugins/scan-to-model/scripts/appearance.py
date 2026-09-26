"""Bake explicit photographic materials onto unchanged planar surfaces."""

from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates

from delivery_contract import digest, require


def face_frame(vertices):
    vertices = np.asarray(vertices, dtype=float)
    origin = vertices[0]
    normal = sum((np.cross(a - origin, b - origin) for a, b in zip(vertices[1:-1], vertices[2:])), np.zeros(3))
    length = np.linalg.norm(normal)
    require(length > 1e-10, "cannot texture a degenerate face")
    normal /= length
    require(np.max(np.abs((vertices - origin) @ normal)) < 1e-5, "appearance requires planar faces")
    edges = np.roll(vertices, -1, axis=0) - vertices
    u = edges[np.argmax(np.linalg.norm(edges, axis=1))]
    u /= np.linalg.norm(u)
    basis = np.array([u, np.cross(normal, u)])
    local = (vertices - origin) @ basis.T
    low, high = local.min(0), local.max(0)
    return origin + low @ basis, basis, local - low, high - low, normal, length / 2


def project(points, camera, camera_to_world):
    pose = np.asarray(camera_to_world)
    local = (np.asarray(points) - pose[:3, 3]) @ pose[:3, :3]
    depth = -local[:, 2]
    safe = np.where(depth > .001, depth, 1)
    uv = np.column_stack((camera["fx"] * local[:, 0] / safe + camera["cx"],
                          camera["cy"] - camera["fy"] * local[:, 1] / safe))
    valid = (depth > .001) & (uv[:, 0] >= 0) & (uv[:, 1] >= 0)
    valid &= (uv[:, 0] <= camera["width"] - 1) & (uv[:, 1] <= camera["height"] - 1)
    return uv, depth, valid


def depth_visibility(uv, projected_depth, valid, source, tolerance):
    camera, depth, confidence = source["camera"], source["depth_pixels"], source["confidence_pixels"]
    require(depth.ndim == 2 and depth.shape == confidence.shape, "depth/confidence dimensions differ")
    x = np.clip(np.rint(uv[:, 0] * depth.shape[1] / camera["width"]).astype(int), 0, depth.shape[1] - 1)
    y = np.clip(np.rint(uv[:, 1] * depth.shape[0] / camera["height"]).astype(int), 0, depth.shape[0] - 1)
    observed = depth[y, x].astype(float) * source.get("depth_scale", .001)
    difference = np.abs(observed - projected_depth)
    accepted = valid & (confidence[y, x] == source.get("confidence_value", 255))
    accepted &= np.isfinite(observed) & (observed > 0) & (difference <= tolerance)
    if "mask_pixels" in source:
        mask = source["mask_pixels"]
        require(mask.shape == (camera["height"], camera["width"]), "exclusion mask must use native RGB dimensions")
        mx = np.clip(np.rint(uv[:, 0]).astype(int), 0, mask.shape[1] - 1)
        my = np.clip(np.rint(uv[:, 1]).astype(int), 0, mask.shape[0] - 1)
        accepted &= mask[my, mx] > 0
    return accepted, difference


def sample_rgb(pixels, uv):
    return np.column_stack([map_coordinates(pixels[:, :, channel].astype(float),
                            [uv[:, 1], uv[:, 0]], order=1, mode="nearest") for channel in range(3)])


def rectify_sample(pixels, quad, size=256):
    quad = np.asarray(quad, dtype=float)
    require(quad.shape == (4, 2) and np.isfinite(quad).all(), "invalid sample quadrilateral")
    require(((quad >= 0) & (quad <= np.array(pixels.shape[1::-1]) - 1)).all(), "sample leaves source image")
    edges = np.roll(quad, -1, axis=0) - quad
    following = np.roll(edges, -1, axis=0)
    crosses = edges[:, 0]*following[:, 1] - edges[:, 1]*following[:, 0]
    require((crosses > 0).all() or (crosses < 0).all(), "sample quadrilateral must be convex and ordered")
    equations, values = [], []
    for (x, y), (u, v) in zip([[0, 0], [1, 0], [1, 1], [0, 1]], quad):
        equations.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]])
        values.extend([u, v])
    matrix = np.append(np.linalg.solve(equations, values), 1).reshape(3, 3)
    xx, yy = np.meshgrid(np.linspace(0, 1, size), np.linspace(0, 1, size))
    projected = np.column_stack((xx.ravel(), yy.ravel(), np.ones(size*size))) @ matrix.T
    require((np.abs(projected[:, 2]) > 1e-9).all(), "singular sample projection")
    return sample_rgb(pixels, projected[:, :2] / projected[:, 2:]).reshape(size, size, 3)


def normalize_detail(pixels, color, contrast):
    """Reduce broad captured illumination; this is an inferred albedo approximation."""
    low = gaussian_filter(pixels, (max(1, pixels.shape[0]/12), max(1, pixels.shape[1]/12), 0))
    detail = np.clip(pixels / np.maximum(low, 1), 1 - contrast, 1 + contrast)
    return np.clip(detail * np.asarray(color), 0, 255)


def repeated_coordinates(points, mapping, shape):
    local = (np.asarray(points) - mapping["origin"]) @ np.array([mapping["u"], mapping["v"]]).T
    local /= np.array(mapping["size_m"])
    mirrored = 1 - np.abs(np.mod(local, 2) - 1)
    return mirrored * np.array([shape[1] - 1, shape[0] - 1])


def ceiling_height_at(meshes, x, y, floor_z):
    heights = []
    for mesh in meshes:
        for face in mesh["faces"]:
            polygon = np.asarray(mesh["vertices"])[face]
            origin, _, _, _, normal, _ = face_frame(polygon)
            if abs(normal[2]) < .01:
                continue
            inside = False
            for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
                if (a[1] > y) != (b[1] > y) and x < a[0] + (y-a[1]) * (b[0]-a[0]) / (b[1]-a[1]):
                    inside = not inside
            height = origin[2] - ((x-origin[0])*normal[0] + (y-origin[1])*normal[1]) / normal[2]
            if inside and height > floor_z:
                heights.append(float(height))
    return min(heights) if heights else None


def plan_atlas(extents, density, minimum_density, max_size, padding=3):
    """Choose a fitting texel density before allocating or sampling image tiles."""
    attempts = []
    while True:
        sizes = [np.maximum(2, np.ceil(np.asarray(extent) * density).astype(int)).tolist() for extent in extents]
        x = y = row_height = 0
        rectangles = [None] * len(sizes)
        # Group similar tile heights so narrow trim does not waste rows beside large faces.
        for index in sorted(range(len(sizes)), key=lambda index: (sizes[index][1], sizes[index][0]), reverse=True):
            width, height = sizes[index]
            if x + width + 2*padding > max_size:
                x = 0
                y += row_height
                row_height = 0
            rectangles[index] = [x + padding, y + padding, width, height]
            x += width + 2*padding
            row_height = max(row_height, height + 2*padding)
        total = y + row_height
        fits = total <= max_size and all(width + 2*padding <= max_size for width, _ in sizes)
        attempts.append({"density": density, "height": total, "fits": fits})
        if fits:
            height = max(32, 2**int(np.ceil(np.log2(max(1, total)))))
            return {"size": [max_size, min(max_size, height)], "rectangles": rectangles,
                    "density": density, "padding": padding, "attempts": attempts}
        require(density > minimum_density, "atlas exceeds budget even at minimum density")
        density = max(minimum_density, density * .75)


def load_sources(rows):
    result = {}
    for row in rows:
        source = dict(row)
        source["rgb"] = np.asarray(Image.open(row["image"]).convert("RGB"))
        if "camera" in row:
            require(source["rgb"].shape[:2] == (row["camera"]["height"], row["camera"]["width"]),
                    "source image and calibration dimensions differ")
        for key in ["depth", "confidence", "mask"]:
            if key in row:
                source[key + "_pixels"] = np.asarray(Image.open(row[key]))
        result[row["id"]] = source
    return result


def bake_face(vertices, material, sources, size, sample=None):
    width, height = size
    origin, basis, polygon, extent, normal, area = face_frame(vertices)
    uu, vv = np.meshgrid((np.arange(width)+.5)/width*extent[0], (np.arange(height)+.5)/height*extent[1])
    points = origin + np.column_stack((uu.ravel(), vv.ravel())) @ basis
    mask = Image.new("L", (width, height))
    ImageDraw.Draw(mask).polygon([tuple(point) for point in polygon / extent * [width, height]], fill=255)
    inside = np.asarray(mask) > 0
    pixels = np.broadcast_to(np.array(material["color"], dtype=float), (height, width, 3)).copy()
    coverage = np.zeros((height, width), dtype=bool)
    contributions = Counter()
    if material["method"] == "repeated-photo":
        uv = repeated_coordinates(points, material["mapping"], sample.shape)
        pixels = sample_rgb(sample, uv).reshape(height, width, 3)
    elif material["method"] == "photo-projection":
        colors = np.zeros((len(points), 3))
        weights = np.zeros(len(points))
        for ident in material["sources"]:
            source = sources[ident]
            uv, depth, valid = project(points, source["camera"], source["camera_to_world"])
            valid, residual = depth_visibility(uv, depth, valid, source, material.get("depth_tolerance_m", .1))
            view = np.asarray(source["camera_to_world"])[:3, 3] - points
            distance = np.linalg.norm(view, axis=1)
            cosine = np.abs(view @ normal) / np.maximum(distance, .001)
            rgb = sample_rgb(source["rgb"], uv)
            valid &= inside.ravel() & (cosine > .3) & (np.min(rgb, axis=1) < 248)
            weight = np.where(valid, cosine**4 / np.maximum(distance, .1), 0)
            weight *= np.exp(-(residual / material.get("depth_tolerance_m", .1))**2)
            colors += rgb * weight[:, None]
            weights += weight
            contributions[ident] = int((weight > 0).sum())
        coverage = (weights > 0).reshape(height, width) & inside
        if coverage.any():
            observed = (colors / np.maximum(weights[:, None], 1e-12)).reshape(height, width, 3)
            _, nearest = distance_transform_edt(~coverage, return_indices=True)
            filled = observed[tuple(nearest)]
            if "detail_contrast" in material:
                filled = normalize_detail(filled, material["color"], material["detail_contrast"])
            pixels[coverage] = filled[coverage]
    if not inside.all():
        _, nearest = distance_transform_edt(~inside, return_indices=True)
        pixels = pixels[tuple(nearest)]
    return np.rint(np.clip(pixels, 0, 255)).astype(np.uint8), {
        "uv": (polygon / extent).tolist(), "area_m2": float(area),
        "photo_coverage": float(coverage.sum() / max(1, inside.sum())),
        "source_contributions": dict(contributions), "method": material["method"],
        "inferred_continuation": material["method"] in {"inferred", "repeated-photo", "photo-projection"}}


def bake(job, scene, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    materials = {row["id"]: row for row in job.get("materials", [])}
    meshes = {row["id"]: row for row in scene["objects"]}
    faces = []
    for obj in job["objects"]:
        material = materials.get(obj.get("material"))
        if not material or material["method"] not in {"photo-projection", "repeated-photo"}:
            continue
        mesh = meshes[obj["id"]]
        require(mesh["type"] == "MESH" and not mesh["modifiers"], "apply topology-changing modifiers before photo mapping")
        for index, face in enumerate(mesh["faces"]):
            vertices = np.asarray(mesh["vertices"])[face]
            frame = face_frame(vertices)
            faces.append({"object": obj["id"], "face": index, "vertices": vertices, "extent": frame[3], "material": material})
    result = {"materials": materials, "faces": [], "atlas": None, "planning": None}
    if not faces:
        return result
    options = job.get("texture", {})
    plan = plan_atlas([face["extent"] for face in faces], options.get("density", 128),
                      options.get("minimum_density", 16), options.get("max_size", 2048))
    result["planning"] = plan
    atlas = np.zeros((plan["size"][1], plan["size"][0], 3), dtype=np.uint8)
    sources = load_sources(job["sources"])
    samples = {}
    for ident, material in materials.items():
        if material["method"] == "repeated-photo":
            sample = material["sample"]
            pixels = rectify_sample(sources[sample["source"]]["rgb"], sample["quad"])
            if "detail_contrast" in material:
                pixels = normalize_detail(pixels, material["color"], material["detail_contrast"])
            samples[ident] = pixels
    for face, rectangle in zip(faces, plan["rectangles"]):
        x, y, width, height = rectangle
        pixels, record = bake_face(face["vertices"], face["material"], sources, [width, height], samples.get(face["material"]["id"]))
        pad = plan["padding"]
        atlas[y-pad:y+height+pad, x-pad:x+width+pad] = np.pad(pixels, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        uv = np.asarray(record["uv"])
        record.update(object=face["object"], face=face["face"], material=face["material"]["id"],
                      uv=np.column_stack(((x+uv[:, 0]*width)/plan["size"][0], 1-(y+uv[:, 1]*height)/plan["size"][1])).tolist())
        result["faces"].append(record)
    image = directory / "atlas.png"
    Image.fromarray(atlas).save(image)
    result["atlas"] = {"path": str(image.resolve()), "sha256": digest(image)}
    return result
