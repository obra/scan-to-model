"""Measure photographed surface patches using their native depth samples."""

import argparse
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import ConvexHull

from polycam import camera_matrix, digest, read_frame, unproject
from pixel_inspection import coordinate_inspection_bytes, native_pixel_center, patch_inspection_bytes


def _finite_array(value, shape, label):
    try:
        array = np.asarray(value, float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a finite array") from error
    if array.shape != shape or not np.isfinite(array).all():
        raise ValueError(f"{label} must be a finite array with shape {shape}")
    return array


def _rigid_matrix(transform):
    matrix = _finite_array(transform, (4, 4), "Transform")
    rotation = matrix[:3, :3]
    if not np.allclose(matrix[3], [0., 0., 0., 1.], atol=1e-7, rtol=0):
        raise ValueError("Transform must be homogeneous")
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6, rtol=0):
        raise ValueError("Transform must contain a rigid rotation")
    if not np.isclose(np.linalg.det(rotation), 1., atol=1e-6, rtol=0):
        raise ValueError("Transform must contain a proper rigid rotation")
    return matrix


def transform_plane(normal, offset, transform):
    """Transform the explicit plane equation ``normal @ point = offset``."""
    normal = _finite_array(normal, (3,), "Plane normal")
    if np.linalg.norm(normal) <= 1e-12:
        raise ValueError("Plane normal must be nonzero")
    scalar = np.asarray(offset, float)
    if scalar.ndim or not np.isfinite(scalar).all():
        raise ValueError("Plane offset must be a finite scalar")
    matrix = _rigid_matrix(transform)
    transformed_normal = matrix[:3, :3] @ normal
    transformed_offset = float(scalar + transformed_normal @ matrix[:3, 3])
    return transformed_normal, transformed_offset


def _point_on_segment(point, start, end, tolerance):
    edge = end - start
    length = np.linalg.norm(edge)
    if length == 0:
        return np.linalg.norm(point - start) <= tolerance
    parameter = (point - start) @ edge / (length * length)
    if parameter < -tolerance / length or parameter > 1. + tolerance / length:
        return False
    cross = edge[0] * (point - start)[1] - edge[1] * (point - start)[0]
    return abs(cross) / length <= tolerance


def _segments_intersect(first_start, first_end, second_start, second_end, tolerance):
    def cross(first, second):
        return first[0] * second[1] - first[1] * second[0]

    first_edge = first_end - first_start
    second_edge = second_end - second_start
    scale = max(np.linalg.norm(first_edge), np.linalg.norm(second_edge), 1e-12)
    epsilon = tolerance * scale
    orientations = np.array([
        cross(first_edge, second_start - first_start),
        cross(first_edge, second_end - first_start),
        cross(second_edge, first_start - second_start),
        cross(second_edge, first_end - second_start),
    ])
    if (abs(orientations[0]) <= epsilon
            and _point_on_segment(second_start, first_start, first_end, tolerance)):
        return True
    if (abs(orientations[1]) <= epsilon
            and _point_on_segment(second_end, first_start, first_end, tolerance)):
        return True
    if (abs(orientations[2]) <= epsilon
            and _point_on_segment(first_start, second_start, second_end, tolerance)):
        return True
    if (abs(orientations[3]) <= epsilon
            and _point_on_segment(first_end, second_start, second_end, tolerance)):
        return True
    if np.all(np.abs(orientations) <= epsilon):
        return True
    return ((orientations[0] > epsilon and orientations[1] < -epsilon)
            or (orientations[0] < -epsilon and orientations[1] > epsilon)) and (
                (orientations[2] > epsilon and orientations[3] < -epsilon)
                or (orientations[2] < -epsilon and orientations[3] > epsilon))


