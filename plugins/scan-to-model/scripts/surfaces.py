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


def measured_patch(patch, defaults, parent, output):
    name = patch["id"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError("Patch IDs must be safe file names")
    source = resolve(patch.get("capture", defaults.get("capture")), parent)
    frame = str(patch["frame_id"])
    depth_variant = patch.get("depth_variant", defaults.get("depth_variant", "raw"))
    pose_variant = patch.get("pose_variant", defaults.get("pose_variant", "raw"))
    camera, depth, confidence, rgb = read_frame(source,frame,depth_variant,pose_variant)
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
        row,sample=measured_patch(patch,spec,spec_path.parent,output)
        records[row["id"]]=row;samples[row["id"]]=sample
    result={"spec":{"path":str(spec_path),"sha256":digest(spec_path)},"patches":list(records.values()),
            "comparisons":[compare(pair[0],pair[1],samples,records) for pair in spec.get("comparisons",[])],
            "limits":["Native sample support is not physical accuracy.","Planes require physical surface segmentation and photo review.",
                      "Rejected fit samples remain in NPZ and all-sample residual statistics.","Nearby frames may share depth/pose errors."]}
    (output/"measurements.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"output":str(output),"patches":len(records),"comparisons":result["comparisons"]},allow_nan=False))


if __name__=="__main__":main()