def _planar_polygon(polygon, planarity_tolerance, boundary_tolerance):
    polygon = np.asarray(polygon, float)
    if polygon.ndim != 2 or polygon.shape[1] != 3 or len(polygon) < 3:
        raise ValueError("Planar polygons require at least three 3-D vertices")
    if not np.isfinite(polygon).all():
        raise ValueError("Planar polygon vertices must be finite")
    relative = polygon - polygon[0]
    area_vector = sum(np.cross(relative[index], relative[(index + 1) % len(relative)])
                      for index in range(len(relative)))
    edge_scale = max(np.linalg.norm(relative[index] - relative[(index + 1) % len(relative)])
                     for index in range(len(relative)))
    if np.linalg.norm(area_vector) <= 1e-12 * edge_scale**2:
        raise ValueError("Planar polygon is degenerate")
    normal = area_vector / np.linalg.norm(area_vector)
    if np.max(np.abs(relative @ normal)) > planarity_tolerance:
        raise ValueError("Planar polygon vertices are not coplanar")
    reference = np.eye(3)[np.argmin(np.abs(normal))]
    along = np.cross(reference, normal)
    along /= np.linalg.norm(along)
    across = np.cross(normal, along)
    coordinates = np.column_stack((relative @ along, relative @ across))
    for first_index in range(len(coordinates)):
        first_start = coordinates[first_index]
        first_end = coordinates[(first_index + 1) % len(coordinates)]
        for second_index in range(first_index + 1, len(coordinates)):
            if (second_index == first_index + 1
                    or first_index == 0 and second_index == len(coordinates) - 1):
                continue
            second_start = coordinates[second_index]
            second_end = coordinates[(second_index + 1) % len(coordinates)]
            if _segments_intersect(first_start, first_end, second_start, second_end,
                                   boundary_tolerance):
                raise ValueError("Planar polygon ring is not simple")
    return polygon[0], normal, along, across, coordinates


def _projected_polygon_contains(points, polygon, origin, normal, along, across, tolerance):
    relative = points - origin
    projected = relative - np.outer(relative @ normal, normal)
    coordinates = np.column_stack((projected @ along, projected @ across))
    inside = np.zeros(len(points), dtype=bool)
    boundary = np.zeros(len(points), dtype=bool)
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        edge = end - start
        length_squared = edge @ edge
        if length_squared == 0:
            boundary |= np.linalg.norm(coordinates - start, axis=1) <= tolerance
            continue
        parameter = np.clip(((coordinates - start) @ edge) / length_squared, 0., 1.)
        nearest = start + parameter[:, None] * edge
        boundary |= np.linalg.norm(coordinates - nearest, axis=1) <= tolerance
        crosses = (start[1] > coordinates[:, 1]) != (end[1] > coordinates[:, 1])
        crossing_x = np.zeros(len(points))
        if edge[1] != 0:
            crossing_x = start[0] + (coordinates[:, 1] - start[1]) * edge[0] / edge[1]
        inside ^= crosses & (coordinates[:, 0] < crossing_x)
    return boundary | inside


def compare_points_to_planar_polygons(points, polygons, *, source_normal=None,
                                       planarity_tolerance=1e-7, boundary_tolerance=1e-9):
    """Compare source points with a union of actual planar polygon footprints.

    Each input point is retained in the returned arrays and receives at most one
    signed plane residual. Points whose orthogonal projection is inside several
    polygons use the closest supporting plane; ties use polygon input order.
    Polygon vertex winding controls signs unless ``source_normal`` is supplied,
    in which case each polygon normal is flipped toward that source direction.
    """
    points = np.asarray(points, float)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("Points must be a finite array with shape (N, 3)")
    for value, label in ((planarity_tolerance, "Planarity tolerance"),
                         (boundary_tolerance, "Boundary tolerance")):
        scalar = np.asarray(value, float)
        if scalar.ndim or not np.isfinite(scalar).all() or scalar < 0:
            raise ValueError(f"{label} must be finite and nonnegative")
    if source_normal is not None:
        source_normal = _finite_array(source_normal, (3,), "Source normal")
        length = np.linalg.norm(source_normal)
        if length <= 1e-12:
            raise ValueError("Source normal must be nonzero")
        source_normal = source_normal / length
    try:
        polygons = list(polygons)
    except TypeError as error:
        raise ValueError("Polygons must be an iterable of 3-D vertex arrays") from error
    residuals = np.full(len(points), np.nan)
    supporting = np.full(len(points), -1, dtype=int)
    nearest_distance = np.full(len(points), np.inf)
    normals = []
    offsets = []
    for index, polygon in enumerate(polygons):
        origin, normal, along, across, coordinates = _planar_polygon(
            polygon, planarity_tolerance, boundary_tolerance)
        if source_normal is not None:
            alignment = normal @ source_normal
            if abs(alignment) <= 1e-12:
                raise ValueError("Source normal is orthogonal to a polygon normal")
            if alignment < 0:
                normal = -normal
        signed = (points - origin) @ normal
        inside = _projected_polygon_contains(
            points, coordinates, origin, normal, along, across, boundary_tolerance)
        distance = np.abs(signed)
        selected = inside & (distance < nearest_distance)
        residuals[selected] = signed[selected]
        supporting[selected] = index
        nearest_distance[selected] = distance[selected]
        normals.append(normal)
        offsets.append(float(normal @ origin))
    overlap = supporting >= 0
    return {
        "points": points.copy(),
        "overlap_mask": overlap,
        "overlap_indices": np.flatnonzero(overlap),
        "overlap_count": int(overlap.sum()),
        "supporting_polygon": supporting,
        "residuals": residuals,
        "statistics": stats(np.abs(residuals[overlap])) if overlap.any() else None,
        "polygon_normals": np.asarray(normals).reshape((-1, 3)),
        "polygon_offsets": np.asarray(offsets),
        "normal_convention": "source-aligned" if source_normal is not None else "vertex-winding",
        "source_normal": None if source_normal is None else source_normal.copy(),
        "residual_definition": "signed distance to n @ point = d; absolute values are used for statistics",
    }


def fit_plane(points, rejection_m):
    keep = np.ones(len(points), dtype=bool)
    for _ in range(5):
        center = points[keep].mean(axis=0)
        _, singular, axes = np.linalg.svd(points[keep]-center, full_matrices=False)
        if singular[1] < 1e-8:
            raise ValueError("Surface samples do not span a plane")
        residual = np.abs((points-center) @ axes[-1])
        updated = residual <= rejection_m
        if updated.sum() < 30:
            raise ValueError("Fewer than 30 samples satisfy the plane rejection threshold")
        if np.array_equal(updated, keep):
            break
        keep = updated
    center = points[keep].mean(axis=0)
    _, singular, axes = np.linalg.svd(points[keep]-center, full_matrices=False)
    if singular[1] < 1e-8:
        raise ValueError("Surface samples do not span a plane")
    residual = np.abs((points-center) @ axes[-1])
    keep = residual <= rejection_m
    if keep.sum() < 30:
        raise ValueError("Fewer than 30 samples satisfy the plane rejection threshold")
    return center, axes[-1], axes[:2], keep, residual


def stats(values):
    return {"median":float(np.median(values)), "p95":float(np.percentile(values,95)),
            "max":float(np.max(values))} if len(values) else None


def resolve(path, parent):
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("Every patch requires a capture directory")
    path = Path(path).expanduser()
    return path.resolve() if path.is_absolute() else (parent/path).resolve()


def tracking_scope(camera, patch, defaults):
    if "tracking_segment" in patch:
        declared = patch["tracking_segment"]
        declaration_present = True
    elif "tracking_segment" in defaults:
        declared = defaults["tracking_segment"]
        declaration_present = True
    else:
        declared = None
        declaration_present = False
    actual = camera.get("tracking_segment")
    if declaration_present and (isinstance(declared, bool) or not isinstance(declared, int)):
        raise ValueError("Declared tracking segment must be an integer")
    if actual is not None and (isinstance(actual, bool) or not isinstance(actual, int)):
        raise ValueError("Camera tracking segment must be an integer or null")
    if declared is not None and actual is None:
        raise ValueError("Camera tracking segment is unavailable for the declared segment")
    if declared is not None and actual != declared:
        raise ValueError(f"Camera tracking segment {actual} does not match declared segment {declared}")
    return declared, actual


def measured_patch(patch, defaults, parent, output, pixel_inspections=False):
    name = patch["id"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError("Patch IDs must be safe file names")
    source = resolve(patch.get("capture", defaults.get("capture")), parent)
    frame = str(patch["frame_id"])
    depth_variant = patch.get("depth_variant", defaults.get("depth_variant", "raw"))
    pose_variant = patch.get("pose_variant", defaults.get("pose_variant", "raw"))
    camera, depth, confidence, rgb = read_frame(source,frame,depth_variant,pose_variant)
    raw_camera = (camera if pose_variant == "raw" else json.loads(
        (source/"keyframes/cameras"/f"{frame}.json").read_text()))
    declared_segment, camera_segment = tracking_scope(raw_camera, patch, defaults)
    maximum = float(defaults.get("max_depth_m", 5))
    selected_confidence = defaults.get("confidence_value", 255)
    if not isinstance(selected_confidence, int) or not 0 <= selected_confidence <= 255:
        raise ValueError("confidence_value must be an integer from 0 to 255")
    if not np.isfinite(maximum) or maximum <= 0:
        raise ValueError("max_depth_m must be positive and finite")
    points, uv = unproject(depth,confidence,camera,maximum,selected_confidence)
    orientation = patch.get("orientation", defaults.get("orientation", "upright90cw"))
    if orientation not in {"raw", "upright90cw"}:
        raise ValueError("orientation must be raw or upright90cw")
    height,width = rgb.shape[:2]
    shown = rgb if orientation == "raw" else np.rot90(rgb,k=3)
    polygon = np.asarray(patch["polygon_px"],float)
    if polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon)<3 or not np.isfinite(polygon).all():
        raise ValueError(f"Invalid polygon: {name}")
    if (polygon<0).any() or (polygon[:,0]>=shown.shape[1]).any() or (polygon[:,1]>=shown.shape[0]).any():
        raise ValueError(f"Polygon outside image: {name}")
    mask_image = Image.new("1",(shown.shape[1],shown.shape[0]))
    ImageDraw.Draw(mask_image).polygon([tuple(p) for p in polygon],fill=1)
    mask = np.array(mask_image)
    v,u = np.indices(depth.shape)
    raw_x = np.rint(u*width/depth.shape[1]).astype(int)
    raw_y = np.rint(v*height/depth.shape[0]).astype(int)
    raw_x = np.clip(raw_x,0,width-1);raw_y = np.clip(raw_y,0,height-1)
    native_mask = mask[raw_y,raw_x] if orientation == "raw" else mask[raw_x,height-1-raw_y]
    selected = native_mask[uv[:,1],uv[:,0]]
    points,uv = points[selected],uv[selected]
    matrix = np.array(patch.get("transform", defaults.get("transform",np.eye(4))),float)
    if matrix.shape!=(4,4) or not np.isfinite(matrix).all() or not np.allclose(matrix[3],[0,0,0,1]):
        raise ValueError("Expected a finite homogeneous transform")
    if not np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),atol=1e-5) or np.linalg.det(matrix[:3,:3])<.99999:
        raise ValueError("Only rigid metre transforms are accepted")
    transformed = points@matrix[:3,:3].T+matrix[:3,3]
    eligible = (confidence==selected_confidence)&(depth>0)&(depth<=maximum*1000)
    native_count = int(native_mask.sum())
    row = {"id":name,"capture":str(source),"frame_id":frame,"physical_surface":patch["physical_surface"],
           "orientation":orientation,"polygon_px":polygon.tolist(),"depth_variant":depth_variant,"pose_variant":pose_variant,
           "declared_tracking_segment":declared_segment,"camera_tracking_segment":camera_segment,
           "max_depth_m":maximum,"confidence_value":selected_confidence,"native_patch_pixels":native_count,
           "eligible_pixels":len(points),"eligible_fraction":len(points)/native_count if native_count else 0,
           "transform":matrix.tolist(),"analysis_frame":defaults.get("analysis_frame",str(source)),
           "camera_position":(camera_matrix(camera)[:3,3]@matrix[:3,:3].T+matrix[:3,3]).tolist(),
           "notes":patch.get("notes",""),"fit_status":"not fitted","plane":None}
    keep = np.zeros(len(points),dtype=bool)
    sample = None
    if patch.get("fit",True) and len(points)>=30:
        rejection = float(defaults.get("rejection_m",.02))
        if not np.isfinite(rejection) or rejection<=0:
            raise ValueError("rejection_m must be positive and finite")
        row["rejection_m"] = rejection
        try:
            center,normal,basis,keep,residual = fit_plane(transformed,rejection)
        except ValueError as error:
            row["fit_status"] = f"plane not fitted: {error}"
        else:
            up = matrix[:3,:3]@np.array([0.,1.,0.])
            if normal@up<0:normal=-normal
            row["plane"] = {"center_m":center.tolist(),"normal":normal.tolist(),"offset_m":float(center@normal),
                            "inlier_count":int(keep.sum()),"rejected_count":int((~keep).sum()),
                            "all_residual_m":stats(residual),"inlier_residual_m":stats(residual[keep]),
                            "tilt_from_capture_up_degrees":float(np.degrees(np.arccos(np.clip(abs(normal@up),0,1)))),
                            "inlier_bounds_m":[transformed[keep].min(0).tolist(),transformed[keep].max(0).tolist()]}
            row["fit_status"] = "free plane; interpretation requires photo review"
            sample = dict(points=transformed[keep],center=center,normal=normal,basis=basis)
    elif patch.get("fit",True):
        row["fit_status"] = "fewer than 30 eligible native samples"
    suffix = "" if depth_variant=="raw" else ".Clean"
    files = {"rgb":source/"keyframes/images"/f"{frame}.jpg", "depth":source/"keyframes/depth"/f"{frame}{suffix}.png",
             "confidence":source/"keyframes/confidence"/f"{frame}{suffix}.png","raw_camera":source/"keyframes/cameras"/f"{frame}.json"}
    if pose_variant=="corrected":files["corrected_camera"]=source/"keyframes/corrected_cameras"/f"{frame}.json"
    row["sources"] = {k:{"path":str(p),"sha256":digest(p)} for k,p in files.items()}
    np.savez_compressed(output/f"{name}.npz",raw_points=points,points=transformed,pixels=uv,inlier_mask=keep)
    row["samples"] = f"{name}.npz"
    z=depth.astype(float)/1000;z[~eligible]=np.nan
    if orientation!="raw":z=np.rot90(z,k=3)
    fig,axes=plt.subplots(1,2,figsize=(10,7.4),layout="constrained")
    axes[0].imshow(shown);axes[0].set_title("Source photo and selected surface")
    cmap=plt.get_cmap("viridis").copy();cmap.set_bad("#dddddd")
    heat=axes[1].imshow(z,extent=(0,shown.shape[1]-1,shown.shape[0]-1,0),interpolation="nearest",vmin=0,vmax=maximum,cmap=cmap)
    axes[1].set_title("Native depth after confidence/range filter")
    for ax in axes:
        ax.add_patch(Polygon(polygon,fill=False,edgecolor="#ff743f",linewidth=2));ax.axis("off")
    fig.colorbar(heat,ax=axes[1],shrink=.75,label="Camera-axis depth (m)")
    fig.suptitle(f"{name} | {frame}\n{len(points)} eligible / {native_count} native patch pixels; gray = rejected or missing",fontsize=10)
    fig.savefig(output/f"{name}.jpg",dpi=150);plt.close(fig)
    row["figure"] = f"{name}.jpg"
    if pixel_inspections:
        source_image = {"width":width,"height":height,"orientation":orientation}
        display_coordinates = polygon.tolist()
        native_coordinates = [native_pixel_center(point, source_image) for point in display_coordinates]
        annotation = {"native_coordinates":native_coordinates,"display_coordinates":display_coordinates}
        displayed = Image.fromarray(shown).convert("RGBA")
        patch_image, patch_record = patch_inspection_bytes(source_image,displayed,display_coordinates)
        vertex_image, coordinates = coordinate_inspection_bytes(source_image,displayed,annotation)
        patch_path, vertex_path = output/f"{name}-patch.png",output/f"{name}-vertices.png"
        patch_path.write_bytes(patch_image);vertex_path.write_bytes(vertex_image)
        row["pixel_inspection"] = {
            "status":"pending visual review","source_rgb":row["sources"]["rgb"],
            "polygon_native_pixel_centers":native_coordinates,"polygon_display_pixel_centers":display_coordinates,
            "patch":{"path":patch_path.name,"sha256":digest(patch_path),**patch_record},
            "vertices":{"path":vertex_path.name,"sha256":digest(vertex_path),
                        "resampling":"nearest","nearest_pixel_rule":"floor(coordinate + 0.5) in native pixel-center coordinates",
                        "coordinates":coordinates},
            "limits":["Enlargement adds no source detail and does not accept the polygon's physical interpretation.",
                      "Vertex inspection does not establish pure surface support for every selected depth cell."]}
    return row,sample


def compare(first, second, samples, records):
    a,b=samples[first],samples[second]
    out={"first":first,"second":second,"status":"not measured"}
    if a is None or b is None:return out
    if records[first]["analysis_frame"]!=records[second]["analysis_frame"]:
        raise ValueError("Comparisons require a shared analysis frame and explicit transforms")
    if records[first]["analysis_frame"] == records[first]["capture"] and records[first]["transform"] != records[second]["transform"]:
        raise ValueError("Different transforms require an explicitly named shared analysis_frame")
    if records[first]["physical_surface"]!=records[second]["physical_surface"]:
        raise ValueError("Repeat comparisons must identify the same physical surface")
    pa=(a["points"]-a["center"])@a["basis"].T
    pb=(b["points"]-a["center"])@a["basis"].T
    hull=ConvexHull(pb)
    shared=(pa@hull.equations[:,:2].T+hull.equations[:,2]<=1e-9).all(1)
    sites=pa[shared]@a["basis"]+a["center"]
    out.update(status="local plane comparison; not absolute accuracy",overlap_samples=int(shared.sum()),
               plane_separation_m=stats(np.abs((sites-b["center"])@b["normal"])),
               normal_angle_degrees=float(np.degrees(np.arccos(np.clip(abs(a["normal"]@b["normal"]),0,1)))))
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--pixel-inspections",action="store_true")
    args=parser.parse_args();spec_path=args.spec.resolve();spec=json.loads(spec_path.read_text())
    output=args.output.resolve()
    if spec_path == output/"measurements.json":
        raise ValueError("Output must not overwrite the input specification")
    if not isinstance(spec.get("patches"),list) or not spec["patches"]:
        raise ValueError("At least one reviewed surface patch is required")
    output.mkdir(parents=True,exist_ok=True)
    records={};samples={}
    for patch in spec["patches"]:
        if patch["id"] in records:raise ValueError("Duplicate patch ID")
        row,sample=measured_patch(patch,spec,spec_path.parent,output,pixel_inspections=args.pixel_inspections)
        records[row["id"]]=row;samples[row["id"]]=sample
    result={"spec":{"path":str(spec_path),"sha256":digest(spec_path)},"patches":list(records.values()),
            "comparisons":[compare(pair[0],pair[1],samples,records) for pair in spec.get("comparisons",[])],
            "limits":["Native sample support is not physical accuracy.","Planes require physical surface segmentation and photo review.",
                      "Rejected fit samples remain in NPZ and all-sample residual statistics.","Nearby frames may share depth/pose errors."]}
    (output/"measurements.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"output":str(output),"patches":len(records),"comparisons":result["comparisons"]},allow_nan=False))


if __name__=="__main__":main()
